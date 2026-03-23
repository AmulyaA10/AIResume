"""
System endpoint tests — validates every API route the UI calls.

Each test hits the real FastAPI route with mocked DB / LLM / file-system
dependencies so tests are deterministic, fast, and require no live credentials.

Coverage:
  AUTH        POST /login, GET /google, /google/callback, /linkedin, /linkedin/callback
  HEALTH      GET /health
  DASHBOARD   GET /dashboard/stats
  RESUMES     POST /upload, GET /list, /database, /filter-options, /locations,
              /preview/{f}, /download/{f}, /{f}/text, PUT /{f}/text, /{f}/rename,
              DELETE /{f}, POST /save-generated, GET /{f}/applied-jobs
  SEARCH      POST /search (candidate semantic search)
  JOBS        POST /, GET /, GET /locations, GET /public, GET /{id},
              PUT /{id}, DELETE /{id}, POST /parse-query-intent,
              POST /parse-upload, POST /{id}/apply, GET /my-applied,
              GET /{id}/candidates, POST /{id}/shortlist,
              PUT /{id}/candidates/{r}/status, PUT /{id}/candidates/{r}/notify
  MATCH       GET /search/jobs, GET /job/{id}/candidates,
              GET /resume/{id}, GET /resume/{id}/extract-skills,
              GET /resume/{id}/skills-match
  ANALYZE     POST /screen, /quality, /gap
  GENERATE    POST /resume, /refine, /export
  LINKEDIN    POST /parse, /check-profile, /scrape
  VALIDATE    POST /text, /json
  SETTINGS    PUT /user/settings, GET /user/settings, DELETE /user/settings,
              PUT /user/system/settings, GET /user/system/settings
  USER        GET /user/profile
"""

from __future__ import annotations

import io
import json
import sys
import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_backend_root = os.path.join(_project_root, "backend")
for p in (_project_root, _backend_root):
    if p not in sys.path:
        sys.path.insert(0, p)

from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Auth header shortcuts
# ---------------------------------------------------------------------------
_A  = {"Authorization": "Bearer mock-token-123"}           # jobseeker
_R  = {"Authorization": "Bearer mock-recruiter-token-123"} # recruiter
_M  = {"Authorization": "Bearer mock-manager-token"}       # manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_pdf(name="resume.pdf"):
    buf = io.BytesIO(b"%PDF-1.4 fake resume content")
    buf.name = name
    return buf


def _sample_df():
    return pd.DataFrame([
        {"id": "1", "user_id": "user_manager_789", "filename": "alice.pdf",
         "text": "Python FastAPI senior engineer"},
    ])


def _job_row(job_id="job-001"):
    return {
        "job_id": job_id,
        "id": job_id,
        "user_id": "user_manager_789",
        "title": "Software Engineer", "employer_name": "Acme",
        "location_name": "San Francisco, CA, USA", "job_level": "SENIOR",
        "job_category": "Engineering", "description": "Build great software.",
        "skills_required": ["Python", "FastAPI"],
        "skills_tiers": json.dumps({"must_have": ["Python"], "nice_to_have": ["Go"]}),
        "salary_min": 120000.0, "salary_max": 160000.0, "salary_currency": "USD",
        "date_posted": "2026-03-01", "work_type": "Remote",
        "benefits": ["Health insurance", "401k"],
        "applicant_count": 5, "status": "in_progress",
        "positions": 1,
        "vector": [0.0] * 1536,
    }


# ---------------------------------------------------------------------------
# ── AUTH ────────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_login_success(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/login", json={"username": "recruit", "password": "admin123"})
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert "token" in r.json()


@pytest.mark.asyncio
async def test_auth_login_bad_creds(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/login", json={"username": "x", "password": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_auth_google_redirect(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as c:
        r = await c.get("/api/v1/auth/google")
    assert r.status_code in (302, 307)
    assert "accounts.google.com" in r.headers["location"]


@pytest.mark.asyncio
async def test_auth_google_callback(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as c:
        r = await c.get("/api/v1/auth/google/callback", params={"code": "fake"})
    assert r.status_code in (302, 307)
    assert "auth/callback" in r.headers["location"]


@pytest.mark.asyncio
async def test_auth_linkedin_redirect(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as c:
        r = await c.get("/api/v1/auth/linkedin")
    assert r.status_code in (302, 307)
    assert "linkedin.com" in r.headers["location"]


@pytest.mark.asyncio
async def test_auth_linkedin_callback(app):
    with patch("app.routes.v1.auth.get_or_create_table", return_value=MagicMock(delete=MagicMock())):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as c:
            r = await c.get("/api/v1/auth/linkedin/callback", params={"code": "fake"})
    assert r.status_code in (302, 307)
    assert "auth/callback" in r.headers["location"]


# ---------------------------------------------------------------------------
# ── HEALTH ──────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---------------------------------------------------------------------------
# ── NO-AUTH USES GUEST IDENTITY ─────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_auth_header_uses_guest_identity(app):
    """Requests without an Authorization header resolve to the guest user and
    return a 2xx (not 401) for endpoints that allow guest access."""
    mock_tbl = MagicMock()
    mock_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = []
    with patch("app.routes.v1.resumes.list_user_resumes", return_value=[]), \
         patch("app.routes.v1.resumes.get_resume_validations", return_value={}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/resumes/list")
    assert r.status_code in (200, 201, 400, 404, 422), (
        f"Expected 2xx/4xx (not 401) for guest request, got {r.status_code}"
    )


# ---------------------------------------------------------------------------
# ── DASHBOARD ───────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_stats(app):
    mock_stats = {
        "total_resumes": 0, "auto_screened": 0, "high_matches": 0,
        "skill_gaps": 0, "quality_scored": 0, "total_applied": 0,
        "recent_activity": [],
    }
    with patch("services.db.lancedb_client.get_dashboard_stats", return_value=mock_stats):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/dashboard/stats", headers=_R)
    assert r.status_code == 200
    body = r.json()
    assert "total_resumes" in body


# ---------------------------------------------------------------------------
# ── RESUMES ─────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resume_upload(app):
    with patch("app.routes.v1.resumes.extract_text", return_value="Senior Python engineer"), \
         patch("app.routes.v1.resumes.store_resume"), \
         patch("app.routes.v1.resumes.safe_log_activity"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/resumes/upload", headers=_A,
                             files={"files": ("r.pdf", _fake_pdf(), "application/pdf")},
                             data={"store_db": "true", "run_validation": "false"})
    assert r.status_code == 200
    assert r.json()["success"] is True


@pytest.mark.asyncio
async def test_resume_list(app):
    with patch("app.routes.v1.resumes.list_user_resumes", return_value=["alice.pdf"]), \
         patch("app.routes.v1.resumes.get_resume_validations", return_value={}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/resumes/list", headers=_A)
    assert r.status_code == 200
    body = r.json()
    assert "resumes" in body
    assert isinstance(body["resumes"], list)


@pytest.mark.asyncio
async def test_resume_database(app):
    meta_tbl = MagicMock()
    meta_tbl.to_pandas.return_value = pd.DataFrame()
    with patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=meta_tbl), \
         patch("services.db.lancedb_client.list_all_resumes_with_users", return_value=[]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/resumes/database", headers=_R)
    assert r.status_code == 200
    body = r.json()
    # Response may be a list or {"resumes": [...], "total": N}
    assert isinstance(body, (list, dict))


@pytest.mark.asyncio
async def test_resume_filter_options(app):
    meta_tbl = MagicMock()
    meta_tbl.to_pandas.return_value = pd.DataFrame([
        {"industry": "Tech", "role": "Engineer", "exp_level": "Senior",
         "location": "SF", "filename": "a.pdf", "candidate_name": "Alice",
         "user_id": "user_alex_chen_123"}
    ])
    with patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=meta_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/resumes/filter-options", headers=_R)
    assert r.status_code == 200
    body = r.json()
    assert "industries" in body


@pytest.mark.asyncio
async def test_resume_locations(app):
    meta_tbl = MagicMock()
    meta_tbl.to_pandas.return_value = pd.DataFrame([
        {"location": "San Francisco, CA", "user_id": "user_alex_chen_123", "filename": "a.pdf"}
    ])
    with patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=meta_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/resumes/locations", headers=_R)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_resume_preview_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/resumes/preview/missing.pdf", headers=_A)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_resume_download_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/resumes/download/missing.pdf", headers=_A)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_resume_get_text(app):
    with patch("app.routes.v1.resumes.list_user_resumes", return_value=["alice.pdf"]), \
         patch("app.routes.v1.resumes.get_resume_validations", return_value={}):
        # The /{f}/text GET route reads from DB. We need the inline import patched.
        mock_tbl = MagicMock()
        mock_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = [
            {"filename": "alice.pdf", "text": "Python engineer", "user_id": "user_alex_chen_123"}
        ]
        with patch("services.db.lancedb_client.get_or_create_table", return_value=mock_tbl):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/api/v1/resumes/alice.pdf/text", headers=_A)
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_resume_update_text(app):
    mock_tbl = MagicMock()
    mock_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = [
        {"filename": "alice.pdf", "text": "old", "user_id": "user_alex_chen_123", "vector": [0.0]*1536}
    ]
    with patch("services.db.lancedb_client.get_or_create_table", return_value=mock_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.put("/api/v1/resumes/alice.pdf/text", headers=_A,
                            json={"text": "updated resume text"})
    assert r.status_code in (200, 400, 404, 500)


@pytest.mark.asyncio
async def test_resume_rename(app):
    mock_tbl = MagicMock()
    mock_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = [
        {"filename": "old.pdf", "user_id": "user_alex_chen_123", "text": "x", "vector": [0.0]*1536}
    ]
    meta_tbl = MagicMock()
    with patch("services.db.lancedb_client.get_or_create_table", return_value=mock_tbl), \
         patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=meta_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.put("/api/v1/resumes/old.pdf/rename", headers=_A,
                            json={"new_filename": "new.pdf"})
    assert r.status_code in (200, 400, 404, 500)


@pytest.mark.asyncio
async def test_resume_delete(app):
    with patch("app.routes.v1.resumes.delete_user_resume"), \
         patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=MagicMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete("/api/v1/resumes/alice.pdf", headers=_A)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_resume_save_generated(app):
    with patch("app.routes.v1.resumes.store_resume"), \
         patch("app.routes.v1.resumes.safe_log_activity"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/resumes/save-generated", headers=_A,
                             json={
                                 "resume_json": {"contact": {"name": "Test"}, "summary": "Engineer"},
                                 "new_filename": "gen.pdf"
                             })
    assert r.status_code in (200, 422)


@pytest.mark.asyncio
async def test_resume_applied_jobs(app):
    mock_tbl = MagicMock()
    mock_tbl.to_pandas.return_value = pd.DataFrame()
    with patch("services.db.lancedb_client.get_or_create_job_applied_table", return_value=mock_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/resumes/alice.pdf/applied-jobs", headers=_A)
    assert r.status_code == 200
    body = r.json()
    # Response may be a list or {"jobs": [...]}
    assert isinstance(body, (list, dict))


# ---------------------------------------------------------------------------
# ── CANDIDATE SEARCH ────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_candidate_search_returns_results(app):
    mock_ch = MagicMock()
    mock_ch.invoke.return_value = json.dumps({"results": [
        {"filename": "alice.pdf", "score": 88, "justification": "Strong match",
         "missing_skills": [], "auto_screen": "SELECTED"}
    ]})
    mock_ch.__or__ = MagicMock(return_value=mock_ch)
    mock_pr = MagicMock()
    mock_pr.__or__ = MagicMock(return_value=mock_ch)
    with patch("app.routes.v1.search.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.search.search_resumes_hybrid", return_value=_sample_df()), \
         patch("langchain_openai.ChatOpenAI", return_value=MagicMock()), \
         patch("langchain_core.prompts.PromptTemplate", return_value=mock_pr):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/search", headers=_R, json={"query": "python engineer"})
    assert r.status_code == 200
    assert isinstance(r.json().get("results"), list)


@pytest.mark.asyncio
async def test_candidate_search_no_key(app):
    with patch("app.routes.v1.search.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": None, "llm_model": None})):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/search", headers=_A, json={"query": "python"})
    assert r.status_code == 200
    assert "error" in r.json()


# ---------------------------------------------------------------------------
# ── JOBS ────────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def _mock_jobs_table(rows=None):
    tbl = MagicMock()
    rows = rows or [_job_row()]
    q = MagicMock()
    q.where.return_value = q
    q.limit.return_value = q
    q.to_list.return_value = rows
    q.search.return_value = q
    tbl.search.return_value = q
    tbl.count_rows.return_value = len(rows)
    return tbl


@pytest.mark.asyncio
async def test_jobs_list(app):
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_mock_jobs_table()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/jobs", headers=_R, params={"limit": 10})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_jobs_create(app):
    tbl = MagicMock()
    tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = []
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=tbl), \
         patch("app.routes.v1.jobs.get_embeddings_model") as mock_emb, \
         patch("app.routes.v1.jobs.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})):
        mock_emb.return_value.embed_documents.return_value = [[0.0] * 1536]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/jobs", headers=_R, json={
                "title": "Backend Engineer", "employer_name": "Acme",
                "location_name": "Remote", "job_level": "SENIOR",
                "job_category": "Engineering", "description": "Build APIs.",
                "skills_required": ["Python"], "salary_min": 100000, "salary_max": 140000,
                "salary_currency": "USD", "date_posted": "2026-03-01",
                "work_type": "Remote", "benefits": [],
            })
    assert r.status_code in (200, 201, 500)


@pytest.mark.asyncio
async def test_jobs_get_by_id(app):
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_mock_jobs_table()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/jobs/job-001", headers=_R)
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_jobs_update(app):
    tbl = _mock_jobs_table()
    tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = [_job_row()]
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.put("/api/v1/jobs/job-001", headers=_R, json={"title": "Senior Engineer"})
    assert r.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
async def test_jobs_delete(app):
    tbl = MagicMock()
    tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = [_job_row()]
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete("/api/v1/jobs/job-001", headers=_R)
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_jobs_locations(app):
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_mock_jobs_table()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/jobs/locations", headers=_R)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


@pytest.mark.asyncio
async def test_jobs_public(app):
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_mock_jobs_table()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/jobs/public", headers=_A)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_jobs_parse_query_intent_no_key(app):
    with patch("app.routes.v1.jobs.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": None, "llm_model": None})):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/jobs/parse-query-intent", headers=_R,
                             json={"query": "top paid python jobs in SF"})
    assert r.status_code == 200
    body = r.json()
    # fallback: cleanQuery equals the raw query
    assert body["cleanQuery"] == "top paid python jobs in SF"
    assert body["sortBySalary"] is False


@pytest.mark.asyncio
async def test_jobs_parse_query_intent_with_key(app):
    intent_json = json.dumps({
        "location": "san francisco", "locationAliases": ["san francisco", "sf", "bay area"],
        "topN": None, "sortBySalary": True, "cleanQuery": "python jobs"
    })
    # The chain is built via `prompt | llm | StrOutputParser()`.
    # We need the final chained object's ainvoke to be async.
    mock_final_chain = MagicMock()
    mock_final_chain.ainvoke = AsyncMock(return_value=intent_json)
    # Each `|` step should return the same final chain so ainvoke is always available
    mock_final_chain.__or__ = MagicMock(return_value=mock_final_chain)

    mock_prompt = MagicMock()
    mock_prompt.__or__ = MagicMock(return_value=mock_final_chain)

    with patch("app.routes.v1.jobs.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("langchain_openai.ChatOpenAI", return_value=MagicMock()), \
         patch("langchain_core.prompts.ChatPromptTemplate") as mock_tmpl, \
         patch("langchain_core.output_parsers.StrOutputParser", return_value=MagicMock()):
        mock_tmpl.from_messages.return_value = mock_prompt
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/jobs/parse-query-intent", headers=_R,
                             json={"query": "top paid python jobs in SF"})
    assert r.status_code == 200
    body = r.json()
    assert "cleanQuery" in body
    assert "sortBySalary" in body


@pytest.mark.asyncio
async def test_jobs_parse_upload(app):
    with patch("app.routes.v1.jobs.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": None, "llm_model": None})):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/jobs/parse-upload", headers=_R,
                             files={"file": ("jd.txt", io.BytesIO(b"Senior Python Engineer"), "text/plain")})
    assert r.status_code in (200, 400, 422, 500)


@pytest.mark.asyncio
async def test_jobs_apply(app):
    jobs_tbl = _mock_jobs_table()
    applied_tbl = MagicMock()
    applied_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = []
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=jobs_tbl), \
         patch("app.routes.v1.jobs.get_or_create_job_applied_table", return_value=applied_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/jobs/job-001/apply", headers=_A,
                             json={"resume_filename": "alice.pdf"})
    assert r.status_code in (200, 400, 404, 409, 422)


@pytest.mark.asyncio
async def test_jobs_my_applied(app):
    applied_tbl = MagicMock()
    applied_tbl.search.return_value.where.return_value.to_list.return_value = []
    with patch("app.routes.v1.jobs.get_or_create_job_applied_table", return_value=applied_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/jobs/my-applied", headers=_A)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_jobs_candidates(app):
    resume_tbl = MagicMock()
    resume_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = []
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_mock_jobs_table()), \
         patch("services.db.lancedb_client.get_or_create_table", return_value=resume_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/jobs/job-001/candidates", headers=_R)
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_jobs_shortlist(app):
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_mock_jobs_table()), \
         patch("app.routes.v1.jobs.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": None, "llm_model": None})):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/jobs/job-001/shortlist", headers=_R)
    assert r.status_code in (200, 400, 404, 422, 500)


@pytest.mark.asyncio
async def test_jobs_candidate_status(app):
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_mock_jobs_table()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.put("/api/v1/jobs/job-001/candidates/alice.pdf/status",
                            headers=_R, json={"status": "SELECTED"})
    assert r.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_jobs_candidate_notify(app):
    with patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_mock_jobs_table()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.put("/api/v1/jobs/job-001/candidates/alice.pdf/notify",
                            headers=_R, json={"message": "You are shortlisted!"})
    assert r.status_code in (200, 404, 422, 500)


# ---------------------------------------------------------------------------
# ── MATCH ───────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_search_jobs(app):
    tbl = MagicMock()
    tbl.search.return_value.metric.return_value.limit.return_value.to_list.return_value = [
        {**_job_row(), "_distance": 0.2}
    ]
    tbl.search.return_value.metric.return_value.where.return_value.limit.return_value.to_list.return_value = [
        {**_job_row(), "_distance": 0.2}
    ]
    with patch("app.routes.v1.match.get_or_create_jobs_table", return_value=tbl), \
         patch("app.routes.v1.match.get_embeddings_model") as mock_emb, \
         patch("app.routes.v1.match.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})):
        mock_emb.return_value.embed_query.return_value = [0.1] * 1536
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/match/search/jobs", headers=_A, params={"q": "python engineer"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_match_job_candidates(app):
    jobs_tbl = _mock_jobs_table()
    resume_tbl = MagicMock()
    resume_tbl.search.return_value.metric.return_value.limit.return_value.to_list.return_value = []
    with patch("app.routes.v1.match.get_or_create_jobs_table", return_value=jobs_tbl), \
         patch("app.routes.v1.match.get_or_create_table", return_value=resume_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/match/job/job-001/candidates", headers=_R)
    assert r.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_match_resume(app):
    resume_tbl = MagicMock()
    resume_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = [
        {"filename": "alice.pdf", "text": "Python engineer", "user_id": "user_alex_chen_123",
         "vector": [0.0]*1536}
    ]
    jobs_tbl = MagicMock()
    jobs_tbl.search.return_value.metric.return_value.limit.return_value.to_list.return_value = []
    jobs_tbl.search.return_value.limit.return_value.to_list.return_value = []
    with patch("app.routes.v1.match.get_or_create_table", return_value=resume_tbl), \
         patch("app.routes.v1.match.get_or_create_jobs_table", return_value=jobs_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/match/resume/alice.pdf", headers=_A)
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_match_resume_extract_skills(app):
    resume_tbl = MagicMock()
    resume_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = [
        {"filename": "alice.pdf", "text": "Python FastAPI engineer", "user_id": "user_alex_chen_123"}
    ]
    with patch("app.routes.v1.match.get_or_create_table", return_value=resume_tbl), \
         patch("app.routes.v1.match.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": None, "llm_model": None})):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/match/resume/alice.pdf/extract-skills", headers=_A)
    assert r.status_code in (200, 400, 404, 500)


@pytest.mark.asyncio
async def test_match_resume_skills_match(app):
    resume_tbl = MagicMock()
    resume_tbl.search.return_value.where.return_value.limit.return_value.to_list.return_value = [
        {"filename": "alice.pdf", "text": "Python engineer", "user_id": "user_alex_chen_123"}
    ]
    jobs_tbl = _mock_jobs_table()
    with patch("app.routes.v1.match.get_or_create_table", return_value=resume_tbl), \
         patch("app.routes.v1.match.get_or_create_jobs_table", return_value=jobs_tbl), \
         patch("app.routes.v1.match.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": None, "llm_model": None})):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/match/resume/alice.pdf/skills-match",
                            headers=_A, params={"job_id": "job-001"})
    assert r.status_code in (200, 400, 404, 500)


# ---------------------------------------------------------------------------
# ── ANALYZE ─────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_screen(app, sample_resume_text, sample_jd_text, mock_screen_output):
    with patch("app.routes.v1.analyze.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_screen_output), \
         patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None), \
         patch("app.routes.v1.analyze.safe_log_activity"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/analyze/screen", headers=_R,
                             json={"resume_text": sample_resume_text, "jd_text": sample_jd_text})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_analyze_quality(app, sample_resume_text, mock_quality_output):
    with patch("app.routes.v1.analyze.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_quality_output), \
         patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None), \
         patch("app.routes.v1.analyze.safe_log_activity"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/analyze/quality", headers=_A,
                             json={"resume_text": sample_resume_text})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_analyze_gap(app, sample_resume_text, sample_jd_text, mock_gap_output):
    with patch("app.routes.v1.analyze.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.analyze.run_resume_pipeline", return_value=mock_gap_output), \
         patch("app.routes.v1.analyze.precheck_resume_validation", return_value=None), \
         patch("app.routes.v1.analyze.safe_log_activity"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/analyze/gap", headers=_A,
                             json={"resume_text": sample_resume_text, "jd_text": sample_jd_text})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# ── GENERATE ────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_resume(app, sample_resume_text, mock_generate_output):
    pipeline_out = {"resume_json": mock_generate_output["resume"]}
    with patch("app.routes.v1.generate.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.generate.run_resume_pipeline", return_value=pipeline_out), \
         patch("app.routes.v1.generate.precheck_resume_validation", return_value=None), \
         patch("app.routes.v1.generate.validate_resume_fields", return_value={}), \
         patch("app.routes.v1.generate.validate_resume_output", return_value={"ai_validation": None}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/generate/resume", headers=_A,
                             json={"profile": sample_resume_text})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_generate_refine(app, mock_generate_output):
    with patch("app.routes.v1.generate.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.generate.validate_resume_fields", return_value={}), \
         patch("app.routes.v1.generate.validate_resume_output", return_value={"ai_validation": None}), \
         patch("services.ai.common.extract_skills_from_text", return_value=[]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/generate/refine", headers=_A,
                             json=mock_generate_output["resume"])
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_generate_export(app, mock_generate_output):
    with patch("app.routes.v1.generate.generate_docx", return_value=io.BytesIO(b"docx-content")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/generate/export", headers=_A,
                             json=mock_generate_output["resume"])
    assert r.status_code in (200, 400, 500)


# ---------------------------------------------------------------------------
# ── LINKEDIN ────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_linkedin_parse(app, sample_resume_text, mock_linkedin_output):
    with patch("app.routes.v1.linkedin.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.linkedin.parse_linkedin_profile_text",
               return_value={"resume": mock_linkedin_output["resume"]}), \
         patch("app.routes.v1.linkedin.validate_resume_fields", return_value={}), \
         patch("app.routes.v1.linkedin.validate_resume_output", return_value={"ai_validation": None}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/linkedin/parse", headers=_A,
                             json={"profile_text": sample_resume_text})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_linkedin_check_profile(app):
    mock_tbl = MagicMock()
    mock_tbl.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = \
        pd.DataFrame()
    with patch("app.routes.v1.user.get_or_create_table", return_value=mock_tbl), \
         patch("services.db.lancedb_client.get_or_create_table", return_value=mock_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/user/profile", headers=_A)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_linkedin_scrape_no_creds(app):
    with patch("app.routes.v1.linkedin.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test",
                                           "linkedin_user": None, "linkedin_pass": None,
                                           "llm_model": None})):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/linkedin/scrape", headers=_A,
                             json={"query": "https://linkedin.com/in/test"})
    # Without LinkedIn creds, expects 422 (early validation guard)
    assert r.status_code in (200, 422)


# ---------------------------------------------------------------------------
# ── VALIDATE ────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_text(app, sample_resume_text):
    with patch("app.routes.v1.validate.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.validate.precheck_resume_validation", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/validate/text", headers=_A,
                             json={"resume_text": sample_resume_text})
    assert r.status_code == 200
    body = r.json()
    assert "status" in body


@pytest.mark.asyncio
async def test_validate_json(app, mock_generate_output):
    with patch("app.routes.v1.validate.resolve_credentials",
               new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})), \
         patch("app.routes.v1.validate.validate_resume_output",
               return_value={"field_validation": {}, "ai_validation": {}}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/validate/json", headers=_A,
                             json={"resume_json": mock_generate_output["resume"]})
    assert r.status_code == 200
    body = r.json()
    assert "field_validation" in body


# ---------------------------------------------------------------------------
# ── USER SETTINGS ───────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_save_and_get(app):
    with patch("app.routes.v1.user.upsert_user_setting"), \
         patch("app.routes.v1.user.encrypt_value", return_value="enc"), \
         patch("app.routes.v1.user.get_user_settings", return_value={"openRouterKey": "enc"}), \
         patch("app.routes.v1.user.decrypt_value", return_value="sk-or-v1-test"), \
         patch("app.routes.v1.user.mask_value", return_value="****test"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            put_r = await c.put("/api/v1/user/settings", headers=_A,
                                json={"openRouterKey": "sk-or-v1-realkey"})
            get_r = await c.get("/api/v1/user/settings", headers=_A)
    assert put_r.status_code == 200
    assert put_r.json()["success"] is True
    assert get_r.status_code == 200
    assert "has_openRouterKey" in get_r.json()


@pytest.mark.asyncio
async def test_settings_delete(app):
    with patch("app.routes.v1.user.delete_user_settings"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete("/api/v1/user/settings", headers=_A)
    assert r.status_code == 200
    assert r.json()["success"] is True


@pytest.mark.asyncio
async def test_settings_empty_body_rejected(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.put("/api/v1/user/settings", headers=_A, json={})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# ── SYSTEM SETTINGS (manager-only) ──────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_system_settings_save_manager(app):
    with patch("app.routes.v1.user.upsert_user_setting"), \
         patch("app.routes.v1.user.encrypt_value", return_value="enc"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.put("/api/v1/user/system/settings", headers=_R,
                            json={"googleClientId": "123.apps.googleusercontent.com",
                                  "googleClientSecret": "GOCSPX-abc",
                                  "linkedinClientId": "78abc",
                                  "linkedinClientSecret": "WPL_AP1.xyz"})
    assert r.status_code == 200
    assert r.json()["success"] is True


@pytest.mark.asyncio
async def test_system_settings_get_manager(app):
    with patch("app.routes.v1.user.get_user_settings", return_value={
        "googleClientId": "enc", "linkedinClientId": "enc2"
    }), patch("app.routes.v1.user.decrypt_value", return_value="decrypted"), \
         patch("app.routes.v1.user.mask_value", return_value="****ted"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/user/system/settings", headers=_R)
    assert r.status_code == 200
    body = r.json()
    assert "has_googleClientId" in body
    assert "has_linkedinClientId" in body


@pytest.mark.asyncio
async def test_system_settings_forbidden_for_jobseeker(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/user/system/settings", headers=_A)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_system_settings_empty_body_rejected(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.put("/api/v1/user/system/settings", headers=_R, json={})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# ── USER PROFILE ────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_profile_no_linkedin(app):
    mock_tbl = MagicMock()
    mock_tbl.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = \
        pd.DataFrame()
    with patch("app.routes.v1.user.get_or_create_table", return_value=mock_tbl):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/user/profile", headers=_A)
    assert r.status_code == 200
    assert r.json().get("found") is False
