from services.ai.resume_quality_graph import build_resume_quality_graph
from services.ai.skill_gap_graph import build_skill_gap_graph
from services.ai.linkedin_resume_graph import build_linkedin_resume_graph
from services.ai.langgraph_workflow import build_resume_graph
from services.ai.screening_graph import build_screening_graph
from services.ai.resume_generator_graph import build_resume_generator_graph
from services.ai.resume_validation_graph import build_resume_validation_graph

_quality_graph = build_resume_quality_graph()
_skill_gap_graph = build_skill_gap_graph()
_linkedin_graph = build_linkedin_resume_graph()
_screening_graph = build_screening_graph()
_generator_graph = build_resume_generator_graph()
_validation_graph = build_resume_validation_graph()
graph = build_resume_graph()

def run_resume_pipeline(task: str, resumes: list = None, query: str = None, llm_config: dict = None, threshold: int = 75):
    if task == "score":
        return _quality_graph.invoke(
            {"resumes": resumes, "config": llm_config}
        )
    elif task == "skill_gap":
        return _skill_gap_graph.invoke({
            "resume_text": resumes[0],
            "jd_text": query,
            "config": llm_config
        })
    elif task == "screen":
        return _screening_graph.invoke({
            "resume_text": resumes[0],
            "jd_text": query,
            "config": llm_config,
            "threshold": threshold
        })
    elif task == "generate":
        return _generator_graph.invoke({
            "profile_description": query,
            "config": llm_config
        })

    raise ValueError(f"Unknown task: {task}")

def run_resume_validation(file_name: str, file_type: str, extracted_text: str,
                          target_role: str = None, llm_config: dict = None) -> dict:
    """Validate a resume document and return a structured validation report."""
    result = _validation_graph.invoke({
        "file_name": file_name,
        "file_type": file_type,
        "extracted_text": extracted_text,
        "target_role": target_role or "",
        "config": llm_config
    })
    return result.get("validation_result", {})


def generate_resume_from_linkedin(url: str, llm_config: dict = None, linkedin_creds: dict = None):
    return _linkedin_graph.invoke({
        "linkedin_url": url,
        "config": llm_config,
        "linkedin_creds": linkedin_creds
    })
