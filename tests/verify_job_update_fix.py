import requests
import json
import lancedb
import os
import uuid

# Backend URL
BASE_URL = "http://127.0.0.1:8000/api/v1"

# 1. Manually insert a job into the DB owned by 'user_alex_chen_123'
db_path = os.path.join(os.getcwd(), "data", "lancedb")
if not os.path.exists(db_path):
    db_path = os.path.join(os.getcwd(), "backend", "data", "lancedb")

db = lancedb.connect(db_path)
table = db.open_table("jobs")

test_job_id = str(uuid.uuid4())
alex_user_id = "user_alex_chen_123"

# Get a sample row to copy the vector format if needed (though we can just use zeros)
sample_rows = table.search().limit(1).to_list()
sample_vector = [0.0] * 1536
if sample_rows:
    sample_vector = sample_rows[0].get("vector", sample_vector)

job_record = {
    "job_id": test_job_id,
    "user_id": alex_user_id,
    "title": "Test Job for Permission Fix",
    "description": "Created by Alex Chen",
    "employer_name": "Alex Inc",
    "employer_email": "alex@example.com",
    "location_name": "Remote",
    "posted_date": "2026-03-27T00:00:00",
    "vector": sample_vector,
    "employment_type": "FULL_TIME",
    "job_category": "IT",
    "job_level": "MID"
}

table.add([job_record])
print(f"Created test job {test_job_id} owned by {alex_user_id}")

# 2. Try to update this job as a MANAGER (should succeed now)
manager_headers = {
    "Authorization": "Bearer manager_token",
    "Content-Type": "application/json"
}

update_data = {
    "title": "Test Job for Permission Fix (Updated by Manager)",
    "description": "Updated by Manager",
    "employer_name": "Alex Inc",
    "location_name": "Remote",
    "salary_min": 100000,
    "salary_max": 200000,
    "skills_required": ["Fixing Bugs"]
}

print(f"Attempting to update job {test_job_id} as manager...")
resp = requests.put(f"{BASE_URL}/jobs/{test_job_id}", json=update_data, headers=manager_headers)

print(f"Manger Update Status: {resp.status_code}")
if resp.status_code == 200:
    print("SUCCESS: Manager successfully updated a job they don't own!")
else:
    print(f"FAILURE: Manager failed to update job. Response: {resp.text}")

# 3. Try to update as a DIFFERENT jobseeker (should fail with 404)
seeker_headers = {
    "Authorization": "Bearer seeker_token",
    "X-User-ID": "uid_other_seeker@example.com",
    "Content-Type": "application/json"
}

print(f"Attempting to update job {test_job_id} as another seeker...")
resp2 = requests.put(f"{BASE_URL}/jobs/{test_job_id}", json=update_data, headers=seeker_headers)

print(f"Seeker Update Status: {resp2.status_code}")
if resp2.status_code == 404:
    print("SUCCESS: Other seeker was correctly denied access (404).")
else:
    print(f"FAILURE: Other seeker should have been denied but got {resp2.status_code}: {resp2.text}")

# Clean up
table.delete(f"job_id = '{test_job_id}'")
print(f"Cleaned up test job {test_job_id}")
