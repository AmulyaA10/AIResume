import os
import sys

# CRITICAL: Add project root to sys.path so all modules can import from services/
# This is done ONCE here — all route files inherit it.
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS, UPLOAD_DIR


def create_app() -> FastAPI:
    """Factory function to create and configure the FastAPI application."""

    app = FastAPI(title="Resume Intelligence API")

    # Configure CORS for React
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Import and include routers
    from app.routes import (
        auth_router,
        resumes_router,
        dashboard_router,
        search_router,
        analyze_router,
        generate_router,
        linkedin_router,
        user_router,
        health_router,
    )

    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(resumes_router, prefix="/api/resumes", tags=["Resumes"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(search_router, prefix="/api", tags=["Search"])
    app.include_router(analyze_router, prefix="/api/analyze", tags=["Analysis"])
    app.include_router(generate_router, prefix="/api/generate", tags=["Generation"])
    app.include_router(linkedin_router, prefix="/api/linkedin", tags=["LinkedIn"])
    app.include_router(user_router, prefix="/api/user", tags=["User"])
    app.include_router(health_router, tags=["Health"])

    return app
