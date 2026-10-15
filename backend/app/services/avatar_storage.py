"""Private Supabase Storage access used only by the authenticated backend."""

import os
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv


BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(BACKEND_ENV_FILE)


class AvatarStorageError(RuntimeError):
    pass


class SupabaseAvatarStorage:
    def __init__(self):
        self.base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.bucket = os.getenv("SUPABASE_AVATAR_BUCKET", "avatars")

    def _configuration(self) -> tuple[str, dict]:
        if not self.base_url or not self.service_key:
            raise AvatarStorageError("Private avatar storage is not configured.")
        return self.base_url, {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }

    def _object_url(self, path: str) -> tuple[str, dict]:
        base_url, headers = self._configuration()
        bucket = quote(self.bucket, safe="")
        object_path = quote(path, safe="/")
        return f"{base_url}/storage/v1/object/{bucket}/{object_path}", headers

    def upload(self, path: str, content: bytes) -> None:
        url, headers = self._object_url(path)
        try:
            response = requests.post(
                url,
                data=content,
                headers={**headers, "Content-Type": "image/webp", "x-upsert": "false"},
                timeout=20,
            )
        except requests.RequestException as exc:
            raise AvatarStorageError("Avatar storage is unavailable.") from exc
        if not response.ok:
            raise AvatarStorageError("Avatar upload was rejected by private storage.")

    def download(self, path: str) -> bytes:
        url, headers = self._object_url(path)
        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException as exc:
            raise AvatarStorageError("Avatar storage is unavailable.") from exc
        if not response.ok:
            raise AvatarStorageError("Avatar could not be loaded from private storage.")
        return response.content

    def delete(self, path: str) -> None:
        base_url, headers = self._configuration()
        bucket = quote(self.bucket, safe="")
        try:
            response = requests.delete(
                f"{base_url}/storage/v1/object/{bucket}",
                json={"prefixes": [path]},
                headers={**headers, "Content-Type": "application/json"},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise AvatarStorageError("Avatar storage is unavailable.") from exc
        if not response.ok:
            raise AvatarStorageError("Avatar could not be removed from private storage.")


def get_avatar_storage() -> SupabaseAvatarStorage:
    return SupabaseAvatarStorage()
