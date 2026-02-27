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
    jobs_router,
    match_router,
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
    "jobs_router",
    "match_router",
]
