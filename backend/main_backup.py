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
print("STARTING APP AND LOADING ROUTES")

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
        clusters = miner.perform_clustering(dist_matrix, n_clusters=5)
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
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hospital_id = row['hospital_id'] if row and row['hospital_id'] else 'H000'

        recent = conn.execute(
            """
            SELECT p.patient_id, p.admission_date, p.is_flu_positive, COALESCE(h.name, 'Unknown Hospital') as hospital_name
            FROM patients p
            LEFT JOIN dim_hospital h ON p.hospital_id = h.hospital_id
            WHERE p.hospital_id = ?
            ORDER BY p.created_at DESC LIMIT 50
            """, (hospital_id,)
        ).fetchall()
        
        return [dict(row) for row in recent]
    finally:
        conn.close()

@app.delete("/api/patients/{patient_id}")
def delete_patient(patient_id: int, role: str = Depends(require_admin)):
    conn = get_db_connection()
    try:
        return { "status": "deleted" }
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

class HospitalProfile(BaseModel):
    name: str
    city: str = "Unknown"
    region: str = "Unknown"
    latitude: float
    longitude: float

@app.get("/api/hospital/profile")
def get_profile(role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else None
        
        if not hid:
             return {} # No ID assigned
             
        prof = conn.execute("SELECT * FROM dim_hospital WHERE hospital_id = ?", (hid,)).fetchone()
        if prof:
            return dict(prof)
        else:
            return {"hospital_id": hid, "name": f"Hospital {hid}", "city": "", "region": "", "latitude": 43.65, "longitude": -79.38}
    finally:
        conn.close()

@app.post("/api/hospital/profile")
def update_profile(profile: HospitalProfile, role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else None
        
        if not hid:
            raise HTTPException(status_code=400, detail="User has no Hospital ID assigned.")

        # Upsert
        exists = conn.execute("SELECT 1 FROM dim_hospital WHERE hospital_id = ?", (hid,)).fetchone()
        
        if exists:
            conn.execute("""
                UPDATE dim_hospital 
                SET name = ?, city = ?, region = ?, latitude = ?, longitude = ?
                WHERE hospital_id = ?
            """, (profile.name, profile.city, profile.region, profile.latitude, profile.longitude, hid))
        else:
            conn.execute("""
                INSERT INTO dim_hospital (hospital_id, name, city, region, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (hid, profile.name, profile.city, profile.region, profile.latitude, profile.longitude))
            
        conn.commit()
        return {"message": "Profile updated successfully"}
    finally:
        conn.close()

@app.get("/api/hospital/analytics")
def get_analytics(role: str = Depends(require_admin), user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT hospital_id FROM users WHERE username = ?", (user['sub'],))
        row = cur.fetchone()
        hid = row['hospital_id'] if row and row['hospital_id'] else 'H000'
        
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/simulation/run")
def run_simulation(metric: str = 'spatial', n_clusters: int = 5, role: str = Depends(require_admin)):
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
        clusters = miner.perform_clustering(dist_matrix, n_clusters=n_clusters)
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

# --- Static Files (Frontend) ---
# Mount the frontend 'out' directory
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# Catch-all for SPA routing (if file not found, serve index.html)
# Note: FastAPI StaticFiles 'html=True' handles index.html for root, 
# but for nested routes or failing lookups we might need 404 handler to return index.html
# For simple static export, it usually just works if we structure it right.


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

        # 2. Get Data for Mining (Same as dashboard)
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

        # 3. Run Miner
        miner = OutbreakMiner(hospitals_df, visits_df)
        dist_matrix = miner.compute_distance_matrix(metric='spatial') # Using spatial for consistency
        clusters = miner.perform_clustering(dist_matrix) # {cluster_id: [hids]}

        # 4. Find My Cluster
        my_cluster_id = None
        for cid, members in clusters.items():
            # Mining engine uses whatever type is in DB. SQLite might be string "H001", but miner maps to index?
            # Wait, miner uses hospital_key from DF.
            # let's check members content.
            if hid in members:
                my_cluster_id = cid
                break
        
        if my_cluster_id is None:
             return {"alert": False, "message": "Not in any cluster"}

        # 5. Check Risk Level
        # Calculate recent cases for this cluster
        members = clusters[my_cluster_id]
        recent_cases = visits_df[
            (visits_df['hospital_key'].isin(members)) & 
            (visits_df['date_key'] >= pd.Timestamp('now') - pd.Timedelta(days=7))
        ]['flu_positive_count'].sum()

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

# --- Phase 2: Smart Alerts API ---
from mining.alert_engine import AlertEngine

@app.get("/api/alerts/active")
def get_active_alerts():
    conn = get_db_connection()
    try:
        engine = AlertEngine(conn)
        alerts = engine.run_checks() # Run checks and get fresh alerts
        
        # Get all unread alerts from DB
        # For public view, we might want system-wide alerts.
        # For admin, specific hospital.
        # Let's return all CRITICAL/WARNING for public ticker
        
        rows = conn.execute("SELECT * FROM alerts WHERE created_at >= date('now', '-1 day') ORDER BY created_at DESC LIMIT 10").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

# --- Phase 3: Citizen Reporting & Integrity ---
from mining.integrity_engine import IntegrityEngine
from pydantic import BaseModel

class ReportRequest(BaseModel):
    latitude: float
    longitude: float
    symptoms: str # Comma separated
    
@app.get("/api/public/report")
def debug_get_report():
    return {"message": "GET works, but POST should too"}

print("REGISTERING REPORT ROUTE")
@app.post("/api/public/report")
def submit_report(report: ReportRequest, request: Request, background_tasks: BackgroundTasks):
    client_ip = request.client.host
    conn = get_db_connection()
    try:
        engine = IntegrityEngine(conn)
        
        # Validate
        is_valid, trust_score, reason = engine.validate_report(report.dict(), client_ip)
        
        if not is_valid:
            print(f"Rejected Report: {reason}")
            raise HTTPException(status_code=429, detail=reason)
            
        # Insert
        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()
        conn.execute("""
            INSERT INTO community_reports (latitude, longitude, symptoms, trust_score, ip_hash)
            VALUES (?, ?, ?, ?, ?)
        """, (report.latitude, report.longitude, report.symptoms, trust_score, ip_hash))
        conn.commit()
        
        return {"status": "success", "trust_score": trust_score}
    except Exception as e:
        print(f"Report Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        conn.close()

@app.get("/api/public/reports")
def get_community_reports():
    conn = get_db_connection()
    try:
        # Only return reports from last 48 hours to keep map clean
        reports = conn.execute("""
            SELECT latitude, longitude, symptoms, trust_score 
            FROM community_reports 
            WHERE created_at >= date('now', '-2 days')
            AND trust_score > 0
        """).fetchall()
        return [dict(row) for row in reports]
    finally:
        conn.close()

# --- Phase 4: Predictive Simulator ---
from mining.simulation_engine import SimulationEngine

class SimulationRequest(BaseModel):
    mask_compliance: float = 0.0 # 0.0 to 1.0
    lockdown_level: float = 0.0 # 0.0 to 1.0
    
@app.post("/api/simulation/predict")
def run_simulation_projection(params: SimulationRequest):
    conn = get_db_connection()
    try:
        # Get Current State
        # Total Patients, but really we want active infected.
        # Let's approximate from patients table (last 14 days)
        active_infected = conn.execute("SELECT COUNT(*) FROM patients WHERE is_flu_positive = 1 AND admission_date >= date('now', '-14 days')").fetchone()[0]
        active_infected = max(1, active_infected) # Avoid 0 for math stability
        
        # Assume total population of our region (e.g., covered area)
        # 30 hospitals * ~50k catchment = 1.5M
        population = 1500000 
        
        # Estimate Recovered
        total_cases = conn.execute("SELECT COUNT(*) FROM patients WHERE is_flu_positive = 1").fetchone()[0]
        recovered = max(0, total_cases - active_infected)
        
        engine = SimulationEngine(active_infected, recovered, population)
        
        # Calculate aggregate intervention factor
        # Mask = 0.4 max impact, Lockdown = 0.6 max impact
        # Naive linear combination
        impact = (params.mask_compliance * 0.4) + (params.lockdown_level * 0.6)
        
        # 1. Baseline (Do Nothing)
        baseline = engine.run_sir_projection(days=30, intervention_factor=0.0)
        
        # 2. Intervention
        projected = engine.run_sir_projection(days=30, intervention_factor=impact)
        
        return {
            "baseline": baseline,
            "projected": projected,
            "impact_score": round(impact * 100, 1) # % transmission reduction
        }
    finally:
        conn.close()

# --- Phase 5: ERP Integration ---
from integrations.erp_integration import ERPIntegration

class IntegrationPayload(BaseModel):
    api_key: str
    event_type: str
    data: dict

@app.post("/api/v1/connect/admission")
def ingest_erp_event(payload: IntegrationPayload):
    integrator = ERPIntegration()
    hospital_id = integrator.validate_api_key(payload.api_key)
    
    if not hospital_id:
        return {"status": "error", "message": "Invalid API Key"}, 401
        
    success = integrator.process_admission_event(hospital_id, payload.data)
    
    if success:
        return {"status": "success", "message": "Event Ingested"}
    else:
        return {"status": "error", "message": "Processing Failed"}, 500

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
