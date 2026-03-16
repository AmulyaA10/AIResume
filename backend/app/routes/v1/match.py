from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List, Optional
import json
import os

from app.models import JobMatchResponse, JobSkillMatchResponse
from app.dependencies import get_current_user, resolve_credentials
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
        # Try to find by filename for this user
        safe_filename = resume_id.replace("'", "''")
        res_results = resumes_table.search().where(f"filename = '{safe_filename}' AND user_id = '{user_id}'").limit(1).to_list()
    if not res_results:
        # Try to find by user_id if ID not found directly (simple fallback)
        res_results = resumes_table.search().where(f"user_id = '{user_id}'").limit(1).to_list()

    if not res_results:
        # No resume uploaded yet — return empty list so the UI shows "no matches" gracefully
        return []

    resume_vec = res_results[0]["vector"]

    # Detect zero vector (embedding failed during upload)
    vec_norm = sum(float(v) ** 2 for v in resume_vec) ** 0.5

    jobs_table = get_or_create_jobs_table()

    if vec_norm < 0.001:
        # Zero vector — can't do meaningful matching, return all public jobs
        print("DEBUG: [match] Resume vector is zero, falling back to all-jobs listing")
        results = jobs_table.search().limit(limit).to_list()
        return [{"score": 0.5, "job": _serialize_job(r)} for r in results]

    try:
        results = jobs_table.search(resume_vec).metric("cosine").limit(limit).to_list()
    except Exception as e:
        print(f"DEBUG: [match] Vector search failed: {e}, falling back to all-jobs listing")
        results = jobs_table.search().limit(limit).to_list()
        return [{"score": 0.5, "job": _serialize_job(r)} for r in results]

    matches = []
    for r in results:
        # Cosine distance is 1 - cosine similarity
        dist = r.get("_distance", 1.0)
        score = max(0.0, 1.0 - float(dist))
        matches.append({
            "score": score,
            "job": _serialize_job(r)
        })

    # If all scores are near-zero, job vectors in DB are likely zeros too
    if matches and max(m["score"] for m in matches) < 0.05:
        print("DEBUG: [match] All job scores near zero (zero vectors in DB), falling back to all-jobs listing")
        results = jobs_table.search().limit(limit).to_list()
        return [{"score": 0.5, "job": _serialize_job(r)} for r in results]

    return matches

@router.get("/job/{job_id}/candidates")
async def match_candidates_for_job(
    job_id: str,
    limit: int = 50,
    user_id: str = Depends(get_current_user),
):
    """Find resumes that best match a job using vector similarity (recruiter/manager view)."""
    jobs_table = get_or_create_jobs_table()
    job_rows = jobs_table.search().where(f"job_id = '{job_id}'").limit(1).to_list()
    if not job_rows:
        raise HTTPException(status_code=404, detail="Job not found")

    job_vec = job_rows[0].get("vector")
    if job_vec is None:
        raise HTTPException(status_code=422, detail="Job has no embedding vector")

    vec_norm = sum(float(v) ** 2 for v in job_vec) ** 0.5
    resumes_table = get_or_create_table()

    if vec_norm < 0.001:
        results = resumes_table.search().limit(limit).to_list()
        return [{"score": 0.5, "resume_id": r["filename"], "user_id": r.get("user_id", ""), "snippet": (r.get("text") or "")[:200]} for r in results]

    results = resumes_table.search(job_vec).metric("cosine").limit(limit).to_list()

    matches = []
    seen_filenames = set()
    for r in results:
        filename = r.get("filename", "")
        if filename in seen_filenames:
            continue
        seen_filenames.add(filename)
        dist = r.get("_distance", 1.0)
        score = max(0.0, 1.0 - float(dist))
        matches.append({
            "score": score,
            "resume_id": filename,
            "user_id": r.get("user_id", ""),
            "snippet": (r.get("text") or "")[:200],
        })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


@router.get("/search/jobs", response_model=List[JobMatchResponse])
async def search_jobs(
    q: str,
    limit: int = 50,
    job_level: Optional[str] = None,
    job_category: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """Semantic search for jobs using natural language query, with text fallback."""
    jobs_table = get_or_create_jobs_table()

    # --- Try semantic (vector) search first ---
    try:
        embeddings = get_embeddings_model()
        query_vec = embeddings.embed_query(q)

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
            matches.append({"score": score, "job": _serialize_job(r)})

        # Only return semantic results if scores are meaningful (not all zero vectors)
        if matches and max(m["score"] for m in matches) > 0.05:
            return matches

        print("DEBUG: [match] Semantic search returned zero scores, falling back to text search")
    except Exception as e:
        print(f"DEBUG: [match] Semantic search failed: {e}, falling back to text search")

    # --- Text-based keyword fallback ---
    all_results = jobs_table.search().limit(1000).to_list()
    q_lower = q.lower()
    matches = []
    for r in all_results:
        title = (r.get("title") or "").lower()
        desc = (r.get("description") or "").lower()
        employer = (r.get("employer_name") or "").lower()
        skills = [s.lower() for s in (r.get("skills_required") or [])]

        if q_lower in title or q_lower in employer:
            matches.append({"score": 1.0, "job": _serialize_job(r)})
        elif any(q_lower in s for s in skills):
            matches.append({"score": 0.85, "job": _serialize_job(r)})
        elif q_lower in desc:
            matches.append({"score": 0.7, "job": _serialize_job(r)})

    return matches[:limit]


# ---------- Skill extraction only ----------

@router.get("/resume/{resume_id}/extract-skills")
async def extract_skills_from_resume(
    resume_id: str,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    """Return only the extracted skills for a resume — no job matching."""
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    resumes_table = get_or_create_table()

    safe_filename = resume_id.replace("'", "''")
    res_results = resumes_table.search().where(
        f"filename = '{safe_filename}' AND user_id = '{user_id}'"
    ).to_list()
    if not res_results:
        res_results = resumes_table.search().where(f"id = '{resume_id}'").limit(1).to_list()
    if not res_results:
        res_results = resumes_table.search().where(f"user_id = '{user_id}'").to_list()
    if not res_results:
        return {"skills": []}

    full_text = " ".join(r.get("text", "") for r in res_results)
    skills = await _extract_skills_ai(full_text, creds)
    return {"skills": skills}


# ---------- Skills-based matching ----------

def _extract_skills_keywords(text: str) -> List[str]:
    """Keyword-based skill extraction fallback."""
    common_skills = [
        "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "Ruby", "PHP",
        "React", "Angular", "Vue", "Node.js", "Express", "Django", "Flask", "FastAPI", "Spring",
        "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Terraform", "CI/CD", "Jenkins", "GitHub",
        "Machine Learning", "Deep Learning", "NLP", "TensorFlow", "PyTorch", "scikit-learn",
        "REST API", "GraphQL", "Microservices", "Agile", "Scrum", "Git", "Linux",
        "HTML", "CSS", "Tailwind", "Bootstrap", "Next.js", "Webpack",
        "Data Analysis", "Excel", "Tableau", "Power BI", "R", "MATLAB",
        "Project Management", "Communication", "Leadership", "Problem Solving",
        "Swift", "Kotlin", "Scala", "Perl", "Bash", "PowerShell",
        "Figma", "Sketch", "Photoshop", "Illustrator", "UX", "UI",
        "Selenium", "Pytest", "Jest", "Cypress", "JUnit",
        "Hadoop", "Spark", "Kafka", "Airflow", "dbt",
        "Blockchain", "Solidity", "Web3", "DevOps", "SRE",
    ]
    text_lower = text.lower()
    return [skill for skill in common_skills if skill.lower() in text_lower]


async def _extract_skills_ai(text: str, creds: dict) -> List[str]:
    """Extract skills from resume text using AI, with keyword fallback."""
    api_key = creds.get("openrouter_key") or os.getenv("OPEN_ROUTER_KEY")
    if not api_key:
        return _extract_skills_keywords(text)
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import PromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        from services.ai.common import clean_json_output

        prompt = PromptTemplate(
            input_variables=["text"],
            template="""Extract all technical and professional skills from this resume text.
Return ONLY a JSON array of skill name strings, e.g. ["Python", "React", "Project Management"].
Include programming languages, frameworks, tools, platforms, and professional competencies.
Limit to the 30 most relevant skills.

RESUME TEXT:
{text}

JSON array:"""
        )
        llm = ChatOpenAI(
            model=creds.get("llm_model") or "gpt-4o-mini",
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        chain = prompt | llm | StrOutputParser()
        raw = chain.invoke({"text": text[:8000]})
        cleaned = clean_json_output(raw)
        skills = json.loads(cleaned)
        if isinstance(skills, list) and skills:
            return [str(s) for s in skills if s]
    except Exception as e:
        print(f"DEBUG: [skills] AI extraction failed: {e}, using keyword fallback")
    return _extract_skills_keywords(text)


@router.get("/resume/{resume_id}/skills-match", response_model=List[JobSkillMatchResponse])
async def match_jobs_by_resume_skills(
    resume_id: str,
    limit: int = 100,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    """Extract skills from a resume and semantically match against all jobs."""
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)

    resumes_table = get_or_create_table()

    # Collect all chunks for this resume (filename lookup first)
    safe_filename = resume_id.replace("'", "''")
    res_results = resumes_table.search().where(
        f"filename = '{safe_filename}' AND user_id = '{user_id}'"
    ).to_list()

    if not res_results:
        res_results = resumes_table.search().where(f"id = '{resume_id}'").limit(1).to_list()
    if not res_results:
        res_results = resumes_table.search().where(f"user_id = '{user_id}'").to_list()
    if not res_results:
        return []

    # Combine all chunks into full resume text
    full_text = " ".join(r.get("text", "") for r in res_results)

    # Extract skills
    skills = await _extract_skills_ai(full_text, creds)

    jobs_table = get_or_create_jobs_table()

    if not skills:
        # Zero-skills fallback: use the first chunk's vector
        resume_vec = res_results[0]["vector"]
        vec_norm = sum(float(v) ** 2 for v in resume_vec) ** 0.5
        if vec_norm < 0.001:
            results = jobs_table.search().limit(limit).to_list()
            return [{"score": 0.5, "job": _serialize_job(r), "matched_skills": []} for r in results]
        results = jobs_table.search(resume_vec).metric("cosine").limit(limit).to_list()
        matches = []
        for r in results:
            dist = r.get("_distance", 1.0)
            score = max(0.0, 1.0 - float(dist))
            matches.append({"score": score, "job": _serialize_job(r), "matched_skills": []})
        return matches

    # Embed the extracted skills as the search query
    skills_query = "Technical skills and competencies: " + ", ".join(skills)
    try:
        embeddings = get_embeddings_model(api_key=creds.get("openrouter_key"))
        skills_vec = embeddings.embed_query(skills_query)
        results = jobs_table.search(skills_vec).metric("cosine").limit(limit).to_list()
    except Exception as e:
        print(f"DEBUG: [skills-match] Embedding/search failed: {e}")
        results = jobs_table.search().limit(limit).to_list()
        return [{"score": 0.5, "job": _serialize_job(r), "matched_skills": skills} for r in results]

    skills_lower = [s.lower() for s in skills]
    matches = []
    for r in results:
        dist = r.get("_distance", 1.0)
        score = max(0.0, 1.0 - float(dist))
        job_skills = r.get("skills_required") or []
        if hasattr(job_skills, "tolist"):
            job_skills = job_skills.tolist()
        # Compute overlapping skills between resume and job
        matched = [
            s for s, sl in zip(skills, skills_lower)
            if any(sl in js.lower() or js.lower() in sl for js in job_skills)
        ]
        matches.append({"score": score, "job": _serialize_job(r), "matched_skills": matched})

    # If all scores are near-zero (zero vectors in DB), normalise to 0.5
    if matches and max(m["score"] for m in matches) < 0.05:
        for m in matches:
            m["score"] = 0.5

    return matches


# ---------- SSE streaming skills-match ----------

@router.get("/resume/{resume_id}/skills-match-stream")
async def match_jobs_skills_stream(
    resume_id: str,
    limit: int = 100,
    min_score: float = 0.0,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    """
    SSE endpoint — streams live progress of skills extraction + semantic job matching.
    Each event: data: {"type": str, "message": str, "ts": str}
    Final event: data: {"type": "results", "data": [...matches]}
    Terminal event: data: {"type": "done"}
    """
    import asyncio
    import time
    from fastapi.responses import StreamingResponse as SR

    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)

    async def generate():
        def evt(msg: str, evt_type: str = "log") -> str:
            payload = json.dumps({"type": evt_type, "message": msg, "ts": time.strftime("%H:%M:%S")})
            return f"data: {payload}\n\n"

        try:
            # ── STEP 1: Load resume ─────────────────────────────────────────
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("  RESUME LOADING", "section")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("MODULE   › services/db/lancedb_client.py", "module")
            yield evt("FUNCTION › get_or_create_table()", "module")
            yield evt(f"ACTION   › Querying resumes table for '{resume_id}'", "action")

            resumes_table = get_or_create_table()
            safe_filename = resume_id.replace("'", "''")

            res_results = resumes_table.search().where(
                f"filename = '{safe_filename}' AND user_id = '{user_id}'"
            ).to_list()
            yield evt(f"QUERY    › filename='{safe_filename}' AND user_id='{user_id}'", "query")

            if not res_results:
                yield evt("         › No exact filename match — trying by ID...", "log")
                yield evt(f"QUERY    › id='{resume_id}'", "query")
                res_results = resumes_table.search().where(f"id = '{resume_id}'").limit(1).to_list()

            if not res_results:
                yield evt("         › No ID match — loading first resume for user...", "log")
                yield evt(f"QUERY    › user_id='{user_id}'", "query")
                res_results = resumes_table.search().where(f"user_id = '{user_id}'").to_list()

            if not res_results:
                yield evt("ERROR    › No resume found in database", "error")
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            yield evt(f"RESULT   › {len(res_results)} chunk(s) loaded from LanceDB ✓", "success")

            # ── STEP 2: Resume info ─────────────────────────────────────────
            yield evt("", "spacer")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("  RESUME INFORMATION", "section")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")

            full_text = " ".join(r.get("text", "") for r in res_results)
            word_count = len(full_text.split())

            yield evt(f"Filename   : {resume_id}", "info")
            yield evt(f"Chunks     : {len(res_results)}", "info")
            yield evt(f"Characters : {len(full_text):,}", "info")
            yield evt(f"Words      : {word_count:,}", "info")
            yield evt("Preview ↓", "info")

            words = full_text.split()[:80]
            line, lines_out = [], []
            for w in words:
                line.append(w)
                if len(" ".join(line)) > 72:
                    lines_out.append(" ".join(line))
                    line = []
            if line:
                lines_out.append(" ".join(line))
            for ln in lines_out:
                yield evt(f"  {ln}", "preview")

            # ── STEP 3: Skill extraction ────────────────────────────────────
            yield evt("", "spacer")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("  SKILL EXTRACTION", "section")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("MODULE   › app/routes/v1/match.py", "module")
            yield evt("FUNCTION › _extract_skills_ai()", "module")

            api_key = creds.get("openrouter_key") or os.getenv("OPEN_ROUTER_KEY")
            skills: List[str] = []

            if api_key:
                model = creds.get("llm_model") or "gpt-4o-mini"
                yield evt("ACTION   › Invoking LLM for skill extraction", "action")
                yield evt("Provider : OpenRouter  (https://openrouter.ai/api/v1)", "log")
                yield evt(f"Model    : {model}", "log")
                yield evt(f"Input    : {min(len(full_text), 8000):,} characters sent to LLM", "log")
                yield evt("PROCESS  › Building LangChain PromptTemplate...", "process")
                try:
                    from langchain_openai import ChatOpenAI
                    from langchain_core.prompts import PromptTemplate
                    from langchain_core.output_parsers import StrOutputParser
                    from services.ai.common import clean_json_output

                    prompt_tpl = PromptTemplate(
                        input_variables=["text"],
                        template="""Extract all technical and professional skills from this resume text.
Return ONLY a JSON array of skill name strings, e.g. ["Python", "React", "Project Management"].
Include programming languages, frameworks, tools, platforms, and professional competencies.
Limit to the 30 most relevant skills.

RESUME TEXT:
{text}

JSON array:"""
                    )
                    yield evt("PROCESS  › Initialising ChatOpenAI client...", "process")
                    llm = ChatOpenAI(model=model, api_key=api_key, base_url="https://openrouter.ai/api/v1")
                    chain = prompt_tpl | llm | StrOutputParser()

                    yield evt("PROCESS  › Sending request to LLM — awaiting response...", "process")
                    loop = asyncio.get_event_loop()
                    raw = await loop.run_in_executor(None, lambda: chain.invoke({"text": full_text[:8000]}))

                    yield evt("PROCESS  › Parsing JSON response from LLM...", "process")
                    cleaned = clean_json_output(raw)
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, list):
                        skills = [str(s) for s in parsed if s]
                    yield evt(f"RESULT   › LLM returned {len(skills)} skills ✓", "success")
                except Exception as e:
                    yield evt(f"WARNING  › LLM extraction failed: {e}", "warning")
                    yield evt("FALLBACK › Switching to keyword-based extraction", "warning")
                    yield evt("FUNCTION › _extract_skills_keywords()", "module")
                    skills = _extract_skills_keywords(full_text)
                    yield evt(f"RESULT   › Keyword scan found {len(skills)} skills ✓", "success")
            else:
                yield evt("WARNING  › No API key configured", "warning")
                yield evt("FALLBACK › Using keyword-based extraction", "warning")
                yield evt("FUNCTION › _extract_skills_keywords()", "module")
                skills = _extract_skills_keywords(full_text)
                yield evt(f"RESULT   › Keyword scan found {len(skills)} skills ✓", "success")

            if skills:
                yield evt("", "spacer")
                yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
                yield evt("  EXTRACTED SKILLS", "section")
                yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
                for i, skill in enumerate(skills, 1):
                    yield evt(f"  {i:2d}.  {skill}", "skill")

            # ── STEP 4: Vector embedding ────────────────────────────────────
            yield evt("", "spacer")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("  VECTOR EMBEDDING", "section")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("MODULE   › services/db/lancedb_client.py", "module")
            yield evt("FUNCTION › get_embeddings_model()", "module")
            yield evt("Model    › openai/text-embedding-3-small  (1536 dims)", "log")

            jobs_table = get_or_create_jobs_table()
            skills_vec = None

            if skills:
                skills_query = "Technical skills and competencies: " + ", ".join(skills)

                yield evt(f"PROCESS  › Building vectorisation query from {len(skills)} skills", "process")
                yield evt("", "spacer")
                yield evt("  ┌─ TEXT PASSED TO embed_query() ───────────────────", "section")
                # Show the full query broken into ~72-char wrapped lines
                words_q = skills_query.split()
                ln, lns = [], []
                for w in words_q:
                    ln.append(w)
                    if len(" ".join(ln)) > 68:
                        lns.append(" ".join(ln))
                        ln = []
                if ln:
                    lns.append(" ".join(ln))
                for l in lns:
                    yield evt(f"  │  {l}", "vectorise")
                yield evt("  └──────────────────────────────────────────────────", "section")
                yield evt("", "spacer")
                yield evt(f"  Words    : {len(words_q)}", "info")
                yield evt(f"  Tokens   : ~{int(len(skills_query) / 4)}  (est. @ 4 chars/token)", "info")
                yield evt(f"  Chars    : {len(skills_query)}", "info")
                yield evt("", "spacer")
                # Show individual skill tokens
                yield evt("  Token breakdown (each skill → one semantic unit):", "info")
                for i, skill in enumerate(skills, 1):
                    token_est = max(1, round(len(skill) / 4))
                    yield evt(f"    [{i:2d}]  \"{skill}\"  (~{token_est} token{'s' if token_est != 1 else ''})", "vectorise_token")

                yield evt("", "spacer")
                yield evt("PROCESS  › Calling embed_query() — generating 1536-dim vector...", "process")
                try:
                    embeddings = get_embeddings_model(api_key=creds.get("openrouter_key"))
                    loop = asyncio.get_event_loop()
                    skills_vec = await loop.run_in_executor(None, lambda: embeddings.embed_query(skills_query))
                    yield evt(f"RESULT   › Embedding generated  |  shape: ({len(skills_vec)},)  |  dtype: float32 ✓", "success")
                    # Show a tiny sample of the vector
                    sample = [f"{v:.4f}" for v in skills_vec[:6]]
                    yield evt(f"  Vector  : [{', '.join(sample)}, ...]", "vectorise")
                except Exception as e:
                    yield evt(f"WARNING  › Embedding failed: {e}", "warning")
                    yield evt("FALLBACK › Will use unranked all-jobs listing", "warning")

            # ── STEP 5: Cosine search ───────────────────────────────────────
            yield evt("", "spacer")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("  JOB SEARCH  (LanceDB cosine similarity)", "section")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("MODULE   › services/db/lancedb_client.py", "module")
            yield evt("FUNCTION › get_or_create_jobs_table()", "module")

            if skills_vec is not None:
                yield evt(f"ACTION   › jobs_table.search(skills_vec).metric('cosine').limit({limit})", "action")
                results = jobs_table.search(skills_vec).metric("cosine").limit(limit).to_list()
            else:
                yield evt(f"ACTION   › jobs_table.search().limit({limit})  [fallback — no vector]", "action")
                results = jobs_table.search().limit(limit).to_list()

            yield evt(f"RESULT   › {len(results)} candidate job(s) returned from LanceDB ✓", "success")

            # ── STEP 6: Score & skill overlap ───────────────────────────────
            yield evt("", "spacer")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("  SCORING  JOBS", "section")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("ACTION   › Computing cosine score + skill overlap for each job", "action")
            threshold_pct = round(min_score * 100)
            yield evt(f"Threshold › {threshold_pct}%  (min match score from slider)", "info")
            yield evt("", "spacer")

            skills_lower = [s.lower() for s in skills]
            matches = []

            for i, r in enumerate(results, 1):
                title    = r.get("title", "Unknown")
                employer = r.get("employer_name", "Unknown Employer")
                level    = r.get("job_level", "")
                dist     = r.get("_distance", 1.0) if skills_vec else 0.5
                score    = max(0.0, 1.0 - float(dist)) if skills_vec else 0.5

                job_skills = r.get("skills_required") or []
                if hasattr(job_skills, "tolist"):
                    job_skills = job_skills.tolist()

                matched = [
                    s for s, sl in zip(skills, skills_lower)
                    if any(sl in js.lower() or js.lower() in sl for js in job_skills)
                ]

                score_pct = round(score * 100)
                qualifies = score >= min_score
                badge     = "✓ PASS" if qualifies else "✗ SKIP"
                badge_type = "job_pass" if qualifies else "job_fail"

                yield evt(f"  [{i:3d}/{len(results)}]  {badge}  {score_pct:3d}%  {title}  [{level}]", badge_type)
                yield evt(f"           Employer : {employer}", "job_detail")
                if matched:
                    yield evt(f"           Skills   : {', '.join(matched)}", "skill_detail")
                else:
                    yield evt("           Skills   : (no direct skill overlap)", "job_detail")

                matches.append({"score": score, "job": _serialize_job(r), "matched_skills": matched})

                if i % 5 == 0:
                    await asyncio.sleep(0)

            if matches and max(m["score"] for m in matches) < 0.05:
                for m in matches:
                    m["score"] = 0.5

            # ── COMPLETE ────────────────────────────────────────────────────
            yield evt("", "spacer")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            qualifying = sum(1 for m in matches if m["score"] >= min_score)
            yield evt(f"  SUMMARY  ✓  {len(matches)} jobs searched  |  threshold: {threshold_pct}%", "success")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")
            yield evt("", "spacer")

            # Sort by score descending for the summary listing
            sorted_matches = sorted(matches, key=lambda m: m["score"], reverse=True)
            col_w = 38  # title column width
            yield evt(f"  {'#':<4}  {'Score':<6}  {'Status':<6}  {'Job Title':<{col_w}}  Employer", "info")
            yield evt(f"  {'─'*4}  {'─'*6}  {'─'*6}  {'─'*col_w}  {'─'*20}", "info")
            for rank, m in enumerate(sorted_matches, 1):
                job        = m["job"]
                title      = job.get("title", "Unknown")
                employer   = job.get("employer_name", "")
                level      = job.get("job_level", "")
                score_pct  = round(m["score"] * 100)
                qualifies  = m["score"] >= min_score
                status     = "PASS" if qualifies else "SKIP"
                status_type = "summary_pass" if qualifies else "summary_fail"
                title_col  = f"{title[:col_w]:<{col_w}}"
                yield evt(
                    f"  {rank:<4}  {score_pct:>3d}%   {status:<6}  {title_col}  {employer}  [{level}]",
                    status_type
                )

            yield evt("", "spacer")
            yield evt(f"  Qualifying (≥ {threshold_pct}%) : {qualifying}", "success")
            yield evt(f"  Skipped   (< {threshold_pct}%) : {len(matches) - qualifying}", "summary_fail")
            yield evt("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "section")

            yield f"data: {json.dumps({'type': 'results', 'data': matches})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield evt(f"FATAL    › {str(e)}", "error")
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return SR(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
