# Disease Outbreak Detection System

A comprehensive system for detecting and visualizing disease outbreaks using real-time hospital data and mock ERP simulations.

## 🚀 Quick Start (First Time Setup)

If you are setting this up on a new machine, follow these steps in order.

### 1. Prerequisites
- **Python 3.8+**: [Download Here](https://www.python.org/downloads/)
- **Node.js 16+ & npm**: [Download Here](https://nodejs.org/)
- **Git**: [Download Here](https://git-scm.com/downloads)

### 2. Backend Setup
Open a terminal in the project folder and run:

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate it:
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup
Open a **new terminal** (or use the same one), go to the `frontend` folder:

```bash
cd frontend
npm install
```

### 4. Initialize Database
Back in the project root (make sure your virtual environment is active):

```bash
# Verify you are in the root directory (where populate_demo_data.py is)
python populate_demo_data.py
```
*This creates `backend/database/warehouse.db` with sample data.*

---

## 🎮 Running the Application

We provide a single script to launch everything (Backend, Frontend, and ERP Simulator).

1. **Ensure your virtual environment is active** (`.\venv\Scripts\activate`).
2. Run the demo script from the project root:

```bash
python run_demo.py
```

This will automatically start:
- **Public Dashboard**: [http://localhost:3000](http://localhost:3000)
- **Hospital Admin Portal**: [http://localhost:3000/hospital](http://localhost:3000/hospital)
- **ERP Simulator (Mock Data)**: [http://localhost:8001](http://localhost:8001)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

**To Stop:** Press `Ctrl+C` in the terminal to shut down all services.

---

## 🔧 Manual Startup (Alternative)

If the script doesn't work or you prefer manual control, use 3 separate terminals:

**Terminal 1: Backend**
```bash
.\venv\Scripts\activate
cd backend
uvicorn main:app --port 8000 --reload
```

**Terminal 2: ERP Simulator**
```bash
.\venv\Scripts\activate
# Run from project root
uvicorn mock_erp_gui.main:app --port 8001 --reload
```

**Terminal 3: Frontend**
```bash
cd frontend
npm run dev
```

## 🛠 Troubleshooting

- **"Module not found" errors**: Ensure you activated the virtual environment (`.\venv\Scripts\activate`) before running python commands.
- **Port Conflicts**: Ensure ports `3000`, `8000`, and `8001` are free.
- **Database Errors**: Rerun `python populate_demo_data.py` to reset the database.
