from typing import TypedDict, Optional, Dict
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
import json

from services.ai.common import get_llm, clean_json_output
from services.linkedin_scraper import scrape_linkedin_profile

class LinkedInResumeState(TypedDict):
    linkedin_url: str
    raw_profile: Optional[str]
    parsed_profile: Optional[Dict]
    resume: Optional[str]
    error: Optional[str]
    config: Optional[Dict]
    linkedin_creds: Optional[Dict]

def linkedin_fetch_agent(state: LinkedInResumeState):
    url = state["linkedin_url"]
    creds = state.get("linkedin_creds") or {}
    print(f"--- Fetching LinkedIn Profile: {url} ---")
    try:
        profile_text = scrape_linkedin_profile(
            url,
            email=creds.get("email"),
            password=creds.get("password")
        )
        if not profile_text or len(profile_text.strip()) < 50:
            return {"raw_profile": None, "error": "Scraped profile was empty or too short. LinkedIn may have blocked the request or the profile is not accessible."}
        return {"raw_profile": profile_text, "error": None}
    except Exception as e:
        print(f"Error scraping LinkedIn: {e}")
        return {"raw_profile": None, "error": str(e)}


def profile_parser_agent(state: LinkedInResumeState):
    if state.get("error") or not state.get("raw_profile"):
        return {"parsed_profile": None}

    llm = get_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["profile"],
        template="""
Extract structured resume data from LinkedIn profile text.

Profile:
{profile}

Return ONLY valid JSON:
{{
  "name": "",
  "headline": "",
  "experience": [],
  "skills": [],
  "education": []
}}
"""
    )

    response = llm.invoke(
        prompt.format(profile=state["raw_profile"])
    )

    try:
        clean_content = clean_json_output(response.content)
        parsed_data = json.loads(clean_content)
        return {"parsed_profile": parsed_data}
    except Exception as e:
        print(f"Error parsing profile JSON: {e}")
        print(f"Raw content: {response.content}")
        return {"parsed_profile": None, "error": f"Failed to parse LinkedIn profile data: {e}"}

def resume_writer_agent(state: LinkedInResumeState):
    if state.get("error") or not state.get("parsed_profile"):
        return {"resume": None}

    llm = get_llm(state.get("config"))
    profile = state["parsed_profile"]

    prompt = PromptTemplate(
        input_variables=["profile"],
        template="""
You are a professional resume writer.

Convert the following parsed LinkedIn profile data into a structured resume format.

Profile Data:
{profile}

Return ONLY valid JSON with this exact structure:
{{
  "contact": {{
    "name": "",
    "email": "",
    "phone": "",
    "location": ""
  }},
  "summary": "Professional summary...",
  "skills": ["Skill 1", "Skill 2"],
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "period": "Start Date - End Date",
      "bullets": ["Achievement 1", "Achievement 2"]
    }}
  ],
  "education": [
    {{
      "degree": "Degree Name",
      "school": "University Name",
      "year": "Year"
    }}
  ]
}}
"""
    )

    response = llm.invoke(
        prompt.format(profile=json.dumps(profile, indent=2))
    )

    try:
        clean_content = clean_json_output(response.content)
        resume_json = json.loads(clean_content)
        return {"resume": resume_json}
    except Exception as e:
        print(f"Error parsing resume JSON: {e}")
        return {"resume": None, "error": f"Failed to generate structured resume: {e}"}

def build_linkedin_resume_graph():
    graph = StateGraph(LinkedInResumeState)

    graph.add_node("fetch", linkedin_fetch_agent)
    graph.add_node("parse", profile_parser_agent)
    graph.add_node("write", resume_writer_agent)

    graph.set_entry_point("fetch")

    graph.add_edge("fetch", "parse")
    graph.add_edge("parse", "write")
    graph.add_edge("write", END)

    return graph.compile()
