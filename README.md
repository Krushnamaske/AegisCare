# AegisCare — Full-stack demo delivery

A FastAPI + SQLite/PostgreSQL + WebSocket emergency-coordination demonstration. Passwords are stored with salted PBKDF2-HMAC-SHA256 hashing; no passlib/bcrypt dependency is required for fresh databases.
The web application includes citizen reporting, advisory triage, hospital resource
matching/pre-alerts, ambulance dispatch/accept/reject/fallback, live dashboard
updates, dispatch progress stages, an OpenStreetMap map, and OSRM road-route overlays.

## Fastest Windows demo (Python 3.12 (or 3.11))

1. Extract this folder.
2. Open PowerShell in `AegisCare_Project`.
3. Run:
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. Open `http://127.0.0.1:8000`. Health: `http://127.0.0.1:8000/api/health`.
5. For a phone on the same Wi-Fi, open `http://YOUR-LAPTOP-IP:8000` (get IP with `ipconfig`).
   Allow Python/Uvicorn through Windows Firewall on private networks.

## Demo logins

All passwords: `AegisDemo!2026`

- Citizen: `citizen@aegiscare.demo`
- Hospital 1–3: `hospital@aegiscare.demo`, `hospital2@aegiscare.demo`, `hospital3@aegiscare.demo`
- Ambulance 1–3: `ambulance@aegiscare.demo`, `ambulance2@aegiscare.demo`, `ambulance3@aegiscare.demo`
- Admin: `admin@aegiscare.demo`

Demo hospitals and ambulances are seeded automatically at first startup.
The database is `aegiscare.db` (SQLite) and uploads are stored in `uploads/`.
Delete `aegiscare.db` only if you want to reset the local demo data.

## Deployment

Deploy the `AegisCare_Project` directory as a Python web service with start command:
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`
Set `SECRET_KEY` to a long random value (at least 32 random characters). Set `DATABASE_URL` to a persistent
PostgreSQL URL for hosted deployments; standard `postgres://` and `postgresql://` URLs are normalized automatically. Add persistent storage for `uploads/`
or use object storage for uploaded incident photos. WebSockets must be supported
by the hosting service. The map uses OpenStreetMap tiles and Leaflet; road routing uses the public OSRM demo
service. No Google Maps key or billing account is required. OSRM public service is
subject to its fair-use policy and availability; it does not provide live traffic. If
routing is unavailable, the backend falls back to a straight-line distance estimate.
For production or sustained traffic, host your own OSRM instance and follow the
OpenStreetMap tile usage policy.

## Safety and scope

This is a deployable supervised demo, not a certified emergency dispatch service.
Seeded hospitals, ambulances, availability, and demo accounts are fictional.
AI priority is rule-based advisory triage, not medical diagnosis. The demo does
not send SMS/push notifications or connect to real emergency providers. Verify
resources independently and use official emergency services for real incidents.


## Updated workflow behaviour
- Incident descriptions support browser speech-to-text in Chrome/Edge where the Web Speech API is available. The transcript remains editable before submission; typed entry always remains available.
- Hospital requests are sent one at a time. Matching checks emergency-open status, available bed, trauma capability for accident/vehicle cases, ICU availability for high-risk cases, surgery for injury descriptions that suggest it, and ventilator availability for breathing emergencies. A hospital has 90 seconds to respond; on decline/timeout the next eligible hospital is contacted.
- Ambulance requests are sent one at a time, ranked by OSRM ETA when available and straight-line fallback otherwise. A request has 45 seconds to respond; decline/timeout advances to the next available ambulance.
- Uploaded incident photos are saved and shown in the selected hospital's incoming request, and the incident queue; the hospital can open the image.
- Triage score uses grouped, explainable text cues and limited generic object detections only when optional YOLO is enabled. Synonyms are not simply added together. The score is an advisory demonstration heuristic, not a validated clinical prediction.
- Dashboard polling (8 seconds) drives timeout escalation; authenticated WebSocket dispatch/pre-alert events are routed only to the assigned ambulance/hospital (admins also receive operational events).
- Demo credentials: `hospital2@aegiscare.demo`, `hospital3@aegiscare.demo`, `ambulance2@aegiscare.demo`, and `ambulance3@aegiscare.demo` are seeded in addition to the original role accounts. All use `AegisDemo!2026`.
