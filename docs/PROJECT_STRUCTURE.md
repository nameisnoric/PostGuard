# Project structure

PostGuard separates code by runtime first and responsibility second. The
desktop application owns camera processing because frames stay on the user's
machine. The backend owns authentication, persistent records and external
integrations.

## Dependency direction

```text
Desktop UI -> Desktop services -> Vision / Backend API
Backend routers -> Backend services / schemas / models -> Database
```

The backend must not import desktop code. Desktop code communicates with the
backend through `APIClient`; it must not import backend Python modules. This
keeps both applications independently runnable and packageable.

## Backend

| Folder | Responsibility |
| --- | --- |
| `backend/app/core` | Security helpers and global application policies |
| `backend/app/database` | SQLAlchemy engine, session lifecycle and base model |
| `backend/app/models` | Persistent database entities |
| `backend/app/schemas` | Pydantic API request and response contracts |
| `backend/app/routers` | FastAPI endpoints and HTTP orchestration |
| `backend/app/services` | Email, avatar storage and account lifecycle logic |
| `backend/alembic` | Ordered database schema migrations |
| `backend/scripts` | Explicit administrative and setup commands |
| `backend/tests/unit` | Isolated backend behavior tests |

## Desktop

| Folder | Responsibility |
| --- | --- |
| `desktop/app/core` | Local configuration and authentication token storage |
| `desktop/app/services` | UI-independent workflows, API calls and session logic |
| `desktop/app/ui/windows` | Login, registration, recovery and main windows |
| `desktop/app/ui/pages` | Pages displayed inside the authenticated main window |
| `desktop/app/ui/dialogs` | Modal confirmations, reports and notices |
| `desktop/app/ui/utils` | Presentation-only sizing and rendering helpers |
| `desktop/app/vision` | Local camera calibration, models and MediaPipe features |
| `desktop/app/assets` | Resources shipped with the desktop executable |
| `desktop/tests/unit` | Automated tests that do not open physical hardware |
| `desktop/tests/hardware` | Opt-in webcam integration checks |
| `desktop/tests/vision_manual` | Interactive research diagnostics, excluded from unit tests |

## Placement rules

- Put a new API endpoint in `routers`, its data contract in `schemas`, and
  reusable business logic in `services`.
- Put a new navigable Desktop screen in `ui/pages`; use `ui/dialogs` only for
  short modal interactions and `ui/windows` for independent windows.
- Put camera frame and landmark algorithms in `vision`. Expose them to pages
  through `services` so UI code does not know model file locations.
- Put automated mocks and regression tests in `tests/unit`. Any test that opens
  a camera or waits for user input belongs in `hardware` or `vision_manual`.
- Keep secrets in ignored `.env` files. Commit only `.env.example` templates.
