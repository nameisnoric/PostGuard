"""Authenticated password-change and token-revocation tests."""

import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password, verify_password
from app.database.database import Base, get_db
from app.models.user import User
from app.routers.auth import get_current_user, router as auth_router
from app.routers.users import router as users_router


class ChangePasswordTests(unittest.TestCase):
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
            email="student@ku.th",
            username="student",
            password_hash=hash_password("OldPass123!"),
            auth_version=0,
        )
        self.db.add(self.user)
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(auth_router)
        self.app.include_router(users_router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_change_password_rehashes_notifies_and_revokes_old_token(self):
        old_token = create_access_token(self.user.id, self.user.auth_version)
        with patch(
            "app.routers.users.send_password_changed_notice"
        ) as notify:
            result = self.client.put(
                "/users/me/password",
                json={
                    "current_password": "OldPass123!",
                    "new_password": "NewPass456!",
                },
            )

        self.assertEqual(result.status_code, 200, result.text)
        self.db.refresh(self.user)
        self.assertEqual(self.user.auth_version, 1)
        self.assertFalse(verify_password("OldPass123!", self.user.password_hash))
        self.assertTrue(verify_password("NewPass456!", self.user.password_hash))
        notify.assert_called_once_with("student@ku.th")
        revoked = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        self.assertEqual(revoked.status_code, 401)

    def test_wrong_current_same_and_weak_password_are_rejected(self):
        cases = (
            ({"current_password": "WrongPass123!", "new_password": "NewPass456!"}, 400),
            ({"current_password": "OldPass123!", "new_password": "OldPass123!"}, 400),
            ({"current_password": "OldPass123!", "new_password": "weak"}, 422),
        )
        for payload, expected in cases:
            with self.subTest(payload=payload):
                result = self.client.put("/users/me/password", json=payload)
                self.assertEqual(result.status_code, expected, result.text)
        self.db.refresh(self.user)
        self.assertEqual(self.user.auth_version, 0)
        self.assertTrue(verify_password("OldPass123!", self.user.password_hash))

    def test_email_failure_does_not_undo_password_change(self):
        with patch(
            "app.routers.users.send_password_changed_notice",
            side_effect=RuntimeError("email unavailable"),
        ):
            result = self.client.put(
                "/users/me/password",
                json={
                    "current_password": "OldPass123!",
                    "new_password": "NewPass456!",
                },
            )
        self.assertEqual(result.status_code, 200, result.text)
        self.db.refresh(self.user)
        self.assertTrue(verify_password("NewPass456!", self.user.password_hash))


if __name__ == "__main__":
    unittest.main()
