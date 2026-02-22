from fastapi import APIRouter, Header, Depends
from typing import Optional

from app.dependencies import get_current_user
from app.models import AnalyzeRequest
from services.agent_controller import run_resume_pipeline
from services.db.lancedb_client import log_activity

router = APIRouter()


@router.post("/quality")
async def analyze_quality(
    request: AnalyzeRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    llm_config = {"api_key": x_openrouter_key, "model": x_llm_model} if x_openrouter_key else None
    output = run_resume_pipeline(task="score", resumes=[request.resume_text], llm_config=llm_config)

    # Log activity
    try:
        score = output.get("score", {}).get("overall", 0)
        log_activity(user_id, "quality", "Manual Input", score)
    except Exception as e:
        print(f"DEBUG: Failed to log quality activity: {e}")

    return output


@router.post("/gap")
async def analyze_gap(
    request: AnalyzeRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    llm_config = {"api_key": x_openrouter_key, "model": x_llm_model} if x_openrouter_key else None
    output = run_resume_pipeline(task="skill_gap", resumes=[request.resume_text], query=request.jd_text, llm_config=llm_config)

    # Log activity
    try:
        score = output.get("match_score", 0)
        log_activity(user_id, "skill_gap", "Manual Input", score)
    except Exception as e:
        print(f"DEBUG: Failed to log skill_gap activity: {e}")

    return output


@router.post("/screen")
async def analyze_screen(
    request: AnalyzeRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    llm_config = {"api_key": x_openrouter_key, "model": x_llm_model} if x_openrouter_key else None
    output = run_resume_pipeline(
        task="screen",
        resumes=[request.resume_text],
        query=request.jd_text,
        llm_config=llm_config,
        threshold=request.threshold
    )

    # Log activity
    try:
        score = output.get("score", {}).get("overall", 0)
        decision = "SELECTED" if output.get("decision", {}).get("selected") else "REJECTED"
        log_activity(user_id, "screen", "Manual Input", score, decision)
    except Exception as e:
        print(f"DEBUG: Failed to log screen activity: {e}")

    return output
