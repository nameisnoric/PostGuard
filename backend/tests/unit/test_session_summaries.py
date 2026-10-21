"""Summary API integration tests against an isolated in-memory database."""

import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

# Set before importing the application's engine; never use the configured cloud DB.
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
import app.models
from app.models.user import User
from app.models.camera import Camera
from app.models.personal_baseline import PersonalBaseline
from app.models.session import PostureSession
from app.models.session_summary import SessionSummary
from app.models.alert_event import AlertEvent
from app.routers.auth import get_current_user
from app.routers.session_summaries import router
from app.schemas.session_summary import SessionSummaryCreate


class SessionSummaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(User(id=1, email="summary@example.invalid", username="summary", password_hash="test"))
        self.db.flush()
        self.db.add(Camera(camera_id=1, user_id=1, device_id="test", camera_name="test", resolution_width=640, resolution_height=360))
        self.db.flush()
        self.db.add(PersonalBaseline(
            baseline_id=1,
            user_id=1,
            camera_id=1,
            camera_frame_width=640,
            camera_frame_height=360,
            camera_scale_x=3.5,
            camera_scale_y=3.5,
            camera_scale_avg=3.5,
            camera_card_roll=0.0,
            camera_horizontal_perspective=0.0,
            camera_vertical_perspective=0.0,
            camera_calibrated_at=datetime.now(timezone.utc),
            baseline_status="SUCCESS",
            confirmation_status="CONFIRMED",
            baseline_sample_count=60,
            baseline_duration_seconds=15.0,
            baseline_valid_ratio=1.0,
            shoulder_angle=-1.25,
            lateral_tilt_baseline=2.75,
            neck_flexion_baseline=1.5,
            ipd_baseline=70.0,
        ))
        self.db.flush()
        self.db.add(PostureSession(session_id=1, user_id=1, camera_id=1, baseline_id=1, status="COMPLETED"))
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self.client = TestClient(self.app)
        self.payload = dict(
            detection_count=20,
            pose_detected_count=18,
            face_detected_count=15,
            average_shoulder=-1.25,
            average_neck=2.75,
            average_risk_score=1.25,
            maximum_risk_score=3.0,
            blink_rate=14.0,
            risk_score_method="RULA_ADAPTED_FRONT_V1",
        )

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_save_read_and_duplicate(self):
        now = datetime.now(timezone.utc)
        self.db.add(AlertEvent(session_id=1, event_type="NECK_LATERAL_TILT", risk_level="MEDIUM", started_at=now, ended_at=now, duration=12))
        self.db.commit()
        result = self.client.post("/sessions/1/summary", json=self.payload)
        self.assertEqual(result.status_code, 201, result.text)
        self.db.expire_all()
        saved = self.client.get("/sessions/1/summary").json()
        for key, value in self.payload.items():
            self.assertEqual(saved[key], value)
        self.assertEqual(saved["average_risk_score"], 1.25)
        self.assertEqual(saved["maximum_risk_score"], 3.0)
        self.assertEqual(saved["blink_rate"], 14.0)
        self.assertEqual(saved["risk_score_method"], "RULA_ADAPTED_FRONT_V1")
        self.assertEqual(saved["medium_risk_duration"], 12)
        self.assertEqual(saved["total_alert_count"], 1)
        self.assertEqual(self.client.get("/summaries").json(), [saved])
        duplicate = self.client.post("/sessions/1/summary", json=self.payload)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SessionSummary)), 1)

    def test_no_report_and_unfinished_session(self):
        self.assertEqual(self.client.get("/sessions/1/summary").status_code, 404)
        session = self.db.get(PostureSession, 1)
        for status in ("RUNNING", "PAUSED"):
            session.status = status
            self.db.commit()
            self.assertEqual(self.client.post("/sessions/1/summary", json=self.payload).status_code, 409)

    def test_open_alert_has_zero_completed_duration(self):
        self.db.add(AlertEvent(
            session_id=1,
            event_type="SHOULDER_TILT",
            risk_level="HIGH",
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            duration=None,
        ))
        self.db.commit()

        result = self.client.post("/sessions/1/summary", json=self.payload)

        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()["high_risk_duration"], 0)
        self.assertEqual(result.json()["high_risk_alert_count"], 1)

    def test_other_user_cannot_read_or_write(self):
        self.client.post("/sessions/1/summary", json=self.payload)
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2)
        self.assertEqual(self.client.get("/sessions/1/summary").status_code, 404)
        self.assertEqual(self.client.post("/sessions/1/summary", json=self.payload).status_code, 404)
        self.assertEqual(self.client.get("/summaries").json(), [])

    def test_invalid_measurements(self):
        for change in ({"detection_count": -1}, {"pose_detected_count": 21}, {"face_detected_count": True}, {"detection_count": 2.5}):
            with self.subTest(change=change):
                response = self.client.post("/sessions/1/summary", json={**self.payload, **change})
                self.assertEqual(response.status_code, 422)
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                SessionSummaryCreate(**{**self.payload, "average_neck": value})
        for change in (
            {"average_risk_score": 0},
            {"maximum_risk_score": 7.1},
            {"average_risk_score": 2.0, "maximum_risk_score": 1.0},
            {"blink_rate": -1.0},
            {"average_risk_score": 2.0, "maximum_risk_score": 3.0, "risk_score_method": None},
            {"average_risk_score": None, "maximum_risk_score": None, "risk_score_method": "RULA_ADAPTED_FRONT_V1"},
        ):
            with self.subTest(change=change):
                response = self.client.post(
                    "/sessions/1/summary", json={**self.payload, **change}
                )
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
