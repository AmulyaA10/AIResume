"""
Validates the job search endpoint (/api/v1/jobs) with 100 query scenarios.

Covers:
  - Free-text search (keyword + vector path)
  - job_level, status, location, date_range, has_applicants filters
  - location_aliases soft geo matching
  - sort_by_salary
  - top_n cap
  - Combinations and edge cases

The LanceDB table and embeddings model are fully mocked so the tests run
without a running database or OpenAI key.
"""

from __future__ import annotations

import sys
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_backend_root = os.path.join(_project_root, "backend")
for p in (_project_root, _backend_root):
    if p not in sys.path:
        sys.path.insert(0, p)

from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Shared test data – 30 jobs with varied attributes
# ---------------------------------------------------------------------------

_NOW = datetime.now()


def _job(
    job_id: str,
    title: str,
    level: str,
    location: str,
    salary_min: int,
    salary_max: int,
    days_ago: int = 5,
    positions: int = 1,
    user_id: str = "user_recruiter_456",
) -> dict:
    return {
        "job_id": job_id,
        "user_id": user_id,
        "title": title,
        "description": f"Description for {title}",
        "employer_name": "Acme Corp",
        "employer_email": "hr@acme.com",
        "job_level": level,
        "job_category": "Engineering",
        "location_name": location,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": "USD",
        "skills_required": ["Python", "FastAPI"],
        "benefits": [],
        "positions": positions,
        "posted_date": (_NOW - timedelta(days=days_ago)).isoformat(),
        "vector": [0.0] * 1536,
    }


SAMPLE_JOBS = [
    # California jobs
    _job("j01", "Senior Python Engineer",        "SENIOR", "San Francisco, CA, USA",   140, 180, days_ago=2),
    _job("j02", "Mid Python Developer",           "MID",    "Los Angeles, CA, USA",     100, 130, days_ago=10),
    _job("j03", "Junior Python Dev",              "JUNIOR", "Sacramento, CA, USA",       70,  90, days_ago=60),
    _job("j04", "Staff Data Scientist",           "SENIOR", "Bay Area, CA, USA",        160, 200, days_ago=1),
    _job("j05", "Machine Learning Engineer",      "MID",    "Silicon Valley, CA, USA",  120, 160, days_ago=20),
    # New York jobs
    _job("j06", "Senior React Engineer",          "SENIOR", "New York, NY, USA",        145, 185, days_ago=3),
    _job("j07", "Mid Full-Stack Developer",       "MID",    "Manhattan, NY, USA",       105, 135, days_ago=15),
    _job("j08", "Junior Frontend Developer",      "JUNIOR", "Brooklyn, NY, USA",         65,  85, days_ago=45),
    # London jobs
    _job("j09", "Senior Java Engineer",           "SENIOR", "London, UK",               130, 170, days_ago=7),
    _job("j10", "Mid DevOps Engineer",            "MID",    "London, UK",                95, 125, days_ago=25),
    # India jobs
    _job("j11", "Senior Backend Engineer",        "SENIOR", "Bangalore, India",          40,  60, days_ago=5),
    _job("j12", "Mid Software Engineer",          "MID",    "Hyderabad, India",          30,  45, days_ago=35),
    _job("j13", "Junior QA Engineer",             "JUNIOR", "Pune, India",               20,  30, days_ago=55),
    # Remote
    _job("j14", "Senior Cloud Architect",         "SENIOR", "Remote",                   155, 195, days_ago=2),
    _job("j15", "Mid Data Engineer",              "MID",    "Remote",                   110, 145, days_ago=18),
    _job("j16", "Junior Data Analyst",            "JUNIOR", "Remote",                    60,  80, days_ago=40),
    # Canada
    _job("j17", "Senior iOS Developer",           "SENIOR", "Toronto, Canada",          120, 155, days_ago=6),
    _job("j18", "Mid Android Developer",          "MID",    "Vancouver, Canada",         90, 120, days_ago=28),
    # Austin TX
    _job("j19", "Senior Site Reliability Eng",   "SENIOR", "Austin, TX, USA",           135, 175, days_ago=4),
    _job("j20", "Mid Platform Engineer",          "MID",    "Austin, TX, USA",           100, 130, days_ago=22),
    # Seattle
    _job("j21", "Senior Software Engineer",       "SENIOR", "Seattle, WA, USA",         150, 190, days_ago=3),
    _job("j22", "Mid Software Engineer",          "MID",    "Seattle, WA, USA",         115, 145, days_ago=16),
    # Chicago
    _job("j23", "Senior Product Manager",         "SENIOR", "Chicago, IL, USA",         140, 175, days_ago=8),
    _job("j24", "Mid Product Manager",            "MID",    "Chicago, IL, USA",         100, 130, days_ago=30),
    # Singapore
    _job("j25", "Senior Blockchain Engineer",     "SENIOR", "Singapore",                125, 160, days_ago=5),
    # Edge cases
    _job("j26", "Senior Manager",                 "SENIOR", "",                         130, 160, days_ago=5),   # empty location
    _job("j27", "Principal Engineer",             "SENIOR", "San Jose, CA, USA",        170, 220, days_ago=1),   # highest salary
    _job("j28", "Staff Engineer",                 "SENIOR", "Menlo Park, CA, USA",      165, 210, days_ago=2),   # high salary CA
    _job("j29", "Junior Designer",                "JUNIOR", "New York, NY, USA",         55,  75, days_ago=5),
    _job("j30", "Mid Data Scientist",             "MID",    "San Francisco, CA, USA",   115, 150, days_ago=12),
]

# Applied records – used to simulate applied_count / shortlisted_count
APPLIED_RECORDS = [
    # j01 has 2 applicants (applied), 1 shortlisted → selected_count = 0
    {"id": "a1", "job_id": "j01", "resume_id": "r1", "user_id": "uid_user1", "applied_status": "applied",     "timestamp": _NOW.isoformat(), "notified": False, "notified_at": ""},
    {"id": "a2", "job_id": "j01", "resume_id": "r2", "user_id": "uid_user2", "applied_status": "applied",     "timestamp": _NOW.isoformat(), "notified": False, "notified_at": ""},
    {"id": "a3", "job_id": "j01", "resume_id": "r3", "user_id": "uid_user3", "applied_status": "shortlisted", "timestamp": _NOW.isoformat(), "notified": False, "notified_at": ""},
    # j04 is "completed" – selected_count == positions (1)
    {"id": "a4", "job_id": "j04", "resume_id": "r4", "user_id": "uid_user4", "applied_status": "selected",    "timestamp": _NOW.isoformat(), "notified": False, "notified_at": ""},
    # j06 has 1 applicant
    {"id": "a5", "job_id": "j06", "resume_id": "r5", "user_id": "uid_user5", "applied_status": "applied",     "timestamp": _NOW.isoformat(), "notified": False, "notified_at": ""},
]


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _make_mock_table(jobs: list[dict] | None = None):
    """Return a mock LanceDB table that yields SAMPLE_JOBS (or a subset)."""
    rows = jobs if jobs is not None else list(SAMPLE_JOBS)

    mock_q = MagicMock()
    mock_q.where.return_value = mock_q
    mock_q.limit.return_value = mock_q
    mock_q.to_list.return_value = rows

    mock_table = MagicMock()
    mock_table.search.return_value = mock_q
    return mock_table


def _make_applied_table():
    import pandas as pd
    mock_q = MagicMock()
    mock_q.where.return_value = mock_q
    mock_q.to_list.return_value = list(APPLIED_RECORDS)

    mock_table = MagicMock()
    mock_table.search.return_value = mock_q
    mock_table.to_pandas.return_value = pd.DataFrame(APPLIED_RECORDS)
    return mock_table


def _mock_embeddings():
    m = MagicMock()
    m.embed_query.return_value = [0.0] * 1536
    return m


def _patches():
    """Context managers that mock LanceDB + embeddings for the route layer."""
    return [
        patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_make_mock_table()),
        patch("app.routes.v1.jobs.get_or_create_job_applied_table", return_value=_make_applied_table()),
        patch("app.routes.v1.jobs.get_embeddings_model", return_value=_mock_embeddings()),
    ]


# ---------------------------------------------------------------------------
# Parametrized scenarios
# ---------------------------------------------------------------------------

# Each entry: (scenario_name, query_params, assertion_fn)
# assertion_fn receives (status_code, json_body)

def _has_status(code: int):
    def _check(status, body): assert status == code, f"expected {code}, got {status}: {body}"
    return _check


def _count_ge(n: int):
    def _check(status, body):
        assert status == 200
        assert len(body) >= n, f"expected >= {n} results, got {len(body)}: {[j['job_id'] for j in body]}"
    return _check


def _count_le(n: int):
    def _check(status, body):
        assert status == 200
        assert len(body) <= n, f"expected <= {n} results, got {len(body)}"
    return _check


def _count_eq(n: int):
    def _check(status, body):
        assert status == 200
        assert len(body) == n, f"expected exactly {n} results, got {len(body)}: {[j['job_id'] for j in body]}"
    return _check


def _all_match(field: str, value):
    def _check(status, body):
        assert status == 200
        for job in body:
            assert job.get(field) == value, f"job {job['job_id']} has {field}={job.get(field)!r}, expected {value!r}"
    return _check


def _all_location_contains(substring: str):
    def _check(status, body):
        assert status == 200
        assert len(body) > 0, f"expected some results for location substring '{substring}'"
        for job in body:
            loc = (job.get("location_name") or "").lower()
            assert substring.lower() in loc, f"job {job['job_id']} location '{loc}' does not contain '{substring}'"
    return _check


def _sorted_by_salary_desc():
    def _check(status, body):
        assert status == 200
        salaries = [max(j.get("salary_max") or 0, j.get("salary_min") or 0) for j in body]
        assert salaries == sorted(salaries, reverse=True), \
            f"results not sorted by salary desc: {list(zip([j['job_id'] for j in body], salaries))}"
    return _check


def _top_n_cap(n: int):
    def _check(status, body):
        assert status == 200
        assert len(body) <= n, f"top_n={n} but got {len(body)} results"
    return _check


def _ok_and_list():
    def _check(status, body):
        assert status == 200
        assert isinstance(body, list)
    return _check


# Build 100 scenarios
SCENARIOS: list[tuple[str, dict, any]] = [
    # ── Basic list ────────────────────────────────────────────────────────────
    ("list_default",                {"limit": 20},                               _count_ge(1)),
    ("list_limit_5",                {"limit": 5},                                _count_le(5)),
    ("list_limit_10",               {"limit": 10},                               _count_le(10)),
    ("list_limit_1",                {"limit": 1},                                _count_eq(1)),
    ("list_limit_30",               {"limit": 30},                               _count_le(30)),
    ("list_skip_0",                 {"limit": 5, "skip": 0},                     _count_le(5)),
    ("list_skip_5",                 {"limit": 5, "skip": 5},                     _ok_and_list()),
    ("list_skip_100",               {"limit": 5, "skip": 100},                   _ok_and_list()),  # empty ok
    ("list_large_limit",            {"limit": 200},                              _count_ge(1)),
    ("list_no_params",              {},                                           _ok_and_list()),

    # ── job_level filter ──────────────────────────────────────────────────────
    ("level_senior",                {"job_level": "SENIOR"},                     _ok_and_list()),
    ("level_mid",                   {"job_level": "MID"},                        _ok_and_list()),
    ("level_junior",                {"job_level": "JUNIOR"},                     _ok_and_list()),
    ("level_senior_limit_5",        {"job_level": "SENIOR", "limit": 5},        _count_le(5)),
    ("level_mid_limit_3",           {"job_level": "MID", "limit": 3},           _count_le(3)),
    ("level_invalid",               {"job_level": "EXECUTIVE"},                  _ok_and_list()),  # no results is fine

    # ── status filter ─────────────────────────────────────────────────────────
    ("status_in_progress",          {"status": "in_progress"},                   _ok_and_list()),
    ("status_completed",            {"status": "completed"},                     _ok_and_list()),
    ("status_invalid",              {"status": "unknown_status"},                _ok_and_list()),

    # ── location exact match (WHERE pushed to LanceDB; mock doesn't filter rows) ──
    ("location_sf",                 {"location": "San Francisco, CA, USA"},      _ok_and_list()),
    ("location_london",             {"location": "London, UK"},                  _ok_and_list()),
    ("location_remote",             {"location": "Remote"},                      _ok_and_list()),
    ("location_ny",                 {"location": "New York, NY, USA"},           _ok_and_list()),
    ("location_bangalore",          {"location": "Bangalore, India"},            _ok_and_list()),
    ("location_nonexistent",        {"location": "Atlantis, XZ"},                _ok_and_list()),  # 0 results ok

    # ── date_range filter ─────────────────────────────────────────────────────
    ("date_range_7d",               {"date_range": 7},                           _ok_and_list()),
    ("date_range_30d",              {"date_range": 30},                          _ok_and_list()),
    ("date_range_90d",              {"date_range": 90},                          _ok_and_list()),
    ("date_range_1d",               {"date_range": 1},                           _ok_and_list()),
    ("date_range_365d",             {"date_range": 365},                         _count_ge(1)),

    # ── has_applicants filter ─────────────────────────────────────────────────
    ("has_applicants_true",         {"has_applicants": True},                    _ok_and_list()),
    ("has_applicants_false",        {"has_applicants": False},                   _ok_and_list()),

    # ── free-text search ──────────────────────────────────────────────────────
    ("search_python",               {"search": "python developer"},              _ok_and_list()),
    ("search_react",                {"search": "react engineer"},                _ok_and_list()),
    ("search_data_scientist",       {"search": "data scientist"},                _ok_and_list()),
    ("search_devops",               {"search": "devops kubernetes"},             _ok_and_list()),
    ("search_ml_engineer",          {"search": "machine learning engineer"},     _ok_and_list()),
    ("search_frontend",             {"search": "frontend developer typescript"}, _ok_and_list()),
    ("search_backend",              {"search": "backend api microservices"},     _ok_and_list()),
    ("search_fullstack",            {"search": "full stack javascript node"},    _ok_and_list()),
    ("search_manager",              {"search": "engineering manager"},           _ok_and_list()),
    ("search_product_manager",      {"search": "product manager agile"},        _ok_and_list()),
    ("search_cloud_arch",           {"search": "cloud architect aws"},           _ok_and_list()),
    ("search_mobile",               {"search": "mobile ios android"},            _ok_and_list()),
    ("search_qa",                   {"search": "quality assurance testing"},     _ok_and_list()),
    ("search_sre",                  {"search": "site reliability engineer"},     _ok_and_list()),
    ("search_blockchain",           {"search": "blockchain web3 smart contract"},_ok_and_list()),
    ("search_empty",                {"search": ""},                              _ok_and_list()),
    ("search_whitespace",           {"search": "   "},                           _ok_and_list()),
    ("search_single_word",          {"search": "engineer"},                      _ok_and_list()),
    ("search_number",               {"search": "5 years experience"},            _ok_and_list()),
    ("search_long_query",           {"search": "senior software engineer with 10 years python fastapi aws microservices agile scrum teamwork"},
                                                                                 _ok_and_list()),

    # ── location_aliases (soft geo) ───────────────────────────────────────────
    ("alias_california",            {"location_aliases": "san francisco,bay area,los angeles,silicon valley,sacramento,san jose,menlo park"},
                                                                                 _ok_and_list()),
    ("alias_new_york",              {"location_aliases": "new york city,manhattan,brooklyn,new york"},
                                                                                 _ok_and_list()),
    ("alias_london",                {"location_aliases": "london"},              _ok_and_list()),
    ("alias_india",                 {"location_aliases": "bangalore,hyderabad,pune,mumbai,delhi"},
                                                                                 _ok_and_list()),
    ("alias_remote",                {"location_aliases": "remote"},              _ok_and_list()),
    ("alias_canada",                {"location_aliases": "toronto,vancouver"},   _ok_and_list()),
    ("alias_seattle",               {"location_aliases": "seattle"},             _ok_and_list()),
    ("alias_austin",                {"location_aliases": "austin"},              _ok_and_list()),
    ("alias_short_us",              {"location_aliases": "usa"},                 _ok_and_list()),  # multi-char alias
    ("alias_nonexistent",           {"location_aliases": "atlantis,narnia"},     _ok_and_list()),  # 0 results ok

    # ── sort_by_salary ────────────────────────────────────────────────────────
    ("sort_salary_all",             {"sort_by_salary": True, "limit": 30},       _sorted_by_salary_desc()),
    ("sort_salary_senior",          {"sort_by_salary": True, "job_level": "SENIOR", "limit": 30},
                                                                                 _sorted_by_salary_desc()),
    ("sort_salary_mid",             {"sort_by_salary": True, "job_level": "MID", "limit": 30},
                                                                                 _sorted_by_salary_desc()),
    ("sort_salary_with_search",     {"sort_by_salary": True, "search": "engineer", "limit": 20},
                                                                                 _sorted_by_salary_desc()),
    ("sort_salary_california",      {"sort_by_salary": True, "location_aliases": "san francisco,bay area,los angeles,silicon valley,san jose,menlo park", "limit": 30},
                                                                                 _sorted_by_salary_desc()),

    # ── top_n ─────────────────────────────────────────────────────────────────
    ("top_n_5",                     {"top_n": 5, "limit": 5},                   _top_n_cap(5)),
    ("top_n_10",                    {"top_n": 10, "limit": 10},                 _top_n_cap(10)),
    ("top_n_1",                     {"top_n": 1, "limit": 1},                   _top_n_cap(1)),
    ("top_n_3",                     {"top_n": 3, "limit": 3},                   _top_n_cap(3)),
    ("top_n_0",                     {"top_n": 0, "limit": 20},                  _ok_and_list()),  # 0 = no cap

    # ── Combinations (mirror real intent-parsed queries) ──────────────────────
    # "top 10 paid jobs in california"
    ("combo_top10_paid_ca",         {"search": "jobs", "location_aliases": "san francisco,bay area,los angeles,silicon valley,sacramento,san jose,menlo park",
                                      "sort_by_salary": True, "top_n": 10, "limit": 10},
                                                                                 _top_n_cap(10)),
    # "top 5 senior python jobs"
    ("combo_top5_senior_python",    {"search": "python developer", "job_level": "SENIOR", "top_n": 5, "limit": 5},
                                                                                 _top_n_cap(5)),
    # "best paying remote jobs"
    ("combo_best_paying_remote",    {"location_aliases": "remote", "sort_by_salary": True, "limit": 30},
                                                                                 _sorted_by_salary_desc()),
    # "junior jobs in new york posted this week"
    ("combo_junior_ny_7d",          {"job_level": "JUNIOR", "location_aliases": "new york city,manhattan,brooklyn,new york",
                                      "date_range": 7},
                                                                                 _ok_and_list()),
    # "senior backend jobs with applicants"
    ("combo_senior_backend_apps",   {"search": "backend", "job_level": "SENIOR", "has_applicants": True},
                                                                                 _ok_and_list()),
    # "top 3 highest paying jobs in london"
    ("combo_top3_london",           {"location_aliases": "london", "sort_by_salary": True, "top_n": 3, "limit": 3},
                                                                                 _top_n_cap(3)),
    # "completed roles in san francisco last 30 days"
    ("combo_completed_sf_30d",      {"location": "San Francisco, CA, USA", "status": "completed", "date_range": 30},
                                                                                 _ok_and_list()),
    # "mid level data engineer remote"
    ("combo_mid_data_remote",       {"search": "data engineer", "job_level": "MID", "location_aliases": "remote"},
                                                                                 _ok_and_list()),
    # "top 10 paid jobs in new york"
    ("combo_top10_paid_ny",         {"search": "jobs", "location_aliases": "new york city,manhattan,brooklyn,new york",
                                      "sort_by_salary": True, "top_n": 10, "limit": 10},
                                                                                 _top_n_cap(10)),
    # "senior engineer with applicants sorted by salary"
    ("combo_senior_apps_salary",    {"search": "engineer", "job_level": "SENIOR", "has_applicants": True, "sort_by_salary": True},
                                                                                 _sorted_by_salary_desc()),
    # "jobs in india last 7 days"
    ("combo_india_7d",              {"location_aliases": "bangalore,hyderabad,pune,mumbai,delhi", "date_range": 7},
                                                                                 _ok_and_list()),
    # "top 5 cloud architect roles"
    ("combo_top5_cloud",            {"search": "cloud architect", "top_n": 5, "limit": 5},
                                                                                 _top_n_cap(5)),
    # "all senior completed roles"
    ("combo_senior_completed",      {"job_level": "SENIOR", "status": "completed"},
                                                                                 _ok_and_list()),
    # "react engineer in new york last 30 days"
    ("combo_react_ny_30d",          {"search": "react engineer", "location_aliases": "new york,manhattan", "date_range": 30},
                                                                                 _ok_and_list()),

    # ── Edge cases ────────────────────────────────────────────────────────────
    ("edge_all_filters",            {"search": "engineer", "job_level": "SENIOR", "status": "in_progress",
                                      "location_aliases": "san francisco", "date_range": 30,
                                      "has_applicants": True, "sort_by_salary": True, "top_n": 10, "limit": 10},
                                                                                 _top_n_cap(10)),
    ("edge_search_special_chars",   {"search": "C++ / C# developer"},           _ok_and_list()),
    ("edge_search_unicode",         {"search": "ingénieur logiciel"},            _ok_and_list()),
    ("edge_large_top_n",            {"top_n": 1000, "limit": 1000},             _ok_and_list()),
    ("edge_top_n_larger_than_pool", {"top_n": 999, "limit": 999, "job_level": "JUNIOR"},
                                                                                 _ok_and_list()),
    ("edge_date_range_0",           {"date_range": 0},                          _ok_and_list()),  # 0 = no filter
    ("edge_no_match_search",        {"search": "nonexistentxyzjob12345"},        _ok_and_list()),  # 0 results ok
    ("edge_salary_junior_india",    {"sort_by_salary": True, "job_level": "JUNIOR", "location_aliases": "bangalore,hyderabad,pune"},
                                                                                 _sorted_by_salary_desc()),
    ("edge_senior_no_location",     {"job_level": "SENIOR", "limit": 50},       _ok_and_list()),
    ("edge_limit_equals_top_n",     {"top_n": 7, "limit": 7, "sort_by_salary": True},
                                                                                 _top_n_cap(7)),
    ("edge_search_with_exact_loc",  {"search": "engineer", "location": "London, UK"},
                                                                                 _ok_and_list()),
    ("edge_alias_overridden_by_loc",{"location": "Remote", "location_aliases": "san francisco"},
                                                                                 _ok_and_list()),
    ("edge_all_senior_salary",      {"job_level": "SENIOR", "sort_by_salary": True, "limit": 50},
                                                                                 _sorted_by_salary_desc()),
    ("edge_combine_search_level_status", {"search": "developer", "job_level": "MID", "status": "in_progress"},
                                                                                 _ok_and_list()),
]

# Sanity-check exactly 100 scenarios
assert len(SCENARIOS) == 100, f"Expected 100 scenarios, got {len(SCENARIOS)}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("name,params,assert_fn", SCENARIOS, ids=[s[0] for s in SCENARIOS])
async def test_job_search(name: str, params: dict, assert_fn, app):
    """Run a single job-search scenario against the real route with mocked DB."""
    with (
        patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_make_mock_table()),
        patch("app.routes.v1.jobs.get_or_create_job_applied_table", return_value=_make_applied_table()),
        patch("app.routes.v1.jobs.get_embeddings_model", return_value=_mock_embeddings()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/jobs",
                params=params,
                headers={"Authorization": "Bearer mock-recruiter-token-123"},
            )

    status = resp.status_code
    body = resp.json() if status == 200 else resp.text
    assert_fn(status, body)


# ---------------------------------------------------------------------------
# Additional targeted tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_location_alias_filters_correctly(app):
    """Alias matching should only return jobs whose location contains the alias."""
    with (
        patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_make_mock_table()),
        patch("app.routes.v1.jobs.get_or_create_job_applied_table", return_value=_make_applied_table()),
        patch("app.routes.v1.jobs.get_embeddings_model", return_value=_mock_embeddings()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/jobs",
                params={"location_aliases": "london", "limit": 50},
                headers={"Authorization": "Bearer mock-recruiter-token-123"},
            )
    assert resp.status_code == 200
    body = resp.json()
    for job in body:
        assert "london" in (job.get("location_name") or "").lower(), \
            f"job {job['job_id']} has unexpected location: {job.get('location_name')}"


@pytest.mark.asyncio
async def test_sort_by_salary_order(app):
    """sort_by_salary=True must return jobs in descending salary order."""
    with (
        patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_make_mock_table()),
        patch("app.routes.v1.jobs.get_or_create_job_applied_table", return_value=_make_applied_table()),
        patch("app.routes.v1.jobs.get_embeddings_model", return_value=_mock_embeddings()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/jobs",
                params={"sort_by_salary": True, "limit": 30},
                headers={"Authorization": "Bearer mock-recruiter-token-123"},
            )
    assert resp.status_code == 200
    jobs = resp.json()
    salaries = [max(j.get("salary_max") or 0, j.get("salary_min") or 0) for j in jobs]
    assert salaries == sorted(salaries, reverse=True), \
        f"Not sorted: {list(zip([j['job_id'] for j in jobs], salaries))}"


@pytest.mark.asyncio
async def test_top_n_with_location_alias_gets_enough_pool(app):
    """
    Regression: top_n=10 + location_aliases must fetch >=500 rows before filtering
    (the FETCH_CAP fix) so the geo filter has a big enough pool to work with.
    """
    call_args_list = []

    def _tracking_table():
        tbl = _make_mock_table()
        original_search = tbl.search

        def search_spy(*args, **kwargs):
            q = original_search(*args, **kwargs)
            original_limit = q.limit

            def limit_spy(n):
                call_args_list.append(n)
                return original_limit(n)

            q.limit = limit_spy
            return q

        tbl.search = search_spy
        return tbl

    with (
        patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_tracking_table()),
        patch("app.routes.v1.jobs.get_or_create_job_applied_table", return_value=_make_applied_table()),
        patch("app.routes.v1.jobs.get_embeddings_model", return_value=_mock_embeddings()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/jobs",
                params={
                    "top_n": 10,
                    "limit": 10,
                    "location_aliases": "san francisco,bay area,los angeles",
                    "sort_by_salary": True,
                },
                headers={"Authorization": "Bearer mock-recruiter-token-123"},
            )

    assert resp.status_code == 200
    # FETCH_CAP must be >=500 when location_aliases is set (regression check)
    if call_args_list:
        assert max(call_args_list) >= 500, \
            f"FETCH_CAP was {max(call_args_list)}, expected >= 500 when location_aliases set"


@pytest.mark.asyncio
async def test_top_10_paid_california(app):
    """
    End-to-end scenario: 'top 10 paid jobs in california'
    After intent parsing this becomes: location_aliases=sf aliases, sort_by_salary, top_n=10.
    Validates we get <=10 results and all are from California.
    """
    ca_aliases = "san francisco,bay area,los angeles,silicon valley,sacramento,san jose,menlo park"
    with (
        patch("app.routes.v1.jobs.get_or_create_jobs_table", return_value=_make_mock_table()),
        patch("app.routes.v1.jobs.get_or_create_job_applied_table", return_value=_make_applied_table()),
        patch("app.routes.v1.jobs.get_embeddings_model", return_value=_mock_embeddings()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/jobs",
                params={
                    "search": "jobs",
                    "location_aliases": ca_aliases,
                    "sort_by_salary": True,
                    "top_n": 10,
                    "limit": 10,
                },
                headers={"Authorization": "Bearer mock-recruiter-token-123"},
            )

    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) <= 10
    assert len(jobs) > 0, "Expected some California jobs"
    ca_keywords = {"san francisco", "bay area", "los angeles", "silicon valley", "sacramento", "san jose", "menlo park"}
    for job in jobs:
        loc = (job.get("location_name") or "").lower()
        assert any(kw in loc for kw in ca_keywords), \
            f"job {job['job_id']} has non-CA location: {job.get('location_name')}"
