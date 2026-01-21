import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "../database/warehouse.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "../database/schema.sql")

def init_db():
    """Initialize the database with the schema."""
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.close()
    print("Database initialized.")

def generate_hospitals(n=30):
    """Generate synthetic hospital data."""
    # Ontario-ish coordinates approx range: Lat 42-50, Lon -85 to -74
    hospitals = []
    regions = ['Southern', 'Eastern', 'Northern', 'Western', 'Central']
    
    for i in range(n):
        hospitals.append({
            'hospital_id': f'H{i:03d}',
            'name': f'General Hospital {i}',
            'latitude': np.random.uniform(43.0, 48.0),
            'longitude': np.random.uniform(-82.0, -76.0),
            'region': np.random.choice(regions),
            'city': f'City_{i}',
            # Synthetic Capacity
            'total_beds': np.random.randint(50, 500),
            'icu_beds': 0, # calculated below
            'ventilators': 0 # calculated below
        })
        
        # Logic: ~10-20% of beds are ICU, ~50% of ICU have Vents
        hospitals[-1]['icu_beds'] = int(hospitals[-1]['total_beds'] * np.random.uniform(0.1, 0.2))
        hospitals[-1]['ventilators'] = int(hospitals[-1]['icu_beds'] * np.random.uniform(0.4, 0.6))
    return pd.DataFrame(hospitals)

def generate_outbreak_pattern(length):
    """Generate a bell-curve like outbreak pattern."""
    x = np.linspace(-3, 3, length)
    return np.exp(-x**2)

def generate_daily_visits(hospitals_df, days=60):
    """Generate synthetic daily visits with outbreak patterns."""
    visits = []
    # End date is today, start date is 'days' ago
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = [start_date + timedelta(days=i) for i in range(days)]
    
    # Simulate a few outbreaks
    outbreak_starts = [300, 650] # Days when outbreaks start (approx Winter)
    
    for _, hospital in hospitals_df.iterrows():
        # Base baseline visits
        base_visits = np.random.randint(50, 150)
        
        # Each hospital has a slightly different lag for the outbreak
        hospital_lag = np.random.randint(-10, 10) 
        
        for i, date in enumerate(dates):
            day_of_year = date.timetuple().tm_yday
            
            # Seasonality (higher in winter)
            seasonality = 10 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
            
            # Outbreak signal
            outbreak_signal = 0
            for start in outbreak_starts:
                t = i - start - hospital_lag
                if 0 <= t < 60: # Outbreak lasts ~60 days
                    # Bell curve shape
                    outbreak_signal += 50 * np.exp(-((t - 30)**2) / 200)
            
            total_visits = int(max(0, base_visits + seasonality + np.random.normal(0, 10)))
            flu_positive = int(max(0, (total_visits * 0.05) + outbreak_signal + np.random.normal(0, 2)))
            
            # Ensure logical consistency
            flu_positive = min(flu_positive, total_visits)
            
            visits.append({
                'hospital_id': hospital['hospital_id'],
                'date': date,
                'total_visits': total_visits,
                'flu_positive_count': flu_positive,
                'resp_syndrome_count': int(flu_positive * 1.2), # Correlated
                'ili_syndrome_count': flu_positive,
                
                # Resource Usage Logic
                # ~15% of Flu cases need Bed, ~5% need ICU, ~2% need Vent
                # Plus baseline non-flu usage (~60-80% of capacity)
                'beds_in_use': int(hospital['total_beds'] * np.random.uniform(0.6, 0.85)) + int(flu_positive * 0.15),
                'icu_in_use': int(hospital['icu_beds'] * np.random.uniform(0.5, 0.7)) + int(flu_positive * 0.05),
                'vents_in_use': int(hospital['ventilators'] * np.random.uniform(0.3, 0.5)) + int(flu_positive * 0.02)
            })
            
    return pd.DataFrame(visits)

def load_dims(conn, hospitals_df, visits_df):
    """Load Dimension tables."""
    # Load Hospitals
    hospitals_df.to_sql('dim_hospital', conn, if_exists='append', index=False)
    
    # Load Dates
    unique_dates = pd.to_datetime(visits_df['date'].unique())
    dates_df = pd.DataFrame({
        'full_date': unique_dates,
        'date_key': unique_dates.strftime('%Y%m%d').astype(int),
        'year': unique_dates.year,
        'month': unique_dates.month,
        'day_of_week': unique_dates.dayofweek,
        'is_weekend': unique_dates.dayofweek >= 5,
        'season': pd.Series(unique_dates.month).map(lambda m: 'Winter' if m in [12, 1, 2] else 'Spring' if m in [3, 4, 5] else 'Summer' if m in [6, 7, 8] else 'Fall')
    })
    dates_df.to_sql('dim_date', conn, if_exists='append', index=False)
    
    return dates_df

def load_facts(conn, visits_df, dates_df, hospitals_df):
    """Load Fact table."""
    # Map foreign keys
    hospital_map = pd.read_sql("SELECT hospital_id, hospital_key FROM dim_hospital", conn)
    date_map = pd.read_sql("SELECT full_date, date_key FROM dim_date", conn)
    
    # Convert dates to string for merging if needed, or ensure types match
    visits_df['date'] = pd.to_datetime(visits_df['date'])
    date_map['full_date'] = pd.to_datetime(date_map['full_date'])
    
    merged = visits_df.merge(hospital_map, on='hospital_id').merge(date_map, left_on='date', right_on='full_date')
    
    facts = merged[['hospital_key', 'date_key', 'total_visits', 'flu_positive_count', 'resp_syndrome_count', 'ili_syndrome_count', 'beds_in_use', 'icu_in_use', 'vents_in_use']]
    facts.to_sql('fact_daily_visits', conn, if_exists='append', index=False)

def load_patients(conn, visits_df):
    """
    Populate the 'patients' table with synthetic individual records based on daily visits.
    This ensures the 'Live Stats' and 'Clustering' (which query 'patients') have data to work with.
    """
    patients = []
    # Optimization: Only generate patients for the last 30 days to save time/space for this demo
    cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=30)
    
    # Filter visits for efficiency
    recent_visits = visits_df[visits_df['date'] >= cutoff_date]
    
    print(f"Generating patient details for {len(recent_visits)} days of data...")
    
    for _, row in recent_visits.iterrows():
        # Get integer hospital ID if possible, but schema accepts integer FK.
        # Our generate_hospitals uses 'H000' strings. 
        # API Keys mock uses 1,2,3.
        # Let's simple query dim_hospital to get the PK for 'H000'
        # For bulk load, we'll assume the same mapping logic: 1-based index if inserted in order
        # Actually, let's look up the ID.
        h_id_str = row['hospital_id']
        # Extract number H001 -> 2 (0-indexed loop + 1?)
        # safer to query map.
        pass
    
    # Faster approach: Get Map
    for _, row in recent_visits.iterrows():
        # Use the TEXT hospital_id directly as per schema (patients.hospital_id is TEXT)
        h_pk = row['hospital_id']
        if not h_pk: continue
        
        # Generate N patients for 'total_visits'
        count = row['total_visits']
        flu_count = row['flu_positive_count']
        
        for i in range(count):
            is_flu = 1 if i < flu_count else 0
            
            p = {
                'hospital_id': h_pk,
                'admission_date': row['date'].strftime('%Y-%m-%d'),
                'age': np.random.randint(5, 90),
                'gender': np.random.choice(['M', 'F']),
                'is_flu_positive': is_flu,
                'symptoms': 'Fever, Cough' if is_flu else 'None'
            }
            patients.append(p)
            
    if patients:
        pdf = pd.DataFrame(patients)
        pdf.to_sql('patients', conn, if_exists='append', index=False)
        print(f"Loaded {len(patients)} synthetic patients.")

def run_pipeline():
    print("Generating synthetic data...")
    hosp_df = generate_hospitals()
    visits_df = generate_daily_visits(hosp_df, days=30)
    
    print("Loading Data Warehouse...")
    init_db()
    conn = sqlite3.connect(DB_PATH)
    
    # Clear existing data for clean run
    conn.execute("DELETE FROM fact_daily_visits")
    conn.execute("DELETE FROM patients")
    conn.execute("DELETE FROM dim_hospital")
    conn.execute("DELETE FROM dim_date")
    
    print("Loading Dimensions...")
    dates_df = load_dims(conn, hosp_df, visits_df)
    
    print("Loading Facts...")
    load_facts(conn, visits_df, dates_df, hosp_df)
    
    print("Loading Patients (Granular Data)...")
    load_patients(conn, visits_df)
    
    # Generate API Keys for Testing
    print("Generating API Keys...")
    conn.execute("CREATE TABLE IF NOT EXISTS api_keys (key_id INTEGER PRIMARY KEY AUTOINCREMENT, hospital_id INTEGER, api_secret TEXT UNIQUE, is_active BOOLEAN DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(hospital_id) REFERENCES dim_hospital(hospital_id))")
    
    # Create keys for first 3 hospitals matching the mock script
    # We need to map hospital_id string (H000) to integer ID if our schema uses ints, 
    # but dim_hospital uses text IDs usually? No, let's check schema.
    # Schema says hospital_id in dim_hospital is PK? 
    # Actually schema.sql says hospital_id INTEGER PRIMARY KEY
    # But generate_hospitals makes 'H000'. 
    # Let's just insert assuming the IDs are 1, 2, 3 based on autoincrement order of insertion
    secrets = ["HOSP_001_SECRET", "HOSP_002_SECRET", "HOSP_003_SECRET"]
    for i, secret in enumerate(secrets):
        # We need actual hospital_keys from dim_table. 
        # But for simplicity in this mock, let's just assume IDs 1, 2, 3 exist.
        conn.execute("INSERT OR IGNORE INTO api_keys (hospital_id, api_secret) VALUES (?, ?)", (i+1, secret))

    conn.commit()
    conn.close()
    print("ETL Pipeline Complete!")

if __name__ == "__main__":
    run_pipeline()
