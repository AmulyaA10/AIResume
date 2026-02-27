"""Unit tests for the LinkedIn scrape endpoint and credential resolution."""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from cryptography.fernet import Fernet


_TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def set_encryption_key():
    """Set a valid ENCRYPTION_KEY for all tests in this module."""
    with patch.dict(os.environ, {"ENCRYPTION_KEY": _TEST_KEY}):
        import app.common.encryption as enc_mod
        enc_mod._ENCRYPTION_KEY = _TEST_KEY
        yield
        enc_mod._ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")


# ── Endpoint tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_linkedin_scrape(app, mock_linkedin_output):
    """POST /api/v1/linkedin/scrape returns structured resume."""
    with patch(
        "app.routes.v1.linkedin.generate_resume_from_linkedin",
        return_value=mock_linkedin_output,
    ), patch(
        "app.routes.v1.linkedin.resolve_credentials",
        return_value={
            "openrouter_key": "test-key",
            "llm_model": None,
            "linkedin_user": "test@test.com",
            "linkedin_pass": "test-pass",
        },
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/linkedin/scrape",
                json={"query": "https://www.linkedin.com/in/janedoe"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "resume" in data
    assert data["resume"]["contact"]["name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_linkedin_scrape_missing_query(app):
    """LinkedIn scrape requires query field."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/linkedin/scrape", json={})
    assert resp.status_code == 422


# ── _resolve_credentials_sync tests ─────────────────────────────────────────

def test_resolve_creds_sync_from_stored():
    """_resolve_credentials_sync returns decrypted stored credentials."""
    from app.common.encryption import encrypt_value
    from app.routes.v1.linkedin import _resolve_credentials_sync

    stored = {
        "linkedinUser": encrypt_value("li-user@test.com"),
        "linkedinPass": encrypt_value("li-pass-123"),
        "openRouterKey": encrypt_value("or-key-abc"),
    }

    with patch("app.routes.v1.linkedin.get_user_settings", return_value=stored), \
         patch("app.routes.v1.linkedin.migrate_orphaned_settings") as mock_migrate:
        result = _resolve_credentials_sync("user_other_789")

    assert result["linkedin_user"] == "li-user@test.com"
    assert result["linkedin_pass"] == "li-pass-123"
    assert result["openrouter_key"] == "or-key-abc"
    mock_migrate.assert_not_called()


def test_resolve_creds_sync_env_fallback():
    """Falls back to env vars when no stored credentials exist."""
    from app.routes.v1.linkedin import _resolve_credentials_sync

    with patch("app.routes.v1.linkedin.get_user_settings", return_value={}), \
         patch("app.routes.v1.linkedin.migrate_orphaned_settings") as mock_migrate, \
         patch("app.routes.v1.linkedin.LINKEDIN_LOGIN", "env-user@test.com"), \
         patch("app.routes.v1.linkedin.LINKEDIN_PASSWORD", "env-pass-456"):
        result = _resolve_credentials_sync("user_other_789")

    assert result["linkedin_user"] == "env-user@test.com"
    assert result["linkedin_pass"] == "env-pass-456"
    assert result["openrouter_key"] is None
    mock_migrate.assert_not_called()


def test_resolve_creds_sync_triggers_migration():
    """Triggers orphan migration for user_alex_chen_123 when settings are empty."""
    from app.common.encryption import encrypt_value
    from app.routes.v1.linkedin import _resolve_credentials_sync

    migrated = {
        "linkedinUser": encrypt_value("migrated@test.com"),
        "linkedinPass": encrypt_value("migrated-pass"),
    }

    with patch(
        "app.routes.v1.linkedin.get_user_settings",
        side_effect=[{}, migrated],
    ) as mock_get, patch(
        "app.routes.v1.linkedin.migrate_orphaned_settings"
    ) as mock_migrate, patch(
        "app.routes.v1.linkedin.LINKEDIN_LOGIN", None
    ), patch(
        "app.routes.v1.linkedin.LINKEDIN_PASSWORD", None
    ):
        result = _resolve_credentials_sync("user_alex_chen_123")

    mock_migrate.assert_called_once_with("user_recruiter_456", "user_alex_chen_123")
    assert mock_get.call_count == 2
    assert result["linkedin_user"] == "migrated@test.com"
    assert result["linkedin_pass"] == "migrated-pass"


def test_resolve_creds_sync_decryption_failure_env_fallback():
    """When decryption fails, falls back to env vars gracefully."""
    from app.routes.v1.linkedin import _resolve_credentials_sync

    stored = {
        "linkedinUser": "corrupted-not-valid-ciphertext",
        "linkedinPass": "also-corrupted",
    }

    with patch("app.routes.v1.linkedin.get_user_settings", return_value=stored), \
         patch("app.routes.v1.linkedin.migrate_orphaned_settings"), \
         patch("app.routes.v1.linkedin.LINKEDIN_LOGIN", "env-fallback-user"), \
         patch("app.routes.v1.linkedin.LINKEDIN_PASSWORD", "env-fallback-pass"):
        result = _resolve_credentials_sync("user_other_789")

    assert result["linkedin_user"] == "env-fallback-user"
    assert result["linkedin_pass"] == "env-fallback-pass"
    assert result["openrouter_key"] is None


# ── background_sync_linkedin tests ──────────────────────────────────────────

def test_background_sync_missing_creds():
    """Stores error JSON and logs MISSING_CREDS when no credentials found."""
    from app.routes.v1.linkedin import background_sync_linkedin

    with patch(
        "app.routes.v1.linkedin._resolve_credentials_sync",
        return_value={"linkedin_user": None, "linkedin_pass": None, "openrouter_key": None},
    ), patch(
        "app.routes.v1.linkedin.store_resume"
    ) as mock_store, patch(
        "app.routes.v1.linkedin.safe_log_activity"
    ) as mock_log, patch(
        "app.routes.v1.linkedin.generate_resume_from_linkedin"
    ) as mock_pipeline:
        background_sync_linkedin("user_123", "https://linkedin.com/in/test")

    # Pipeline should NOT be called
    mock_pipeline.assert_not_called()
    # Error JSON should be stored
    mock_store.assert_called_once()
    stored_args = mock_store.call_args
    assert stored_args[0][0] == "LinkedIn_Profile.pdf"
    error_data = json.loads(stored_args[0][1])
    assert "error" in error_data
    assert stored_args[0][2] == "user_123"
    # Activity logged with MISSING_CREDS
    mock_log.assert_called_once_with(
        "user_123", "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "MISSING_CREDS"
    )


def test_background_sync_success():
    """Stores resume and logs SYNCED on successful pipeline run."""
    from app.routes.v1.linkedin import background_sync_linkedin

    resume_output = {
        "resume": {
            "contact": {"name": "Test User"},
            "summary": "Software engineer",
        }
    }

    with patch(
        "app.routes.v1.linkedin._resolve_credentials_sync",
        return_value={"linkedin_user": "user@test.com", "linkedin_pass": "pass", "openrouter_key": "key"},
    ), patch(
        "app.routes.v1.linkedin.build_llm_config",
        return_value={"api_key": "key", "model": None},
    ), patch(
        "app.routes.v1.linkedin.build_linkedin_creds",
        return_value={"email": "user@test.com", "password": "pass"},
    ), patch(
        "app.routes.v1.linkedin.generate_resume_from_linkedin",
        return_value=resume_output,
    ) as mock_pipeline, patch(
        "app.routes.v1.linkedin.store_resume"
    ) as mock_store, patch(
        "app.routes.v1.linkedin.safe_log_activity"
    ) as mock_log:
        background_sync_linkedin("user_123", "https://linkedin.com/in/test")

    # Pipeline called with credentials
    mock_pipeline.assert_called_once()
    call_kwargs = mock_pipeline.call_args
    assert call_kwargs[1]["linkedin_creds"] == {"email": "user@test.com", "password": "pass"}
    # Resume stored
    mock_store.assert_called_once()
    stored_text = mock_store.call_args[0][1]
    stored_data = json.loads(stored_text)
    assert stored_data["contact"]["name"] == "Test User"
    # Activity logged SYNCED
    mock_log.assert_called_once_with(
        "user_123", "linkedin_sync_complete", "LinkedIn_Profile.pdf", 100, "SYNCED"
    )


def test_background_sync_pipeline_error():
    """Logs ERROR when pipeline raises an exception."""
    from app.routes.v1.linkedin import background_sync_linkedin

    with patch(
        "app.routes.v1.linkedin._resolve_credentials_sync",
        return_value={"linkedin_user": "user@test.com", "linkedin_pass": "pass", "openrouter_key": "key"},
    ), patch(
        "app.routes.v1.linkedin.build_llm_config",
        return_value={"api_key": "key", "model": None},
    ), patch(
        "app.routes.v1.linkedin.build_linkedin_creds",
        return_value={"email": "user@test.com", "password": "pass"},
    ), patch(
        "app.routes.v1.linkedin.generate_resume_from_linkedin",
        side_effect=Exception("Selenium timeout"),
    ), patch(
        "app.routes.v1.linkedin.store_resume"
    ) as mock_store, patch(
        "app.routes.v1.linkedin.safe_log_activity"
    ) as mock_log:
        background_sync_linkedin("user_123", "https://linkedin.com/in/test")

    # Resume should NOT be stored
    mock_store.assert_not_called()
    # Activity logged ERROR
    mock_log.assert_called_once_with(
        "user_123", "linkedin_sync_failed", "LinkedIn_Profile.pdf", 0, "ERROR"
    )
