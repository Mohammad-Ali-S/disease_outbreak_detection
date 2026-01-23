from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3
import hashlib
import pandas as pd
import os
from datetime import timedelta
from fastapi.responses import FileResponse, Response

from mining.mining_engine import OutbreakMiner
import auth

app = FastAPI(title="Disease Outbreak Detection API")

# Allow CORS for Frontend (even if served statically, good for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database/warehouse.db")
STATIC_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend/out")

# Models source of truth
class UserRegister(BaseModel):
    username: str
    password: str
    role: str = "user" # 'admin' or 'user'
    hospital_id: str = None # Optional, for admins

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# --- Authentication Endpoints ---

@app.post("/api/auth/register", response_model=Token)
def register(user: UserRegister):
    if user.role not in ['admin', 'user']:
         raise HTTPException(status_code=400, detail="Invalid role")
         
    conn = get_db_connection()
    try:
        # Check if user exists
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (user.username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Username already registered")
        
        if user.hospital_id:
             # Auto-create hospital if it doesn't exist
             h_exists = conn.execute("SELECT 1 FROM dim_hospital WHERE hospital_id = ?", (user.hospital_id,)).fetchone()
             if not h_exists:
                 # Auto-create dummy hospital record
                 conn.execute("""
                    INSERT INTO dim_hospital (hospital_id, name, region, city, latitude, longitude)
                    VALUES (?, ?, ?, ?, ?, ?)
                 """, (user.hospital_id, f"Hospital {user.hospital_id}", "Toronto", "Unknown", 43.65, -79.38))

        hashed_pw = auth.get_password_hash(user.password)
        conn.execute("INSERT INTO users (username, password_hash, role, hospital_id) VALUES (?, ?, ?, ?)",
                     (user.username, hashed_pw, user.role, user.hospital_id))
        conn.commit()
        
        access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
        return {"access_token": access_token, "token_type": "bearer", "role": user.role}
    finally:
        conn.close()

@app.post("/api/auth/login", response_model=Token)
def login(user: UserLogin):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (user.username,))
        db_user = cur.fetchone()
        
        if not db_user or not auth.verify_password(user.password, db_user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        access_token = auth.create_access_token(data={"sub": db_user['username'], "role": db_user['role']})
        return {"access_token": access_token, "token_type": "bearer", "role": db_user['role']}
    finally:
        conn.close()

# Dependency
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = auth.decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user.get("role")

# --- Application Endpoints ---

@app.get("/api/health")
def health_check():
    return {"status": "ok"}


def run_simulation_internal(conn):
    try:
        visits_df = pd.read_sql("SELECT count(*) FROM patients", conn) # Dummy check
        # Real logic
        query = """
        SELECT 
            hospital_id as hospital_key, 
            admission_date as date_key, 
            SUM(CASE WHEN is_flu_positive THEN 1 ELSE 0 END) as flu_positive_count
        FROM patients
        GROUP BY hospital_id, admission_date
        """
        visits_df = pd.read_sql(query, conn)
        
        if visits_df.empty: return {"clusters": [], "network": []}
        
        visits_df['date_key'] = pd.to_datetime(visits_df['date_key'])
        hospitals_df = pd.read_sql("SELECT * FROM dim_hospital", conn)
        
        miner = OutbreakMiner(hospitals_df, visits_df)
        dist_matrix = miner.compute_distance_matrix(metric='spatial')
        clusters = miner.perform_clustering(dist_matrix, threshold=0.05)
        cluster_series = miner.calculate_cluster_series(clusters)
        edges = miner.predict_spread(cluster_series)
        
        cluster_response = []
        for cid, h_keys in clusters.items():
            members = hospitals_df[hospitals_df['hospital_key'].isin(h_keys)][['hospital_id', 'name', 'latitude', 'longitude']].to_dict('records')
            cluster_response.append({ "cluster_id": cid, "members": members })
            
        return {"clusters": cluster_response, "network": edges}
    except Exception as e:
        print(f"Mining Error: {e}")
        return {"clusters": [], "network": []}

@app.get("/api/public/dashboard")
def get_public_dashboard():
    """
    Public Endpoint: Returns live stats and latest analysis results (cached or computed).
    """
    conn = get_db_connection()
    try:
        # Live Stats from Patients Table
        total_patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        flu_positive = conn.execute("SELECT COUNT(*) FROM patients WHERE is_flu_positive = 1").fetchone()[0]
        
        # Get active hospitals (those with patient data)
        active_hospitals = conn.execute("SELECT COUNT(DISTINCT hospital_id) FROM patients").fetchone()[0]
        
        # Logic: Estimate Resource Usage based on Flu Positive Count
        # Severity Assumptions: 15% Hospitalized, 5% ICU, 2% Vent
        # We need per-hospital stats to map to capacity
        
        hospitals_query = """
        SELECT 
            h.hospital_id, h.name, h.latitude, h.longitude, h.city, h.region,
            h.total_beds, h.icu_beds, h.ventilators,
            COUNT(p.patient_id) as active_cases,
            SUM(CASE WHEN p.is_flu_positive THEN 1 ELSE 0 END) as active_flu
        FROM dim_hospital h
        LEFT JOIN patients p ON h.hospital_id = p.hospital_id AND p.admission_date >= date('now', '-14 days') -- Active window
        GROUP BY h.hospital_id
        """
        
        hospitals_rows = conn.execute(hospitals_query).fetchall()
        hospitals_list = []
        
        system_icu_capacity = 0
        system_icu_usage = 0
        
        for row in hospitals_rows:
            h = dict(row)
            # Estimate usage
            active_flu = h['active_flu'] if h['active_flu'] else 0
            
            # Estimated resources in use (Baseline 60% + Outbreak impact)
            icu_used = int(h['icu_beds'] * 0.1) + int(active_flu * 0.15) # 10% baseline + 15% of flu cases
            bed_used = int(h['total_beds'] * 0.6) + int(active_flu * 0.40) # 60% baseline + 40% of flu cases
            
            # Cap at max
            icu_used = min(icu_used, h['icu_beds'])
            bed_used = min(bed_used, h['total_beds'])
            
            h['usage'] = {
                'beds_used': bed_used,
                'icu_used': icu_used,
                'icu_utilization': round((icu_used / h['icu_beds'] if h['icu_beds'] > 0 else 0) * 100, 1),
                'bed_utilization': round((bed_used / h['total_beds'] if h['total_beds'] > 0 else 0) * 100, 1)
            }
            
            hospitals_list.append(h)
            
            system_icu_capacity += h['icu_beds']
            system_icu_usage += icu_used

        system_stress = (system_icu_usage / system_icu_capacity) if system_icu_capacity > 0 else 0

        return {
            "stats": {
                "hospitals": active_hospitals,
                "total_visits": total_patients,
                "flu_positive": flu_positive,
                "risk_level": "CRITICAL" if system_stress > 0.8 else "ELEVATED" if system_stress > 0.5 else "NOMINAL",
                "system_stress": round(system_stress * 100, 1)
            },
            "hospitals_list": hospitals_list,
            # On-the-fly Clustering for Public View
            "analysis": run_simulation_internal(conn) 
        }
    finally:
        conn.close()

@app.get("/api/public/history")
def get_public_history():
    """
    Returns daily case counts per hospital for the last 30 days.
    Used for Time-Lapse Map.
    """
    conn = get_db_connection()
    try:
        # Get last 30 days data
        query = """
        SELECT 
            p.admission_date,
            p.hospital_id,
            h.latitude,
            h.longitude,
            COUNT(*) as case_count
        FROM patients p
        JOIN dim_hospital h ON p.hospital_id = h.hospital_id
        WHERE p.admission_date >= date('now', '-30 days')
        AND p.is_flu_positive = 1
        GROUP BY p.admission_date, p.hospital_id
        ORDER BY p.admission_date ASC
        """
        rows = conn.execute(query).fetchall()
        
        # Structure: { "2023-10-01": [ {lat, lon, count}, ... ] }
        history = {}
        for r in rows:
            date = r['admission_date']
            if date not in history: history[date] = []
            history[date].append({
                "hospital_id": r['hospital_id'],
                "lat": r['latitude'],
                "lon": r['longitude'],
                "count": r['case_count']
            })
            
        return history
    finally:
        conn.close()

# --- Patient Management (Hospital Admin) ---

class PatientEntry(BaseModel):
    admission_date: str # YYYY-MM-DD
    is_flu_positive: bool

@app.post("/api/patients")
def add_patient(entry: PatientEntry, role: str = Depends(require_admin), user=Depends(get_current_user)):
    """
    Add a patient record. Linked to the Admin's assigned hospital.
    """
    conn = get_db_connection()
    try:
        # Get Admin's Hospital ID
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        if not row or not row['hospital_id']:
            # Fallback for 'Super Admins' or Demo: If no hospital assigned, assign random or ID='H000'
            # For this demo, let's assign to 'Toronto General' (ID 'H000') if null
            hospital_id = 'H000' 
        else:
            hospital_id = row['hospital_id']

        conn.execute(
            "INSERT INTO patients (hospital_id, admission_date, is_flu_positive) VALUES (?, ?, ?)",
            (hospital_id, entry.admission_date, entry.is_flu_positive)
        )
        conn.commit()
        return {"status": "success", "message": "Patient record added"}
    finally:
        conn.close()

@app.get("/api/patients/recent")
def get_recent_patients(role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        # Get Admin's Hospital ID
        # Get Admin's Hospital PK
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hospital_pk = row['hospital_id'] if row and row['hospital_id'] else None

        if hospital_pk:
             # Resolve to Text ID (H000...)
            cur = conn.execute("SELECT hospital_id FROM dim_hospital WHERE hospital_key = ?", (hospital_pk,))
            h_row = cur.fetchone()
            hospital_id = h_row['hospital_id'] if h_row else 'H000'
        else:
            hospital_id = 'H000'

        recent = conn.execute(
            """
            SELECT p.patient_id, p.admission_date, p.is_flu_positive, p.status, COALESCE(h.name, 'Unknown Hospital') as hospital_name
            FROM patients p
            LEFT JOIN dim_hospital h ON p.hospital_id = h.hospital_id
            WHERE p.hospital_id = ?
            ORDER BY p.patient_id DESC LIMIT 50
            """, (hospital_id,)
        ).fetchall()
        
        return [dict(row) for row in recent]
    finally:
        conn.close()

@app.delete("/api/patients/{patient_id}")
def delete_patient(patient_id: int, role: str = Depends(require_admin)):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()

class StatusUpdate(BaseModel):
    status: str

@app.patch("/api/patients/{patient_id}/status")
def update_patient_status(patient_id: int, update: StatusUpdate, role: str = Depends(require_admin)):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE patients SET status = ? WHERE patient_id = ?", (update.status, patient_id))
        conn.commit()
        return {"status": "updated", "new_status": update.status}
    finally:
        conn.close()

class HospitalProfile(BaseModel):
    name: str | None = None
    city: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None


def ensure_hospital_link(username, hospital_id, conn):
    """
    Ensures a user is linked to a valid hospital.
    Auto-creates hospital and proper link if missing.
    Returns: Valid hospital_id
    """
    # 1. If hospital_id is present, check if valid
    if hospital_id:
        exists = conn.execute("SELECT 1 FROM dim_hospital WHERE hospital_id = ?", (hospital_id,)).fetchone()
        if exists:
            return hospital_id
    
    # 2. If missing or invalid, create new
    import secrets
    new_hid = f"H_AUTO_{secrets.token_hex(4).upper()}"
    hospital_name = f"{username.capitalize()} Hospital"
    
    # Create Hospital (Default values)
    conn.execute("""
        INSERT INTO dim_hospital (hospital_id, name, city, region, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (new_hid, hospital_name, "Unknown City", "Unknown Region", 0.0, 0.0))
    
    # Link User
    conn.execute("UPDATE users SET hospital_id = ? WHERE username = ?", (new_hid, username))
    conn.commit()
    
    print(f"Auto-provisioned hospital {new_hid} for user {username}")
    return new_hid

@app.get("/api/hospital/profile")
def get_hospital_profile(user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        # Resolve user to hospital
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        
        # AUTO-PROVISIONING: Ensure link exists
        current_hid = row['hospital_id'] if row else None
        hospital_pk = ensure_hospital_link(user['sub'], current_hid, conn)
             
        profile = conn.execute("SELECT * FROM dim_hospital WHERE hospital_id = ?", (hospital_pk,)).fetchone()
        return dict(profile) if profile else {}
    except Exception as e:
        print(f"Profile Fetch Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch profile")
    finally:
        conn.close()

@app.post("/api/hospital/profile")
def update_hospital_profile(profile: HospitalProfile, user=Depends(get_current_user), role: str = Depends(require_admin)):
    conn = get_db_connection()
    try:
        # Resolve user to hospital
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        
        # AUTO-PROVISIONING: Ensure link exists before update
        current_hid = row['hospital_id'] if row else None
        hospital_pk = ensure_hospital_link(user['sub'], current_hid, conn)

        # Update
        # Build dynamic query based on provided fields
        fields = []
        values = []
        if profile.name: 
            fields.append("name = ?")
            values.append(profile.name)
        if profile.city:
            fields.append("city = ?")
            values.append(profile.city)
        if profile.region:
            fields.append("region = ?")
            values.append(profile.region)
        if profile.latitude is not None:
             fields.append("latitude = ?")
             values.append(profile.latitude)
        if profile.longitude is not None:
             fields.append("longitude = ?")
             values.append(profile.longitude)
             
        if not fields:
            return {"status": "no_change"}
            
        values.append(hospital_pk)
        query = f"UPDATE dim_hospital SET {', '.join(fields)} WHERE hospital_id = ?"
        
        conn.execute(query, tuple(values))
        conn.commit()
        
    finally:
        conn.close()

# --- API Key Management (ERP Integration) ---
from integrations.erp_integration import ERPIntegration

class ERPPacket(BaseModel):
    api_key: str
    event_type: str
    data: dict

@app.post("/api/v1/connect/admission")
async def receive_erp_event(packet: ERPPacket):
    """
    Endpoint for External ERP Systems to push patient data.
    """
    integrator = ERPIntegration(db_path=DB_PATH)
    
    # 1. Validate Key
    hospital_pk = integrator.validate_api_key(packet.api_key)
    if not hospital_pk:
         raise HTTPException(status_code=403, detail="Invalid API Key")

    # 2. Process Data
    if packet.event_type == "ADMISSION":
        success = integrator.process_admission_event(hospital_pk, packet.data)
        if success:
            return {"status": "success", "message": "Data ingested"}
        else:
            raise HTTPException(status_code=500, detail="Ingestion failed")
            
    return {"status": "ignored", "message": "Event type not supported"}

@app.get("/api/hospital/key")
def get_api_key(user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        # Get Hospital ID
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hospital_pk = row['hospital_id'] if row and row['hospital_id'] else None
        
        if not hospital_pk:
            return {"api_secret": None}
            
        # Get Active Key
        key_row = conn.execute("SELECT api_secret FROM api_keys WHERE hospital_id = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 1", (hospital_pk,)).fetchone()
        return {"api_secret": key_row['api_secret'] if key_row else None}
    finally:
        conn.close()

@app.post("/api/hospital/key")
def generate_api_key(user=Depends(get_current_user), role: str = Depends(require_admin)):
    conn = get_db_connection()
    try:
        # Get Hospital ID
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hospital_pk = row['hospital_id'] if row and row['hospital_id'] else None
        
        if not hospital_pk:
             raise HTTPException(status_code=400, detail="User not linked to a hospital")
             
        # Generate Secure Key
        import secrets
        new_secret = f"HOSP_{hospital_pk}_" + secrets.token_urlsafe(16)
        
        # Deactivate old keys
        conn.execute("UPDATE api_keys SET is_active = 0 WHERE hospital_id = ?", (hospital_pk,))
        
        # Insert new key
        conn.execute("INSERT INTO api_keys (hospital_id, api_secret) VALUES (?, ?)", (hospital_pk, new_secret))
        conn.commit()
        
        return {"api_secret": new_secret}
    finally:
        conn.close()

# --- Phase 8: Advanced Hospital Management ---

class CapacityUpdate(BaseModel):
    total_beds: int
    occupied_beds: int

@app.get("/api/hospital/capacity")
def get_capacity(role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else 'H000'
        
        stats = conn.execute("SELECT total_beds, occupied_beds FROM dim_hospital WHERE hospital_id = ?", (hid,)).fetchone()
        return dict(stats) if stats else {"total_beds": 100, "occupied_beds": 0}
    finally:
        conn.close()

@app.post("/api/hospital/capacity")
def update_capacity(data: CapacityUpdate, role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else 'H000'
        
        conn.execute("UPDATE dim_hospital SET total_beds = ?, occupied_beds = ? WHERE hospital_id = ?", 
                    (data.total_beds, data.occupied_beds, hid))
        conn.commit()
        return {"status": "updated"}
    finally:
        conn.close()



@app.get("/api/hospital/analytics")
def get_analytics(role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hospital_pk = row['hospital_id'] if row and row['hospital_id'] else None
        
        if hospital_pk:
             # Resolve to Text ID (H000...)
            cur = conn.execute("SELECT hospital_id FROM dim_hospital WHERE hospital_key = ?", (hospital_pk,))
            h_row = cur.fetchone()
            hid = h_row['hospital_id'] if h_row else 'H000'
        else:
            hid = 'H000'
        
        # 7-Day Trend
        query = """
        SELECT admission_date, COUNT(*) as count, SUM(is_flu_positive) as flu_positive
        FROM patients 
        WHERE hospital_id = ? 
        GROUP BY admission_date 
        ORDER BY admission_date DESC LIMIT 7
        """
        trend = [dict(row) for row in conn.execute(query, (hid,)).fetchall()]
        
        return trend[::-1] # Return chronological order
    finally:
        conn.close()

@app.post("/api/hospital/upload")
async def upload_patients(file: UploadFile = File(...), role: str = Depends(require_admin), user=Depends(get_current_user)):
    # Simple CSV parser: Date, IsFlu (0/1 or True/False)
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else 'H000'
        
        content = await file.read()
        text = content.decode('utf-8')
        lines = text.split('\n')
        
        count = 0
        for line in lines[1:]: # Skip header
            parts = line.strip().split(',')
            if len(parts) >= 2:
                date = parts[0].strip()
                is_flu = parts[1].strip().lower() in ['true', '1', 'yes']
                conn.execute(
                    "INSERT INTO patients (hospital_id, admission_date, is_flu_positive) VALUES (?, ?, ?)",
                    (hid, date, is_flu)
                )
                count += 1
        conn.commit()
        return {"status": "success", "imported": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")
    finally:
        conn.close()

@app.get("/api/hospital/export")
def export_patients(role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else 'H000'
        
        rows = conn.execute("SELECT admission_date, is_flu_positive FROM patients WHERE hospital_id = ?", (hid,)).fetchall()
        
        # Generate CSV string
        output = "Date,Flu_Positive\n"
        for r in rows:
            output += f"{r['admission_date']},{r['is_flu_positive']}\n"
            
        return Response(content=output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=patients.csv"})
    finally:
        conn.close()

@app.get("/api/hospital/predict")
def get_prediction(days: int = 7, role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else 'H000'
        
        # 1. Get All Data for Mining Engine
        # We need ALL hospitals data to normalize properly (or just this one? Engine expects all usually)
        # But for simple single-series prediction, we might just need this hospital's data.
        # However, OutbreakMiner architecture takes full DF. Let's stick to that for consistency.
        
        query = """
        SELECT 
            hospital_id as hospital_key, 
            admission_date as date_key, 
            SUM(CASE WHEN is_flu_positive THEN 1 ELSE 0 END) as flu_positive_count
        FROM patients
        GROUP BY hospital_id, admission_date
        """
        visits_df = pd.read_sql(query, conn)
        
        if visits_df.empty:
            return []

        visits_df['date_key'] = pd.to_datetime(visits_df['date_key'])
        hospitals_df = pd.read_sql("SELECT * FROM dim_hospital", conn)
        
        miner = OutbreakMiner(hospitals_df, visits_df)
        prediction = miner.predict_hospital_visits(hid, horizon=days)
        
        return prediction
    except Exception as e:
        print(f"Prediction API Error: {e}")
        with open("error_log.txt", "w") as f:
            import traceback
            traceback.print_exc(file=f)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/simulation/run")
def run_simulation(metric: str = 'spatial', threshold: float = 0.05, role: str = Depends(require_admin)):
    """
    Run Mining Pipeline using LIVE PATIENT DATA.
    """
    conn = get_db_connection()
    try:
        # 1. Aggregate Patient Data -> Visit Counts
        # We need to transform 'patients' table into the format expected by OutbreakMiner (fact_daily_visits like)
        # Expected: hospital_key, date_key, flu_positive_count
        
        # Check if we have data
        count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        if count == 0:
            # Fallback to static data if no live data yet (for demo continuity)
            print("No live data, using static warehouse...")
            visits_df = pd.read_sql("SELECT hospital_key, date_key, flu_positive_count FROM fact_daily_visits", conn)
        else:
            print("Using Live Patient Data...")
            # Aggregate Live Data
            # Note: Mining Engine expects 'hospital_key' which matches 'hospital_id' in our schema roughly
            # Group by Hospital and Date
            query = """
            SELECT 
                hospital_id as hospital_key, 
                admission_date as date_key, 
                SUM(CASE WHEN is_flu_positive THEN 1 ELSE 0 END) as flu_positive_count
            FROM patients
            GROUP BY hospital_id, admission_date
            """
            visits_df = pd.read_sql(query, conn)
            # Ensure date_key is datetime
            visits_df['date_key'] = pd.to_datetime(visits_df['date_key'])

        hospitals_df = pd.read_sql("SELECT * FROM dim_hospital", conn)
        
        miner = OutbreakMiner(hospitals_df, visits_df)
        dist_matrix = miner.compute_distance_matrix(metric=metric)
        clusters = miner.perform_clustering(dist_matrix, threshold=threshold)
        cluster_series = miner.calculate_cluster_series(clusters)
        edges = miner.predict_spread(cluster_series)
        
        cluster_response = []
        for cid, h_keys in clusters.items():
            members = hospitals_df[hospitals_df['hospital_key'].isin(h_keys)][['hospital_id', 'name', 'latitude', 'longitude']].to_dict('records')
            cluster_response.append({
                "cluster_id": cid,
                "members": members
            })
            
        return {
            "metric": metric,
            "clusters": cluster_response,
            "network": edges
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# Static Files Mount moved to end



# --- Caching Defaults ---
# Simple in-memory cache for mining results. 
# Key: 'mining_result', Value: { 'data': ..., 'timestamp': ... }
MINING_CACHE = {
    'last_run': 0,
    'data': None,
    'ttl': 300 # 5 minutes
}

@app.get("/api/hospital/alerts")
def get_alerts(role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        # 1. Get Admin's Hospital ID
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else None
        
        if not hid:
            return {"alert": False, "message": "No hospital assigned."}

        # 2. Check Cache
        import time
        current_time = time.time()
        
        # If cache is fresh, use it to find MY cluster
        if MINING_CACHE['data'] and (current_time - MINING_CACHE['last_run'] < MINING_CACHE['ttl']):
            # print("Using Cached Mining Results")
            clusters = MINING_CACHE['data']
        else:
            # print("Running Fresh Mining...")
            # 3. Get Data for Mining (Same as dashboard)
            query = """
            SELECT 
                hospital_id as hospital_key, 
                admission_date as date_key, 
                SUM(CASE WHEN is_flu_positive THEN 1 ELSE 0 END) as flu_positive_count
            FROM patients
            GROUP BY hospital_id, admission_date
            """
            visits_df = pd.read_sql(query, conn)
            
            if visits_df.empty:
                return {"alert": False}

            visits_df['date_key'] = pd.to_datetime(visits_df['date_key'])
            hospitals_df = pd.read_sql("SELECT * FROM dim_hospital", conn)
            # Ensure we use hospital_id as key
            hospitals_df = hospitals_df.rename(columns={'hospital_id': 'hospital_key'}) 

            # 4. Run Miner
            miner = OutbreakMiner(hospitals_df, visits_df)
            dist_matrix = miner.compute_distance_matrix(metric='spatial') # Using spatial for consistency
            clusters = miner.perform_clustering(dist_matrix, threshold=0.05)
            
            # Update Cache
            MINING_CACHE['data'] = clusters
            MINING_CACHE['last_run'] = current_time

        # 5. Find My Cluster
        my_cluster_id = None
        for cid, members in clusters.items():
            if hid in members:
                my_cluster_id = cid
                break
        
        if my_cluster_id is None:
             return {"alert": False, "message": "Not in any cluster"}

        # 6. Check Risk Level (Optimization: We need connection for this part if not cached, 
        # but 'clusters' only gives IDs. We need case counts.
        # Ideally we should cache the risk assessment too, but for now caching the heavy clustering is enough.)
        
        # Quick check of recent cases for THIS cluster
        # This is fast enough to do on the fly usually.
        
        # To avoid re-querying DF, let's just do a specific SQL for the cluster members
        members = clusters[my_cluster_id]
        if not members: return {"alert": False}
        
        placeholders = ','.join(['?'] * len(members))
        query = f"""
            SELECT COUNT(*) 
            FROM patients 
            WHERE hospital_id IN ({placeholders})
            AND is_flu_positive = 1
            AND admission_date >= date('now', '-7 days')
        """
        recent_cases = conn.execute(query, tuple(members)).fetchone()[0]

        if recent_cases > 5:
            return {
                "alert": True, 
                "cluster_id": int(my_cluster_id),
                "risk_level": "High",
                "message": f"High Risk: Your facility is in Active Cluster {my_cluster_id} ({recent_cases} recent cases in area)."
            }
        
        return {"alert": False, "message": "Monitoring - Low Risk"}

    except Exception as e:
        print(f"Alert Error: {e}")
        return {"alert": False, "error": str(e)}
    finally:
        conn.close()

# ... (omitted)

from functools import lru_cache

@lru_cache(maxsize=100)
def cached_search_request(q):
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'http://localhost:3000/'
    }
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': q,
        'format': 'json',
        'addressdetails': 1,
        'limit': 5
    }
    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()

@app.get("/api/hospital/search")
def search_nominatim(q: str):
    try:
        return cached_search_request(q)
    except Exception as e:
        print(f"Nominatim Error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

# --- Static Files (Must be last) ---
# --- Static Files (Must be last) ---
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
else:
    print(f"WARNING: Static directory '{STATIC_DIR}' not found. Frontend serving disabled (Development Mode).")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


