import sqlite3
import pandas as pd
import os

DB_PATH = "backend/database/warehouse.db"

def inspect_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    
    print("--- Table Counts ---")
    tables = ["patients", "fact_daily_visits", "dim_hospital", "dim_date"]
    for t in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t}: {count}")
        except Exception as e:
            print(f"{t}: Error {e}")

    print("\n--- Recent Patients ---")
    try:
        df = pd.read_sql("SELECT * FROM patients ORDER BY admission_date DESC LIMIT 5", conn)
        print(df)
    except Exception as e:
        print(f"Error reading patients: {e}")

    print("\n--- Date Check ---")
    # Check what 'now' means to SQLite vs Python
    sqlite_now = conn.execute("SELECT date('now')").fetchone()[0]
    print(f"SQLite date('now'): {sqlite_now}")
    
    conn.close()

if __name__ == "__main__":
    inspect_db()
