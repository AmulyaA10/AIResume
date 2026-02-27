"""Symmetric encryption helpers for credential storage using Fernet."""

import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

_ENCRYPTION_KEY = None  # Lazy-initialised by _ensure_key()


def _ensure_key() -> str:
    """Return a valid Fernet key, auto-generating one if needed.

    Resolution order:
      1. Module-level cache (_ENCRYPTION_KEY)
      2. Environment variable ENCRYPTION_KEY
      3. Auto-generate a new key → append to backend/.env → set in os.environ
    """
    global _ENCRYPTION_KEY

    if _ENCRYPTION_KEY:
        return _ENCRYPTION_KEY

    # Safety: ensure backend/.env is loaded even if config.py hasn't been imported yet
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")

    key = os.getenv("ENCRYPTION_KEY")

    # Reject obvious placeholders from .env.example
    if key and key.startswith("your_"):
        key = None

    if not key:
        key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = key
        print(f"INFO: [encryption] Auto-generated ENCRYPTION_KEY (first run).")

        # Persist to backend/.env so it survives restarts
        env_path = Path(__file__).resolve().parents[2] / ".env"
        try:
            if env_path.exists():
                content = env_path.read_text()
                if "ENCRYPTION_KEY=" in content:
                    # Replace existing placeholder line
                    lines = content.splitlines(keepends=True)
                    new_lines = []
                    for line in lines:
                        if line.strip().startswith("ENCRYPTION_KEY="):
                            new_lines.append(f"ENCRYPTION_KEY={key}\n")
                        else:
                            new_lines.append(line)
                    env_path.write_text("".join(new_lines))
                else:
                    # Append to existing .env
                    with open(env_path, "a") as f:
                        f.write(f"\n# Auto-generated Fernet encryption key\nENCRYPTION_KEY={key}\n")
            else:
                # Create new .env with just the key
                env_path.write_text(
                    "# Auto-generated Fernet encryption key\n"
                    f"ENCRYPTION_KEY={key}\n"
                )
            print(f"INFO: [encryption] Persisted ENCRYPTION_KEY to {env_path}")
        except Exception as e:
            print(f"WARNING: [encryption] Could not persist ENCRYPTION_KEY to {env_path}: {e}")

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
