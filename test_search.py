
import requests

try:
    resp = requests.get("http://localhost:8000/api/hospital/search?q=Sinai")
    print(f"Status: {resp.status_code}")
    print(f"Data: {resp.json()[:1]}") # Print first result
except Exception as e:
    print(e)
