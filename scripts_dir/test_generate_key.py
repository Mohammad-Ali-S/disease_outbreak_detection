import requests

API_URL = "http://localhost:8000"

def test_keygen():
    # 1. Login
    print("Logging in...")
    try:
        res = requests.post(f"{API_URL}/api/auth/login", json={"username": "admin", "password": "admin"})
        if res.status_code != 200:
            print(f"Login failed: {res.status_code} {res.text}")
            return
        token = res.json()['access_token']
        print("Login successful.")
        
        # 2. Generate Key
        print("Generating Key...")
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.post(f"{API_URL}/api/hospital/key", headers=headers)
        
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_keygen()
