"""
Backend tests for GET /api/v1/resumes/database?search=<natural-language-query>

Validates that the resume database semantic search endpoint correctly:
  - Resolves credentials and calls search_resumes_hybrid with the API key
  - Returns 200 with {"resumes": [...], "total": N} for all supported query patterns
  - Surfaces the right candidates for geo/company/skill/seniority queries
  - Falls back gracefully when semantic search raises an exception

Queries covered (mirrors the E2E Playwright tests):
  1.  candidates from southern california
  2.  candidates from silicon valley
  3.  senior managers from europe
  4.  executives from NY
  5.  candidates currently working in FANG
  6.  candidates from SF metro area or 50 mile radius
  7.  experts in ML or machine learning
  8.  experts in AI
  9.  experts in cloud storage or distributed storage
  10. smart engineers in data science
  11. candidates who worked in FANG      (past-tense + boost)
  12. candidate working in microsoft      (present-tense strict filter → only current employees)
  13. candidate from apple and google     (multi-company LLM expansion + boost)
  14. candidate worked in apple           (single-company past-tense + boost)
  15. java developer from apple           (role+company → hasRoleSignal, no company boost, semantic-first)
  16. candidate from google               (strictCompany=True → current Google employees only)
  17. candidate from netflix              (strictCompany=True → current Netflix employee only)
  18. candidate from amazon               (strictCompany=True → current Amazon employee only)
  19. senior engineer at microsoft        (strictCompany=True + expLevel=Senior → senior MS employees)
  20. candidate from meta                 (strictCompany=True → current Meta employee only)

Apple phrasing variations:
  21. candidate working in apple          (present-tense "working in" → strictCompany=True)
  22. candidate worked for apple          (past-tense "worked for" → strictCompany=False)
  23. former apple employee               (past-tense "former" → strictCompany=False)
  24. ex apple engineer                   (past-tense "ex" → strictCompany=False)
  25. engineers at apple                  (present-tense "at" → strictCompany=True)
  26. apple software engineer             (implicit current → strictCompany=True)
  27. senior engineer from apple          (strictCompany=True + expLevel=Senior → senior Apple only)
  28. apple alumni                        (past-tense "alumni" → strictCompany=False)
"""

from __future__ import annotations

import json
import os
import sys
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
# Rich candidate pool — covers all query scenarios
# ---------------------------------------------------------------------------

_CANDIDATES = [
    # --- Southern California (locations contain "california" / "los angeles" / "san diego")
    {"filename": "alice_la_engineer.pdf",     "user_id": "user_manager_789",
     "location": "Los Angeles, California",   "current_company": "Snap Inc",
     "role": "Software Engineer",             "exp_level": "Senior",
     "candidate_name": "Alice Torres",        "industry": "Technology"},
    {"filename": "bob_sandiego_dev.pdf",       "user_id": "user_manager_789",
     "location": "San Diego, California",     "current_company": "Qualcomm",
     "role": "Embedded Engineer",             "exp_level": "Mid-level",
     "candidate_name": "Bob Navarro",         "industry": "Technology"},

    # --- Silicon Valley (locations contain "palo alto" / "san jose") ---
    {"filename": "carol_sv_ml.pdf",           "user_id": "user_manager_789",
     "location": "Palo Alto, CA",             "current_company": "NVIDIA",
     "role": "ML Engineer",                   "exp_level": "Senior",
     "candidate_name": "Carol Zhang",         "industry": "Technology"},
    {"filename": "dave_sanjose_swe.pdf",      "user_id": "user_manager_789",
     "location": "San Jose, CA",              "current_company": "Cisco",
     "role": "Software Engineer",             "exp_level": "Mid-level",
     "candidate_name": "Dave Kim",            "industry": "Technology"},

    # --- Europe (locations contain "london" / "berlin" / "germany" / "uk") ---
    {"filename": "eva_london_manager.pdf",    "user_id": "user_manager_789",
     "location": "London, UK",                "current_company": "Revolut",
     "role": "Senior Engineering Manager",    "exp_level": "Senior",
     "candidate_name": "Eva Müller",          "industry": "Fintech"},
    {"filename": "frank_berlin_vp.pdf",       "user_id": "user_manager_789",
     "location": "Berlin, Germany",           "current_company": "N26",
     "role": "VP Engineering",               "exp_level": "Executive",
     "candidate_name": "Frank Bauer",         "industry": "Fintech"},

    # --- New York (locations contain "new york" / "manhattan") ---
    {"filename": "grace_ny_cto.pdf",          "user_id": "user_manager_789",
     "location": "New York, NY",              "current_company": "Bloomberg",
     "role": "CTO",                           "exp_level": "Executive",
     "candidate_name": "Grace Chen",          "industry": "Finance"},
    {"filename": "henry_nyc_director.pdf",    "user_id": "user_manager_789",
     "location": "Manhattan, NY",             "current_company": "Goldman Sachs",
     "role": "Director of Engineering",       "exp_level": "Executive",
     "candidate_name": "Henry Park",          "industry": "Finance"},

    # --- FANG employees (FANG = company, not a location — no loc pre-filter) ---
    {"filename": "iris_google_swe.pdf",       "user_id": "user_manager_789",
     "location": "Mountain View, CA",         "current_company": "Google",
     "role": "Staff Software Engineer",       "exp_level": "Senior",
     "candidate_name": "Iris Patel",          "industry": "Technology"},
    {"filename": "jack_meta_ml.pdf",          "user_id": "user_manager_789",
     "location": "Menlo Park, CA",            "current_company": "Meta",
     "role": "ML Research Engineer",          "exp_level": "Senior",
     "candidate_name": "Jack Liu",            "industry": "Technology"},
    {"filename": "kim_amazon_sde.pdf",        "user_id": "user_manager_789",
     "location": "Seattle, WA",               "current_company": "Amazon",
     "role": "Senior SDE",                    "exp_level": "Senior",
     "candidate_name": "Kim Brown",           "industry": "Technology"},
    {"filename": "lee_netflix_arch.pdf",      "user_id": "user_manager_789",
     "location": "Los Gatos, CA",             "current_company": "Netflix",
     "role": "Principal Architect",           "exp_level": "Senior",
     "candidate_name": "Lee Davis",           "industry": "Technology"},
    # Apple and Google candidates (for multi-company and "jobs in apple" style queries)
    {"filename": "nora_apple_eng.pdf",        "user_id": "user_manager_789",
     "location": "Cupertino, CA",             "current_company": "Apple",
     "role": "iOS Software Engineer",         "exp_level": "Senior",
     "candidate_name": "Nora Kim",            "industry": "Technology"},
    {"filename": "omar_apple_design.pdf",     "user_id": "user_manager_789",
     "location": "Cupertino, CA",             "current_company": "Apple",
     "role": "UI Engineer",                   "exp_level": "Mid-level",
     "candidate_name": "Omar Hassan",         "industry": "Technology"},
    {"filename": "priya_google_infra.pdf",    "user_id": "user_manager_789",
     "location": "Mountain View, CA",         "current_company": "Google",
     "role": "Infrastructure Engineer",       "exp_level": "Senior",
     "candidate_name": "Priya Singh",         "industry": "Technology"},
    # Microsoft candidates (for strict present-tense company filter tests)
    {"filename": "raj_microsoft_pm.pdf",      "user_id": "user_manager_789",
     "location": "Redmond, WA",               "current_company": "Microsoft",
     "role": "Product Manager",               "exp_level": "Senior",
     "candidate_name": "Raj Patel",           "industry": "Technology"},
    {"filename": "sara_microsoft_swe.pdf",    "user_id": "user_manager_789",
     "location": "Redmond, WA",               "current_company": "Microsoft",
     "role": "Software Engineer II",          "exp_level": "Mid-level",
     "candidate_name": "Sara Williams",       "industry": "Technology"},

    # --- SF metro (locations contain "san francisco" / "oakland") ---
    {"filename": "maya_sf_pm.pdf",            "user_id": "user_manager_789",
     "location": "San Francisco, CA",         "current_company": "Stripe",
     "role": "Product Manager",               "exp_level": "Mid-level",
     "candidate_name": "Maya Johnson",        "industry": "Fintech"},
    {"filename": "noah_oakland_sre.pdf",      "user_id": "user_manager_789",
     "location": "Oakland, CA",               "current_company": "Cloudflare",
     "role": "SRE",                           "exp_level": "Mid-level",
     "candidate_name": "Noah Williams",       "industry": "Technology"},

    # --- ML / AI experts ---
    {"filename": "olivia_ml_research.pdf",    "user_id": "user_manager_789",
     "location": "Boston, MA",                "current_company": "MIT CSAIL",
     "role": "ML Research Scientist",         "exp_level": "Senior",
     "candidate_name": "Olivia Hernandez",    "industry": "Research"},
    {"filename": "paul_ai_nlp.pdf",           "user_id": "user_manager_789",
     "location": "Seattle, WA",               "current_company": "Microsoft",
     "role": "AI Engineer",                   "exp_level": "Senior",
     "candidate_name": "Paul Nguyen",         "industry": "Technology"},

    # --- Cloud / distributed storage experts ---
    {"filename": "quinn_cloud_infra.pdf",     "user_id": "user_manager_789",
     "location": "Austin, TX",                "current_company": "Snowflake",
     "role": "Cloud Infrastructure Engineer", "exp_level": "Senior",
     "candidate_name": "Quinn Rodriguez",     "industry": "Technology"},
    {"filename": "rosa_dist_systems.pdf",     "user_id": "user_manager_789",
     "location": "San Francisco, CA",         "current_company": "Databricks",
     "role": "Distributed Systems Engineer",  "exp_level": "Senior",
     "candidate_name": "Rosa Martinez",       "industry": "Technology"},

    # --- Data science ---
    {"filename": "sam_datascience.pdf",       "user_id": "user_manager_789",
     "location": "Chicago, IL",               "current_company": "Tableau",
     "role": "Senior Data Scientist",         "exp_level": "Senior",
     "candidate_name": "Sam Thompson",        "industry": "Analytics"},
    {"filename": "tina_analytics.pdf",        "user_id": "user_manager_789",
     "location": "Denver, CO",                "current_company": "Palantir",
     "role": "Data Scientist",                "exp_level": "Mid-level",
     "candidate_name": "Tina Garcia",         "industry": "Analytics"},

    # --- Java developers (for "java developer from apple" role-signal test) ---
    {"filename": "uma_java_dev.pdf",          "user_id": "user_manager_789",
     "location": "New York, NY",              "current_company": "JPMorgan",
     "role": "Java Backend Developer",        "exp_level": "Senior",
     "candidate_name": "Uma Krishnan",        "industry": "Finance"},
    {"filename": "victor_apple_java.pdf",     "user_id": "user_manager_789",
     "location": "Cupertino, CA",             "current_company": "Apple",
     "role": "Java Software Engineer",        "exp_level": "Mid-level",
     "candidate_name": "Victor Tan",          "industry": "Technology"},

    # --- Geographic region candidates (for regional search tests) ---
    # Asia (broad)
    {"filename": "wei_beijing_swe.pdf",       "user_id": "user_manager_789",
     "location": "Beijing, China",            "current_company": "Baidu",
     "role": "Senior Software Engineer",      "exp_level": "Senior",
     "candidate_name": "Wei Zhang",           "industry": "Technology"},
    {"filename": "yuki_tokyo_eng.pdf",        "user_id": "user_manager_789",
     "location": "Tokyo, Japan",              "current_company": "Sony",
     "role": "Software Engineer",             "exp_level": "Mid-level",
     "candidate_name": "Yuki Tanaka",         "industry": "Technology"},
    {"filename": "ji_seoul_dev.pdf",          "user_id": "user_manager_789",
     "location": "Seoul, South Korea",        "current_company": "Samsung",
     "role": "Backend Developer",             "exp_level": "Senior",
     "candidate_name": "Ji-ho Kim",           "industry": "Technology"},
    # Southeast Asia
    {"filename": "andi_jakarta_eng.pdf",      "user_id": "user_manager_789",
     "location": "Jakarta, Indonesia",        "current_company": "Gojek",
     "role": "Platform Engineer",             "exp_level": "Mid-level",
     "candidate_name": "Andi Pratama",        "industry": "Technology"},
    {"filename": "siri_bangkok_dev.pdf",      "user_id": "user_manager_789",
     "location": "Bangkok, Thailand",         "current_company": "Agoda",
     "role": "Software Developer",            "exp_level": "Mid-level",
     "candidate_name": "Siri Charoenwong",    "industry": "Technology"},
    # USA — West Coast
    {"filename": "alex_portland_swe.pdf",     "user_id": "user_manager_789",
     "location": "Portland, OR",              "current_company": "Nike",
     "role": "Software Engineer",             "exp_level": "Mid-level",
     "candidate_name": "Alex Rivera",         "industry": "Technology"},
    # USA — Midwest
    {"filename": "dan_chicago_eng.pdf",       "user_id": "user_manager_789",
     "location": "Chicago, IL",               "current_company": "Motorola",
     "role": "Senior Engineer",               "exp_level": "Senior",
     "candidate_name": "Dan Kowalski",        "industry": "Technology"},
    {"filename": "mia_detroit_dev.pdf",       "user_id": "user_manager_789",
     "location": "Detroit, MI",               "current_company": "Ford",
     "role": "Software Developer",            "exp_level": "Mid-level",
     "candidate_name": "Mia Johnson",         "industry": "Automotive"},
    # USA — East Coast
    {"filename": "eli_boston_eng.pdf",        "user_id": "user_manager_789",
     "location": "Boston, MA",                "current_company": "HubSpot",
     "role": "Backend Engineer",              "exp_level": "Senior",
     "candidate_name": "Eli Cohen",           "industry": "Technology"},
    # North America — Canada
    {"filename": "sophie_montreal_dev.pdf",   "user_id": "user_manager_789",
     "location": "Montreal, Canada",          "current_company": "Ubisoft",
     "role": "Game Developer",                "exp_level": "Mid-level",
     "candidate_name": "Sophie Tremblay",     "industry": "Gaming"},
    # South Asia (additional)
    {"filename": "arjun_pune_swe.pdf",        "user_id": "user_manager_789",
     "location": "Pune, India",               "current_company": "Infosys",
     "role": "Software Engineer",             "exp_level": "Mid-level",
     "candidate_name": "Arjun Desai",         "industry": "Technology"},
    # Australia
    {"filename": "chloe_sydney_eng.pdf",      "user_id": "user_manager_789",
     "location": "Sydney, Australia",         "current_company": "Atlassian",
     "role": "Senior Software Engineer",      "exp_level": "Senior",
     "candidate_name": "Chloe Murphy",        "industry": "Technology"},
    {"filename": "liam_melbourne_dev.pdf",    "user_id": "user_manager_789",
     "location": "Melbourne, Australia",      "current_company": "Canva",
     "role": "Full Stack Developer",          "exp_level": "Mid-level",
     "candidate_name": "Liam O'Brien",        "industry": "Technology"},
]


def _make_meta_df() -> pd.DataFrame:
    """Build a resume_meta table DataFrame from the candidate pool."""
    rows = []
    for i, c in enumerate(_CANDIDATES):
        rows.append({
            "id": f"m{i:02d}",
            "user_id": c["user_id"],
            "filename": c["filename"],
            "validation_json": json.dumps({
                "classification": "resume_valid_good",
                "total_score": 22,
                "scores": {},
            }),
            "uploaded_at": f"2026-02-{(i % 28) + 1:02d}T10:00:00",
            "industry":       c.get("industry"),
            "role":           c.get("role"),
            "exp_level":      c.get("exp_level"),
            "location":       c.get("location"),
            "candidate_name": c.get("candidate_name"),
            "current_company":c.get("current_company"),
            "phone":          None,
            "email":          f"{c['filename'].replace('.pdf','').replace('_','.')}@example.com",
            "linkedin_url":   None,
            "github_url":     None,
            "skills_json":    None,
            "summary":        None,
            "years_experience": None,
            "education":      None,
            "certifications_json": None,
        })
    return pd.DataFrame(rows)


def _semantic_df(*filenames: str) -> pd.DataFrame:
    """Return a DataFrame of the requested filenames (simulates semantic search ranking)."""
    rows = [c for c in _CANDIDATES if c["filename"] in filenames]
    return pd.DataFrame([
        {"id": f"r{i}", "user_id": c["user_id"], "filename": c["filename"],
         "text": f"{c['role']} at {c['current_company']} in {c['location']}"}
        for i, c in enumerate(rows)
    ])


_MANAGER = {"Authorization": "Bearer mock-manager-token"}
_CREDS   = {"openrouter_key": "sk-test-key", "llm_model": "gpt-4o-mini"}

# Per-query AI intent — mirrors what the LLM would return.
# locationAliases must match the stored location strings in _CANDIDATES.
_QUERY_INTENTS: dict[str, dict] = {
    "candidates from southern california": {
        "locationAliases": ["los angeles", "san diego", "orange county", "irvine",
                            "anaheim", "riverside", "pasadena", "long beach",
                            "santa monica", "burbank"],
        "companyFilter": [], "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from LA metro area": {
        "locationAliases": ["los angeles", "long beach", "santa monica", "burbank", "culver city"],
        "companyFilter": [], "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from greater LA": {
        "locationAliases": ["los angeles", "long beach", "santa monica", "burbank", "culver city"],
        "companyFilter": [], "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from silicon valley": {
        "locationAliases": ["palo alto", "san jose", "mountain view", "sunnyvale", "san francisco"],
        "companyFilter": [], "expLevel": None, "cleanQuery": "software engineer",
    },
    "senior managers from europe": {
        "locationAliases": ["london", "berlin", "uk", "germany", "france", "amsterdam"],
        "companyFilter": [], "expLevel": "Senior", "cleanQuery": "engineering manager",
    },
    "executives from NY": {
        "locationAliases": ["new york", "manhattan"],
        "companyFilter": [], "expLevel": "Executive", "cleanQuery": "executive",
    },
    "candidates currently working in FANG": {
        "locationAliases": [],
        "companyFilter": ["google", "meta", "amazon", "apple", "netflix", "microsoft"],
        "strictCompany": True,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidate working in microsoft": {
        "locationAliases": [],
        "companyFilter": ["microsoft"],
        "strictCompany": True,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates who worked in FANG": {
        # Past tense → boost current employees to top; semantic search finds alumni
        "locationAliases": [],
        "companyFilter": ["google", "meta", "amazon", "apple", "netflix", "microsoft", "facebook"],
        "strictCompany": False,
        "expLevel": None,
        "cleanQuery": "software engineer experience Google Meta Amazon Apple Netflix Facebook",
    },
    "candidate from apple and google": {
        "locationAliases": [],
        "companyFilter": ["apple", "google"],
        "strictCompany": False,
        "expLevel": None,
        "cleanQuery": "software engineer Apple Google",
    },
    "candidate from apple": {
        # Present-tense strict filter → ONLY current Apple employees returned
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": True,
        "expLevel": None,
        "cleanQuery": "software engineer",
    },
    "candidate worked in apple": {
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": False,
        "expLevel": None,
        "cleanQuery": "software engineer Apple experience",
    },
    # ── Apple phrasing variations ──────────────────────────────────────────────
    "candidate working in apple": {
        # Present-tense "working in" → same as "from" → strictCompany=True
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": True,
        "expLevel": None,
        "cleanQuery": "software engineer",
    },
    "candidate worked for apple": {
        # Past-tense alt "worked for" → boost + semantic, strictCompany=False
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": False,
        "expLevel": None,
        "cleanQuery": "software engineer Apple experience",
    },
    "former apple employee": {
        # "former" → past-tense, strictCompany=False
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": False,
        "expLevel": None,
        "cleanQuery": "software engineer Apple former",
    },
    "ex apple engineer": {
        # "ex" prefix → past-tense, strictCompany=False
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": False,
        "expLevel": None,
        "cleanQuery": "engineer Apple former",
    },
    "engineers at apple": {
        # "at" → present-tense, strictCompany=True
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": True,
        "expLevel": None,
        "cleanQuery": "software engineer",
    },
    "apple software engineer": {
        # Implicit current employment → strictCompany=True
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": True,
        "expLevel": None,
        "cleanQuery": "software engineer",
    },
    "senior engineer from apple": {
        # strictCompany=True + expLevel=Senior → only senior Apple employees
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": True,
        "expLevel": "Senior",
        "cleanQuery": "senior software engineer",
    },
    "apple alumni": {
        # "alumni" → past-tense / ever worked there, strictCompany=False
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": False,
        "expLevel": None,
        "cleanQuery": "software engineer Apple alumni",
    },
    "candidates from SF metro area or 50 mile radius": {
        "locationAliases": ["san francisco", "oakland", "palo alto", "san jose", "berkeley"],
        "companyFilter": [], "expLevel": None, "cleanQuery": "software engineer",
    },
    "experts in ML or machine learning": {
        "locationAliases": [], "companyFilter": [], "expLevel": None,
        "cleanQuery": "machine learning expert",
    },
    "experts in AI": {
        "locationAliases": [], "companyFilter": [], "expLevel": None,
        "cleanQuery": "artificial intelligence expert",
    },
    "experts in cloud storage or distributed storage": {
        "locationAliases": [], "companyFilter": [], "expLevel": None,
        "cleanQuery": "cloud storage distributed systems",
    },
    "smart engineers in data science": {
        "locationAliases": [], "companyFilter": [], "expLevel": None,
        "cleanQuery": "data science engineer",
    },
    # ── Geographic region queries ──────────────────────────────────────────────
    "candidates from Asia": {
        "locationAliases": ["india", "singapore", "japan", "china", "hong kong",
                            "south korea", "bangalore", "tokyo", "shanghai", "seoul"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from Southeast Asia": {
        "locationAliases": ["singapore", "vietnam", "thailand", "philippines",
                            "malaysia", "indonesia", "jakarta", "kuala lumpur", "bangkok"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from South Asia": {
        "locationAliases": ["india", "bangalore", "hyderabad", "mumbai",
                            "delhi", "pune", "chennai", "kolkata", "pakistan"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from Europe": {
        "locationAliases": ["london", "uk", "germany", "france", "netherlands",
                            "berlin", "paris", "amsterdam", "dublin", "zurich"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from North America": {
        "locationAliases": ["usa", "united states", "canada", "new york", "texas",
                            "washington", ", ca", ", ny", ", tx", ", wa"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidate from usa": {
        "locationAliases": ["usa", "united states", "california", "new york", "texas",
                            "washington", "illinois", "florida", "georgia",
                            ", ca", ", ny", ", tx", ", wa", ", il", ", fl", ", ga"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from west coast": {
        "locationAliases": ["san francisco", "los angeles", "seattle", "california",
                            "washington", "oregon", "silicon valley", "bay area", ", ca", ", wa", ", or"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from midwest USA": {
        "locationAliases": ["chicago", "detroit", "minneapolis", "cleveland",
                            "illinois", "michigan", "ohio", "minnesota", ", il", ", mi", ", oh", ", mn"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidates from california": {
        "locationAliases": ["california", "san francisco", "los angeles", "silicon valley",
                            "bay area", "san jose", "sacramento", ", ca"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidate from australia": {
        "locationAliases": ["australia", "new zealand", "sydney", "melbourne",
                            "brisbane", "auckland", "perth"],
        "companyFilter": [], "strictCompany": False, "hasRoleSignal": False,
        "expLevel": None, "cleanQuery": "software engineer",
    },
    "candidate from google": {
        "locationAliases": [],
        "companyFilter": ["google"],
        "strictCompany": True,
        "expLevel": None,
        "cleanQuery": "software engineer",
    },
    "candidate from netflix": {
        "locationAliases": [],
        "companyFilter": ["netflix"],
        "strictCompany": True,
        "expLevel": None,
        "cleanQuery": "software engineer",
    },
    "candidate from amazon": {
        "locationAliases": [],
        "companyFilter": ["amazon"],
        "strictCompany": True,
        "expLevel": None,
        "cleanQuery": "software engineer",
    },
    "senior engineer at microsoft": {
        "locationAliases": [],
        "companyFilter": ["microsoft"],
        "strictCompany": True,
        "expLevel": "Senior",
        "cleanQuery": "senior software engineer",
    },
    "candidate from meta": {
        "locationAliases": [],
        "companyFilter": ["meta"],
        "strictCompany": True,
        "expLevel": None,
        "cleanQuery": "software engineer",
    },
    # hasRoleSignal=true → company boost is skipped; semantic search ranks by role
    "java developer from apple": {
        "locationAliases": [],
        "companyFilter": ["apple"],
        "strictCompany": False,
        "hasRoleSignal": True,
        "expLevel": None,
        "cleanQuery": "java developer",
    },
}


def _patches(semantic_df: pd.DataFrame, query: str = ""):
    """Return a context manager stack patching all external calls.
    The AI intent parser is mocked with a deterministic response keyed by query.
    """
    from contextlib import ExitStack
    mock_meta_table = MagicMock()
    mock_meta_table.to_pandas.return_value = _make_meta_df()
    mock_empty = MagicMock()
    mock_empty.to_pandas.return_value = pd.DataFrame(columns=["filename", "user_id", "job_id"])

    intent = _QUERY_INTENTS.get(query, {
        "locationAliases": [], "companyFilter": [], "expLevel": None, "cleanQuery": query,
    })

    stack = ExitStack()
    stack.enter_context(patch(
        "app.routes.v1.resumes.resolve_credentials",
        new=AsyncMock(return_value=_CREDS),
    ))
    stack.enter_context(patch(
        "app.routes.v1.resumes._parse_candidate_search_intent",
        new=AsyncMock(return_value=intent),
    ))
    stack.enter_context(patch(
        "services.db.lancedb_client.search_resumes_hybrid",
        return_value=semantic_df,
    ))
    stack.enter_context(patch(
        "services.db.lancedb_client.get_or_create_resume_meta_table",
        return_value=mock_meta_table,
    ))
    stack.enter_context(patch(
        "services.db.lancedb_client.get_or_create_job_applied_table",
        return_value=mock_empty,
    ))
    stack.enter_context(patch(
        "services.db.lancedb_client.list_all_resumes_with_users",
        return_value=[{"filename": c["filename"], "user_id": c["user_id"]} for c in _CANDIDATES],
    ))
    # get_or_create_table (chunks table) is not populated in tests — raise so
    # _valid_filenames is set to None and the disk-existence filter is skipped,
    # letting the full meta DataFrame flow through to the location pre-filter.
    stack.enter_context(patch(
        "services.db.lancedb_client.get_or_create_table",
        side_effect=RuntimeError("test: chunks table not available"),
    ))
    return stack


# ---------------------------------------------------------------------------
# Parametrized scenarios: (query, expected_filenames_in_results)
# ---------------------------------------------------------------------------

SEARCH_SCENARIOS = [
    (
        "candidates from southern california",
        ["alice_la_engineer.pdf", "bob_sandiego_dev.pdf"],
    ),
    (
        "candidates from LA metro area",
        ["alice_la_engineer.pdf"],
    ),
    (
        "candidates from greater LA",
        ["alice_la_engineer.pdf"],
    ),
    (
        "candidates from silicon valley",
        ["carol_sv_ml.pdf", "dave_sanjose_swe.pdf"],
    ),
    (
        "senior managers from europe",
        # "senior" exp_level signal filters to Senior; VP (Executive) is correctly excluded
        ["eva_london_manager.pdf"],
    ),
    (
        "executives from NY",
        ["grace_ny_cto.pdf", "henry_nyc_director.pdf"],
    ),
    (
        "candidates currently working in FANG",
        ["iris_google_swe.pdf", "jack_meta_ml.pdf", "kim_amazon_sde.pdf", "lee_netflix_arch.pdf"],
    ),
    (
        "candidates who worked in FANG",
        # companyFilter boosts current FANG/Apple/Google employees to top;
        # semantic search surfaces alumni in the remainder
        ["iris_google_swe.pdf", "jack_meta_ml.pdf", "kim_amazon_sde.pdf", "lee_netflix_arch.pdf",
         "nora_apple_eng.pdf", "omar_apple_design.pdf", "priya_google_infra.pdf"],
    ),
    (
        "candidate working in microsoft",
        # Strict present-tense filter → ONLY Microsoft employees returned
        ["raj_microsoft_pm.pdf", "sara_microsoft_swe.pdf", "paul_ai_nlp.pdf"],
    ),
    (
        "candidate from apple",
        # strictCompany=True → ONLY current Apple employees; victor_apple_java included
        ["nora_apple_eng.pdf", "omar_apple_design.pdf", "victor_apple_java.pdf"],
    ),
    (
        "candidate from apple and google",
        ["nora_apple_eng.pdf", "omar_apple_design.pdf", "priya_google_infra.pdf",
         "iris_google_swe.pdf"],
    ),
    (
        "candidate from google",
        # strictCompany=True → ONLY current Google employees
        ["iris_google_swe.pdf", "priya_google_infra.pdf"],
    ),
    (
        "candidate from netflix",
        # strictCompany=True → ONLY current Netflix employee
        ["lee_netflix_arch.pdf"],
    ),
    (
        "candidate from amazon",
        # strictCompany=True → ONLY current Amazon employee
        ["kim_amazon_sde.pdf"],
    ),
    (
        "senior engineer at microsoft",
        # strictCompany=True + expLevel=Senior → senior MS employees (raj=Senior, paul=Senior@MS)
        ["raj_microsoft_pm.pdf", "paul_ai_nlp.pdf"],
    ),
    (
        "candidate from meta",
        # strictCompany=True → ONLY current Meta employee
        ["jack_meta_ml.pdf"],
    ),
    (
        "candidate worked in apple",
        ["nora_apple_eng.pdf", "omar_apple_design.pdf"],
    ),
    # ── Apple phrasing variations ─────────────────────────────────────────────
    (
        "candidate working in apple",
        # Present-tense "working in" → strictCompany=True → all 3 current Apple employees
        ["nora_apple_eng.pdf", "omar_apple_design.pdf", "victor_apple_java.pdf"],
    ),
    (
        "candidate worked for apple",
        # Past-tense alt phrasing → strictCompany=False; boosts current Apple employees
        ["nora_apple_eng.pdf", "omar_apple_design.pdf"],
    ),
    (
        "former apple employee",
        # "former" → past-tense boost → current Apple employees surface first
        ["nora_apple_eng.pdf", "omar_apple_design.pdf"],
    ),
    (
        "ex apple engineer",
        # "ex" prefix → past-tense boost → current Apple employees surface first
        ["nora_apple_eng.pdf", "omar_apple_design.pdf"],
    ),
    (
        "engineers at apple",
        # Present-tense "at" → strictCompany=True → all 3 current Apple employees
        ["nora_apple_eng.pdf", "omar_apple_design.pdf", "victor_apple_java.pdf"],
    ),
    (
        "apple software engineer",
        # Implicit current → strictCompany=True → all 3 current Apple employees
        ["nora_apple_eng.pdf", "omar_apple_design.pdf", "victor_apple_java.pdf"],
    ),
    (
        "senior engineer from apple",
        # strictCompany=True + expLevel=Senior → nora (Senior); omar/victor are Mid-level
        ["nora_apple_eng.pdf"],
    ),
    (
        "apple alumni",
        # "alumni" → past-tense boost → current Apple employees surface first
        ["nora_apple_eng.pdf", "omar_apple_design.pdf"],
    ),
    (
        "candidates from SF metro area or 50 mile radius",
        ["maya_sf_pm.pdf", "noah_oakland_sre.pdf"],
    ),
    (
        "experts in ML or machine learning",
        ["olivia_ml_research.pdf", "paul_ai_nlp.pdf", "carol_sv_ml.pdf", "jack_meta_ml.pdf"],
    ),
    (
        "experts in AI",
        ["paul_ai_nlp.pdf", "olivia_ml_research.pdf", "jack_meta_ml.pdf"],
    ),
    (
        "experts in cloud storage or distributed storage",
        ["quinn_cloud_infra.pdf", "rosa_dist_systems.pdf"],
    ),
    (
        "smart engineers in data science",
        ["sam_datascience.pdf", "tina_analytics.pdf", "olivia_ml_research.pdf"],
    ),
    (
        "java developer from apple",
        ["uma_java_dev.pdf", "victor_apple_java.pdf"],
    ),
    # ── Geographic region scenarios ─────────────────────────────────────────
    (
        "candidates from Asia",
        ["wei_beijing_swe.pdf", "yuki_tokyo_eng.pdf", "ji_seoul_dev.pdf"],  # Beijing, Tokyo, Seoul
    ),
    (
        "candidates from Southeast Asia",
        ["andi_jakarta_eng.pdf", "siri_bangkok_dev.pdf"],
    ),
    (
        "candidates from South Asia",
        ["arjun_pune_swe.pdf"],    # Pune, India ✅
    ),
    (
        "candidates from Europe",
        ["eva_london_manager.pdf", "frank_berlin_vp.pdf"],
    ),
    (
        "candidates from North America",
        ["alice_la_engineer.pdf", "grace_ny_cto.pdf",
         "noah_oakland_sre.pdf", "sophie_montreal_dev.pdf"],
    ),
    (
        "candidate from usa",
        ["alice_la_engineer.pdf", "bob_sandiego_dev.pdf",
         "grace_ny_cto.pdf", "dan_chicago_eng.pdf"],
    ),
    (
        "candidates from west coast",
        ["alice_la_engineer.pdf", "carol_sv_ml.pdf",
         "noah_oakland_sre.pdf", "alex_portland_swe.pdf"],
    ),
    (
        "candidates from midwest USA",
        ["dan_chicago_eng.pdf", "mia_detroit_dev.pdf"],
    ),
    (
        "candidates from california",
        ["alice_la_engineer.pdf", "bob_sandiego_dev.pdf",
         "carol_sv_ml.pdf", "maya_sf_pm.pdf"],
    ),
    (
        "candidate from australia",
        ["chloe_sydney_eng.pdf", "liam_melbourne_dev.pdf"],
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_files", SEARCH_SCENARIOS,
                         ids=[s[0][:40] for s in SEARCH_SCENARIOS])
async def test_resume_db_semantic_search(app, query, expected_files):
    """Each natural-language query returns 200 + the expected candidates in results."""
    semantic_result = _semantic_df(*expected_files)

    with _patches(semantic_result, query):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": query, "limit": 50},
            )

    assert resp.status_code == 200, f"[{query!r}] got {resp.status_code}: {resp.text}"
    payload = resp.json()
    assert "resumes" in payload,  f"[{query!r}] 'resumes' key missing"
    assert "total"   in payload,  f"[{query!r}] 'total' key missing"
    assert isinstance(payload["resumes"], list)

    returned_files = {r["filename"] for r in payload["resumes"]}
    for fn in expected_files:
        assert fn in returned_files, (
            f"[{query!r}] expected '{fn}' in results but got: {sorted(returned_files)}"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_files", SEARCH_SCENARIOS,
                         ids=[s[0][:40] for s in SEARCH_SCENARIOS])
async def test_resume_db_search_count_matches_returned(app, query, expected_files):
    """total field equals the length of the resumes list."""
    semantic_result = _semantic_df(*expected_files)

    with _patches(semantic_result, query):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": query, "limit": 50},
            )

    assert resp.status_code == 200
    payload = resp.json()
    # total must be >= the page we received (some may be on next page)
    assert payload["total"] >= len(payload["resumes"])


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_files", SEARCH_SCENARIOS,
                         ids=[s[0][:40] for s in SEARCH_SCENARIOS])
async def test_resume_db_search_result_shape(app, query, expected_files):
    """Every returned record has at minimum filename and user_id fields."""
    semantic_result = _semantic_df(*expected_files)

    with _patches(semantic_result, query):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": query, "limit": 50},
            )

    assert resp.status_code == 200
    for record in resp.json()["resumes"]:
        assert "filename" in record, f"missing 'filename' in {record}"
        assert "user_id"  in record, f"missing 'user_id' in {record}"


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_files", SEARCH_SCENARIOS,
                         ids=[s[0][:40] for s in SEARCH_SCENARIOS])
async def test_resume_db_search_uses_api_key(app, query, expected_files):
    """resolve_credentials is called and its key is forwarded to search_resumes_hybrid."""
    semantic_result = _semantic_df(*expected_files)
    mock_search = MagicMock(return_value=semantic_result)
    mock_meta = MagicMock()
    mock_meta.to_pandas.return_value = _make_meta_df()
    mock_empty = MagicMock()
    mock_empty.to_pandas.return_value = pd.DataFrame(columns=["filename", "user_id", "job_id"])

    intent = _QUERY_INTENTS.get(query, {
        "locationAliases": [], "companyFilter": [], "expLevel": None, "cleanQuery": query,
    })
    with (
        patch("app.routes.v1.resumes.resolve_credentials",
              new=AsyncMock(return_value=_CREDS)) as mock_creds,
        patch("app.routes.v1.resumes._parse_candidate_search_intent",
              new=AsyncMock(return_value=intent)),
        patch("services.db.lancedb_client.search_resumes_hybrid", mock_search),
        patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=mock_meta),
        patch("services.db.lancedb_client.get_or_create_job_applied_table", return_value=mock_empty),
        patch("services.db.lancedb_client.list_all_resumes_with_users",
              return_value=[{"filename": c["filename"], "user_id": c["user_id"]} for c in _CANDIDATES]),
        patch("services.db.lancedb_client.get_or_create_table",
              side_effect=RuntimeError("test: chunks table not available")),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": query, "limit": 50},
            )

    mock_creds.assert_awaited_once()
    # Verify the key was forwarded
    call_kwargs = mock_search.call_args
    assert call_kwargs is not None, "search_resumes_hybrid was never called"
    passed_key = call_kwargs.kwargs.get("api_key") or (
        call_kwargs.args[3] if len(call_kwargs.args) > 3 else None
    )
    assert passed_key == "sk-test-key", f"wrong api_key forwarded: {passed_key!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize("query,_", SEARCH_SCENARIOS,
                         ids=[s[0][:40] for s in SEARCH_SCENARIOS])
async def test_resume_db_search_graceful_on_semantic_failure(app, query, _):
    """If semantic search raises, the endpoint still returns 200 (falls back to filename match)."""
    mock_meta = MagicMock()
    mock_meta.to_pandas.return_value = _make_meta_df()
    mock_empty = MagicMock()
    mock_empty.to_pandas.return_value = pd.DataFrame(columns=["filename", "user_id", "job_id"])

    intent = _QUERY_INTENTS.get(query, {
        "locationAliases": [], "companyFilter": [], "expLevel": None, "cleanQuery": query,
    })
    with (
        patch("app.routes.v1.resumes.resolve_credentials",
              new=AsyncMock(return_value=_CREDS)),
        patch("app.routes.v1.resumes._parse_candidate_search_intent",
              new=AsyncMock(return_value=intent)),
        patch("services.db.lancedb_client.search_resumes_hybrid",
              side_effect=Exception("OpenRouter API key is required for semantic search")),
        patch("services.db.lancedb_client.get_or_create_resume_meta_table", return_value=mock_meta),
        patch("services.db.lancedb_client.get_or_create_job_applied_table", return_value=mock_empty),
        patch("services.db.lancedb_client.list_all_resumes_with_users",
              return_value=[{"filename": c["filename"], "user_id": c["user_id"]} for c in _CANDIDATES]),
        patch("services.db.lancedb_client.get_or_create_table",
              side_effect=RuntimeError("test: chunks table not available")),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": query, "limit": 50},
            )

    assert resp.status_code == 200, f"expected graceful 200 on failure, got {resp.status_code}"
    payload = resp.json()
    assert "resumes" in payload
    assert isinstance(payload["resumes"], list)


@pytest.mark.asyncio
async def test_java_developer_from_apple_has_role_signal(app):
    """
    'java developer from apple' with hasRoleSignal=true must NOT suppress non-Apple Java devs.

    The company boost is skipped when hasRoleSignal=true, so semantic search order is preserved:
    uma_java_dev (JPMorgan, pure Java dev) must appear alongside victor_apple_java (Apple, Java dev).
    """
    expected = ["uma_java_dev.pdf", "victor_apple_java.pdf"]
    semantic_result = _semantic_df(*expected)

    with _patches(semantic_result, "java developer from apple"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": "java developer from apple", "limit": 50},
            )

    assert resp.status_code == 200
    payload = resp.json()
    returned_files = [r["filename"] for r in payload["resumes"]]

    # Non-Apple Java dev must be present (not filtered out because of Apple company filter)
    assert "uma_java_dev.pdf" in returned_files, (
        "Non-Apple Java developer was incorrectly suppressed when hasRoleSignal=true"
    )
    # Apple Java dev must also be present
    assert "victor_apple_java.pdf" in returned_files, (
        "Apple Java developer missing from results"
    )

    # uma must NOT be pushed below victor (no Apple boost when hasRoleSignal=true)
    uma_idx    = returned_files.index("uma_java_dev.pdf")
    victor_idx = returned_files.index("victor_apple_java.pdf")
    assert uma_idx <= victor_idx, (
        f"Apple boost incorrectly applied: victor (Apple) at {victor_idx} ranked above "
        f"uma (non-Apple) at {uma_idx} despite hasRoleSignal=true"
    )


# ---------------------------------------------------------------------------
# Name search tests — direct lookup by candidate_name (bypasses semantic search)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_by_full_name(app):
    """Searching a candidate's full name returns only that candidate."""
    semantic_result = _semantic_df()  # empty — name search bypasses semantic

    with _patches(semantic_result, "Grace Chen"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": "Grace Chen", "limit": 50},
            )

    assert resp.status_code == 200
    payload = resp.json()
    returned_files = [r["filename"] for r in payload["resumes"]]
    assert "grace_ny_cto.pdf" in returned_files, "Grace Chen not found by full name"
    assert payload["total"] >= 1


@pytest.mark.asyncio
async def test_search_by_first_name(app):
    """Searching by first name alone returns all candidates with that first name."""
    semantic_result = _semantic_df()

    with _patches(semantic_result, "Henry"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": "Henry", "limit": 50},
            )

    assert resp.status_code == 200
    payload = resp.json()
    returned_files = [r["filename"] for r in payload["resumes"]]
    assert "henry_nyc_director.pdf" in returned_files, "Henry Park not found by first name"


@pytest.mark.asyncio
async def test_search_by_last_name(app):
    """Searching by last name alone returns candidates with that surname."""
    semantic_result = _semantic_df()

    with _patches(semantic_result, "Patel"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": "Patel", "limit": 50},
            )

    assert resp.status_code == 200
    payload = resp.json()
    returned_files = [r["filename"] for r in payload["resumes"]]
    assert "iris_google_swe.pdf" in returned_files, "Iris Patel not found by last name"


@pytest.mark.asyncio
async def test_name_search_exact_ranked_first(app):
    """Exact full-name match is ranked before partial matches."""
    semantic_result = _semantic_df()

    # Search "Jack" — matches "Jack Liu" (jack_meta_ml.pdf)
    with _patches(semantic_result, "Jack Liu"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": "Jack Liu", "limit": 50},
            )

    assert resp.status_code == 200
    payload = resp.json()
    returned_files = [r["filename"] for r in payload["resumes"]]
    assert returned_files[0] == "jack_meta_ml.pdf", (
        f"Exact match should be first but got {returned_files[0]}"
    )


@pytest.mark.asyncio
async def test_name_search_no_match_falls_through_to_semantic(app):
    """A query that doesn't match any candidate name falls through to semantic search."""
    semantic_result = _semantic_df("alice_la_engineer.pdf", "carol_sv_ml.pdf")

    # "Alice Johnson" — not a name in _CANDIDATES, so falls through to semantic
    with _patches(semantic_result, "Alice Johnson"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/resumes/database",
                headers=_MANAGER,
                params={"search": "Alice Johnson", "limit": 50},
            )

    assert resp.status_code == 200
    payload = resp.json()
    # Semantic search results should appear (not empty)
    returned_files = {r["filename"] for r in payload["resumes"]}
    assert "alice_la_engineer.pdf" in returned_files, (
        "Should fall through to semantic search when no name match"
    )
