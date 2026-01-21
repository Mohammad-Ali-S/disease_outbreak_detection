# Disease Outbreak Detection System

## Prerequisites

Before running the project, ensure you have the following installed:

-   **Python 3.8+**: [Download Python](https://www.python.org/downloads/)
-   **Node.js 16+ & npm**: [Download Node.js](https://nodejs.org/)

## Installation

### 1. Backend Setup

Open a terminal in the project root directory:

```bash
# Optional: Create a virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Frontend Setup

Open a new terminal (or the same one) and navigate to the `frontend` directory:

```bash
cd frontend
npm install
```

## Database Setup

Before running the app for the first time, populate the database with demo data:

```bash
# From the project root directory
python populate_demo_data.py
```

This will create/update `backend/database/warehouse.db` with synthetic hospital entry data.

## Running the Application

### Option A: The "All-in-One" Script (Recommended)

We have provided a script that launches the Backend, Frontend, and ERP Simulator simultaneously.

From the project root:

```bash
python run_demo.py
```

This script will start:
-   **Main App (Frontend)**: `http://localhost:3000`
-   **Backend API**: `http://localhost:8000`
-   **ERP Simulator**: `http://localhost:8001`

**To Stop:** Press `Ctrl+C` in the terminal where the script is running. It will automatically terminate all processes.

### Option B: Manual Startup

If you prefer to run services individually, open **three separate terminals**:

**Terminal 1: Backend**
```bash
cd backend
uvicorn main:app --port 8000 --reload
```

**Terminal 2: ERP Simulator**
```bash
# From project root
uvicorn mock_erp_gui.main:app --port 8001 --reload
```

**Terminal 3: Frontend**
```bash
cd frontend
npm run dev
```

## Troubleshooting

-   **Port Conflicts**: If the script fails, ensure ports `3000`, `8000`, and `8001` are not being used by other applications. The `run_demo.py` script tries to auto-kill processes on these ports, but you may need to manually close them.
-   **Database Errors**: If you see errors about missing tables, run `python populate_demo_data.py` again.
