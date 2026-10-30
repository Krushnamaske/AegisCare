# Deploy AegisCare on Render

This guide deploys the FastAPI website. You must sign in to GitHub and Render yourself; this package cannot create services inside your accounts or publish a live URL without your authorization.

## Before deploying

- Create a GitHub repository for this project.
- Create a Render account and connect GitHub.
- For persistent hosted data, provision a PostgreSQL database on Render (or another PostgreSQL provider). Do not rely on SQLite on an ephemeral web-service filesystem for a public demo.
- Incident image uploads are stored on the app filesystem. On Render, add a persistent disk mounted at `/opt/render/project/src/uploads` (if supported by your selected service plan), or switch uploads to object storage. Without persistent upload storage, uploaded images can disappear after redeploy/restart.

## 1. Push the project to GitHub

Extract the ZIP. Open PowerShell inside `AegisCare_Project` and run:

```powershell
git init
git add .
git commit -m "Prepare AegisCare hackathon submission"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/aegiscare.git
git push -u origin main
```

Replace the remote URL with your own repository URL. If the repository already exists locally, do not run `git init` or add a second `origin`; update the existing remote instead.

## 2. Create PostgreSQL

In Render Dashboard, create a PostgreSQL database. Copy its **Internal Database URL** when the web service is also hosted on Render. Keep the database in the same region as the web service where possible.

## 3. Create the web service

1. In Render, choose **New + → Web Service** and connect your GitHub repository.
2. If the repository contains the contents of `AegisCare_Project` at its root, leave Root Directory blank. If you uploaded the parent folder, set Root Directory to `AegisCare_Project`.
3. Runtime: **Python 3**.
4. Build command: `pip install -r requirements.txt`.
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
6. Add environment variables:
   - `SECRET_KEY`: generate a long random secret (at least 32 random characters; do not reuse the demo password).
   - `DATABASE_URL`: the PostgreSQL Internal Database URL.
   - `COOKIE_SECURE`: `true`.
   - `MAX_UPLOAD_MB`: `8` (optional).
7. Deploy and wait for the build to finish.

The included `render.yaml` is a starting Blueprint configuration. It intentionally asks you to supply `DATABASE_URL` rather than silently creating a billable database.

## 4. Verify deployment

Open these URLs, replacing `YOUR-SERVICE.onrender.com` with the URL Render assigns:

- Website: `https://YOUR-SERVICE.onrender.com/`
- Health: `https://YOUR-SERVICE.onrender.com/api/health`
- API docs: `https://YOUR-SERVICE.onrender.com/docs`

Health should return JSON containing `"status":"ok"` and `"database":"connected"`.

Sign in with the demo accounts listed in `SUBMISSION_GUIDE.md`. Change or disable demo credentials before any non-demo/public use. The demo seed accounts are intentionally for evaluator walkthrough only.

## 5. Important deployment limitations

- Render free web services may sleep when idle; the first request after inactivity can take time.
- Free database offerings can have storage, connection, or expiry limits that change. Check the current plan details before selecting one.
- The public OSRM demo routing service and OpenStreetMap tile service have fair-use policies. They do not provide live traffic and are not guaranteed for production/high-volume use.
- If the deployment does not have persistent storage for `uploads/`, image files may not survive a restart or redeploy. Core incident data is stored in PostgreSQL.
- WebSockets need to be supported by the chosen host. AegisCare also has a manual Refresh button as a fallback.
- This is a supervised hackathon prototype, not a certified emergency dispatch service. Do not use it to coordinate real emergencies.
