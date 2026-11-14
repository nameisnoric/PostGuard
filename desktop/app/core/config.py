import os


API_BASE_URL = os.getenv(
    "POSTGUARD_API_BASE_URL",
    "http://127.0.0.1:8001",
).rstrip("/")
