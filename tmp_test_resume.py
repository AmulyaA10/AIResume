import requests

# Test resume semantic search
resp = requests.get("http://localhost:8000/api/v1/resumes/database", 
    headers={ "Authorization": "Bearer recruiter_dummy_token" },
    params={"search": "python developer", "limit": 10}
)

print("Status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print("Resumes found:", data.get("total", len(data.get("resumes", []))))
    print("First item:", list(data.get("resumes", []))[:1])
else:
    print(resp.text[:500])
