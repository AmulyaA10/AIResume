"""Symmetric encryption helpers for credential storage using Fernet."""

import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

_ENCRYPTION_KEY = None  # Lazy-initialised by _ensure_key()


def _ensure_key() -> str:
    """Return a valid Fernet key, auto-generating one if needed.

    Resolution order:
      1. Module-level cache (_ENCRYPTION_KEY)
      2. Dedicated key file (backend/.secret_key)
      3. Environment variable ENCRYPTION_KEY (migration fallback)
      4. Auto-generate a new key → write to backend/.secret_key
    """
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY:
        return _ENCRYPTION_KEY

    # 1. Dedicated key file (preferred)
    key_file = Path(__file__).resolve().parents[2] / ".secret_key"
    if key_file.exists():
        key = key_file.read_text().strip()
        if key and not key.startswith("your_"):
            _ENCRYPTION_KEY = key
            return key

    # 2. Env var fallback (migration path)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    key = os.getenv("ENCRYPTION_KEY", "")
    if key and not key.startswith("your_"):
        _ENCRYPTION_KEY = key
        return key

    # 3. Auto-generate and persist
    key = Fernet.generate_key().decode()
    print("INFO: [encryption] Auto-generated ENCRYPTION_KEY (first run).")
    try:
        key_file.write_text(key)
        print(f"INFO: [encryption] Persisted encryption key to {key_file}")
    except Exception as e:
        print(f"WARNING: [encryption] Could not persist encryption key to {key_file}: {e}")
    os.environ["ENCRYPTION_KEY"] = key
    _ENCRYPTION_KEY = key
    return key


def _get_fernet() -> Fernet:
    """Return a Fernet instance, auto-generating a key if needed."""
    key = _ensure_key()
    return Fernet(key.encode() if isinstance(key, str) else key)


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
