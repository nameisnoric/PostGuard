"""Privacy Notice consent API and persistence tests."""

import os
import unittest

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.privacy import CURRENT_PRIVACY_NOTICE_VERSION
from app.database.database import Base, get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.privacy import router


class PrivacyConsentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(
            email="privacy@ku.th",
            username="privacy-user",
            password_hash="test",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_accept_and_read_current_consent(self):
        initial = self.client.get("/users/me/privacy-consent")
        self.assertEqual(initial.status_code, 200, initial.text)
        self.assertFalse(initial.json()["has_current_consent"])

        accepted = self.client.put(
            "/users/me/privacy-consent",
            json={"notice_version": CURRENT_PRIVACY_NOTICE_VERSION},
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertTrue(accepted.json()["has_current_consent"])
        self.assertEqual(
            accepted.json()["accepted_version"],
            CURRENT_PRIVACY_NOTICE_VERSION,
        )
        self.assertIsNotNone(accepted.json()["accepted_at"])
        self.assertIsNone(accepted.json()["withdrawn_at"])

    def test_old_notice_version_is_rejected(self):
        response = self.client.put(
            "/users/me/privacy-consent",
            json={"notice_version": "old-version"},
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertFalse(response.json().get("has_current_consent", False))

    def test_withdrawal_is_timestamped_and_can_be_accepted_again(self):
        self.client.put(
            "/users/me/privacy-consent",
            json={"notice_version": CURRENT_PRIVACY_NOTICE_VERSION},
        )
        withdrawn = self.client.delete("/users/me/privacy-consent")

        self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertFalse(withdrawn.json()["has_current_consent"])
        self.assertIsNotNone(withdrawn.json()["accepted_at"])
        self.assertIsNotNone(withdrawn.json()["withdrawn_at"])

        repeated = self.client.delete("/users/me/privacy-consent")
        self.assertEqual(
            repeated.json()["withdrawn_at"],
            withdrawn.json()["withdrawn_at"],
        )

        accepted_again = self.client.put(
            "/users/me/privacy-consent",
            json={"notice_version": CURRENT_PRIVACY_NOTICE_VERSION},
        )
        self.assertTrue(accepted_again.json()["has_current_consent"])
        self.assertIsNone(accepted_again.json()["withdrawn_at"])


if __name__ == "__main__":
    unittest.main()
