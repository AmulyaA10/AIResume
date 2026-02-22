from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END

class ResumeState(TypedDict):
    task: str
    resumes: Optional[List[str]]
    query: Optional[str]
    results: Optional[List[dict]]
    score: Optional[dict]
    gaps: Optional[dict]
    decision: Optional[dict]

def resume_reader_agent(state: ResumeState):
    resumes = state["resumes"]
    parsed = [{"text": r, "tokens": len(r.split())} for r in resumes]
    return {"results": parsed}

def quality_scoring_agent(state: ResumeState):
    return {
        "score": {
            "clarity": 85,
            "skills": 80,
            "format": 90,
            "overall": 85
        }
    }

def skill_gap_agent(state: ResumeState):
    return {
        "gaps": {
            "missing_skills": ["Docker", "Kubernetes"],
            "recommended": ["AWS", "CI/CD"]
        }
    }

def screening_agent(state):
    score = state["score"]["overall"]
    threshold = state.get("threshold", 75)

    return {
        "decision": {
            "selected": score >= threshold,
            "reason": (
                "Score meets threshold"
                if score >= threshold
                else "Score below threshold"
            )
        }
    }


def search_agent(state: ResumeState):
    query = state["query"]
    resumes = state["results"]

    ranked = sorted(
        resumes,
        key=lambda x: x["tokens"],
        reverse=True
    )

    return {
        "results": [
            {"name": f"Candidate {i+1}", "score": 80-i*5, "summary": "AI Engineer"}
            for i in range(len(ranked))
        ]
    }

    
    
def build_resume_graph():
    graph = StateGraph(ResumeState)

    graph.add_node("reader", resume_reader_agent)
    graph.add_node("search", search_agent)
    graph.add_node("score", quality_scoring_agent)
    graph.add_node("gap", skill_gap_agent)
    graph.add_node("screen", screening_agent)

    graph.set_entry_point("reader")

    graph.add_edge("reader", "search")
    graph.add_edge("search", "score")
    graph.add_edge("score", "gap")
    graph.add_edge("gap", "screen")
    graph.add_edge("screen", END)

    return graph.compile()

