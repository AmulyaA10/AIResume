"""Helpers for building LLM and credential configs from HTTP headers."""

from typing import Optional


def build_llm_config(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[dict]:
    """Build an LLM config dict from header values, or ``None`` if no key.

    Every route that calls ``run_resume_pipeline`` needs the same one-liner.
    Centralising it here keeps the routes clean and ensures a consistent
    dict shape that ``get_llm()`` in ``services/ai/common`` expects.
    """
    if not api_key:
        return None
    return {"api_key": api_key, "model": model}


def build_linkedin_creds(
    email: Optional[str] = None,
    password: Optional[str] = None,
) -> Optional[dict]:
    """Build LinkedIn credential dict, or ``None`` if incomplete."""
    if email and password:
        return {"email": email, "password": password}
    return None
