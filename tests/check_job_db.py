import lancedb
import os

# Assuming the default LanceDB path
db_path = os.path.join(os.getcwd(), "data", "lancedb")
if not os.path.exists(db_path):
    # Try backend/data/lancedb
    db_path = os.path.join(os.getcwd(), "backend", "data", "lancedb")

print(f"Opening database at: {db_path}")
db = lancedb.connect(db_path)

job_id = "e2deabbb-ebcd-419b-a0db-06751d4c753c"
user_id = "user_manager_789"

try:
    table = db.open_table("jobs")
    df = table.to_pandas()
    print(f"Total jobs in table: {len(df)}")
    
    # Search for the specific job
    job = df[df["job_id"] == job_id]
    if not job.empty:
        print("Job found!")
        print(job[["job_id", "user_id", "title"]].to_dict('records'))
    else:
        print(f"Job {job_id} NOT found in the database.")
        # Print a few job IDs to see what we have
        print("Sample job IDs in DB:")
        print(df["job_id"].head().tolist())

except Exception as e:
    print(f"Error: {e}")
