"""Eye reminder persistence tests against an isolated database."""

import os
import unittest

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


class EyeAlertNotificationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        self.user = User(
            id=1,
            email="eye-alert@example.invalid",
            username="eye-alert",
            password_hash="test",
        )
        self.db.add(self.user)
        self.db.add(Camera(
            camera_id=1,
            user_id=1,
            device_id="0",
            camera_name="Camera 0",
            resolution_width=640,
            resolution_height=480,
        ))
        self.db.add(PersonalBaseline(
            baseline_id=1,
            user_id=1,
            camera_id=1,
        ))
        self.db.flush()
        self.db.add(PostureSession(
            session_id=1,
            user_id=1,
            baseline_id=1,
            camera_id=1,
            status="RUNNING",
        ))
        self.db.add(PostureSession(
            session_id=2,
            user_id=1,
            baseline_id=1,
            camera_id=1,
            status="COMPLETED",
        ))
        self.db.commit()

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def payload(runtime_id="eye-runtime-1", alert_type="FIRST"):
        return {
            "runtime_notification_id": runtime_id,
            "alert_type": alert_type,
            "blink_rate": 4.0,
            "window_blink_count": 4,
            "decision": "ALERT",
            "reason": "LOW_BLINK_CONFIRMED",
        }

    def test_first_and_repeat_are_persisted(self):
        first = self.client.post(
            "/sessions/1/eye-alert-notifications",
            json=self.payload(),
        )
        repeat = self.client.post(
            "/sessions/1/eye-alert-notifications",
            json=self.payload("eye-runtime-2", "REPEAT"),
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(repeat.status_code, 201)
        self.assertEqual(
            self.db.scalar(select(func.count(EyeAlertNotification.eye_notification_id))),
            2,
        )

    def test_duplicate_runtime_id_returns_existing_row(self):
        first = self.client.post(
            "/sessions/1/eye-alert-notifications",
            json=self.payload(),
        )
        duplicate = self.client.post(
            "/sessions/1/eye-alert-notifications",
            json=self.payload(),
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 201)
        self.assertEqual(
            first.json()["eye_notification_id"],
            duplicate.json()["eye_notification_id"],
        )
        self.assertEqual(
            self.db.scalar(select(func.count(EyeAlertNotification.eye_notification_id))),
            1,
        )

    def test_completed_session_is_rejected(self):
        response = self.client.post(
            "/sessions/2/eye-alert-notifications",
            json=self.payload(),
        )
        self.assertEqual(response.status_code, 409)

    def test_history_returns_persisted_runtime_id(self):
        self.client.post(
            "/sessions/1/eye-alert-notifications",
            json=self.payload(),
        )
        response = self.client.get(
            "/sessions/1/eye-alert-notifications"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(
            response.json()[0]["runtime_notification_id"],
            "eye-runtime-1",
        )


if __name__ == "__main__":
    unittest.main()
