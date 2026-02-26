"""Unit tests for user settings (credential storage) endpoints."""

import os
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


# ---- PUT /settings ----

@pytest.mark.asyncio
async def test_save_settings_success(app, auth_headers):
    """PUT /settings encrypts and stores credentials."""
    with patch("app.routes.v1.user.upsert_user_setting") as mock_upsert, \
         patch("app.routes.v1.user.encrypt_value", return_value="encrypted_blob"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/api/v1/user/settings",
                headers=auth_headers,
                json={"openRouterKey": "sk-or-v1-test123"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "openRouterKey" in data["updated_keys"]
        mock_upsert.assert_called_once_with("user_alex_chen_123", "openRouterKey", "encrypted_blob")


@pytest.mark.asyncio
async def test_save_settings_multiple_keys(app, auth_headers):
    """PUT /settings stores multiple credentials at once."""
    with patch("app.routes.v1.user.upsert_user_setting") as mock_upsert, \
         patch("app.routes.v1.user.encrypt_value", return_value="enc"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/api/v1/user/settings",
                headers=auth_headers,
                json={
                    "openRouterKey": "key123",
                    "linkedinUser": "user@test.com",
                    "linkedinPass": "pass123",
                },
            )
        assert resp.status_code == 200
        assert len(resp.json()["updated_keys"]) == 3
        assert mock_upsert.call_count == 3


@pytest.mark.asyncio
async def test_save_settings_empty_body(app, auth_headers):
    """PUT /settings with no fields returns 400."""
    with patch("app.routes.v1.user.upsert_user_setting"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/api/v1/user/settings",
                headers=auth_headers,
                json={},
            )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_save_settings_unauthenticated(app):
    """PUT /settings without auth token still works (mock auth returns guest-like user)."""
    with patch("app.routes.v1.user.upsert_user_setting"), \
         patch("app.routes.v1.user.encrypt_value", return_value="enc"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/api/v1/user/settings",
                json={"openRouterKey": "test"},
            )
        # Mock auth doesn't reject — it returns a default user
        assert resp.status_code == 200


# ---- GET /settings ----

@pytest.mark.asyncio
async def test_get_settings_with_stored_creds(app, auth_headers):
    """GET /settings returns masked values for stored credentials."""
    from app.common.encryption import encrypt_value

    stored = {
        "openRouterKey": encrypt_value("sk-or-v1-abcdef123456"),
        "linkedinUser": encrypt_value("user@example.com"),
    }

    with patch("app.routes.v1.user.get_user_settings", return_value=stored):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/user/settings", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_openRouterKey"] is True
    assert data["has_linkedinUser"] is True
    assert data["has_linkedinPass"] is False
    # Masked values should end with last 4 chars
    assert data["openRouterKey"].endswith("3456")
    assert data["openRouterKey"].startswith("*")
    assert data["linkedinUser"].endswith(".com")


@pytest.mark.asyncio
async def test_get_settings_empty(app, auth_headers):
    """GET /settings with no stored credentials returns all false."""
    with patch("app.routes.v1.user.get_user_settings", return_value={}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/user/settings", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_openRouterKey"] is False
    assert data["has_linkedinUser"] is False
    assert data["has_linkedinPass"] is False
    assert data["openRouterKey"] is None
    assert data["linkedinUser"] is None
    assert data["linkedinPass"] is None


# ---- DELETE /settings ----

@pytest.mark.asyncio
async def test_delete_settings(app, auth_headers):
    """DELETE /settings clears all credentials."""
    with patch("app.routes.v1.user.delete_user_settings") as mock_delete:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/api/v1/user/settings", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    mock_delete.assert_called_once_with("user_alex_chen_123")


# ---- resolve_credentials ----

@pytest.mark.asyncio
async def test_resolve_credentials_headers_first():
    """Headers take priority over stored credentials."""
    from app.dependencies import resolve_credentials

    result = await resolve_credentials(
        user_id="user_123",
        x_openrouter_key="header-key",
        x_llm_model="gpt-4",
        x_linkedin_user="header-user",
        x_linkedin_pass="header-pass",
    )
    assert result["openrouter_key"] == "header-key"
    assert result["llm_model"] == "gpt-4"
    assert result["linkedin_user"] == "header-user"
    assert result["linkedin_pass"] == "header-pass"


@pytest.mark.asyncio
async def test_resolve_credentials_falls_back_to_stored():
    """When headers are absent, falls back to decrypted server-stored values."""
    from app.common.encryption import encrypt_value
    from app.dependencies import resolve_credentials

    stored = {
        "openRouterKey": encrypt_value("stored-api-key"),
        "linkedinUser": encrypt_value("stored@email.com"),
        "linkedinPass": encrypt_value("stored-pass"),
    }

    with patch("services.db.lancedb_client.get_user_settings", return_value=stored):
        result = await resolve_credentials(user_id="user_123")

    assert result["openrouter_key"] == "stored-api-key"
    assert result["linkedin_user"] == "stored@email.com"
    assert result["linkedin_pass"] == "stored-pass"


@pytest.mark.asyncio
async def test_resolve_credentials_partial_fallback():
    """Headers override selectively; missing keys fall back to stored."""
    from app.common.encryption import encrypt_value
    from app.dependencies import resolve_credentials

    stored = {
        "openRouterKey": encrypt_value("stored-key"),
        "linkedinUser": encrypt_value("stored@email.com"),
        "linkedinPass": encrypt_value("stored-pass"),
    }

    with patch("services.db.lancedb_client.get_user_settings", return_value=stored):
        result = await resolve_credentials(
            user_id="user_123",
            x_openrouter_key="my-header-key",  # override
            # linkedin creds will fall back
        )

    assert result["openrouter_key"] == "my-header-key"
    assert result["linkedin_user"] == "stored@email.com"
    assert result["linkedin_pass"] == "stored-pass"
