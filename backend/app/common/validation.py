"""Shared resume validation helpers for all route handlers.

Provides:
  - precheck_resume_validation: AI-based input validation (block / warn / pass)
  - validate_resume_fields: structural field-completeness check on resume JSON
  - resume_json_to_text: convert structured resume JSON to plain text

Every route that accepts or produces resume data should use these helpers
so that candidate input (LinkedIn) and recruiter input (generate, upload,
analyze) follow the same validation routine.
"""

from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from services.agent_controller import run_resume_validation

# ─── Classification tiers ────────────────────────────────────────────────────
BLOCKING_CLASSIFICATIONS = {"not_resume"}
WARNING_CLASSIFICATIONS = {"resume_invalid_or_incomplete", "resume_valid_but_weak"}

# ─── Mandatory field definitions ─────────────────────────────────────────────
# Each entry: (json_path, human label, is_required)
# is_required=True  → missing = error
# is_required=False → missing = warning
MANDATORY_CONTACT_FIELDS = [
    ("name", "Name", True),
    ("email", "Email", True),
    ("phone", "Phone", True),
    ("location", "Location", False),
]

MANDATORY_SECTIONS = [
    ("summary", "Professional Summary", True),
    ("skills", "Skills", True),
    ("experience", "Work Experience", True),
    ("education", "Education", True),
]

OPTIONAL_SECTIONS = [
    ("certifications", "Certifications", False),
    ("projects", "Projects", False),
]

# Minimum counts for list-based sections
MIN_SKILLS = 3
MIN_EXPERIENCE_BULLETS = 1


# ─── AI-based precheck (uses LLM validation graph) ──────────────────────────

def precheck_resume_validation(
    resume_text: str,
    llm_config: dict,
    file_name: str = "pasted_text",
    file_type: str = "txt",
) -> Optional[dict]:
    """Run resume validation and raise HTTP 422 if text is not a resume.

    Returns:
        None  – if validation passes cleanly (good/strong) or validation itself errored
        dict  – validation result if classification is warning-level

    Raises:
        HTTPException(422) if classification is 'not_resume'
    """
    validation = run_resume_validation(
        file_name=file_name,
        file_type=file_type,
        extracted_text=resume_text,
        llm_config=llm_config,
    )

    # If the validation graph itself failed, don't punish the user
    if validation.get("error"):
        return None

    classification = validation.get("classification", "not_resume")

    if classification in BLOCKING_CLASSIFICATIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "not_a_resume",
                "message": "The provided text does not appear to be a resume.",
                "validation": validation,
            },
        )

    if classification in WARNING_CLASSIFICATIONS:
        return validation

    return None


# ─── Structural field validation (no LLM needed) ────────────────────────────

def validate_resume_fields(resume_json: dict) -> Dict[str, Any]:
    """Check structured resume JSON for mandatory field completeness.

    Returns a dict with:
        valid (bool): True if all required fields are present
        errors (list[str]): required fields that are missing or empty
        warnings (list[str]): recommended fields that are missing or empty
        field_report (dict): per-field status map
    """
    errors: List[str] = []
    warnings: List[str] = []
    field_report: Dict[str, str] = {}

    # --- Contact ---
    contact = resume_json.get("contact") or {}
    if not contact:
        errors.append("Contact information is completely missing")
        field_report["contact"] = "missing"
    else:
        for key, label, required in MANDATORY_CONTACT_FIELDS:
            val = contact.get(key, "")
            present = bool(val and str(val).strip())
            field_report[f"contact.{key}"] = "present" if present else "missing"
            if not present:
                if required:
                    errors.append(f"Contact: {label} is missing")
                else:
                    warnings.append(f"Contact: {label} is missing")

    # --- Top-level sections ---
    for key, label, required in MANDATORY_SECTIONS:
        val = resume_json.get(key)
        if isinstance(val, list):
            present = len(val) > 0
        elif isinstance(val, str):
            present = len(val.strip()) > 0
        else:
            present = bool(val)

        field_report[key] = "present" if present else "missing"
        if not present:
            if required:
                errors.append(f"{label} section is missing or empty")
            else:
                warnings.append(f"{label} section is missing or empty")

    # --- Skills count ---
    skills = resume_json.get("skills") or []
    if isinstance(skills, list) and 0 < len(skills) < MIN_SKILLS:
        warnings.append(f"Only {len(skills)} skill(s) listed — recommend at least {MIN_SKILLS}")
        field_report["skills_count"] = "low"
    elif isinstance(skills, list) and len(skills) >= MIN_SKILLS:
        field_report["skills_count"] = "good"

    # --- Experience bullets ---
    experience = resume_json.get("experience") or []
    for i, exp in enumerate(experience):
        bullets = exp.get("bullets") or []
        if len(bullets) < MIN_EXPERIENCE_BULLETS:
            warnings.append(f"Experience #{i+1} ({exp.get('title', 'untitled')}): only {len(bullets)} bullet(s)")

        # Check required sub-fields
        for sub_key, sub_label in [("title", "Job title"), ("company", "Company"), ("period", "Period")]:
            if not exp.get(sub_key, ""):
                warnings.append(f"Experience #{i+1}: {sub_label} is missing")

    # --- Education sub-fields ---
    education = resume_json.get("education") or []
    for i, edu in enumerate(education):
        for sub_key, sub_label in [("degree", "Degree"), ("school", "School")]:
            if not edu.get(sub_key, ""):
                warnings.append(f"Education #{i+1}: {sub_label} is missing")
        if not edu.get("field_of_study", ""):
            warnings.append(f"Education #{i+1}: Field of study is missing")

    # --- Optional sections (never errors, just note presence) ---
    for key, label, _ in OPTIONAL_SECTIONS:
        val = resume_json.get(key)
        present = isinstance(val, list) and len(val) > 0
        field_report[key] = "present" if present else "empty"

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "field_report": field_report,
    }


# ─── Resume JSON → plain text conversion ────────────────────────────────────

def resume_json_to_text(resume_json: dict) -> str:
    """Convert structured resume JSON to plain text for AI validation.

    Shared by generate, LinkedIn, and upload routes so the same format
    is always passed to run_resume_validation().
    """
    parts = []
    contact = resume_json.get("contact", {})
    if contact.get("name"):
        parts.append(contact["name"])
    if contact.get("email"):
        parts.append(contact["email"])
    if contact.get("phone"):
        parts.append(contact["phone"])
    if contact.get("location"):
        parts.append(contact["location"])
    if contact.get("linkedin"):
        parts.append(contact["linkedin"])

    if resume_json.get("summary"):
        parts.append(f"\nPROFESSIONAL SUMMARY\n{resume_json['summary']}")

    skills = resume_json.get("skills", [])
    if isinstance(skills, list) and skills:
        parts.append(f"\nSKILLS\n{', '.join(str(s) for s in skills)}")

    for exp in resume_json.get("experience", []):
        location = exp.get("location", "")
        loc_str = f" | {location}" if location else ""
        parts.append(f"\nEXPERIENCE\n{exp.get('title', '')} | {exp.get('company', '')} | {exp.get('period', '')}{loc_str}")
        for bullet in exp.get("bullets", []):
            parts.append(f"- {bullet}")

    for edu in resume_json.get("education", []):
        field = edu.get("field_of_study", "")
        field_str = f" | {field}" if field else ""
        parts.append(f"\nEDUCATION\n{edu.get('degree', '')} | {edu.get('school', '')} | {edu.get('year', '')}{field_str}")

    for cert in resume_json.get("certifications", []):
        parts.append(f"\nCERTIFICATION\n{cert.get('name', '')} | {cert.get('issuer', '')} | {cert.get('date', '')}")

    for proj in resume_json.get("projects", []):
        tech = ", ".join(proj.get("tech_stack", []))
        parts.append(f"\nPROJECT\n{proj.get('name', '')} | {tech}")
        if proj.get("description"):
            parts.append(proj["description"])
        for outcome in proj.get("outcomes", []):
            parts.append(f"- {outcome}")

    return "\n".join(parts)


# ─── Combined output validation (AI + structural) ───────────────────────────

def validate_resume_output(
    resume_json: dict,
    llm_config: dict,
    file_name: str = "generated_resume",
) -> Dict[str, Any]:
    """Run both structural field validation and AI quality validation on resume JSON.

    Used as a common post-generation/post-parse validation routine for both
    recruiter (generate) and candidate (LinkedIn) flows.

    Returns dict with:
        field_validation: result from validate_resume_fields()
        ai_validation: result from run_resume_validation() (or None on failure)
    """
    # 1. Structural field check (instant, no LLM)
    field_result = validate_resume_fields(resume_json)

    # 2. AI quality validation (uses LLM)
    ai_result = None
    resume_text = resume_json_to_text(resume_json)
    if resume_text.strip():
        try:
            ai_result = run_resume_validation(
                file_name=file_name,
                file_type="txt",
                extracted_text=resume_text,
                llm_config=llm_config,
            )
        except Exception as e:
            print(f"DEBUG: AI output validation failed: {e}")

    return {
        "field_validation": field_result,
        "ai_validation": ai_result,
    }
