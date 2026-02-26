from fastapi import APIRouter, Header, Depends, HTTPException
from typing import Optional
import json

from app.dependencies import get_current_user, resolve_credentials
from app.models import SearchRequest
from app.config import LINKEDIN_LOGIN, LINKEDIN_PASSWORD
from app.common import build_llm_config, build_linkedin_creds, safe_log_activity
from services.agent_controller import generate_resume_from_linkedin
from services.db.lancedb_client import store_resume

router = APIRouter()


def background_sync_linkedin(user_id: str, profile_url: str):
    """Background task for LinkedIn profile syncing."""
    print(f"--- [Background] Starting LinkedIn Sync for {user_id} at {profile_url} ---")

    li_user = LINKEDIN_LOGIN
    li_pass = LINKEDIN_PASSWORD
    if not li_user or not li_pass:
        print("--- [Background] FAILED: Missing LinkedIn credentials in .env ---")
        safe_log_activity(user_id, "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "MISSING_CREDS")
        error_json = json.dumps({
            "error": "LinkedIn scraper credentials missing in .env file.",
            "raw_text": "Please configure LinkedinLogin and LinkedinPassword in your server environment."
        })
        store_resume("LinkedIn_Profile.pdf", error_json, user_id, api_key=None)
        return

    try:
        output = generate_resume_from_linkedin(profile_url)

        if output and output.get("resume"):
            resume_data = output["resume"]
            structured_text = json.dumps(resume_data, indent=2)

            store_resume("LinkedIn_Profile.pdf", structured_text, user_id, api_key=None)
            safe_log_activity(user_id, "linkedin_sync_complete", "LinkedIn_Profile.pdf", 100, "SYNCED")
            print(f"--- [Background] LinkedIn Sync Complete for {user_id} ---")
        else:
            error_msg = output.get("error", "No resume data returned") if output else "No output from pipeline"
            print(f"--- [Background] LinkedIn Sync returned no resume for {user_id}: {error_msg} ---")
            safe_log_activity(user_id, "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "NO_DATA")

    except Exception as e:
        print(f"--- [Background] LinkedIn Sync Failed: {e} ---")
        safe_log_activity(user_id, "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "ERROR")


@router.post("/scrape")
async def linkedin_scrape(
    request: SearchRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    x_linkedin_user: Optional[str] = Header(None),
    x_linkedin_pass: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model, x_linkedin_user, x_linkedin_pass)
    llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])
    linkedin_creds = build_linkedin_creds(creds["linkedin_user"], creds["linkedin_pass"])

    try:
        output = generate_resume_from_linkedin(request.query, llm_config=llm_config, linkedin_creds=linkedin_creds)
    except Exception as e:
        print(f"--- LinkedIn scrape pipeline error: {e} ---")
        raise HTTPException(status_code=500, detail=f"LinkedIn scraping failed: {str(e)}")

    if not output:
        raise HTTPException(status_code=500, detail="LinkedIn pipeline returned no output.")

    if output.get("error"):
        raise HTTPException(status_code=422, detail=output["error"])

    if not output.get("resume"):
        raise HTTPException(status_code=422, detail="Could not extract resume data from the LinkedIn profile. The profile may be private or the scraper credentials may be missing.")

    return output
