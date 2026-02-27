from fastapi import APIRouter, Header, Depends, HTTPException
from typing import Optional
import json

from app.dependencies import get_current_user, resolve_credentials
from app.models import SearchRequest
from app.config import LINKEDIN_LOGIN, LINKEDIN_PASSWORD
from app.common import build_llm_config, build_linkedin_creds, safe_log_activity
from app.common import decrypt_value
from services.agent_controller import generate_resume_from_linkedin
from services.db.lancedb_client import store_resume, get_user_settings, migrate_orphaned_settings

router = APIRouter()


def _resolve_credentials_sync(user_id: str) -> dict:
    """Synchronous credential resolution for background tasks.

    Checks server-stored (encrypted) credentials first, then falls back
    to environment variables. Also triggers orphan migration if needed.
    """
    li_user = None
    li_pass = None
    openrouter_key = None

    print(f"DEBUG: [_resolve_credentials_sync] user_id={user_id}")

    try:
        stored = get_user_settings(user_id)
        print(f"DEBUG: [_resolve_credentials_sync] get_user_settings('{user_id}') returned keys: {list(stored.keys()) if stored else '(empty)'}")

        # One-time migration for orphaned credentials
        if not stored and user_id == "user_alex_chen_123":
            print("DEBUG: [_resolve_credentials_sync] Triggering orphan migration...")
            migrate_orphaned_settings("user_recruiter_456", "user_alex_chen_123")
            stored = get_user_settings(user_id)
            print(f"DEBUG: [_resolve_credentials_sync] Post-migration keys: {list(stored.keys()) if stored else '(empty)'}")

        if stored:
            if stored.get("linkedinUser"):
                try:
                    li_user = decrypt_value(stored["linkedinUser"])
                    print(f"DEBUG: [_resolve_credentials_sync] Decrypted linkedinUser successfully (len={len(li_user)})")
                except Exception as e:
                    print(f"WARNING: [_resolve_credentials_sync] Decryption failed for linkedinUser: {e}")
            if stored.get("linkedinPass"):
                try:
                    li_pass = decrypt_value(stored["linkedinPass"])
                    print(f"DEBUG: [_resolve_credentials_sync] Decrypted linkedinPass successfully (len={len(li_pass)})")
                except Exception as e:
                    print(f"WARNING: [_resolve_credentials_sync] Decryption failed for linkedinPass: {e}")
            if stored.get("openRouterKey"):
                try:
                    openrouter_key = decrypt_value(stored["openRouterKey"])
                    print(f"DEBUG: [_resolve_credentials_sync] Decrypted openRouterKey successfully (len={len(openrouter_key)})")
                except Exception as e:
                    print(f"WARNING: [_resolve_credentials_sync] Decryption failed for openRouterKey: {e}")
    except Exception as e:
        print(f"ERROR: [_resolve_credentials_sync] OUTER EXCEPTION (user={user_id}): {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # Fall back to environment variables if server-stored values are missing
    li_user = li_user or LINKEDIN_LOGIN
    li_pass = li_pass or LINKEDIN_PASSWORD

    final_status = f"linkedin_user={'SET' if li_user else 'MISSING'}, linkedin_pass={'SET' if li_pass else 'MISSING'}, openrouter_key={'SET' if openrouter_key else 'MISSING'}"
    print(f"DEBUG: [_resolve_credentials_sync] Final: {final_status}")

    return {
        "linkedin_user": li_user,
        "linkedin_pass": li_pass,
        "openrouter_key": openrouter_key,
    }


def background_sync_linkedin(user_id: str, profile_url: str):
    """Background task for LinkedIn profile syncing."""
    print(f"--- [Background] Starting LinkedIn Sync for {user_id} at {profile_url} ---")

    creds = _resolve_credentials_sync(user_id)
    li_user = creds["linkedin_user"]
    li_pass = creds["linkedin_pass"]

    if not li_user or not li_pass:
        print("--- [Background] FAILED: Missing LinkedIn credentials ---")
        safe_log_activity(user_id, "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "MISSING_CREDS")
        error_json = json.dumps({
            "error": "LinkedIn scraper credentials not configured.",
            "raw_text": "Please save your LinkedIn email and password in Settings."
        })
        store_resume("LinkedIn_Profile.pdf", error_json, user_id, api_key=None)
        return

    llm_config = build_llm_config(creds["openrouter_key"], None)
    linkedin_creds = build_linkedin_creds(li_user, li_pass)

    try:
        output = generate_resume_from_linkedin(profile_url, llm_config=llm_config, linkedin_creds=linkedin_creds)

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

    # Early validation: fail fast with clear error before invoking pipeline
    if not linkedin_creds:
        print(f"ERROR: [linkedin_scrape] No LinkedIn creds resolved for {user_id}. "
              f"linkedin_user={'SET' if creds.get('linkedin_user') else 'MISSING'}, "
              f"linkedin_pass={'SET' if creds.get('linkedin_pass') else 'MISSING'}")
        raise HTTPException(
            status_code=422,
            detail="LinkedIn credentials could not be resolved. "
                   "Please save your LinkedIn email and password in Settings, "
                   "or check the server logs for credential resolution errors."
        )

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

<<<<<<< HEAD
    return output
=======
    # Return only non-sensitive fields — never expose credentials or API keys
    return {
        "resume": output.get("resume"),
        "error": output.get("error"),
    }
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
