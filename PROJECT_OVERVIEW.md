# AegisCare — Project Overview for Evaluators

## The problem
Emergency response can be slowed when incident details, hospital capacity, and ambulance availability are handled in disconnected channels. Responders may lack a shared view of the incident and the resources being considered.

## Our solution
AegisCare is a shared web-based emergency coordination prototype. It brings incident reporting, advisory prioritisation, hospital resource visibility, ambulance dispatch, and response status tracking into one application.

## End-to-end workflow

1. **Report:** A citizen/reporter submits an incident description, coordinates (or browser location), and an optional photo.
2. **Prioritise:** An explainable, grouped-evidence rules score reviews reported symptoms and incident context. Optional generic object detection can add limited evidence; it cannot identify injuries or diagnose severity. The score is not clinically validated.
3. **Match:** The backend filters emergency-open hospitals by required capabilities and available beds, then ranks eligible facilities by OSRM road ETA (or straight-line fallback). Only the first matched hospital receives the request and image; decline or 90-second timeout advances to the next eligible facility.
4. **Pre-alert and dispatch:** The system stores the hospital request and creates a request for only the nearest available ambulance. Decline or 45-second timeout advances sequentially to the next available ambulance; it never broadcasts the dispatch to the fleet.
5. **Respond:** An ambulance user accepts or rejects the request. Rejection triggers a fallback attempt to another available ambulance.
6. **Track:** The ambulance advances through Accepted, En route, Arrived, Transporting, and Completed. Authenticated WebSocket events are targeted to the assigned hospital/ambulance; role-based dashboards show the relevant incidents and alerts.
7. **Map:** OpenStreetMap and Leaflet display incident, hospital, and ambulance markers. OSRM can provide road-route geometry, distance, and estimated duration. The estimate excludes live traffic.

## Technology

- Frontend: HTML, CSS, JavaScript, Leaflet
- Backend: Python, FastAPI, REST API, WebSocket
- Database: SQLAlchemy with SQLite locally and PostgreSQL for hosted deployment
- Security: HTTP-only session cookie, JWT, PBKDF2-HMAC-SHA256 password hashing, role checks
- Maps and routing: OpenStreetMap tiles, Leaflet, OSRM public demo routing endpoint

## What is demonstrated vs. future work

**Demonstrated in this prototype:** multi-role login, editable speech-to-text incident entry on supported browsers, citizen incident intake, image upload and hospital-side image display, explainable advisory priority score, facility-filtered hospital matching with sequential escalation, nearest-first ambulance dispatch with sequential rejection/timeout escalation, ambulance progress lifecycle, role-filtered dashboards, map markers, and route overlay when OSRM is reachable.

**Not integrated:** real hospital/ambulance networks, verified live capacity, emergency call centers, SMS/phone/push delivery, live traffic, certified medical triage, and production-grade 24/7 operations. Seeded Pune hospitals, ambulances, and demo accounts are fictional test data.

## Responsible-use statement
AegisCare is a hackathon prototype for demonstrating coordination workflows. AI/rule outputs are advisory only; facility availability must be independently verified. It must not replace official emergency numbers, professional medical judgment, or real emergency dispatch systems.
