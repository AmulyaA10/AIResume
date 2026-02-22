from fastapi import APIRouter, Depends
import json

from app.dependencies import get_current_user
from services.db.lancedb_client import get_or_create_table

router = APIRouter()


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
