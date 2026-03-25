"""
Validates the candidate search endpoint (POST /api/v1/search) with 121 parametrized
scenarios + 12 targeted tests = 133 total tests.

Covers:
  - Role / skill queries (python, react, devops, ml, mobile, qa, blockchain, …)
  - Seniority + skill combinations (senior/mid/junior + stack)
  - Tech stack queries (fastapi, k8s, spark, solidity, rust, …)
  - Regional / contextual queries (remote, london, bangalore, sf, …)
  - Industry verticals (fintech, healthcare, edtech, gaming, …)
  - Natural-language / conversational queries
  - Recruiter (global) vs jobseeker (user-scoped) scoping
  - Response shape validation (score 0-100, auto_screen, required fields)
  - Edge cases (unicode, special chars, empty, very long, emojis, ALLCAPS)
  - Error conditions (no API key, DB empty, DB exception, LLM failure, malformed JSON)
"""

from __future__ import annotations

import json
import sys
import os
from contextlib import ExitStack
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch, AsyncMock

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_backend_root = os.path.join(_project_root, "backend")
for p in (_project_root, _backend_root):
    if p not in sys.path:
        sys.path.insert(0, p)

from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Shared candidate mock data — 10 diverse profiles
# ---------------------------------------------------------------------------

SAMPLE_CANDIDATES = [
    {"id": "c01", "user_id": "user_manager_789", "filename": "alice_senior_python.pdf",
     "text": "Senior Python engineer 8 yrs FastAPI PostgreSQL Kubernetes AWS microservices."},
    {"id": "c02", "user_id": "user_manager_789", "filename": "bob_react_typescript.pdf",
     "text": "Mid React developer 5 yrs TypeScript Redux Tailwind Next.js frontend."},
    {"id": "c03", "user_id": "user_manager_789", "filename": "carol_data_scientist.pdf",
     "text": "Senior Data Scientist TensorFlow PyTorch scikit-learn NLP recommendation systems."},
    {"id": "c04", "user_id": "user_manager_789", "filename": "dave_devops_sre.pdf",
     "text": "DevOps/SRE Docker Kubernetes Terraform Ansible CI/CD Jenkins GitHub Actions."},
    {"id": "c05", "user_id": "user_manager_789", "filename": "eva_ml_engineer.pdf",
     "text": "ML Engineer MLOps Kubeflow Spark Kafka streaming deep learning pipelines."},
    {"id": "c06", "user_id": "user_manager_789", "filename": "frank_fullstack.pdf",
     "text": "Full-stack Node.js Express React GraphQL MongoDB PostgreSQL REST APIs."},
    {"id": "c07", "user_id": "user_manager_789", "filename": "grace_cloud_architect.pdf",
     "text": "Cloud Architect AWS GCP Azure serverless Lambda EKS multi-cloud."},
    {"id": "c08", "user_id": "user_manager_789", "filename": "henry_mobile_dev.pdf",
     "text": "Senior iOS/Android Swift Kotlin React Native Flutter cross-platform."},
    {"id": "c09", "user_id": "user_manager_789", "filename": "iris_qa_engineer.pdf",
     "text": "QA Engineer Selenium Cypress Jest Playwright automated testing CI/CD."},
    {"id": "c10", "user_id": "user_manager_789", "filename": "jack_blockchain.pdf",
     "text": "Blockchain developer Solidity Ethereum Web3.js smart contracts DeFi Rust."},
]

_SAMPLE_DF = pd.DataFrame(SAMPLE_CANDIDATES)


def _llm_json(candidates=None, base_score=85):
    """Build a valid LLM ranking JSON string for the given candidates."""
    rows = candidates or SAMPLE_CANDIDATES
    results = []
    for i, c in enumerate(rows):
        score = max(0, min(100, base_score - i * 3))
        results.append({
            "filename": c["filename"],
            "score": score,
            "justification": f"Strong match: {c['text'][:50]}",
            "missing_skills": [],
            "auto_screen": "SELECTED" if score > 70 else "WAITLIST",
        })
    return json.dumps({"results": results})


def _mock_chain(response_text=None):
    """Return (mock_prompt, mock_chain) that yields response_text on invoke.

    The route does: chain = prompt | llm | StrOutputParser()
    That means: (prompt.__or__(llm)).__or__(StrOutputParser())
    We need both __or__ calls to return mock_ch so invoke() is always on mock_ch.
    """
    mock_ch = MagicMock()
    mock_ch.invoke.return_value = response_text or _llm_json()
    mock_ch.__or__ = MagicMock(return_value=mock_ch)  # handle | StrOutputParser()
    mock_pr = MagicMock()
    mock_pr.__or__ = MagicMock(return_value=mock_ch)
    return mock_pr, mock_ch


def _std_patches(search_df=None, llm_resp=None):
    """Standard patch stack used by every parametrized scenario."""
    mock_pr, _ = _mock_chain(llm_resp)
    stack = ExitStack()
    stack.enter_context(patch(
        "app.routes.v1.search.resolve_credentials",
        new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": "gpt-4o-mini"}),
    ))
    stack.enter_context(patch(
        "app.routes.v1.search.search_resumes_hybrid",
        return_value=search_df if search_df is not None else _SAMPLE_DF,
    ))
    stack.enter_context(patch("langchain_openai.ChatOpenAI", return_value=MagicMock()))
    stack.enter_context(patch("langchain_core.prompts.PromptTemplate", return_value=mock_pr))
    return stack


# Auth header shortcuts
_AUTH     = {"Authorization": "Bearer mock-token-123"}
_RECRUITER = {"Authorization": "Bearer mock-recruiter-token-123"}
_MANAGER  = {"Authorization": "Bearer mock-manager-token"}


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _ok_list():
    """Status 200 + results is a list."""
    def _c(s, b):
        assert s == 200, f"expected 200 got {s}: {b}"
        assert isinstance(b.get("results"), list), f"results not a list: {b}"
    return _c


def _non_empty():
    """Status 200 + at least 1 result."""
    def _c(s, b):
        assert s == 200
        assert len(b.get("results", [])) > 0, f"expected non-empty results: {b}"
    return _c


def _scores_valid():
    """All returned scores are in [0, 100]."""
    def _c(s, b):
        assert s == 200
        for r in b.get("results", []):
            sc = r.get("score", -1)
            assert 0 <= sc <= 100, f"score {sc} out of range in {r.get('filename')}"
    return _c


def _auto_screen_valid():
    """All auto_screen values are SELECTED or WAITLIST."""
    def _c(s, b):
        assert s == 200
        for r in b.get("results", []):
            assert r.get("auto_screen") in ("SELECTED", "WAITLIST"), \
                f"bad auto_screen '{r.get('auto_screen')}' for {r.get('filename')}"
    return _c


def _fields_present():
    """Every result has the 5 required fields."""
    def _c(s, b):
        assert s == 200
        for r in b.get("results", []):
            for f in ("filename", "score", "justification", "missing_skills", "auto_screen"):
                assert f in r, f"missing '{f}' in {r}"
    return _c


def _missing_skills_list():
    """missing_skills must be a list (may be empty)."""
    def _c(s, b):
        assert s == 200
        for r in b.get("results", []):
            assert isinstance(r.get("missing_skills"), list), \
                f"missing_skills is not a list in {r.get('filename')}"
    return _c


def _expect_status(expected: int):
    """Assert an exact HTTP status code."""
    def _c(s, b):
        assert s == expected, f"expected {expected} got {s}: {b}"
    return _c


def _count_le(n: int):
    def _c(s, b):
        assert s == 200
        assert len(b.get("results", [])) <= n, \
            f"expected <= {n} results, got {len(b.get('results', []))}"
    return _c


# ---------------------------------------------------------------------------
# 121 parametrized scenarios
# Each tuple: (name, query, headers, assertion_fn)
# ---------------------------------------------------------------------------

SCENARIOS: list[tuple[str, str, dict, any]] = [

    # ── 1. Role / skill queries (15) ─────────────────────────────────────────
    ("role_python_engineer",         "python engineer",                          _AUTH,     _ok_list()),
    ("role_react_developer",         "react developer",                          _AUTH,     _ok_list()),
    ("role_data_scientist",          "data scientist",                           _AUTH,     _ok_list()),
    ("role_devops_engineer",         "devops engineer",                          _AUTH,     _ok_list()),
    ("role_ml_engineer",             "machine learning engineer",                _AUTH,     _ok_list()),
    ("role_frontend_dev",            "frontend developer",                       _AUTH,     _ok_list()),
    ("role_backend_dev",             "backend engineer api",                     _AUTH,     _ok_list()),
    ("role_fullstack",               "full stack developer",                     _AUTH,     _ok_list()),
    ("role_cloud_architect",         "cloud architect",                          _AUTH,     _ok_list()),
    ("role_mobile_dev",              "mobile developer ios android",             _AUTH,     _ok_list()),
    ("role_qa_engineer",             "quality assurance automation engineer",    _AUTH,     _ok_list()),
    ("role_sre",                     "site reliability engineer",                _AUTH,     _ok_list()),
    ("role_blockchain",              "blockchain developer web3 solidity",       _AUTH,     _ok_list()),
    ("role_product_manager",         "technical product manager",                _AUTH,     _ok_list()),
    ("role_java_engineer",           "java spring boot microservices",           _AUTH,     _ok_list()),

    # ── 2. Seniority + skill combinations (12) ──────────────────────────────
    ("senior_python_fastapi",        "senior python fastapi postgresql",         _AUTH,     _ok_list()),
    ("senior_react_typescript",      "senior react typescript developer",        _AUTH,     _ok_list()),
    ("senior_data_scientist",        "senior data scientist tensorflow",         _AUTH,     _ok_list()),
    ("mid_devops_k8s",               "mid level devops kubernetes",              _AUTH,     _ok_list()),
    ("mid_backend_nodejs",           "mid level backend node.js express",        _AUTH,     _ok_list()),
    ("junior_frontend_react",        "junior frontend react developer",          _AUTH,     _ok_list()),
    ("junior_qa_selenium",           "junior qa automation selenium cypress",    _AUTH,     _ok_list()),
    ("lead_arch_distributed",        "lead software architect distributed",      _AUTH,     _ok_list()),
    ("staff_engineer_platform",      "staff engineer platform scalability",      _AUTH,     _ok_list()),
    ("principal_engineer",           "principal engineer technical leadership",  _AUTH,     _ok_list()),
    ("senior_mlops_kubeflow",        "senior mlops engineer kubeflow",           _AUTH,     _ok_list()),
    ("senior_cloud_aws_eks",         "senior cloud engineer aws eks lambda",     _AUTH,     _ok_list()),

    # ── 3. Tech stack deep-dives (20) ───────────────────────────────────────
    ("stack_fastapi_pg",             "fastapi postgresql sqlalchemy alembic",    _AUTH,     _ok_list()),
    ("stack_django_celery",          "django rest framework celery redis",       _AUTH,     _ok_list()),
    ("stack_react_ts_tailwind",      "react typescript tailwind css vite",       _AUTH,     _ok_list()),
    ("stack_k8s_docker",             "kubernetes docker helm containerisation",  _AUTH,     _ok_list()),
    ("stack_aws_lambda",             "aws lambda serverless cloudformation",     _AUTH,     _ok_list()),
    ("stack_tf_pytorch",             "tensorflow pytorch deep learning GPU",     _AUTH,     _ok_list()),
    ("stack_golang_grpc",            "golang grpc protobuf microservices",       _AUTH,     _ok_list()),
    ("stack_spark_kafka",            "apache spark kafka flink streaming",       _AUTH,     _ok_list()),
    ("stack_ruby_rails",             "ruby on rails postgresql sidekiq",         _AUTH,     _ok_list()),
    ("stack_node_express",           "node.js express mongodb rest api",         _AUTH,     _ok_list()),
    ("stack_vue_graphql",            "vue.js graphql apollo subscriptions",      _AUTH,     _ok_list()),
    ("stack_terraform_ansible",      "terraform ansible infrastructure as code", _AUTH,     _ok_list()),
    ("stack_elastic_kibana",         "elasticsearch kibana logstash elk stack",  _AUTH,     _ok_list()),
    ("stack_solidity_hardhat",       "solidity hardhat ethereum smart contracts",_AUTH,     _ok_list()),
    ("stack_flutter_dart",           "flutter dart mobile cross-platform",       _AUTH,     _ok_list()),
    ("stack_rust_tokio",             "rust tokio async systems programming",     _AUTH,     _ok_list()),
    ("stack_scala_akka",             "scala akka actor model reactive streams",  _AUTH,     _ok_list()),
    ("stack_snowflake_dbt",          "snowflake dbt data warehouse analytics",   _AUTH,     _ok_list()),
    ("stack_redis_rabbitmq",         "redis rabbitmq message queue caching",     _AUTH,     _ok_list()),
    ("stack_nextjs_prisma",          "next.js prisma trpc typescript fullstack", _AUTH,     _ok_list()),

    # ── 4. Regional / contextual queries (12) ───────────────────────────────
    ("region_remote",                "remote software engineer",                 _AUTH,     _ok_list()),
    ("region_london_backend",        "backend engineer london uk",               _AUTH,     _ok_list()),
    ("region_bangalore_python",      "python developer bangalore india",         _AUTH,     _ok_list()),
    ("region_sf_engineer",           "software engineer san francisco bay area", _AUTH,     _ok_list()),
    ("region_ny_fintech",            "software engineer new york fintech",       _AUTH,     _ok_list()),
    ("region_canada_ml",             "machine learning engineer toronto canada", _AUTH,     _ok_list()),
    ("region_seattle_cloud",         "cloud engineer seattle aws",               _AUTH,     _ok_list()),
    ("region_austin_sre",            "site reliability engineer austin texas",   _AUTH,     _ok_list()),
    ("region_singapore_blockchain",  "blockchain developer singapore",           _AUTH,     _ok_list()),
    ("region_berlin_backend",        "backend engineer berlin germany",          _AUTH,     _ok_list()),
    ("region_hybrid_role",           "hybrid remote senior engineer",            _AUTH,     _ok_list()),
    ("region_apac_mobile",           "mobile developer apac",                    _AUTH,     _ok_list()),

    # ── 5. Industry verticals (8) ────────────────────────────────────────────
    ("vertical_fintech",             "fintech backend engineer payments api",    _AUTH,     _ok_list()),
    ("vertical_healthcare",          "healthcare software engineer hl7 fhir",    _AUTH,     _ok_list()),
    ("vertical_edtech",              "edtech learning platform developer lms",   _AUTH,     _ok_list()),
    ("vertical_gaming",              "game developer unity c++ real-time",       _AUTH,     _ok_list()),
    ("vertical_ecommerce",           "ecommerce backend engineer shopify",       _AUTH,     _ok_list()),
    ("vertical_cybersecurity",       "cybersecurity engineer appsec owasp",      _AUTH,     _ok_list()),
    ("vertical_adtech",              "adtech data engineer bidding rtb",         _AUTH,     _ok_list()),
    ("vertical_logistics",           "logistics platform engineer routing api",  _AUTH,     _ok_list()),

    # ── 6. Natural-language / conversational queries (10) ───────────────────
    ("nl_team_lead",                 "looking for someone who can lead a team",  _AUTH,     _ok_list()),
    ("nl_mentor",                    "experienced engineer who mentors junior developers", _AUTH, _ok_list()),
    ("nl_startup",                   "engineer who thrives in fast-paced startup",_AUTH,    _ok_list()),
    ("nl_genai_llm",                 "engineer experienced in generative ai llm applications langchain", _AUTH, _ok_list()),
    ("nl_problem_solver",            "strong problem solver excellent communicator", _AUTH,  _ok_list()),
    ("nl_agile",                     "agile practitioner scrum master delivery", _AUTH,     _ok_list()),
    ("nl_cross_functional",          "cross-functional collaboration stakeholders", _AUTH,  _ok_list()),
    ("nl_open_source",               "open source contributor github active projects", _AUTH, _ok_list()),
    ("nl_phd_researcher",            "phd researcher machine learning published", _AUTH,    _ok_list()),
    ("nl_code_quality",              "highly productive engineer code quality best practices TDD", _AUTH, _ok_list()),

    # ── 7. Recruiter / manager scope (global search) (5) ────────────────────
    ("recruiter_python",             "python engineer",                          _RECRUITER, _ok_list()),
    ("recruiter_data_science",       "data scientist ml tensorflow",             _RECRUITER, _ok_list()),
    ("recruiter_fullstack",          "full stack developer",                     _RECRUITER, _ok_list()),
    ("manager_cloud",                "cloud architect aws gcp",                  _MANAGER,  _ok_list()),
    ("manager_senior_backend",       "senior backend engineer python microservices", _MANAGER, _ok_list()),

    # ── 8. Response shape / quality assertions (9) ──────────────────────────
    ("quality_scores_range",         "senior software engineer",                 _AUTH,     _scores_valid()),
    ("quality_auto_screen_valid",    "python backend developer",                 _AUTH,     _auto_screen_valid()),
    ("quality_required_fields",      "react frontend developer",                 _AUTH,     _fields_present()),
    ("quality_missing_skills_list",  "devops kubernetes docker terraform",       _AUTH,     _missing_skills_list()),
    ("quality_non_empty",            "data scientist tensorflow pytorch nlp",    _AUTH,     _non_empty()),
    ("quality_count_le_10",          "software engineer",                        _AUTH,     _count_le(10)),
    ("quality_scores_recruiter",     "machine learning engineer",                _RECRUITER,_scores_valid()),
    ("quality_auto_screen_manager",  "cloud architect",                          _MANAGER,  _auto_screen_valid()),
    ("quality_fields_recruiter",     "senior python engineer",                   _RECRUITER,_fields_present()),

    # ── 9. Edge cases — query content (15) ──────────────────────────────────
    ("edge_empty_string",            "",                                          _AUTH,     _expect_status(422)),
    ("edge_whitespace_only",         "   ",                                       _AUTH,     _ok_list()),
    ("edge_single_char",             "a",                                         _AUTH,     _ok_list()),
    ("edge_single_word",             "engineer",                                  _AUTH,     _ok_list()),
    ("edge_numbers_only",            "5 years experience",                        _AUTH,     _ok_list()),
    ("edge_special_chars",           "C++ / C# .NET developer",                   _AUTH,     _ok_list()),
    ("edge_unicode_fr",              "ingénieur logiciel python",                 _AUTH,     _ok_list()),
    ("edge_unicode_jp",              "ソフトウェアエンジニア",                       _AUTH,     _ok_list()),
    ("edge_unicode_kr",              "백엔드 개발자",                               _AUTH,     _ok_list()),
    ("edge_emoji",                   "🚀 rocket engineer 💻 coding",              _AUTH,     _ok_list()),
    ("edge_allcaps",                 "SENIOR PYTHON ENGINEER AWS",                _AUTH,     _ok_list()),
    ("edge_camelcase",               "SeniorPythonEngineerAWS",                   _AUTH,     _ok_list()),
    ("edge_question",                "who is the best python developer here?",    _AUTH,     _ok_list()),
    ("edge_html_tags",               "<b>engineer</b> <script>xss</script>",      _AUTH,     _ok_list()),
    ("edge_long_query",
        "senior software engineer 10 years python fastapi django postgresql "
        "mongodb redis kafka kubernetes docker terraform aws gcp react typescript "
        "microservices distributed systems leadership mentoring agile ci/cd "
        "github actions code review testing tdd bdd clean architecture solid",    _AUTH,     _ok_list()),

    # ── 10. Complex real-world combination queries (15) ──────────────────────
    ("combo_senior_py_remote",       "senior python engineer remote work",       _AUTH,     _ok_list()),
    ("combo_mid_react_ny",           "mid level react developer new york",       _AUTH,     _ok_list()),
    ("combo_junior_qa_india",        "junior qa automation bangalore india",     _AUTH,     _ok_list()),
    ("combo_lead_arch_sf",           "lead cloud architect san francisco",       _AUTH,     _ok_list()),
    ("combo_senior_ml_fintech",      "senior ml engineer fintech payments fraud",_AUTH,     _ok_list()),
    ("combo_devops_k8s_remote",      "devops kubernetes terraform remote",       _AUTH,     _ok_list()),
    ("combo_fullstack_startup",      "full stack engineer startup fast-paced react node", _AUTH, _ok_list()),
    ("combo_senior_go_microservices","senior golang microservices engineer",     _AUTH,     _ok_list()),
    ("combo_data_eng_spark_remote",  "data engineer apache spark kafka remote",  _AUTH,     _ok_list()),
    ("combo_ios_swift_london",       "ios swift developer london uk",            _AUTH,     _ok_list()),
    ("combo_senior_sre_aws",         "senior sre reliability engineer aws gcp", _AUTH,     _ok_list()),
    ("combo_blockchain_sg",          "blockchain solidity engineer singapore",   _AUTH,     _ok_list()),
    ("combo_pm_saas_agile",          "product manager b2b saas agile roadmap",  _AUTH,     _ok_list()),
    ("combo_nlp_research",           "machine learning nlp research scientist bert", _AUTH,  _ok_list()),
    ("combo_security_appsec",        "application security engineer owasp devsecops", _AUTH, _ok_list()),
]

assert len(SCENARIOS) == 121, f"Expected 121 scenarios, got {len(SCENARIOS)}"


# ---------------------------------------------------------------------------
# Parametrized test runner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("name,query,headers,assert_fn", SCENARIOS, ids=[s[0] for s in SCENARIOS])
async def test_candidate_search(name: str, query: str, headers: dict, assert_fn, app):
    """Run one candidate-search scenario against the real route with mocked DB + LLM."""
    with _std_patches():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search",
                json={"query": query},
                headers=headers,
            )

    status = resp.status_code
    body = resp.json() if status == 200 else resp.text
    assert_fn(status, body)


# ---------------------------------------------------------------------------
# Targeted tests — error conditions and scoping behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_api_key_returns_error(app):
    """Route returns error payload (not 500) when OpenRouter key is missing."""
    with patch(
        "app.routes.v1.search.resolve_credentials",
        new=AsyncMock(return_value={"openrouter_key": None, "llm_model": None}),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "python engineer"}, headers=_AUTH)

    assert resp.status_code == 200
    body = resp.json()
    assert "error" in body, f"expected 'error' key: {body}"
    assert body.get("results") == [], f"expected empty results: {body}"


@pytest.mark.asyncio
async def test_db_empty_returns_empty_results(app):
    """Empty DB (zero rows) returns results=[] without calling the LLM."""
    mock_pr, mock_ch = _mock_chain()
    with (
        patch("app.routes.v1.search.resolve_credentials",
              new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})),
        patch("app.routes.v1.search.search_resumes_hybrid",
              return_value=pd.DataFrame()),
        patch("langchain_openai.ChatOpenAI", return_value=MagicMock()),
        patch("langchain_core.prompts.PromptTemplate", return_value=mock_pr),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "react developer"}, headers=_AUTH)

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("results") == [], f"expected empty results: {body}"
    mock_ch.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_db_exception_returns_error(app):
    """DB embedding/search failure is caught and returned as an error payload."""
    mock_pr, _ = _mock_chain()
    with (
        patch("app.routes.v1.search.resolve_credentials",
              new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})),
        patch("app.routes.v1.search.search_resumes_hybrid",
              side_effect=RuntimeError("LanceDB connection failed")),
        patch("langchain_openai.ChatOpenAI", return_value=MagicMock()),
        patch("langchain_core.prompts.PromptTemplate", return_value=mock_pr),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "backend engineer"}, headers=_AUTH)

    assert resp.status_code == 200
    body = resp.json()
    assert "error" in body, f"expected 'error' key: {body}"


@pytest.mark.asyncio
async def test_search_returns_results_without_llm(app):
    """Search now uses deterministic scoring — no LLM call; results are returned directly."""
    with (
        patch("app.routes.v1.search.resolve_credentials",
              new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})),
        patch("app.routes.v1.search.search_resumes_hybrid", return_value=_SAMPLE_DF),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "data scientist"}, headers=_AUTH)

    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body, f"expected 'results' key: {body}"
    assert len(body["results"]) > 0


@pytest.mark.asyncio
async def test_llm_malformed_json_handled(app):
    """LLM returning non-JSON text doesn't crash the route."""
    mock_ch = MagicMock()
    mock_ch.invoke.return_value = "Sorry I cannot help with that."
    mock_pr = MagicMock()
    mock_pr.__or__ = MagicMock(return_value=mock_ch)

    with (
        patch("app.routes.v1.search.resolve_credentials",
              new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})),
        patch("app.routes.v1.search.search_resumes_hybrid", return_value=_SAMPLE_DF),
        patch("langchain_openai.ChatOpenAI", return_value=MagicMock()),
        patch("langchain_core.prompts.PromptTemplate", return_value=mock_pr),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "cloud architect"}, headers=_AUTH)

    assert resp.status_code == 200  # never a 500


@pytest.mark.asyncio
async def test_recruiter_searches_globally(app):
    """Recruiter token must call search_resumes_hybrid with is_recruiter=True."""
    mock_pr, _ = _mock_chain()
    search_mock = MagicMock(return_value=_SAMPLE_DF)

    with (
        patch("app.routes.v1.search.resolve_credentials",
              new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})),
        patch("app.routes.v1.search.search_resumes_hybrid", search_mock),
        patch("langchain_openai.ChatOpenAI", return_value=MagicMock()),
        patch("langchain_core.prompts.PromptTemplate", return_value=mock_pr),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search",
                json={"query": "python engineer"},
                headers=_RECRUITER,
            )

    assert resp.status_code == 200
    call_kwargs = search_mock.call_args
    is_recruiter_arg = (
        call_kwargs.kwargs.get("is_recruiter")
        if call_kwargs.kwargs
        else (call_kwargs.args[4] if len(call_kwargs.args) > 4 else None)
    )
    assert is_recruiter_arg is True, f"is_recruiter should be True for recruiter, got {is_recruiter_arg}"


@pytest.mark.asyncio
async def test_jobseeker_searches_own_scope(app):
    """Regular jobseeker token must call search_resumes_hybrid with is_recruiter=False."""
    mock_pr, _ = _mock_chain()
    search_mock = MagicMock(return_value=_SAMPLE_DF)

    with (
        patch("app.routes.v1.search.resolve_credentials",
              new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})),
        patch("app.routes.v1.search.search_resumes_hybrid", search_mock),
        patch("langchain_openai.ChatOpenAI", return_value=MagicMock()),
        patch("langchain_core.prompts.PromptTemplate", return_value=mock_pr),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search",
                json={"query": "python engineer"},
                headers=_AUTH,
            )

    assert resp.status_code == 200
    call_kwargs = search_mock.call_args
    is_recruiter_arg = (
        call_kwargs.kwargs.get("is_recruiter")
        if call_kwargs.kwargs
        else (call_kwargs.args[4] if len(call_kwargs.args) > 4 else None)
    )
    assert is_recruiter_arg is False, f"is_recruiter should be False for jobseeker, got {is_recruiter_arg}"


@pytest.mark.asyncio
async def test_auto_screen_selected_above_70(app):
    """Candidates with score > 70 must have auto_screen=SELECTED."""
    high_score_resp = json.dumps({"results": [
        {"filename": "a.pdf", "score": 90, "justification": "great", "missing_skills": [], "auto_screen": "SELECTED"},
        {"filename": "b.pdf", "score": 72, "justification": "ok",    "missing_skills": [], "auto_screen": "SELECTED"},
        {"filename": "c.pdf", "score": 55, "justification": "weak",  "missing_skills": ["docker"], "auto_screen": "WAITLIST"},
    ]})
    mock_pr, _ = _mock_chain(high_score_resp)

    with _std_patches(llm_resp=high_score_resp):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "senior python"}, headers=_AUTH)

    body = resp.json()
    for r in body.get("results", []):
        if r["score"] > 70:
            assert r["auto_screen"] == "SELECTED", \
                f"score {r['score']} > 70 but auto_screen={r['auto_screen']}"
        else:
            assert r["auto_screen"] == "WAITLIST", \
                f"score {r['score']} <= 70 but auto_screen={r['auto_screen']}"


@pytest.mark.asyncio
async def test_chunk_deduplication(app):
    """Duplicate text chunks from the same file must produce only one result entry."""
    dup_df = pd.DataFrame([
        {"id": "x1", "user_id": "u", "filename": "resume.pdf", "text": "Python expert"},
        {"id": "x2", "user_id": "u", "filename": "resume.pdf", "text": "Python expert"},   # duplicate
        {"id": "x3", "user_id": "u", "filename": "resume.pdf", "text": "FastAPI experience"},
    ])

    with (
        patch("app.routes.v1.search.resolve_credentials",
              new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})),
        patch("app.routes.v1.search.search_resumes_hybrid", return_value=dup_df),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "python"}, headers=_AUTH)

    assert resp.status_code == 200
    body = resp.json()
    # All three rows are from the same file — should be aggregated into one result entry
    filenames = [r["filename"] for r in body.get("results", [])]
    assert filenames.count("resume.pdf") == 1, \
        f"duplicate chunks were not aggregated into a single result: {filenames}"


@pytest.mark.asyncio
async def test_missing_query_field_returns_422(app):
    """POST body without 'query' field must return HTTP 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/search", json={}, headers=_AUTH)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_llm_search_limit_is_10(app):
    """search_resumes_hybrid must be called with limit=10."""
    mock_pr, _ = _mock_chain()
    search_mock = MagicMock(return_value=_SAMPLE_DF)

    with (
        patch("app.routes.v1.search.resolve_credentials",
              new=AsyncMock(return_value={"openrouter_key": "sk-test", "llm_model": None})),
        patch("app.routes.v1.search.search_resumes_hybrid", search_mock),
        patch("langchain_openai.ChatOpenAI", return_value=MagicMock()),
        patch("langchain_core.prompts.PromptTemplate", return_value=mock_pr),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/search", json={"query": "devops"}, headers=_AUTH)

    call_kwargs = search_mock.call_args
    limit_arg = (
        call_kwargs.kwargs.get("limit")
        if call_kwargs.kwargs
        else (call_kwargs.args[2] if len(call_kwargs.args) > 2 else None)
    )
    assert limit_arg == 10, f"expected limit=10, got {limit_arg}"
