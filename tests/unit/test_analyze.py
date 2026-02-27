"""Unit tests for the analysis endpoints (quality, gap, screen)."""

import pytest
from unittest.mock import patch
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport


# ---- Quality Scoring ----

@pytest.mark.asyncio
async def test_quality_scoring(app, auth_headers, sample_resume_text, mock_quality_output):
    """POST /api/v1/analyze/quality returns quality scores."""
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_quality_output),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/quality",
                json={"resume_text": sample_resume_text},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert data["score"]["overall"] == 78


@pytest.mark.asyncio
async def test_quality_missing_resume_text(app, auth_headers):
    """Quality endpoint requires resume_text field."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/analyze/quality", json={}, headers=auth_headers)
    assert resp.status_code == 422


# ---- Skill Gap ----

@pytest.mark.asyncio
async def test_skill_gap(app, auth_headers, sample_resume_text, sample_jd_text, mock_gap_output):
    """POST /api/v1/analyze/gap returns gap analysis."""
    with (
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_gap_output),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/gap",
                json={"resume_text": sample_resume_text, "jd_text": sample_jd_text},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "match_score" in data
    assert data["match_score"] == 65


# ---- Auto Screening ----

@pytest.mark.asyncio
async def test_screening_selected(app, auth_headers, sample_resume_text, sample_jd_text, mock_screen_output):
    """POST /api/v1/analyze/screen returns SELECTED decision."""
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_screen_output),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/screen",
                json={
                    "resume_text": sample_resume_text,
                    "jd_text": sample_jd_text,
                    "threshold": 75,
                },
                headers=auth_headers,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"]["selected"] is True
    assert data["score"]["overall"] == 80


@pytest.mark.asyncio
async def test_screening_rejected(app, auth_headers, sample_resume_text, sample_jd_text):
    """Screening with low score returns REJECTED."""
    rejected_output = {
        "score": {"overall": 40},
        "decision": {"selected": False, "reason": "Does not meet minimum requirements."},
    }
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=rejected_output),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/screen",
                json={
                    "resume_text": sample_resume_text,
                    "jd_text": sample_jd_text,
                    "threshold": 75,
                },
                headers=auth_headers,
            )
    assert resp.status_code == 200
    assert resp.json()["decision"]["selected"] is False


@pytest.mark.asyncio
async def test_screening_custom_threshold(app, auth_headers, sample_resume_text, sample_jd_text, mock_screen_output):
    """Screening passes threshold to pipeline."""
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_screen_output) as mock_pipe,
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/screen",
                json={
                    "resume_text": sample_resume_text,
                    "jd_text": sample_jd_text,
                    "threshold": 90,
                },
                headers=auth_headers,
            )
    assert resp.status_code == 200
    # Verify threshold was forwarded
    call_kwargs = mock_pipe.call_args
    assert call_kwargs.kwargs.get("threshold") == 90 or call_kwargs[1].get("threshold") == 90


# ---- Quality Scoring: Validation Pre-check ----

@pytest.mark.asyncio
async def test_quality_blocked_not_resume(app, auth_headers, mock_not_resume_validation):
    """Quality scoring returns 422 when input is not a resume."""
    with patch(
        "app.routes.v1.analyze.precheck_resume_validation",
        side_effect=HTTPException(
            status_code=422,
            detail={"error": "not_a_resume", "message": "Not a resume", "validation": mock_not_resume_validation},
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/quality",
                json={"resume_text": "Buy milk, eggs, bread"},
                headers=auth_headers,
            )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "not_a_resume"
    assert resp.json()["detail"]["validation"]["classification"] == "not_resume"


@pytest.mark.asyncio
async def test_quality_warning_weak_resume(app, auth_headers, sample_resume_text, mock_quality_output, mock_weak_resume_validation):
    """Quality scoring proceeds with warning for weak resumes."""
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=mock_weak_resume_validation),
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_quality_output),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/quality",
                json={"resume_text": sample_resume_text},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "validation_warning" in data
    assert data["validation_warning"]["classification"] == "resume_valid_but_weak"


@pytest.mark.asyncio
async def test_quality_no_warning_good_resume(app, auth_headers, sample_resume_text, mock_quality_output):
    """Quality scoring has no validation_warning for good resumes."""
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_quality_output),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/quality",
                json={"resume_text": sample_resume_text},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    assert "validation_warning" not in resp.json()


# ---- Auto Screening: Validation Pre-check ----

@pytest.mark.asyncio
async def test_screening_blocked_not_resume(app, auth_headers, mock_not_resume_validation):
    """Screening returns 422 when input is not a resume."""
    with patch(
        "app.routes.v1.analyze.precheck_resume_validation",
        side_effect=HTTPException(
            status_code=422,
            detail={"error": "not_a_resume", "message": "Not a resume", "validation": mock_not_resume_validation},
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/screen",
                json={"resume_text": "Shopping list: apples, oranges", "jd_text": "Software Engineer role"},
                headers=auth_headers,
            )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "not_a_resume"


@pytest.mark.asyncio
async def test_screening_warning_weak_resume(app, auth_headers, sample_resume_text, sample_jd_text, mock_screen_output, mock_weak_resume_validation):
    """Screening proceeds with warning for weak resumes."""
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=mock_weak_resume_validation),
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_screen_output),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/screen",
                json={"resume_text": sample_resume_text, "jd_text": sample_jd_text, "threshold": 75},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "decision" in data
    assert "validation_warning" in data
    assert data["validation_warning"]["classification"] == "resume_valid_but_weak"


@pytest.mark.asyncio
async def test_screening_no_warning_good_resume(app, auth_headers, sample_resume_text, sample_jd_text, mock_screen_output):
    """Screening has no validation_warning for good resumes."""
    with (
        patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None),
        patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_screen_output),
        patch("app.routes.v1.analyze.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analyze/screen",
                json={"resume_text": sample_resume_text, "jd_text": sample_jd_text, "threshold": 75},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    assert "validation_warning" not in resp.json()
