"""Integration checks for sequential facility/ambulance escalation."""
import os,sys,tempfile
from pathlib import Path
TMP=tempfile.TemporaryDirectory(prefix="aegiscare_sequence_")
os.environ["DATABASE_URL"]="sqlite:///"+str(Path(TMP.name)/"sequence.db")
os.environ["SECRET_KEY"]="sequential-test-secret-key-at-least-32-bytes"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import app.main as backend
async def fake_route(a,b,c,d):
    distance=backend.km(a,b,c,d)*1.15
    return {"distance_km":distance,"eta_minutes":max(1,round(distance*2)),"source":"deterministic test route"}
backend.route=fake_route
assert backend.analyze(None,"road collision, crash, accident with no injuries")[0] == 8
assert backend.analyze(None,"not breathing after a road collision")[0] >= 85
backend.AMBULANCE_RESPONSE_SECONDS=45
backend.HOSPITAL_RESPONSE_SECONDS=90
with TestClient(backend.app) as client:
    def login(email):
        r=client.post("/api/login",data={"email":email,"password":"AegisDemo!2026"})
        assert r.status_code==200,(email,r.text)
    login("citizen@aegiscare.demo")
    incident=client.post("/api/incidents",data={"latitude":"18.5204","longitude":"73.8567","description":"Road collision, one person injured"},files={"image":("scene.jpg",b"demo-image-bytes","image/jpeg")})
    assert incident.status_code==200,incident.text
    payload=incident.json(); iid=payload["id"]; first_dispatch=payload["dispatch"]; first_hospital=payload["selected_hospital"]
    assert first_dispatch and first_hospital
    db=backend.SessionLocal()
    first_alerts=db.query(backend.Alert).filter_by(incident_id=iid,recipient_role="hospital",alert_type="hospital_prealert").all()
    assert len(first_alerts)==1, len(first_alerts)
    assert first_alerts[0].recipient_id==first_hospital["id"]
    saved_image=db.query(backend.Incident).filter_by(id=iid).first().image_uri
    assert saved_image.startswith("/uploads/"),saved_image
    db.close()
    first_amb=first_dispatch["ambulance_id"]
    login(f"ambulance{first_amb}@aegiscare.demo")
    declined=client.post(f"/api/dispatches/{first_dispatch['id']}/respond",data={"decision":"reject"})
    assert declined.status_code==200,declined.text
    second=declined.json()["next_dispatch"]
    assert second and second["ambulance_id"]!=first_amb,declined.json()
    login(f"hospital{first_hospital['id']}@aegiscare.demo")
    hdeclined=client.post(f"/api/hospitals/{first_hospital['id']}/incidents/{iid}/respond",data={"decision":"reject"})
    assert hdeclined.status_code==200,hdeclined.text
    assert hdeclined.json()["next_hospital"],hdeclined.json()
    db=backend.SessionLocal()
    alerts=db.query(backend.Alert).filter_by(incident_id=iid,recipient_role="hospital",alert_type="hospital_prealert").all()
    assert len(alerts)==2 and len({a.recipient_id for a in alerts})==2
    db.close()
    login("admin@aegiscare.demo")
    backend.AMBULANCE_RESPONSE_SECONDS=0;backend.HOSPITAL_RESPONSE_SECONDS=0
    client.get("/api/dashboard")
    data=client.get("/api/dashboard").json()
    assert any(d["incident_id"]==iid and d["status"]=="Timed out" for d in data["dispatches"])
    hospital_alerts=[a for a in data["alerts"] if a["incident_id"]==iid and a["alert_type"]=="hospital_prealert"]
    assert len(hospital_alerts)==2 and any(a["delivery_status"]=="Timed out" for a in hospital_alerts)
print("PASS: one hospital notified at a time; facility/image routing; sequential ambulance and hospital declines; timeout escalation.")
TMP.cleanup()
