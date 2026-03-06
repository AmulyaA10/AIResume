from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import re

from app.dependencies import get_current_user, resolve_credentials
from app.models import GenerateRequest
from app.common import build_llm_config, precheck_resume_validation
from services.agent_controller import run_resume_pipeline, run_resume_validation
from services.export_service import generate_docx

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


def _resume_json_to_text(resume_json: dict) -> str:
    """Convert structured resume JSON to plain text for validation."""
    parts = []
    contact = resume_json.get("contact", {})
    if contact.get("name"):
        parts.append(contact["name"])
    contact_line = " | ".join(filter(None, [contact.get("email"), contact.get("phone"), contact.get("location")]))
    if contact_line:
        parts.append(contact_line)
    if contact.get("linkedin"):
        parts.append(f"LinkedIn: {contact['linkedin']}")

    if resume_json.get("summary"):
        parts.extend(["", "PROFESSIONAL SUMMARY", resume_json["summary"]])

    skills = resume_json.get("skills", [])
    if skills:
        parts.extend(["", "CORE COMPETENCIES", ", ".join(skills)])

    experiences = resume_json.get("experience", [])
    if experiences:
        parts.extend(["", "PROFESSIONAL EXPERIENCE"])
        for exp in experiences:
            parts.append(f"{exp.get('title', '')} | {exp.get('company', '')} | {exp.get('period', '')}")
            for bullet in exp.get("bullets", []):
                parts.append(f"- {bullet}")
            parts.append("")

    education = resume_json.get("education", [])
    if education:
        parts.extend(["", "EDUCATION"])
        for edu in education:
            parts.append(f"{edu.get('degree', '')} | {edu.get('school', '')} | {edu.get('year', '')}")

    return "\n".join(parts)


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

    # Post-generation validation: assess quality of the generated resume
    # Graph state uses "resume_json" key; some serializations may use "resume"
    resume_json = output.get("resume_json") or output.get("resume") or {}
    if resume_json:
        resume_text = _resume_json_to_text(resume_json)
        if resume_text.strip():
            try:
                output_validation = run_resume_validation(
                    file_name="generated_resume",
                    file_type="txt",
                    extracted_text=resume_text,
                    llm_config=llm_config,
                )
                output["output_validation"] = _normalize_output_validation(output_validation)
            except Exception as e:
                print(f"DEBUG: Post-generation validation failed: {e}")

    # Attach input validation warning if present (distinct from output_validation)
    if input_validation_warning:
        output["input_validation_warning"] = input_validation_warning

    return output


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
