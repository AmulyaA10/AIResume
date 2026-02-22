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
