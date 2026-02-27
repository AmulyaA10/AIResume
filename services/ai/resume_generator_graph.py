from typing import TypedDict, Optional
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
import json

from services.ai.common import get_llm, clean_json_output

class GeneratorState(TypedDict):
    profile_description: str
    resume_json: Optional[dict]
    config: Optional[dict]

def generator_agent(state: GeneratorState):
    llm = get_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["profile"],
        template="""
You are an expert resume writer. Use the provided profile description to create a comprehensive, professional resume.

Profile Description:
{profile}

TASK:
Generate a professional resume including:
- Contact Information (use placeholders if missing)
- Professional Summary
- Key Skills
- Work Experience (elaborate on bullet points)
- Education

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
    )
    
    try:
        response = llm.invoke(prompt.format(profile=state["profile_description"]))
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
