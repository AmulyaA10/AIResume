import requests
import json

# Backend URL
BASE_URL = "http://127.0.0.1:8000/api/v1"

# Realistic Job ID from the previous check
job_id = "e2deabbb-ebcd-419b-a0db-06751d4c753c"

# Headers for manager role
headers = {
    "Authorization": "Bearer manager_token",
    "Content-Type": "application/json"
}

# Dummy JobUpdate data (matches JobCreate model)
job_data = {
    "title": "Energy Systems Software Engineer (Updated)",
    "description": "Updated description for testing 404 issue.",
    "employer_name": "Test Employer",
    "location_name": "Remote",
    "salary_min": 100000,
    "salary_max": 150000,
    "salary_currency": "USD",
    "job_level": "SENIOR",
    "employment_type": "FULL_TIME",
    "skills_required": ["Python", "AWS"]
}

print(f"Testing PUT {BASE_URL}/jobs/{job_id}")
response = requests.put(f"{BASE_URL}/jobs/{job_id}", json=job_data, headers=headers)

print(f"Status Code: {response.status_code}")
try:
    print(f"Response: {response.json()}")
except:
    print(f"Response Text: {response.text}")

if response.status_code == 404:
    print("Reproduced 404!")
elif response.status_code == 200:
    print("Success! Could not reproduce 404.")
else:
    print(f"Unexpected status code: {response.status_code}")
