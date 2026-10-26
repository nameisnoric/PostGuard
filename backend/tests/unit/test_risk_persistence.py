"""Risk persistence API tests against an isolated database."""

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
from app.models.alert_notification import AlertNotification
from app.models.camera import Camera
from app.models.personal_baseline import PersonalBaseline
from app.models.risk_event import RiskEvent
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.risk_persistence import router


class RiskPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(User(id=1, email="risk@example.invalid", username="risk", password_hash="x"))
        self.db.flush()
        self.db.add(Camera(camera_id=1, user_id=1, device_id="0", camera_name="cam", resolution_width=640, resolution_height=360))
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
        self.db.add(PostureSession(session_id=1, user_id=1, camera_id=1, baseline_id=1, status="RUNNING"))
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

    def test_lifecycle_and_idempotent_notification(self):
        start_payload = {
            "runtime_event_id": "risk-event-000001", "risk_level": "MODERATE",
            "active_factors": ["neck_lateral_tilt"], "evidence_groups": ["NECK"],
        }
        first = self.client.post("/sessions/1/risk-events", json=start_payload)
        duplicate = self.client.post("/sessions/1/risk-events", json=start_payload)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(duplicate.json()["risk_event_id"], first.json()["risk_event_id"])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(RiskEvent)), 1)

        update = self.client.patch(
            "/sessions/1/risk-events/risk-event-000001",
            json={"event_action": "ESCALATED", "risk_level": "HIGH", "active_factors": ["neck_lateral_tilt"], "evidence_groups": ["NECK"]},
        )
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["max_risk_level"], "HIGH")

        notification = {
            "runtime_notification_id": "notification-stable", "alert_type": "ESCALATION",
            "risk_level": "HIGH", "decision": "ALERT", "reason": "RISK_ESCALATED",
        }
        for _ in range(2):
            response = self.client.post(
                "/sessions/1/risk-events/risk-event-000001/notifications", json=notification
            )
            self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AlertNotification)), 1)

        resolved = self.client.post(
            "/sessions/1/risk-events/risk-event-000001/resolve",
            json={"resolved_reason": "SAFE_POSTURE"},
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["status"], "RESOLVED")
        self.assertEqual(len(self.client.get("/sessions/1/risk-events").json()), 1)
        self.assertEqual(len(self.client.get("/sessions/1/alert-notifications").json()), 1)

    def test_ownership_and_session_state_are_enforced(self):
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2)
        response = self.client.post(
            "/sessions/1/risk-events",
            json={"runtime_event_id": "x", "risk_level": "MODERATE"},
        )
        self.assertEqual(response.status_code, 404)
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self.db.get(PostureSession, 1).status = "COMPLETED"
        self.db.commit()
        response = self.client.post(
            "/sessions/1/risk-events",
            json={"runtime_event_id": "x", "risk_level": "MODERATE"},
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
