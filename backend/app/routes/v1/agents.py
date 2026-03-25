"""Autonomous agent management endpoints.

Exposes stats, history, config and manual-trigger controls for the
background auto-screening agent that runs after every resume upload.
"""
from fastapi import APIRouter, Depends, BackgroundTasks, Header
from pydantic import BaseModel
from typing import Optional
import pandas as pd

from app.dependencies import get_current_user, resolve_credentials
from app.common import build_llm_config
from services.db.lancedb_client import (
    get_or_create_job_applied_table,
    get_or_create_jobs_table,
    get_user_settings,
    upsert_user_setting,
)

router = APIRouter()

_DEFAULT_THRESHOLD = 70
_DEFAULT_MAX_JDS = 20


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_applied_df() -> pd.DataFrame:
    try:
        df = get_or_create_job_applied_table().to_pandas()
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _get_jobs_df() -> pd.DataFrame:
    try:
        df = get_or_create_jobs_table().to_pandas()
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _read_agent_config(user_id: str) -> dict:
    stored = get_user_settings(user_id) or {}
    return {
        "threshold": int(stored.get("agent_threshold", _DEFAULT_THRESHOLD)),
        "max_jds": int(stored.get("agent_max_jds", _DEFAULT_MAX_JDS)),
        "enabled": stored.get("agent_enabled", "true").lower() == "true",
        "jd_enabled": stored.get("agent_jd_enabled", "true").lower() == "true",
    }


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/screening/stats")
async def get_screening_stats(user_id: str = Depends(get_current_user)):
    """Aggregate stats for the autonomous screening agent."""
    adf = _get_applied_df()
    jdf = _get_jobs_df()

    if adf.empty:
        return {
            "total_screened": 0,
            "shortlisted": 0,
            "rejected": 0,
            "pass_rate": 0.0,
            "jobs_covered": 0,
            "resumes_covered": 0,
            "per_job": [],
        }

    ai_df = adf[adf["applied_status"].isin(["auto_shortlisted", "auto_rejected"])].copy()
    total = len(ai_df)
    shortlisted = int((ai_df["applied_status"] == "auto_shortlisted").sum())
    rejected = int((ai_df["applied_status"] == "auto_rejected").sum())
    pass_rate = round(shortlisted / total * 100, 1) if total else 0.0

    # Per-job breakdown
    per_job = []
    if not ai_df.empty and not jdf.empty:
        # Build job_id → title map
        id_col = "job_id" if "job_id" in jdf.columns else (jdf.columns[0] if not jdf.empty else None)
        title_map: dict = {}
        if id_col:
            for _, row in jdf.iterrows():
                title_map[str(row.get(id_col, ""))] = str(row.get("title", ""))

        for job_id, grp in ai_df.groupby("job_id"):
            jid = str(job_id)
            sl = int((grp["applied_status"] == "auto_shortlisted").sum())
            rj = int((grp["applied_status"] == "auto_rejected").sum())
            tot = sl + rj
            per_job.append({
                "job_id": jid,
                "title": title_map.get(jid, jid),
                "screened": tot,
                "shortlisted": sl,
                "rejected": rj,
                "pass_rate": round(sl / tot * 100, 1) if tot else 0.0,
            })
        per_job.sort(key=lambda x: x["screened"], reverse=True)

    return {
        "total_screened": total,
        "shortlisted": shortlisted,
        "rejected": rejected,
        "pass_rate": pass_rate,
        "jobs_covered": int(ai_df["job_id"].nunique()) if not ai_df.empty else 0,
        "resumes_covered": int(ai_df["resume_id"].nunique()) if not ai_df.empty else 0,
        "per_job": per_job,
    }


@router.get("/screening/history")
async def get_screening_history(
    limit: int = 50,
    job_id: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    """Recent autonomous screening results, newest first."""
    adf = _get_applied_df()
    if adf.empty:
        return []

    ai_df = adf[adf["applied_status"].isin(["auto_shortlisted", "auto_rejected"])].copy()
    if job_id:
        ai_df = ai_df[ai_df["job_id"] == job_id]

    if ai_df.empty:
        return []

    # Sort newest first
    if "timestamp" in ai_df.columns:
        ai_df = ai_df.sort_values("timestamp", ascending=False)

    ai_df = ai_df.head(limit)

    # Enrich with job titles
    jdf = _get_jobs_df()
    title_map: dict = {}
    if not jdf.empty:
        id_col = "job_id" if "job_id" in jdf.columns else jdf.columns[0]
        for _, row in jdf.iterrows():
            title_map[str(row.get(id_col, ""))] = str(row.get("title", ""))

    records = []
    for _, row in ai_df.iterrows():
        jid = str(row.get("job_id", ""))
        records.append({
            "resume_id": row.get("resume_id", ""),
            "job_id": jid,
            "job_title": title_map.get(jid, jid),
            "status": row.get("applied_status", ""),
            "timestamp": row.get("timestamp", ""),
        })
    return records


class AgentConfigUpdate(BaseModel):
    threshold: Optional[int] = None
    max_jds: Optional[int] = None
    enabled: Optional[bool] = None
    jd_enabled: Optional[bool] = None


@router.get("/screening/config")
async def get_agent_config(user_id: str = Depends(get_current_user)):
    return _read_agent_config(user_id)


@router.put("/screening/config")
async def save_agent_config(
    body: AgentConfigUpdate,
    user_id: str = Depends(get_current_user),
):
    if body.threshold is not None:
        upsert_user_setting(user_id, "agent_threshold", str(body.threshold))
    if body.max_jds is not None:
        upsert_user_setting(user_id, "agent_max_jds", str(body.max_jds))
    if body.enabled is not None:
        upsert_user_setting(user_id, "agent_enabled", str(body.enabled).lower())
    if body.jd_enabled is not None:
        upsert_user_setting(user_id, "agent_jd_enabled", str(body.jd_enabled).lower())
    return _read_agent_config(user_id)


class ManualRunRequest(BaseModel):
    resume_id: str
    job_id: Optional[str] = None   # None = screen against all open JDs


@router.post("/screening/run")
async def trigger_manual_screening(
    body: ManualRunRequest,
    background_tasks: BackgroundTasks,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
):
    """Manually trigger autonomous screening for a specific resume."""
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])

    # Load resume text from uploaded file
    import os
    from fastapi import HTTPException
    from app.config import UPLOAD_DIR
    from services.resume_parser import extract_text, to_ats_text
    file_path = os.path.join(UPLOAD_DIR, body.resume_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resume file not found")
    resume_text = to_ats_text(extract_text(file_path))

    agent_cfg = _read_agent_config(user_id)

    from services.ai.auto_screening_agent import run_auto_screening
    background_tasks.add_task(
        run_auto_screening,
        body.resume_id,
        resume_text,
        user_id,
        llm_config,
        job_id_filter=body.job_id,
        threshold=agent_cfg["threshold"],
        max_jds=agent_cfg["max_jds"],
    )
    return {"queued": True, "resume_id": body.resume_id, "job_id": body.job_id}


@router.post("/screening/run-all")
async def trigger_full_screening(
    background_tasks: BackgroundTasks,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
):
    """Manually screen every resume against every open JD."""
    import os
    from app.config import UPLOAD_DIR
    from services.resume_parser import extract_text, to_ats_text

    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])

    agent_cfg = _read_agent_config(user_id)

    # Collect all resumes that have a readable file
    from services.db.lancedb_client import get_or_create_resume_meta_table
    meta_df = pd.DataFrame()
    try:
        meta_df = get_or_create_resume_meta_table().to_pandas()
        meta_df = meta_df.drop_duplicates(subset=["filename"], keep="last") if not meta_df.empty else meta_df
    except Exception:
        pass

    if meta_df.empty:
        return {"queued": False, "reason": "No resumes found", "resume_count": 0}

    from services.ai.auto_screening_agent import run_auto_screening

    queued = 0
    for _, row in meta_df.iterrows():
        filename = str(row.get("filename", ""))
        candidate_user_id = str(row.get("user_id", user_id))
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not filename or not os.path.exists(file_path):
            continue
        try:
            resume_text = to_ats_text(extract_text(file_path))
        except Exception:
            continue
        if not resume_text.strip():
            continue
        background_tasks.add_task(
            run_auto_screening,
            filename,
            resume_text,
            candidate_user_id,
            llm_config,
            threshold=agent_cfg["threshold"],
            max_jds=agent_cfg["max_jds"],
        )
        queued += 1

    return {"queued": True, "resume_count": queued}
