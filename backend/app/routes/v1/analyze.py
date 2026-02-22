from fastapi import APIRouter, Header, Depends
from typing import Optional

from app.dependencies import get_current_user
from app.models import AnalyzeRequest
from app.common import build_llm_config, safe_log_activity
from services.agent_controller import run_resume_pipeline

router = APIRouter()


@router.post("/quality")
async def analyze_quality(
    request: AnalyzeRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    llm_config = build_llm_config(x_openrouter_key, x_llm_model)
    output = run_resume_pipeline(task="score", resumes=[request.resume_text], llm_config=llm_config)

    score = output.get("score", {}).get("overall", 0)
    safe_log_activity(user_id, "quality", score=score)

    return output


@router.post("/gap")
async def analyze_gap(
    request: AnalyzeRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    llm_config = build_llm_config(x_openrouter_key, x_llm_model)
    output = run_resume_pipeline(task="skill_gap", resumes=[request.resume_text], query=request.jd_text, llm_config=llm_config)

    score = output.get("match_score", 0)
    safe_log_activity(user_id, "skill_gap", score=score)

    return output


@router.post("/screen")
async def analyze_screen(
    request: AnalyzeRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    llm_config = build_llm_config(x_openrouter_key, x_llm_model)
    output = run_resume_pipeline(
        task="screen",
        resumes=[request.resume_text],
        query=request.jd_text,
        llm_config=llm_config,
        threshold=request.threshold
    )

    score = output.get("score", {}).get("overall", 0)
    decision = "SELECTED" if output.get("decision", {}).get("selected") else "REJECTED"
    safe_log_activity(user_id, "screen", score=score, decision=decision)

    return output
