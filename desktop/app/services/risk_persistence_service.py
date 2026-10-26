"""Asynchronously persist risk-event lifecycle and alert decisions.

The detector runs on the Qt UI thread, so database requests are serialized on a
single worker. Ordinary UPDATED events are throttled; lifecycle transitions and
notifications are written immediately and retried with stable idempotency keys.
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any, Callable, Mapping

import requests

from app.services.api_client import APIClient


IMMEDIATE_ACTIONS = {"STARTED", "ESCALATED", "DEESCALATED", "DATA_GAP", "RESOLVED"}


class RiskPersistenceService:
    def __init__(
        self,
        *,
        update_interval_seconds: float = 5.0,
        max_attempts: int = 3,
        clock: Callable[[], float] | None = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self.update_interval_seconds = max(0.0, float(update_interval_seconds))
        self.max_attempts = max(1, int(max_attempts))
        self.clock = clock or time.monotonic
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="postguard-risk-persistence",
        )
        self._owns_executor = executor is None
        self._lock = threading.Lock()
        self._futures: set[Future] = set()
        self._errors: list[str] = []
        self._last_update_at: dict[tuple[int, str], float] = {}

    @staticmethod
    def _event_payload(risk_event: Mapping[str, Any]) -> Mapping[str, Any] | None:
        value = risk_event.get("event") or risk_event.get("resolved_event")
        return value if isinstance(value, Mapping) else None

    @staticmethod
    def _active_factors(result: Mapping[str, Any]) -> list[str]:
        assessment = result.get("assessment")
        factors = assessment.get("factors", []) if isinstance(assessment, Mapping) else []
        return [
            str(row.get("factor"))
            for row in factors
            if isinstance(row, Mapping) and row.get("factor")
        ]

    @staticmethod
    def _evidence_groups(result: Mapping[str, Any]) -> list[str]:
        risk = result.get("risk")
        groups = risk.get("evidence_groups", {}) if isinstance(risk, Mapping) else {}
        return [
            str(name)
            for name, row in groups.items()
            if isinstance(row, Mapping) and row.get("active") is True
        ] if isinstance(groups, Mapping) else []

    @staticmethod
    def _raise_for_response(response, operation: str) -> None:
        if response.ok:
            return
        try:
            payload = response.json()
            detail = payload.get("detail", response.text) if isinstance(payload, dict) else response.text
        except ValueError:
            detail = response.text
        raise RuntimeError(f"{operation} failed (HTTP {response.status_code}): {detail}")

    def _with_retry(self, operation: str, call: Callable[[], Any]) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = call()
                self._raise_for_response(response, operation)
                return
            except (requests.RequestException, RuntimeError) as error:
                last_error = error
                if attempt < self.max_attempts:
                    time.sleep(0.15 * attempt)
        assert last_error is not None
        raise last_error

    def _run_operations(self, operations: list[tuple[str, Callable[[], Any]]]) -> None:
        for name, operation in operations:
            self._with_retry(name, operation)

    def _remember_future(self, future: Future) -> None:
        with self._lock:
            self._futures.add(future)

        def completed(done: Future) -> None:
            error = done.exception()
            with self._lock:
                self._futures.discard(done)
                if error is not None:
                    self._errors.append(str(error))

        future.add_done_callback(completed)

    def process_pipeline_result(self, session_id: int, result: Mapping[str, Any]) -> bool:
        """Queue writes for one pipeline result. Return True when work was queued."""
        risk_event = result.get("risk_event")
        alert_policy = result.get("alert_policy")
        if not isinstance(risk_event, Mapping) or not isinstance(alert_policy, Mapping):
            return False

        action = str(risk_event.get("event_action") or "NONE")
        event = self._event_payload(risk_event)
        runtime_event_id = event.get("runtime_event_id") if event else None
        if not runtime_event_id:
            return False

        level = (
            risk_event.get("current_risk_level")
            or (event.get("current_risk_level") if event else None)
        )
        factors = self._active_factors(result)
        groups = self._evidence_groups(result)
        operations: list[tuple[str, Callable[[], Any]]] = []

        if action == "UPDATED":
            key = (session_id, str(runtime_event_id))
            now = self.clock()
            previous = self._last_update_at.get(key)
            if previous is not None and now - previous < self.update_interval_seconds:
                action = "NONE"
            else:
                self._last_update_at[key] = now

        if action == "STARTED" and level in {"MODERATE", "HIGH"}:
            operations.append((
                "start risk event",
                lambda: APIClient.create_risk_event(
                    session_id, str(runtime_event_id), str(level), factors, groups
                ),
            ))
        elif action in {"UPDATED", "ESCALATED", "DEESCALATED", "DATA_GAP"}:
            persisted_level = level or (event.get("current_risk_level") if event else None)
            if persisted_level in {"MODERATE", "HIGH"}:
                operations.append((
                    "update risk event",
                    lambda: APIClient.update_risk_event(
                        session_id,
                        str(runtime_event_id),
                        action,
                        str(persisted_level),
                        factors,
                        groups,
                    ),
                ))
        elif action == "RESOLVED":
            reason = str(risk_event.get("reason") or "RISK_EVENT_RESOLVED")
            operations.append((
                "resolve risk event",
                lambda: APIClient.resolve_risk_event(
                    session_id, str(runtime_event_id), reason
                ),
            ))

        if alert_policy.get("should_notify") is True:
            alert_type = str(alert_policy.get("alert_type") or "FIRST")
            notification_id = f"notification-{uuid.uuid4()}"
            notification_level = alert_policy.get("current_risk_level") or level
            decision = str(alert_policy.get("decision") or "ALERT")
            reason = alert_policy.get("reason")
            operations.append((
                "create alert notification",
                lambda: APIClient.create_alert_notification(
                    session_id,
                    str(runtime_event_id),
                    notification_id,
                    alert_type,
                    str(notification_level) if notification_level else None,
                    decision,
                    str(reason) if reason else None,
                ),
            ))

        if not operations:
            return False
        self._remember_future(self._executor.submit(self._run_operations, operations))
        return True

    def flush(self, timeout: float = 8.0) -> bool:
        with self._lock:
            pending = set(self._futures)
        if not pending:
            return True
        _, unfinished = wait(pending, timeout=max(0.0, timeout))
        return not unfinished

    def drain_errors(self) -> list[str]:
        with self._lock:
            errors = list(self._errors)
            self._errors.clear()
        return errors

    def reset(self) -> None:
        self.flush()
        self._last_update_at.clear()
        self.drain_errors()

    def shutdown(self) -> None:
        self.flush()
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=False)

