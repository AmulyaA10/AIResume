import os
from dotenv import load_dotenv

load_dotenv()

# ---------- OAuth ----------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "placeholder_id")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "placeholder_secret")
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "placeholder_id")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "placeholder_secret")

# ---------- LLM ----------
OPEN_ROUTER_KEY = os.getenv("OPEN_ROUTER_KEY")

# ---------- LinkedIn Scraper ----------
LINKEDIN_LOGIN = os.getenv("LinkedinLogin")
LINKEDIN_PASSWORD = os.getenv("LinkedinPassword")

# ---------- CORS ----------
CORS_ORIGINS = ["*"]  # In production, replace with specific React URL

# ---------- Paths ----------
UPLOAD_DIR = "data/raw_resumes"

# ---------- URLs ----------
FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://localhost:8000"
