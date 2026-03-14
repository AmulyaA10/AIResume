from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_user_role
from services.db.lancedb_client import get_dashboard_stats

router = APIRouter()


@router.get("/stats")
async def dashboard_stats(
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    is_recruiter = role in ("recruiter", "manager")
    return get_dashboard_stats(user_id, is_recruiter=is_recruiter)
