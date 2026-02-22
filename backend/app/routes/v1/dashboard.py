from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from services.db.lancedb_client import get_dashboard_stats

router = APIRouter()


@router.get("/stats")
async def dashboard_stats(user_id: str = Depends(get_current_user)):
    return get_dashboard_stats(user_id)
