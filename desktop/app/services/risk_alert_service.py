"""Persist alerts produced by the integrated prototype risk pipeline."""

from __future__ import annotations

import time
from collections.abc import Mapping

import requests

from app.services.api_client import APIClient


FEATURE_EVENT_TYPES = {
    "shoulder_tilt": "SHOULDER_TILT",
    "neck_lateral_tilt": "NECK_LATERAL_TILT",
    "neck_flexion": "NECK_FLEXION",
}
BACKEND_LEVELS = {"LOW": "LOW", "MODERATE": "MEDIUM", "HIGH": "HIGH"}


class RiskAlertService:
    """Keep one active backend alert for each sustained posture feature."""

    def __init__(self, client=None, clock=None, minimum_seconds=60.0):
        self.client = client or APIClient
        self.clock = clock or time.monotonic
        self.minimum_seconds = float(minimum_seconds)
        self.reset()

    def reset(self):
        self.active_events: dict[str, dict] = {}
        self.retry_after = 0.0
        self.last_error = None

    @property
    def has_active_alerts(self) -> bool:
        return bool(self.active_events)

    @staticmethod
    def _error(response):
        try:
            data = response.json()
            detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
        except ValueError:
            detail = response.text
        return f"HTTP {response.status_code}: {detail}"

    def _recover(self, session_id: int, event_type: str):
        response = self.client.get_session_alerts(session_id)
        if not response.ok:
            raise RuntimeError(self._error(response))
        events = response.json()
        if not isinstance(events, list):
            raise ValueError("Invalid alert list from backend")
        active = [
            event for event in events
            if isinstance(event, dict)
            and event.get("event_type") == event_type
            and event.get("ended_at") is None
        ]
        if len(active) > 1:
            raise RuntimeError(f"Multiple active {event_type} alerts")
        return active[0] if active else None

    def _create(self, session_id: int, event_type: str, level: str) -> dict:
        try:
            response = self.client.create_alert_event(session_id, event_type, level)
        except requests.RequestException:
            recovered = self._recover(session_id, event_type)
            if recovered is None:
                raise
            return recovered
        if response.status_code == 409:
            recovered = self._recover(session_id, event_type)
            if recovered is not None:
                return recovered
            raise RuntimeError(self._error(response))
        if not response.ok:
            raise RuntimeError(self._error(response))
        event = response.json()
        if not isinstance(event, dict) or type(event.get("event_id")) is not int:
            raise ValueError("Backend returned invalid alert event")
        return event

    def _end(self, event_id: int) -> None:
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

    def _desired(self, risk_result: Mapping) -> dict[str, dict]:
        if risk_result.get("status") != "EVALUATED":
            return {}
        backend_level = BACKEND_LEVELS.get(risk_result.get("risk_level"))
        if backend_level is None:
            return {}
        features = risk_result.get("feature_results")
        if not isinstance(features, Mapping):
            return {}
        desired = {}
        for feature, event_type in FEATURE_EVENT_TYPES.items():
            row = features.get(feature)
            if not isinstance(row, Mapping) or row.get("active") is not True:
                continue
            seconds = row.get("continuous_seconds")
            if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and seconds >= self.minimum_seconds:
                desired[event_type] = {
                    "feature": feature,
                    "factor": row.get("factor"),
                    "duration_seconds": float(seconds),
                    "risk_level": backend_level,
                }
        return desired

    def update(self, session_id: int, risk_result: Mapping) -> dict:
        if type(session_id) is not int or session_id <= 0:
            raise ValueError("Invalid session_id")
        if not isinstance(risk_result, Mapping):
            raise TypeError("risk_result must be a mapping")
        actions = {"created": [], "ended": [], "errors": []}
        now = self.clock()
        if now < self.retry_after:
            return actions
        desired = self._desired(risk_result)
        try:
            for event_type in list(self.active_events):
                current = self.active_events[event_type]
                wanted = desired.get(event_type)
                if wanted is not None and wanted["risk_level"] == current["risk_level"]:
                    continue
                self._end(current["event_id"])
                actions["ended"].append(event_type)
                del self.active_events[event_type]

            for event_type, wanted in desired.items():
                if event_type in self.active_events:
                    continue
                event = self._create(session_id, event_type, wanted["risk_level"])
                record = {**wanted, "event_id": event["event_id"]}
                self.active_events[event_type] = record
                actions["created"].append({"event_type": event_type, **record})
            self.last_error = None
        except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
            self.last_error = str(error)
            self.retry_after = now + 5.0
            actions["errors"].append(self.last_error)
        return actions

    def close_all(self) -> bool:
        try:
            for event_type, event in list(self.active_events.items()):
                self._end(event["event_id"])
                del self.active_events[event_type]
            self.last_error = None
            return True
        except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
            self.last_error = str(error)
            return False
