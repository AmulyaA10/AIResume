from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from typing import Optional

from app.dependencies import get_current_user, resolve_credentials
from app.models import GenerateRequest
from app.common import (
    build_llm_config, precheck_resume_validation,
    validate_resume_fields, validate_resume_output, resume_json_to_text,
)
from services.agent_controller import run_resume_pipeline
from services.export_service import generate_docx

router = APIRouter()


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

    output = run_resume_pipeline(task="generate", query=request.profile, llm_config=llm_config)

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
