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
        
    @staticmethod
    def get_cameras():
        return APIClient.get(
            "/cameras"
        )


    @staticmethod
    def get_camera(camera_id: int):
        return APIClient.get(
            f"/cameras/{camera_id}"
        )
        
    
    @staticmethod
    def create_camera(
        device_id: str,
        camera_name: str,
        resolution_width: int,
        resolution_height: int
    ):
        return APIClient.post(
            "/cameras",
            {
                "device_id": device_id,
                "camera_name": camera_name,
                "resolution_width": resolution_width,
                "resolution_height": resolution_height,
                "reprojection_error": None
            }
        )
    
    @staticmethod
    def create_personal_baseline(
        camera_id: int,
        measurements: dict
    ):
        allowed_fields = {
            "neck_flexion_baseline",
            "shoulder_angle",
            "lateral_tilt_baseline",
            "shoulder_tilt_status",
            "forward_head_baseline",
            "neck_rotation_baseline",
            "shoulder_level_difference_baseline",
            "ipd_baseline",
            "screen_distance_baseline"
        }

        unknown_fields = (
            set(measurements) - allowed_fields
        )

        if unknown_fields:
            raise ValueError(
                f"Unknown baseline fields: {unknown_fields}"
            )

        if not isinstance(camera_id, int) or camera_id <= 0:
            raise ValueError(
                "A valid camera_id is required."
            )

        if not measurements:
            raise ValueError(
                "Calibration measurements are required."
            )

        data = {
            "camera_id": camera_id,
            **measurements
        }

        return APIClient.post(
            "/personal-baselines",
            data
        )
