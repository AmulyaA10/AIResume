"""Unit tests for resume database filtering (industry/role/exp_level + recruiter scope)."""

import json
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from app.routes.v1 import resumes as resumes_route


def _meta_df_for(files: list[str], user_id: str = "user_alex_chen_123") -> pd.DataFrame:
    rows = []
    for i, fn in enumerate(files):
        rows.append(
            {
                "id": f"m{i}",
                "user_id": user_id,
                "filename": fn,
                "validation_json": json.dumps({"classification": "resume_valid_good", "total_score": 20, "scores": {}}),
                "uploaded_at": f"2026-03-{10 + i:02d}T12:00:00",
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.asyncio
async def test_resume_database_recruiter_uses_global_listing(app, recruiter_auth_headers):
    """Recruiter path should use global listing and not crash on role handling."""
    mock_meta_table = MagicMock()
    mock_meta_table.to_pandas.return_value = _meta_df_for(["global_resume.pdf"], user_id="uid_candidate")

    with (
        patch("services.db.lancedb_client.list_all_resumes_with_users", return_value=[{"filename": "global_resume.pdf", "user_id": "uid_candidate"}]) as mock_all,
        patch("app.routes.v1.resumes.list_user_resumes", return_value=["my_only_resume.pdf"]) as mock_user,
        patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=mock_meta_table),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/resumes/database", headers=recruiter_auth_headers)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert payload["resumes"][0]["filename"] == "global_resume.pdf"
    # Fast path should be served from resume_meta (no chunk-table scan).
    mock_all.assert_not_called()
    mock_user.assert_not_called()


@pytest.mark.asyncio
async def test_resume_database_applies_industry_role_exp_level_filters(app, auth_headers):
    """industry/role/exp_level query params should narrow results using classifier metadata."""
    filenames = ["resume_a.pdf", "resume_b.pdf", "resume_c.pdf"]
    mock_meta_table = MagicMock()
    mock_meta_table.to_pandas.return_value = _meta_df_for(filenames)

    classifier_output = {
        "resume_a.pdf": {"industry": "Technology", "role": "Software Engineer", "exp_level": "Senior"},
        "resume_b.pdf": {"industry": "Finance", "role": "Analyst", "exp_level": "Mid Level"},
        "resume_c.pdf": {"industry": "Technology", "role": "Data Scientist", "exp_level": "Entry Level"},
    }

    with (
        patch("app.routes.v1.resumes.list_user_resumes", return_value=filenames),
        patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=mock_meta_table),
        patch(
            "services.db.lancedb_client.get_resume_text_map",
            return_value={
                "resume_a.pdf": "Senior software engineer with Python and distributed systems.",
                "resume_b.pdf": "Financial analyst with forecasting and Excel expertise.",
                "resume_c.pdf": "Entry-level data scientist with ML projects.",
            },
        ),
        patch("app.routes.v1.resumes.resolve_credentials", new=AsyncMock(return_value={"openrouter_key": "k", "llm_model": "gpt-4o-mini"})),
        patch("app.routes.v1.resumes._llm_classify_batch", return_value=classifier_output) as mock_classify,
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
    mock_classify.assert_called_once()


@pytest.mark.asyncio
async def test_resume_locations_cached_between_calls(app, auth_headers):
    """Second /resumes/locations call should use server cache (no repeated LLM extraction)."""
    resumes_route._reset_resume_locations_cache_state_for_tests()

    mock_df = pd.DataFrame(
        [{"filename": "resume_a.pdf", "text": "Based in San Francisco, CA", "user_id": "user_alex_chen_123"}]
    )
    mock_table = MagicMock()
    mock_table.to_pandas.return_value = mock_df

    with (
        patch("services.db.lancedb_client.get_or_create_table", return_value=mock_table),
        patch("app.routes.v1.resumes.resolve_credentials", new=AsyncMock(return_value={"openrouter_key": "k", "llm_model": "gpt-4o-mini"})),
        patch("app.routes.v1.resumes._llm_extract_locations_batch", return_value={"resume_a.pdf": ["San Francisco, CA"]}) as mock_extract,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.get("/api/v1/resumes/locations", headers=auth_headers)
            second = await client.get("/api/v1/resumes/locations", headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["total"] == 1
    mock_extract.assert_called_once()
    mock_table.to_pandas.assert_called_once()


@pytest.mark.asyncio
async def test_resume_locations_force_refresh_bypasses_cache(app, auth_headers):
    """force_refresh=true should bypass cache and recompute locations."""
    resumes_route._reset_resume_locations_cache_state_for_tests()

    mock_df = pd.DataFrame(
        [{"filename": "resume_a.pdf", "text": "Based in San Francisco, CA", "user_id": "user_alex_chen_123"}]
    )
    mock_table = MagicMock()
    mock_table.to_pandas.return_value = mock_df

    with (
        patch("services.db.lancedb_client.get_or_create_table", return_value=mock_table),
        patch("app.routes.v1.resumes.resolve_credentials", new=AsyncMock(return_value={"openrouter_key": "k", "llm_model": "gpt-4o-mini"})),
        patch("app.routes.v1.resumes._llm_extract_locations_batch", return_value={"resume_a.pdf": ["San Francisco, CA"]}) as mock_extract,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.get("/api/v1/resumes/locations", headers=auth_headers)
            refreshed = await client.get(
                "/api/v1/resumes/locations",
                headers=auth_headers,
                params={"force_refresh": "true"},
            )

    assert first.status_code == 200
    assert refreshed.status_code == 200
    assert mock_extract.call_count == 2
