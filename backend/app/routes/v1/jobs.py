from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
import uuid
from datetime import datetime
from typing import List, Optional
import json

from app.dependencies import get_current_user
from app.models import JobCreate, JobResponse
from services.db.lancedb_client import get_or_create_jobs_table, get_embeddings_model, get_or_create_job_applied_table

router = APIRouter(tags=["v1 — Jobs"])

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

@router.post("/parse-upload")
async def parse_job_upload(file: UploadFile = File(...)):
    content = await file.read()
    # Simple mock parsing for now - in production this would use docx/txt parsers
    try:
        text = content.decode('utf-8', errors='replace')
    except Exception:
        text = "Failed to parse file content."
    
    # Very simple extraction
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    title = lines[0] if lines else "Job Opening"
    
    return {
        "title": title,
        "description": text,
        "skills_required": [], # Placeholder
        "job_level": "MID",
    }

@router.post("", response_model=JobResponse)
async def create_job(job: JobCreate, user_id: str = Depends(get_current_user)):
    table = get_or_create_jobs_table()
    
    job_dict = job.model_dump()
    job_id = str(uuid.uuid4())
    job_dict["job_id"] = job_id
    job_dict["user_id"] = user_id
    job_dict["posted_date"] = datetime.now().isoformat()
    
    # Generate embedding for the job
    try:
        embeddings = get_embeddings_model()
        skills_text = ", ".join(job_dict.get("skills_required", []))
        embed_text = f"{job_dict['title']}\n{job_dict['description']}\nSkills: {skills_text}"
        vector = embeddings.embed_query(embed_text)
        job_dict["vector"] = vector
    except Exception as e:
        print(f"DEBUG: [jobs] Embedding failed: {e}")
        job_dict["vector"] = [0.0] * 1536
    
    table.add([job_dict])
    return _serialize_job(job_dict)

@router.get("", response_model=List[JobResponse])
async def list_jobs(
    skip: int = 0,
    limit: int = 20,
    job_level: Optional[str] = None,
    job_category: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    table = get_or_create_jobs_table()
    query = table.search()
    
    filters = [f"user_id = '{user_id}'"]
    if job_level:
        filters.append(f"job_level = '{job_level}'")
    if job_category:
        filters.append(f"job_category = '{job_category}'")
    
    query = query.where(" AND ".join(filters))
    
    results = query.limit(limit + skip).to_list()
    return [_serialize_job(r) for r in results[skip:skip + limit]]

# New endpoint to fetch applied jobs for the current user
@router.get("/my-applied", response_model=List[dict])
async def get_applied_jobs(user_id: str = Depends(get_current_user)):
    # Retrieve applied records
    applied_table = get_or_create_job_applied_table()
    applied_records = applied_table.search().where(f"user_id = '{user_id}'").to_list()
    
    if not applied_records:
        return []

    # Retrieve job details for each applied record
    jobs_table = get_or_create_jobs_table()
    result = []
    for rec in applied_records:
        job_id = rec.get('job_id')
        job_rows = jobs_table.search().where(f"job_id = '{job_id}'").limit(1).to_list()
        
        if job_rows:
            job = job_rows[0]
            # Serialize job without vector
            job_serialized = {k: v for k, v in job.items() if k != 'vector'}
            # Combine with applied info
            combined = {
                "job_id": job_id,
                "title": job_serialized.get('title'),
                "company": job_serialized.get('employer_name'),
                "location": job_serialized.get('location_name'),
                "posted_date": job_serialized.get('posted_date'),
                "resume_id": rec.get('resume_id'),
                "applied_at": rec.get('timestamp'),
                "applied_status": rec.get('applied_status', 'applied')
            }
            result.append(combined)
    return result

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user_id: str = Depends(get_current_user)):
    table = get_or_create_jobs_table()
    results = table.search().where(f"job_id = '{job_id}' AND user_id = '{user_id}'").limit(1).to_list()
    if not results:
        raise HTTPException(status_code=404, detail="Job not found")
    return _serialize_job(results[0])

@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, job: JobCreate, user_id: str = Depends(get_current_user)):
    table = get_or_create_jobs_table()
    existing = table.search().where(f"job_id = '{job_id}' AND user_id = '{user_id}'").limit(1).to_list()
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")
    
    updated = job.model_dump()
    updated["job_id"] = job_id
    updated["user_id"] = user_id
    updated["posted_date"] = existing[0]["posted_date"]
    
    # Re-generate embedding
    try:
        embeddings = get_embeddings_model()
        skills_text = ", ".join(updated.get("skills_required", []))
        embed_text = f"{updated['title']}\n{updated['description']}\nSkills: {skills_text}"
        vector = embeddings.embed_query(embed_text)
        updated["vector"] = vector
    except Exception as e:
        print(f"DEBUG: [jobs] Embedding failed: {e}")
        updated["vector"] = existing[0]["vector"]
    
    table.delete(f"job_id = '{job_id}'")
    table.add([updated])
    return _serialize_job(updated)

@router.delete("/{job_id}")
async def delete_job(job_id: str, user_id: str = Depends(get_current_user)):
    table = get_or_create_jobs_table()
    existing = table.search().where(f"job_id = '{job_id}' AND user_id = '{user_id}'").limit(1).to_list()
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")
    
    table.delete(f"job_id = '{job_id}'")
    return {"message": "Deleted"}

@router.post("/{job_id}/apply")
async def apply_job(job_id: str, resume_id: str = Query(...), user_id: str = Depends(get_current_user)):
    from services.db.lancedb_client import apply_for_job
    try:
        success = apply_for_job(user_id, job_id, resume_id)
        if success:
            return {"message": "Successfully applied for job"}
        else:
            return {"message": "Already applied for job"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

