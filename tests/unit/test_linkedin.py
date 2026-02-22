"""Unit tests for the LinkedIn scrape endpoint."""

import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_linkedin_scrape(app, mock_linkedin_output):
    """POST /api/v1/linkedin/scrape returns structured resume."""
    with patch(
        "app.routes.v1.linkedin.generate_resume_from_linkedin",
        return_value=mock_linkedin_output,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/linkedin/scrape",
                json={"query": "https://www.linkedin.com/in/janedoe"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "resume" in data
    assert data["resume"]["contact"]["name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_linkedin_scrape_missing_query(app):
    """LinkedIn scrape requires query field."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/linkedin/scrape", json={})
    assert resp.status_code == 422
