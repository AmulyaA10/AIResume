from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from typing import Optional

from app.dependencies import get_current_user, resolve_credentials
from app.models import GenerateRequest
<<<<<<< HEAD
from app.common import build_llm_config
=======
from app.common import build_llm_config, precheck_resume_validation
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
from services.agent_controller import run_resume_pipeline, run_resume_validation
from services.export_service import generate_docx

router = APIRouter()


def _resume_json_to_text(resume_json: dict) -> str:
    """Convert structured resume JSON to plain text for validation."""
    parts = []
    contact = resume_json.get("contact", {})
    if contact.get("name"):
        parts.append(contact["name"])
    if contact.get("email"):
        parts.append(contact["email"])
    if contact.get("phone"):
        parts.append(contact["phone"])

    if resume_json.get("summary"):
        parts.append(f"\nPROFESSIONAL SUMMARY\n{resume_json['summary']}")

    skills = resume_json.get("skills", [])
    if skills:
        parts.append(f"\nSKILLS\n{', '.join(skills)}")

    for exp in resume_json.get("experience", []):
        parts.append(f"\nEXPERIENCE\n{exp.get('title', '')} | {exp.get('company', '')} | {exp.get('period', '')}")
        for bullet in exp.get("bullets", []):
            parts.append(f"- {bullet}")

    for edu in resume_json.get("education", []):
        parts.append(f"\nEDUCATION\n{edu.get('degree', '')} | {edu.get('school', '')} | {edu.get('year', '')}")

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
<<<<<<< HEAD
=======

    # Pre-check: validate that the input text looks like resume/profile content
    input_validation_warning = precheck_resume_validation(request.profile, llm_config)

>>>>>>> 9d136502ee9374e86211849855e67746afb88872
    output = run_resume_pipeline(task="generate", query=request.profile, llm_config=llm_config)

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
                output["output_validation"] = output_validation
            except Exception as e:
                print(f"DEBUG: Post-generation validation failed: {e}")

<<<<<<< HEAD
=======
    # Attach input validation warning if present (distinct from output_validation)
    if input_validation_warning:
        output["input_validation_warning"] = input_validation_warning

>>>>>>> 9d136502ee9374e86211849855e67746afb88872
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
