import sqlite3
import sys
import os

# Add backend to path to import auth
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from auth import get_password_hash

DB_PATH = "backend/database/warehouse.db"

def reset_password():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    username = "admin"
    password = "admin"
    hashed_pw = get_password_hash(password)
    
    # Check if user exists
    user = cursor.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    
    if user:
        cursor.execute("UPDATE users SET password_hash=? WHERE username=?", (hashed_pw, username))
        print(f"Updated password for '{username}' to '{password}'")
    else:
        # Create user if not exists
        print(f"User '{username}' not found. Creating...")
        # Assuming hospital_id 1 exists from link_admin.py logic, or use NULL/default
        cursor.execute("INSERT INTO users (username, password_hash, role, hospital_id) VALUES (?, ?, ?, ?)",
                       (username, hashed_pw, 'admin', 1))
        print(f"Created user '{username}' with password '{password}'")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    reset_password()
