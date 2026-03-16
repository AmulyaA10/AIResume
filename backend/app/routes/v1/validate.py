from fastapi import APIRouter, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional

from app.dependencies import get_current_user, resolve_credentials
from app.common import (
    build_llm_config,
    precheck_resume_validation,
    validate_resume_output,
)

router = APIRouter()


class ValidateTextRequest(BaseModel):
    """Validate raw resume text (AI classification + keyword skill detection)."""
    resume_text: str = Field(..., min_length=50)


class ValidateJsonRequest(BaseModel):
    """Validate structured resume JSON (structural fields + AI quality)."""
    resume_json: dict


@router.post("/text")
async def validate_text(
    request: ValidateTextRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
):
    """Run AI-based validation on raw resume text.

    Returns classification (not_resume / weak / valid / strong) and scores.
    Raises 422 if text is clearly not a resume.
    """
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])

    warning = precheck_resume_validation(request.resume_text, llm_config)
    return {
        "status": "warning" if warning else "pass",
        "validation": warning,
    }


@router.post("/json")
async def validate_json(
    request: ValidateJsonRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
):
    """Run both structural and AI validation on structured resume JSON.

    Returns field_validation (errors/warnings) and ai_validation (classification/scores).
    """
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])

    combined = validate_resume_output(request.resume_json, llm_config)
    return {
        "field_validation": combined["field_validation"],
        "ai_validation": combined["ai_validation"],
    }
