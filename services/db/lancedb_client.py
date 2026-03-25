import lancedb
from pathlib import Path
from uuid import uuid4
import pyarrow as pa
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

# Always load backend/.env regardless of current working directory
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / "backend" / ".env")

# ---------- DB PATH ----------
# Use absolute path so the same DB is used regardless of CWD
DB_PATH = _PROJECT_ROOT / "data" / "lancedb"
DB_PATH.mkdir(parents=True, exist_ok=True)

db = lancedb.connect(DB_PATH)

# ---------- EMBEDDINGS CACHE ----------
_embeddings_cache = {}

def get_embeddings_model(api_key=None, model="text-embedding-3-small"):
    key = api_key
    if not key:
        print("DEBUG: [embeddings] ERROR: No API key found for embeddings")
        raise ValueError("OpenRouter API key is required for semantic search. Please save your key in Settings.")
    
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

# ---------- JOB SCHEMA ----------
job_schema = pa.schema([
    pa.field("job_id", pa.string()),
    pa.field("user_id", pa.string()),
    pa.field("title", pa.string()),
    pa.field("description", pa.string()),
    pa.field("employer_name", pa.string()),
    pa.field("employer_email", pa.string()),
    pa.field("location_name", pa.string()),
    pa.field("metro_location", pa.string()),    # LLM-resolved major metro (e.g. "Los Angeles, CA")
    pa.field("location_lat", pa.float64()),
    pa.field("location_lng", pa.float64()),
    pa.field("employment_type", pa.string()),
    pa.field("job_category", pa.string()),
    pa.field("job_level", pa.string()),
    pa.field("positions", pa.int64()),
    pa.field("skills_required", pa.list_(pa.string())),
    pa.field("salary_min", pa.float64()),
    pa.field("salary_max", pa.float64()),
    pa.field("salary_currency", pa.string()),
    pa.field("benefits", pa.list_(pa.string())),
    pa.field("application_url", pa.string()),
    pa.field("metadata", pa.string()),
    pa.field("skills_tiers", pa.string()),       # nullable JSON: {must_have,strong,familiarity,nice_to_have}
    pa.field("posted_date", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 1536))
])
# ---------- TABLE HANDLER ----------
def get_or_create_table():
    if "resumes" in db.table_names():
        return db.open_table("resumes")

    return db.create_table(
        name="resumes",
        schema=resume_schema,
        mode="create"
    )

def get_or_create_jobs_table():
    if "jobs" in db.table_names():
        table = db.open_table("jobs")
        # Migrate: add any columns present in job_schema but missing from the live table
        existing = {f.name for f in table.schema}
        new_fields = [f for f in job_schema if f.name not in existing]
        if new_fields:
            table.add_columns(pa.schema(new_fields))
        return table

    return db.create_table(
        name="jobs",
        schema=job_schema,
        mode="create"
    )
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
    
    _embedding_failed = False
    data = []
    for i, chunk in enumerate(chunks):
        # Only print every 10th chunk to reduce noise
        if i % 10 == 0:
            print(f"DEBUG: Generating embedding for chunk {i+1}/{len(chunks)}...")
        if _embedding_failed:
            vector = [0.0] * 1536
        else:
            try:
                vector = embeddings.embed_query(chunk)
            except Exception as embed_err:
                print(f"DEBUG: Embedding failed ({embed_err}); storing with zero vectors.")
                _embedding_failed = True
                vector = [0.0] * 1536
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

# ---------- JOB RESUME APPLIED SCHEMA ----------
job_resume_applied_schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("user_id", pa.string()),
    pa.field("job_id", pa.string()),
    pa.field("resume_id", pa.string()),
    pa.field("applied_status", pa.string()),
    pa.field("timestamp", pa.string()),
    pa.field("notified", pa.bool_()),
    pa.field("notified_at", pa.string()),
])

def get_or_create_job_applied_table():
    if "job_resume_applied" in db.table_names():
        table = db.open_table("job_resume_applied")
        schema_names = table.schema.names
        # Hard reset if core field is missing
        if "applied_status" not in schema_names:
            print("DEBUG: [db] job_resume_applied missing applied_status — dropping and recreating...")
            db.drop_table("job_resume_applied")
            return db.create_table("job_resume_applied", schema=job_resume_applied_schema, mode="create")
        # Migrate: add notified/notified_at columns if missing (preserves existing rows)
        if "notified" not in schema_names:
            print("DEBUG: [db] job_resume_applied missing notified columns — migrating...")
            try:
                df = table.to_pandas()
                df["notified"] = False
                df["notified_at"] = ""
                db.drop_table("job_resume_applied")
                return db.create_table("job_resume_applied", data=df, mode="create")
            except Exception as e:
                print(f"DEBUG: [db] Migration failed: {e} — recreating empty table")
                db.drop_table("job_resume_applied")
                return db.create_table("job_resume_applied", schema=job_resume_applied_schema, mode="create")
        return table
    return db.create_table("job_resume_applied", schema=job_resume_applied_schema, mode="create")

def apply_for_job(user_id: str, job_id: str, resume_id: str):
    from datetime import datetime
    table = get_or_create_job_applied_table()

    try:
        df = table.to_pandas()
        if not df.empty:
            mask = (df['user_id'] == user_id) & (df['job_id'] == job_id) & (df['resume_id'] == resume_id)
            existing = df[mask]
            if not existing.empty:
                statuses = set(existing['applied_status'].tolist())
                # Already formally applied — no-op
                if statuses & {'applied', 'selected', 'rejected'}:
                    print(f"DEBUG: User {user_id} already applied to job {job_id} with resume {resume_id}")
                    return False
                # Was auto_shortlisted — delete that record then fall through to add applied below
                if 'auto_shortlisted' in statuses:
                    safe_resume = resume_id.replace("'", "''")
                    safe_job = job_id.replace("'", "''")
                    safe_user = user_id.replace("'", "''")
                    table.delete(
                        f"user_id = '{safe_user}' AND job_id = '{safe_job}' "
                        f"AND resume_id = '{safe_resume}' AND applied_status = 'auto_shortlisted'"
                    )
                    print(f"DEBUG: Deleted auto_shortlisted for job {job_id}, resume {resume_id}")
    except Exception as e:
        print(f"DEBUG: Error checking existing applications: {e}")

    table.add([{
        "id": str(uuid4()),
        "user_id": user_id,
        "job_id": job_id,
        "resume_id": resume_id,
        "applied_status": "applied",
        "timestamp": datetime.now().isoformat(),
        "notified": False,
        "notified_at": "",
    }])
    print(f"DEBUG: Applied job {job_id} using resume {resume_id} for user {user_id}")
    return True

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

def get_dashboard_stats(user_id: str, is_recruiter: bool = False):
    print(f"DEBUG: [stats] Fetching stats for user: {user_id} (IsRecruiter: {is_recruiter})")
    resumes_table = get_or_create_table()
    activity_table = get_or_create_activity_table()
    applied_table = get_or_create_job_applied_table()
    
    resumes_df = resumes_table.to_pandas()
    
    total_resumes = 0
    if not resumes_df.empty:
        if is_recruiter:
            # Recruiter sees total unique filenames across all users
            total_resumes = resumes_df['filename'].nunique()
        else:
            user_resumes = resumes_df[resumes_df['user_id'] == user_id]
            total_resumes = user_resumes['filename'].nunique()
        print(f"DEBUG: [stats] Found {total_resumes} resumes (Global: {is_recruiter})")
    
    # Activity Stats
    activity_df = activity_table.to_pandas()
    
    total_screened = 0
    high_matches = 0
    skill_gaps = 0
    quality_scored = 0
    total_applied = 0
    recent_activity = []

    # Applied Stats
    applied_df = applied_table.to_pandas()
    if not applied_df.empty:
        if is_recruiter:
            total_applied = len(applied_df)
        else:
            user_applied = applied_df[applied_df['user_id'] == user_id]
            total_applied = len(user_applied)
        print(f"DEBUG: [stats] Found {total_applied} applied jobs (Global: {is_recruiter})")


    if not activity_df.empty:
        # Filter by user_id for jobseekers, show all for recruiters
        if is_recruiter:
            view_activity = activity_df
        else:
            view_activity = activity_df[activity_df['user_id'] == user_id]
            
        print(f"DEBUG: [stats] Found {len(view_activity)} activities for view")
        
        total_screened = len(view_activity[view_activity['type'] == 'screen'])
        high_matches = len(view_activity[view_activity['score'] >= 80])
        skill_gaps = len(view_activity[view_activity['type'] == 'skill_gap'])
        quality_scored = len(view_activity[view_activity['type'] == 'quality'])
        
        # Get 5 most recent activities
        recent_df = view_activity.sort_values(by="timestamp", ascending=False).head(5)
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
        "total_applied": total_applied,
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

# ---------- RESUME METADATA (validation scores + extracted candidate metadata) ----------
resume_meta_schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("user_id", pa.string()),
    pa.field("filename", pa.string()),
    pa.field("validation_json", pa.string()),
    pa.field("uploaded_at", pa.string()),
    # Candidate metadata extracted by LLM at upload time
    pa.field("candidate_name", pa.string()),
    pa.field("role", pa.string()),
    pa.field("industry", pa.string()),
    pa.field("exp_level", pa.string()),
    pa.field("current_company", pa.string()),
    pa.field("location", pa.string()),
    pa.field("metro_location", pa.string()),    # LLM-resolved major metro (e.g. "Los Angeles, CA")
    pa.field("phone", pa.string()),
    pa.field("email", pa.string()),
    pa.field("linkedin_url", pa.string()),
    pa.field("github_url", pa.string()),
    pa.field("skills_json", pa.string()),         # JSON array of {name, level}
    pa.field("summary", pa.string()),             # 1-2 sentence professional headline
    pa.field("years_experience", pa.string()),    # total years as string e.g. "11"
    pa.field("education", pa.string()),           # highest degree + institution
    pa.field("certifications_json", pa.string()), # JSON array of cert names
])

_RESUME_META_COLS = ["candidate_name", "role", "industry", "exp_level",
                     "current_company", "location", "metro_location", "phone", "email",
                     "linkedin_url", "github_url", "skills_json",
                     "summary", "years_experience", "education", "certifications_json"]

_RESUME_META_NEW_COLS = {"phone", "email", "linkedin_url", "github_url",
                         "summary", "years_experience", "education", "certifications_json",
                         "metro_location"}


def get_or_create_resume_meta_table():
    if "resume_meta" not in db.table_names():
        return db.create_table("resume_meta", schema=resume_meta_schema, mode="create")
    table = db.open_table("resume_meta")
    # Migrate: add any columns that exist in schema but not in the table
    missing = _RESUME_META_NEW_COLS - set(table.schema.names)
    if missing:
        df = table.to_pandas()
        for col in missing:
            df[col] = None
        db.drop_table("resume_meta")
        db.create_table("resume_meta", data=df, schema=resume_meta_schema, mode="create")
        table = db.open_table("resume_meta")
    return table


def store_resume_validation(user_id: str, filename: str, validation: dict,
                            metadata: dict = None):
    """Upsert validation results + optional candidate metadata for a resume."""
    import json
    from datetime import datetime
    table = get_or_create_resume_meta_table()
    try:
        table.delete(f"user_id = '{user_id}' AND filename = '{filename}'")
    except Exception:
        pass
    meta = metadata or {}
    skills = meta.get("skills") or []
    table.add([{
        "id": str(uuid4()),
        "user_id": user_id,
        "filename": filename,
        "validation_json": json.dumps(validation or {}),
        "uploaded_at": datetime.now().isoformat(),
        "candidate_name": meta.get("candidate_name") or None,
        "role": meta.get("role") or None,
        "industry": meta.get("industry") or None,
        "exp_level": meta.get("exp_level") or None,
        "current_company": meta.get("current_company") or None,
        "location": meta.get("location") or None,
        "phone": meta.get("phone") or None,
        "email": meta.get("email") or None,
        "linkedin_url": meta.get("linkedin_url") or None,
        "github_url":          meta.get("github_url") or None,
        "skills_json":         json.dumps(skills) if skills else None,
        "summary":             meta.get("summary") or None,
        "years_experience":    str(meta.get("years_experience") or "").strip() or None,
        "education":           meta.get("education") or None,
        "certifications_json": json.dumps(meta.get("certifications") or []),
    }])

def get_resume_validations(user_id: str) -> dict:
    """Return {filename: validation_dict} for all resumes of a user."""
    import json
    table = get_or_create_resume_meta_table()
    try:
        df = table.to_pandas()
        if df.empty:
            return {}
        user_df = df[df['user_id'] == user_id]
        result = {}
        for _, row in user_df.iterrows():
            try:
                result[row['filename']] = json.loads(row['validation_json'])
            except Exception:
                result[row['filename']] = {}
        return result
    except Exception as e:
        print(f"DEBUG: Failed to get resume validations for {user_id}: {e}")
        return {}

def delete_resume_validation(user_id: str, filename: str):
    """Remove validation record for a resume."""
    table = get_or_create_resume_meta_table()
    try:
        table.delete(f"user_id = '{user_id}' AND filename = '{filename}'")
    except Exception:
        pass

# ---------- DELETE USER RESUME ----------
def delete_user_resume(user_id: str, filename: str):
    """Delete all LanceDB entries for a specific user's resume across all tables."""
    safe_fn = filename.replace("'", "''")
    safe_uid = user_id.replace("'", "''")

    # 1. Resume chunks + vectors
    table = get_or_create_table()
    try:
        table.delete(f"user_id = '{safe_uid}' AND filename = '{safe_fn}'")
        print(f"DEBUG: Deleted resume chunks '{filename}' for user {user_id}")
    except Exception as e:
        print(f"DEBUG: Failed to delete resume chunks '{filename}' for {user_id}: {e}")
        raise e

    # 2. Job applications referencing this resume
    try:
        applied_table = get_or_create_job_applied_table()
        applied_table.delete(f"user_id = '{safe_uid}' AND resume_id = '{safe_fn}'")
        print(f"DEBUG: Deleted job_resume_applied rows for '{filename}'")
    except Exception as e:
        print(f"DEBUG: Failed to clean job_resume_applied for '{filename}': {e}")

    # 3. Activity log entries referencing this resume
    try:
        activity_table = get_or_create_activity_table()
        activity_table.delete(f"user_id = '{safe_uid}' AND filename = '{safe_fn}'")
        print(f"DEBUG: Deleted activity rows for '{filename}'")
    except Exception as e:
        print(f"DEBUG: Failed to clean activity for '{filename}': {e}")

# ---------- LIST USER RESUMES ----------
def list_user_resumes(user_id: str) -> list:
    """Return a list of unique filenames uploaded by the given user."""
    table = get_or_create_table()
    try:
        df = table.to_pandas()[["filename", "user_id"]]
        if df.empty:
            return []
        user_df = df[df['user_id'] == user_id]
        return user_df['filename'].drop_duplicates().tolist()
    except Exception as e:
        print(f"DEBUG: Failed to list resumes for {user_id}: {e}")
        return []

# ---------- UPDATE ----------
def update_resume_text(filename: str, user_id: str, new_text: str, api_key: str = None):
    """Delete existing chunks for a resume and re-store with updated text."""
    table = get_or_create_table()
    try:
        table.delete(f"filename = '{filename}' AND user_id = '{user_id}'")
        print(f"DEBUG: Deleted old chunks for {filename} (user: {user_id})")
    except Exception as e:
        print(f"DEBUG: Error deleting old chunks: {e}")
    store_resume(filename, new_text, user_id, api_key=api_key)


def rename_resume(old_filename: str, new_filename: str, user_id: str):
    """Propagate a resume rename across all tables that reference it by filename."""
    safe_old = old_filename.replace("'", "''")

    # 1. Update resumes table — keep existing vectors, just swap filename
    table = get_or_create_table()
    try:
        df = table.to_pandas()
        if not df.empty:
            mask = (df['filename'] == old_filename) & (df['user_id'] == user_id)
            rows = df[mask].copy()
            if not rows.empty:
                table.delete(f"filename = '{safe_old}' AND user_id = '{user_id}'")
                rows['filename'] = new_filename
                table.add(rows.to_dict('records'))
                print(f"DEBUG: Renamed {len(rows)} resume chunks: {old_filename} -> {new_filename}")
    except Exception as e:
        print(f"DEBUG: Error renaming in resumes table: {e}")
        raise

    # 2. Update activity table
    try:
        activity_table = get_or_create_activity_table()
        act_df = activity_table.to_pandas()
        if not act_df.empty:
            mask = (act_df['filename'] == old_filename) & (act_df['user_id'] == user_id)
            rows = act_df[mask].copy()
            if not rows.empty:
                activity_table.delete(f"filename = '{safe_old}' AND user_id = '{user_id}'")
                rows['filename'] = new_filename
                activity_table.add(rows.to_dict('records'))
                print(f"DEBUG: Updated {len(rows)} activity records for renamed resume")
    except Exception as e:
        print(f"DEBUG: Error updating activity table on rename: {e}")

    # 3. Update job_resume_applied table (resume_id stores the filename)
    try:
        applied_table = get_or_create_job_applied_table()
        applied_df = applied_table.to_pandas()
        if not applied_df.empty:
            mask = (applied_df['resume_id'] == old_filename) & (applied_df['user_id'] == user_id)
            rows = applied_df[mask].copy()
            if not rows.empty:
                applied_table.delete(f"resume_id = '{safe_old}' AND user_id = '{user_id}'")
                rows['resume_id'] = new_filename
                applied_table.add(rows.to_dict('records'))
                print(f"DEBUG: Updated {len(rows)} job application records for renamed resume")
    except Exception as e:
        print(f"DEBUG: Error updating job_resume_applied table on rename: {e}")


# ---------- LIST ALL (recruiter/manager) ----------
def list_all_resumes_with_users():
    """Return all distinct resumes across all users with their uploader's user_id."""
    table = get_or_create_table()
    try:
        df = table.to_pandas()[["filename", "user_id"]]
        seen = set()
        results = []
        for _, row in df.iterrows():
            fn = row["filename"]
            if fn and fn not in seen:
                seen.add(fn)
                results.append({"filename": fn, "user_id": row["user_id"]})
        return results
    except Exception as e:
        print(f"DEBUG: list_all_resumes_with_users error: {e}")
        return []


def get_resume_text_map(filenames: list) -> dict:
    """Return {filename: text} for the given list of filenames (used for location filtering)."""
    if not filenames:
        return {}
    table = get_or_create_table()
    try:
        result = {}
        unique_files = []
        seen = set()
        for fn in filenames:
            if fn and fn not in seen:
                seen.add(fn)
                unique_files.append(fn)

        # Query only requested filenames in manageable chunks to avoid scanning all rows.
        CHUNK = 50
        for i in range(0, len(unique_files), CHUNK):
            batch = unique_files[i:i + CHUNK]
            safe_names = [str(n).replace("'", "''") for n in batch]
            where = " OR ".join([f"filename = '{n}'" for n in safe_names])
            rows = table.search().where(where).limit(20000).to_list()
            for row in rows:
                fn = row.get("filename")
                if fn in seen and fn not in result:
                    result[fn] = row.get("text") or ""
        return result
    except Exception as e:
        print(f"DEBUG: get_resume_text_map error: {e}")
        return {}


# ---------- PURGE DANGLING METADATA ----------

def purge_dangling_meta() -> list:
    """Remove resume_meta (and orphaned chunks) where either:
      - The meta row has no corresponding chunks in the resumes table, OR
      - The physical file no longer exists on disk (lost file — DB is stale).

    Called at server startup and available to the API layer. Returns list of purged filenames.
    """
    import os
    from pathlib import Path as _Path

    # Derive upload dir the same way the app config does
    upload_dir = str(_PROJECT_ROOT / "data" / "raw_resumes")

    try:
        chunks_table = get_or_create_table()
        chunks_df = chunks_table.to_pandas()
        chunks_filenames = set(chunks_df["filename"].unique()) if not chunks_df.empty else set()
    except Exception as e:
        print(f"DEBUG: [purge] Could not load chunks table: {e}")
        return []

    try:
        meta_table = get_or_create_resume_meta_table()
        meta_df = meta_table.to_pandas()
        if meta_df.empty:
            return []
        meta_filenames = set(meta_df["filename"].unique())
    except Exception as e:
        print(f"DEBUG: [purge] Could not load meta table: {e}")
        return []

    # Case 1: meta with no chunks
    no_chunks = meta_filenames - chunks_filenames

    # Case 2: has chunks + meta but physical file is gone from disk
    disk_missing = {
        fn for fn in meta_filenames
        if not os.path.exists(os.path.join(upload_dir, fn))
    }

    dangling = no_chunks | disk_missing

    purged = []
    for fn in sorted(dangling):
        safe = fn.replace("'", "''")
        try:
            meta_table.delete(f"filename = '{safe}'")
        except Exception as e:
            print(f"DEBUG: [purge] Failed to remove meta for '{fn}': {e}")
            continue
        # Also remove orphaned chunks if disk file is missing
        if fn in disk_missing:
            try:
                chunks_table.delete(f"filename = '{safe}'")
            except Exception as e:
                print(f"DEBUG: [purge] Failed to remove chunks for '{fn}': {e}")
        purged.append(fn)
        print(f"DEBUG: [purge] Removed dangling entry for '{fn}'")

    if purged:
        print(f"DEBUG: [purge] Removed {len(purged)} dangling entries: {purged}")
    return purged


# ---------- HYBRID SEARCH UTILITIES ----------

# Track which tables already have an FTS index this session to avoid recreating
_fts_indexed: set = set()

def _ensure_fts_index(table, columns: list, table_name: str) -> list:
    """Create per-column FTS indexes lazily (LanceDB supports only one field per index).

    Returns the list of columns that now have a usable FTS index.
    """
    global _fts_indexed
    ready = []
    for col in columns:
        key = f"{table_name}.{col}"
        if key in _fts_indexed:
            ready.append(col)
            continue
        try:
            table.create_fts_index(col, replace=True)
            _fts_indexed.add(key)
            print(f"DEBUG: [fts] Created FTS index on {table_name}.{col}")
            ready.append(col)
        except Exception as e:
            print(f"DEBUG: [fts] Could not create FTS index on {table_name}.{col}: {e}")
    return ready


def _rrf_merge(ranked_lists: list, k: int = 60) -> list:
    """
    Reciprocal Rank Fusion: merge multiple ranked ID lists into one.
    score(id) = Σ 1 / (k + rank_i + 1)  for each list that contains id.
    Returns IDs sorted by descending combined score.
    """
    scores: dict = {}
    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)


# ---------- SEARCH ----------

def search_resumes_hybrid(query: str, user_id: str, limit: int = 5, api_key: str = None,
                          is_recruiter: bool = False, pre_computed_vector: list = None):
    """
    Hybrid search: vector (semantic) + FTS (keyword) merged with Reciprocal Rank Fusion.
    Falls back gracefully — if one source fails, the other is used alone.
    Returns a pandas DataFrame in RRF-merged order (compatible with search_resumes_semantic).

    pre_computed_vector: optional pre-computed query embedding (avoids a second embed API call
    when the caller already embedded the query in parallel with intent parsing).
    """
    import pandas as pd
    print(f"DEBUG: Hybrid search query: {query!r} (IsRecruiter: {is_recruiter})")
    table = get_or_create_table()
    if len(table) == 0:
        return pd.DataFrame()

    where_clause = None if is_recruiter else f"user_id = '{user_id}'"

    # -- Vector (semantic) search --
    sem_rows: list = []
    try:
        embeddings = get_embeddings_model(api_key=api_key)
        query_vector = pre_computed_vector if pre_computed_vector is not None else embeddings.embed_query(query)
        op = table.search(query_vector)
        if where_clause:
            op = op.where(where_clause)
        sem_rows = op.limit(limit).to_list()
        print(f"DEBUG: [hybrid] Semantic returned {len(sem_rows)} rows")
    except Exception as e:
        print(f"DEBUG: [hybrid] Semantic search failed: {e}")

    # -- FTS (keyword) search --
    fts_rows: list = []
    if _ensure_fts_index(table, ["text"], "resumes"):
        try:
            op = table.search(query, query_type="fts", fts_columns="text")
            if where_clause:
                op = op.where(where_clause)
            fts_rows = op.limit(limit).to_list()
            print(f"DEBUG: [hybrid] FTS returned {len(fts_rows)} rows")
        except Exception as e:
            print(f"DEBUG: [hybrid] FTS search failed: {e}")

    if not sem_rows and not fts_rows:
        return pd.DataFrame()

    # Deduplicate each source to a ranked filename list (first occurrence = best chunk)
    def _dedup(rows: list) -> list:
        seen: set = set()
        out: list = []
        for r in rows:
            fn = r.get("filename", "")
            if fn and fn not in seen:
                seen.add(fn)
                out.append(fn)
        return out

    sem_fns = _dedup(sem_rows)
    fts_fns = _dedup(fts_rows)
    print(f"DEBUG: [hybrid] Unique filenames — semantic: {len(sem_fns)}, fts: {len(fts_fns)}")

    # RRF merge
    lists = [l for l in [sem_fns, fts_fns] if l]
    merged_fns = _rrf_merge(lists)

    # Build row lookup — prefer semantic row (richer data with distance)
    row_lookup: dict = {}
    for r in fts_rows:
        fn = r.get("filename", "")
        if fn and fn not in row_lookup:
            row_lookup[fn] = r
    for r in sem_rows:
        fn = r.get("filename", "")
        if fn:
            row_lookup[fn] = r

    records = [row_lookup[fn] for fn in merged_fns if fn in row_lookup]
    df = pd.DataFrame(records[:limit])
    print(f"DEBUG: [hybrid] Final merged result: {len(df)} rows")
    return df


def search_jobs_hybrid(query: str, limit: int = 50, api_key: str = None,
                       where_clause: str = None, fetch_cap: int = 500) -> list:
    """
    Hybrid search for jobs: vector + FTS merged with RRF.
    Returns a list of raw LanceDB row dicts in merged order.
    Falls back gracefully — if one source fails, the other is used alone.
    """
    table = get_or_create_jobs_table()
    if len(table) == 0:
        return []

    # -- Vector (semantic) search --
    sem_rows: list = []
    try:
        embeddings = get_embeddings_model(api_key=api_key)
        query_vector = embeddings.embed_query(query)
        op = table.search(query_vector).metric("cosine")
        if where_clause:
            op = op.where(where_clause)
        sem_rows = op.limit(fetch_cap).to_list()
        print(f"DEBUG: [hybrid-jobs] Semantic returned {len(sem_rows)} rows")
    except Exception as e:
        print(f"DEBUG: [hybrid-jobs] Semantic search failed: {e}")

    # -- FTS (keyword) search — one index per column, results merged by job_id --
    fts_rows: list = []
    fts_cols = _ensure_fts_index(table, ["title", "description", "employer_name"], "jobs")
    if fts_cols:
        fts_seen: set = set()
        for col in fts_cols:
            try:
                op = table.search(query, query_type="fts", fts_columns=col)
                if where_clause:
                    op = op.where(where_clause)
                col_rows = op.limit(fetch_cap).to_list()
                for r in col_rows:
                    jid = r.get("job_id", "")
                    if jid and jid not in fts_seen:
                        fts_seen.add(jid)
                        fts_rows.append(r)
            except Exception as e:
                print(f"DEBUG: [hybrid-jobs] FTS search on '{col}' failed: {e}")
        if fts_rows:
            print(f"DEBUG: [hybrid-jobs] FTS returned {len(fts_rows)} unique rows across {fts_cols}")

    if not sem_rows and not fts_rows:
        return []

    # Deduplicate each source to a ranked job_id list
    def _dedup(rows: list) -> list:
        seen: set = set()
        out: list = []
        for r in rows:
            jid = r.get("job_id", "")
            if jid and jid not in seen:
                seen.add(jid)
                out.append(jid)
        return out

    sem_ids = _dedup(sem_rows)
    fts_ids = _dedup(fts_rows)
    print(f"DEBUG: [hybrid-jobs] Unique jobs — semantic: {len(sem_ids)}, fts: {len(fts_ids)}")

    lists = [l for l in [sem_ids, fts_ids] if l]
    merged_ids = _rrf_merge(lists)

    # Build row lookup — prefer semantic row (has _distance)
    row_lookup: dict = {}
    for r in fts_rows:
        jid = r.get("job_id", "")
        if jid and jid not in row_lookup:
            row_lookup[jid] = r
    for r in sem_rows:
        jid = r.get("job_id", "")
        if jid:
            row_lookup[jid] = r

    result = [row_lookup[jid] for jid in merged_ids if jid in row_lookup]
    print(f"DEBUG: [hybrid-jobs] Final merged result: {len(result)} rows")
    return result
