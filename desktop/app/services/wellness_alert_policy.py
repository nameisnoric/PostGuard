"""Non-RULA alert policy for screen distance and blink rate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any


@dataclass(frozen=True)
class WellnessAlertConfig:
    low_blink_rate_per_minute: float = 10.0
    repeat_cooldown_seconds: float = 300.0


class WellnessAlertPolicy:
    """Create stable alert decisions from already-confirmed measurements."""

    def __init__(self, config: WellnessAlertConfig | None = None) -> None:
        self.config = config or WellnessAlertConfig()
        if self.config.low_blink_rate_per_minute < 0:
            raise ValueError("low blink threshold cannot be negative")
        if self.config.repeat_cooldown_seconds < 0:
            raise ValueError("repeat cooldown cannot be negative")
        self.reset()

    def reset(self) -> None:
        self._active = {"SCREEN_DISTANCE": False, "LOW_BLINK_RATE": False}
        self._last_notification: dict[str, float] = {}

    def _transition(
        self,
        event_type: str,
        *,
        evaluated: bool,
        active: bool,
        now: float,
        value: float | None,
    ) -> dict[str, Any]:
        previous = self._active[event_type]
        if not evaluated:
            return {
                "event_type": event_type,
                "action": "DATA_GAP",
                "active": previous,
                "should_notify": False,
                "alert_type": None,
                "value": value,
            }
        if not active:
            self._active[event_type] = False
            return {
                "event_type": event_type,
                "action": "RESOLVED" if previous else "NONE",
                "active": False,
                "should_notify": False,
                "alert_type": None,
                "value": value,
            }

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
                    and float(blink_rate) < self.config.low_blink_rate_per_minute
                ),
                now=float(now),
                value=float(blink_rate) if blink_valid else None,
            ),
        ]
        notification = next(
            (event for event in events if event["should_notify"]),
            None,
        )
        return {
            "contract_version": "1.0",
            "events": events,
            "active": any(event["active"] for event in events),
            "notification": notification,
            "threshold_status": "candidate_policy",
        }
