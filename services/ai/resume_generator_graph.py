from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
import json

from services.ai.common import get_llm, clean_json_output

class GeneratorState(TypedDict):
    profile_description: str
    refinement_instructions: Optional[str]
    resume_json: Optional[dict]
    config: Optional[dict]

def generator_agent(state: GeneratorState):
    llm = get_llm(state.get("config"))
    refinement_instructions = state.get("refinement_instructions") or ""

    is_refinement = bool(refinement_instructions.strip())

    if is_refinement:
        template = """
You are an expert resume editor. You are given an EXISTING resume and a list of specific improvements to apply.
Your job is to preserve factual content while improving ATS performance, clarity, and consistency.
Do NOT invent or fabricate facts. Do NOT drop real content.

CONTACT EXTRACTION RULE: Scan the entire resume text for contact details — name, email, phone, LinkedIn URL, location.
If a LinkedIn URL appears anywhere in the text (e.g. "LinkedIn: https://..."), extract and put it in contact.linkedin.
Do NOT fabricate contact details that are not present in the text.

LAYOUT + ATS RULES:
- Always output a clean, standard structure: summary, skills, experience, education.
- Ensure consistent formatting throughout: standardize date formats (e.g. "Jan 2020 - Mar 2022"),
  consistent capitalization, and bullet points for all experience entries.
- Optimize for ATS readability and keyword matching while keeping content truthful.
- For weak bullets, rewrite as Action + Scope + Measurable Result when data is present in the text.

Existing Resume:
{profile}

REQUIRED IMPROVEMENTS (apply all of these exactly):
{refinement_section}

Return the improved resume as ONLY valid JSON with the following structure:
{{
  "contact": {{ "name": "...", "email": "...", "phone": "...", "location": "...", "linkedin": "..." }},
  "summary": "...",
  "skills": ["...", "..."],
  "experience": [
    {{
      "title": "...",
      "company": "...",
      "period": "...",
      "bullets": ["...", "..."]
    }}
  ],
  "education": [
    {{
      "degree": "...",
      "school": "...",
      "year": "..."
    }}
  ]
}}
"""
        formatted_prompt = template.replace("{profile}", state["profile_description"]).replace("{refinement_section}", refinement_instructions)
    else:
        template = """
You are an expert resume writer. Use the provided profile description to create a comprehensive, professional resume.
Primary objective: produce ATS-friendly, high-quality resume content in a clean standard layout.

Profile Description:
{profile}

TASK:
Generate a professional resume including:
- Contact Information (use placeholders if missing)
- Professional Summary (concise, role-aligned, keyword-rich)
- Key Skills (ATS keywords aligned to the role/domain in the profile)
- Work Experience (bullet points should emphasize measurable outcomes and impact)
- Education

QUALITY + ATS REQUIREMENTS:
- Use consistent and machine-readable date formats.
- Keep section names standard and scannable.
- Prefer strong action verbs and quantified achievements when provided.
- Preserve truthfulness: never fabricate employers, dates, metrics, or credentials.

Return ONLY valid JSON with the following structure:
{{
  "contact": {{ "name": "...", "email": "...", "phone": "...", "location": "...", "linkedin": "..." }},
  "summary": "...",
  "skills": ["...", "..."],
  "experience": [
    {{
      "title": "...",
      "company": "...",
      "period": "...",
      "bullets": ["...", "..."]
    }}
  ],
  "education": [
    {{
      "degree": "...",
      "school": "...",
      "year": "..."
    }}
  ]
}}
"""
        formatted_prompt = template.replace("{profile}", state["profile_description"])

    try:
        response = llm.invoke(formatted_prompt)
        clean_content = clean_json_output(response.content)
        result = json.loads(clean_content)
        return {"resume_json": result}
    except Exception as e:
        # Fallback structure if LLM fails
        return {
            "resume_json": {
                "summary": f"Failed to generate: {str(e)}",
                "experience": [],
                "skills": [],
                "education": []
            }
        }

def build_resume_generator_graph():
    graph = StateGraph(GeneratorState)
    graph.add_node("generate", generator_agent)
    graph.set_entry_point("generate")
    graph.add_edge("generate", END)
    return graph.compile()
