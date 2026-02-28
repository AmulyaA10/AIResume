"""Shared test fixtures for unit and integration tests."""

import os
import sys
import io
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure project root is on sys.path so backend & services imports work
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_backend_root = os.path.join(_project_root, "backend")
for p in (_project_root, _backend_root):
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Stub out optional heavy dependencies that may not be installed in test env
# ---------------------------------------------------------------------------
for _mod_name in (
    "selenium",
    "selenium.webdriver",
    "selenium.webdriver.chrome",
    "selenium.webdriver.chrome.options",
    "selenium.webdriver.chrome.service",
    "selenium.webdriver.common",
    "selenium.webdriver.common.by",
    "selenium.webdriver.common.keys",
    "selenium.webdriver.support",
    "selenium.webdriver.support.ui",
    "selenium.webdriver.support.expected_conditions",
    "webdriver_manager",
    "webdriver_manager.chrome",
    "google",
    "google.generativeai",
):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()


# ---------------------------------------------------------------------------
# Pytest-asyncio configuration
# ---------------------------------------------------------------------------
def pytest_collection_modifyitems(config, items):
    """Auto-mark async test functions with pytest.mark.asyncio."""
    for item in items:
        if item.get_closest_marker("asyncio") is None and "async" in str(type(item.obj)):
            item.add_marker(pytest.mark.asyncio)


# ---------------------------------------------------------------------------
# Mock fixtures — prevents real DB / LLM calls during tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_dashboard_stats():
    """Realistic dashboard stats response."""
    return {
        "total_resumes": 5,
        "auto_screened": 3,
        "high_matches": 2,
        "skill_gaps": 1,
        "quality_scored": 4,
        "recent_activity": [
            {
                "type": "screen",
                "filename": "john_doe_resume.pdf",
                "score": 82,
                "decision": "SELECTED",
                "timestamp": "2026-02-20T10:30:00",
            }
        ],
    }


@pytest.fixture()
def mock_quality_output():
    """Realistic quality scoring pipeline output."""
    return {
        "score": {"overall": 78, "formatting": 85, "content": 70, "keywords": 80},
        "feedback": "Good resume overall, consider adding more quantified achievements.",
    }


@pytest.fixture()
def mock_gap_output():
    """Realistic skill-gap pipeline output."""
    return {
        "match_score": 65,
        "missing_skills": ["Kubernetes", "GraphQL"],
        "matching_skills": ["Python", "FastAPI", "React"],
        "recommendations": "Add cloud orchestration experience.",
    }


@pytest.fixture()
def mock_screen_output():
    """Realistic screening pipeline output."""
    return {
        "score": {"overall": 80},
        "decision": {"selected": True, "reason": "Strong match for required skills."},
    }


@pytest.fixture()
def mock_search_results():
    """Realistic search results from LanceDB."""
    import pandas as pd

    return pd.DataFrame(
        {
            "filename": ["resume_a.pdf", "resume_b.pdf"],
            "text": [
                "Experienced Python developer with 5 years in FastAPI and Django.",
                "Senior full-stack engineer specializing in React and Node.js.",
            ],
            "user_id": ["user_alex_chen_123", "user_alex_chen_123"],
        }
    )


@pytest.fixture()
def mock_validation_result():
    """Realistic resume validation result."""
    return {
        "classification": "resume_valid_good",
        "total_score": 22,
        "scores": {
            "completeness": 4,
            "structure_readability": 4,
            "achievement_quality": 3,
            "credibility_consistency": 4,
            "ats_friendliness": 4,
            "overall_impression": 3,
        },
        "issues": ["No LinkedIn URL provided"],
        "improvements": ["Add more quantified achievements", "Include GitHub link"],
        "missing_fields": [],
        "verification_questions": [],
    }


@pytest.fixture()
def mock_generate_output():
    """Realistic resume generation output."""
    return {
        "resume": {
            "contact": {"name": "Test User", "email": "test@example.com", "phone": "555-0100"},
            "summary": "Experienced software engineer with 5+ years in full-stack development.",
            "skills": ["Python", "React", "FastAPI", "PostgreSQL"],
            "experience": [
                {
                    "title": "Software Engineer",
                    "company": "Tech Corp",
                    "period": "2021-Present",
                    "bullets": ["Designed and built microservices architecture"],
                }
            ],
            "education": [{"degree": "BS Computer Science", "school": "MIT", "year": "2020"}],
        }
    }


@pytest.fixture()
def mock_linkedin_output():
    """Realistic LinkedIn scrape output."""
    return {
        "resume": {
            "contact": {"name": "Jane Doe", "email": "jane@linkedin.com"},
            "summary": "Senior recruiter with expertise in tech hiring.",
            "experience": [
                {
                    "title": "Technical Recruiter",
                    "company": "BigTech Inc",
                    "period": "2019-Present",
                    "bullets": ["Hired 200+ engineers"],
                }
            ],
            "education": [{"degree": "MBA", "school": "Stanford", "year": "2018"}],
        }
    }


@pytest.fixture()
def mock_linkedin_security_challenge():
    """LinkedIn scrape output when security challenge / 2FA was detected."""
    return {
        "resume": None,
        "error": "LinkedIn security verification timed out after 30 seconds. "
                 "Please log into LinkedIn manually in a regular browser first, "
                 "approve any security checks, then retry the scrape.",
        "error_code": "SECURITY_CHALLENGE",
    }


@pytest.fixture()
def mock_linkedin_generic_error():
    """LinkedIn scrape output for a generic (non-security) error."""
    return {
        "resume": None,
        "error": "Scraped content does not appear to contain LinkedIn profile sections.",
        "error_code": None,
    }


@pytest.fixture()
def sample_resume_text():
    """Sample resume text for testing."""
    return """
    JOHN DOE
    Senior Software Engineer
    john.doe@email.com | (555) 123-4567 | San Francisco, CA

    PROFESSIONAL SUMMARY
    Passionate software engineer with 7+ years of experience in full-stack development.
    Proficient in Python, TypeScript, React, and cloud-native architectures.

    EXPERIENCE
    Senior Software Engineer | Tech Innovations Inc. | 2021 - Present
    - Led migration of monolithic application to microservices, reducing deploy time by 60%
    - Designed real-time data pipeline processing 2M+ events daily using Apache Kafka
    - Mentored team of 5 junior developers, improving code review turnaround by 40%

    Software Engineer | StartupCo | 2018 - 2021
    - Built customer-facing dashboard with React and D3.js serving 50K+ monthly users
    - Implemented CI/CD pipeline reducing release cycle from 2 weeks to daily deploys

    EDUCATION
    B.S. Computer Science | University of California, Berkeley | 2018

    SKILLS
    Python, TypeScript, React, Node.js, FastAPI, PostgreSQL, Docker, Kubernetes, AWS
    """


@pytest.fixture()
def sample_jd_text():
    """Sample job description for testing."""
    return """
    Senior Full-Stack Engineer

    We are looking for a Senior Full-Stack Engineer to join our platform team.

    Requirements:
    - 5+ years of experience in software development
    - Strong proficiency in Python and TypeScript
    - Experience with React and modern frontend frameworks
    - Familiarity with cloud platforms (AWS/GCP)
    - Experience with containerization (Docker, Kubernetes)
    - Strong communication skills

    Nice to have:
    - GraphQL experience
    - Machine learning knowledge
    - Open source contributions
    """


# ---------------------------------------------------------------------------
# App / client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Create a fresh FastAPI app instance for testing."""
    from app import create_app

    return create_app()


@pytest.fixture()
def auth_headers():
    """Default auth headers for authenticated requests."""
    return {"Authorization": "Bearer mock-token-123"}


@pytest.fixture()
def recruiter_auth_headers():
    """Recruiter auth headers."""
    return {"Authorization": "Bearer mock-recruiter-token-123"}


# ---------------------------------------------------------------------------
# Resume validation pre-check fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_not_resume_validation():
    """Validation result for non-resume text (e.g. a grocery list)."""
    return {
        "is_resume": False,
        "classification": "not_resume",
        "total_score": 2,
        "scores": {
            "document_type_validity": 0,
            "completeness": 0,
            "structure_readability": 1,
            "achievement_quality": 0,
            "credibility_consistency": 0,
            "ats_friendliness": 1,
        },
        "missing_fields": ["name", "email", "experience", "education"],
        "top_issues": ["This text does not appear to be a resume"],
        "suggested_improvements": [],
        "followup_verification_questions": [],
        "summary": "The submitted text is not a resume.",
    }


@pytest.fixture()
def mock_weak_resume_validation():
    """Validation result for a weak but valid resume."""
    return {
        "is_resume": True,
        "classification": "resume_valid_but_weak",
        "total_score": 14,
        "scores": {
            "document_type_validity": 3,
            "completeness": 2,
            "structure_readability": 2,
            "achievement_quality": 2,
            "credibility_consistency": 3,
            "ats_friendliness": 2,
        },
        "missing_fields": ["phone"],
        "top_issues": ["Missing quantified achievements", "Weak formatting"],
        "suggested_improvements": ["Add metrics to bullet points"],
        "followup_verification_questions": [],
        "summary": "Resume is present but needs significant improvement.",
    }


@pytest.fixture()
def mock_good_resume_validation():
    """Validation result for a good resume (no warning needed)."""
    return {
        "is_resume": True,
        "classification": "resume_valid_good",
        "total_score": 22,
        "scores": {
            "document_type_validity": 4,
            "completeness": 4,
            "structure_readability": 3,
            "achievement_quality": 4,
            "credibility_consistency": 4,
            "ats_friendliness": 3,
        },
        "missing_fields": [],
        "top_issues": [],
        "suggested_improvements": ["Consider adding LinkedIn URL"],
        "followup_verification_questions": [],
        "summary": "Solid resume with minor improvements possible.",
    }
