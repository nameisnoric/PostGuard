"""Persist continuous non-RULA wellness alert episodes."""

import time
import uuid

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
        self.pending_eye_notifications: list[dict] = []
        self.pending_screen_notifications: list[dict] = []

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

    def update(
        self,
        session_id: int,
        policy: dict,
        *,
        persist_notifications: bool = True,
    ) -> None:
        now = self.clock()
        notifications = policy.get("notifications")
        if not isinstance(notifications, list):
            notifications = [policy.get("notification")]
        for notification in notifications if persist_notifications else []:
            if not isinstance(notification, dict):
                continue
            event_type = notification.get("event_type")
            alert_type = notification.get("alert_type")
            if alert_type not in {"FIRST", "REPEAT"}:
                continue
            if event_type == "LOW_BLINK_RATE":
                value = notification.get("value")
                count = notification.get("window_blink_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self.pending_eye_notifications.append({
                        "runtime_notification_id": f"eye-{uuid.uuid4()}",
                        "alert_type": alert_type,
                        "blink_rate": float(value),
                        "window_blink_count": count if type(count) is int and count >= 0 else 0,
                        "reason": "LOW_BLINK_CONFIRMED",
                        "retry_at": 0.0,
                    })
            elif event_type == "SCREEN_DISTANCE":
                value = notification.get("value")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self.pending_screen_notifications.append({
                        "runtime_notification_id": f"screen-{uuid.uuid4()}",
                        "alert_type": alert_type,
                        "distance_ratio": float(value),
                        "reason": "SCREEN_DISTANCE_CONFIRMED",
                        "retry_at": 0.0,
                    })

        errors = []
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
            except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
                errors.append(str(error))
                self.retry_after[event_type] = now + self.RETRY_SECONDS

        remaining = []
        for item in self.pending_eye_notifications:
            if now < item.get("retry_at", 0.0):
                remaining.append(item)
                continue
            try:
                response = self.client.create_eye_alert_notification(
                    session_id,
                    item["runtime_notification_id"],
                    item["alert_type"],
                    item["blink_rate"],
                    item["window_blink_count"],
                    item["reason"],
                )
                if not response.ok:
                    raise RuntimeError(self._error(response))
            except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
                item["retry_at"] = now + self.RETRY_SECONDS
                remaining.append(item)
                errors.append(str(error))
        self.pending_eye_notifications = remaining

        remaining_screen = []
        for item in self.pending_screen_notifications:
            if now < item.get("retry_at", 0.0):
                remaining_screen.append(item)
                continue
            try:
                response = self.client.create_screen_distance_notification(
                    session_id,
                    item["runtime_notification_id"],
                    item["alert_type"],
                    item["distance_ratio"],
                    item["reason"],
                )
                if not response.ok:
                    raise RuntimeError(self._error(response))
            except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
                item["retry_at"] = now + self.RETRY_SECONDS
                remaining_screen.append(item)
                errors.append(str(error))
        self.pending_screen_notifications = remaining_screen
        self.last_error = errors[0] if errors else None

    def flush(self, session_id: int) -> bool:
        """Retry queued eye reminders before pausing or ending the session."""
        for item in self.pending_eye_notifications:
            item["retry_at"] = 0.0
        for item in self.pending_screen_notifications:
            item["retry_at"] = 0.0
        self.update(session_id, {"events": [], "notifications": []})
        return not self.pending_eye_notifications and not self.pending_screen_notifications
