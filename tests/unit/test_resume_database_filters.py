"""Unit tests for resume database filtering (industry/role/exp_level + recruiter scope)."""

import json
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


_CLASSIFIER_DEFAULTS = {
    "resume_a.pdf": {"industry": "Technology", "role": "Software Engineer", "exp_level": "Senior"},
    "resume_b.pdf": {"industry": "Finance", "role": "Analyst", "exp_level": "Mid-level"},
    "resume_c.pdf": {"industry": "Technology", "role": "Data Scientist", "exp_level": "Entry"},
}


def _meta_df_for(files: list[str], user_id: str = "user_alex_chen_123") -> pd.DataFrame:
    rows = []
    for i, fn in enumerate(files):
        meta = _CLASSIFIER_DEFAULTS.get(fn, {})
        rows.append(
            {
                "id": f"m{i}",
                "user_id": user_id,
                "filename": fn,
                "validation_json": json.dumps({"classification": "resume_valid_good", "total_score": 20, "scores": {}}),
                "uploaded_at": f"2026-03-{10 + i:02d}T12:00:00",
                "industry": meta.get("industry"),
                "role": meta.get("role"),
                "exp_level": meta.get("exp_level"),
                "location": None,
                "candidate_name": None,
                "current_company": None,
                "phone": None,
                "email": None,
                "linkedin_url": None,
                "github_url": None,
                "skills_json": None,
                "summary": None,
                "years_experience": None,
                "education": None,
                "certifications_json": None,
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.asyncio
async def test_resume_database_recruiter_uses_global_listing(app, recruiter_auth_headers):
    """Recruiter path should use global listing and not crash on role handling."""
    mock_meta_table = MagicMock()
    mock_meta_table.to_pandas.return_value = _meta_df_for(["global_resume.pdf"], user_id="uid_candidate")

    with (
        patch("services.db.lancedb_client.list_all_resumes_with_users", return_value=[{"filename": "global_resume.pdf", "user_id": "uid_candidate"}]),
        patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=mock_meta_table),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/resumes/database", headers=recruiter_auth_headers)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert payload["resumes"][0]["filename"] == "global_resume.pdf"


@pytest.mark.asyncio
async def test_resume_database_applies_industry_role_exp_level_filters(app, auth_headers):
    """industry/role/exp_level query params should narrow results using stored metadata."""
    filenames = ["resume_a.pdf", "resume_b.pdf", "resume_c.pdf"]
    mock_meta_table = MagicMock()
    mock_meta_table.to_pandas.return_value = _meta_df_for(filenames)

    with (
        patch("app.routes.v1.resumes.list_user_resumes", return_value=filenames),
        patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=mock_meta_table),
        patch("services.db.lancedb_client.get_or_create_table",
              side_effect=RuntimeError("test: chunks table not available")),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=auth_headers,
                params={
                    "industry": "technology",  # case-insensitive
                    "role": "software engineer",
                    "exp_level": "senior",
                },
            )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert len(payload["resumes"]) == 1
    assert payload["resumes"][0]["filename"] == "resume_a.pdf"
    assert payload["resumes"][0]["industry"] == "Technology"
    assert payload["resumes"][0]["role"] == "Software Engineer"
    assert payload["resumes"][0]["exp_level"] == "Senior"


@pytest.mark.asyncio
async def test_resume_locations_returns_from_meta(app, auth_headers):
    """GET /resumes/locations reads location column from resume_meta table."""
    mock_df = pd.DataFrame([
        {"filename": "resume_a.pdf", "user_id": "user_alex_chen_123", "location": "San Francisco, CA"},
        {"filename": "resume_b.pdf", "user_id": "user_alex_chen_123", "location": "London, UK"},
    ])
    mock_table = MagicMock()
    mock_table.to_pandas.return_value = mock_df

    with patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=mock_table):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/resumes/locations", headers=auth_headers)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 2
    mock_table.to_pandas.assert_called_once()


@pytest.mark.asyncio
async def test_resume_locations_filters_by_user(app, auth_headers):
    """Non-recruiter sees only their own locations."""
    mock_df = pd.DataFrame([
        {"filename": "resume_a.pdf", "user_id": "user_alex_chen_123", "location": "San Francisco, CA"},
        {"filename": "resume_b.pdf", "user_id": "other_user", "location": "Berlin, Germany"},
    ])
    mock_table = MagicMock()
    mock_table.to_pandas.return_value = mock_df

    with patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=mock_table):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/resumes/locations", headers=auth_headers)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1  # only user_alex_chen_123's resume
