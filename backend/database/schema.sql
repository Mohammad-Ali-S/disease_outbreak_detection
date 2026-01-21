-- Star Schema for Disease Outbreak Detection

-- Dimension: Hospitals
CREATE TABLE IF NOT EXISTS dim_hospital (
    hospital_key INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id TEXT UNIQUE NOT NULL, -- Original ID from source
    name TEXT,
    latitude REAL,
    longitude REAL,
    region TEXT,
    city TEXT,
    -- Capacity columns added in Phase 8
    total_beds INTEGER DEFAULT 100,
    icu_beds INTEGER DEFAULT 20,
    ventilators INTEGER DEFAULT 10,
    occupied_beds INTEGER DEFAULT 0
);

-- Dimension: Time (Pre-generated dates for faster querying)
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY, -- YYYYMMDD format
    full_date DATE UNIQUE NOT NULL,
    year INTEGER,
    month INTEGER,
    day_of_week INTEGER, -- 0=Monday, 6=Sunday
    is_weekend BOOLEAN,
    season TEXT -- 'Winter', 'Spring', 'Summer', 'Fall'
);

-- Fact: Daily Visits
CREATE TABLE IF NOT EXISTS fact_daily_visits (
    visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_key INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    
    total_visits INTEGER DEFAULT 0,
    flu_positive_count INTEGER DEFAULT 0,
    
    -- Syndromic Surveillance Indicators (from paper)
    resp_syndrome_count INTEGER DEFAULT 0, -- Respiratory
    ili_syndrome_count INTEGER DEFAULT 0, -- Influenza-like Illness

    -- Resource Usage (Daily Snapshot)
    beds_in_use INTEGER DEFAULT 0,
    icu_in_use INTEGER DEFAULT 0,
    vents_in_use INTEGER DEFAULT 0,
    
    FOREIGN KEY (hospital_key) REFERENCES dim_hospital(hospital_key),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);

-- Indexes for performance


-- Users Table for Authentication (Updated with hospital_id)
-- Note: In SQLite we can't easily ALTER to add FK, so we'll just add the column or rely on migration script logic.
-- For this file, we define the IDEAL schema.
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
    hospital_id INTEGER, -- Link Admin to a specific hospital (NULL for super-admin or public user)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(hospital_id) REFERENCES dim_hospital(hospital_id)
);

-- Live Patient Records (Transactional)
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id TEXT NOT NULL,
    admission_date DATE NOT NULL,
    age INTEGER,
    gender TEXT,
    symptoms TEXT,
    is_flu_positive BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(hospital_id) REFERENCES dim_hospital(hospital_id)
);

-- Active Alerts System
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id TEXT,
    severity TEXT CHECK(severity IN ('INFO', 'WARNING', 'CRITICAL')),
    message TEXT,
    is_read BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(hospital_id) REFERENCES dim_hospital(hospital_id)
);

-- Phase 3: Citizen Reporting & Data Integrity
CREATE TABLE IF NOT EXISTS community_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    symptoms TEXT,
    trust_score REAL DEFAULT 0.1, -- 0.0 to 1.0
    ip_hash TEXT, -- Anonymized IP for spam detection
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, -- Link to user if known, else NULL
    username TEXT, -- Captured at time of action
    action TEXT, -- e.g. "ADD_PATIENT", "UPDATE_CAPACITY"
    details TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id INTEGER,
    api_secret TEXT UNIQUE,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(hospital_id) REFERENCES dim_hospital(hospital_id)
);


