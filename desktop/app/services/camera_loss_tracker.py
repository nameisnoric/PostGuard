"""Track camera-unavailable periods without treating them as safe posture."""

from __future__ import annotations

import math


class CameraLossTracker:
    """Accumulate camera gaps for one monitoring session."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.started_at: float | None = None
        self.total_duration = 0.0
        self.loss_count = 0

    @staticmethod
    def _time(value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("timestamp must be numeric")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("timestamp must be finite")
        return value

    @property
    def active(self) -> bool:
        return self.started_at is not None

    def begin(self, now: float) -> bool:
        """Start a gap. Return True only for the first failure in that gap."""
        now = self._time(now)
        if self.started_at is not None:
            return False
        self.started_at = now
        self.loss_count += 1
        return True

    def continue_after_pause(self, now: float) -> bool:
        """Continue a pre-pause gap without counting a second camera loss."""
        now = self._time(now)
        if self.started_at is not None:
            return False
        self.started_at = now
        return True

    def recover(self, now: float) -> float:
        """Close the active gap and return its duration."""
        now = self._time(now)
        if self.started_at is None:
            return 0.0
        duration = max(0.0, now - self.started_at)
        self.total_duration += duration
        self.started_at = None
        return duration

    def duration(self, now: float | None = None) -> float:
        """Return total duration, including an active gap when ``now`` is given."""
        if self.started_at is None or now is None:
            return self.total_duration
        return self.total_duration + max(0.0, self._time(now) - self.started_at)
