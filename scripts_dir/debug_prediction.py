import sqlite3
import pandas as pd
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath('backend'))

from main import get_db_connection
from mining.mining_engine import OutbreakMiner

def test_prediction():
    conn = get_db_connection()
    try:
        print("Querying data...")
        query = """
        SELECT 
            hospital_id as hospital_key, 
            admission_date as date_key, 
            SUM(CASE WHEN is_flu_positive THEN 1 ELSE 0 END) as flu_positive_count
        FROM patients
        GROUP BY hospital_id, admission_date
        """
        visits_df = pd.read_sql(query, conn)
        print(f"Visits DF: {len(visits_df)} rows")
        
        if visits_df.empty:
            print("Visits DF empty.")
            return

        visits_df['date_key'] = pd.to_datetime(visits_df['date_key'])
        
        hospitals_df = pd.read_sql("SELECT * FROM dim_hospital", conn)
        print(f"Hospitals DF: {len(hospitals_df)} rows")
        
        print("Initializing Miner...")
        miner = OutbreakMiner(hospitals_df, visits_df)
        
        # Test with a likely ID. In generated data, IDs are H000..H029
        hid = 'H000'
        print(f"Predicting for {hid}...")
        
        prediction = miner.predict_hospital_visits(hid, horizon=7)
        print("Prediction Result:", prediction)
        
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    test_prediction()
