import sqlite3
import random
from datetime import datetime, timedelta
import os

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "backend/database/warehouse.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    # Enable WAL for concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def populate_hospitals(conn):
    print("Populating Hospitals...")
    hospitals = [
        ("H001", "Toronto General", 43.6596, -79.3884, "Toronto", "Ontario"),
        ("H002", "Mount Sinai", 43.6573, -79.3903, "Toronto", "Ontario"),
        ("H003", "St. Michael's", 43.6534, -79.3790, "Toronto", "Ontario"),
        ("H004", "Sunnybrook", 43.7220, -79.3756, "North York", "Ontario"),
        ("H005", "North York General", 43.7691, -79.3643, "North York", "Ontario"),
    ]
    
    cur = conn.cursor()
    count = 0
    for hid, name, lat, lon, city, region in hospitals:
        # Check if exists
        exists = cur.execute("SELECT 1 FROM dim_hospital WHERE hospital_id = ?", (hid,)).fetchone()
        if not exists:
            cur.execute("""
                INSERT INTO dim_hospital (hospital_id, name, latitude, longitude, city, region, total_beds, icu_beds)
                VALUES (?, ?, ?, ?, ?, ?, 200, 40)
            """, (hid, name, lat, lon, city, region))
            count += 1
    conn.commit()
    print(f"  Added {count} new hospitals.")
    return [h[0] for h in hospitals]

def populate_patients(conn, hospital_ids):
    print("Populating Patients...")
    # Generate data for last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    cur = conn.cursor()
    total_added = 0
    
    for _ in range(500): # Generate 500 records
        # Random date
        days_offset = random.randint(0, 30)
        record_date = (start_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")
        
        # Random Hospital
        visiting_hospital = random.choice(hospital_ids)
        
        # Flu Logic: Clustered outbreak logic (simplified)
        # Higher chance of flu in 'Cluster' hospitals (H001, H002)
        is_flu = False
        rand_val = random.random()
        
        if visiting_hospital in ['H001', 'H002']:
            if rand_val < 0.4: is_flu = True # 40% chance
        else:
            if rand_val < 0.1: is_flu = True # 10% chance
            
        cur.execute("""
            INSERT INTO patients (hospital_id, admission_date, age, gender, is_flu_positive, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (visiting_hospital, record_date, random.randint(18, 90), random.choice(['M', 'F']), is_flu, 'Admitted'))
        total_added += 1
        
    conn.commit()
    print(f"  Added {total_added} patient records.")

def main():
    try:
        conn = get_db()
        
        # Ensure schema exists first (basic check)
        try:
            conn.execute("SELECT count(*) FROM dim_hospital")
        except sqlite3.OperationalError:
            print("Tables not found. Please run 'setup_database.py' first.")
            return

        h_ids = populate_hospitals(conn)
        populate_patients(conn, h_ids)
        
        print("\nDemo Data Population Complete!")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
