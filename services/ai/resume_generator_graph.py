from typing import TypedDict, Optional
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
import json

from services.ai.common import get_llm, safe_parse_json, extract_skills_from_text


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
Generate a professional resume with ALL of the following mandatory sections.
Every section MUST be present and populated — use placeholders or reasonable inferences if details are missing from the input.

MANDATORY SECTIONS:
1. Contact Information — name, email, phone, location, linkedin URL
2. Professional Summary — 3-5 sentence compelling overview
3. Skills — at least 6 skills, grouped into categories (technical, soft skills, tools, etc.)
4. Work Experience — at least 1 entry with 2-4 achievement bullets each
5. Education — at least 1 entry with degree, school, field of study, and year
6. Certifications — include any mentioned; if none mentioned, return empty array []
7. Projects — include any mentioned; if none mentioned, return empty array []

Return ONLY valid JSON with the following structure:
{{
  "contact": {{
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1-XXX-XXX-XXXX",
    "location": "City, State/Country",
    "linkedin": "https://linkedin.com/in/username"
  }},
  "summary": "3-5 sentence professional summary highlighting key strengths and career focus.",
  "skills": ["Skill 1", "Skill 2", "Skill 3", "Skill 4", "Skill 5", "Skill 6"],
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "period": "Start Date - End Date",
      "location": "City, Country",
      "bullets": ["Achievement/responsibility 1", "Achievement/responsibility 2"]
    }}
  ],
  "education": [
    {{
      "degree": "Degree Name",
      "school": "University Name",
      "field_of_study": "Major / Field of Study",
      "year": "Graduation Year or Start - End"
    }}
  ],
  "certifications": [
    {{
      "name": "Certification Name",
      "issuer": "Issuing Organization",
      "date": "Issue Date"
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "description": "Brief project description",
      "tech_stack": ["Tech 1", "Tech 2"],
      "outcomes": ["Outcome or result"]
    }}
  ]
}}

CRITICAL RULES:
- contact.name is REQUIRED — extract or infer from the profile text. Never leave it blank.
- contact.email and contact.phone are REQUIRED — if not in input, use realistic placeholders like "firstname.lastname@email.com" and "+1-000-000-0000".
- skills MUST have at least 6 entries. Extract from experience descriptions if not explicitly listed.
- Each experience entry MUST have at least 2 bullet points with quantified achievements where possible.
- education entries MUST include field_of_study when inferable.
- If certifications or projects are not mentioned, return empty arrays for those fields.
- Return ONLY the JSON object. No markdown. No commentary.
"""
    )

    try:
        response = llm.invoke(prompt.format(profile=state["profile_description"]))
        result = safe_parse_json(response.content)

        # Enforce mandatory fields with fallbacks
        if not result.get("contact"):
            result["contact"] = {}
        contact = result["contact"]
        if not contact.get("name"):
            contact["name"] = "Candidate Name"
        if not contact.get("email"):
            contact["email"] = "contact@email.com"
        if not contact.get("phone"):
            contact["phone"] = "+1-000-000-0000"
        if not contact.get("location"):
            contact["location"] = "Location Not Specified"

        if not result.get("summary"):
            result["summary"] = "Professional summary not available."
        if not result.get("skills") or len(result.get("skills", [])) == 0:
            # Safety net: extract skills from experience descriptions + profile input
            all_text = state["profile_description"]
            for exp in result.get("experience", []):
                all_text += " " + " ".join(exp.get("bullets", []))
            extracted = extract_skills_from_text(all_text)
            result["skills"] = extracted if extracted else ["Not specified"]
        elif len(result.get("skills", [])) < 6:
            # Augment sparse skills from experience text
            all_text = state["profile_description"]
            for exp in result.get("experience", []):
                all_text += " " + " ".join(exp.get("bullets", []))
            extracted = extract_skills_from_text(all_text)
            existing_lower = {s.lower() for s in result["skills"]}
            for skill in extracted:
                if skill.lower() not in existing_lower:
                    result["skills"].append(skill)
                    existing_lower.add(skill.lower())
        if not result.get("experience"):
            result["experience"] = []
        if not result.get("education"):
            result["education"] = []
        if "certifications" not in result:
            result["certifications"] = []
        if "projects" not in result:
            result["projects"] = []

        return {"resume_json": result}
    except Exception as e:
        # Fallback structure if LLM fails
        return {
            "resume_json": {
                "contact": {"name": "Candidate Name", "email": "contact@email.com", "phone": "+1-000-000-0000", "location": ""},
                "summary": f"Failed to generate: {str(e)}",
                "experience": [],
                "skills": [],
                "education": [],
                "certifications": [],
                "projects": []
            }
        }

def build_resume_generator_graph():
    graph = StateGraph(GeneratorState)
    graph.add_node("generate", generator_agent)
    graph.set_entry_point("generate")
    graph.add_edge("generate", END)
    return graph.compile()
