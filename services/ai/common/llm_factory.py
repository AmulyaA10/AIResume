"""Canonical LLM factory — every graph imports from here."""

import os
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def get_llm(config: Optional[dict] = None, temperature: float = 0.7) -> ChatOpenAI:
    """Initialise a ChatOpenAI instance from *config* or fall back to env vars.

    Parameters
    ----------
    config : dict | None
        Optional dict with keys ``api_key``, ``model``, ``temperature``,
        ``base_url``.  When the caller passes header-derived config from a
        route, all four may be present; when running from a script only
        ``OPEN_ROUTER_KEY`` env-var is used.
    temperature : float
        Default temperature used when *config* does not specify one.
        Pass ``0`` for deterministic scoring, ``0.7`` for generation, etc.
    """
    if config and config.get("api_key"):
        return ChatOpenAI(
            model=config.get("model", DEFAULT_MODEL),
            temperature=config.get("temperature", temperature),
            api_key=config.get("api_key"),
            base_url=config.get("base_url", DEFAULT_BASE_URL),
        )
    # Fallback to .env
    return ChatOpenAI(
        model=DEFAULT_MODEL,
        temperature=temperature,
        api_key=os.getenv("OPEN_ROUTER_KEY"),
        base_url=DEFAULT_BASE_URL,
    )
