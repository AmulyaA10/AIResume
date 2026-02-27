"""Unit tests for the encryption module."""

import os
import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet


# Generate a test key once for all tests in this module
_TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def set_encryption_key():
    """Set a valid ENCRYPTION_KEY for all tests in this module."""
    with patch.dict(os.environ, {"ENCRYPTION_KEY": _TEST_KEY}):
<<<<<<< HEAD
        # Reload the module-level variable
        import app.common.encryption as enc_mod
        enc_mod._ENCRYPTION_KEY = _TEST_KEY
        yield
=======
        import app.common.encryption as enc_mod
        enc_mod._ENCRYPTION_KEY = _TEST_KEY
        yield
        # Reset to env value (or None) so next test starts clean
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
        enc_mod._ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")


def test_encrypt_decrypt_roundtrip():
    """Encrypting then decrypting returns the original value."""
    from app.common.encryption import encrypt_value, decrypt_value

    plaintext = "sk-or-v1-abc123secret"
    ciphertext = encrypt_value(plaintext)
    assert ciphertext != plaintext  # must not be stored as plain text
    assert decrypt_value(ciphertext) == plaintext


def test_encrypt_empty_string():
    """Encrypting empty string returns empty string without error."""
    from app.common.encryption import encrypt_value

    assert encrypt_value("") == ""


def test_decrypt_empty_string():
    """Decrypting empty string returns empty string without error."""
    from app.common.encryption import decrypt_value

    assert decrypt_value("") == ""


def test_decrypt_wrong_key_raises():
    """Decrypting with a different key raises ValueError."""
    from app.common.encryption import encrypt_value
    import app.common.encryption as enc_mod

    plaintext = "my-secret"
    ciphertext = encrypt_value(plaintext)

    # Switch to a different key
    other_key = Fernet.generate_key().decode()
    enc_mod._ENCRYPTION_KEY = other_key

    from app.common.encryption import decrypt_value

    with pytest.raises(ValueError, match="Failed to decrypt"):
        decrypt_value(ciphertext)


def test_mask_value_short():
    """Short values (<=4 chars) are fully masked."""
    from app.common.encryption import mask_value

    assert mask_value("abcd") == "****"
    assert mask_value("ab") == "****"
    assert mask_value("") == "****"


def test_mask_value_long():
    """Longer values show only the last 4 chars."""
    from app.common.encryption import mask_value

    result = mask_value("sk-or-v1-abc123")
    assert result.endswith("c123")
    assert result.startswith("*")
    assert len(result) == len("sk-or-v1-abc123")


def test_mask_value_email():
    """Email addresses are properly masked."""
    from app.common.encryption import mask_value

    result = mask_value("user@example.com")
    assert result.endswith(".com")
    assert result.count("*") == len("user@example.com") - 4


<<<<<<< HEAD
def test_missing_encryption_key_raises():
    """Missing ENCRYPTION_KEY raises ValueError."""
    import app.common.encryption as enc_mod

    enc_mod._ENCRYPTION_KEY = None
    from app.common.encryption import encrypt_value

    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        encrypt_value("test")
=======
def test_missing_encryption_key_auto_generates():
    """Missing ENCRYPTION_KEY auto-generates a valid key."""
    import app.common.encryption as enc_mod

    enc_mod._ENCRYPTION_KEY = None
    # Also remove from env so _ensure_key() must auto-generate
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ENCRYPTION_KEY", None)
        from app.common.encryption import encrypt_value, decrypt_value

        # Should NOT raise — auto-generates a key
        ciphertext = encrypt_value("test-auto")
        assert ciphertext != ""
        assert ciphertext != "test-auto"

        # Verify the auto-generated key works for decryption too
        assert decrypt_value(ciphertext) == "test-auto"

        # Verify a key was generated and cached
        assert enc_mod._ENCRYPTION_KEY is not None
        assert len(enc_mod._ENCRYPTION_KEY) > 0
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
