# 4-minute AegisCare evaluator walkthrough

Use three separate browser profiles/windows so the Citizen, Hospital, and Ambulance roles can remain signed in simultaneously. Use only the fictional demo accounts in the submission guide.

## 0:00–0:30 — Introduce the problem and shared platform
"AegisCare brings incident reporting, hospital coordination, and ambulance dispatch into one shared workspace. The goal of this prototype is to demonstrate how information can move between the three roles without manually switching between disconnected tools."

## 0:30–1:15 — Citizen reports an incident
1. Sign in as `citizen@aegiscare.demo`.
2. Use the default Pune coordinates or click **Use my location** after granting browser permission.
3. Optionally click **Speak to text**, dictate the incident, then review/edit the transcript. Or type: `Road collision, one person injured near the junction.`
4. Submit the incident.
5. Point out the incident ID, explainable advisory score, one facility-matched hospital request, attached image, and the first ambulance request.

Say: "The current prioritisation is a transparent rules-based demonstration, not a medical diagnosis. The photo field is optional."

## 1:15–1:55 — Hospital resource desk
1. In a second browser, sign in as `hospital@aegiscare.demo`.
2. Show the incoming request for this hospital, including the incident photo. Accept or decline it; if declined, show the next eligible hospital receiving the request.
3. Change one demo resource value and save.

Say: "Hospital capacity and capabilities are self-reported in this prototype. A real deployment would require verified integrations and operational ownership."

## 1:55–3:15 — Ambulance response
1. In a third browser, sign in as `ambulance@aegiscare.demo`.
2. Show the pending dispatch and accept it.
3. Advance it through **En route**, **Arrived**, **Transporting**, and **Completed**.
4. To demonstrate fallback, reject the first request and show the next-nearest ambulance receiving the request. If nobody responds, wait for the response timeout to trigger sequential escalation.

Say: "Only one ambulance is requested at a time. A decline or timeout advances to the next-nearest available unit. No fleet-wide broadcast is sent."

## 3:15–4:00 — Map and shared outcome
1. Return to the citizen/admin window and refresh.
2. Show the same incident and dispatch lifecycle.
3. Point out map markers and, if available, the OSRM route line.

Say: "The map uses OpenStreetMap and Leaflet. OSRM supplies a road route and estimated duration when reachable; it does not include live traffic."

## If the internet/routing service is unavailable
The core API workflow can still be demonstrated locally. The map may show markers without route geometry, and the backend falls back to straight-line distance/ETA. Do not claim that live traffic, SMS, or real emergency providers are integrated.
