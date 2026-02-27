from app.routes.v1.auth import router as auth_router
from app.routes.v1.resumes import router as resumes_router
from app.routes.v1.dashboard import router as dashboard_router
from app.routes.v1.search import router as search_router
from app.routes.v1.analyze import router as analyze_router
from app.routes.v1.generate import router as generate_router
from app.routes.v1.linkedin import router as linkedin_router
from app.routes.v1.user import router as user_router
from app.routes.v1.health import router as health_router
<<<<<<< HEAD
from app.routes.v1.jobs import router as jobs_router
from app.routes.v1.match import router as match_router
=======
>>>>>>> 9d136502ee9374e86211849855e67746afb88872

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
<<<<<<< HEAD
    "jobs_router",
    "match_router",
=======
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
]
