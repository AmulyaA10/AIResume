from app.routes.v1.auth import router as auth_router
from app.routes.v1.resumes import router as resumes_router
from app.routes.v1.dashboard import router as dashboard_router
from app.routes.v1.search import router as search_router
from app.routes.v1.analyze import router as analyze_router
from app.routes.v1.generate import router as generate_router
from app.routes.v1.linkedin import router as linkedin_router
from app.routes.v1.user import router as user_router
from app.routes.v1.health import router as health_router

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
