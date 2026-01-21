import hashlib
import time

class IntegrityEngine:
    def __init__(self, db_conn):
        self.conn = db_conn

    def validate_report(self, data, ip_address):
        """
        Validates a community report and assigns a Trust Score.
        Returns (is_valid, trust_score, rejection_reason)
        """
        # 1. IP Hashing (Anonymity)
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()
        
        # 2. Velocity Check (Spam Protection)
        # Check how many reports from this IP hash in last hour
        cursor = self.conn.cursor()
        count = cursor.execute("""
            SELECT COUNT(*) FROM community_reports 
            WHERE ip_hash = ? AND created_at >= datetime('now', '-1 hour')
        """, (ip_hash,)).fetchone()[0]

        if count > 5:
            return False, 0.0, "Rate Limit Exceeded (Too many reports from this feedback source)"
        
        if count > 2:
            # Suspicious but maybe valid (family reporting?) -> Lower trust
            return True, 0.1, None

        # 3. Geo-Fencing (Basic sanity check - is it within our map bounds?)
        # Let's assume valid bounds approx Ontario
        if not (41.0 <= data['latitude'] <= 57.0 and -96.0 <= data['longitude'] <= -74.0):
             # Out of bounds - auto-reject or mark as extremely low trust (0.01)
             return True, 0.01, "Location Out of Expected Region"

        # Baseline Trust for Anonymous
        return True, 0.5, None

    def log_action(self, username, user_id, action, details, ip_address='unknown'):
        """
        Logs critical actions for audit.
        """
        self.conn.execute("""
            INSERT INTO audit_logs (username, user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?, ?)
        """, (username, user_id, action, details, ip_address))
        self.conn.commit()

    def check_insider_threats(self, hospital_id):
        """
        Checks for unrealistic data entry patterns at a hospital.
        """
        # Example: >500 admissions in 1 hour
        # This would be a batch job or triggered on insert
        pass
