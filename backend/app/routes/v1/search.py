from fastapi import APIRouter, Header, Depends
from typing import Optional
import time

from app.dependencies import get_current_user, get_user_role, resolve_credentials
from app.models import SearchRequest
from services.db.lancedb_client import search_resumes_hybrid

router = APIRouter()

# Skill keywords used for lightweight missing-skill detection (no LLM needed)
_SKILL_KEYWORDS = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "ruby",
    "react", "vue", "angular", "node", "django", "fastapi", "flask", "spring",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
    "postgres", "mysql", "mongodb", "redis", "elasticsearch",
    "machine learning", "deep learning", "pytorch", "tensorflow", "nlp",
    "ci/cd", "git", "linux", "rest", "graphql", "kafka", "spark",
}


def _score_from_rank(rank: int) -> int:
    """Convert 1-based semantic rank to a 0-100 score (rank 1 = 95, decays by ~8 per rank)."""
    return max(10, 95 - (rank - 1) * 8)


def _missing_skills(query: str, excerpts: list[str]) -> list[str]:
    """Return skill keywords mentioned in query but absent from resume excerpts."""
    query_lower = query.lower()
    combined_text = " ".join(excerpts).lower()
    query_skills = {kw for kw in _SKILL_KEYWORDS if kw in query_lower}
    return sorted(kw for kw in query_skills if kw not in combined_text)


@router.post("/search")
async def search_resumes(
    request: SearchRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)

    if not creds["openrouter_key"]:
        return {"results": [], "error": "OpenRouter API key not configured. Please add it in Settings."}

    start_time = time.time()
    print(f"--- [Search Start] Query: '{request.query}' for user {user_id} ---")

    is_recruiter = role in ("recruiter", "manager")
    db_start = time.time()
    try:
        df = search_resumes_hybrid(
            request.query, user_id, limit=10,
            api_key=creds["openrouter_key"],
            is_recruiter=is_recruiter,
        )
    except Exception as e:
        print(f"DEBUG: [Search] Embedding/DB search failed: {e}")
        return {"results": [], "error": f"Search failed: {str(e)}"}

    db_end = time.time()
    print(f"DEBUG: LanceDB search took {db_end - db_start:.2f}s. Found {len(df)} results.")

    if df.empty:
        return {"results": []}

    # Aggregate chunks by filename, preserving semantic rank order
    aggregated: dict = {}
    for _, row in df.iterrows():
        fname = row["filename"]
        if fname not in aggregated:
            aggregated[fname] = []
        if row["text"] not in aggregated[fname]:
            aggregated[fname].append(row["text"])

    # Build scored results deterministically from rank position — no LLM needed
    results = []
    for rank, (fname, excerpts) in enumerate(aggregated.items(), start=1):
        score = _score_from_rank(rank)
        missing = _missing_skills(request.query, excerpts)
        results.append({
            "filename": fname,
            "score": score,
            "justification": f"Ranked #{rank} by semantic similarity to query.",
            "missing_skills": missing,
            "auto_screen": "SELECTED" if score > 70 else "WAITLIST",
        })

    total_time = time.time() - start_time
    print(f"--- [Search End] Total time: {total_time:.2f}s (no LLM re-rank) ---")
    return {"results": results}
