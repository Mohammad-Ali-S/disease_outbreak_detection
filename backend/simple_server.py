from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import requests


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ReportRequest(BaseModel):
    latitude: float
    longitude: float
    symptoms: str

@app.post("/api/public/report")
def submit_report(report: ReportRequest):
    return {"status": "success", "trust_score": 0.5}


@app.get("/api/hospital/search")
def search_hospitals(q: str):
    headers = {
        "User-Agent": "DiseaseOutbreakDetection/1.0 (contact@example.com)",
        "Referer": "http://localhost:3000"
    }
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=5"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error proxing to Nominatim: {e}")
        return []

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8001)
