import threading

import requests

from app.core.config import API_BASE_URL
from app.core.token_store import TokenStore


class APIClient:
    # ========================================================
    # TOKEN REFRESH
    # ========================================================

    # Prevent multiple requests from refreshing the same
    # expired access token at the same time.
    _refresh_lock = threading.Lock()

    # These endpoints must never attempt automatic refresh.
    #
    # Example:
    # Login returns 401 because password is wrong.
    # That 401 must be returned directly to Login UI instead
    # of trying /auth/refresh.
    _public_auth_endpoints = {
        "/auth/login",
        "/auth/forgot-password",
        "/auth/verify-reset-otp",
        "/auth/reset_password",
        "/auth/register/request-otp",
        "/auth/register/verify-otp",
        "/auth/refresh",
    }

    # ========================================================
    # AUTH / PASSWORD
    # ========================================================

    @staticmethod
    def request_password_reset(email: str):
        return APIClient.post(
            "/auth/forgot-password",
            {"email": email},
        )

    @staticmethod
    def verify_reset_otp(
        email: str,
        otp: str,
    ):
        return APIClient.post(
            "/auth/verify-reset-otp",
            {
                "email": email,
                "otp": otp,
            },
        )

    @staticmethod
    def reset_password(
        reset_token: str,
        new_password: str,
    ):
        return APIClient.post(
            "/auth/reset_password",
            {
                "reset_token": reset_token,
                "new_password": new_password,
            },
        )

    # ========================================================
    # HEADERS
    # ========================================================

    @staticmethod
    def _get_headers() -> dict:
        headers = {
            "Content-Type": "application/json",
        }

        token = TokenStore.get_token()

        if token:
            headers["Authorization"] = (
                f"Bearer {token}"
            )

        return headers

    # ========================================================
    # REFRESH ACCESS TOKEN
    # ========================================================

    @staticmethod
    def _refresh_access_token(
        failed_token: str | None = None,
    ) -> bool:
        """
        Refresh the current access token.

        failed_token is supplied when a request already received
        HTTP 401.

        If another thread already refreshed the token while this
        request was waiting for the lock, do not refresh again.
        """

        refresh_token = (
            TokenStore.get_refresh_token()
        )

        if not refresh_token:
            return False

        with APIClient._refresh_lock:
            current_token = (
                TokenStore.get_token()
            )

            # Another request may already have replaced the
            # expired token while we waited for the lock.
            if (
                failed_token is not None
                and current_token != failed_token
            ):
                return bool(current_token)

            # Proactive refresh is only required when the
            # TokenStore says the token is close to expiry.
            if (
                failed_token is None
                and not TokenStore.should_refresh()
            ):
                return bool(current_token)

            response = requests.post(
                f"{API_BASE_URL}/auth/refresh",
                json={
                    "refresh_token":
                        TokenStore.get_refresh_token(),
                },
                headers={
                    "Content-Type":
                        "application/json",
                },
                timeout=10,
            )

            if response.status_code != 200:
                # A rejected refresh token means the session is
                # no longer recoverable.
                if response.status_code == 401:
                    TokenStore.clear_token()

                return False

            try:
                data = response.json()

                access_token = (
                    data["access_token"]
                )

                new_refresh_token = (
                    data["refresh_token"]
                )

                expires_in = int(
                    data.get(
                        "expires_in",
                        30 * 60,
                    )
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                TokenStore.clear_token()
                return False

            if (
                not access_token
                or not new_refresh_token
            ):
                TokenStore.clear_token()
                return False

            TokenStore.set_session(
                access_token,
                new_refresh_token,
                expires_in,
            )

            return True

    # ========================================================
    # CENTRAL REQUEST
    # ========================================================

    @staticmethod
    def _request(
        method: str,
        endpoint: str,
        **kwargs,
    ):
        """
        Central request handler.

        Flow:

            request
                ↓
        Access token still valid?
                ↓
               yes
                ↓
             continue

        Near expiry:
            refresh proactively

        HTTP 401:
            refresh token
                ↓
            retry exactly once

        Public authentication endpoints never use refresh.
        """

        token = TokenStore.get_token()

        authenticated = bool(
            token
            and endpoint
            not in APIClient._public_auth_endpoints
        )

        # ----------------------------------------------------
        # Proactive refresh
        # ----------------------------------------------------

        if (
            authenticated
            and TokenStore.should_refresh()
        ):
            try:
                APIClient._refresh_access_token()

            except requests.RequestException:
                # Network problem while refreshing should not
                # immediately destroy the current credentials.
                #
                # Let the original API call continue.
                pass

        token = TokenStore.get_token()

        # ----------------------------------------------------
        # Headers
        # ----------------------------------------------------

        custom_headers = (
            kwargs.pop("headers", None)
        )

        headers = APIClient._get_headers()

        if custom_headers:
            headers.update(custom_headers)

        kwargs["headers"] = headers

        # ----------------------------------------------------
        # First request
        # ----------------------------------------------------

        response = getattr(
            requests,
            method,
        )(
            f"{API_BASE_URL}{endpoint}",
            **kwargs,
        )

        # Success or non-authentication failure.
        if (
            response.status_code != 401
            or not authenticated
        ):
            return response

        # ----------------------------------------------------
        # 401 -> Refresh -> Retry once
        # ----------------------------------------------------

        try:
            refreshed = (
                APIClient._refresh_access_token(
                    failed_token=token,
                )
            )

        except requests.RequestException:
            refreshed = False

        if not refreshed:
            return response

        # Token has changed. Rebuild Authorization header.
        retry_headers = (
            APIClient._get_headers()
        )

        if custom_headers:
            retry_headers.update(
                custom_headers
            )

        kwargs["headers"] = retry_headers

        return getattr(
            requests,
            method,
        )(
            f"{API_BASE_URL}{endpoint}",
            **kwargs,
        )

    # ========================================================
    # HTTP METHODS
    # ========================================================

    @staticmethod
    def get(
        endpoint: str,
    ):
        return APIClient._request(
            "get",
            endpoint,
            timeout=10,
        )

    @staticmethod
    def post(
        endpoint: str,
        data: dict | None = None,
    ):
        return APIClient._request(
            "post",
            endpoint,
            json=data,
            timeout=10,
        )

    @staticmethod
    def patch(
        endpoint: str,
        data: dict | None = None,
    ):
        return APIClient._request(
            "patch",
            endpoint,
            json=data,
            timeout=10,
        )

    @staticmethod
    def put(
        endpoint: str,
        data: dict | None = None,
    ):
        return APIClient._request(
            "put",
            endpoint,
            json=data,
            timeout=10,
        )

    @staticmethod
    def delete(
        endpoint: str,
    ):
        return APIClient._request(
            "delete",
            endpoint,
            timeout=15,
        )

    # ========================================================
    # LOGIN / USER
    # ========================================================

    @staticmethod
    def login(
        email: str,
        password: str,
    ):
        return APIClient.post(
            "/auth/login",
            {
                "email": email,
                "password": password,
            },
        )

    @staticmethod
    def get_current_user():
        return APIClient.get(
            "/auth/me"
        )

    @staticmethod
    def update_profile(
        username: str,
        full_name: str,
    ):
        return APIClient.patch(
            "/users/me",
            {
                "username": username,
                "full_name": full_name,
            },
        )

    # ========================================================
    # ACCOUNT
    # ========================================================

    @staticmethod
    def request_account_deletion():
        return APIClient.post(
            "/users/me/deletion-request"
        )

    @staticmethod
    def cancel_account_deletion():
        return APIClient.delete(
            "/users/me/deletion-request"
        )

    # ========================================================
    # SETTINGS
    # ========================================================

    @staticmethod
    def get_settings():
        return APIClient.get(
            "/users/me/settings"
        )

    @staticmethod
    def update_settings(
        settings: dict,
    ):
        allowed_fields = {
            "notifications_enabled",
            "sound_enabled",
            "sound_volume",
            "reminder_interval_minutes",
        }

        if set(settings) != allowed_fields:
            raise ValueError(
                "Invalid settings payload."
            )

        return APIClient.put(
            "/users/me/settings",
            settings,
        )

    # ========================================================
    # PRIVACY CONSENT
    # ========================================================

    @staticmethod
    def get_privacy_consent():
        return APIClient.get(
            "/users/me/privacy-consent"
        )

    @staticmethod
    def accept_privacy_consent(
        notice_version: str,
    ):
        if not notice_version:
            raise ValueError(
                "Privacy Notice version is required."
            )

        return APIClient.put(
            "/users/me/privacy-consent",
            {
                "notice_version":
                    notice_version,
            },
        )

    @staticmethod
    def withdraw_privacy_consent():
        return APIClient.delete(
            "/users/me/privacy-consent"
        )

    # ========================================================
    # AVATAR
    # ========================================================

    @staticmethod
    def upload_avatar(
        path: str,
    ):
        suffix = (
            path.rsplit(".", 1)[-1].lower()
            if "." in path
            else ""
        )

        content_type = (
            "image/png"
            if suffix == "png"
            else "image/jpeg"
        )

        with open(
            path,
            "rb",
        ) as avatar_file:
            content = avatar_file.read()

        # Use central request handler as well so an avatar
        # upload can also recover from an expired token.
        return APIClient._request(
            "put",
            "/users/me/avatar",
            data=content,
            headers={
                "Content-Type":
                    content_type,
            },
            timeout=20,
        )

    @staticmethod
    def get_avatar():
        return APIClient.get(
            "/users/me/avatar"
        )

    @staticmethod
    def delete_avatar():
        return APIClient.delete(
            "/users/me/avatar"
        )

    # ========================================================
    # REGISTER
    # ========================================================

    @staticmethod
    def request_register_otp(
        email: str,
        username: str,
        password: str,
        full_name: str,
    ):
        return APIClient.post(
            "/auth/register/request-otp",
            {
                "email": email,
                "username": username,
                "password": password,
                "full_name": full_name,
            },
        )

    @staticmethod
    def verify_register_otp(
        email: str,
        otp: str,
    ):
        return APIClient.post(
            "/auth/register/verify-otp",
            {
                "email": email,
                "otp": otp,
            },
        )

    # ========================================================
    # CAMERAS
    # ========================================================

    @staticmethod
    def get_cameras():
        return APIClient.get(
            "/cameras"
        )

    @staticmethod
    def get_camera(
        camera_id: int,
    ):
        return APIClient.get(
            f"/cameras/{camera_id}"
        )

    @staticmethod
    def create_camera(
        device_id: str,
        camera_name: str,
        resolution_width: int,
        resolution_height: int,
    ):
        return APIClient.post(
            "/cameras",
            {
                "device_id": device_id,
                "camera_name": camera_name,
                "resolution_width":
                    resolution_width,
                "resolution_height":
                    resolution_height,
                "reprojection_error": None,
            },
        )

    # ========================================================
    # PERSONAL BASELINE
    # ========================================================

    @staticmethod
    def create_personal_baseline(
        camera_id: int,
        measurements: dict,
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
            "screen_distance_baseline",
            "camera_frame_width",
            "camera_frame_height",
            "camera_scale_x",
            "camera_scale_y",
            "camera_scale_avg",
            "camera_card_roll",
            "camera_horizontal_perspective",
            "camera_vertical_perspective",
            "camera_calibrated_at",
            "baseline_status",
            "confirmation_status",
            "baseline_sample_count",
            "baseline_duration_seconds",
            "baseline_valid_ratio",
            "shoulder_tilt_sd",
            "neck_lateral_tilt_sd",
            "neck_flexion_sd",
            "eye_distance_sd",
        }

        unknown_fields = (
            set(measurements)
            -
            allowed_fields
        )

        if unknown_fields:
            raise ValueError(
                "Unknown baseline fields: "
                f"{unknown_fields}"
            )

        if (
            type(camera_id) is not int
            or camera_id <= 0
        ):
            raise ValueError(
                "A valid camera_id is required."
            )

        if not measurements:
            raise ValueError(
                "Calibration measurements are required."
            )

        return APIClient.post(
            "/personal-baselines",
            {
                "camera_id": camera_id,
                **measurements,
            },
        )

    # ========================================================
    # SESSION
    # ========================================================

    @staticmethod
    def start_session(
        camera_id: int,
        baseline_id: int,
    ):
        """
        Create a RUNNING session.

        Backend validates ownership and camera/baseline match.
        """

        for label, value in (
            ("camera_id", camera_id),
            ("baseline_id", baseline_id),
        ):
            if (
                type(value) is not int
                or value <= 0
            ):
                raise ValueError(
                    f"A valid {label} is required."
                )

        return APIClient.post(
            "/sessions/start",
            {
                "camera_id": camera_id,
                "baseline_id": baseline_id,
            },
        )

    @staticmethod
    def end_session(
        session_id: int,
    ):
        """
        Complete a RUNNING or PAUSED session.
        """

        if (
            type(session_id) is not int
            or session_id <= 0
        ):
            raise ValueError(
                "A valid session_id is required."
            )

        return APIClient.post(
            f"/sessions/{session_id}/end"
        )

    @staticmethod
    def get_sessions():
        return APIClient.get(
            "/sessions"
        )

    @staticmethod
    def get_session(
        session_id: int,
    ):
        return APIClient.get(
            f"/sessions/{session_id}"
        )

    @staticmethod
    def interrupt_session(
        session_id: int,
    ):
        if (
            type(session_id) is not int
            or session_id <= 0
        ):
            raise ValueError(
                "A valid session_id is required."
            )

        return APIClient.post(
            f"/sessions/{session_id}/interrupt"
        )

    @staticmethod
    def pause_session(
        session_id: int,
    ):
        """
        Pause an existing RUNNING session.
        """

        if (
            type(session_id) is not int
            or session_id <= 0
        ):
            raise ValueError(
                "A valid session_id is required."
            )

        return APIClient.post(
            f"/sessions/{session_id}/pause"
        )

    @staticmethod
    def resume_session(
        session_id: int,
    ):
        """
        Resume an existing PAUSED session.
        """

        if (
            type(session_id) is not int
            or session_id <= 0
        ):
            raise ValueError(
                "A valid session_id is required."
            )

        return APIClient.post(
            f"/sessions/{session_id}/resume"
        )

    # ========================================================
    # SESSION SUMMARY
    # ========================================================

    @staticmethod
    def get_session_summaries():
        return APIClient.get(
            "/summaries"
        )

    # ========================================================
    # LEGACY ALERT EVENT API
    # ========================================================

    @staticmethod
    def create_alert_event(
        session_id: int,
        event_type: str,
        risk_level: str,
    ):
        return APIClient.post(
            f"/sessions/{session_id}/alerts",
            {
                "event_type": event_type,
                "risk_level": risk_level,
            },
        )

    @staticmethod
    def end_alert_event(
        event_id: int,
    ):
        return APIClient.post(
            f"/alerts/{event_id}/end"
        )

    @staticmethod
    def get_session_alerts(
        session_id: int,
    ):
        return APIClient.get(
            f"/sessions/{session_id}/alerts"
        )

    @staticmethod
    def get_alert_event(
        event_id: int,
    ):
        return APIClient.get(
            f"/alerts/{event_id}"
        )

    # ========================================================
    # VALIDATED RISK PERSISTENCE
    #
    # IMPORTANT:
    # These signatures intentionally remain compatible with
    # the validated integration branch.
    #
    # Do NOT replace them with the feature/detection versions
    # unless RiskPersistenceService is migrated at the same
    # time and revalidated.
    # ========================================================

    @staticmethod
    def create_risk_event(
        session_id: int,
        runtime_event_id: str,
        risk_level: str,
        active_factors: list[str],
        evidence_groups: list[str],
    ):
        return APIClient.post(
            f"/sessions/{session_id}/risk-events",
            {
                "runtime_event_id":
                    runtime_event_id,
                "risk_level":
                    risk_level,
                "active_factors":
                    active_factors,
                "evidence_groups":
                    evidence_groups,
            },
        )

    @staticmethod
    def update_risk_event(
        session_id: int,
        runtime_event_id: str,
        event_action: str,
        risk_level: str,
        active_factors: list[str],
        evidence_groups: list[str],
    ):
        return APIClient.patch(
            (
                f"/sessions/{session_id}"
                f"/risk-events/{runtime_event_id}"
            ),
            {
                "event_action":
                    event_action,
                "risk_level":
                    risk_level,
                "active_factors":
                    active_factors,
                "evidence_groups":
                    evidence_groups,
            },
        )

    @staticmethod
    def resolve_risk_event(
        session_id: int,
        runtime_event_id: str,
        resolved_reason: str,
    ):
        return APIClient.post(
            (
                f"/sessions/{session_id}"
                f"/risk-events/{runtime_event_id}"
                "/resolve"
            ),
            {
                "resolved_reason":
                    resolved_reason,
            },
        )

    @staticmethod
    def create_alert_notification(
        session_id: int,
        runtime_event_id: str,
        alert_type: str,
        risk_level: str | None,
        decision: str,
        reason: str | None,
    ):
        """
        Keep the validated integration contract.

        feature/detection currently introduces
        runtime_notification_id here, but the validated
        RiskPersistenceService still calls this method using
        the original signature.
        """

        return APIClient.post(
            (
                f"/sessions/{session_id}"
                f"/risk-events/{runtime_event_id}"
                "/notifications"
            ),
            {
                "alert_type":
                    alert_type,
                "risk_level":
                    risk_level,
                "decision":
                    decision,
                "reason":
                    reason,
            },
        )

    @staticmethod
    def get_session_risk_events(
        session_id: int,
    ):
        return APIClient.get(
            f"/sessions/{session_id}/risk-events"
        )

    @staticmethod
    def get_session_alert_notifications(
        session_id: int,
    ):
        return APIClient.get(
            (
                f"/sessions/{session_id}"
                "/alert-notifications"
            )
        )