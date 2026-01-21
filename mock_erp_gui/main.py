from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import httpx
import random
import time
import uuid
import asyncio

app = FastAPI()

# Mount static files (our UI)
app.mount("/static", StaticFiles(directory="mock_erp_gui/static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("mock_erp_gui/static/index.html")

# Simulation Logic
SYMPTOMS_LIST = ["Fever", "Cough", "Shortness of Breath", "Fatigue", "Headache", "Sore Throat", "Runny Nose"]

class AdmissionRequest(BaseModel):
    api_key: str
    target_url: str
    patient_name: str | None = None
    age: int | None = None
    symptoms: str | None = None
    diagnosis: str | None = None # FLU_POS, FLU_NEG

@app.post("/simulate/admit")
async def admit_patient(req: AdmissionRequest):
    # Construct the payload expected by the main platform
    is_flu = req.diagnosis == "FLU_POS"
    
    patient_data = {
        "event_type": "ADMISSION",
        "patient_id_hash": str(uuid.uuid4())[:8],
        "age": req.age or random.randint(5, 90),
        "gender": random.choice(["M", "F"]),
        "admission_date": time.strftime("%Y-%m-%d"),
        "symptoms": req.symptoms or ", ".join(random.sample(SYMPTOMS_LIST, k=random.randint(1, 3))),
        "diagnosis": req.diagnosis or ("FLU_POS" if random.random() < 0.3 else "FLU_NEG")
    }
    
    payload = {
        "api_key": req.api_key,
        "event_type": "ADMISSION",
        "data": patient_data
    }
    
    print(f"Sending to {req.target_url}: {payload}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(req.target_url, json=payload, timeout=5.0)
            if resp.status_code == 200:
                return {"status": "success", "data_sent": patient_data, "response": resp.json()}
            else:
                return {"status": "error", "code": resp.status_code, "detail": resp.text}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

# Auto-generation state (simplistic global state for demo)
is_running = False

@app.post("/simulate/toggle")
async def toggle_simulation(enable: bool = Body(...)):
    global is_running
    is_running = enable
    return {"status": "running" if is_running else "stopped"}

