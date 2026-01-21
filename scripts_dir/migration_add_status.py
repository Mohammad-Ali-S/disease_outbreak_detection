import sqlite3

db_path = "backend/database/warehouse.db"
conn = sqlite3.connect(db_path)

try:
    print("Migrating schema...")
    # Check if column exists
    cursor = conn.execute("PRAGMA table_info(patients)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'status' not in columns:
        print("Adding 'status' column...")
        conn.execute("ALTER TABLE patients ADD COLUMN status TEXT DEFAULT 'Admitted'")
        print("Column added.")
    else:
        print("'status' column already exists.")

    # Update existing rows
    conn.execute("UPDATE patients SET status = 'Admitted' WHERE status IS NULL")
    conn.commit()
    print("Migration complete.")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
