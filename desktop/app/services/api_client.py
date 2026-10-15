import requests

from app.core.config import API_BASE_URL
from app.core.token_store import TokenStore


class APIClient:
    @staticmethod
    def request_password_reset(email: str):
        return APIClient.post("/auth/forgot-password", {"email": email})

    @staticmethod
    def verify_reset_otp(email: str, otp: str):
        return APIClient.post("/auth/verify-reset-otp", {"email": email, "otp": otp})

    @staticmethod
    def reset_password(reset_token: str, new_password: str):
        return APIClient.post(
            "/auth/reset_password",
            {"reset_token": reset_token, "new_password": new_password},
        )

    @staticmethod
    def get_sessions():
        return APIClient.get("/sessions")

    @staticmethod
    def interrupt_session(session_id: int):
        if type(session_id) is not int or session_id <= 0:
            raise ValueError("A valid session_id is required.")
        return APIClient.post(f"/sessions/{session_id}/interrupt")

    @staticmethod
    def _get_headers() -> dict:
        headers = {"Content-Type": "application/json"}
        token = TokenStore.get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def get(endpoint: str):
        return requests.get(
            f"{API_BASE_URL}{endpoint}",
            headers=APIClient._get_headers(),
            timeout=10,
        )

    @staticmethod
    def post(endpoint: str, data: dict | None = None):
        return requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=APIClient._get_headers(),
            timeout=10,
        )

    @staticmethod
    def patch(endpoint: str, data: dict | None = None):
        return requests.patch(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=APIClient._get_headers(),
            timeout=10,
        )

    @staticmethod
    def put(endpoint: str, data: dict | None = None):
        return requests.put(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=APIClient._get_headers(),
            timeout=10,
        )

    @staticmethod
    def delete(endpoint: str):
        return requests.delete(
            f"{API_BASE_URL}{endpoint}",
            headers=APIClient._get_headers(),
            timeout=15,
        )

    @staticmethod
    def login(email: str, password: str):
        return APIClient.post("/auth/login", {"email": email, "password": password})

    @staticmethod
    def get_current_user():
        return APIClient.get("/auth/me")

    @staticmethod
    def update_profile(username: str, full_name: str):
        return APIClient.patch(
            "/users/me",
            {"username": username, "full_name": full_name},
        )

    @staticmethod
    def request_account_deletion():
        return APIClient.post("/users/me/deletion-request")

    @staticmethod
    def cancel_account_deletion():
        return APIClient.delete("/users/me/deletion-request")

    @staticmethod
    def get_settings():
        return APIClient.get("/users/me/settings")

    @staticmethod
    def update_settings(settings: dict):
        allowed_fields = {
            "notifications_enabled",
            "sound_enabled",
            "sound_volume",
            "reminder_interval_minutes",
        }
        if set(settings) != allowed_fields:
            raise ValueError("Invalid settings payload.")
        return APIClient.put("/users/me/settings", settings)

    @staticmethod
    def upload_avatar(path: str):
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        content_type = "image/png" if suffix == "png" else "image/jpeg"
        with open(path, "rb") as avatar_file:
            content = avatar_file.read()
        headers = APIClient._get_headers()
        headers["Content-Type"] = content_type
        return requests.put(
            f"{API_BASE_URL}/users/me/avatar",
            data=content,
            headers=headers,
            timeout=20,
        )

    @staticmethod
    def get_avatar():
        return APIClient.get("/users/me/avatar")

    @staticmethod
    def delete_avatar():
        return APIClient.delete("/users/me/avatar")

    @staticmethod
    def request_register_otp(email: str, username: str, password: str, full_name: str):
        return APIClient.post(
            "/auth/register/request-otp",
            {"email": email, "username": username, "password": password, "full_name": full_name},
        )

    @staticmethod
    def verify_register_otp(email: str, otp: str):
        return APIClient.post("/auth/register/verify-otp", {"email": email, "otp": otp})

    @staticmethod
    def get_cameras():
        return APIClient.get("/cameras")

    @staticmethod
    def get_camera(camera_id: int):
        return APIClient.get(f"/cameras/{camera_id}")

    @staticmethod
    def create_camera(device_id: str, camera_name: str, resolution_width: int, resolution_height: int):
        return APIClient.post(
            "/cameras",
            {
                "device_id": device_id,
                "camera_name": camera_name,
                "resolution_width": resolution_width,
                "resolution_height": resolution_height,
                "reprojection_error": None,
            },
        )

    @staticmethod
    def create_personal_baseline(camera_id: int, measurements: dict):
        allowed_fields = {
            "neck_flexion_baseline", "shoulder_angle", "lateral_tilt_baseline",
            "shoulder_tilt_status", "forward_head_baseline", "neck_rotation_baseline",
            "shoulder_level_difference_baseline", "ipd_baseline", "screen_distance_baseline",
            "camera_frame_width", "camera_frame_height", "camera_scale_x",
            "camera_scale_y", "camera_scale_avg", "camera_card_roll",
            "camera_horizontal_perspective", "camera_vertical_perspective",
            "camera_calibrated_at",
        }
        unknown_fields = set(measurements) - allowed_fields
        if unknown_fields:
            raise ValueError(f"Unknown baseline fields: {unknown_fields}")
        if type(camera_id) is not int or camera_id <= 0:
            raise ValueError("A valid camera_id is required.")
        if not measurements:
            raise ValueError("Calibration measurements are required.")
        return APIClient.post("/personal-baselines", {"camera_id": camera_id, **measurements})

    @staticmethod
    def start_session(camera_id: int, baseline_id: int):
        """Create a RUNNING session; backend validates ownership and camera/baseline match."""
        for label, value in (("camera_id", camera_id), ("baseline_id", baseline_id)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"A valid {label} is required.")
        return APIClient.post(
            "/sessions/start", {"camera_id": camera_id, "baseline_id": baseline_id}
        )

    @staticmethod
    def end_session(session_id: int):
        """Complete a RUNNING or PAUSED session."""
        if type(session_id) is not int or session_id <= 0:
            raise ValueError("A valid session_id is required.")
        return APIClient.post(f"/sessions/{session_id}/end")

    @staticmethod
    def get_sessions():
        return APIClient.get("/sessions")

    @staticmethod
    def get_session(session_id: int):
        return APIClient.get(f"/sessions/{session_id}")

    @staticmethod
    def get_session_summaries():
        return APIClient.get("/summaries")

    @staticmethod
    def create_alert_event(session_id: int, event_type: str, risk_level: str):
        return APIClient.post(
            f"/sessions/{session_id}/alerts",
            {"event_type": event_type, "risk_level": risk_level},
        )

    @staticmethod
    def end_alert_event(event_id: int):
        return APIClient.post(f"/alerts/{event_id}/end")

    @staticmethod
    def get_session_alerts(session_id: int):
        return APIClient.get(f"/sessions/{session_id}/alerts")

    @staticmethod
    def get_alert_event(event_id: int):
        return APIClient.get(f"/alerts/{event_id}")

    @staticmethod
    def pause_session(session_id: int):
        """Pause an existing RUNNING session."""
        if type(session_id) is not int or session_id <= 0:
            raise ValueError("A valid session_id is required.")

        return APIClient.post(
            f"/sessions/{session_id}/pause"
        )

    @staticmethod
    def resume_session(session_id: int):
        """Resume an existing PAUSED session."""
        if type(session_id) is not int or session_id <= 0:
            raise ValueError("A valid session_id is required.")

        return APIClient.post(
            f"/sessions/{session_id}/resume"
        )
