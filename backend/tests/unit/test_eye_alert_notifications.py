"""Eye reminder persistence tests against an isolated database."""

import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
import app.models
from app.models.camera import Camera
from app.models.eye_alert_notification import EyeAlertNotification
from app.models.personal_baseline import PersonalBaseline
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.eye_alert_notifications import router


class EyeAlertNotificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(User(id=1, email="eye@example.invalid", username="eye", password_hash="x"))
        self.db.flush()
        self.db.add(Camera(
            camera_id=1, user_id=1, device_id="0", camera_name="cam",
            resolution_width=640, resolution_height=360,
        ))
        self.db.flush()
        self.db.add(PersonalBaseline(
            baseline_id=1, user_id=1, camera_id=1,
            camera_frame_width=640, camera_frame_height=360,
            camera_scale_x=1.0, camera_scale_y=1.0, camera_scale_avg=1.0,
            camera_card_roll=0.0, camera_horizontal_perspective=0.0,
            camera_vertical_perspective=0.0,
            camera_calibrated_at=datetime.now(timezone.utc), baseline_status="SUCCESS",
            confirmation_status="CONFIRMED", baseline_sample_count=10,
            baseline_duration_seconds=5.0, baseline_valid_ratio=1.0,
            shoulder_angle=0.0, lateral_tilt_baseline=0.0,
            neck_flexion_baseline=0.0, ipd_baseline=70.0,
        ))
        self.db.flush()
        self.db.add(PostureSession(
            session_id=1, user_id=1, camera_id=1, baseline_id=1, status="RUNNING"
        ))
        self.db.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_first_notification_is_idempotent_and_readable(self):
        payload = {
            "runtime_notification_id": "eye-runtime-1",
            "alert_type": "FIRST",
            "blink_rate": 5.0,
            "window_blink_count": 5,
            "decision": "ALERT",
            "reason": "LOW_BLINK_CONFIRMED",
        }
        first = self.client.post("/sessions/1/eye-alert-notifications", json=payload)
        duplicate = self.client.post("/sessions/1/eye-alert-notifications", json=payload)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(
            duplicate.json()["eye_notification_id"],
            first.json()["eye_notification_id"],
        )
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(EyeAlertNotification)), 1
        )
        rows = self.client.get("/sessions/1/eye-alert-notifications")
        self.assertEqual(rows.status_code, 200)
        self.assertEqual(rows.json()[0]["alert_type"], "FIRST")

    def test_requires_owner_and_running_session(self):
        payload = {
            "runtime_notification_id": "eye-runtime-2",
            "alert_type": "REPEAT",
            "blink_rate": 4.0,
            "window_blink_count": 4,
        }
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2)
        self.assertEqual(
            self.client.post("/sessions/1/eye-alert-notifications", json=payload).status_code,
            404,
        )
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self.db.get(PostureSession, 1).status = "COMPLETED"
        self.db.commit()
        self.assertEqual(
            self.client.post("/sessions/1/eye-alert-notifications", json=payload).status_code,
            409,
        )


if __name__ == "__main__":
    unittest.main()
