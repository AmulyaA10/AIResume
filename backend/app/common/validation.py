"""Resume validation pre-check helper for route handlers.

Reuses the existing run_resume_validation() pipeline to validate pasted
resume text before Quality Scoring, Auto Screening, etc. proceed.

Behavior:
  - not_resume          → raise HTTP 422 (block)
  - invalid/incomplete  → return validation dict (warn)
  - valid_but_weak      → return validation dict (warn)
  - valid_good/strong   → return None (pass silently)
  - validation error    → return None (don't block on infra failure)
"""

from typing import Optional
from fastapi import HTTPException
from services.agent_controller import run_resume_validation

# Classifications that block processing entirely
BLOCKING_CLASSIFICATIONS = {"not_resume"}

# Classifications that allow processing but emit a warning
WARNING_CLASSIFICATIONS = {"resume_invalid_or_incomplete", "resume_valid_but_weak"}


def precheck_resume_validation(
    resume_text: str,
    llm_config: dict,
    file_name: str = "pasted_text",
    file_type: str = "txt",
) -> Optional[dict]:
    """Run resume validation and raise HTTP 422 if text is not a resume.

    Returns:
        None  – if validation passes cleanly (good/strong) or validation itself errored
        dict  – validation result if classification is warning-level

    Raises:
        HTTPException(422) if classification is 'not_resume'
    """
    validation = run_resume_validation(
        file_name=file_name,
        file_type=file_type,
        extracted_text=resume_text,
        llm_config=llm_config,
    )

    # If the validation graph itself failed, don't punish the user
    if validation.get("error"):
        return None

    classification = validation.get("classification", "not_resume")

    if classification in BLOCKING_CLASSIFICATIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "not_a_resume",
                "message": "The provided text does not appear to be a resume.",
                "validation": validation,
            },
        )

    if classification in WARNING_CLASSIFICATIONS:
        return validation

    return None
