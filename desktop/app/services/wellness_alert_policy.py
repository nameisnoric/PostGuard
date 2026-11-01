"""Non-RULA alert policy for screen distance and blink rate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any


@dataclass(frozen=True)
class WellnessAlertConfig:
    low_blink_rate_per_minute: float = 8.0
    recovery_blink_rate_per_minute: float = 10.0
    blink_confirmation_seconds: float = 15.0
    repeat_cooldown_seconds: float = 600.0


class WellnessAlertPolicy:
    """Create stable alert decisions from already-confirmed measurements."""

    def __init__(self, config: WellnessAlertConfig | None = None) -> None:
        self.config = config or WellnessAlertConfig()
        if self.config.low_blink_rate_per_minute < 0:
            raise ValueError("low blink threshold cannot be negative")
        if self.config.recovery_blink_rate_per_minute < self.config.low_blink_rate_per_minute:
            raise ValueError("blink recovery threshold cannot be below low threshold")
        if self.config.blink_confirmation_seconds < 0:
            raise ValueError("blink confirmation cannot be negative")
        if self.config.repeat_cooldown_seconds < 0:
            raise ValueError("repeat cooldown cannot be negative")
        self.reset()

    def reset(self) -> None:
        self._active = {"SCREEN_DISTANCE": False, "LOW_BLINK_RATE": False}
        self._last_notification: dict[str, float] = {}
        self._pending_started_at: dict[str, float] = {}

    def _transition(
        self,
        event_type: str,
        *,
        evaluated: bool,
        active: bool,
        now: float,
        value: float | None,
        confirmation_seconds: float = 0.0,
        recovery_active: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous = self._active[event_type]
        extra = dict(metadata or {})
        if not evaluated:
            self._pending_started_at.pop(event_type, None)
            return {
                "event_type": event_type,
                "action": "DATA_GAP",
                "active": previous,
                "should_notify": False,
                "alert_type": None,
                "value": value,
                **extra,
            }
        if not active and not (previous and recovery_active):
            self._active[event_type] = False
            self._pending_started_at.pop(event_type, None)
            self._last_notification.pop(event_type, None)
            return {
                "event_type": event_type,
                "action": "RESOLVED" if previous else "NONE",
                "active": False,
                "should_notify": False,
                "alert_type": None,
                "value": value,
                **extra,
            }

        if not previous and confirmation_seconds > 0:
            pending_at = self._pending_started_at.get(event_type)
            if pending_at is None:
                self._pending_started_at[event_type] = now
                return {
                    "event_type": event_type,
                    "action": "PENDING",
                    "active": False,
                    "should_notify": False,
                    "alert_type": None,
                    "value": value,
                    "confirmation_seconds": 0.0,
                    **extra,
                }
            elapsed = max(0.0, now - pending_at)
            if elapsed < confirmation_seconds:
                return {
                    "event_type": event_type,
                    "action": "PENDING",
                    "active": False,
                    "should_notify": False,
                    "alert_type": None,
                    "value": value,
                    "confirmation_seconds": elapsed,
                    **extra,
                }
            self._pending_started_at.pop(event_type, None)

        self._active[event_type] = True
        last = self._last_notification.get(event_type)
        if not previous:
            should_notify = True
            alert_type = "FIRST"
        elif last is None or now - last >= self.config.repeat_cooldown_seconds:
            should_notify = True
            alert_type = "REPEAT"
        else:
            should_notify = False
            alert_type = None
        if should_notify:
            self._last_notification[event_type] = now
        return {
            "event_type": event_type,
            "action": "STARTED" if not previous else "UPDATED",
            "active": True,
            "should_notify": should_notify,
            "alert_type": alert_type,
            "value": value,
            **extra,
        }

    def update(
        self,
        screen_distance: Mapping[str, Any] | None,
        blink_statistics: Mapping[str, Any] | None,
        *,
        now: float,
    ) -> dict[str, Any]:
        screen = screen_distance if isinstance(screen_distance, Mapping) else {}
        blink = blink_statistics if isinstance(blink_statistics, Mapping) else {}
        screen_evaluated = screen.get("evaluated") is True
        screen_state = screen.get("state")
        blink_evaluated = blink.get("window_ready") is True
        blink_rate = blink.get("blink_rate")
        blink_valid = isinstance(blink_rate, (int, float)) and not isinstance(blink_rate, bool)
        blink_count = blink.get("blink_count_60s")

        events = [
            self._transition(
                "SCREEN_DISTANCE",
                evaluated=screen_evaluated,
                active=screen_state == "TOO_CLOSE",
                now=float(now),
                value=screen.get("ratio") if screen_evaluated else None,
            ),
            self._transition(
                "LOW_BLINK_RATE",
                evaluated=blink_evaluated and blink_valid,
                active=bool(
                    blink_evaluated
                    and blink_valid
                    and float(blink_rate) <= self.config.low_blink_rate_per_minute
                ),
                now=float(now),
                value=float(blink_rate) if blink_valid else None,
                confirmation_seconds=self.config.blink_confirmation_seconds,
                recovery_active=bool(
                    blink_valid
                    and float(blink_rate) < self.config.recovery_blink_rate_per_minute
                ),
                metadata={
                    "window_blink_count": (
                        int(blink_count)
                        if type(blink_count) is int and blink_count >= 0
                        else None
                    ),
                },
            ),
        ]
        notifications = [event for event in events if event["should_notify"]]
        notification = notifications[0] if notifications else None
        return {
            "contract_version": "1.1-pipeline-adapted",
            "events": events,
            "active": any(event["active"] for event in events),
            "notification": notification,
            "notifications": notifications,
            "threshold_status": "prototype_engineering_policy",
            "policy": {
                "low_blink_rate_per_minute": self.config.low_blink_rate_per_minute,
                "recovery_blink_rate_per_minute": self.config.recovery_blink_rate_per_minute,
                "blink_confirmation_seconds": self.config.blink_confirmation_seconds,
                "repeat_cooldown_seconds": self.config.repeat_cooldown_seconds,
                "is_clinical_threshold": False,
            },
        }
