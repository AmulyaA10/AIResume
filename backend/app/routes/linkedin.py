from fastapi import APIRouter, Header, Depends
from typing import Optional
import os
import json

from app.dependencies import get_current_user
from app.models import SearchRequest
from app.config import LINKEDIN_LOGIN, LINKEDIN_PASSWORD
from services.agent_controller import run_resume_pipeline, generate_resume_from_linkedin
from services.db.lancedb_client import store_resume, log_activity

router = APIRouter()


def background_sync_linkedin(user_id: str, profile_url: str):
    """Background task for LinkedIn profile syncing."""
    print(f"--- [Background] Starting LinkedIn Sync for {user_id} at {profile_url} ---")

    li_user = LINKEDIN_LOGIN
    li_pass = LINKEDIN_PASSWORD
    if not li_user or not li_pass:
        print("--- [Background] FAILED: Missing LinkedIn credentials in .env ---")
        log_activity(user_id, "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "MISSING_CREDS")
        error_json = json.dumps({
            "error": "LinkedIn scraper credentials missing in .env file.",
            "raw_text": "Please configure LinkedinLogin and LinkedinPassword in your server environment."
        })
        store_resume("LinkedIn_Profile.pdf", error_json, user_id, api_key=None)
        return

    try:
        output = generate_resume_from_linkedin(profile_url)

        if output and "resume" in output:
            resume_data = output["resume"]
            structured_text = json.dumps(resume_data, indent=2)

            store_resume("LinkedIn_Profile.pdf", structured_text, user_id, api_key=None)
            log_activity(user_id, "linkedin_sync_complete", "LinkedIn_Profile.pdf", 100, "SYNCED")
            print(f"--- [Background] LinkedIn Sync Complete for {user_id} ---")
        else:
            print(f"--- [Background] LinkedIn Sync returned no resume for {user_id} ---")
            log_activity(user_id, "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "NO_DATA")

    except Exception as e:
        print(f"--- [Background] LinkedIn Sync Failed: {e} ---")
        log_activity(user_id, "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "ERROR")


@router.post("/scrape")
async def linkedin_scrape(
    request: SearchRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    x_linkedin_user: Optional[str] = Header(None),
    x_linkedin_pass: Optional[str] = Header(None)
):
    llm_config = {"api_key": x_openrouter_key, "model": x_llm_model} if x_openrouter_key else None
    linkedin_creds = {"email": x_linkedin_user, "password": x_linkedin_pass} if x_linkedin_user and x_linkedin_pass else None
    output = generate_resume_from_linkedin(request.query, llm_config=llm_config, linkedin_creds=linkedin_creds)
    return output
