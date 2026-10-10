"""One experimental neck side-bending alert per continuous episode.

This service does not calculate clinical risk or PostGuard's full risk score.
The backend's required MEDIUM enum is a provisional transport label only.
"""
import time

import requests

from app.services.api_client import APIClient


class ExperimentalAlertService:
    EVENT_TYPE = "NECK_LATERAL_TILT"
    PROVISIONAL_LEVEL = "MEDIUM"
    MIN_SECONDS = 60.0
    RETRY_SECONDS = 5.0

    def __init__(self, client=None, clock=None):
        self.client = client or APIClient
        self.clock = clock or time.monotonic
        self.reset()

    def reset(self):
        self.active_event_id = None
        self.alerted_direction = None
        self.retry_after = 0.0
        self.last_error = None

    @staticmethod
    def _error(response):
        try:
            data = response.json()
            detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
        except ValueError:
            detail = response.text
        return f"HTTP {response.status_code}: {detail}"

    def _recover_active(self, session_id):
        """Reconcile a create timeout/409 before attempting another POST."""
        response = self.client.get_session_alerts(session_id)
        if not response.ok:
            raise RuntimeError(self._error(response))
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Invalid alert list from backend")
        active = [
            event for event in data
            if isinstance(event, dict)
            and event.get("event_type") == self.EVENT_TYPE
            and event.get("ended_at") is None
        ]
        if len(active) > 1:
            raise RuntimeError("Multiple active neck alerts; manual review required")
        if active:
            event_id = active[0].get("event_id")
            if type(event_id) is not int or event_id <= 0:
                raise ValueError("Invalid active alert ID")
            return event_id
        return None

    def _create(self, session_id):
        try:
            response = self.client.create_alert_event(
                session_id, self.EVENT_TYPE, self.PROVISIONAL_LEVEL
            )
        except requests.RequestException:
            # Server may have committed the alert even though client timed out.
            recovered = self._recover_active(session_id)
            if recovered is None:
                raise
            return recovered

        if response.status_code == 409:
            recovered = self._recover_active(session_id)
            if recovered is not None:
                return recovered
            raise RuntimeError(self._error(response))
        if not response.ok:
            raise RuntimeError(self._error(response))
        data = response.json()
        event_id = data.get("event_id") if isinstance(data, dict) else None
        if type(event_id) is not int or event_id <= 0:
            raise ValueError("Backend returned invalid event_id")
        return event_id

    def _end(self):
        event_id = self.active_event_id
        try:
            response = self.client.end_alert_event(event_id)
        except requests.RequestException:
            check = self.client.get_alert_event(event_id)
            if check.ok and check.json().get("ended_at") is not None:
                return
            raise
        if response.status_code == 409:
            check = self.client.get_alert_event(event_id)
            if check.ok and check.json().get("ended_at") is not None:
                return
        if not response.ok:
            raise RuntimeError(self._error(response))
        data = response.json()
        if not isinstance(data, dict) or data.get("ended_at") is None:
            raise ValueError("Backend did not confirm alert end")

    def update(self, session_id: int, direction: int | None, seconds: float | None) -> str | None:
        """Return 'created'/'ended' or None; retain state on API failure.

        Must be called only for a RUNNING session. The caller owns the posture
        duration tracker; direction must be -1, 0, +1, or None.
        """
        if direction not in (-1, 0, 1, None):
            raise ValueError("Invalid posture direction")
        now = self.clock()
        if now < self.retry_after:
            return None

        try:
            # Close an active event on neutral, lost detection or side change.
            if self.active_event_id is not None:
                if direction != self.alerted_direction:
                    self._end()
                    self.active_event_id = None
                    self.alerted_direction = None
                    self.last_error = None
                    return "ended"
                return None

            # After a successful event, don't create another for the same
            # continuous episode. Reset only after a new direction/neutral.
            if direction != self.alerted_direction:
                self.alerted_direction = None

            if (
                direction in (-1, 1)
                and seconds is not None
                and seconds >= self.MIN_SECONDS
                and self.alerted_direction is None
            ):
                self.active_event_id = self._create(session_id)
                self.alerted_direction = direction
                self.last_error = None
                return "created"
            return None
        except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
            self.last_error = str(error)
            self.retry_after = now + self.RETRY_SECONDS
            return None

    def close_if_active(self) -> bool:
        """Close alert when threshold changes. Return False on API failure."""
        if self.active_event_id is None:
            self.alerted_direction = None
            return True
        try:
            self._end()
            self.reset()
            return True
        except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
            self.last_error = str(error)
            self.retry_after = 0.0  # retry next detection
            return False
