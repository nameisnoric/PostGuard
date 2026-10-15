"""Private avatar API tests with an in-memory database and fake storage."""

import os
import unittest
from io import BytesIO

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.users import get_avatar_storage, router


class FakeAvatarStorage:
    def __init__(self):
        self.objects = {}
        self.deleted = []

    def upload(self, path, content):
        self.objects[path] = content

    def download(self, path):
        return self.objects[path]

    def delete(self, path):
        self.deleted.append(path)
        self.objects.pop(path, None)


def image_bytes(size=(640, 480), image_format="JPEG"):
    output = BytesIO()
    Image.new("RGB", size, (40, 90, 140)).save(output, format=image_format)
    return output.getvalue()


class UserAvatarTests(unittest.TestCase):
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
            email="avatar@example.invalid",
            username="avatar",
            password_hash="test",
        )
        self.db.add(self.user)
        self.db.commit()
        self.storage = FakeAvatarStorage()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_avatar_storage] = lambda: self.storage
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_upload_normalizes_and_private_endpoint_reads_owner_avatar(self):
        result = self.client.put(
            "/users/me/avatar",
            content=image_bytes(),
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(result.status_code, 200, result.text)
        path = result.json()["avatar_path"]
        self.assertTrue(path.startswith("users/1/"))
        self.assertTrue(path.endswith(".webp"))
        stored = self.storage.objects[path]
        with Image.open(BytesIO(stored)) as avatar:
            self.assertEqual(avatar.format, "WEBP")
            self.assertEqual(avatar.size, (400, 400))
        downloaded = self.client.get("/users/me/avatar")
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.headers["content-type"], "image/webp")
        self.assertTrue(downloaded.headers["cache-control"].startswith("private"))

    def test_replacement_deletes_previous_private_object(self):
        self.user.avatar_path = "users/1/old.webp"
        self.storage.objects[self.user.avatar_path] = b"old"
        self.db.commit()
        result = self.client.put(
            "/users/me/avatar",
            content=image_bytes(image_format="PNG"),
            headers={"Content-Type": "image/png"},
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.storage.deleted, ["users/1/old.webp"])

    def test_invalid_uploads_are_rejected_before_storage(self):
        wrong_type = self.client.put(
            "/users/me/avatar",
            content=b"not an image",
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(wrong_type.status_code, 415)
        invalid_image = self.client.put(
            "/users/me/avatar",
            content=b"not an image",
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(invalid_image.status_code, 422)
        self.assertEqual(self.storage.objects, {})

    def test_delete_removes_database_reference_and_private_object(self):
        self.user.avatar_path = "users/1/avatar.webp"
        self.storage.objects[self.user.avatar_path] = b"avatar"
        self.db.commit()
        result = self.client.delete("/users/me/avatar")
        self.assertEqual(result.status_code, 204)
        self.db.refresh(self.user)
        self.assertIsNone(self.user.avatar_path)
        self.assertEqual(self.storage.deleted, ["users/1/avatar.webp"])
        self.assertEqual(self.client.get("/users/me/avatar").status_code, 404)


if __name__ == "__main__":
    unittest.main()
