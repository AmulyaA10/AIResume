"""Shared backend utilities — DRY helpers for route handlers."""

from app.common.llm_helpers import build_llm_config, build_linkedin_creds
from app.common.activity import safe_log_activity

__all__ = ["build_llm_config", "build_linkedin_creds", "safe_log_activity"]
