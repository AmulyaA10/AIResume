"""Shared backend utilities — DRY helpers for route handlers."""

from app.common.llm_helpers import build_llm_config, build_linkedin_creds
from app.common.activity import safe_log_activity
from app.common.encryption import encrypt_value, decrypt_value, mask_value
from app.common.validation import (
    precheck_resume_validation,
    validate_resume_fields,
    validate_resume_output,
    resume_json_to_text,
)
from app.common.skill_utils import canonicalize_skill

__all__ = [
    "build_llm_config", "build_linkedin_creds", "safe_log_activity",
    "encrypt_value", "decrypt_value", "mask_value",
    "precheck_resume_validation",
    "validate_resume_fields", "validate_resume_output", "resume_json_to_text",
    "canonicalize_skill",
]
