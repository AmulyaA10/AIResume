from app.routes.auth import router as auth_router
from app.routes.resumes import router as resumes_router
from app.routes.dashboard import router as dashboard_router
from app.routes.search import router as search_router
from app.routes.analyze import router as analyze_router
from app.routes.generate import router as generate_router
from app.routes.linkedin import router as linkedin_router
from app.routes.user import router as user_router
from app.routes.health import router as health_router

__all__ = [
    "auth_router",
    "resumes_router",
    "dashboard_router",
    "search_router",
    "analyze_router",
    "generate_router",
    "linkedin_router",
    "user_router",
    "health_router",
]
