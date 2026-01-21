import pandas as pd
import numpy as np

class AlertEngine:
    def __init__(self, db_conn):
        self.conn = db_conn

    def run_checks(self):
        """
        Main entry point. Runs all checks and persists new alerts.
        Returns active alerts.
        """
        alerts = []
        alerts.extend(self.check_capacity_stress())
        alerts.extend(self.check_outbreak_velocity())
        
        self.persist_alerts(alerts)
        return alerts

    def check_capacity_stress(self):
        """
        Check for hospitals exceeding safe resource limits.
        """
        generated_alerts = []
        
        query = """
            SELECT 
                h.hospital_id, h.name, 
                h.icu_beds, h.total_beds,
                h.occupied_beds, 
                -- We use the columns added in Phase 8 for live capacity if updated via API,
                -- but we also need to consider the 'in_use' columns if we were using the fact table for simulation.
                -- For the 'Real World' app, let's rely on the dim_hospital live values updated by Admin 
                -- OR the estimated usage from patient counts if manual data isn't fresh.
                (SELECT COUNT(*) FROM patients p WHERE p.hospital_id = h.hospital_id AND p.is_flu_positive=1 AND p.admission_date >= date('now', '-7 days')) as recent_flu
            FROM dim_hospital h
        """
        df = pd.read_sql(query, self.conn)
        
        for _, row in df.iterrows():
            # Estimate ICU usage if live data missing (same logic as dashboard)
            # But let's assume the 'occupied_beds' column is the source of truth for General beds
            # For ICU, we lack a direct column in dim_hospital unless we added it?
            # We added 'icu_beds' (total) but not 'icu_occupied' specifically in the schema update earlier?
            # Wait, I added total_beds, icu_beds, ventilators. I did NOT add 'icu_occupied'.
            # I added 'occupied_beds' (general).
            # So for ICU stress, we must estimate based on flu cases OR add that column.
            # Let's estimate for now to keep it simple: 
            # ICU Load = 10% of total occupied + 15% of recent flu cases?
            # Or just use the General Occupancy for now.
            
            # 1. General Capacity Check
            if row['total_beds'] > 0:
                occ_rate = row['occupied_beds'] / row['total_beds']
                if occ_rate > 0.90:
                    generated_alerts.append({
                        "hospital_id": row['hospital_id'],
                        "severity": "CRITICAL",
                        "message": f"Critical Overcrowding: {row['name']} at {int(occ_rate*100)}% capacity."
                    })
                elif occ_rate > 0.80:
                    generated_alerts.append({
                        "hospital_id": row['hospital_id'],
                        "severity": "WARNING",
                        "message": f"High Occupancy: {row['name']} at {int(occ_rate*100)}% capacity."
                    })
            
            # 2. Flu Spike Check (Proxy for ICU stress)
            # If recent flu cases > 20% of total beds -> Critical Risk
            if row['total_beds'] > 0:
                flu_load = row['recent_flu'] / row['total_beds']
                if flu_load > 0.20:
                     generated_alerts.append({
                        "hospital_id": row['hospital_id'],
                        "severity": "CRITICAL",
                        "message": f"surge Detected: Flu patients occupy >20% of capacity at {row['name']}."
                    })

        return generated_alerts

    def check_outbreak_velocity(self):
        """
        Check if infection rate is doubling rapidly across the system.
        """
        alerts = []
        
        # Get daily counts for last 7 days
        query = """
            SELECT admission_date, COUNT(*) as cnt 
            FROM patients 
            WHERE is_flu_positive = 1 
            AND admission_date >= date('now', '-7 days')
            GROUP BY admission_date
            ORDER BY admission_date
        """
        df = pd.read_sql(query, self.conn)
        
        if len(df) < 3: return []
        
        # Simple slope check
        # If today's count > 2 * count 3 days ago
        latest = df.iloc[-1]['cnt']
        past = df.iloc[0]['cnt'] # approx 7 days ago
        
        if latest > past * 2 and latest > 10:
             alerts.append({
                "hospital_id": None, # System-wide
                "severity": "WARNING",
                "message": f"Rapid Spread Alert: Total daily cases doubled in last 7 days ({past} -> {latest})."
            })
            
        return alerts

    def persist_alerts(self, new_alerts):
        """
        Save to DB if not duplicate (simple de-dupe logic: same hospital, same message, same day).
        """
        cursor = self.conn.cursor()
        for alert in new_alerts:
            # Check exist
            exists = cursor.execute("""
                SELECT 1 FROM alerts 
                WHERE (hospital_id = ? OR (hospital_id IS NULL AND ? IS NULL))
                AND message = ? 
                AND date(created_at) = date('now')
            """, (alert['hospital_id'], alert['hospital_id'], alert['message'])).fetchone()
            
            if not exists:
                cursor.execute("""
                    INSERT INTO alerts (hospital_id, severity, message)
                    VALUES (?, ?, ?)
                """, (alert['hospital_id'], alert['severity'], alert['message']))
        
        self.conn.commit()
