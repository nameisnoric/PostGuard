"""Opt-in live DB check.

Run from backend:
.\.venv\Scripts\python.exe -m scripts.check_summary_database --rollback-test

Uses the configured database, creates unique test rows inside an outer transaction,
and rolls them back even when an assertion fails. Does not create or migrate tables.
Exercises password login/JWT, camera/baseline APIs and the monitoring lifecycle.
Database sequences may advance despite rollback.
"""

import argparse
import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def check():
    load_dotenv(".env")
    from app.database.database import get_db
    from app.core.privacy import CURRENT_PRIVACY_NOTICE_VERSION
    from app.models.user import User
    from app.core.security import hash_password, SECRET_KEY, ALGORITHM
    from app.routers.auth import router as auth_router
    from app.routers.cameras import router as cameras_router
    from app.routers.personal_baselines import router as baselines_router
    from app.routers.alert_events import router as alerts_router
    import jwt
    from app.routers.sessions import router as sessions_router
    from app.routers.session_summaries import router as summary_router

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 10})
    marker = "summary_check_" + uuid.uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            password = uuid.uuid4().hex + "Aa1!"
            user = User(
                email=marker + "@ku.th",
                username=marker,
                password_hash=hash_password(password),
                privacy_consent_version=CURRENT_PRIVACY_NOTICE_VERSION,
                privacy_consent_accepted_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.flush()
            user_id = user.id
            app = FastAPI()
            app.include_router(auth_router)
            app.include_router(cameras_router)
            app.include_router(baselines_router)
            app.include_router(alerts_router)
            app.include_router(sessions_router)
            app.include_router(summary_router)
            app.dependency_overrides[get_db] = lambda: db
            with TestClient(app) as client:
                assert client.get("/auth/me").status_code in (401, 403)
                assert client.post("/auth/login", json={"email": user.email, "password": "wrong"}).status_code == 401
                login = client.post("/auth/login", json={"email": user.email, "password": password})
                assert login.status_code == 200, f"Login HTTP {login.status_code}"
                token = login.json()["access_token"]
                client.headers["Authorization"] = "Bearer " + token
                assert client.get("/auth/me").json()["id"] == user_id
                expired = jwt.encode({"sub": str(user_id), "exp": datetime.now(timezone.utc) - timedelta(seconds=10)}, SECRET_KEY, algorithm=ALGORITHM)
                assert client.get("/auth/me", headers={"Authorization": "Bearer " + expired}).status_code == 401
                print("PASS: password login, JWT identity, invalid password and expired token")
                camera = client.post("/cameras", json={"device_id": marker, "camera_name": "Temporary test", "resolution_width": 640, "resolution_height": 360})
                assert camera.status_code == 201, f"Camera HTTP {camera.status_code}"
                camera_id = camera.json()["camera_id"]
                baseline = client.post("/personal-baselines", json={
                    "camera_id": camera_id,
                    "camera_frame_width": 640,
                    "camera_frame_height": 360,
                    "camera_scale_x": 3.5,
                    "camera_scale_y": 3.5,
                    "camera_scale_avg": 3.5,
                    "camera_card_roll": 0.0,
                    "camera_horizontal_perspective": 0.0,
                    "camera_vertical_perspective": 0.0,
                    "camera_calibrated_at": datetime.now(timezone.utc).isoformat(),
                    "baseline_status": "SUCCESS",
                    "confirmation_status": "CONFIRMED",
                    "baseline_sample_count": 60,
                    "baseline_duration_seconds": 15.0,
                    "baseline_valid_ratio": 1.0,
                    "shoulder_angle": 1.0,
                    "lateral_tilt_baseline": 2.0,
                    "neck_flexion_baseline": 1.5,
                    "ipd_baseline": 70.0,
                })
                assert baseline.status_code == 201, f"Baseline HTTP {baseline.status_code}"
                baseline_id = baseline.json()["baseline_id"]
                assert client.get(f"/personal-baselines/{baseline_id}").json()["shoulder_angle"] == 1.0, "Baseline read mismatch"
                start = client.post("/sessions/start", json={"camera_id": camera_id, "baseline_id": baseline_id})
                assert start.status_code == 201, f"Start HTTP {start.status_code}"
                session_id = start.json()["session_id"]
                url = f"/sessions/{session_id}"
                alert = client.post(url + "/alerts", json={"event_type": "NECK_LATERAL_TILT", "risk_level": "MEDIUM"})
                assert alert.status_code == 201, f"Alert HTTP {alert.status_code}"
                for action, status in (("pause", "PAUSED"), ("resume", "RUNNING"), ("end", "COMPLETED")):
                    result = client.post(url + "/" + action)
                    assert result.status_code == 200, f"{action} HTTP {result.status_code}"
                    assert result.json()["status"] == status
                alerts = client.get(url + "/alerts")
                assert alerts.status_code == 200 and len(alerts.json()) == 1
                assert alerts.json()[0]["ended_at"] is not None
                payload = dict(detection_count=24, pose_detected_count=20, face_detected_count=19, average_shoulder=-1.25, average_neck=2.5)
                saved = client.post(url + "/summary", json=payload)
                assert saved.status_code == 201, f"Save HTTP {saved.status_code}"
                db.expire_all()
                loaded = client.get(url + "/summary")
                assert loaded.status_code == 200
                for key, value in payload.items():
                    assert loaded.json()[key] == value, key
                assert loaded.json()["average_risk_score"] is None
                assert loaded.json()["maximum_risk_score"] is None
                assert loaded.json()["total_alert_count"] == 1
                assert client.post(url + "/summary", json=payload).status_code == 409
                assert len(client.get("/summaries").json()) == 1
                # A crashed instance has no reliable end time or local samples.
                unclosed = client.post("/sessions/start", json={"camera_id": camera_id, "baseline_id": baseline_id})
                assert unclosed.status_code == 201
                unclosed_id = unclosed.json()["session_id"]
                unclosed_url = f"/sessions/{unclosed_id}"
                unfinished_alert = client.post(unclosed_url + "/alerts", json={"event_type": "NECK_LATERAL_TILT", "risk_level": "MEDIUM"})
                assert unfinished_alert.status_code == 201
                recovered = client.post(unclosed_url + "/interrupt")
                assert recovered.status_code == 200
                assert recovered.json()["status"] == "INTERRUPTED"
                assert recovered.json()["ended_at"] is None
                assert recovered.json()["total_duration"] is None
                assert client.post(unclosed_url + "/interrupt").status_code == 200
                assert client.post(unclosed_url + "/summary", json=payload).status_code == 409
                incomplete_alerts = client.get(unclosed_url + "/alerts").json()
                assert incomplete_alerts[0]["incomplete"] is True
                assert incomplete_alerts[0]["duration"] is None
                next_session = client.post("/sessions/start", json={"camera_id": camera_id, "baseline_id": baseline_id})
                assert next_session.status_code == 201
                assert client.post(f"/sessions/{next_session.json()['session_id']}/interrupt").status_code == 200
                print("PASS: interrupted recovery, unknown durations, incomplete alert and new session")
                other = User(email=marker + "_other@ku.th", username=marker + "_other", password_hash=hash_password(password))
                db.add(other)
                db.flush()
                other_login = client.post("/auth/login", json={"email": other.email, "password": password})
                assert other_login.status_code == 200
                client.headers["Authorization"] = "Bearer " + other_login.json()["access_token"]
                assert client.get(url + "/summary").status_code == 404
                assert client.post(url + "/summary", json=payload).status_code == 404
                assert client.get("/summaries").json() == []
                assert client.get(url + "/alerts").status_code == 404
                assert client.post(unclosed_url + "/interrupt").status_code == 404
                client.headers.pop("Authorization")
                assert client.get("/sessions").status_code in (401, 403)
            print("PASS: PostgreSQL camera/baseline/start/alert/pause/resume/end/save/read/duplicate/ownership")
        finally:
            db.close()
            transaction.rollback()
        assert connection.scalar(select(User.id).where(User.username == marker)) is None
        print("PASS: temporary test rows rolled back")
    engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollback-test", action="store_true", required=True)
    parser.parse_args()
    try:
        check()
    except AssertionError as error:
        print("FAIL: AssertionError:", str(error)[:200])
        raise SystemExit(1)
    except Exception as error:
        # Do not include SQL parameters, URLs or credentials in console output.
        print("FAIL:", type(error).__name__)
        raise SystemExit(1)
