import requests
import random
import time
import uuid

# Configuration
API_URL = "http://localhost:8000/api/v1/connect/admission"
# These keys need to exist in the DB. We will add them during ETL or manually.
# For now, let's assume we will create a key "HOSP_001_SECRET" for Hospital 1
API_KEYS = ["HOSP_32_v9dQqZZ_leOOXmxgqTra-A"]

SYMPTOMS_LIST = ["Fever", "Cough", "Shortness of Breath", "Fatigue", "Headache"]

def generate_random_patient():
    is_flu = random.random() < 0.3 # 30% chance of flu
    return {
        "event_type": "ADMISSION",
        "patient_id_hash": str(uuid.uuid4())[:8],
        "age": random.randint(5, 90),
        "gender": random.choice(["M", "F"]),
        "admission_date": time.strftime("%Y-%m-%d"),
        "symptoms": ", ".join(random.sample(SYMPTOMS_LIST, k=random.randint(1, 3))),
        "diagnosis": "FLU_POS" if is_flu else "FLU_NEG"
    }

def run_simulator():
    print("Starting Hospital ERP Simulator...")
    print(f"Target: {API_URL}")
    
    while True:
        # Pick a random hospital
        key = random.choice(API_KEYS)
        
        # Generate data
        patient_data = generate_random_patient()
        
        payload = {
            "api_key": key,
            "event_type": "ADMISSION",
            "data": patient_data
        }
        
        try:
            res = requests.post(API_URL, json=payload)
            if res.status_code == 200:
                status = "FLU POSITIVE" if patient_data['diagnosis'] == "FLU_POS" else "Negative"
                print(f"[{time.strftime('%H:%M:%S')}][{key[:8]}] -> DATA PUSHED: {status}")
            else:
                print(f"[Failed] {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Connection Error: {e}")
            
        # Wait a bit (simulate traffic)
        # Fast for demo purposes
        sleep_time = random.uniform(0.2, 1.5) 
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_simulator()
