"""Per-user settings API tests."""

import os
import unittest

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.routers.auth import get_current_user
from app.routers.settings import router


class UserSettingsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(
            email="settings@ku.th",
            username="settings-user",
            password_hash="test",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_get_creates_default_settings_for_current_user(self):
        result = self.client.get("/users/me/settings")

        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["user_id"], self.user.id)
        self.assertTrue(result.json()["notifications_enabled"])
        self.assertTrue(result.json()["sound_enabled"])
        self.assertEqual(result.json()["sound_volume"], 70)
        self.assertEqual(result.json()["reminder_interval_minutes"], 5)

    def test_update_persists_settings(self):
        payload = {
            "notifications_enabled": True,
            "sound_enabled": False,
            "sound_volume": 35,
            "reminder_interval_minutes": 15,
        }
        result = self.client.put("/users/me/settings", json=payload)

        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(
            {key: result.json()[key] for key in payload},
            payload,
        )
        stored = self.db.get(UserSettings, self.user.id)
        self.assertEqual(stored.sound_volume, 35)
        self.assertEqual(stored.reminder_interval_minutes, 15)

    def test_invalid_volume_and_interval_are_rejected(self):
        for volume, interval in ((-1, 5), (101, 5), (50, 0), (50, 61)):
            with self.subTest(volume=volume, interval=interval):
                result = self.client.put("/users/me/settings", json={
                    "notifications_enabled": True,
                    "sound_enabled": True,
                    "sound_volume": volume,
                    "reminder_interval_minutes": interval,
                })
                self.assertEqual(result.status_code, 422, result.text)


if __name__ == "__main__":
    unittest.main()
