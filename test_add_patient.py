import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def run_test():
    print("1. Registering User...")
    try:
        res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "username": "debug_admin",
            "password": "password123",
            "role": "admin",
            "hospital_id": "H_DEBUG"
        })
        if res.status_code == 400 and "already registered" in res.text:
            print("   User already exists, proceeding to login.")
        elif res.status_code != 200:
            print(f"   Registration failed: {res.status_code} {res.text}")
            return
        else:
            print("   Registered successfully.")
    except Exception as e:
        print(f"   Connection failed: {e}")
        return

    print("2. Logging In...")
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "debug_admin",
        "password": "password123"
    })
    
    if res.status_code != 200:
        print(f"   Login failed: {res.status_code} {res.text}")
        return
    
    token = res.json()['access_token']
    print("   Logged in. Token acquired.")

    print("3. Adding Patient...")
    data = {
        "admission_date": "2026-01-23",
        "is_flu_positive": True
    }
    
    try:
        res = requests.post(
            f"{BASE_URL}/api/patients", 
            json=data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10 # 10s timeout
        )
        print(f"   Response Status: {res.status_code}")
        print(f"   Response Body: {res.text}")
    except requests.exceptions.Timeout:
        print("   TIMEOUT! Both backend and database might be locked.")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    run_test()
