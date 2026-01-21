import sqlite3
import os

db_path = "backend/database/warehouse.db"
if not os.path.exists(db_path):
    print(f"File not found: {db_path}")
else:
    print(f"File exists: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables found:", [t[0] for t in tables])
        
        if ('api_keys',) in tables:
            print("api_keys table exists.")
            cursor.execute("SELECT * FROM api_keys")
            rows = cursor.fetchall()
            print(f"Rows in api_keys: {len(rows)}")
            for r in rows:
                print(r)
        else:
            print("api_keys table MISSING!")
            
    except Exception as e:
        print(e)
    finally:
        conn.close()
