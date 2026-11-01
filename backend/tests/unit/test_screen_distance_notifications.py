"""Screen-distance reminder API integration tests."""

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
from app.models.personal_baseline import PersonalBaseline
from app.models.screen_distance_notification import ScreenDistanceNotification
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.screen_distance_notifications import router


class ScreenDistanceNotificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(User(id=1, email="screen@example.invalid", username="screen", password_hash="test"))
        self.db.flush()
        self.db.add(Camera(camera_id=1, user_id=1, device_id="test", camera_name="test", resolution_width=640, resolution_height=360))
        self.db.flush()
        self.db.add(PersonalBaseline(
            baseline_id=1, user_id=1, camera_id=1,
            camera_frame_width=640, camera_frame_height=360,
            camera_scale_x=3.5, camera_scale_y=3.5, camera_scale_avg=3.5,
            camera_card_roll=0.0, camera_horizontal_perspective=0.0,
            camera_vertical_perspective=0.0,
            camera_calibrated_at=datetime.now(timezone.utc),
            baseline_status="SUCCESS", confirmation_status="CONFIRMED",
            baseline_sample_count=60, baseline_duration_seconds=15.0,
            baseline_valid_ratio=1.0, shoulder_angle=0.0,
            lateral_tilt_baseline=0.0, neck_flexion_baseline=0.0,
            ipd_baseline=70.0,
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
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_notification_is_idempotent_and_readable(self):
        payload = {
            "runtime_notification_id": "screen-runtime-1",
            "alert_type": "FIRST",
            "distance_ratio": 1.42,
            "decision": "ALERT",
            "reason": "SCREEN_DISTANCE_CONFIRMED",
        }
        first = self.client.post("/sessions/1/screen-distance-notifications", json=payload)
        duplicate = self.client.post("/sessions/1/screen-distance-notifications", json=payload)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(duplicate.status_code, 201, duplicate.text)
        self.assertEqual(
            first.json()["screen_notification_id"],
            duplicate.json()["screen_notification_id"],
        )
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(ScreenDistanceNotification)), 1
        )
        rows = self.client.get("/sessions/1/screen-distance-notifications")
        self.assertEqual(rows.status_code, 200)
        self.assertEqual(len(rows.json()), 1)


if __name__ == "__main__":
    unittest.main()
