# Re-export v1 routers for use by the app factory.
# When v2 is introduced, add a v2/ package alongside v1/.
from app.routes.v1 import (
    auth_router,
    resumes_router,
    dashboard_router,
    search_router,
    analyze_router,
    generate_router,
    linkedin_router,
    user_router,
    health_router,
<<<<<<< HEAD
    jobs_router,
    match_router,
=======
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
)

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
