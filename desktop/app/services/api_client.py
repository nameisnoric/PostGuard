import requests

from app.core.config import API_BASE_URL
from app.core.token_store import TokenStore

class APIClient:

    @staticmethod
    def _get_headers() -> dict:
        headers = {
            "Content-Type": "application/json"
        }

        token = TokenStore.get_token()

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    @staticmethod
    def get(endpoint: str):
        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            headers=APIClient._get_headers(),
            timeout=10
        )

        return response

    @staticmethod
    def post(endpoint: str, data: dict | None = None):
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=APIClient._get_headers(),
            timeout=10
        )

        return response

    @staticmethod
    def login(email: str, password: str):
        response = APIClient.post(
            "/auth/login",
            {
                "email": email,
                "password": password
            }
        )

        return response

    @staticmethod
    def get_current_user():
        response = APIClient.get(
            "/auth/me"
        )

        return response
    
    @staticmethod
    def request_register_otp(
        email: str,
        username: str,
        password: str,
        full_name: str
    ):
        return APIClient.post(
            "/auth/register/request-otp",
            {
                "email": email,
                "username": username,
                "password": password,
                "full_name": full_name
            }
        )

    @staticmethod
    def verify_register_otp(
        email: str,
        otp: str
    ):
        return APIClient.post(
            "/auth/register/verify-otp",
            {
                "email": email,
                "otp": otp
            }
        )