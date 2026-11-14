# PostGuard deployment

PostGuard has two independently deployed runtimes:

1. The FastAPI backend runs on a public HTTPS host.
2. The PySide6 desktop application runs on the user's Windows device and calls
   that backend. Camera frames remain on the user's device.

## Backend container

Build from the `backend` directory:

```bash
docker build -t postguard-backend .
```

Required environment variables are listed in `backend/.env.example`. Never
copy a real `.env` file into the image. Before starting a release, the container
runs `alembic upgrade head`, then starts Uvicorn on the host-provided `PORT`.

The hosting platform should use:

- liveness: `GET /health`
- readiness: `GET /ready`

`/ready` returns HTTP 503 when PostgreSQL is unavailable and does not expose
connection details.

## Render Free exam deployment

The repository root contains `render.yaml` for a free Docker web service in
Render's Singapore region. In the Render dashboard, create a new Blueprint,
select this repository and the `integration/desktop-risk-pipeline` branch, then
enter every environment variable marked `sync: false`.

Render Free sleeps after an idle period. Before an exam demonstration, open the
service's `/ready` URL and wait for HTTP 200 before starting the desktop app.

## Desktop API endpoint

Development defaults to `http://127.0.0.1:8001`. A deployed build must provide:

```text
POSTGUARD_API_BASE_URL=https://api.postguardapp.xyz
```

The production installer or launcher must set this value before starting
PostGuard. Do not place database, Supabase service-role, Resend, or JWT secrets
in the desktop package.

## Release order

1. Back up the production database.
2. Rotate and configure production secrets on the hosting platform.
3. Deploy the backend container and confirm `/ready` returns HTTP 200.
4. Complete the staging registration, consent, monitoring, summary, history,
   password, and account-deletion flows.
5. Build the Windows desktop application with the production API endpoint.
6. Test the installer on a clean Windows machine before publishing it.
