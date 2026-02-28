from typing import TypedDict, Optional, Dict
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
import json

from services.ai.common import get_llm, clean_json_output
from services.linkedin_scraper import (
    scrape_linkedin_profile,
    resume_linkedin_session,
    SecurityChallengeError,
)

class LinkedInResumeState(TypedDict):
    linkedin_url: str
    raw_profile: Optional[str]
    parsed_profile: Optional[Dict]
    resume: Optional[str]
    error: Optional[str]
    error_code: Optional[str]
    session_id: Optional[str]
    config: Optional[Dict]
    linkedin_creds: Optional[Dict]
    login_wait: Optional[int]

def linkedin_fetch_agent(state: LinkedInResumeState):
    url = state["linkedin_url"]
    creds = state.get("linkedin_creds") or {}
    session_id = state.get("session_id")
    login_wait = state.get("login_wait")
    is_retry = login_wait is not None and login_wait >= 60  # retry uses 60s

    print(f"--- Fetching LinkedIn Profile: {url} (retry={is_retry}, session_id={session_id}) ---")

    try:
        # If retrying with an existing session, resume polling instead of fresh login
        if is_retry and session_id:
            print(f"--- [Fetch] Resuming cached session {session_id} ---")
            profile_text = resume_linkedin_session(
                session_id=session_id,
                profile_url=url,
                login_wait=login_wait,
            )
        else:
            profile_text = scrape_linkedin_profile(
                url,
                email=creds.get("email"),
                password=creds.get("password"),
                login_wait=login_wait,
                session_id=session_id,
            )

        # Debug logging — shows exactly what Selenium captured
        text_len = len(profile_text) if profile_text else 0
        print(f"--- [Fetch] Raw scraped text length: {text_len} chars ---")
        if profile_text:
            print(f"--- [Fetch] First 500 chars: ---")
            print(profile_text[:500])
            print(f"--- [Fetch] Last 500 chars: ---")
            print(profile_text[-500:] if text_len > 500 else "(same as above)")

        if not profile_text or len(profile_text.strip()) < 50:
            return {"raw_profile": None, "error": "Scraped profile was empty or too short. LinkedIn may have blocked the request or the profile is not accessible."}

        # Quality gate: require evidence of actual profile sections, not just boilerplate
        text_lower = profile_text.lower()
        profile_signals = ["experience", "education", "skills", "===section:",
                           "present", "full-time", "part-time", "yrs", "mos",
                           "manager", "engineer", "developer", "analyst", "lead",
                           "director", "consultant", "university", "bachelor", "master"]
        has_profile_signals = any(signal in text_lower for signal in profile_signals)

        if len(profile_text.strip()) < 200 or not has_profile_signals:
            return {
                "raw_profile": None,
                "error": f"LinkedIn scraper captured only {text_len} characters "
                         "without recognizable profile sections (no experience, education, "
                         "or skills found). LinkedIn may have blocked the request with a "
                         "CAPTCHA or login wall. Try logging into LinkedIn manually in a "
                         "regular browser first to clear security challenges, then retry."
            }

        return {"raw_profile": profile_text, "error": None}

    except SecurityChallengeError as e:
        print(f"Security challenge (session held): {e}")
        return {
            "raw_profile": None,
            "error": str(e),
            "error_code": "SECURITY_CHALLENGE",
            "session_id": e.session_id,
        }

    except Exception as e:
        print(f"Error scraping LinkedIn: {e}")
        error_msg = str(e)
        error_code = None

        # Detect security challenge / 2-step verification errors so the
        # frontend can show a specific "check your phone" prompt.
        challenge_keywords = [
            "security verification", "verification timed out",
            "captcha", "2fa", "security check", "security challenge",
        ]
        if any(kw in error_msg.lower() for kw in challenge_keywords):
            error_code = "SECURITY_CHALLENGE"

        return {"raw_profile": None, "error": error_msg, "error_code": error_code}


def profile_parser_agent(state: LinkedInResumeState):
    if state.get("error") or not state.get("raw_profile"):
        return {"parsed_profile": None}

    llm = get_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["profile"],
        template="""
Extract structured resume data from LinkedIn profile text.
The profile text may contain section delimiters like ===SECTION: EXPERIENCE===.
Extract ALL entries from each section — do not truncate or summarize.

Profile:
{profile}

Return ONLY valid JSON:
{{
  "name": "",
  "headline": "",
  "location": "",
  "contact": {{
    "email": "",
    "phone": "",
    "linkedin": "",
    "github": "",
    "portfolio": ""
  }},
  "summary": "",
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "employment_type": "",
      "period": "Start - End",
      "start_date": "",
      "end_date": "",
      "location": "City, Country",
      "is_current": false,
      "description": "Full role description and achievements (verbatim from profile when present)",
      "responsibilities": [],
      "achievements": [],
      "tools_technologies": [],
      "skills_inferred": [],
      "keywords_inferred": []
    }}
  ],
  "projects": [
    {{
      "name": "",
      "role": "",
      "period": "",
      "description": "Full project description (verbatim when present)",
      "tech_stack_explicit": [],
      "skills_inferred": [],
      "outcomes": [],
      "links": []
    }}
  ],
  "skills": {{
    "explicit": [],
    "inferred_from_experience_projects": [],
    "grouped": {{
      "languages": [],
      "frameworks": [],
      "cloud_data": [],
      "ml_genai": [],
      "devops": [],
      "databases": [],
      "analytics_bi": [],
      "testing_quality": [],
      "soft_skills": []
    }}
  }},
  "education": [
    {{
      "degree": "Degree or Program Name",
      "school": "Institution Name",
      "field_of_study": "",
      "year": "Start - End or Graduation Year",
      "location": "",
      "details": ""
    }}
  ],
  "certifications": [
    {{
      "name": "Certification Name",
      "issuer": "Issuing Organization",
      "date": "Issue Date",
      "credential_id": "",
      "credential_url": ""
    }}
  ],
  "publications": [
    {{
      "title": "",
      "publisher": "",
      "date": "",
      "url": ""
    }}
  ],
  "awards": [
    {{
      "name": "",
      "issuer": "",
      "date": "",
      "details": ""
    }}
  ],
  "volunteering": [
    {{
      "role": "",
      "organization": "",
      "period": "",
      "description": ""
    }}
  ]
}}

Important:
- Include ALL work experience entries, even if there are many roles at the same company.
- Include ALL projects (personal + professional) if present.
- Include ALL education entries.
- Include ALL certifications and licenses.
- Include ALL skills listed.

Critical extraction rules:
1) VERBATIM FIRST:
- For fields like description, copy the text exactly as it appears where possible.
- If the profile doesn't provide a field, leave it as "" or [] (do not invent facts like dates, degrees, employers).

2) SPLIT RESPONSIBILITIES VS ACHIEVEMENTS:
- Put "did/owned" statements into responsibilities[].
- Put "results/impact" statements into achievements[].
- If the LinkedIn text mixes both, duplicate a bullet into both arrays ONLY if necessary.

3) EXTRAPOLATE SKILLS (from experience + projects):
- Build skills_inferred (per role/project) and skills.inferred_from_experience_projects (global) by mining tools/tech/processes implied by the descriptions.
- Infer ONLY high-confidence skills strongly implied by the text.
- Do NOT infer employers, titles, dates, degrees, certifications, awards, locations, or exact metrics not present.
- If uncertain, omit the skill.

4) SKILL NORMALIZATION + DEDUP:
- Normalize capitalization (e.g., pyspark -> PySpark, k8s -> Kubernetes).
- Deduplicate across explicit and inferred.
- Keep explicit skills unchanged in skills.explicit.

5) GROUPING:
- Populate skills.grouped using explicit + inferred skills mapped into the best-fit bucket.

Return ONLY the JSON object. No markdown. No commentary.
"""
    )

    response = llm.invoke(
        prompt.format(profile=state["raw_profile"])
    )

    try:
        clean_content = clean_json_output(response.content)
        parsed_data = json.loads(clean_content)

        # Quality gate: ensure the LLM actually extracted meaningful data
        exp_count = len(parsed_data.get("experience") or [])
        edu_count = len(parsed_data.get("education") or [])
        skills_count = len(parsed_data.get("skills") or [])
        cert_count = len(parsed_data.get("certifications") or [])

        print(f"--- [Parser] Parsed: {exp_count} experiences, {edu_count} education, "
              f"{skills_count} skills, {cert_count} certifications ---")

        if exp_count == 0 and edu_count == 0 and skills_count == 0:
            return {
                "parsed_profile": None,
                "error": "Could not extract any experience, education, or skills from "
                         "the scraped LinkedIn profile. The scraper may not have captured "
                         "enough content — LinkedIn may have blocked the request."
            }

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
    skills_source = profile.get("skills") or {}
    derived_skills = []
    if isinstance(skills_source, dict):
        derived_skills.extend(skills_source.get("explicit") or [])
        derived_skills.extend(skills_source.get("inferred_from_experience_projects") or [])
        grouped = skills_source.get("grouped") or {}
        if isinstance(grouped, dict):
            for items in grouped.values():
                if items:
                    derived_skills.extend(items)
    # Deduplicate while preserving order
    seen = set()
    derived_skills = [s for s in derived_skills if isinstance(s, str) and not (s in seen or seen.add(s))]

    prompt = PromptTemplate(
        input_variables=["profile"],
        template="""
You are a professional resume writer.

Convert the following parsed LinkedIn profile data into a structured resume format.
Include ALL experience entries, education entries, certifications, and skills from the input data.
Do not truncate or omit any entries.

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
  ],
  "certifications": [
    {{
      "name": "Certification Name",
      "issuer": "Issuing Organization",
      "date": "Date"
    }}
  ]
}}

Important:
- Include ALL work experiences — list every role even if there are multiple at the same company
- Include ALL education entries
- Include ALL certifications and licenses
- Write 2-4 achievement bullets per experience entry based on the description
- Generate a compelling professional summary from the headline and overall profile
"""
    )

    response = llm.invoke(
        prompt.format(profile=json.dumps(profile, indent=2))
    )

    try:
        clean_content = clean_json_output(response.content)
        resume_json = json.loads(clean_content)

        # Log the generated resume quality
        exp_count = len(resume_json.get("experience") or [])
        edu_count = len(resume_json.get("education") or [])
        cert_count = len(resume_json.get("certifications") or [])
        summary_len = len(resume_json.get("summary", ""))
        print(f"--- [Writer] Generated resume: {exp_count} experiences, "
              f"{edu_count} education, {cert_count} certifications, "
              f"summary_len={summary_len} ---")

        if not resume_json.get("skills") and derived_skills:
            resume_json["skills"] = derived_skills
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


def build_linkedin_parse_graph():
    """Graph that skips Selenium fetch — starts directly from parse.

    Used when the user pastes their LinkedIn profile text manually,
    bypassing the scraper entirely.
    """
    graph = StateGraph(LinkedInResumeState)

    graph.add_node("parse", profile_parser_agent)
    graph.add_node("write", resume_writer_agent)

    graph.set_entry_point("parse")

    graph.add_edge("parse", "write")
    graph.add_edge("write", END)

    return graph.compile()
