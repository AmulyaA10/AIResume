# services/ai/resume_validation_graph.py
from typing import TypedDict, Optional, List
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
import json

from services.ai.common import get_llm, clean_json_output


# ---------- State ----------
class ResumeValidationState(TypedDict):
    file_name: str
    file_type: str
    extracted_text: str
    target_role: Optional[str]
    validation_result: Optional[dict]
    config: Optional[dict]


# ---------- Score validation helpers ----------
def _clamp(value, lo=0, hi=5):
    """Clamp a score to 0-5 range."""
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return 0


def _classify_by_score(total: int, is_resume: bool) -> str:
    """Enforce classification rules based on total score."""
    if not is_resume:
        return "not_resume"
    if total <= 10:
        return "resume_invalid_or_incomplete"
    if total <= 17:
        return "resume_valid_but_weak"
    if total <= 24:
        return "resume_valid_good"
    return "resume_valid_strong"


# ---------- Agent ----------
def validation_agent(state: ResumeValidationState):
    llm = get_llm(state.get("config"), temperature=0)

    prompt = PromptTemplate(
        input_variables=["file_name", "file_type", "extracted_text", "target_role"],
        template="""You are a Resume Validation Agent.

Your job is to analyze extracted text from a candidate document and determine:
1) Whether the document is a valid resume
2) Whether it is complete and usable for screening
3) Whether it has credibility red flags
4) Whether it is ATS-friendly
5) A structured validation report with scores and reasons

IMPORTANT RULES:
- Be strict but fair.
- Do not assume missing information exists if it is not present in the text.
- If the text appears incomplete due to parsing issues (garbled text, broken layout, OCR errors), explicitly mention "possible parsing issue".
- Distinguish between "Not a resume", "Resume but incomplete/weak", and "Valid and strong resume".
- Do not invent facts. If uncertain, state uncertainty clearly.

DOCUMENT METADATA:
- File name: {file_name}
- File type: {file_type}
- Target role (if provided): {target_role}

EXTRACTED TEXT:
{extracted_text}

EVALUATION CRITERIA:

A) DOCUMENT TYPE CHECK
Check whether the text contains resume-like sections/content: candidate name and contact information, work experience/employment history, education, skills, optional sections (summary, projects, certifications, awards, publications). If the document looks like a cover letter, biography, essay, invoice, certificate, or random notes instead of a resume, mark it invalid.

B) COMPLETENESS CHECK
Evaluate whether the resume includes: name, email (or phone/contact method), work experience entries with company/title/date, education, skills, reasonable chronology and enough details to screen candidate.

C) STRUCTURE & READABILITY
Evaluate: clear section headings, reverse chronological order (preferred), consistent date formatting, bullet usage/scannability, formatting consistency (inferred from text structure), excessive noise (headers/footers repeated, broken lines, parser artifacts).

D) ACHIEVEMENT QUALITY
Check if experience bullets are: responsibility-only (weak), mixed responsibility + impact (okay), or impact/achievement focused with metrics (strong).

E) CREDIBILITY & CONSISTENCY CHECK
Identify possible red flags: date inconsistencies or overlaps, missing dates on major roles, unrealistic claims without context, buzzword-heavy skills with no evidence, too many vague statements with no specifics, inconsistent progression, education/certifications missing institutions or dates, contact info looks suspicious or missing.

F) ATS FRIENDLINESS CHECK
Evaluate: standard section names (Experience, Education, Skills), text appears machine-readable, important content not likely hidden in tables/images, date formats parseable, keyword relevance to target_role (if provided).

G) SCORING (0-5 each):
- document_type_validity
- completeness
- structure_readability
- achievement_quality
- credibility_consistency
- ats_friendliness
Also calculate total_score out of 30.

H) CLASSIFICATION (based on total score):
- "not_resume": document is not a resume
- "resume_invalid_or_incomplete": total 0-10, major sections missing or unusable
- "resume_valid_but_weak": total 11-17, resume but needs significant work
- "resume_valid_good": total 18-24, solid resume with minor improvements needed
- "resume_valid_strong": total 25-30, excellent resume

I) ACTIONABLE FEEDBACK:
Provide specific, actionable items for each category.

Return ONLY valid JSON:
{{
  "is_resume": true,
  "classification": "resume_valid_good",
  "scores": {{
    "document_type_validity": 5,
    "completeness": 4,
    "structure_readability": 3,
    "achievement_quality": 4,
    "credibility_consistency": 5,
    "ats_friendliness": 3
  }},
  "total_score": 24,
  "missing_fields": ["linkedin_url"],
  "top_issues": ["Issue 1", "Issue 2"],
  "suggested_improvements": ["Improvement 1", "Improvement 2"],
  "followup_verification_questions": ["Question 1"],
  "summary": "Brief overall assessment of the document."
}}
"""
    )

    try:
        response = llm.invoke(prompt.format(
            file_name=state["file_name"],
            file_type=state.get("file_type", "unknown"),
            extracted_text=state["extracted_text"],
            target_role=state.get("target_role") or "Not specified"
        ))

        clean_content = clean_json_output(response.content)
        result = json.loads(clean_content)

        # --- Python-side validation to prevent LLM hallucinations ---
        scores = result.get("scores", {})
        score_keys = [
            "document_type_validity", "completeness", "structure_readability",
            "achievement_quality", "credibility_consistency", "ats_friendliness"
        ]
        for key in score_keys:
            scores[key] = _clamp(scores.get(key, 0))
        result["scores"] = scores

        # Recalculate total from individual scores
        total = sum(scores[k] for k in score_keys)
        result["total_score"] = total

        # Enforce classification rules
        is_resume = result.get("is_resume", True)
        result["classification"] = _classify_by_score(total, is_resume)

        # Ensure list fields are lists
        for list_key in ["missing_fields", "top_issues", "suggested_improvements", "followup_verification_questions"]:
            if not isinstance(result.get(list_key), list):
                result[list_key] = []

        # Ensure summary is a string
        if not isinstance(result.get("summary"), str):
            result["summary"] = ""

        return {"validation_result": result}

    except Exception as e:
        return {
            "validation_result": {
                "is_resume": False,
                "classification": "not_resume",
                "scores": {k: 0 for k in [
                    "document_type_validity", "completeness", "structure_readability",
                    "achievement_quality", "credibility_consistency", "ats_friendliness"
                ]},
                "total_score": 0,
                "missing_fields": [],
                "top_issues": [f"Validation error: {str(e)}"],
                "suggested_improvements": [],
                "followup_verification_questions": [],
                "summary": f"Validation failed due to an error: {str(e)}",
                "error": str(e)
            }
        }


# ---------- Graph ----------
def build_resume_validation_graph():
    graph = StateGraph(ResumeValidationState)
    graph.add_node("validate", validation_agent)
    graph.set_entry_point("validate")
    graph.add_edge("validate", END)
    return graph.compile()
