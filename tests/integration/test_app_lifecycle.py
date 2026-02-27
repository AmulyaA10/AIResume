"""Integration tests — verify the full app wiring, middleware, and cross-cutting concerns.

These tests spin up the real FastAPI app (via the factory) and exercise
the HTTP stack end-to-end.  External services (LLM, DB) are still mocked
so the tests run without network access or API keys.
"""

import io
import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


# ── App startup ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_app_starts_and_health_responds(app):
    """Smoke test: the app factory produces a working ASGI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_openapi_docs_available(app):
    """FastAPI auto-generates /docs and /openapi.json."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert "/health" in schema["paths"]


# ── CORS ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cors_headers_present(app):
    """CORS middleware adds the correct headers on preflight."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


# ── Auth flow ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_login_then_access_protected_route(app, mock_dashboard_stats):
    """Full flow: login → receive token → access protected dashboard."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Step 1: Login
        login_resp = await c.post(
            "/api/v1/auth/login",
            json={"username": "recruit", "password": "admin123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]

        # Step 2: Use token to hit protected endpoint
        with patch("app.routes.v1.dashboard.get_dashboard_stats", return_value=mock_dashboard_stats):
            dash_resp = await c.get(
                "/api/v1/dashboard/stats",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert dash_resp.status_code == 200
        assert dash_resp.json()["total_resumes"] == 5


@pytest.mark.asyncio
async def test_recruiter_token_resolves_correct_user(app, mock_dashboard_stats):
    """Recruiter token should map to user_recruiter_456."""
    with patch("app.routes.v1.dashboard.get_dashboard_stats", return_value=mock_dashboard_stats) as mock_fn:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                "/api/v1/dashboard/stats",
                headers={"Authorization": "Bearer mock-recruiter-token"},
            )
    assert resp.status_code == 200
    mock_fn.assert_called_with("user_recruiter_456")


@pytest.mark.asyncio
async def test_default_token_resolves_jobseeker_user(app, mock_dashboard_stats):
    """Non-recruiter token maps to user_alex_chen_123."""
    with patch("app.routes.v1.dashboard.get_dashboard_stats", return_value=mock_dashboard_stats) as mock_fn:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                "/api/v1/dashboard/stats",
                headers={"Authorization": "Bearer some-random-token"},
            )
    assert resp.status_code == 200
    mock_fn.assert_called_with("user_alex_chen_123")


# ── Upload → Validation → Storage pipeline ──────────────────────────────────

@pytest.mark.asyncio
async def test_upload_validate_store_pipeline(app, auth_headers, mock_validation_result):
    """Integration: upload triggers validation + storage + activity logging."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake resume content")

    with (
        patch("app.routes.v1.resumes.extract_text", return_value="JOHN DOE\nSenior Engineer\nPython, React..."),
        patch("app.routes.v1.resumes.run_resume_validation", return_value=mock_validation_result) as mock_val,
        patch("app.routes.v1.resumes.store_resume") as mock_store,
        patch("app.routes.v1.resumes.safe_log_activity") as mock_log,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/resumes/upload",
                headers=auth_headers,
                files={"files": ("resume.pdf", fake_pdf, "application/pdf")},
                data={"store_db": "true", "validate": "true"},
            )

    assert resp.status_code == 200
    result = resp.json()["processed"][0]

    # Validation was called
    mock_val.assert_called_once()

    # Storage was called
    mock_store.assert_called_once()

    # Activity was logged
    mock_log.assert_called_once()

    # Response shape is correct
    assert result["filename"] == "resume.pdf"
    assert result["validation"]["classification"] == "resume_valid_good"


# ── Analyze pipeline (quality → gap → screen) ───────────────────────────────

@pytest.mark.asyncio
async def test_full_analysis_pipeline(
    app, auth_headers, sample_resume_text, sample_jd_text,
    mock_quality_output, mock_gap_output, mock_screen_output,
):
    """Integration: run quality → gap → screen sequentially for the same resume."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Quality
        with (
            patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
            patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_quality_output),
            patch("app.routes.v1.analyze.safe_log_activity"),
        ):
            q_resp = await c.post(
                "/api/v1/analyze/quality",
                json={"resume_text": sample_resume_text},
                headers=auth_headers,
            )
        assert q_resp.status_code == 200
        assert q_resp.json()["score"]["overall"] == 78

        # Gap
        with (
            patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
            patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_gap_output),
            patch("app.routes.v1.analyze.safe_log_activity"),
        ):
            g_resp = await c.post(
                "/api/v1/analyze/gap",
                json={"resume_text": sample_resume_text, "jd_text": sample_jd_text},
                headers=auth_headers,
            )
        assert g_resp.status_code == 200
        assert g_resp.json()["match_score"] == 65

        # Screen
        with (
            patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
            patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_screen_output),
            patch("app.routes.v1.analyze.safe_log_activity"),
        ):
            s_resp = await c.post(
                "/api/v1/analyze/screen",
                json={"resume_text": sample_resume_text, "jd_text": sample_jd_text, "threshold": 75},
                headers=auth_headers,
            )
        assert s_resp.status_code == 200
        assert s_resp.json()["decision"]["selected"] is True


# ── Generate → Export pipeline ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_then_export(app, mock_generate_output):
    """Integration: generate a resume then export to DOCX."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Generate
        with (
            patch("app.routes.v1.generate.precheck_resume_validation", return_value=None),
            patch("app.routes.v1.generate.run_resume_pipeline", return_value=mock_generate_output),
            patch("app.routes.v1.generate.run_resume_validation", return_value={}),
        ):
            gen_resp = await c.post(
                "/api/v1/generate/resume",
                json={"profile": "Python dev with 5 years experience"},
            )
        assert gen_resp.status_code == 200
        resume_json = gen_resp.json()["resume"]

        # Export the generated resume
        export_resp = await c.post("/api/v1/generate/export", json=resume_json)
        assert export_resp.status_code == 200
        assert "wordprocessingml" in export_resp.headers.get("content-type", "")
        assert len(export_resp.content) > 100


# ── Route versioning ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_v1_prefix(app):
    """All API routes are accessible under /api/v1/."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        schema = (await c.get("/openapi.json")).json()
    paths = list(schema["paths"].keys())

    api_paths = [p for p in paths if p.startswith("/api/")]
    for path in api_paths:
        assert path.startswith("/api/v1/"), f"Route {path} is not under /api/v1/"


@pytest.mark.asyncio
async def test_nonexistent_route_returns_404(app):
    """Hitting a non-existent API route returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/nonexistent")
    assert resp.status_code == 404


# ── Error propagation ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_error_propagates(app, auth_headers, sample_resume_text):
    """When the AI pipeline throws, the error propagates (unhandled)."""
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
        patch("app.routes.v1.analyze.run_resume_pipeline", side_effect=Exception("LLM timeout")),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as c:
            resp = await c.post(
                "/api/v1/analyze/quality",
                json={"resume_text": sample_resume_text},
                headers=auth_headers,
            )
    # FastAPI returns 500 for unhandled exceptions
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_validation_error_does_not_block_upload(app, auth_headers):
    """When validation agent fails, file is still stored."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 content")

    with (
        patch("app.routes.v1.resumes.extract_text", return_value="Some resume text"),
        patch("app.routes.v1.resumes.run_resume_validation", side_effect=Exception("LLM down")),
        patch("app.routes.v1.resumes.store_resume") as mock_store,
        patch("app.routes.v1.resumes.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/resumes/upload",
                headers=auth_headers,
                files={"files": ("resume.pdf", fake_pdf, "application/pdf")},
                data={"store_db": "true", "validate": "true"},
            )

    assert resp.status_code == 200
    result = resp.json()["processed"][0]
    # File was stored despite validation failure
    mock_store.assert_called_once()
    # Validation result contains the error
    assert "error" in result["validation"]


# ── LinkedIn credential resolution ────────────────────────────────────────

@pytest.mark.asyncio
async def test_linkedin_scrape_resolves_stored_credentials(
    app, auth_headers, mock_linkedin_output
):
    """LinkedIn scrape resolves credentials from server storage when headers are absent."""
    from cryptography.fernet import Fernet

    _test_key = Fernet.generate_key().decode()

    with patch.dict(os.environ, {"ENCRYPTION_KEY": _test_key}):
        import app.common.encryption as enc_mod
        old_key = enc_mod._ENCRYPTION_KEY
        enc_mod._ENCRYPTION_KEY = _test_key
        try:
            from app.common.encryption import encrypt_value

            stored = {
                "openRouterKey": encrypt_value("test-api-key"),
                "linkedinUser": encrypt_value("test@linkedin.com"),
                "linkedinPass": encrypt_value("test-pass"),
            }

            with (
                patch("services.db.lancedb_client.get_user_settings", return_value=stored),
                patch(
                    "app.routes.v1.linkedin.generate_resume_from_linkedin",
                    return_value=mock_linkedin_output,
                ) as mock_pipeline,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.post(
                        "/api/v1/linkedin/scrape",
                        json={"query": "https://www.linkedin.com/in/janedoe"},
                        headers=auth_headers,  # auth only, no credential headers
                    )

            assert resp.status_code == 200
            assert "resume" in resp.json()
            # Pipeline was called — proving credentials resolved from storage
            mock_pipeline.assert_called_once()
        finally:
            enc_mod._ENCRYPTION_KEY = old_key
