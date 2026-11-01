# PostGuard

PostGuard is a desktop posture-monitoring application built with a PySide6
client, a FastAPI backend, PostgreSQL/Supabase persistence, MediaPipe and
OpenCV.

## Project structure

```text
PostGuard/
|-- backend/                  FastAPI API and persistence
|   |-- app/
|   |   |-- core/             Security and application policies
|   |   |-- database/         SQLAlchemy engine and sessions
|   |   |-- models/           Database models
|   |   |-- routers/          HTTP endpoints
|   |   |-- schemas/          Request and response contracts
|   |   `-- services/         Backend business integrations
|   |-- alembic/              Database migrations
|   |-- scripts/              Administrative utilities
|   `-- tests/unit/           Backend unit tests
|-- desktop/                  PySide6 application and local vision pipeline
|   |-- app/
|   |   |-- assets/           Sounds and other packaged resources
|   |   |-- core/             Desktop configuration and token storage
|   |   |-- services/         Application use cases and API access
|   |   |-- ui/
|   |   |   |-- windows/      Top-level application windows
|   |   |   |-- pages/        Main navigation pages
|   |   |   |-- dialogs/      Modal user interactions
|   |   |   `-- utils/        UI-only helpers
|   |   `-- vision/           Camera calibration and MediaPipe processing
|   |-- scripts/              Optional development examples
|   `-- tests/
|       |-- unit/             Tests that do not require a webcam
|       |-- hardware/         Explicit webcam checks
|       `-- vision_manual/    Interactive vision diagnostics
`-- docs/                     Architecture, setup and test documentation
```

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for ownership and
dependency rules between these folders.

Environment templates stay beside the application that uses them. Copy
`backend/.env.example` to `backend/.env` and keep real secrets only in `.env`.
For the Desktop client, copy `desktop/.env.example` to `desktop/.env` when the
API is not running at the local development address.

## Run

Run the API:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

Run the desktop application in a second terminal:

```powershell
cd desktop
.\.venv\Scripts\python.exe -m app.main
```

Build the Windows application locally (this does not deploy or upload it):

```powershell
cd desktop
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm PostGuard.spec
```

The executable is created under `desktop/dist/PostGuard/`. Put a `.env` file
beside `PostGuard.exe` with `POSTGUARD_API_BASE_URL=https://...` when connecting
the packaged client to a hosted API. The Desktop `.env` must never contain
database, JWT, Resend or Supabase service-role secrets.

## Test

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p "test_*.py" -v

cd ..\desktop
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p "test_*.py" -v
```

Webcam checks and interactive vision diagnostics are intentionally separate:

```powershell
cd desktop
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests/hardware -p "test_camera_resolution.py" -v

.\.venv\Scripts\python.exe -m tests.vision_manual.test_pose
```

Additional documentation:

- [UI implementation guide](docs/UI_IMPLEMENTATION_GUIDE.md)
- [Flow and test report](docs/FLOW_AND_TEST_REPORT.md)
- [Private avatar setup](docs/PRIVATE_AVATAR_SETUP.md)
- [TOR desktop requirements](docs/TOR_DESKTOP_REQUIREMENTS.md)
- [RULA scoring and camera mapping](docs/RULA_MAPPING.md)
