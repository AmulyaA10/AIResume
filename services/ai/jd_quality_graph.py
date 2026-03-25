# services/ai/jd_quality_graph.py
"""JD Quality Check Agent

Analyses a job description for:
  - Bias language (gendered words, age-coded phrases, cultural exclusion)
  - Unrealistic requirements (experience years exceeding technology age, etc.)
  - Improvement suggestions for flagged phrases

Invoked concurrently with JD parsing so it adds no extra latency to the upload path.
"""
from typing import TypedDict, Optional, List

from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END

from services.ai.common import get_llm, safe_parse_json


class JDQualityState(TypedDict):
    jd_text: str
    config: Optional[dict]
    quality_report: Optional[dict]


_FALLBACK_REPORT = {
    "bias_flags": [],
    "unrealistic_requirements": [],
    "overall_quality_score": 70,
    "summary": "Quality check unavailable.",
}

_PROMPT = PromptTemplate(
    input_variables=["jd"],
    template="""You are an expert hiring consultant reviewing a job description for quality issues.

Analyse the job description below and identify:

1. BIAS LANGUAGE — gendered words (e.g. "rockstar", "ninja", "dominant"), age-coded phrases
   (e.g. "digital native", "recent graduate only"), cultural exclusion language.

2. UNREALISTIC REQUIREMENTS — e.g. "10+ years of Kubernetes" (Kubernetes is ~9 years old),
   demanding a PhD for an entry-level role, requiring 5 tools that are rarely used together.

3. OVERALL QUALITY SCORE — 0 to 100. Deduct points for each bias flag and unrealistic requirement.

Job Description:
{jd}

Return ONLY valid JSON:
{{
  "bias_flags": [
    {{"phrase": "rockstar developer", "type": "gender/age/culture", "suggestion": "Use 'skilled developer' instead"}}
  ],
  "unrealistic_requirements": [
    {{"requirement": "10+ years Kubernetes experience", "reason": "Kubernetes was released in 2014 (~10 years ago); 5+ years is more realistic"}}
  ],
  "overall_quality_score": 85,
  "summary": "Well-written JD with one minor bias flag and one unrealistic requirement."
}}
"""
)


async def jd_quality_agent(state: JDQualityState):
    llm = get_llm(state.get("config"))
    try:
        response = await llm.ainvoke(_PROMPT.format(jd=state["jd_text"][:8000]))
        report = safe_parse_json(response.content)
        # Ensure required keys are present
        report.setdefault("bias_flags", [])
        report.setdefault("unrealistic_requirements", [])
        report.setdefault("overall_quality_score", 70)
        report.setdefault("summary", "")
    except Exception as e:
        print(f"DEBUG: [jd-quality] LLM call failed: {e}")
        report = _FALLBACK_REPORT.copy()

    return {"quality_report": report}


def build_jd_quality_graph():
    graph = StateGraph(JDQualityState)
    graph.add_node("quality_check", jd_quality_agent)
    graph.set_entry_point("quality_check")
    graph.add_edge("quality_check", END)
    return graph.compile()


# ---------------------------------------------------------------------------
# Convenience wrapper — run quality check and return report dict
# ---------------------------------------------------------------------------
_graph = None


def get_jd_quality_graph():
    global _graph
    if _graph is None:
        _graph = build_jd_quality_graph()
    return _graph


async def check_jd_quality(jd_text: str, llm_config: Optional[dict] = None) -> dict:
    """Run the JD quality check and return the quality report dict."""
    graph = get_jd_quality_graph()
    try:
        result = await graph.ainvoke({
            "jd_text": jd_text,
            "config": llm_config,
            "quality_report": None,
        })
        return result.get("quality_report") or _FALLBACK_REPORT.copy()
    except Exception as e:
        print(f"DEBUG: [jd-quality] Graph invocation failed: {e}")
        return _FALLBACK_REPORT.copy()
