from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import json

from app.models import JobResponse, JobMatchResponse
from app.dependencies import get_current_user
from services.db.lancedb_client import get_or_create_jobs_table, get_or_create_table, get_embeddings_model

router = APIRouter(tags=["v1 — Matching"])

def _serialize_job(row: dict) -> dict:
    """Convert LanceDB row to JSON-serializable dict."""
    out = dict(row)
    out.pop("vector", None)
    
    # Ensure lists are lists
    for field in ["skills_required", "benefits"]:
        val = out.get(field, [])
        if val is None:
            out[field] = []
        elif hasattr(val, "tolist"):
            out[field] = val.tolist()
    
    return out

@router.get("/resume/{resume_id}", response_model=List[JobMatchResponse])
async def match_jobs_for_resume(
    resume_id: str,
    limit: int = 50,
    user_id: str = Depends(get_current_user)
):
    """Find jobs that match a specific resume using vector similarity."""
    resumes_table = get_or_create_table()
    # Find the specific resume chunk
    res_results = resumes_table.search().where(f"id = '{resume_id}'").limit(1).to_list()
    if not res_results:
        # Try to find by user_id if ID not found directly (simple fallback)
        res_results = resumes_table.search().where(f"user_id = '{user_id}'").limit(1).to_list()
        
    if not res_results:
        raise HTTPException(status_code=404, detail="No resume chunks found for matching")
    
    resume_vec = res_results[0]["vector"]
    
    jobs_table = get_or_create_jobs_table()
    results = jobs_table.search(resume_vec).metric("cosine").limit(limit).to_list()
    
    matches = []
    for r in results:
        # Cosine distance is 1 - cosine similarity
        dist = r.get("_distance", 1.0)
        score = max(0.0, 1.0 - float(dist))
        matches.append({
            "score": score,
            "job": _serialize_job(r)
        })
    
    return matches

@router.get("/search/jobs", response_model=List[JobMatchResponse])
async def search_jobs(
    q: str,
    limit: int = 50,
    job_level: Optional[str] = None,
    job_category: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """Semantic search for jobs using natural language query."""
    embeddings = get_embeddings_model()
    try:
        query_vec = embeddings.embed_query(q)
    except Exception as e:
        print(f"DEBUG: [match] Embedding failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate query embedding")
    
    jobs_table = get_or_create_jobs_table()
    search = jobs_table.search(query_vec).metric("cosine")
    
    filters = []
    if job_level:
        filters.append(f"job_level = '{job_level}'")
    if job_category:
        filters.append(f"job_category = '{job_category}'")
    
    if filters:
        search = search.where(" AND ".join(filters))
    
    results = search.limit(limit).to_list()
    
    matches = []
    for r in results:
        dist = r.get("_distance", 1.0)
        score = max(0.0, 1.0 - float(dist))
        matches.append({
            "score": score,
            "job": _serialize_job(r)
        })
    
    return matches
