from typing import TypedDict, Optional, Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import os, json
from dotenv import load_dotenv
load_dotenv()

class LinkedInResumeState(TypedDict):
    linkedin_url: str
    raw_profile: Optional[str]
    parsed_profile: Optional[Dict]
    resume: Optional[str]
    config: Optional[Dict]
    linkedin_creds: Optional[Dict]


def get_llm(config: Optional[Dict]):
    """Helper to initialize LLM from config or environment."""
    if config and config.get("api_key"):
        return ChatOpenAI(
            model=config.get("model", "gpt-4o-mini"),
            temperature=config.get("temperature", 0.3),
            api_key=config.get("api_key"),
            base_url=config.get("base_url", "https://openrouter.ai/api/v1")
        )
    # Fallback to .env
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=os.getenv("OPEN_ROUTER_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )

from services.linkedin_scraper import scrape_linkedin_profile

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
        return {"raw_profile": profile_text}
    except Exception as e:
        print(f"Error scraping LinkedIn: {e}")
        return {"raw_profile": f"Error: {str(e)}"}


def clean_json_output(content: str) -> str:
    """Removes markdown code blocks (```json ... ```) from the string."""
    content = content.strip()
    if content.startswith("```"):
        # Remove first line (```json or ```)
        content = content.split("\n", 1)[1]
        # Remove last line (```)
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]
    return content.strip()

def profile_parser_agent(state: LinkedInResumeState):
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
        return {"parsed_profile": {
            "name": "Error Parsing",
            "headline": "Could not extract data",
            "experience": [],
            "skills": [],
            "education": []
        }}

def resume_writer_agent(state: LinkedInResumeState):
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
        # Fallback to a basic structure if AI fails
        return {"resume": {
            "contact": {"name": profile.get("name", "Unknown")},
            "summary": "Error generating structured resume.",
            "skills": profile.get("skills", []),
            "experience": profile.get("experience", []),
            "education": profile.get("education", [])
        }}




from langgraph.graph import StateGraph, END

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
