from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Header
import uuid
import os
import shutil
from datetime import datetime
from typing import List, Optional
import json
from pathlib import Path

from app.dependencies import get_current_user, resolve_credentials
from app.models import JobCreate, JobResponse
from app.config import UPLOAD_DIR
from services.db.lancedb_client import get_or_create_jobs_table, get_embeddings_model, get_or_create_job_applied_table
from services.resume_parser import extract_text
from services.ai.common import clean_json_output

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
async def parse_job_upload(
    file: UploadFile = File(...),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    
    # 1. Save file temporarily
    temp_filename = f"jd_parse_{uuid.uuid4()}_{file.filename}"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 2. Extract text using proper parser
        text = extract_text(temp_path)
        if not text.strip():
            return {"error": "Could not extract text from file."}

        # 3. Use AI to structure the JD
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import PromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        prompt = PromptTemplate(
            input_variables=["text"],
            template="""Analyze this job description text and extract structured information.
            
            TEXT:
            {text}
            
            Return ONLY a JSON object:
            {{
              "title": "Exact job title",
              "employer_name": "Name of company/employer",
              "location_name": "City, Country or Remote",
              "description": "Full job description (preserve formatting)",
              "skills_required": ["skill1", "skill2"],
              "job_level": "JUNIOR", "MID", or "SENIOR"
            }}"""
        )

        llm = ChatOpenAI(
            model=creds["llm_model"] or "gpt-4o-mini",
            api_key=creds["openrouter_key"] or os.getenv("OPEN_ROUTER_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )

        chain = prompt | llm | StrOutputParser()
        raw_res = chain.invoke({"text": text[:10000]}) # Limit text length for safety
        
        clean_res = clean_json_output(raw_res)
        structured = json.loads(clean_res)
        
        return structured

    except Exception as e:
        print(f"DEBUG: [jobs] Parse failed: {e}")
        return {
            "title": file.filename.split('.')[0],
            "description": "Failed to parse automatically. Please paste content here.",
            "skills_required": [],
            "job_level": "MID"
        }
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

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

