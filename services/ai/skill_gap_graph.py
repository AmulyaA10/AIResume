# services/ai/skill_gap_graph.py
from typing import TypedDict, List, Optional

from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
import json

from services.ai.common import get_llm, clean_json_output

class SkillGapState(TypedDict):
    resume_text: str
    jd_text: str
    resume_skills: Optional[List[str]]
    jd_skills: Optional[List[str]]
    gaps: Optional[dict]
    config: Optional[dict]

def resume_skill_agent(state: SkillGapState):
    llm = get_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["resume"],
        template="""
Extract technical and professional skills from the resume.

Resume:
{resume}

Return ONLY valid JSON:
{{
  "skills": ["Python", "AWS", "Docker"]
}}
"""
    )

    response = llm.invoke(prompt.format(resume=state["resume_text"]))
    try:
        clean_content = clean_json_output(response.content)
        skills = json.loads(clean_content).get("skills", [])
    except json.JSONDecodeError:
        print(f"Error parsing resume skills: {response.content}")
        skills = [] # Fallback to empty list or handle error appropriately

    return {"resume_skills": skills}


def jd_skill_agent(state: SkillGapState):
    llm = get_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["jd"],
        template="""
Extract required skills from the job description.

Job Description:
{jd}

Return ONLY valid JSON:
{{
  "skills": ["Kubernetes", "Terraform", "CI/CD"]
}}
"""
    )

    response = llm.invoke(prompt.format(jd=state["jd_text"]))
    try:
        clean_content = clean_json_output(response.content)
        skills = json.loads(clean_content).get("skills", [])
    except json.JSONDecodeError:
        print(f"Error parsing JD skills: {response.content}")
        skills = []

    return {"jd_skills": skills}

def skill_gap_agent(state: SkillGapState):
    resume_skills = set(s.lower() for s in state["resume_skills"])
    jd_skills = set(s.lower() for s in state["jd_skills"])

    missing = sorted(jd_skills - resume_skills)
    recommended = missing[:5]

    return {
        "gaps": {
            "missing_skills": missing,
            "recommended": recommended
        }
    }



def build_skill_gap_graph():
    graph = StateGraph(SkillGapState)

    graph.add_node("resume_skills", resume_skill_agent)
    graph.add_node("jd_skills", jd_skill_agent)
    graph.add_node("compare", skill_gap_agent)

    graph.set_entry_point("resume_skills")

    graph.add_edge("resume_skills", "jd_skills")
    graph.add_edge("jd_skills", "compare")
    graph.add_edge("compare", END)

    return graph.compile()
