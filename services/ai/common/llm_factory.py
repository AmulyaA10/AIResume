"""Canonical LLM factory — every graph imports from here."""

from typing import Optional

from langchain_openai import ChatOpenAI

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def get_llm(config: Optional[dict] = None, temperature: float = 0.7) -> ChatOpenAI:
    """Initialise a ChatOpenAI instance from *config*.

    Parameters
    ----------
    config : dict | None
        Optional dict with keys ``api_key``, ``model``, ``temperature``,
        ``base_url``.  When the caller passes header-derived config from a
        route, all four may be present.
    temperature : float
        Default temperature used when *config* does not specify one.
        Pass ``0`` for deterministic scoring, ``0.7`` for generation, etc.
    """
    api_key = config.get("api_key") if config else None
    if not api_key:
        raise ValueError(
            "OpenRouter API key is required. Please save your key in Settings."
        )
    return ChatOpenAI(
        model=config.get("model") or DEFAULT_MODEL,
        temperature=config.get("temperature", temperature),
        api_key=api_key,
        base_url=config.get("base_url") or DEFAULT_BASE_URL,
    )
