import requests

resp = requests.post("http://localhost:8000/api/v1/jobs/parse-query-intent", 
    headers={ "Authorization": "Bearer test_user_dummy_token" },
    json={"query": "python developer"}
)

print(resp.status_code)
print(resp.text)
