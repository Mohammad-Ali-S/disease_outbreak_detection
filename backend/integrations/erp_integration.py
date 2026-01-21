import hashlib
import sqlite3
from datetime import datetime

class ERPIntegration:
    def __init__(self, db_path="warehouse.db"):
        self.db_path = db_path

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def validate_api_key(self, api_key: str):
        """
        Checks if the API key exists and is active.
        Returns hospital_id if valid, None otherwise.
        """
        conn = self.get_db_connection()
        try:
            row = conn.execute("SELECT hospital_id FROM api_keys WHERE api_secret = ? AND is_active = 1", (api_key,)).fetchone()
            if row:
                return row['hospital_id']
            return None
        finally:
            conn.close()

    def process_admission_event(self, hospital_pk: int, payload: dict):
        """
        Ingests a JSON payload representing a patient event.
        hospital_pk: The integer primary key of the hospital.
        """
        conn = self.get_db_connection()
        try:
            with open("d:/Disease_Outbreak_Detection/debug_error_ABS.log", "a") as f:
                f.write(f"processing event for {hospital_pk}\n")

            # 0. Resolve Hospital Identity (Handle if PK is int or "H001" string)
            # We need:
            # - real_hospital_pk (int) for fact_daily_visits
            # - hospital_text_id (str) for patients table
            
            real_hospital_pk = None
            hospital_text_id = None
            
            # Try finding by Integer Key
            row_by_key = conn.execute("SELECT hospital_key, hospital_id FROM dim_hospital WHERE hospital_key = ?", (hospital_pk,)).fetchone()
            if row_by_key:
                real_hospital_pk = row_by_key['hospital_key']
                hospital_text_id = row_by_key['hospital_id']
            else:
                # Try finding by String ID
                row_by_id = conn.execute("SELECT hospital_key, hospital_id FROM dim_hospital WHERE hospital_id = ?", (hospital_pk,)).fetchone()
                if row_by_id:
                     real_hospital_pk = row_by_id['hospital_key']
                     hospital_text_id = row_by_id['hospital_id']
            
            if not real_hospital_pk or not hospital_text_id:
                msg = f"Ingestion Error: Could not resolve hospital for key '{hospital_pk}'. real_pk={real_hospital_pk}, text_id={hospital_text_id}"
                print(msg)
                with open("debug_error.log", "w") as f:
                    f.write(msg)
                return False

            # 1. Insert into Patients table
            is_flu = 1 if payload.get('diagnosis') == 'FLU_POS' else 0
            adm_date_str = payload.get('admission_date', datetime.now().strftime('%Y-%m-%d'))
            
            conn.execute("""
                INSERT INTO patients (hospital_id, admission_date, age, gender, is_flu_positive, symptoms)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                hospital_text_id,
                adm_date_str,
                payload.get('age'),
                payload.get('gender', 'U'),
                is_flu,
                payload.get('symptoms', '')
            ))

            # 2. Update Daily Visits Fact Table
            # Convert date to key YYYYMMDD
            try:
                dt = datetime.strptime(adm_date_str, '%Y-%m-%d')
                date_key = int(dt.strftime('%Y%m%d'))
            except:
                date_key = int(datetime.now().strftime('%Y%m%d'))

            # Check if row exists
            existing = conn.execute("""
                SELECT visit_id, total_visits, flu_positive_count 
                FROM fact_daily_visits 
                WHERE hospital_key = ? AND date_key = ?
            """, (real_hospital_pk, date_key)).fetchone()
            
            if existing:
                new_total = existing['total_visits'] + 1
                new_flu = existing['flu_positive_count'] + is_flu
                conn.execute("UPDATE fact_daily_visits SET total_visits = ?, flu_positive_count = ? WHERE visit_id = ?", 
                             (new_total, new_flu, existing['visit_id']))
            else:
                conn.execute("""
                    INSERT INTO fact_daily_visits (hospital_key, date_key, total_visits, flu_positive_count, beds_in_use)
                    VALUES (?, ?, 1, ?, 50) 
                """, (real_hospital_pk, date_key, is_flu))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Ingestion Error: {e}")
            with open("debug_error.log", "w") as f:
                import traceback
                traceback.print_exc(file=f)
            return False
        finally:
            conn.close()
