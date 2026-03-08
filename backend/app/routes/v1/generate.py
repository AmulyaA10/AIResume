from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import re

from app.dependencies import get_current_user, resolve_credentials
from app.models import GenerateRequest
from app.common import (
    build_llm_config, precheck_resume_validation,
    validate_resume_fields, validate_resume_output, resume_json_to_text,
)
from services.agent_controller import run_resume_pipeline
from services.export_service import generate_docx
from services.ai.common import extract_skills_from_text

router = APIRouter()

_FORMATTING_ISSUE_RE = re.compile(r"\b(format|formatting|layout|readability|spacing|section\s+structure)\b", re.IGNORECASE)
_MAX_IMPROVEMENT_ITEMS = 5


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _unique(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _build_ats_quality_hints(validation: dict) -> list:
    scores = validation.get("scores", {}) if isinstance(validation, dict) else {}
    ats = int(scores.get("ats_friendliness", 0) or 0)
    quality = int(scores.get("achievement_quality", 0) or 0)
    completeness = int(scores.get("completeness", 0) or 0)
    missing_fields = [str(f).lower() for f in _as_list(validation.get("missing_fields"))]

    hints = []
    if ats < 5:
        hints.extend([
            "Use standard ATS headers exactly once: PROFESSIONAL SUMMARY, CORE COMPETENCIES, PROFESSIONAL EXPERIENCE, EDUCATION.",
            "Mirror important job-description keywords in summary, skills, and experience bullets.",
            "Keep dates consistent and machine-readable (e.g., Jan 2022 - Mar 2024).",
        ])
    if quality < 5:
        hints.extend([
            "Rewrite bullets in Action + Scope + Measurable Result format.",
            "Add metrics to impact bullets (% growth, revenue, time saved, volume, SLA, latency).",
            "Prioritize outcome-first bullets over responsibility-only statements.",
        ])
    if completeness < 5:
        hints.append("Fill all core fields: contact details, role title, company, dates, education, and skills.")
    if any("linkedin" in f for f in missing_fields):
        hints.append("If available in the source text, include the full LinkedIn URL in contact.linkedin.")

    return _unique(hints)


def _normalize_output_validation(validation: dict) -> dict:
    """Normalize feedback so refinement focuses on ATS + quality improvements."""
    if not isinstance(validation, dict):
        return {}

    top_issues = _as_list(validation.get("top_issues")) or _as_list(validation.get("issues"))
    suggested = _as_list(validation.get("suggested_improvements")) or _as_list(validation.get("improvements"))

    filtered_issues = [i for i in top_issues if not _FORMATTING_ISSUE_RE.search(i)]
    filtered_suggested = [s for s in suggested if not _FORMATTING_ISSUE_RE.search(s)]

    filtered_suggested.extend(_build_ats_quality_hints(validation))

    validation["top_issues"] = _unique(filtered_issues)[:_MAX_IMPROVEMENT_ITEMS]
    validation["suggested_improvements"] = _unique(filtered_suggested)[:_MAX_IMPROVEMENT_ITEMS]
    # Backward compatibility for any clients still reading legacy keys.
    validation["issues"] = validation["top_issues"]
    validation["improvements"] = validation["suggested_improvements"]
    return validation




@router.post("/resume")
async def generate_resume_endpoint(
    request: GenerateRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])

    # Pre-check: validate that the input text looks like resume/profile content
    input_validation_warning = precheck_resume_validation(request.profile, llm_config)

    output = run_resume_pipeline(
        task="generate",
        query=request.profile,
        llm_config=llm_config,
        refinement_instructions=request.refinement_instructions,
    )

    # Post-generation validation: common routine for both generate and LinkedIn
    resume_json = output.get("resume_json") or output.get("resume") or {}
    if resume_json:
        # Structural field validation (instant, no LLM)
        output["field_validation"] = validate_resume_fields(resume_json)

        # AI quality validation (uses LLM)
        combined = validate_resume_output(resume_json, llm_config, file_name="generated_resume")
        if combined.get("ai_validation"):
            output["output_validation"] = combined["ai_validation"]

    # Attach input validation warning if present (distinct from output_validation)
    if input_validation_warning:
        output["input_validation_warning"] = input_validation_warning

    return output


@router.post("/refine")
async def refine_resume_endpoint(
    request: dict,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
):
    """Re-run skill extraction and validation on an edited resume JSON.

    Accepts existing resume JSON (possibly edited by the user), re-extracts
    skills from experience text, augments the skills list, and returns
    updated validation results.
    """
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])

    resume_json = dict(request)

    # Re-extract skills from all text content in the resume
    all_text_parts = []
    if resume_json.get("summary"):
        all_text_parts.append(resume_json["summary"])
    for exp in resume_json.get("experience", []):
        if exp.get("title"):
            all_text_parts.append(exp["title"])
        all_text_parts.extend(exp.get("bullets", []))
    for proj in resume_json.get("projects", []):
        if proj.get("description"):
            all_text_parts.append(proj["description"])
        all_text_parts.extend(proj.get("tech_stack", []))

    all_text = " ".join(all_text_parts)
    extracted = extract_skills_from_text(all_text)

    # Merge extracted skills into existing skills (preserve user's list, add new ones)
    existing_skills = resume_json.get("skills") or []
    existing_lower = {s.lower() for s in existing_skills}
    new_skills = [s for s in extracted if s.lower() not in existing_lower]
    resume_json["skills"] = existing_skills + new_skills

    # Run structural + AI validation on the updated resume
    field_validation = validate_resume_fields(resume_json)
    combined = validate_resume_output(resume_json, llm_config, file_name="refined_resume")

    return {
        "resume_json": resume_json,
        "skills_added": new_skills,
        "field_validation": field_validation,
        "output_validation": combined.get("ai_validation"),
    }


@router.post("/export")
async def export_resume_docx(request: dict):
    # This endpoint receives the resume JSON and returns a DOCX file
    try:
        file_stream = generate_docx(request)
        return StreamingResponse(
            file_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=generated_resume.docx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
