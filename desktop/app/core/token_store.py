import threading
import time


class TokenStore:
    _access_token: str | None = None
    _refresh_token: str | None = None
    _access_expires_at: float | None = None
    _lock = threading.RLock()

    @classmethod
    def set_token(cls, token: str) -> None:
        with cls._lock:
            cls._access_token = token
            cls._refresh_token = None
            cls._access_expires_at = None

    @classmethod
    def set_session(
        cls,
        access_token: str,
        refresh_token: str,
        expires_in: int = 30 * 60,
    ) -> None:
        with cls._lock:
            cls._access_token = access_token
            cls._refresh_token = refresh_token
            cls._access_expires_at = time.monotonic() + max(0, expires_in)

    @classmethod
    def get_token(cls) -> str | None:
        with cls._lock:
            return cls._access_token

    @classmethod
    def get_refresh_token(cls) -> str | None:
        with cls._lock:
            return cls._refresh_token

    @classmethod
    def should_refresh(cls, margin_seconds: int = 60) -> bool:
        with cls._lock:
            return bool(
                cls._refresh_token
                and cls._access_expires_at is not None
                and time.monotonic() >= cls._access_expires_at - margin_seconds
            )

    @classmethod
    def clear_token(cls) -> None:
        with cls._lock:
            cls._access_token = None
            cls._refresh_token = None
            cls._access_expires_at = None
