"""Deterministic API workflow smoke test for the AegisCare hackathon demo."""
import os
import tempfile
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_tmp = tempfile.TemporaryDirectory(prefix="aegiscare_smoke_")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp.name) / "smoke.db")
os.environ["SECRET_KEY"] = "smoke-test-secret-key-change-for-real-deployments"

from fastapi.testclient import TestClient
import app.main as backend

async def fake_route(a, b, c, d):
    return {"distance_km": 2.4, "eta_minutes": 8, "source": "smoke-test stub"}

backend.route = fake_route

with TestClient(backend.app) as client:
    health = client.get("/api/health")
    assert health.status_code == 200 and health.json()["status"] == "ok"

    def login(email):
        response = client.post("/api/login", data={"email": email, "password": "AegisDemo!2026"})
        assert response.status_code == 200, (email, response.text)
        return response.json()

    login("citizen@aegiscare.demo")
    assert client.get("/api/dashboard").status_code == 200
    incident = client.post("/api/incidents", data={
        "latitude": "18.5204", "longitude": "73.8567",
        "description": "Road collision, one person injured"
    })
    assert incident.status_code == 200, incident.text
    payload = incident.json()
    assert payload["selected_hospital"] and payload["dispatch"]
    dispatch_id = payload["dispatch"]["id"]

    login("hospital@aegiscare.demo")
    assert client.get("/api/dashboard").status_code == 200

    login("ambulance@aegiscare.demo")
    accepted = client.post(f"/api/dispatches/{dispatch_id}/respond", data={"decision": "accept"})
    assert accepted.status_code == 200, accepted.text
    for status in ["En route", "Arrived", "Transporting", "Completed"]:
        response = client.patch(f"/api/dispatches/{dispatch_id}/status", data={"status": status})
        assert response.status_code == 200, (status, response.text)

    login("admin@aegiscare.demo")
    final = client.get("/api/dashboard").json()
    assert any(x["id"] == payload["id"] for x in final["incidents"])
    assert any(x["id"] == dispatch_id and x["status"] == "Completed" for x in final["dispatches"])

print("PASS: health, four role logins, shared dashboard, incident intake, hospital match, dispatch accept, and full dispatch lifecycle")
_tmp.cleanup()
