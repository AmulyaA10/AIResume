import hashlib
import json
from collections import OrderedDict
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END

from langchain_core.prompts import PromptTemplate

from services.ai.common import get_json_llm, safe_parse_json

# ---------------------------------------------------------------------------
# LRU cache — keyed by SHA-256 of resume text, max 512 entries
# ---------------------------------------------------------------------------
_QUALITY_CACHE: OrderedDict = OrderedDict()
_QUALITY_CACHE_MAX = 512


def _cache_get(key: str):
    if key in _QUALITY_CACHE:
        _QUALITY_CACHE.move_to_end(key)
        return _QUALITY_CACHE[key]
    return None


def _cache_set(key: str, value: dict):
    _QUALITY_CACHE[key] = value
    _QUALITY_CACHE.move_to_end(key)
    if len(_QUALITY_CACHE) > _QUALITY_CACHE_MAX:
        _QUALITY_CACHE.popitem(last=False)


# -----------------------------
# State
# -----------------------------
class ResumeQualityState(TypedDict):
    resumes: List[str]
    parsed: Optional[str]
    score: Optional[dict]
    config: Optional[dict]
    _cache_key: Optional[str]


# -----------------------------
# Agents
# -----------------------------
def resume_reader_agent(state: ResumeQualityState):
    resume_text = state["resumes"][0]
    cache_key = hashlib.sha256(resume_text.encode()).hexdigest()
    return {"parsed": resume_text, "_cache_key": cache_key}


def quality_scoring_agent(state: ResumeQualityState):
    cache_key = state.get("_cache_key")
    if cache_key:
        cached = _cache_get(cache_key)
        if cached is not None:
            print(f"DEBUG: [quality-cache] hit for key {cache_key[:12]}…")
            return {"score": cached}

    llm = get_json_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["resume"],
        template="""
You are an expert resume reviewer.

Resume:
{resume}

TASK:
Evaluate resume quality on a scale of 0–100.

Return ONLY valid JSON:

{{
  "clarity": 0,
  "skills": 0,
  "format": 0,
  "overall": 0
}}
"""
    )

    response = llm.invoke(
        prompt.format(resume=state["parsed"])
    )

    try:
        score_data = json.loads(response.content)
    except Exception as e:
        print(f"Error parsing quality score JSON: {e}")
        score_data = {"clarity": 0, "skills": 0, "format": 0, "overall": 0}

    if cache_key:
        _cache_set(cache_key, score_data)

    return {"score": score_data}


# -----------------------------
# Graph
# -----------------------------
def build_resume_quality_graph():
    graph = StateGraph(ResumeQualityState)

    graph.add_node("reader", resume_reader_agent)
    graph.add_node("score", quality_scoring_agent)

    graph.set_entry_point("reader")
    graph.add_edge("reader", "score")
    graph.add_edge("score", END)

    return graph.compile()
