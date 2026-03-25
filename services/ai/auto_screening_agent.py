# services/ai/auto_screening_agent.py
"""Auto-Screening Agent

Triggered as a FastAPI BackgroundTask after every successful resume upload.
Matches the new resume against all open JDs and writes results to the
job_resume_applied table so recruiters see a pre-populated shortlist.

applied_status values written:
  "auto_shortlisted"  — score >= threshold (default 70)
  "auto_rejected"     — score <  threshold
"""
import asyncio
from typing import Optional

from services.ai.screening_graph import build_screening_graph

_AUTO_SCREEN_THRESHOLD = 70


def _get_candidate_contact(filename: str, user_id: str) -> tuple[str, str]:
    """Return (email, name) for a candidate from resume_meta. Falls back to ('', '')."""
    try:
        from services.db.lancedb_client import get_or_create_resume_meta_table
        meta_table = get_or_create_resume_meta_table()
        rows = meta_table.search().where(
            f"filename = '{filename}' AND user_id = '{user_id}'"
        ).limit(1).to_list()
        if rows:
            return str(rows[0].get("email") or ""), str(rows[0].get("candidate_name") or "")
    except Exception as e:
        print(f"DEBUG: [auto-screen] Could not look up candidate contact: {e}")
    return "", ""
_MAX_JDS_PER_UPLOAD = 20          # cap to avoid rate-limit saturation


async def run_auto_screening(
    filename: str,
    resume_text: str,
    user_id: str,
    llm_config: Optional[dict] = None,
    job_id_filter: Optional[str] = None,
    threshold: int = _AUTO_SCREEN_THRESHOLD,
    max_jds: int = _MAX_JDS_PER_UPLOAD,
) -> None:
    """Background task — match one resume against all open JDs.

    Results are written to job_resume_applied with auto_* status values.
    Any error is logged and swallowed so the upload response is never affected.
    """
    try:
        from services.db.lancedb_client import (
            get_or_create_jobs_table,
            get_or_create_job_applied_table,
        )
        from datetime import datetime

        # 1. Load open JDs (most recent first, capped)
        jobs_table = get_or_create_jobs_table()
        jobs_df = jobs_table.to_pandas()
        if jobs_df.empty:
            print(f"DEBUG: [auto-screen] No JDs found — skipping for {filename}")
            return

        # Optional: filter to a single job when triggered manually
        if job_id_filter:
            id_col = "job_id" if "job_id" in jobs_df.columns else jobs_df.columns[0]
            jobs_df = jobs_df[jobs_df[id_col].astype(str) == str(job_id_filter)]

        # Sort by posted_date descending if available
        if "posted_date" in jobs_df.columns:
            jobs_df = jobs_df.sort_values("posted_date", ascending=False)

        jobs = jobs_df.head(max_jds).to_dict("records")
        print(f"DEBUG: [auto-screen] Screening {filename} against {len(jobs)} JDs…")

        # 2. Build screening graph once; reuse across all JDs
        graph = build_screening_graph()

        # 3. Screen against each JD concurrently
        async def _screen_one(job: dict):
            jd_text = str(job.get("description") or job.get("title") or "")
            if not jd_text.strip():
                return None
            job_id = str(job.get("job_id") or job.get("id") or "")
            try:
                result = await graph.ainvoke({
                    "resume_text": resume_text,
                    "jd_text": jd_text,
                    "threshold": threshold,
                    "score": None,
                    "decision": None,
                    "config": llm_config,
                })
                score = (result.get("score") or {}).get("overall", 0)
                selected = (result.get("decision") or {}).get("selected", False)
                return {
                    "job_id": job_id,
                    "score": score,
                    "selected": selected,
                }
            except Exception as e:
                print(f"DEBUG: [auto-screen] screening against job {job_id} failed: {e}")
                return None

        screen_results = await asyncio.gather(*[_screen_one(j) for j in jobs])

        # 4. Persist results
        applied_table = get_or_create_job_applied_table()
        rows_to_add = []
        for res in screen_results:
            if res is None or not res["selected"]:
                continue  # only persist shortlisted matches
            rows_to_add.append({
                "user_id": user_id,
                "job_id": res["job_id"],
                "resume_id": filename,
                "applied_status": "auto_shortlisted",
                "timestamp": datetime.now().isoformat(),
                "notified": False,
                "notified_at": "",
            })

        if rows_to_add:
            import pandas as pd
            applied_table.add(pd.DataFrame(rows_to_add))
            print(
                f"DEBUG: [auto-screen] {filename} — {len(rows_to_add)} shortlisted "
                f"(threshold={threshold}, screened={len([r for r in screen_results if r])})"
            )

            # 5. Email candidate for each shortlisted job
            if rows_to_add:
                candidate_email, candidate_name = _get_candidate_contact(filename, user_id)
                if candidate_email:
                    from services.email_service import send_candidate_shortlisted
                    # Build job_id → title map once
                    title_map = {str(j.get("job_id") or j.get("id") or ""): str(j.get("title", "")) for j in jobs}
                    for row in rows_to_add:
                        jid = row["job_id"]
                        job_title = title_map.get(jid, jid)
                        send_candidate_shortlisted(
                            candidate_email=candidate_email,
                            candidate_name=candidate_name,
                            job_title=job_title,
                            employer_name="",
                        )
                else:
                    print(f"DEBUG: [auto-screen] No email found for {filename} — skipping candidate notification")

    except Exception as e:
        print(f"DEBUG: [auto-screen] background task failed for {filename}: {e}")
