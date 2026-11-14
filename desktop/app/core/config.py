import os


API_BASE_URL = os.getenv(
    "POSTGUARD_API_BASE_URL",
    "https://postguard-api-k8oh.onrender.com",
).rstrip("/")
