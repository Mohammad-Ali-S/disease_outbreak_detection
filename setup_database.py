import sqlite3
import os
import sys

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
DB_PATH = os.path.join(BACKEND_DIR, 'database', 'warehouse.db')
SCHEMA_PATH = os.path.join(BACKEND_DIR, 'database', 'schema.sql')

def init_db():
    print(f"Initializing database at: {DB_PATH}")
    
    # Ensure database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    try:
        if not os.path.exists(SCHEMA_PATH):
            print(f"Error: Schema file not found at {SCHEMA_PATH}")
            return

        with open(SCHEMA_PATH, 'r') as f:
            schema_sql = f.read()

        conn = sqlite3.connect(DB_PATH)
        conn.executescript(schema_sql)
        conn.commit()
        conn.close()
        print("Database schema applied successfully.")
        
        # Verify tables
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables created: {', '.join(tables)}")
        
        # Check specifically for patients
        if 'patients' in tables:
            print("SUCCESS: 'patients' table exists.")
        else:
            print("ERROR: 'patients' table missing.")
            
        conn.close()

    except Exception as e:
        print(f"Initialization Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
