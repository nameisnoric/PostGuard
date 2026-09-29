import httpx

class APIClient:
    def __init__(self) -> None:
        self.base_url = "http://127.0.0.1:8000"

#Login API
    def login(
        self,
        email: str,
        password: str
    ) -> str:
        response = httpx.post(
            f"{self.base_url}/auth/login",
            json={
                "email": email,
                "password": password
            },
            timeout=10.0
        )

        response.raise_for_status()

        data = response.json()

        return data["access_token"]