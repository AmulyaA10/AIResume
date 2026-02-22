"""Shared output-cleaning helpers for LLM responses."""


def clean_json_output(content: str) -> str:
    """Remove markdown code-block fences (```json ... ```) from a string.

    LLMs frequently wrap JSON in fences even when instructed not to.
    This helper strips them so the result can be fed to ``json.loads``.
    """
    content = content.strip()
    if content.startswith("```"):
        # Remove first line (```json or ```)
        content = content.split("\n", 1)[1]
        # Remove last line (```)
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]
    return content.strip()
