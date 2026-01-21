import sqlite3
import pandas as pd
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from mining.mining_engine import OutbreakMiner

def debug():
    conn = sqlite3.connect("backend/database/warehouse.db")
    try:
        print("Querying Data...")
        query = """
        SELECT 
            hospital_id as hospital_key, 
            admission_date as date_key, 
            SUM(CASE WHEN is_flu_positive THEN 1 ELSE 0 END) as flu_positive_count
        FROM patients
        GROUP BY hospital_id, admission_date
        """
        visits_df = pd.read_sql(query, conn)
        print(f"Visits DF Shape: {visits_df.shape}")
        
        visits_df['date_key'] = pd.to_datetime(visits_df['date_key'])
        hospitals_df = pd.read_sql("SELECT * FROM dim_hospital", conn)
        print(f"Hospitals DF Shape: {hospitals_df.shape}")
        
        print("Initializing Miner...")
        miner = OutbreakMiner(hospitals_df, visits_df)
        
        print("Computing Distance (Spatial)...")
        dist_matrix = miner.compute_distance_matrix(metric='spatial')
        print(f"Distance Matrix:\n{dist_matrix}")
        
        print("Clustering...")
        clusters = miner.perform_clustering(dist_matrix, n_clusters=5)
        print(f"Clusters: {clusters}")
        
        print("Series Calcs...")
        cluster_series = miner.calculate_cluster_series(clusters)
        
        print("Predicting Spread...")
        edges = miner.predict_spread(cluster_series)
        print(f"Edges: {edges}")

    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    debug()
