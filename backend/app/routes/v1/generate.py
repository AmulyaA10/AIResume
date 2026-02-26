from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from typing import Optional

from app.dependencies import get_current_user, resolve_credentials
from app.models import GenerateRequest
from app.common import build_llm_config
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
    output = run_resume_pipeline(task="generate", query=request.profile, llm_config=llm_config)
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
