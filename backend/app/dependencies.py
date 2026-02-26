from typing import Optional
from fastapi import Header


async def get_current_user(authorization: Optional[str] = Header(None)):
    """Mock authentication dependency — returns user_id based on token.

    Token-to-user mapping:
      - Token contains "recruiter" or "linkedin" -> user_recruiter_456
      - Everything else -> user_alex_chen_123

    TODO: Replace with real JWT validation.
    """
    token = authorization.replace("Bearer ", "") if authorization else "guest"
    print(f"DEBUG: [auth] Authorization Header: '{authorization}' -> Token: '{token}'")

    if "recruiter" in token or "linkedin" in token:
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
    if missing:
        try:
            from app.common.encryption import decrypt_value
            from services.db.lancedb_client import get_user_settings

            stored = get_user_settings(user_id)
            key_map = {
                "openrouter_key": "openRouterKey",
                "linkedin_user": "linkedinUser",
                "linkedin_pass": "linkedinPass",
            }
            for internal_key, storage_key in key_map.items():
                if not result[internal_key] and stored.get(storage_key):
                    try:
                        result[internal_key] = decrypt_value(stored[storage_key])
                    except Exception as e:
                        print(f"DEBUG: Failed to decrypt {storage_key}: {e}")
        except Exception as e:
            print(f"DEBUG: Failed to resolve stored credentials: {e}")

    return result
