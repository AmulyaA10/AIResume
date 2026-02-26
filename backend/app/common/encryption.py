"""Symmetric encryption helpers for credential storage using Fernet."""

import os
from cryptography.fernet import Fernet, InvalidToken

_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")


def _get_fernet() -> Fernet:
    """Return a Fernet instance, raising ValueError if key is missing."""
    if not _ENCRYPTION_KEY:
        raise ValueError(
            "ENCRYPTION_KEY environment variable is required for credential storage. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string, returning a base64-encoded ciphertext string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string, returning the original plaintext."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt credential — ENCRYPTION_KEY may have changed.")


def mask_value(plaintext: str) -> str:
    """Return a masked version of a credential, showing only last 4 chars."""
    if not plaintext or len(plaintext) <= 4:
        return "****"
    return "*" * (len(plaintext) - 4) + plaintext[-4:]
