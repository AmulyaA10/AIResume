from typing import TypedDict, Optional
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
import json

from services.ai.common import get_llm, clean_json_output

class ScreeningState(TypedDict):
    resume_text: str
    jd_text: str
    decision: Optional[dict]
    score: Optional[dict]
    config: Optional[dict]
    threshold: int

def screening_agent(state: ScreeningState):
    llm = get_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["resume", "jd", "threshold"],
        template="""
You are an expert AI recruiter.

Job Description:
{jd}

Candidate Resume:
{resume}

Selection Threshold: {threshold}%

TASK:
1. Evaluate if the candidate is a match for the job.
2. Provide a score (0-100) based on skills, experience, and relevance.
3. Decision: 
   - If the score is GREATER THAN OR EQUAL TO the threshold ({threshold}%), set "selected": true.
   - Otherwise, set "selected": false.
4. Provide a brief reason for the decision, mentioning the score and how it compares to the threshold.

Return ONLY valid JSON:
{{
  "decision": {{
    "selected": true,
    "reason": "Score 85% is above threshold 75%."
  }},
  "score": {{
      "overall": 85
  }}
}}
"""
    )
    
    try:
        response = llm.invoke(prompt.format(
            resume=state["resume_text"], 
            jd=state["jd_text"],
            threshold=state.get("threshold", 75)
        ))
        clean_content = clean_json_output(response.content)
        result = json.loads(clean_content)
        
        score_val = result.get("score", {}).get("overall", 0)
        threshold_val = state.get("threshold", 75)
        
        # Enforce threshold logic in Python to prevent LLM hallucinations
        selected = score_val >= threshold_val
        
        # Determine decision and reasoning
        decision = result.get("decision", {})
        if decision.get("selected") != selected:
            # Override if LLM made a mathematical error
            decision["selected"] = selected
            if selected:
                decision["reason"] = f"Automatic override: Score {score_val}% meets or exceeds threshold {threshold_val}%. " + decision.get("reason", "")
            else:
                decision["reason"] = f"Automatic override: Score {score_val}% is below threshold {threshold_val}%. " + decision.get("reason", "")

        return {
            "decision": decision,
            "score": {"overall": score_val}
        }
    except Exception as e:
        return {
            "decision": {"selected": False, "reason": f"Error in screening: {str(e)}"},
            "score": {"overall": 0}
        }

def build_screening_graph():
    graph = StateGraph(ScreeningState)
    graph.add_node("screen", screening_agent)
    graph.set_entry_point("screen")
    graph.add_edge("screen", END)
    return graph.compile()
