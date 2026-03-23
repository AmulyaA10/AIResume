import os
from pathlib import Path

# ---------- CORS ----------
CORS_ORIGINS = ["*"]

# ---------- Paths ----------
UPLOAD_DIR = str(Path(__file__).resolve().parents[2] / "data" / "raw_resumes")

# ---------- URLs ----------
FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://localhost:8000"


def get_oauth_creds() -> dict:
    """Read OAuth creds from DB system settings, with env fallback for migration."""
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        from services.db.lancedb_client import get_user_settings
        from app.common.encryption import decrypt_value
        stored = get_user_settings("__system__") or {}

        def _get(db_key: str, env_key: str, default: str) -> str:
            val = stored.get(db_key)
            if val:
                try:
                    return decrypt_value(val)
                except Exception:
                    pass
            return os.getenv(env_key, default)

        return {
            "google_client_id":      _get("googleClientId",      "GOOGLE_CLIENT_ID",      "placeholder_id"),
            "google_client_secret":  _get("googleClientSecret",  "GOOGLE_CLIENT_SECRET",  "placeholder_secret"),
            "linkedin_client_id":    _get("linkedinClientId",    "LINKEDIN_CLIENT_ID",    "placeholder_id"),
            "linkedin_client_secret":_get("linkedinClientSecret","LINKEDIN_CLIENT_SECRET","placeholder_secret"),
            "smtp_server":           _get("smtpServer",          "SMTP_SERVER",           ""),
            "smtp_port":             _get("smtpPort",            "SMTP_PORT",             "587"),
            "smtp_username":         _get("smtpUsername",        "SMTP_USERNAME",         ""),
            "smtp_password":         _get("smtpPassword",        "SMTP_PASSWORD",         ""),
            "smtp_sender":           _get("smtpSender",          "SMTP_SENDER",           ""),
        }
    except Exception as e:
        print(f"WARNING: [config] get_oauth_creds failed: {e}")
        return {
            "google_client_id": os.getenv("GOOGLE_CLIENT_ID", "placeholder_id"),
            "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "placeholder_secret"),
            "linkedin_client_id": os.getenv("LINKEDIN_CLIENT_ID", "placeholder_id"),
            "linkedin_client_secret": os.getenv("LINKEDIN_CLIENT_SECRET", "placeholder_secret"),
            "smtp_server": os.getenv("SMTP_SERVER", ""),
            "smtp_port": os.getenv("SMTP_PORT", "587"),
            "smtp_username": os.getenv("SMTP_USERNAME", ""),
            "smtp_password": os.getenv("SMTP_PASSWORD", ""),
            "smtp_sender": os.getenv("SMTP_SENDER", ""),
        }
