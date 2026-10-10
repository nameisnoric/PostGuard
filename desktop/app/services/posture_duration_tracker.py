"""Track continuous left/right neck side-bending using a monotonic clock.

This is a timing utility, not a clinical posture classifier.
"""
import math
import time


class PostureDurationTracker:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.direction = 0
        self.started_at = None

    def update(self, direction: int | None, now: float | None = None) -> float | None:
        """Return seconds of uninterrupted bending.

        direction: -1 (one side), 0 (neutral), +1 (other side),
                   None (unavailable). None also resets tracking.
        """
        if direction is not None and type(direction) is not int:
            raise ValueError("direction must be -1, 0, 1 or None")
        if direction not in (-1, 0, 1, None):
            raise ValueError("direction must be -1, 0, 1 or None")
        if now is None:
            now = time.monotonic()
        if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
            raise ValueError("now must be a finite monotonic timestamp")

        if direction is None:
            self.reset()
            return None
        if direction == 0:
            self.reset()
            return 0.0
        if self.direction != direction or self.started_at is None:
            self.direction = direction
            self.started_at = float(now)
            return 0.0
        return max(0.0, float(now) - self.started_at)


def classify_neck_side_bending(
    current_angle: float | None,
    baseline_angle: float | None,
    threshold_degrees: float | None,
) -> int | None:
    """Classify baseline-relative neck tilt for an *experimental* threshold.

    Returns -1/0/+1 or None when disabled/missing. No medical cutoff implied.
    """
    if threshold_degrees is None or threshold_degrees == 0:
        return None
    for value in (current_angle, baseline_angle, threshold_degrees):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
    if threshold_degrees < 0:
        raise ValueError("threshold_degrees must be non-negative")
    difference = float(current_angle) - float(baseline_angle)
    if abs(difference) < threshold_degrees:
        return 0
    return 1 if difference > 0 else -1
