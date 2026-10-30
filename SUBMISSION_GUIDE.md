# AegisCare — Evaluator & Submission Guide

## 1. Project in one sentence
AegisCare is a shared emergency-coordination web platform that connects incident reporters, hospitals and ambulance teams through incident intake, advisory prioritisation, facility matching, dispatch response and status tracking.

## 2. What evaluators can try
- **Citizen / reporter:** create an account or use the demo login; submit an incident with coordinates, description and optional image.
- **Advisory triage:** receive a grouped-evidence score and explanation. Browser speech-to-text can populate the editable description. Optional YOLO generic object detection can add limited evidence, but does not detect injury severity. This is not a medical diagnosis.
- **Hospital desk:** only the best-matched eligible hospital receives the first request and incident image. Accept or decline; a decline or 90-second timeout advances to the next eligible facility. Update bed/ICU counts, ventilators, trauma/surgery capability and blood-bank status.
- **Ambulance desk:** only the nearest available ambulance receives the first dispatch request. Accept or reject; a rejection or 45-second timeout advances to the next nearest available ambulance. Update GPS and advance accepted dispatches through their lifecycle.
- **Shared operations view:** view incidents, hospitals, ambulances, alerts and active dispatches on an OpenStreetMap map. OSRM may draw road routes and provide distance/time estimates when the public routing service is reachable.

## 3. Run locally (Windows)
1. Install Python 3.12 (recommended) or Python 3.11.
2. Extract the submission ZIP.
3. Open PowerShell in `AegisCare_Project`.
4. Run `START_AEGISCARE_WINDOWS.bat`, or use the commands below:
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
5. Visit `http://127.0.0.1:8000`.
6. API health: `http://127.0.0.1:8000/api/health`; interactive API documentation: `http://127.0.0.1:8000/docs`.

## 4. Demo credentials
All four demo accounts use password: `AegisDemo!2026`.

| Role | Login | What to demonstrate |
|---|---|---|
| Citizen | `citizen@aegiscare.demo` | Submit incident and optional photo |
| Hospital | `hospital@aegiscare.demo` | Review pre-alert and update resources |
| Ambulance 1 | `ambulance@aegiscare.demo` | Accept/reject dispatch and update progress |
| Ambulance 2/3 | `ambulance2@aegiscare.demo`, `ambulance3@aegiscare.demo` | Test sequential fallback |
| Hospital 2/3 | `hospital2@aegiscare.demo`, `hospital3@aegiscare.demo` | Test sequential facility fallback |
| Admin | `admin@aegiscare.demo` | View the shared operational picture |

These accounts, hospitals and ambulances are fictional demonstration data, seeded on first startup.

## 5. Recommended 3–4 minute evaluator walkthrough
Use separate browser profiles/windows so all three roles can stay signed in:

1. **Citizen (45–60 sec):** sign in, submit an incident near the default Pune coordinates, explain that the description is evaluated by an advisory rules-based triage function. The response includes priority, selected hospital and dispatch request where resources are available.
2. **Hospital (30–45 sec):** sign in in another browser, show the incident/pre-alert and update a facility resource value. Save the form.
3. **Ambulance (60 sec):** sign in in a third browser, accept the pending request. Demonstrate En route, Arrived, Transporting and Completed.
4. **Shared outcome (30 sec):** return to the citizen/admin window and refresh. Show the incident status and dispatch history reflecting the same backend records.
5. **Map (optional):** point out incident, hospital and ambulance markers. If OSRM is reachable, an active dispatch route is drawn. Explain that route ETA is an estimate and does not include live traffic.

For fallback demonstration, reject the first hospital request to see the next eligible hospital contacted; reject the first ambulance request to see the next nearest available ambulance contacted. If nobody responds, the 90-second hospital and 45-second ambulance response windows trigger sequential escalation on dashboard polling.

## 6. Technical architecture
- Frontend: HTML, CSS, vanilla JavaScript, Leaflet.
- Backend: Python FastAPI REST endpoints and WebSocket event channel.
- Persistence: SQLAlchemy with SQLite by default; PostgreSQL supported through `DATABASE_URL`.
- Authentication: HTTP-only session cookie with JWT; passwords hashed using PBKDF2-HMAC-SHA256.
- Mapping: OpenStreetMap tiles with Leaflet; OSRM public demo endpoint for road routes. Straight-line distance/ETA fallback is used when OSRM cannot be reached.
- Uploads: optional incident images saved under `uploads/`.

## 7. Validation performed for this delivery
The application was exercised with automated API integration checks using a fresh temporary SQLite database. Checks covered API health, login for all four roles, dashboard access, incident submission, hospital selection, dispatch creation, ambulance acceptance and the En route → Arrived → Transporting → Completed lifecycle. Python imports/startup and JavaScript syntax were checked. The integration test stubs OSRM responses so core workflow checks are deterministic; it does not certify public routing availability or every browser/device combination.

To rerun the workflow smoke test from this folder:
```powershell
python tests\smoke_test.py
python tests\sequential_workflow_test.py
```

## 8. Honest scope and limitations
- This is a hackathon prototype, not a certified or production emergency dispatch system.
- All seeded hospitals, ambulances, availability and demo identities are fictional. No real provider is contacted.
- Triage is advisory and rule-based by default. Optional YOLO detections are generic object detections, not injury or severity diagnosis.
- Alerts are persisted in the application and surfaced in dashboards; SMS, phone calls and push notifications are not integrated.
- OSRM public routing and OpenStreetMap tile services have usage policies and availability limits. There is no live traffic feed. A production deployment should host routing infrastructure appropriately and comply with tile-provider policy.
- For hosted deployment, configure a strong `SECRET_KEY`, persistent PostgreSQL, persistent upload storage and HTTPS. Never use the demo credentials or default secret in production.

## 9. Reset local demo data
Stop the server, then delete `aegiscare.db` and files inside `uploads/` if you want a clean local demo. On next startup the fictional demo entities and accounts are recreated.

## New workflow validation
The updated test pass additionally verified that only one hospital receives the first pre-alert, the uploaded incident image is saved and exposed to the hospital dashboard, ambulance rejection advances to a different ambulance, hospital rejection advances to a different eligible hospital, and response timeouts advance both queues. Browser speech-to-text requires a supported browser and microphone permission.
