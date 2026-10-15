# PostGuard

PostGuard is a desktop posture-monitoring application with a PySide6 client,
a FastAPI backend and PostgreSQL/Supabase persistence.

## Project structure

```text
PostGuard/
├── backend/
│   ├── app/                 FastAPI application
│   ├── alembic/             Database migrations
│   ├── camera_card/         Camera and MediaPipe research modules
│   ├── scripts/             Opt-in database and setup utilities
│   └── tests/unit/          Backend unit tests
├── desktop/
│   ├── app/                 PySide6 desktop application
│   ├── scripts/             Manual development utilities
│   ├── tests/unit/          Tests that do not require a webcam
│   └── tests/hardware/      Explicit webcam checks
└── docs/                    Architecture, UI and setup documentation
```

Environment templates stay beside the application that uses them. Copy
`backend/.env.example` to `backend/.env` and keep real secrets only in `.env`.

## Run

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001

cd ..\desktop
.\.venv\Scripts\python.exe -m app.main
```

## Test

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p "test_*.py" -v

cd ..\desktop
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p "test_*.py" -v
```

Webcam checks are intentionally separate:

```powershell
cd desktop
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests/hardware -p "test_camera_resolution.py" -v
```

See [docs/UI_IMPLEMENTATION_GUIDE.md](docs/UI_IMPLEMENTATION_GUIDE.md),
[docs/FLOW_AND_TEST_REPORT.md](docs/FLOW_AND_TEST_REPORT.md) and
[docs/PRIVATE_AVATAR_SETUP.md](docs/PRIVATE_AVATAR_SETUP.md) for details.
