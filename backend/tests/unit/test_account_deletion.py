"""Account deletion request, recovery and permanent purge tests."""

import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.models.user import User
from app.routers.auth import get_authenticated_user, get_current_user
from app.routers.users import router
from app.services.account_deletion import purge_due_accounts
from app.services.avatar_storage import AvatarStorageError


class FakeStorage:
    def __init__(self, fail=False):
        self.deleted = []
        self.fail = fail

    def delete(self, path):
        if self.fail:
            raise AvatarStorageError("unavailable")
        self.deleted.append(path)


class AccountDeletionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(
            email="delete@ku.th",
            username="delete-user",
            full_name="Delete User",
            password_hash="test",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.app = FastAPI()
        self.app.include_router(router)

        @self.app.get("/protected")
        def protected(user: User = Depends(get_current_user)):
            return {"id": user.id}

        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_authenticated_user] = lambda: self.user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_request_sets_exact_recovery_window_and_cancel_restores_access(self):
        result = self.client.post("/users/me/deletion-request")

        self.assertEqual(result.status_code, 200, result.text)
        payload = result.json()
        self.assertEqual(payload["account_status"], "PENDING_DELETION")
        requested = datetime.fromisoformat(payload["deletion_requested_at"])
        scheduled = datetime.fromisoformat(payload["deletion_scheduled_for"])
        self.assertEqual(scheduled - requested, timedelta(days=14))

        self.app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get("/protected").status_code, 403)

        recovered = self.client.delete("/users/me/deletion-request")
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()["account_status"], "ACTIVE")
        self.assertIsNone(recovered.json()["deletion_scheduled_for"])
        self.assertEqual(self.client.get("/protected").status_code, 200)

    def test_recovery_is_rejected_after_deadline(self):
        self.user.account_status = "PENDING_DELETION"
        self.user.deletion_scheduled_for = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.commit()

        result = self.client.delete("/users/me/deletion-request")

        self.assertEqual(result.status_code, 410, result.text)
        self.assertEqual(self.user.account_status, "PENDING_DELETION")

    def test_purge_removes_due_user_and_private_avatar(self):
        self.user.account_status = "PENDING_DELETION"
        self.user.deletion_scheduled_for = datetime.now(timezone.utc) - timedelta(days=1)
        self.user.avatar_path = f"users/{self.user.id}/avatar.webp"
        self.db.commit()
        storage = FakeStorage()

        result = purge_due_accounts(self.db, storage)

        self.assertEqual(result["purged_ids"], [self.user.id])
        self.assertEqual(result["deferred_ids"], [])
        self.assertEqual(storage.deleted, [self.user.avatar_path])
        self.assertIsNone(self.db.get(User, self.user.id))

    def test_purge_defers_database_delete_when_avatar_cleanup_fails(self):
        self.user.account_status = "PENDING_DELETION"
        self.user.deletion_scheduled_for = datetime.now(timezone.utc) - timedelta(days=1)
        self.user.avatar_path = f"users/{self.user.id}/avatar.webp"
        self.db.commit()

        result = purge_due_accounts(self.db, FakeStorage(fail=True))

        self.assertEqual(result["deferred_ids"], [self.user.id])
        self.assertIsNotNone(self.db.get(User, self.user.id))


if __name__ == "__main__":
    unittest.main()
