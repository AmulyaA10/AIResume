from fastapi import APIRouter, Header, Depends
from typing import Optional
import json
import time
import os

from app.dependencies import get_current_user, resolve_credentials
from app.models import SearchRequest
from services.db.lancedb_client import search_resumes_semantic
from services.ai.common import clean_json_output

router = APIRouter()


@router.post("/search")
async def search_resumes(
    request: SearchRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)

    start_time = time.time()
    print(f"--- [Search Start] Query: '{request.query}' for user {user_id} ---")

    is_recruiter = user_id == "user_recruiter_456"
    # Perform semantic search to filter relevant resumes/chunks
    db_start = time.time()
    df = search_resumes_semantic(request.query, user_id, limit=10, api_key=creds["openrouter_key"], is_recruiter=is_recruiter)
    db_end = time.time()
    print(f"DEBUG: LanceDB search took {db_end - db_start:.2f}s. Found {len(df)} results.")

    if df.empty:
        return {"results": []}

    # Aggregate results by filename
    aggregated_resumes = {}
    for _, row in df.iterrows():
        fname = row['filename']
        if fname not in aggregated_resumes:
            aggregated_resumes[fname] = []
        # Keep unique excerpts only
        if row['text'] not in aggregated_resumes[fname]:
            aggregated_resumes[fname].append(row['text'])

    resumes_text = ""
    for fname, excerpts in aggregated_resumes.items():
        combined_text = "\n---\n".join(excerpts)
        resumes_text += f"FILE: {fname}\nCONTENT_EXCERPTS:\n{combined_text}\n====================\n"

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    prompt = PromptTemplate(
        input_variables=["resumes", "query"],
        template="""You are an expert technical recruiter. Analyze the following resume excerpts and evaluate their relevance to the search query.

For each resume, provide:
1. A match score (0-100). Be generous if semantic keywords overlap. 
2. A brief justification (1-2 sentences).
3. A list of missing key skills from the query.
4. An auto_screen decision ('SELECTED' if score > 70, otherwise 'WAITLIST').

QUERY: {query}

RESUMES TO EVALUATE:
{resumes}

Return ONLY a JSON object in this format:
{{
  "results": [
    {{
      "filename": "file.pdf",
      "score": 85,
      "justification": "...",
      "missing_skills": ["docker", "kubernetes"],
      "auto_screen": "SELECTED"
    }}
  ]
}}"""
    )

    llm_start = time.time()
    print(f"DEBUG: Passing {len(aggregated_resumes)} aggregated files to LLM ({creds['llm_model'] or 'gpt-4o-mini'})...")

    # Initialize LLM with dynamic config if available
    llm = ChatOpenAI(
        model=creds["llm_model"] or "gpt-4o-mini",
        api_key=creds["openrouter_key"] or os.getenv("OPEN_ROUTER_KEY"),
        base_url="https://openrouter.ai/api/v1",
        timeout=30
    )

    try:
        chain = prompt | llm | StrOutputParser()
        raw_result = chain.invoke({"resumes": resumes_text, "query": request.query})
        llm_end = time.time()
        print(f"DEBUG: LLM response received in {llm_end - llm_start:.2f}s.")
        print(f"DEBUG: LLM Raw Output (first 100 char): {raw_result[:100]}...")

        clean_res = clean_json_output(raw_result)
        parsed_result = json.loads(clean_res)

        total_time = time.time() - start_time
        print(f"--- [Search End] Total time: {total_time:.2f}s ---")
        return parsed_result
    except Exception as e:
        print(f"DEBUG: Error during LLM processing: {e}")
        return {"results": [], "error": f"Search failed or timed out: {str(e)}"}
