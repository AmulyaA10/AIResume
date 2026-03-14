from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Header, BackgroundTasks
import uuid
import os
import shutil
from datetime import datetime
from typing import List, Optional
import json
from pathlib import Path

from app.dependencies import get_current_user, get_user_role, resolve_credentials
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
    
    # Default salary_currency for rows created before this field existed
    if not out.get("salary_currency"):
        out["salary_currency"] = "USD"

    # Ensure lists are lists
    for field in ["skills_required", "benefits"]:
        val = out.get(field, [])
        if val is None:
            out[field] = []
        elif hasattr(val, "tolist"):
            out[field] = val.tolist()
    
    return out

_ALLOWED_JOB_EXTENSIONS = {".pdf", ".docx", ".txt"}
_PLACEHOLDER_VALUES = {"", "unknown", "n/a", "none", "null", "not specified", "not provided"}


def _is_placeholder(value: str) -> bool:
    return not value or value.strip().lower() in _PLACEHOLDER_VALUES


@router.post("/parse-upload")
async def parse_job_upload(
    file: UploadFile = File(...),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    # 1. File type validation
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_JOB_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{ext}'. "
                "Only PDF (.pdf), Word documents (.docx), and plain text files (.txt) are accepted."
            )
        )

    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)

    # 2. Save file temporarily
    temp_filename = f"jd_parse_{uuid.uuid4()}_{file.filename}"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 3. Extract text
        text = extract_text(temp_path)

        if not text or not text.strip():
            raise HTTPException(
                status_code=422,
                detail="The file appears to be empty or contains no readable text."
            )

        if len(text.strip()) < 100:
            raise HTTPException(
                status_code=422,
                detail=(
                    "The file content is too short to be a valid job description. "
                    "Please provide a document with a full job title, description, and employer details."
                )
            )

        # 4. Use AI to structure the JD
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
        raw_res = chain.invoke({"text": text[:10000]})

        clean_res = clean_json_output(raw_res)
        structured = json.loads(clean_res)

        # 5. Content validation — ensure required job fields were extracted
        missing = []
        if _is_placeholder(structured.get("title", "")):
            missing.append("job title")
        if _is_placeholder(structured.get("employer_name", "")):
            missing.append("employer / company name")
        if not structured.get("description") or len(structured["description"].strip()) < 50:
            missing.append("job description")

        if missing:
            raise HTTPException(
                status_code=422,
                detail=(
                    "The document does not contain sufficient job information. "
                    f"Could not extract: {', '.join(missing)}. "
                    "Please ensure the file includes a job title, a description of responsibilities, "
                    "and the employer or company name."
                )
            )

        return structured

    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: [jobs] Parse failed: {e}")
        raise HTTPException(
            status_code=422,
            detail=(
                "Failed to parse the job document. "
                "Please ensure the file contains valid job description content "
                "(job title, responsibilities, requirements, and employer details)."
            )
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.post("/parse-query-intent")
async def parse_query_intent(
    body: dict,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
):
    """Use an LLM to parse a natural-language job search query into structured intent.

    Returns:
        location        — canonical location string or null
        locationAliases — substrings to match against job location_name fields
        topN            — integer limit or null
        sortBySalary    — true if user wants highest-paid jobs
        cleanQuery      — query stripped of intent tokens, suitable for vector search
    """
    query = (body.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    llm = ChatOpenAI(
        model=creds["llm_model"] or "gpt-4o-mini",
        api_key=creds["openrouter_key"] or os.getenv("OPEN_ROUTER_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a job search query parser. Given a natural-language query, extract structured intent.\n\n"
         "Return ONLY valid JSON with these fields (no markdown, no explanation):\n"
         "{{\n"
         '  "location": <canonical location string in lowercase, or null>,\n'
         '  "locationAliases": <array of 4-8 lowercase substrings that uniquely identify this location in job posting strings. '
         "IMPORTANT: avoid short ambiguous abbreviations (e.g. do NOT use 'ca' for California — it matches 'canada'; "
         "do NOT use 'ny' alone — use ', ny' or 'new york'). Prefer full city/region names and metro area labels.>,\n"
         '  "topN": <integer if user wants top N results, else null>,\n'
         '  "sortBySalary": <true if user wants highest-paid / best-paying / top salary jobs, else false>,\n'
         '  "cleanQuery": <the query with all intent tokens removed, keeping only the job-type signal. If nothing meaningful remains, use a sensible default like "software engineering jobs".>\n'
         "}}\n\n"
         "Examples:\n"
         '  "top paid 5 jobs in california" → {{"location":"california","locationAliases":["san francisco","bay area","los angeles","silicon valley","west coast","sacramento"],"topN":5,"sortBySalary":true,"cleanQuery":"software engineering jobs"}}\n'
         '  "best paying data scientist roles in NYC" → {{"location":"new york","locationAliases":["new york city","manhattan","brooklyn","new york"],"topN":null,"sortBySalary":true,"cleanQuery":"data scientist"}}\n'
         '  "remote python developer" → {{"location":null,"locationAliases":[],"topN":null,"sortBySalary":false,"cleanQuery":"remote python developer"}}'
        ),
        ("human", "Query: {query}"),
    ])
    chain = prompt | llm | StrOutputParser()
    raw = await chain.ainvoke({"query": query})
    try:
        result = json.loads(raw.strip())
        # Ensure required fields with safe defaults
        result.setdefault("location", None)
        result.setdefault("locationAliases", [])
        result.setdefault("topN", None)
        result.setdefault("sortBySalary", False)
        result.setdefault("cleanQuery", query)
    except Exception:
        result = {
            "location": None,
            "locationAliases": [],
            "topN": None,
            "sortBySalary": False,
            "cleanQuery": query,
        }

    return result


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

@router.get("/public", response_model=List[JobResponse])
async def list_public_jobs(
    skip: int = 0,
    limit: int = 50,
    user_id: str = Depends(get_current_user)
):
    """Return all jobs for job seekers to browse (no user_id filter)."""
    table = get_or_create_jobs_table()
    try:
        results = table.search().limit(limit + skip).to_list()
        return [_serialize_job(r) for r in results[skip:skip + limit]]
    except Exception:
        return []

@router.get("", response_model=List[JobResponse])
async def list_jobs(
    skip: int = 0,
    limit: int = 20,
    job_level: Optional[str] = None,
    job_category: Optional[str] = None,
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    table = get_or_create_jobs_table()
    query = table.search()

    is_recruiter = role in ("recruiter", "manager")
    filters = [] if is_recruiter else [f"user_id = '{user_id}'"]
    if job_level:
        filters.append(f"job_level = '{job_level}'")
    if job_category:
        filters.append(f"job_category = '{job_category}'")

    if filters:
        query = query.where(" AND ".join(filters))
    
    results = query.limit(limit + skip).to_list()
    jobs = [_serialize_job(r) for r in results[skip:skip + limit]]
    
    # Add applied_count to each job
    applied_table = get_or_create_job_applied_table()
    try:
        applied_df = applied_table.to_pandas()
        if not applied_df.empty:
            for job in jobs:
                job["applied_count"] = len(applied_df[applied_df['job_id'] == job['job_id']])
    except Exception as e:
        print(f"DEBUG: Error calculating applied_counts: {e}")

    return jobs

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
async def get_job(job_id: str, user_id: str = Depends(get_current_user), role: str = Depends(get_user_role)):
    table = get_or_create_jobs_table()
    is_recruiter = role in ("recruiter", "manager")
    where = f"job_id = '{job_id}'" if is_recruiter else f"job_id = '{job_id}' AND user_id = '{user_id}'"
    results = table.search().where(where).limit(1).to_list()
    if not results:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_dict = _serialize_job(results[0])
    
    applied_table = get_or_create_job_applied_table()
    try:
        applied_df = applied_table.to_pandas()
        if not applied_df.empty:
            job_dict["applied_count"] = len(applied_df[applied_df['job_id'] == job_id])
    except Exception as e:
        print(f"DEBUG: Error calculating applied_count for {job_id}: {e}")
        
    return job_dict

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

@router.get("/{job_id}/candidates", response_model=List[dict])
async def get_job_candidates(job_id: str, user_id: str = Depends(get_current_user), role: str = Depends(get_user_role)):
    # 1. Verify user owns the job (recruiters/managers can access any job)
    jobs_table = get_or_create_jobs_table()
    is_recruiter = role in ("recruiter", "manager")
    where = f"job_id = '{job_id}'" if is_recruiter else f"job_id = '{job_id}' AND user_id = '{user_id}'"
    jobs = jobs_table.search().where(where).limit(1).to_list()
    if not jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # 2. Get applied candidates
    applied_table = get_or_create_job_applied_table()
    applied_records = applied_table.search().where(f"job_id = '{job_id}'").to_list()
    
    result = []
    for rec in applied_records:
        result.append({
            "resume_id": rec.get('resume_id'),
            "candidate_user_id": rec.get('user_id'),
            "applied_at": rec.get('timestamp'),
            "applied_status": rec.get('applied_status', 'applied')
        })
    return result
    
from pydantic import BaseModel
class StatusUpdate(BaseModel):
    status: str

@router.put("/{job_id}/candidates/{resume_id}/status")
async def update_candidate_status(job_id: str, resume_id: str, status_data: StatusUpdate, user_id: str = Depends(get_current_user)):
    # 1. Verify user owns the job
    jobs_table = get_or_create_jobs_table()
    jobs = jobs_table.search().where(f"job_id = '{job_id}' AND user_id = '{user_id}'").limit(1).to_list()
    if not jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    safe_resume_id = resume_id.replace("'", "''")
        
    # 2. Update status
    applied_table = get_or_create_job_applied_table()
    try:
        df = applied_table.to_pandas()
        if not df.empty:
            mask = (df['job_id'] == job_id) & (df['resume_id'] == resume_id)
            rows = df[mask].copy()
            if not rows.empty:
                applied_table.delete(f"job_id = '{job_id}' AND resume_id = '{safe_resume_id}'")
                rows['applied_status'] = status_data.status
                applied_table.add(rows.to_dict('records'))
                return {"message": "Status updated successfully", "status": status_data.status}
    except Exception as e:
        print(f"DEBUG: Error updating status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update application status")
        
    raise HTTPException(status_code=404, detail="Application not found")

@router.post("/{job_id}/apply")
async def apply_job(job_id: str, background_tasks: BackgroundTasks, resume_id: str = Query(...), user_id: str = Depends(get_current_user)):
    from services.db.lancedb_client import apply_for_job, get_or_create_jobs_table, get_or_create_table
    from services.email_service import send_employer_notification
    try:
        success = apply_for_job(user_id, job_id, resume_id)
        if success:
            # Fetch job details to get employer_email
            jobs_table = get_or_create_jobs_table()
            job_results = jobs_table.search().where(f"job_id = '{job_id}'").limit(1).to_list()
            if job_results and job_results[0].get("employer_email"):
                job_ref = job_results[0]
                employer_email = job_ref["employer_email"]
                job_title = job_ref.get("title", "Unknown Job Title")

                # Fetch resume text
                resumes_table = get_or_create_table()
                resume_results = resumes_table.search().where(f"filename = '{resume_id}' AND user_id = '{user_id}'").to_pandas()
                
                resume_text = ""
                if not resume_results.empty:
                    # Chunks are stored, concatenate them
                    resume_text = "\n".join(resume_results['text'].tolist())

                # Queue the email notification in the background
                if employer_email:
                    background_tasks.add_task(send_employer_notification, employer_email, job_title, user_id, resume_id, resume_text)

            return {"message": "Successfully applied for job"}
        else:
            return {"message": "Already applied for job"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

