"""Unit tests for the dashboard endpoint."""

import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_dashboard_stats_authenticated(app, auth_headers, mock_dashboard_stats):
    """GET /api/v1/dashboard/stats with valid auth returns stats."""
    with patch("app.routes.v1.dashboard.get_dashboard_stats", return_value=mock_dashboard_stats):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_resumes" in data
    assert "auto_screened" in data
    assert "total_applied" in data
    assert "recent_activity" in data
    assert data["total_resumes"] == 5


@pytest.mark.asyncio
async def test_dashboard_stats_recruiter_user(app, recruiter_auth_headers, mock_dashboard_stats):
    """Recruiter token should resolve to recruiter user_id."""
    with patch("app.routes.v1.dashboard.get_dashboard_stats", return_value=mock_dashboard_stats) as mock_fn:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/stats", headers=recruiter_auth_headers)
    assert resp.status_code == 200
    # Verify the function was called with recruiter user_id
    mock_fn.assert_called_once_with("user_recruiter_456")


@pytest.mark.asyncio
async def test_dashboard_stats_empty(app, auth_headers):
    """Dashboard returns zero stats when no data exists."""
    empty_stats = {
        "total_resumes": 0,
        "auto_screened": 0,
        "high_matches": 0,
        "skill_gaps": 0,
        "quality_scored": 0,
        "total_applied": 0,
        "recent_activity": [],
    }
    with patch("app.routes.v1.dashboard.get_dashboard_stats", return_value=empty_stats):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_resumes"] == 0
    assert resp.json()["recent_activity"] == []
