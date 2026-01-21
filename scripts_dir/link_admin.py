import sqlite3

db_path = "backend/database/warehouse.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

try:
    print("Checking Admin User...")
    admin = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
    if admin:
        print(f"Admin found. Hospital ID: {admin['hospital_id']}")
        
        # Check logic: mock_erp sends to api_keys where hospital_id is 1, 2, or 3.
        # So Admin should be linked to 1.
        if admin['hospital_id'] != 1:
            print("Updating Admin to Hospital ID 1...")
            conn.execute("UPDATE users SET hospital_id = 1 WHERE username='admin'")
            conn.commit()
            print("Admin linked to Hospital 1 (H000/General Hospital 0).")
    else:
        print("Admin user NOT found!")

    # Verify Hospital 1 exists
    h1 = conn.execute("SELECT * FROM dim_hospital WHERE hospital_key=1").fetchone()
    if h1:
        print(f"Hospital 1: {h1['name']} ({h1['hospital_id']})")

except Exception as e:
    print(e)
finally:
    conn.close()
