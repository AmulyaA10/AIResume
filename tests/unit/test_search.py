"""Unit tests for the semantic search endpoint."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_search_returns_results(app, auth_headers, mock_search_results):
    """POST /api/v1/search with valid query returns ranked results."""
    fake_llm_response = '{"results": [{"filename": "resume_a.pdf", "score": 90, "justification": "Strong Python match", "missing_skills": [], "auto_screen": "SELECTED"}]}'

    mock_chain = MagicMock()
    mock_chain.invoke.return_value = fake_llm_response

    mock_llm = MagicMock()
    mock_prompt = MagicMock()
    # Make the chain composable: prompt | llm | parser => mock_chain
    mock_prompt.__or__ = MagicMock(return_value=mock_chain)

    with (
        patch("app.routes.v1.search.search_resumes_hybrid", return_value=mock_search_results),
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        patch("langchain_core.prompts.PromptTemplate", return_value=mock_prompt),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search",
                json={"query": "Python developer with FastAPI experience"},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data


@pytest.mark.asyncio
async def test_search_empty_results(app, auth_headers):
    """Search with no matching resumes returns empty list."""
    empty_df = pd.DataFrame(columns=["filename", "text", "user_id"])

    with patch("app.routes.v1.search.search_resumes_hybrid", return_value=empty_df):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search",
                json={"query": "underwater basket weaving"},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_search_missing_query(app, auth_headers):
    """Search with missing query returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/search", json={}, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_manager_gets_global_results(app, manager_auth_headers, mock_search_results):
    """Manager token should search across all users (is_recruiter=True)."""
    fake_llm_response = '{"results": [{"filename": "resume_a.pdf", "score": 85, "justification": "Good match", "missing_skills": [], "auto_screen": "SELECTED"}]}'
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = fake_llm_response
    mock_llm = MagicMock()
    mock_prompt = MagicMock()
    mock_prompt.__or__ = MagicMock(return_value=mock_chain)

    with (
        patch("app.routes.v1.search.search_resumes_hybrid", return_value=mock_search_results) as mock_fn,
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        patch("langchain_core.prompts.PromptTemplate", return_value=mock_prompt),
        patch("app.routes.v1.search.resolve_credentials", return_value={"openrouter_key": "fake-test-key", "llm_model": None}),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search",
                json={"query": "Python developer"},
                headers=manager_auth_headers,
            )
    assert resp.status_code == 200
    # Verify search was called with is_recruiter=True for manager
    call_kwargs = mock_fn.call_args
    assert call_kwargs.kwargs.get("is_recruiter") is True or (
        len(call_kwargs.args) >= 5 and call_kwargs.args[4] is True
    )
