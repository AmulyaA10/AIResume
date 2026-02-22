"""Safe activity-logging wrapper — never lets a log failure crash a request."""

from typing import Optional

from services.db.lancedb_client import log_activity


def safe_log_activity(
    user_id: str,
    activity_type: str,
    filename: str = "Manual Input",
    score: int = 0,
    decision: Optional[str] = None,
) -> None:
    """Fire-and-forget wrapper around ``log_activity``.

    If the DB write fails for any reason the request still succeeds.
    The error is printed to stdout for debugging.
    """
    try:
        if decision is not None:
            log_activity(user_id, activity_type, filename, score, decision)
        else:
            log_activity(user_id, activity_type, filename, score)
    except Exception as e:
        print(f"DEBUG: Failed to log {activity_type} activity: {e}")
