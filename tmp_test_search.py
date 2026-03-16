import requests

resp = requests.get("http://localhost:8000/api/v1/match/search/jobs", 
    headers={ "Authorization": "Bearer test_user_dummy_token" },
    params={"q": "python developer", "limit": 50}
)

print(resp.status_code)
print(resp.text[:500])
