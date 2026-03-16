import requests

API_URL = "http://localhost:8000/api/v1"
# We need a token. We can bypass it or check if auth is required?
# search_jobs uses Depends(get_current_user). 
# I can import the backend logic directly to test it.

import sys
sys.path.append('backend')
import asyncio
from app.routes.v1.match import search_jobs
from app.routes.v1.resumes import get_resume_database

async def test():
    print("Testing Job Search...")
    jobs = await search_jobs(q="python", limit=5, job_level=None, job_category=None, user_id="test_user")
    print(f"Jobs found: {len(jobs)}")
    for j in jobs:
        print(f"  - {j['score']:.2f}: {j['job'].get('title')} at {j['job'].get('employer_name')}")

    print("\nTesting Resume Search...")
    # get_resume_database(..., search=None, user_id, current_role)
    res = await get_resume_database(skip=0, limit=5, search="python", user_id="test_user", current_role="recruiter")
    print(f"Resumes found: {res['total']}")
    for r in res['resumes']:
        print(f"  - {r.get('filename')}: {r.get('role')} at {r.get('location')}")

if __name__ == "__main__":
    asyncio.run(test())
