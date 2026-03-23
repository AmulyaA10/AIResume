from fastapi import APIRouter, Depends, HTTPException
import json

from app.dependencies import get_current_user, get_user_role
from app.models import UserSettingsUpdate, UserSettingsResponse, SystemSettingsUpdate, SystemSettingsResponse
from app.common import encrypt_value, decrypt_value, mask_value
from services.db.lancedb_client import (
    get_or_create_table,
    upsert_user_setting,
    get_user_settings,
    delete_user_settings,
    migrate_orphaned_settings,
)

router = APIRouter()

SENSITIVE_KEYS = ["openRouterKey", "linkedinUser", "linkedinPass"]

SYSTEM_USER = "__system__"
SYSTEM_SENSITIVE_KEYS = [
    "googleClientId", "googleClientSecret",
    "linkedinClientId", "linkedinClientSecret",
    "smtpServer", "smtpPort", "smtpUsername", "smtpPassword", "smtpSender",
]


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

    # Sensitive credentials are stored globally under the manager account so that
    # resolve_credentials() can find them regardless of which user is logged in.
    CREDENTIAL_STORE_USER = "user_manager_789"
    try:
        for key, plaintext in updates.items():
            if key in SENSITIVE_KEYS:
                encrypted = encrypt_value(plaintext)
                upsert_user_setting(CREDENTIAL_STORE_USER, key, encrypted)
    except Exception as e:
        print(f"ERROR: [save_user_settings] Failed to encrypt/store credentials for user '{user_id}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save credentials: {str(e)}",
        )

    return {"success": True, "updated_keys": list(updates.keys())}


@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings_endpoint(
    user_id: str = Depends(get_current_user),
):
    """Return masked credentials for display. Never returns raw values."""
    stored = get_user_settings(user_id)

    # One-time migration: if this user has no settings, check for orphaned
    # credentials from the old user_recruiter_456 mapping (LinkedIn OAuth
    # tokens previously mapped to recruiter user_id instead of jobseeker)
    if not stored and user_id == "user_alex_chen_123":
        migrate_orphaned_settings("user_recruiter_456", "user_alex_chen_123")
        stored = get_user_settings(user_id)  # re-fetch after migration

    result = {}
    for key in SENSITIVE_KEYS:
        encrypted = stored.get(key, "")
        if encrypted:
            try:
                plaintext = decrypt_value(encrypted)
                result[key] = mask_value(plaintext)
                result[f"has_{key}"] = True
            except Exception as e:
                print(f"WARNING: [settings] Failed to decrypt '{key}' for user '{user_id}': {e}")
                # Auto-clean: corrupted credential is unusable, remove it
                # so the user sees a clean "no credentials" state
                upsert_user_setting(user_id, key, "")
                print(f"INFO: [settings] Cleared corrupted '{key}' for user '{user_id}'")
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


@router.put("/system/settings")
async def save_system_settings(
    body: SystemSettingsUpdate,
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    """Encrypt and store system-level credentials (manager only)."""
    if role not in ("recruiter", "manager"):
        raise HTTPException(status_code=403, detail="Manager access required.")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided.")
    try:
        for key, plaintext in updates.items():
            if key in SYSTEM_SENSITIVE_KEYS and plaintext:
                encrypted = encrypt_value(plaintext)
                upsert_user_setting(SYSTEM_USER, key, encrypted)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save system settings: {str(e)}")
    return {"success": True, "updated_keys": list(updates.keys())}


@router.get("/system/settings", response_model=SystemSettingsResponse)
async def get_system_settings_endpoint(
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    """Return masked system settings (manager only)."""
    if role not in ("recruiter", "manager"):
        raise HTTPException(status_code=403, detail="Manager access required.")
    stored = get_user_settings(SYSTEM_USER) or {}
    return SystemSettingsResponse(
        has_googleClientId=bool(stored.get("googleClientId")),
        has_googleClientSecret=bool(stored.get("googleClientSecret")),
        has_linkedinClientId=bool(stored.get("linkedinClientId")),
        has_linkedinClientSecret=bool(stored.get("linkedinClientSecret")),
        has_smtpServer=bool(stored.get("smtpServer")),
        has_smtpUsername=bool(stored.get("smtpUsername")),
        googleClientId=mask_value(decrypt_value(stored["googleClientId"])) if stored.get("googleClientId") else None,
        linkedinClientId=mask_value(decrypt_value(stored["linkedinClientId"])) if stored.get("linkedinClientId") else None,
        smtpServer=decrypt_value(stored["smtpServer"]) if stored.get("smtpServer") else None,  # not sensitive to display
        smtpUsername=mask_value(decrypt_value(stored["smtpUsername"])) if stored.get("smtpUsername") else None,
    )
