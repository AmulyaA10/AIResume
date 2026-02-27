"""Unit tests for the resume validation pre-check helper."""

import pytest
from unittest.mock import patch
from fastapi import HTTPException


def test_precheck_blocks_not_resume(mock_not_resume_validation):
    """precheck_resume_validation raises 422 for not_resume classification."""
    with patch("app.common.validation.run_resume_validation", return_value=mock_not_resume_validation):
        from app.common.validation import precheck_resume_validation

        with pytest.raises(HTTPException) as exc_info:
            precheck_resume_validation("Buy milk, eggs, bread, butter", llm_config={})

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error"] == "not_a_resume"
        assert exc_info.value.detail["validation"]["classification"] == "not_resume"


def test_precheck_warns_weak_resume(mock_weak_resume_validation):
    """precheck_resume_validation returns warning dict for weak resumes."""
    with patch("app.common.validation.run_resume_validation", return_value=mock_weak_resume_validation):
        from app.common.validation import precheck_resume_validation

        result = precheck_resume_validation("John Doe, email@test.com, some experience", llm_config={})

        assert result is not None
        assert result["classification"] == "resume_valid_but_weak"
        assert result["total_score"] == 14


def test_precheck_passes_good_resume(mock_good_resume_validation):
    """precheck_resume_validation returns None for good/strong resumes."""
    with patch("app.common.validation.run_resume_validation", return_value=mock_good_resume_validation):
        from app.common.validation import precheck_resume_validation

        result = precheck_resume_validation("Complete professional resume text", llm_config={})

        assert result is None


def test_precheck_skips_on_validation_error():
    """precheck_resume_validation returns None if validation itself errored."""
    errored_validation = {
        "is_resume": False,
        "classification": "not_resume",
        "total_score": 0,
        "scores": {},
        "error": "LLM API call failed: timeout",
        "summary": "Validation failed due to an error.",
    }
    with patch("app.common.validation.run_resume_validation", return_value=errored_validation):
        from app.common.validation import precheck_resume_validation

        # Should NOT raise even though classification is not_resume,
        # because the error field indicates infrastructure failure
        result = precheck_resume_validation("any text", llm_config={})

        assert result is None


def test_precheck_warns_invalid_incomplete():
    """precheck_resume_validation returns warning for invalid/incomplete resumes."""
    invalid_validation = {
        "is_resume": True,
        "classification": "resume_invalid_or_incomplete",
        "total_score": 8,
        "scores": {
            "document_type_validity": 2,
            "completeness": 1,
            "structure_readability": 1,
            "achievement_quality": 1,
            "credibility_consistency": 2,
            "ats_friendliness": 1,
        },
        "missing_fields": ["email", "education", "skills"],
        "top_issues": ["Major sections missing"],
        "suggested_improvements": [],
        "summary": "Resume is incomplete.",
    }
    with patch("app.common.validation.run_resume_validation", return_value=invalid_validation):
        from app.common.validation import precheck_resume_validation

        result = precheck_resume_validation("very short resume", llm_config={})

        assert result is not None
        assert result["classification"] == "resume_invalid_or_incomplete"
