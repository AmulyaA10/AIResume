import lancedb
from pathlib import Path
from uuid import uuid4
import pyarrow as pa
import os
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

<<<<<<< HEAD
load_dotenv()

# ---------- DB PATH ----------
DB_PATH = Path("data/lancedb")
=======
# Always load backend/.env regardless of current working directory
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / "backend" / ".env")

# ---------- DB PATH ----------
# Use absolute path so the same DB is used regardless of CWD
DB_PATH = _PROJECT_ROOT / "data" / "lancedb"
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
DB_PATH.mkdir(parents=True, exist_ok=True)

db = lancedb.connect(DB_PATH)

# ---------- EMBEDDINGS CACHE ----------
_embeddings_cache = {}

def get_embeddings_model(api_key=None, model="text-embedding-3-small"):
    key = api_key or os.getenv("OPEN_ROUTER_KEY")
    if not key:
        print("DEBUG: [embeddings] ERROR: No API key found for embeddings")
        raise ValueError("OPEN_ROUTER_KEY is required for semantic search. Please set it in your .env file or environment.")
    
    # OpenRouter often requires 'openai/' prefix for OpenAI models
    model_name = model if "/" in model else f"openai/{model}"
    
    # Check cache
    cache_key = (key, model_name)
    if cache_key in _embeddings_cache:
        return _embeddings_cache[cache_key]
    
    print(f"DEBUG: [embeddings] Initializing NEW model instance: {model_name} via OpenRouter")
    
    embeddings = OpenAIEmbeddings(
        model=model_name,
        openai_api_key=key,
        openai_api_base="https://openrouter.ai/api/v1",
        request_timeout=15.0
    )
    
    _embeddings_cache[cache_key] = embeddings
    return embeddings

# ---------- SCHEMA ----------
resume_schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("user_id", pa.string()), # Added for multi-tenancy
    pa.field("filename", pa.string()),
    pa.field("text", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 1536)) # Assuming text-embedding-3-small
])

<<<<<<< HEAD
# ---------- JOB SCHEMA ----------
job_schema = pa.schema([
    pa.field("job_id", pa.string()),
    pa.field("user_id", pa.string()),
    pa.field("title", pa.string()),
    pa.field("description", pa.string()),
    pa.field("employer_name", pa.string()),
    pa.field("employer_email", pa.string()),
    pa.field("location_name", pa.string()),
    pa.field("location_lat", pa.float64()),
    pa.field("location_lng", pa.float64()),
    pa.field("employment_type", pa.string()),
    pa.field("job_category", pa.string()),
    pa.field("job_level", pa.string()),
    pa.field("skills_required", pa.list_(pa.string())),
    pa.field("salary_min", pa.float64()),
    pa.field("salary_max", pa.float64()),
    pa.field("benefits", pa.list_(pa.string())),
    pa.field("application_url", pa.string()),
    pa.field("metadata", pa.string()),
    pa.field("posted_date", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 1536))
])

=======
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
# ---------- TABLE HANDLER ----------
def get_or_create_table():
    if "resumes" in db.table_names():
        return db.open_table("resumes")

    return db.create_table(
        name="resumes",
        schema=resume_schema,
        mode="create"
    )

<<<<<<< HEAD
def get_or_create_jobs_table():
    if "jobs" in db.table_names():
        return db.open_table("jobs")

    return db.create_table(
        name="jobs",
        schema=job_schema,
        mode="create"
    )

=======
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
# ---------- CHUNKING ----------
def chunk_text(text, chunk_size=1000, chunk_overlap=200):
    """Simple sliding window chunking."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks

# ---------- STORE ----------
def store_resume(filename: str, text: str, user_id: str, api_key: str = None):
    print(f"DEBUG: Storing resume {filename} for user {user_id} (text length: {len(text)})")
    table = get_or_create_table()
    embeddings = get_embeddings_model(api_key=api_key)
    
    # Chunk the resume text for better semantic search
    chunks = chunk_text(text)
    print(f"DEBUG: Created {len(chunks)} chunks for {filename}")
    
    data = []
    for i, chunk in enumerate(chunks):
        # Only print every 10th chunk to reduce noise
        if i % 10 == 0:
            print(f"DEBUG: Generating embedding for chunk {i+1}/{len(chunks)}...")
        vector = embeddings.embed_query(chunk)
        data.append({
            "id": str(uuid4()),
            "user_id": user_id,
            "filename": filename,
            "text": chunk, # Store the chunk text
            "vector": vector
        })
    
    print(f"DEBUG: Adding {len(data)} rows to LanceDB for {filename}")
    table.add(data)
    print(f"DEBUG: Successfully stored {filename}")

# ---------- ACTIVITY SCHEMA ----------
activity_schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("user_id", pa.string()), # Added for multi-tenancy
    pa.field("type", pa.string()), # 'screen', 'quality', 'skill_gap'
    pa.field("filename", pa.string()),
    pa.field("score", pa.int32()),
    pa.field("decision", pa.string()), # 'SELECTED', 'REJECTED', or N/A
    pa.field("timestamp", pa.string())
])

def get_or_create_activity_table():
    if "activity" in db.table_names():
        return db.open_table("activity")
    return db.create_table("activity", schema=activity_schema, mode="create")

def log_activity(user_id: str, activity_type: str, filename: str, score: int, decision: str = "N/A"):
    from datetime import datetime
    table = get_or_create_activity_table()
    table.add([{
        "id": str(uuid4()),
        "user_id": user_id,
        "type": activity_type,
        "filename": filename,
        "score": score,
        "decision": decision,
        "timestamp": datetime.now().isoformat()
    }])
    print(f"DEBUG: Logged activity: {activity_type} for {filename} (User: {user_id})")

def get_dashboard_stats(user_id: str):
    print(f"DEBUG: [stats] Fetching stats for user: {user_id}")
    resumes_table = get_or_create_table()
    activity_table = get_or_create_activity_table()
    
    import pandas as pd
    resumes_df = resumes_table.to_pandas()
    
    total_resumes = 0
    if not resumes_df.empty:
        # Trace available IDs
        available = resumes_df['user_id'].unique().tolist()
        print(f"DEBUG: [stats] Resumes table Users: {available}")
        
        user_resumes = resumes_df[resumes_df['user_id'] == user_id]
        total_resumes = user_resumes['filename'].nunique()
        print(f"DEBUG: [stats] Found {total_resumes} resumes for {user_id}")
    
    # Activity Stats
    activity_df = activity_table.to_pandas()
    
    total_screened = 0
    high_matches = 0
    skill_gaps = 0
    quality_scored = 0
    recent_activity = []

    if not activity_df.empty:
        available_act = activity_df['user_id'].unique().tolist()
        print(f"DEBUG: [stats] Activity table Users: {available_act}")

        # Filter by user_id
        user_activity = activity_df[activity_df['user_id'] == user_id]
        print(f"DEBUG: [stats] Found {len(user_activity)} activities for {user_id}")
        
        total_screened = len(user_activity[user_activity['type'] == 'screen'])
        high_matches = len(user_activity[user_activity['score'] >= 80])
        skill_gaps = len(user_activity[user_activity['type'] == 'skill_gap'])
        quality_scored = len(user_activity[user_activity['type'] == 'quality'])
        
        # Get 5 most recent activities
        recent_df = user_activity.sort_values(by="timestamp", ascending=False).head(5)
        for _, row in recent_df.iterrows():
            recent_activity.append({
                "type": row['type'],
                "filename": row.get('filename', 'N/A'),
                "score": row.get('score', 0),
                "decision": row.get('decision', 'N/A'),
                "timestamp": row.get('timestamp', '')
            })

    return {
        "total_resumes": total_resumes,
        "auto_screened": total_screened,
        "high_matches": high_matches,
        "skill_gaps": skill_gaps,
        "quality_scored": quality_scored,
        "recent_activity": recent_activity
    }

# ---------- USER SETTINGS SCHEMA ----------
user_settings_schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("user_id", pa.string()),
    pa.field("setting_key", pa.string()),
    pa.field("setting_value", pa.string()),
    pa.field("updated_at", pa.string()),
])

def get_or_create_settings_table():
    if "user_settings" in db.table_names():
        return db.open_table("user_settings")
    return db.create_table("user_settings", schema=user_settings_schema, mode="create")

def upsert_user_setting(user_id: str, key: str, encrypted_value: str):
    """Store or update a single encrypted setting for a user."""
    from datetime import datetime
    table = get_or_create_settings_table()
    try:
        table.delete(f"user_id = '{user_id}' AND setting_key = '{key}'")
    except Exception:
        pass
    if encrypted_value:
        table.add([{
            "id": str(uuid4()),
            "user_id": user_id,
            "setting_key": key,
            "setting_value": encrypted_value,
            "updated_at": datetime.now().isoformat(),
        }])

def get_user_settings(user_id: str) -> dict:
    """Retrieve all settings for a user as {key: encrypted_value}."""
    table = get_or_create_settings_table()
    try:
        df = table.to_pandas()
        if df.empty:
            return {}
        user_df = df[df['user_id'] == user_id]
        return {row['setting_key']: row['setting_value'] for _, row in user_df.iterrows()}
    except Exception as e:
        print(f"DEBUG: Failed to read user settings: {e}")
        return {}

def delete_user_settings(user_id: str):
    """Delete all settings for a user."""
    table = get_or_create_settings_table()
    try:
        table.delete(f"user_id = '{user_id}'")
    except Exception as e:
        print(f"DEBUG: Failed to delete user settings: {e}")

def migrate_orphaned_settings(old_user_id: str, new_user_id: str):
    """One-time migration: copy settings from old user_id to new user_id.

    Only runs if new_user_id has NO settings and old_user_id has settings.
    This handles the case where credentials were saved under a previous
    user ID mapping (e.g., LinkedIn OAuth formerly mapped to user_recruiter_456).
    """
    from datetime import datetime
    table = get_or_create_settings_table()
    try:
        df = table.to_pandas()
        if df.empty:
            return
        new_settings = df[df['user_id'] == new_user_id]
        if not new_settings.empty:
            return  # new user already has settings — no migration needed
        old_settings = df[df['user_id'] == old_user_id]
        if old_settings.empty:
            return  # no orphaned settings to migrate
        # Copy old settings to new user
        for _, row in old_settings.iterrows():
            table.add([{
                "id": str(uuid4()),
                "user_id": new_user_id,
                "setting_key": row['setting_key'],
                "setting_value": row['setting_value'],
                "updated_at": datetime.now().isoformat(),
            }])
        print(f"MIGRATION: Copied {len(old_settings)} settings from {old_user_id} to {new_user_id}")
    except Exception as e:
        print(f"MIGRATION: Failed to migrate settings from {old_user_id} to {new_user_id}: {e}")

# ---------- SEARCH ----------
def search_resumes_semantic(query: str, user_id: str, limit: int = 5, api_key: str = None):
    print(f"DEBUG: Semantic search query: {query} (User: {user_id})")
    table = get_or_create_table()
    
    total_rows = len(table)
    if total_rows == 0:
        import pandas as pd
        return pd.DataFrame()

    embeddings = get_embeddings_model(api_key=api_key)
    
    try:
        query_vector = embeddings.embed_query(query)
    except Exception as e:
        print(f"DEBUG: [search] FATAL: embed_query failed: {e}")
        raise e
    
    # Use LanceDB's where clause for filtering
    results = table.search(query_vector).where(f"user_id = '{user_id}'").limit(limit).to_pandas()
    print(f"DEBUG: Found {len(results)} matches for user {user_id}")
    return results
