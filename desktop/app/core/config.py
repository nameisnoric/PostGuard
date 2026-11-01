"""Desktop runtime configuration."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def runtime_directory() -> Path:
    """Return the folder containing the app or packaged executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def normalize_api_base_url(value: str | None) -> str:
    url = (value or "http://127.0.0.1:8001").strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ValueError("POSTGUARD_API_BASE_URL must start with http:// or https://")
    return url


load_dotenv(runtime_directory() / ".env", override=False)

API_BASE_URL = normalize_api_base_url(os.getenv("POSTGUARD_API_BASE_URL"))
