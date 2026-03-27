from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Header, BackgroundTasks
import re
import uuid
import os
import shutil
from datetime import datetime
from typing import List, Optional
import json
from collections import OrderedDict as _OD
from pathlib import Path

from app.dependencies import get_current_user, get_user_role, resolve_credentials
from app.models import JobCreate, JobResponse
from app.config import UPLOAD_DIR
from app.routes.v1.resumes import _normalize_location, _city_to_metro, _classify_region, _METRO_TO_SUBSTRINGS, _suburb_to_metro, _ai_metro_for_location
from app.common.skill_utils import canonicalize_skill
from app.common import build_llm_config
from services.db.lancedb_client import get_or_create_jobs_table, get_embeddings_model, get_or_create_job_applied_table, search_jobs_hybrid
from services.resume_parser import extract_text
from services.ai.common import clean_json_output

router = APIRouter(tags=["v1 — Jobs"])


async def _screen_all_resumes_for_job(
    job_dict: dict,
    manager_user_id: str,
    llm_config: dict,
) -> None:
    """Background task: when a new JD is created, screen all existing resumes against it."""
    try:
        from services.db.lancedb_client import (
            get_or_create_resume_meta_table,
            get_or_create_job_applied_table,
            get_user_settings,
        )
        from services.ai.screening_graph import build_screening_graph
        from services.email_service import send_candidate_shortlisted
        from services.resume_parser import extract_text, to_ats_text
        import asyncio
        from datetime import datetime

        cfg = get_user_settings(manager_user_id) or {}
        threshold = int(cfg.get("agent_threshold", 70))
        max_resumes = int(cfg.get("agent_max_jds", 20))  # reuse same cap setting

        job_id = job_dict.get("job_id", "")
        job_title = job_dict.get("title", "")
        employer_name = job_dict.get("employer_name", "")
        jd_text = "\n".join(filter(None, [
            job_title and f"Job Title: {job_title}",
            employer_name and f"Company: {employer_name}",
            job_dict.get("description"),
        ]))

        if not jd_text.strip():
            print(f"DEBUG: [jd-screen] No JD text for {job_id} — skipping")
            return

        # Load all resume metadata (user_id + filename + email)
        meta_table = get_or_create_resume_meta_table()
        meta_df = meta_table.to_pandas()
        if meta_df.empty:
            print(f"DEBUG: [jd-screen] No resumes found — skipping for job {job_id}")
            return

        # Deduplicate by filename, take most recent, cap count
        meta_df = meta_df.drop_duplicates(subset=["filename"], keep="last").head(max_resumes)
        print(f"DEBUG: [jd-screen] Screening {len(meta_df)} resumes against new JD '{job_title}'")

        graph = build_screening_graph()

        async def _screen_one(row):
            filename = str(row.get("filename", ""))
            candidate_user_id = str(row.get("user_id", ""))
            resume_text = ""
            try:
                file_path = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(file_path):
                    resume_text = to_ats_text(extract_text(file_path))
            except Exception:
                pass
            if not resume_text.strip():
                return None
            try:
                result = await graph.ainvoke({
                    "resume_text": resume_text,
                    "jd_text": jd_text,
                    "threshold": threshold,
                    "score": None,
                    "decision": None,
                    "config": llm_config,
                })
                selected = (result.get("decision") or {}).get("selected", False)
                if not selected:
                    return None
                return {
                    "user_id": candidate_user_id,
                    "filename": filename,
                    "email": str(row.get("email") or ""),
                    "name": str(row.get("candidate_name") or ""),
                }
            except Exception as e:
                print(f"DEBUG: [jd-screen] screening {filename} failed: {e}")
                return None

        results = await asyncio.gather(*[_screen_one(row) for _, row in meta_df.iterrows()])
        shortlisted = [r for r in results if r]

        if not shortlisted:
            print(f"DEBUG: [jd-screen] No matches for job '{job_title}'")
            return

        # Persist auto_shortlisted records
        applied_table = get_or_create_job_applied_table()
        rows_to_add = []
        for r in shortlisted:
            rows_to_add.append({
                "id": str(__import__("uuid").uuid4()),
                "user_id": r["user_id"],
                "job_id": job_id,
                "resume_id": r["filename"],
                "applied_status": "auto_shortlisted",
                "timestamp": datetime.now().isoformat(),
                "notified": False,
                "notified_at": "",
            })
        import pandas as pd
        applied_table.add(pd.DataFrame(rows_to_add))
        print(f"DEBUG: [jd-screen] {len(shortlisted)} resumes shortlisted for '{job_title}'")

        # Email each shortlisted candidate
        for r in shortlisted:
            if r["email"]:
                send_candidate_shortlisted(
                    candidate_email=r["email"],
                    candidate_name=r["name"],
                    job_title=job_title,
                    employer_name=employer_name,
                )

    except Exception as e:
        print(f"DEBUG: [jd-screen] background task failed: {e}")


async def _auto_screen_application(
    user_id: str,
    job_id: str,
    resume_id: str,
    resume_text: str,
    job_ref: dict,
    llm_config: dict,
) -> None:
    """Background task: screen a candidate application and notify them of the decision."""
    try:
        from services.ai.screening_graph import build_screening_graph
        from services.db.lancedb_client import (
            get_or_create_job_applied_table,
            get_or_create_resume_meta_table,
            get_user_settings,
        )
        from services.email_service import send_candidate_decision
        from datetime import datetime

        # Read agent threshold from user settings (manager/recruiter config)
        cfg = get_user_settings(user_id) or {}
        threshold = int(cfg.get("agent_threshold", 70))

        jd_text = "\n".join(filter(None, [
            job_ref.get("title") and f"Job Title: {job_ref['title']}",
            job_ref.get("employer_name") and f"Company: {job_ref['employer_name']}",
            job_ref.get("description"),
        ]))

        graph = build_screening_graph()
        result = await graph.ainvoke({
            "resume_text": resume_text,
            "jd_text": jd_text,
            "threshold": threshold,
            "score": None,
            "decision": None,
            "config": llm_config,
        })

        score = (result.get("score") or {}).get("overall", 0)
        selected = (result.get("decision") or {}).get("selected", False)
        reason = (result.get("decision") or {}).get("reason", "")
        new_status = "selected" if selected else "rejected"

        # Update applied_status in DB
        applied_table = get_or_create_job_applied_table()
        try:
            df = applied_table.to_pandas()
            if not df.empty:
                mask = (df["user_id"] == user_id) & (df["job_id"] == job_id) & (df["resume_id"] == resume_id)
                if mask.any():
                    applied_table.delete(
                        f"user_id = '{user_id}' AND job_id = '{job_id}' AND resume_id = '{resume_id}'"
                    )
            applied_table.add([{
                "id": str(__import__("uuid").uuid4()),
                "user_id": user_id,
                "job_id": job_id,
                "resume_id": resume_id,
                "applied_status": new_status,
                "timestamp": datetime.now().isoformat(),
                "notified": False,
                "notified_at": "",
            }])
        except Exception as e:
            print(f"DEBUG: [apply-screen] Failed to update status: {e}")

        # Look up candidate email
        candidate_email = ""
        candidate_name = ""
        try:
            meta_table = get_or_create_resume_meta_table()
            rows = meta_table.search().where(
                f"filename = '{resume_id}' AND user_id = '{user_id}'"
            ).limit(1).to_list()
            if rows:
                candidate_email = str(rows[0].get("email") or "")
                candidate_name = str(rows[0].get("candidate_name") or "")
        except Exception:
            pass

        if candidate_email:
            send_candidate_decision(
                candidate_email=candidate_email,
                candidate_name=candidate_name,
                job_title=job_ref.get("title", ""),
                employer_name=job_ref.get("employer_name", ""),
                selected=selected,
                score=score,
                reason=reason,
            )
        else:
            print(f"DEBUG: [apply-screen] No email for {resume_id} — skipping candidate notification")

        print(f"DEBUG: [apply-screen] {resume_id} → {new_status} (score={score}%, threshold={threshold}%)")

    except Exception as e:
        print(f"DEBUG: [apply-screen] background screening failed: {e}")

def _serialize_job(row: dict) -> dict:
    """Convert LanceDB row to JSON-serializable dict."""
    out = dict(row)
    out.pop("vector", None)
    
    # Default salary_currency for rows created before this field existed
    if not out.get("salary_currency"):
        out["salary_currency"] = "USD"
    # Default positions for rows created before this field existed
    if not out.get("positions"):
        out["positions"] = 1

    # Ensure lists are lists
    for field in ["skills_required", "benefits"]:
        val = out.get(field, [])
        if val is None:
            out[field] = []
        elif hasattr(val, "tolist"):
            out[field] = val.tolist()

    # Parse skills_tiers JSON string → dict
    raw_tiers = out.get("skills_tiers")
    if isinstance(raw_tiers, dict):
        out["skills_tiers"] = raw_tiers
    elif isinstance(raw_tiers, str) and raw_tiers.strip() not in ("", "nan", "None"):
        try:
            out["skills_tiers"] = json.loads(raw_tiers)
        except (TypeError, ValueError):
            out["skills_tiers"] = None
    else:
        out["skills_tiers"] = None

    return out

_ALLOWED_JOB_EXTENSIONS = {".pdf", ".docx", ".txt"}
_PLACEHOLDER_VALUES = {"", "unknown", "n/a", "none", "null", "not specified", "not provided"}


def _is_placeholder(value: str) -> bool:
    return not value or value.strip().lower() in _PLACEHOLDER_VALUES


_JOB_LEVEL_MAP: dict = {
    "entry": "ENTRY", "entry level": "ENTRY", "entry-level": "ENTRY", "junior": "JUNIOR", "jr": "JUNIOR",
    "mid": "MID", "mid level": "MID", "mid-level": "MID", "intermediate": "MID",
    "senior": "SENIOR", "sr": "SENIOR", "sr.": "SENIOR",
    "lead": "LEAD", "tech lead": "LEAD",
    "principal": "PRINCIPAL", "staff": "STAFF",
    "director": "DIRECTOR", "vp": "VP", "vice president": "VP",
    "executive": "EXECUTIVE", "c-suite": "EXECUTIVE", "c suite": "EXECUTIVE",
}

_EMPLOYMENT_TYPE_MAP: dict = {
    "full time": "FULL_TIME", "full-time": "FULL_TIME", "fulltime": "FULL_TIME", "permanent": "FULL_TIME",
    "part time": "PART_TIME", "part-time": "PART_TIME", "parttime": "PART_TIME",
    "contract": "CONTRACT", "contractor": "CONTRACT", "freelance": "CONTRACT",
    "hybrid": "HYBRID",
    "remote": "REMOTE",
    "internship": "INTERNSHIP", "intern": "INTERNSHIP",
}


def _normalize_job_fields(job_dict: dict) -> dict:
    """Normalize job fields: title, location, job_level, employment_type, skills."""
    # Title — strip parenthetical specializations and em-dash suffixes
    if job_dict.get("title"):
        title = job_dict["title"].strip()
        title = re.sub(r'\s*\(.*?\)\s*$', '', title).strip()   # "Engineer (Python/Go)" → "Engineer"
        title = re.sub(r'\s*—.*$', '', title).strip()           # "Engineer — Remote" → "Engineer"
        title = re.sub(r'\s*-\s*(Remote|Hybrid|Onsite)\s*$', '', title, flags=re.IGNORECASE).strip()
        job_dict["title"] = title

    # Location
    if job_dict.get("location_name"):
        job_dict["location_name"] = _normalize_location(job_dict["location_name"]) or job_dict["location_name"]

    # Job level
    if job_dict.get("job_level"):
        normalized = _JOB_LEVEL_MAP.get(job_dict["job_level"].strip().lower())
        if normalized:
            job_dict["job_level"] = normalized
        else:
            job_dict["job_level"] = job_dict["job_level"].strip().upper()

    # Employment type
    if job_dict.get("employment_type"):
        normalized = _EMPLOYMENT_TYPE_MAP.get(job_dict["employment_type"].strip().lower())
        if normalized:
            job_dict["employment_type"] = normalized
        else:
            job_dict["employment_type"] = job_dict["employment_type"].strip().upper().replace(" ", "_")

    # Skills — canonicalize casing, deduplicate preserving order
    if job_dict.get("skills_required"):
        seen: set = set()
        cleaned = []
        for s in job_dict["skills_required"]:
            canonical = canonicalize_skill(s)
            if canonical and canonical.lower() not in seen:
                seen.add(canonical.lower())
                cleaned.append(canonical)
        job_dict["skills_required"] = cleaned

    # skills_tiers — normalize each tier, deduplicate globally across tiers
    _VALID_TIERS = ("must_have", "strong", "experience", "knowledge", "familiarity", "nice_to_have")
    raw_tiers = job_dict.get("skills_tiers")
    if isinstance(raw_tiers, str):
        try:
            raw_tiers = json.loads(raw_tiers)
        except (TypeError, ValueError):
            raw_tiers = None
    if isinstance(raw_tiers, dict):
        global_seen: set = set()
        normalized_tiers: dict = {}
        for tier_key in _VALID_TIERS:
            tier_skills = raw_tiers.get(tier_key) or []
            tier_cleaned = []
            for s in tier_skills:
                canonical = canonicalize_skill(s)
                if canonical and canonical.lower() not in global_seen:
                    global_seen.add(canonical.lower())
                    tier_cleaned.append(canonical)
            if tier_cleaned:
                normalized_tiers[tier_key] = tier_cleaned
        job_dict["skills_tiers"] = json.dumps(normalized_tiers) if normalized_tiers else None
    else:
        job_dict["skills_tiers"] = None

    return job_dict


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
              "skills_tiers": {{
                "must_have": ["skills explicitly required or mandatory"],
                "strong": ["skills listed as strongly preferred or a strong background in"],
                "experience": ["skills listed as experience with or X years of experience in"],
                "knowledge": ["skills listed as knowledge of or understanding of"],
                "familiarity": ["skills listed as familiarity with or exposure to"],
                "nice_to_have": ["skills listed as nice to have, a plus, or bonus"]
              }},
              "skills_required": ["union of all tiers — all skills mentioned"],
              "job_level": "JUNIOR", "MID", or "SENIOR"
            }}

            Classify each skill into the tier that best matches the JD wording:
            - must_have: required, must have, essential, proficiency in
            - strong: strongly preferred, strong background, deep experience
            - experience: experience with, X+ years of experience in, hands-on experience
            - knowledge: knowledge of, understanding of, solid grasp of
            - familiarity: familiarity with, exposure to, working knowledge of
            - nice_to_have: nice to have, a plus, bonus, preferred but not required
            Omit a tier key entirely if no skills fall into it."""
        )

        llm = ChatOpenAI(
            model=creds["llm_model"] or "gpt-4o-mini",
            api_key=creds["openrouter_key"],
            base_url="https://openrouter.ai/api/v1"
        )

        import asyncio as _asyncio
        from services.ai.jd_quality_graph import check_jd_quality

        llm_config = {"api_key": creds["openrouter_key"], "model": creds["llm_model"] or "gpt-4o-mini"}

        # Run JD structuring and quality check concurrently
        async def _parse_jd():
            chain = prompt | llm | StrOutputParser()
            return await chain.ainvoke({"text": text[:10000]})

        raw_res, quality_report = await _asyncio.gather(
            _parse_jd(),
            check_jd_quality(text[:8000], llm_config),
        )

        clean_res = clean_json_output(raw_res)
        structured = json.loads(clean_res)

        # Fallback: if LLM didn't return tiers, put all skills in must_have
        if not structured.get("skills_tiers"):
            skills = structured.get("skills_required", [])
            if skills:
                structured["skills_tiers"] = {"must_have": skills}

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

        normalized = _normalize_job_fields(structured)
        normalized["jd_quality"] = quality_report
        return normalized

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

# ---------------------------------------------------------------------------
# Parse-query-intent cache — avoids redundant LLM calls for the same query.
# Keyed by (query_lower, llm_model).  Max 256 entries, LRU eviction.
# ---------------------------------------------------------------------------
_JOB_INTENT_CACHE: "_OD[tuple, dict]" = _OD()
_JOB_INTENT_CACHE_MAX = 256

def _job_intent_cache_get(key: tuple):
    if key in _JOB_INTENT_CACHE:
        _JOB_INTENT_CACHE.move_to_end(key)
        return _JOB_INTENT_CACHE[key]
    return None

def _job_intent_cache_set(key: tuple, value: dict) -> None:
    _JOB_INTENT_CACHE[key] = value
    _JOB_INTENT_CACHE.move_to_end(key)
    if len(_JOB_INTENT_CACHE) > _JOB_INTENT_CACHE_MAX:
        _JOB_INTENT_CACHE.popitem(last=False)


_KNOWN_JOB_COMPANY_TERMS: dict[str, list[str]] = {
    "apple": ["apple"],
    "google": ["google"],
    "microsoft": ["microsoft"],
    "amazon": ["amazon"],
    "meta": ["meta"],
    "facebook": ["meta"],
    "netflix": ["netflix"],
    "nvidia": ["nvidia"],
    "openai": ["openai"],
    "fang": ["google", "meta", "amazon", "netflix"],
    "faang": ["google", "meta", "amazon", "apple", "netflix"],
    "faang+": ["google", "meta", "amazon", "apple", "netflix", "microsoft", "nvidia"],
    "big tech": ["google", "microsoft", "amazon", "apple", "meta"],
}


def _extract_job_company_filter(query: str) -> list[str]:
    """Extract company names from a query string using keyword matching."""
    q = query.lower()
    for key, companies in _KNOWN_JOB_COMPANY_TERMS.items():
        if key in q:
            return companies
    return []


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
    if not creds["openrouter_key"]:
        # No API key — return a basic fallback intent so the caller can still search
        return {
            "location": None,
            "locationAliases": [],
            "companyFilter": _extract_job_company_filter(query),
            "topN": None,
            "sortBySalary": False,
            "cleanQuery": query,
        }

    # Cache hit — skip LLM entirely
    llm_model = creds["llm_model"] or "gpt-4o-mini"
    _cache_key = (query.lower(), llm_model)
    cached = _job_intent_cache_get(_cache_key)
    if cached is not None:
        return cached

    llm = ChatOpenAI(
        model=llm_model,
        api_key=creds["openrouter_key"],
        base_url="https://openrouter.ai/api/v1",
        timeout=15,
    ).bind(response_format={"type": "json_object"})
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a job search query parser. Given a natural-language query, extract structured intent.\n\n"
         "KEY RULE 1 — company keyword expansion: whenever the query contains an acronym, abbreviation, or group name "
         "for companies, expand it to explicit employer names before filling companyFilter. Examples:\n"
         "  FANG/FAANG → google meta amazon apple netflix microsoft\n"
         "  Big 4 (consulting) → deloitte pwc ernst kpmg\n"
         "  Big 3 / MBB → mckinsey bain bcg\n"
         "  Big Tech / MANGA / FAANG+ → google microsoft amazon apple meta nvidia openai\n"
         "  WITCH → wipro infosys tcs cognizant hcl\n"
         "  SWE → software engineer  |  PM → product manager  |  MLE → machine learning engineer\n"
         "  ML → machine learning  |  NLP → natural language processing  |  CV → computer vision\n\n"
         "KEY RULE 2 — geographic region expansion: when the query mentions a macro region or sub-region, "
         "expand it to the specific location substrings that appear in job posting location strings. "
         "Use these expansions (choose the 6-8 most relevant):\n"
         "  Asia            → india, singapore, japan, china, hong kong, south korea, tokyo, bangalore, hyderabad, mumbai, beijing, shanghai, seoul, taipei, jakarta, kuala lumpur\n"
         "  Southeast Asia  → singapore, vietnam, thailand, philippines, malaysia, indonesia, jakarta, kuala lumpur, ho chi minh, bangkok\n"
         "  South Asia      → india, bangalore, hyderabad, mumbai, delhi, pune, chennai, kolkata, pakistan, sri lanka\n"
         "  Europe          → london, uk, germany, france, netherlands, sweden, ireland, switzerland, italy, spain, berlin, paris, amsterdam, stockholm, dublin, munich, barcelona, zurich, warsaw, prague\n"
         "  North America   → usa, canada, mexico, toronto, vancouver, montreal\n"
         "  USA (whole)     → usa, , ca, , ny, , tx, , wa, , il, , fl, , ga, , ma, , co\n"
         "  West Coast      → san francisco, los angeles, seattle, , ca, , wa, , or, portland, silicon valley, bay area\n"
         "  California      → san francisco, , ca, los angeles, silicon valley, bay area, san jose, sacramento\n"
         "  Southern California / SoCal → los angeles, san diego, orange county, irvine, anaheim, riverside, pasadena, long beach, santa monica, burbank, san bernardino, , ca\n"
         "  Northern California / NorCal / Bay Area / Silicon Valley → san francisco, palo alto, mountain view, sunnyvale, san jose, santa clara, menlo park, oakland, berkeley, cupertino, redwood city, , ca\n"
         "  IMPORTANT: 'Southern California' and 'SoCal' do NOT include San Francisco, Bay Area, Silicon Valley, or Seattle. 'Northern California/Bay Area/Silicon Valley' do NOT include Los Angeles, San Diego, Seattle.\n"
         "  East Coast      → new york, boston, washington, philadelphia, miami, atlanta, , ny, , ma, , dc, , pa, , fl, , ga\n"
         "  Midwest USA     → chicago, detroit, minneapolis, cleveland, columbus, milwaukee, st. louis, kansas city, , il, , mi, , oh, , mn, , wi, , in, , mo\n"
         "  South USA       → dallas, houston, austin, atlanta, miami, charlotte, nashville, , tx, , ga, , fl, , nc, , tn\n"
         "  Middle East     → dubai, uae, saudi, israel, qatar, bahrain, abu dhabi, riyadh\n"
         "  Africa          → south africa, nigeria, kenya, egypt, johannesburg, lagos, nairobi, cairo\n"
         "  Australia       → australia, new zealand, sydney, melbourne, brisbane, auckland, perth\n"
         "  Latin America   → brazil, argentina, colombia, chile, sao paulo, bogota, buenos aires, lima\n\n"
         "Return ONLY valid JSON with these fields (no markdown, no explanation):\n"
         "{{\n"
         '  "location": <canonical region/location name in lowercase, or null>,\n'
         '  "locationAliases": <array of lowercase substrings a job location must contain at least one of. '
         "RULE: For a specific CITY query (Los Angeles, Seattle, Austin) use ONLY the city name and its metro keywords — "
         "do NOT include the state abbreviation (', ca', ', wa') because that would match ALL cities in the state. "
         "For a broad STATE or REGION query (California, West Coast) use the state abbreviation (', ca') to match any city in the state. "
         "For sub-regions (Southern California, Bay Area) use the state abbreviation plus exclusions to remove the opposite sub-region.>,\n"
         '  "locationExclusions": <array of lowercase substrings — any job whose location contains one of these '
         "is excluded. Use for sub-region searches to remove the opposite sub-region. "
         "E.g. SoCal: exclude NorCal cities. Bay Area: exclude LA/San Diego.>,\n"
         '  "companyFilter": <array of lowercase employer name substrings. Expand group names. Empty array if no company.>,\n'
         '  "topN": <integer if user wants top N results, else null>,\n'
         '  "sortBySalary": <true if user wants highest-paid / best-paying / top salary, else false>,\n'
         '  "cleanQuery": <role/skill signal only — strip location, count, salary, and company tokens. '
         "Expand acronyms. Never include company names or 'jobs in X' — infer role if only company remains "
         "(e.g. 'jobs in Apple' → 'software engineer', 'Big 4 jobs' → 'consultant').>\n"
         "}}\n\n"
         "Examples:\n"
         '  "google jobs in Asia" → {{"location":"asia","locationAliases":["india","singapore","japan","china","hong kong","south korea","bangalore","tokyo","shanghai"],"locationExclusions":[],"companyFilter":["google"],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "google jobs in Europe" → {{"location":"europe","locationAliases":["london","uk","germany","france","netherlands","berlin","paris","amsterdam","dublin","zurich"],"locationExclusions":[],"companyFilter":["google"],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "google jobs in North America" → {{"location":"north america","locationAliases":["usa","canada","toronto","vancouver","mexico",", ca",", ny",", tx"],"locationExclusions":[],"companyFilter":["google"],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "google jobs in midwest USA" → {{"location":"midwest usa","locationAliases":["chicago","detroit","minneapolis","cleveland","columbus",", il",", mi",", oh",", mn"],"locationExclusions":[],"companyFilter":["google"],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "google jobs in west coast" → {{"location":"west coast","locationAliases":[", ca",", wa",", or"],"locationExclusions":[],"companyFilter":["google"],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "jobs in Los Angeles" → {{"location":"los angeles","locationAliases":["los angeles","santa monica","culver city","burbank","long beach","anaheim","irvine","orange county"],"locationExclusions":[],"companyFilter":[],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "jobs in Seattle" → {{"location":"seattle","locationAliases":["seattle","bellevue","redmond","kirkland",", wa"],"locationExclusions":[],"companyFilter":[],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "jobs in Austin" → {{"location":"austin","locationAliases":["austin","round rock",", tx"],"locationExclusions":["dallas","houston"],"companyFilter":[],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "jobs in southern california" → {{"location":"southern california","locationAliases":[", ca"],"locationExclusions":["san francisco","bay area","palo alto","mountain view","sunnyvale","san jose","santa clara","menlo park","oakland","berkeley","cupertino","sacramento","fresno","stockton"],"companyFilter":[],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "jobs in socal" → {{"location":"southern california","locationAliases":[", ca"],"locationExclusions":["san francisco","bay area","palo alto","mountain view","sunnyvale","san jose","santa clara","menlo park","oakland","berkeley","cupertino","sacramento","fresno","stockton"],"companyFilter":[],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "jobs in northern california" → {{"location":"northern california","locationAliases":[", ca"],"locationExclusions":["los angeles","san diego","irvine","anaheim","riverside","long beach","santa monica","burbank","orange county","chula vista","san bernardino","oxnard"],"companyFilter":[],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "top paid 5 jobs in california" → {{"location":"california","locationAliases":[", ca"],"locationExclusions":[],"companyFilter":[],"topN":5,"sortBySalary":true,"cleanQuery":"software engineer"}}\n'
         '  "top 5 paid jobs in google, USA" → {{"location":"usa","locationAliases":["usa",", ca",", ny",", tx",", wa",", il","san francisco","new york"],"companyFilter":["google"],"topN":5,"sortBySalary":true,"cleanQuery":"software engineer"}}\n'
         '  "best paying data scientist roles in NYC" → {{"location":"new york","locationAliases":["new york city","manhattan","brooklyn","new york",", ny"],"companyFilter":[],"topN":null,"sortBySalary":true,"cleanQuery":"data scientist"}}\n'
         '  "remote python developer" → {{"location":null,"locationAliases":[],"companyFilter":[],"topN":null,"sortBySalary":false,"cleanQuery":"remote python developer"}}\n'
         '  "jobs in apple" → {{"location":null,"locationAliases":[],"companyFilter":["apple"],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "top paid jobs in apple, france" → {{"location":"france","locationAliases":["paris","france","lyon","marseille","ile-de-france"],"companyFilter":["apple"],"topN":null,"sortBySalary":true,"cleanQuery":"software engineer"}}\n'
         '  "FANG jobs" → {{"location":null,"locationAliases":[],"companyFilter":["google","meta","amazon","apple","netflix","microsoft"],"topN":null,"sortBySalary":false,"cleanQuery":"software engineer"}}\n'
         '  "Big 4 consulting jobs in London" → {{"location":"london","locationAliases":["london","uk","england"],"companyFilter":["deloitte","pwc","ernst","kpmg"],"topN":null,"sortBySalary":false,"cleanQuery":"consultant"}}\n'
         '  "MLE roles at FAANG" → {{"location":null,"locationAliases":[],"companyFilter":["google","meta","amazon","apple","netflix","microsoft"],"topN":null,"sortBySalary":false,"cleanQuery":"machine learning engineer"}}'
        ),
        ("human", "Query: {query}"),
    ])
    chain = prompt | llm | StrOutputParser()
    try:
        raw = await chain.ainvoke({"query": query})
        result = json.loads(raw)  # JSON mode guarantees valid JSON — no repair needed
        # Ensure required fields with safe defaults
        result.setdefault("location", None)
        result.setdefault("locationAliases", [])
        result.setdefault("locationExclusions", [])
        result.setdefault("companyFilter", [])
        result.setdefault("topN", None)
        result.setdefault("sortBySalary", False)
        result.setdefault("cleanQuery", query)
    except Exception:
        result = {
            "location": None,
            "locationAliases": [],
            "locationExclusions": [],
            "companyFilter": _extract_job_company_filter(query),
            "topN": None,
            "sortBySalary": False,
            "cleanQuery": query,
        }

    _job_intent_cache_set(_cache_key, result)
    return result


_REGION_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Remote", ["remote", "anywhere", "worldwide", "global", "distributed"]),
    ("United States", ["united states", " usa", ", us", "u.s.", "california", "new york", "texas", "washington", "illinois", "florida", "seattle", "chicago", "boston", "austin", "denver", "atlanta", "san francisco", "los angeles", "san jose", "new jersey", "pennsylvania"]),
    ("United Kingdom", ["united kingdom", " uk", "england", "london", "manchester", "birmingham", "scotland", "wales"]),
    ("Canada", ["canada", "toronto", "vancouver", "montreal", "calgary", "ontario", "british columbia"]),
    ("India", ["india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "pune", "kolkata"]),
    ("Europe", ["europe", "germany", "france", "spain", "italy", "netherlands", "sweden", "norway", "denmark", "finland", "switzerland", "austria", "poland", "berlin", "paris", "amsterdam", "stockholm", "madrid", "rome", "barcelona", "munich", "dublin", "ireland", "portugal", "belgium", "czech"]),
    ("Australia / NZ", ["australia", "new zealand", "sydney", "melbourne", "brisbane", "auckland", "perth"]),
    ("Asia Pacific", ["singapore", "japan", "china", "hong kong", "south korea", "taiwan", "vietnam", "thailand", "malaysia", "philippines", "indonesia", "tokyo", "beijing", "shanghai"]),
    ("Middle East / Africa", ["dubai", "uae", "saudi", "israel", "south africa", "nigeria", "kenya", "egypt", "qatar", "bahrain"]),
    ("Latin America", ["brazil", "mexico", "argentina", "colombia", "chile", "peru", "bogota", "sao paulo"]),
]


def _classify_region(location: str) -> str:
    loc_lower = location.lower()
    for region, keywords in _REGION_KEYWORDS:
        if any(kw in loc_lower for kw in keywords):
            return region
    return "Other"


@router.get("/locations")
async def get_job_locations(user_id: str = Depends(get_current_user), role: str = Depends(get_user_role)):
    """Return all distinct job locations grouped by geographic region."""
    table = get_or_create_jobs_table()
    is_recruiter = role in ("recruiter", "manager")
    where = None if is_recruiter else f"user_id = '{user_id}'"
    try:
        query = table.search()
        if where:
            query = query.where(where)
        rows = query.limit(5000).to_list()
    except Exception:
        rows = []

    from collections import Counter
    # Count jobs by metro_location (LLM-resolved at ingest).
    # Fall back to _suburb_to_metro for older JDs without the field.
    city_counts: Counter = Counter()
    for row in rows:
        metro = (row.get("metro_location") or "").strip()
        if not metro:
            loc = (row.get("location_name") or "").strip()
            if not loc:
                continue
            metro = _suburb_to_metro(loc) or loc
        city_counts[metro] += 1

    # Group cities by state (US) or region (international) with their counts
    state_cities: dict[str, list] = {}   # state  → [(city, count)]
    region_cities: dict[str, list] = {}  # region → [(city, count)]
    for loc, count in city_counts.items():
        state = _city_to_metro(loc)
        if state:
            state_cities.setdefault(state, []).append((loc, count))
        else:
            region = _classify_region(loc)
            region_cities.setdefault(region, []).append((loc, count))

    # Show only cities with 2+ jobs; cap international regions at 5.
    MIN_COUNT = 2
    MAX_PER_REGION = 5
    groups: dict[str, list[dict]] = {}

    # US states: "All {State}" + all cities with 2+ jobs, sorted by frequency.
    for state in sorted(state_cities):
        cities = state_cities[state]
        qualifying = sorted(
            [(c, n) for c, n in cities if n >= MIN_COUNT],
            key=lambda x: (-x[1], x[0]),
        )
        groups[state] = [{"value": state, "label": f"All {state}"}]
        for city, _ in qualifying:
            groups[state].append({"value": city, "label": city})

    # International regions: top cities by frequency, capped at MAX_PER_REGION
    for region in sorted(region_cities):
        cities = region_cities[region]
        top = sorted(
            [(c, n) for c, n in cities if n >= MIN_COUNT],
            key=lambda x: (-x[1], x[0]),
        )[:MAX_PER_REGION]
        for city, _ in top:
            groups.setdefault(region, []).append({"value": city, "label": city})

    return {
        "locations": sorted(city_counts.keys()),
        "groups": groups,
        "total": sum(city_counts.values()),
    }


@router.post("", response_model=JobResponse)
async def create_job(
    job: JobCreate,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
):
    table = get_or_create_jobs_table()
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)

    job_dict = job.model_dump()
    job_id = str(uuid.uuid4())
    job_dict["job_id"] = job_id
    job_dict["user_id"] = user_id
    job_dict["posted_date"] = datetime.now().isoformat()
    job_dict = _normalize_job_fields(job_dict)

    # Resolve metro area via LLM; fall back to hardcoded mapping
    loc = job_dict.get("location_name") or ""
    if loc and loc.lower() != "remote":
        metro = _ai_metro_for_location(loc, creds)
        job_dict["metro_location"] = metro or _suburb_to_metro(loc) or loc
    else:
        job_dict["metro_location"] = None

    # Generate embedding for the job
    try:
        embeddings = get_embeddings_model(api_key=creds["openrouter_key"])
        skills_text = ", ".join(job_dict.get("skills_required", []))
        embed_text = f"{job_dict['title']}\n{job_dict['description']}\nSkills: {skills_text}"
        vector = embeddings.embed_query(embed_text)
        job_dict["vector"] = vector
    except Exception as e:
        print(f"DEBUG: [jobs] Embedding failed: {e}")
        job_dict["vector"] = [0.0] * 1536
    
    table.add([job_dict])

    # Trigger autonomous recruiter: screen all existing resumes against this new JD (if enabled)
    from services.db.lancedb_client import get_user_settings as _get_user_settings
    agent_cfg = _get_user_settings(user_id) or {}
    jd_enabled = agent_cfg.get("agent_jd_enabled", "true").lower() == "true"
    if jd_enabled:
        llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])
        background_tasks.add_task(
            _screen_all_resumes_for_job,
            job_dict=job_dict,
            manager_user_id=user_id,
            llm_config=llm_config,
        )

    return _serialize_job(job_dict)


@router.post("/reindex-embeddings")
async def reindex_job_embeddings(
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
):
    """Re-generate embeddings for all jobs that have zero vectors. Recruiter/manager only."""
    if role not in ("recruiter", "manager"):
        raise HTTPException(status_code=403, detail="Recruiter or manager role required")

    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    table = get_or_create_jobs_table()

    import numpy as np
    rows = table.search().limit(10000).to_list()
    zero_rows = [r for r in rows if not any(v != 0 for v in (r.get("vector") or []))]
    print(f"DEBUG: [reindex] Found {len(zero_rows)} jobs with zero vectors out of {len(rows)}")

    if not zero_rows:
        return {"reindexed": 0, "message": "All jobs already have embeddings"}

    try:
        embeddings = get_embeddings_model(api_key=creds["openrouter_key"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding model unavailable: {e}")

    updated = 0
    errors = 0
    for row in zero_rows:
        try:
            skills_text = ", ".join(row.get("skills_required") or [])
            embed_text = f"{row.get('title', '')}\n{row.get('description', '')}\nSkills: {skills_text}"
            vector = embeddings.embed_query(embed_text)
            job_id = row["job_id"]
            table.update(where=f"job_id = '{job_id}'", values={"vector": vector})
            updated += 1
        except Exception as e:
            print(f"DEBUG: [reindex] Failed for job {row.get('job_id')}: {e}")
            errors += 1

    print(f"DEBUG: [reindex] Done: {updated} updated, {errors} errors")
    return {"reindexed": updated, "errors": errors, "total_zero": len(zero_rows)}


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
    search: Optional[str] = None,
    location: Optional[str] = None,
    date_range: Optional[int] = Query(None, description="Posted within N days"),
    has_applicants: Optional[bool] = Query(None),
    status: Optional[str] = Query(None, description="in_progress or completed"),
    location_aliases: Optional[str] = Query(None, description="Comma-separated location substrings for soft geo matching"),
    employer_filter: Optional[str] = Query(None, description="Comma-separated employer name substrings; matching jobs are sorted first"),
    sort_by_salary: Optional[bool] = Query(None),
    top_n: Optional[int] = Query(None, description="Limit to top N results after all filters"),
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
):
    from datetime import timedelta

    table = get_or_create_jobs_table()
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    is_recruiter = role in ("recruiter", "manager")

    # --- DB-level WHERE filters (pushed to LanceDB) ---
    where_parts = [] if is_recruiter else [f"user_id = '{user_id}'"]
    if job_level:
        where_parts.append(f"job_level = '{job_level}'")
    if job_category:
        where_parts.append(f"job_category = '{job_category}'")
    # Only use SQL WHERE for exact location match when it's not a state-level metro name.
    # State-level names (e.g. "California") are handled as a Python post-filter below.
    location_metro_substrings: list[str] = []
    location_city_filter: str = ""   # city-level filter (includes suburbs)
    if location:
        metro_subs = _METRO_TO_SUBSTRINGS.get(location.strip())
        if metro_subs:
            location_metro_substrings = metro_subs
        else:
            # City-level: use Python post-filter so suburbs roll up to their metro
            location_city_filter = location.strip()
    where_clause = " AND ".join(where_parts) if where_parts else None

    # For post-DB filters (date_range, has_applicants, status) we need a larger pool to filter from.
    # For plain list or vector search, use limit + skip directly.
    needs_post_filter = bool(date_range or has_applicants or status or location_aliases or employer_filter or location_metro_substrings or location_city_filter)
    FETCH_CAP = max(limit + skip, 500) if needs_post_filter else limit + skip

    # --- Hybrid search (vector + FTS via RRF) when a query is provided ---
    if search and search.strip():
        results = search_jobs_hybrid(
            search.strip(),
            limit=FETCH_CAP,
            api_key=creds["openrouter_key"],
            where_clause=where_clause,
            fetch_cap=FETCH_CAP,
        )
    else:
        q = table.search()
        if where_clause:
            q = q.where(where_clause)
        results = q.limit(FETCH_CAP).to_list()

    jobs = [_serialize_job(r) for r in results]

    # --- State-level metro location post-filter ---
    # Skip when location_aliases present: text-query location wins over dropdown.
    if location_metro_substrings and not location_aliases:
        subs_lower = [s.lower() for s in location_metro_substrings]
        jobs = [
            j for j in jobs
            if any(sub in (j.get("location_name") or "").lower() for sub in subs_lower)
            and _classify_region(j.get("location_name") or "") == "United States"
        ]

    # --- City-level location post-filter ---
    # Skip when location_aliases is present: text-query location takes precedence over dropdown.
    if location_city_filter and not location_aliases:
        city_lower = location_city_filter.lower()
        city_name_only = city_lower.split(",")[0].strip()
        def _job_city_matches(j: dict) -> bool:
            stored_metro = (j.get("metro_location") or "").strip()
            if stored_metro:
                return stored_metro.lower() == city_lower
            # Legacy fallback
            loc = j.get("location_name") or ""
            return (
                city_lower in loc.lower()
                or city_name_only in loc.lower()
                or _suburb_to_metro(loc) == location_city_filter
            )
        jobs = [j for j in jobs if _job_city_matches(j)]

    # --- Date range filter (Python-level, needs datetime parse) ---
    if date_range:
        cutoff = datetime.now() - timedelta(days=date_range)
        def _parse_dt(d: str):
            try:
                return datetime.fromisoformat(str(d)[:19])
            except Exception:
                return datetime.min
        jobs = [j for j in jobs if _parse_dt(j.get("posted_date", "")) >= cutoff]

    # --- Compute applied/shortlisted/selected/rejected counts ---
    for job in jobs:
        job["applied_count"] = 0
        job["shortlisted_count"] = 0
        job["selected_count"] = 0
        job["rejected_count"] = 0
    applied_table = get_or_create_job_applied_table()
    try:
        applied_df = applied_table.to_pandas()
        if not applied_df.empty:
            for job in jobs:
                jdf = applied_df[applied_df['job_id'] == job['job_id']]
                job["applied_count"] = int(len(jdf[jdf['applied_status'].isin(['applied', 'selected', 'rejected'])]))
                job["shortlisted_count"] = int(len(jdf[jdf['applied_status'].isin(['shortlisted', 'invited', 'auto_shortlisted'])]))
                job["selected_count"] = int(len(jdf[jdf['applied_status'] == 'selected']))
                job["rejected_count"] = int(len(jdf[jdf['applied_status'] == 'rejected']))
                job["ai_screened_count"] = int(len(jdf[jdf['applied_status'].isin(['auto_shortlisted', 'auto_rejected'])]))
    except Exception as e:
        print(f"DEBUG: Error calculating applied_counts: {e}")

    # --- Post-count filters (need applied_count / selected_count) ---
    if has_applicants:
        jobs = [j for j in jobs if (j.get("applied_count", 0) + j.get("shortlisted_count", 0)) > 0]

    if status:
        def _filled(j): return (j.get("selected_count") or 0) >= (j.get("positions") or 1)
        if status == "completed":
            jobs = [j for j in jobs if _filled(j)]
        elif status == "in_progress":
            jobs = [j for j in jobs if not _filled(j)]

    # --- Soft geo matching via location aliases (text-query location takes precedence over dropdown) ---
    if location_aliases:
        aliases = [a.strip().lower() for a in location_aliases.split(",") if a.strip()]
        if aliases:
            def _alias_match(loc_str: str) -> bool:
                loc_lower = (loc_str or "").lower()
                for alias in aliases:
                    if len(alias) <= 3:
                        import re
                        if re.search(r"\b" + re.escape(alias) + r"\b", loc_lower):
                            return True
                    elif alias in loc_lower:
                        return True
                return False
            jobs = [j for j in jobs if _alias_match(j.get("location_name", ""))]

    # --- Employer filter: strict — only return jobs at matching companies ---
    # Semantic search may only return a subset of all jobs, missing employer-specific jobs
    # that rank low for the generic query. So we ALSO do a full-table scan for the employer
    # and merge the results, preserving semantic rank order for overlapping results.
    if employer_filter:
        emp_terms = [e.strip().lower() for e in employer_filter.split(",") if e.strip()]
        if emp_terms:
            def _emp_match(j: dict) -> bool:
                name = (j.get("employer_name") or "").lower()
                return any(t in name for t in emp_terms)

            # Full-table scan to ensure ALL employer jobs are captured
            try:
                eq = table.search()
                if where_clause:
                    eq = eq.where(where_clause)
                all_employer_jobs = [s for r in eq.limit(10000).to_list()
                                     for s in [_serialize_job(r)] if _emp_match(s)]
            except Exception:
                all_employer_jobs = []

            # Apply state-level metro filter to full-table scan results
            if location_metro_substrings:
                subs_lower = [s.lower() for s in location_metro_substrings]
                all_employer_jobs = [
                    j for j in all_employer_jobs
                    if any(sub in (j.get("location_name") or "").lower() for sub in subs_lower)
                    and _classify_region(j.get("location_name") or "") == "United States"
                ]
            if location_city_filter:
                all_employer_jobs = [j for j in all_employer_jobs if _job_city_matches(j)]

            # Apply location alias filter to the full-table scan results too
            if location_aliases:
                loc_aliases = [a.strip().lower() for a in location_aliases.split(",") if a.strip()]
                def _loc_alias_match(j: dict) -> bool:
                    loc_lower = (j.get("location_name") or "").lower()
                    for alias in loc_aliases:
                        if len(alias) <= 3:
                            if re.search(r"\b" + re.escape(alias) + r"\b", loc_lower):
                                return True
                        elif alias in loc_lower:
                            return True
                    return False
                all_employer_jobs = [j for j in all_employer_jobs if _loc_alias_match(j)]

            # Semantic employer matches (ranked by relevance) come first
            sem_employer = [j for j in jobs if _emp_match(j)]
            sem_ids = {j.get("job_id") for j in sem_employer}
            # Append any employer jobs not already in semantic results
            extra = [j for j in all_employer_jobs if j.get("job_id") not in sem_ids]
            jobs = sem_employer + extra

    # --- Sort by salary ---
    if sort_by_salary:
        jobs.sort(key=lambda j: (j.get("salary_max") or j.get("salary_min") or 0), reverse=True)

    # --- Top N (overrides pagination) ---
    if top_n and top_n > 0:
        return jobs[:top_n]

    return jobs[skip: skip + limit]

# New endpoint to fetch applied jobs for the current user
@router.get("/my-applied", response_model=List[dict])
async def get_applied_jobs(user_id: str = Depends(get_current_user)):
    # Retrieve applied records
    applied_table = get_or_create_job_applied_table()
    applied_records = applied_table.search().where(f"user_id = '{user_id}'").to_list()
    
    if not applied_records:
        return []

    # De-duplicate: for same (job_id, resume_id), prefer applied/selected/rejected over auto_shortlisted
    STATUS_PRIORITY = {"selected": 0, "rejected": 1, "applied": 2, "shortlisted": 3, "invited": 3, "auto_shortlisted": 4, "auto_rejected": 5}
    deduped: dict = {}
    for rec in applied_records:
        key = (rec.get('job_id', ''), rec.get('resume_id', ''))
        existing = deduped.get(key)
        if existing is None or STATUS_PRIORITY.get(rec.get('applied_status', ''), 99) < STATUS_PRIORITY.get(existing.get('applied_status', ''), 99):
            deduped[key] = rec

    # Retrieve job details for each de-duplicated record
    jobs_table = get_or_create_jobs_table()
    result = []
    for rec in deduped.values():
        job_id = rec.get('job_id')
        job_rows = jobs_table.search().where(f"job_id = '{job_id}'").limit(1).to_list()
        if job_rows:
            job = job_rows[0]
            job_serialized = {k: v for k, v in job.items() if k != 'vector'}
            result.append({
                "job_id": job_id,
                "title": job_serialized.get('title'),
                "company": job_serialized.get('employer_name'),
                "location": job_serialized.get('location_name'),
                "posted_date": job_serialized.get('posted_date'),
                "resume_id": rec.get('resume_id'),
                "applied_at": rec.get('timestamp'),
                "applied_status": rec.get('applied_status', 'applied'),
            })
    return result

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user_id: str = Depends(get_current_user), role: str = Depends(get_user_role)):
    table = get_or_create_jobs_table()
    results = table.search().where(f"job_id = '{job_id}'").limit(1).to_list()
    if not results:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_dict = _serialize_job(results[0])
    
    applied_table = get_or_create_job_applied_table()
    try:
        applied_df = applied_table.to_pandas()
        if not applied_df.empty:
            jdf = applied_df[applied_df['job_id'] == job_id]
            job_dict["applied_count"] = len(jdf[jdf['applied_status'].isin(['applied', 'selected', 'rejected'])])
            job_dict["shortlisted_count"] = len(jdf[jdf['applied_status'].isin(['shortlisted', 'invited', 'auto_shortlisted'])])
            job_dict["selected_count"] = int(len(jdf[jdf['applied_status'] == 'selected']))
            job_dict["rejected_count"] = int(len(jdf[jdf['applied_status'] == 'rejected']))
            job_dict["ai_screened_count"] = int(len(jdf[jdf['applied_status'].isin(['auto_shortlisted', 'auto_rejected'])]))
    except Exception as e:
        print(f"DEBUG: Error calculating applied_count for {job_id}: {e}")
        
    return job_dict

@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job: JobCreate,
    user_id: str = Depends(get_current_user),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    role: str = Depends(get_user_role),
):
    table = get_or_create_jobs_table()
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)

    # Allow managers and recruiters to update any job. Others must be the owner.
    is_recruiter = role in ("recruiter", "manager")
    where_clause = f"job_id = '{job_id}'" if is_recruiter else f"job_id = '{job_id}' AND user_id = '{user_id}'"
    
    print(f"DEBUG: [update_job] user_id={user_id}, role={role}, job_id={job_id}, where='{where_clause}'")

    existing = table.search().where(where_clause).limit(1).to_list()
    if not existing:
        print(f"DEBUG: [update_job] Job {job_id} not found or not owned by {user_id}")
        raise HTTPException(status_code=404, detail="Job not found")

    updated = job.model_dump()
    updated["job_id"] = job_id
    updated["user_id"] = user_id
    updated["posted_date"] = existing[0]["posted_date"]
    updated = _normalize_job_fields(updated)

    # Resolve metro area via LLM; fall back to hardcoded mapping
    loc = updated.get("location_name") or ""
    if loc and loc.lower() != "remote":
        metro = _ai_metro_for_location(loc, creds)
        updated["metro_location"] = metro or _suburb_to_metro(loc) or loc
    else:
        updated["metro_location"] = None

    # Re-generate embedding
    try:
        embeddings = get_embeddings_model(api_key=creds["openrouter_key"])
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
async def delete_job(job_id: str, user_id: str = Depends(get_current_user), role: str = Depends(get_user_role)):
    table = get_or_create_jobs_table()
    safe_jid = job_id.replace("'", "''")
    
    # Allow managers and recruiters to delete any job. Others must be the owner.
    is_recruiter = role in ("recruiter", "manager")
    where_clause = f"job_id = '{safe_jid}'" if is_recruiter else f"job_id = '{safe_jid}' AND user_id = '{user_id}'"
    
    existing = table.search().where(where_clause).limit(1).to_list()
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")

    # 1. Delete job posting + vector
    table.delete(f"job_id = '{safe_jid}'")

    # 2. Delete all candidate applications / shortlist entries for this job
    try:
        from services.db.lancedb_client import get_or_create_job_applied_table
        applied_table = get_or_create_job_applied_table()
        applied_table.delete(f"job_id = '{safe_jid}'")
        print(f"DEBUG: Deleted job_resume_applied rows for job '{job_id}'")
    except Exception as e:
        print(f"DEBUG: Failed to clean job_resume_applied for job '{job_id}': {e}")

    return {"message": "Deleted"}

@router.get("/{job_id}/candidates", response_model=List[dict])
async def get_job_candidates(job_id: str, status: str = None, user_id: str = Depends(get_current_user), role: str = Depends(get_user_role)):
    # 1. Verify user owns the job (recruiters/managers can access any job)
    jobs_table = get_or_create_jobs_table()
    is_recruiter = role in ("recruiter", "manager")
    where = f"job_id = '{job_id}'" if is_recruiter else f"job_id = '{job_id}' AND user_id = '{user_id}'"
    jobs = jobs_table.search().where(where).limit(1).to_list()
    if not jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    # 2. Get applied candidates, optionally filtered by status
    applied_table = get_or_create_job_applied_table()
    applied_records_all = applied_table.search().where(f"job_id = '{job_id}'").to_list()
    if status == 'shortlisted':
        # Proactive pipeline: shortlisted + invited + auto_shortlisted
        applied_records = [r for r in applied_records_all if r.get('applied_status') in ('shortlisted', 'invited', 'auto_shortlisted')]
    elif status == 'ai_screened':
        # All autonomous agent results
        applied_records = [r for r in applied_records_all if r.get('applied_status') in ('auto_shortlisted', 'auto_rejected')]
    elif status == 'applied':
        # Full applied pool: applied + selected + rejected
        applied_records = [r for r in applied_records_all if r.get('applied_status') in ('applied', 'selected', 'rejected')]
    elif status == 'selected':
        applied_records = [r for r in applied_records_all if r.get('applied_status') == 'selected']
    elif status == 'rejected':
        applied_records = [r for r in applied_records_all if r.get('applied_status') == 'rejected']
    elif status:
        applied_records = [r for r in applied_records_all if r.get('applied_status') == status]
    else:
        applied_records = applied_records_all

    result = []
    for rec in applied_records:
        result.append({
            "resume_id": rec.get('resume_id'),
            "candidate_user_id": rec.get('user_id'),
            "applied_at": rec.get('timestamp'),
            "applied_status": rec.get('applied_status', 'applied'),
            "notified": bool(rec.get('notified', False)),
        })
    return result
    
from pydantic import BaseModel
class StatusUpdate(BaseModel):
    status: str

@router.put("/{job_id}/candidates/{resume_id}/status")
async def update_candidate_status(job_id: str, resume_id: str, status_data: StatusUpdate, user_id: str = Depends(get_current_user), role: str = Depends(get_user_role)):
    # 1. Verify job exists (recruiters/managers can update any job's candidates)
    jobs_table = get_or_create_jobs_table()
    is_recruiter = role in ("recruiter", "manager")
    where = f"job_id = '{job_id}'" if is_recruiter else f"job_id = '{job_id}' AND user_id = '{user_id}'"
    jobs = jobs_table.search().where(where).limit(1).to_list()
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


@router.put("/{job_id}/candidates/{resume_id}/notify")
async def mark_candidate_notified(job_id: str, resume_id: str, user_id: str = Depends(get_current_user)):
    """Mark that the recruiter has sent a notification to this candidate."""
    from datetime import datetime
    jobs_table = get_or_create_jobs_table()
    jobs = jobs_table.search().where(f"job_id = '{job_id}'").limit(1).to_list()
    if not jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    safe_resume_id = resume_id.replace("'", "''")
    applied_table = get_or_create_job_applied_table()
    try:
        df = applied_table.to_pandas()
        if not df.empty:
            mask = (df['job_id'] == job_id) & (df['resume_id'] == resume_id)
            rows = df[mask].copy()
            if not rows.empty:
                applied_table.delete(f"job_id = '{job_id}' AND resume_id = '{safe_resume_id}'")
                rows['notified'] = True
                rows['notified_at'] = datetime.now().isoformat()
                applied_table.add(rows.to_dict('records'))
                return {"message": "Candidate marked as notified"}
    except Exception as e:
        print(f"DEBUG: Error marking notified: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark notification")

    raise HTTPException(status_code=404, detail="Application not found")


class ShortlistRequest(BaseModel):
    resume_id: str
    candidate_user_id: str = ""


@router.post("/{job_id}/shortlist")
async def shortlist_candidate(
    job_id: str,
    body: ShortlistRequest,
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    """Recruiter/manager shortlists a matched candidate for outreach."""
    if role not in ("recruiter", "manager"):
        raise HTTPException(status_code=403, detail="Only recruiters and managers can shortlist candidates")

    from uuid import uuid4
    from datetime import datetime

    applied_table = get_or_create_job_applied_table()

    # Prevent duplicates — if already shortlisted just return OK
    try:
        df = applied_table.to_pandas()
        if not df.empty:
            existing = df[(df['job_id'] == job_id) & (df['resume_id'] == body.resume_id) & (df['applied_status'] == 'shortlisted')]
            if not existing.empty:
                return {"message": "Already shortlisted", "status": "shortlisted"}
    except Exception:
        pass

    applied_table.add([{
        "id": str(uuid4()),
        "user_id": body.candidate_user_id or user_id,
        "job_id": job_id,
        "resume_id": body.resume_id,
        "applied_status": "shortlisted",
        "timestamp": datetime.now().isoformat(),
        "notified": False,
        "notified_at": "",
    }])
    return {"message": "Candidate shortlisted", "status": "shortlisted"}


@router.post("/{job_id}/apply")
async def apply_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    resume_id: str = Query(...),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
):
    from services.db.lancedb_client import apply_for_job, get_or_create_jobs_table, get_or_create_table
    from services.email_service import send_employer_notification
    try:
        success = apply_for_job(user_id, job_id, resume_id)
        if not success:
            return {"message": "Already applied for job"}

        # Fetch job details
        jobs_table = get_or_create_jobs_table()
        job_results = jobs_table.search().where(f"job_id = '{job_id}'").limit(1).to_list()
        job_ref = job_results[0] if job_results else {}
        job_title = job_ref.get("title", "Unknown Job Title")
        employer_name = job_ref.get("employer_name", "")
        employer_email = job_ref.get("employer_email", "")

        # Fetch resume text (concatenated chunks)
        resumes_table = get_or_create_table()
        resume_results = resumes_table.search().where(
            f"filename = '{resume_id}' AND user_id = '{user_id}'"
        ).to_pandas()
        resume_text = "\n".join(resume_results['text'].tolist()) if not resume_results.empty else ""

        # Notify employer
        if employer_email and resume_text:
            background_tasks.add_task(
                send_employer_notification, employer_email, job_title, user_id, resume_id, resume_text
            )

        # Auto-screen the application and notify candidate
        if resume_text and job_ref:
            creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
            llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])
            background_tasks.add_task(
                _auto_screen_application,
                user_id=user_id,
                job_id=job_id,
                resume_id=resume_id,
                resume_text=resume_text,
                job_ref=job_ref,
                llm_config=llm_config,
            )

        return {"message": "Successfully applied for job"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

