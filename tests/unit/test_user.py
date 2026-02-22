"""Unit tests for the user profile endpoint."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_user_profile_found(app, auth_headers):
    """GET /api/v1/user/profile returns synced LinkedIn profile."""
    import json

    profile_json = json.dumps({
        "contact": {"name": "Alex Chen", "email": "alex@example.com"},
        "summary": "Experienced engineer with a strong background in full-stack development and cloud infrastructure.",
        "experience": [
            {"title": "Senior Engineer", "company": "Tech Co", "period": "2020-Present", "bullets": ["Led platform team"]}
        ],
    })

    mock_df = pd.DataFrame({
        "filename": ["LinkedIn_Profile.pdf"],
        "text": [profile_json],
        "user_id": ["user_alex_chen_123"],
    })

    mock_table = MagicMock()
    mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = mock_df

    with patch("app.routes.v1.user.get_or_create_table", return_value=mock_table):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/user/profile", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["resume"]["contact"]["name"] == "Alex Chen"


@pytest.mark.asyncio
async def test_user_profile_not_found(app, auth_headers):
    """GET /api/v1/user/profile returns found=false when no profile exists."""
    empty_df = pd.DataFrame(columns=["filename", "text", "user_id"])

    mock_table = MagicMock()
    mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = empty_df

    with patch("app.routes.v1.user.get_or_create_table", return_value=mock_table):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/user/profile", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["found"] is False
