from fastapi import APIRouter, Depends, HTTPException
import json

from app.dependencies import get_current_user
from app.models import UserSettingsUpdate, UserSettingsResponse
from app.common import encrypt_value, decrypt_value, mask_value
from services.db.lancedb_client import (
    get_or_create_table,
    upsert_user_setting,
    get_user_settings,
    delete_user_settings,
)

router = APIRouter()

SENSITIVE_KEYS = ["openRouterKey", "linkedinUser", "linkedinPass"]


@router.get("/profile")
async def get_user_synced_profile(user_id: str = Depends(get_current_user)):
    """
    Fetches the most recent 'LinkedIn_Profile.pdf' content for the user.
    """
    table = get_or_create_table()

    # Filter by user_id AND filename
    results = table.search([0]*1536).where(f"user_id = '{user_id}' AND filename = 'LinkedIn_Profile.pdf'").limit(1).to_pandas()

    if results.empty:
        return {"found": False}

    row = results.iloc[0]
    text_content = row['text']

    try:
        # Try to parse the stored JSON
        resume_json = json.loads(text_content)

        # QUALITY CHECK: If it's just a name/email stub without real experience or summary,
        # we treat it as "not found" to force a real sync.
        has_summary = bool(resume_json.get("summary") and len(resume_json.get("summary", "")) > 50)
        has_exp = bool(resume_json.get("experience") and len(resume_json.get("experience", [])) > 0)

        if not (has_summary or has_exp) and not resume_json.get("error"):
            print(f"DEBUG: Found a stub for {user_id}, ignoring it to allow fresh sync.")
            return {"found": False}

        return {
            "found": True,
            "resume": resume_json
        }
    except:
        # Fallback if it's just raw text
        return {
            "found": True,
            "resume": {
                "contact": {"name": "Synced User", "email": "hidden@linkedin.com"},
                "summary": text_content[:500] + "...",
                "experience": [],
                "raw_text": text_content
            }
        }


@router.put("/settings")
async def save_user_settings(
    body: UserSettingsUpdate,
    user_id: str = Depends(get_current_user),
):
    """Encrypt and store user credentials server-side."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided.")

    for key, plaintext in updates.items():
        if key in SENSITIVE_KEYS:
            encrypted = encrypt_value(plaintext)
            upsert_user_setting(user_id, key, encrypted)

    return {"success": True, "updated_keys": list(updates.keys())}


@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings_endpoint(
    user_id: str = Depends(get_current_user),
):
    """Return masked credentials for display. Never returns raw values."""
    stored = get_user_settings(user_id)
    result = {}
    for key in SENSITIVE_KEYS:
        encrypted = stored.get(key, "")
        if encrypted:
            try:
                plaintext = decrypt_value(encrypted)
                result[key] = mask_value(plaintext)
                result[f"has_{key}"] = True
            except Exception:
                result[key] = None
                result[f"has_{key}"] = False
        else:
            result[key] = None
            result[f"has_{key}"] = False
    return result


@router.delete("/settings")
async def clear_user_settings(
    user_id: str = Depends(get_current_user),
):
    """Delete all stored credentials for the user."""
    delete_user_settings(user_id)
    return {"success": True, "message": "All credentials cleared."}
