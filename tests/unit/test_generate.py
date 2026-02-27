"""Unit tests for the resume generation endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
import io


@pytest.mark.asyncio
async def test_generate_resume(app, mock_generate_output):
    """POST /api/v1/generate/resume returns generated resume JSON."""
    with (
        patch("app.routes.v1.generate.run_resume_pipeline", return_value=mock_generate_output),
        patch("app.routes.v1.generate.run_resume_validation", return_value={}),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/generate/resume",
                json={"profile": "Experienced Python developer with 5 years building web APIs"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "resume" in data
    assert data["resume"]["contact"]["name"] == "Test User"


@pytest.mark.asyncio
async def test_generate_resume_missing_profile(app):
    """Generate endpoint requires profile field."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/generate/resume", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_docx(app):
    """POST /api/v1/generate/export returns a DOCX file stream."""
    resume_json = {
        "contact": {"name": "Test User", "email": "test@test.com"},
        "summary": "A great engineer.",
        "skills": ["Python"],
        "experience": [],
        "education": [],
    }

    # Use real generate_docx since it doesn't call external services
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/generate/export", json=resume_json)
    assert resp.status_code == 200
    assert "wordprocessingml" in resp.headers.get("content-type", "")
    assert len(resp.content) > 100  # Should be a valid DOCX binary


@pytest.mark.asyncio
async def test_export_empty_resume(app):
    """Export with minimal data still produces a DOCX."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/generate/export", json={})
    assert resp.status_code == 200
    assert len(resp.content) > 0


# ---- Post-Generation Output Validation ----

@pytest.mark.asyncio
async def test_generate_with_output_validation(app, mock_generate_output, mock_good_resume_validation):
    """Generate endpoint includes output_validation in response."""
    with (
        patch("app.routes.v1.generate.run_resume_pipeline", return_value=mock_generate_output),
        patch("app.routes.v1.generate.run_resume_validation", return_value=mock_good_resume_validation),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/generate/resume",
                json={"profile": "Senior Python developer specializing in distributed systems"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "resume" in data
    assert "output_validation" in data
    assert data["output_validation"]["classification"] == "resume_valid_good"
    assert data["output_validation"]["total_score"] == 22
