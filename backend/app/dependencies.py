from typing import Optional
from fastapi import Header


async def get_current_user(authorization: Optional[str] = Header(None)):
    """Mock authentication dependency — returns user_id based on token.

    Token-to-user mapping:
      - Token contains "recruiter" -> user_recruiter_456
      - Everything else (including OAuth: google, linkedin) -> user_alex_chen_123

    NOTE: LinkedIn OAuth users are jobseekers, not recruiters.
    Only the corporate SSO "mock-recruiter-token" maps to the recruiter user.

    TODO: Replace with real JWT validation.
    """
    token = authorization.replace("Bearer ", "") if authorization else "guest"
    print(f"DEBUG: [auth] Authorization Header: '{authorization}' -> Token: '{token}'")

    if "recruiter" in token:
        user_id = "user_recruiter_456"
    else:
        user_id = "user_alex_chen_123"

    print(f"DEBUG: [auth] Resolved User ID: {user_id}")
    return user_id


async def resolve_credentials(
    user_id: str,
    x_openrouter_key: Optional[str] = None,
    x_llm_model: Optional[str] = None,
    x_linkedin_user: Optional[str] = None,
    x_linkedin_pass: Optional[str] = None,
) -> dict:
    """Resolve credentials: header values take priority, then fall back to
    server-side stored (encrypted) values for the user.

    Returns a dict with keys: openrouter_key, llm_model, linkedin_user, linkedin_pass.
    """
    result = {
        "openrouter_key": x_openrouter_key,
        "llm_model": x_llm_model,
        "linkedin_user": x_linkedin_user,
        "linkedin_pass": x_linkedin_pass,
    }

    missing = [k for k, v in result.items() if not v and k != "llm_model"]
    print(f"DEBUG: [resolve_credentials] user_id={user_id}, missing_keys={missing}")

    if missing:
        try:
            from app.common.encryption import decrypt_value
            from services.db.lancedb_client import get_user_settings, migrate_orphaned_settings

            stored = get_user_settings(user_id)
            print(f"DEBUG: [resolve_credentials] get_user_settings('{user_id}') returned keys: {list(stored.keys()) if stored else '(empty)'}")

            # One-time migration: if no settings found for this user, check
            # for orphaned credentials from the old recruiter user ID mapping
            if not stored and user_id == "user_alex_chen_123":
                print("DEBUG: [resolve_credentials] Triggering orphan migration...")
                migrate_orphaned_settings("user_recruiter_456", "user_alex_chen_123")
                stored = get_user_settings(user_id)
                print(f"DEBUG: [resolve_credentials] Post-migration keys: {list(stored.keys()) if stored else '(empty)'}")

            key_map = {
                "openrouter_key": "openRouterKey",
                "linkedin_user": "linkedinUser",
                "linkedin_pass": "linkedinPass",
            }
            for internal_key, storage_key in key_map.items():
                if not result[internal_key] and stored.get(storage_key):
                    try:
                        result[internal_key] = decrypt_value(stored[storage_key])
                        print(f"DEBUG: [resolve_credentials] Decrypted '{storage_key}' successfully (len={len(result[internal_key])})")
                    except Exception as e:
                        print(f"WARNING: [resolve_credentials] Decryption failed for '{storage_key}' (user={user_id}): {e}")
                        # Auto-clean the corrupted entry so user can re-enter
                        try:
                            from services.db.lancedb_client import upsert_user_setting
                            upsert_user_setting(user_id, storage_key, "")
                            print(f"INFO: [resolve_credentials] Cleared corrupted '{storage_key}' for user '{user_id}'")
                        except Exception:
                            pass
                else:
                    if not result[internal_key]:
                        print(f"DEBUG: [resolve_credentials] No stored value for '{storage_key}'")
        except Exception as e:
            print(f"ERROR: [resolve_credentials] OUTER EXCEPTION (user={user_id}): {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    resolved_keys = [k for k, v in result.items() if v]
    print(f"DEBUG: [resolve_credentials] Final resolved keys: {resolved_keys}")
    return result
