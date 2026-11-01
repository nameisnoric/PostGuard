"""Persist continuous non-RULA wellness alert episodes."""

import time

import requests

from app.services.api_client import APIClient


class WellnessAlertPersistence:
    RETRY_SECONDS = 5.0

    def __init__(self, client=None, clock=None) -> None:
        self.client = client or APIClient
        self.clock = clock or time.monotonic
        self.reset()

    def reset(self) -> None:
        self.event_ids: dict[str, int] = {}
        self.retry_after: dict[str, float] = {}
        self.last_error: str | None = None

    @staticmethod
    def _error(response) -> str:
        try:
            body = response.json()
            detail = body.get("detail", response.text) if isinstance(body, dict) else response.text
        except ValueError:
            detail = response.text
        return f"HTTP {response.status_code}: {detail}"

    def _find_active(self, session_id: int, event_type: str) -> int | None:
        response = self.client.get_session_alerts(session_id)
        if not response.ok:
            raise RuntimeError(self._error(response))
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("Invalid alert list")
        active = [
            row for row in rows
            if isinstance(row, dict)
            and row.get("event_type") == event_type
            and row.get("ended_at") is None
        ]
        if len(active) > 1:
            raise RuntimeError(f"Multiple active {event_type} alerts")
        if not active:
            return None
        event_id = active[0].get("event_id")
        if type(event_id) is not int or event_id <= 0:
            raise ValueError("Invalid alert event ID")
        return event_id

    def _create(self, session_id: int, event_type: str) -> int:
        try:
            response = self.client.create_alert_event(session_id, event_type, "MEDIUM")
        except requests.RequestException:
            recovered = self._find_active(session_id, event_type)
            if recovered is None:
                raise
            return recovered
        if response.status_code == 409:
            recovered = self._find_active(session_id, event_type)
            if recovered is not None:
                return recovered
        if not response.ok:
            raise RuntimeError(self._error(response))
        body = response.json()
        event_id = body.get("event_id") if isinstance(body, dict) else None
        if type(event_id) is not int or event_id <= 0:
            raise ValueError("Backend returned an invalid alert event ID")
        return event_id

    def update(self, session_id: int, policy: dict) -> None:
        now = self.clock()
        for event in policy.get("events", []):
            if not isinstance(event, dict):
                continue
            event_type = event.get("event_type")
            if event_type not in {"SCREEN_DISTANCE", "LOW_BLINK_RATE"}:
                continue
            if now < self.retry_after.get(event_type, 0.0):
                continue
            try:
                event_id = self.event_ids.get(event_type)
                if event.get("active") is True and event_id is None:
                    self.event_ids[event_type] = self._create(session_id, event_type)
                elif event.get("active") is False and event_id is not None:
                    response = self.client.end_alert_event(event_id)
                    if response.status_code != 409 and not response.ok:
                        raise RuntimeError(self._error(response))
                    self.event_ids.pop(event_type, None)
                self.retry_after.pop(event_type, None)
                self.last_error = None
            except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
                self.last_error = str(error)
                self.retry_after[event_type] = now + self.RETRY_SECONDS
