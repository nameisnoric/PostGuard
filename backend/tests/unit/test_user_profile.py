"""Authenticated profile update API tests."""

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
from app.routers.auth import get_current_user
from app.routers.users import router


class UserProfileTests(unittest.TestCase):
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
            email="profile@ku.th",
            username="current-user",
            full_name="Current User",
            password_hash="test",
        )
        self.other_user = User(
            id=2,
            email="other@ku.th",
            username="already-used",
            full_name="Other User",
            password_hash="test",
        )
        self.db.add_all((self.user, self.other_user))
        self.db.commit()

        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_update_profile_persists_username_and_full_name(self):
        result = self.client.patch(
            "/users/me",
            json={"username": "new-user", "full_name": "New User"},
        )

        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["username"], "new-user")
        self.assertEqual(result.json()["full_name"], "New User")
        self.db.refresh(self.user)
        self.assertEqual(self.user.username, "new-user")
        self.assertEqual(self.user.full_name, "New User")

    def test_update_profile_rejects_another_users_username(self):
        result = self.client.patch(
            "/users/me",
            json={"username": "already-used", "full_name": "New User"},
        )

        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(result.json()["detail"], "Username is already in use.")
        self.db.refresh(self.user)
        self.assertEqual(self.user.username, "current-user")
        self.assertEqual(self.user.full_name, "Current User")

    def test_update_profile_rejects_blank_or_oversized_values(self):
        invalid_profiles = (
            {"username": "   ", "full_name": "Valid Name"},
            {"username": "valid", "full_name": "   "},
            {"username": "u" * 101, "full_name": "Valid Name"},
            {"username": "valid", "full_name": "n" * 151},
        )
        for profile in invalid_profiles:
            with self.subTest(profile=profile):
                result = self.client.patch("/users/me", json=profile)
                self.assertEqual(result.status_code, 422, result.text)


if __name__ == "__main__":
    unittest.main()
