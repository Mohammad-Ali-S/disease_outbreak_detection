import requests
import json

url = "http://localhost:8000/api/public/report"
payload = {
    "latitude": 43.6532,
    "longitude": -79.3832,
    "symptoms": "Fever, Cough"
}

try:
    print(f"POSTing to {url}")
    res = requests.post(url, json=payload)
    print(f"Status: {res.status_code}")
    print(f"Response: {res.text}")
except Exception as e:
    print(f"Error: {e}")

try:
    print(f"GETting {url}")
    res = requests.get(url)
    print(f"Status: {res.status_code}")
    print(f"Response: {res.text}")
except Exception as e:
    print(f"Error: {e}")
