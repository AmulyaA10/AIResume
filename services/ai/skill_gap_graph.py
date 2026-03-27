# services/ai/skill_gap_graph.py
import asyncio
import json
from typing import TypedDict, List, Optional

from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from services.ai.common import get_llm, get_json_llm, safe_parse_json, extract_skills_from_text


class _CombinedSkillsOutput(BaseModel):
    resume_skills: List[str] = Field(default_factory=list)
    jd_skills: List[str] = Field(default_factory=list)


class SkillGapState(TypedDict):
    resume_text: str
    jd_text: str
    resume_skills: Optional[List[str]]
    jd_skills: Optional[List[str]]
    gaps: Optional[dict]
    config: Optional[dict]


def _augment_with_keywords(skills: list, text: str) -> list:
    """Augment LLM skill list with keyword fallback if too few returned."""
    if len(skills) < 3:
        extracted = extract_skills_from_text(text)
        existing_lower = {s.lower() for s in skills}
        for s in extracted:
            if s.lower() not in existing_lower:
                skills.append(s)
                existing_lower.add(s.lower())
    return skills


def combined_skill_agent(state: SkillGapState):
    """Single async LLM call that extracts skills from both resume and JD at once.

    Replaces the original two sequential calls (resume_skill_agent + jd_skill_agent),
    cutting LLM round-trips in half.
    """
    llm = get_json_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["resume", "jd"],
        template="""
Extract technical and professional skills from the resume AND the job description.

Resume:
{resume}

Job Description:
{jd}

Return ONLY valid JSON with two lists:
{{
  "resume_skills": ["Python", "AWS", "Docker"],
  "jd_skills": ["Kubernetes", "Terraform", "CI/CD"]
}}
"""
    )

    try:
        response = llm.invoke(prompt.format(
            resume=state["resume_text"],
            jd=state["jd_text"],
        ))
        parsed = json.loads(response.content)
        resume_skills = parsed.get("resume_skills", [])
        jd_skills = parsed.get("jd_skills", [])
    except Exception as e:
        print(f"Error parsing combined skill extraction: {e}")
        resume_skills, jd_skills = [], []

    # Keyword fallback for either list that came back thin
    resume_skills = _augment_with_keywords(resume_skills, state["resume_text"])
    jd_skills = _augment_with_keywords(jd_skills, state["jd_text"])

    return {"resume_skills": resume_skills, "jd_skills": jd_skills}


def skill_gap_agent(state: SkillGapState):
    resume_skills = set(s.lower() for s in state["resume_skills"])
    jd_skills = set(s.lower() for s in state["jd_skills"])

    missing = sorted(jd_skills - resume_skills)
    recommended = missing[:5]

    return {
        "gaps": {
            "missing_skills": missing,
            "recommended": recommended,
        }
    }


def build_skill_gap_graph():
    graph = StateGraph(SkillGapState)

    graph.add_node("extract_skills", combined_skill_agent)
    graph.add_node("compare", skill_gap_agent)

    graph.set_entry_point("extract_skills")
    graph.add_edge("extract_skills", "compare")
    graph.add_edge("compare", END)

    return graph.compile()
