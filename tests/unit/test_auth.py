"""Unit tests for authentication endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_login_valid_credentials(app):
    """POST /api/v1/auth/login with correct creds returns token."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "recruit", "password": "admin123"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "token" in data
    assert "user" in data
    assert data["user"]["id"] == "user_recruiter_456"


@pytest.mark.asyncio
async def test_login_invalid_credentials(app):
    """POST /api/v1/auth/login with bad creds returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "wrong", "password": "wrong"},
        )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_missing_fields(app):
    """POST /api/v1/auth/login with missing fields returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_google_auth_redirects(app):
    """GET /api/v1/auth/google should redirect to Google OAuth."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        resp = await client.get("/api/v1/auth/google")
    assert resp.status_code in (302, 307)
    assert "accounts.google.com" in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_google_callback_redirects_to_frontend(app):
    """GET /api/v1/auth/google/callback redirects to frontend with token."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        resp = await client.get("/api/v1/auth/google/callback", params={"code": "test_code"})
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    assert "/auth/callback" in location
    assert "token=" in location


@pytest.mark.asyncio
async def test_linkedin_auth_redirects(app):
    """GET /api/v1/auth/linkedin should redirect to LinkedIn OAuth."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        resp = await client.get("/api/v1/auth/linkedin")
    assert resp.status_code in (302, 307)
    assert "linkedin.com" in resp.headers.get("location", "")
