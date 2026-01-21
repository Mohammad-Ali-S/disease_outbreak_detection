import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "backend/database/warehouse.db"
HOSPITALS = ['H001', 'H002', 'H003', 'H004', 'H005'] # Assuming these exist in dim_hospital

def populate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Ensure Hospitals Exist in Dim
    print("Checking hospitals...")
    existing = [r[0] for r in cursor.execute("SELECT hospital_id FROM dim_hospital").fetchall()]
    
    for h in HOSPITALS:
        if h not in existing:
            # Add dummy hospital location
            lat = 43.65 + random.uniform(-0.1, 0.1)
            lon = -79.38 + random.uniform(-0.1, 0.1)
            cursor.execute("INSERT INTO dim_hospital (hospital_id, name, region, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
                           (h, f"Hospital {h}", "Toronto", lat, lon))
            print(f"Created {h}")
            
    # 2. Insert Patients (Last 14 days)
    print("Inserting patient records...")
    start_date = datetime.now() - timedelta(days=14)
    
    count = 0
    for day in range(15):
        curr_date = (start_date + timedelta(days=day)).strftime("%Y-%m-%d")
        
        # Create a "wave" pattern: H001 starts early, H002 follows...
        for h_idx, h_id in enumerate(HOSPITALS):
            # Peak shifts by hospital
            peak_day = 3 + (h_idx * 2) 
            intensity = max(0, 10 - abs(day - peak_day)) 
            
            num_patients = int(random.uniform(5, 10) + intensity)
            
            for _ in range(num_patients):
                is_flu = random.random() < (0.3 + (intensity * 0.05)) # Higher probability near peak
                cursor.execute("INSERT INTO patients (hospital_id, admission_date, is_flu_positive) VALUES (?, ?, ?)",
                               (h_id, curr_date, is_flu))
                count += 1
                
    conn.commit()
    conn.close()
    print(f"Successfully added {count} synthetic patient records.")

if __name__ == "__main__":
    populate()
