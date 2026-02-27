import os
import sys

# CRITICAL: Add project root to sys.path so all modules can import from services/
# This is done ONCE here — all route files inherit it.
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.config import CORS_ORIGINS, UPLOAD_DIR, FRONTEND_URL


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
        jobs_router,
        match_router,
    )

    # --- API v1 routes ---
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["v1 — Authentication"])
    # Backward-compatible OAuth callback mount (redirect URIs registered in Google/LinkedIn consoles)
    app.include_router(auth_router, prefix="/api/auth", tags=["OAuth Compat"], include_in_schema=False)
    app.include_router(resumes_router, prefix="/api/v1/resumes", tags=["v1 — Resumes"])
    app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["v1 — Dashboard"])
    app.include_router(search_router, prefix="/api/v1", tags=["v1 — Search"])
    app.include_router(analyze_router, prefix="/api/v1/analyze", tags=["v1 — Analysis"])
    app.include_router(generate_router, prefix="/api/v1/generate", tags=["v1 — Generation"])
    app.include_router(linkedin_router, prefix="/api/v1/linkedin", tags=["v1 — LinkedIn"])
    app.include_router(user_router, prefix="/api/v1/user", tags=["v1 — User"])
    app.include_router(jobs_router, prefix="/api/v1/jobs", tags=["v1 — Jobs"])
    app.include_router(match_router, prefix="/api/v1/match", tags=["v1 — Matching"])
    app.include_router(health_router, tags=["Health"])

    # --- Root route: serve built frontend or show API info ---
    _frontend_dist = os.path.join(_project_root, "frontend", "dist")

    if os.path.isdir(_frontend_dist):
        # Serve the React SPA — static assets first, then catch-all for client-side routing
        @app.get("/", include_in_schema=False)
        async def serve_root():
            return FileResponse(os.path.join(_frontend_dist, "index.html"))

        app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="static-assets")

        # Catch-all for React Router — must be registered LAST
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            """Serve index.html for any non-API path (React Router catch-all)."""
            # Don't intercept API routes or health check
            if full_path.startswith("api/") or full_path == "health":
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            file_path = os.path.join(_frontend_dist, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(_frontend_dist, "index.html"))
    else:
        @app.get("/", include_in_schema=False)
        async def root_info():
            return {
                "service": "Resume Intelligence API",
                "version": "v1",
                "docs": "/docs",
                "health": "/health",
                "frontend": FRONTEND_URL,
                "hint": f"Frontend not built. Run 'cd frontend && npm run build' to serve UI from this port, or visit {FRONTEND_URL} for the dev server."
            }

    return app
