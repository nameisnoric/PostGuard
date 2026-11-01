from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Mapping


EYE_ALERT_POLICY_VERSION = "1.0"


STATE_WARMUP = "WARMUP"
STATE_NORMAL = "NORMAL"
STATE_PENDING_LOW_BLINK = "PENDING_LOW_BLINK"
STATE_LOW_BLINK = "LOW_BLINK"
STATE_DATA_GAP = "DATA_GAP"
STATE_NOT_EVALUATED = "NOT_EVALUATED"


ALERT_FIRST = "FIRST"
ALERT_REPEAT = "REPEAT"


@dataclass(frozen=True)
class EyeAlertPolicyConfig:
    """
    PostGuard prototype engineering thresholds.

    IMPORTANT:
    These values are NOT clinical diagnostic thresholds.
    """

    window_seconds: float = 60.0

    # Window must contain enough valid observation time
    # before Blink Rate is interpreted.
    minimum_valid_seconds: float = 45.0

    # Candidate engineering threshold.
    low_blink_rate_per_minute: float = 8.0

    # Hysteresis:
    # once LOW_BLINK is active, require a slightly higher
    # blink rate before considering the condition recovered.
    recovery_blink_rate_per_minute: float = 10.0

    # Low blink condition must continue before FIRST alert.
    confirmation_seconds: float = 15.0

    # Do not repeatedly disturb the user.
    repeat_cooldown_seconds: float = 600.0

    # Break temporal continuity if usable eye observations
    # disappear for too long.
    maximum_sample_gap_seconds: float = 2.0

    def __post_init__(self) -> None:

        numeric_values = (
            self.window_seconds,
            self.minimum_valid_seconds,
            self.low_blink_rate_per_minute,
            self.recovery_blink_rate_per_minute,
            self.confirmation_seconds,
            self.repeat_cooldown_seconds,
            self.maximum_sample_gap_seconds,
        )

        for value in numeric_values:

            if (
                isinstance(value, bool)
                or
                not isinstance(
                    value,
                    (int, float),
                )
                or
                not math.isfinite(
                    float(value)
                )
                or
                float(value) < 0.0
            ):

                raise ValueError(
                    "Eye Alert Policy config values must "
                    "be finite non-negative numbers."
                )

        if (
            self.minimum_valid_seconds
            >
            self.window_seconds
        ):

            raise ValueError(
                "minimum_valid_seconds cannot exceed "
                "window_seconds."
            )

        if (
            self.recovery_blink_rate_per_minute
            <
            self.low_blink_rate_per_minute
        ):

            raise ValueError(
                "recovery threshold must be greater than "
                "or equal to low-blink threshold."
            )


class EyeAlertPolicy:
    """
    PostGuard Eye Alert Policy v1.0.

    Responsibilities
    ----------------
    - Observe validated Blink Detection output.
    - Maintain a rolling blink window.
    - Calculate recent blink rate.
    - Detect sustained low-blink condition.
    - Apply confirmation time.
    - Produce FIRST / REPEAT notification decisions.
    - Apply cooldown.
    - Use hysteresis for recovery.
    - Break continuity on missing/invalid eye data.

    Does NOT
    --------
    - detect eyes,
    - count blinks itself,
    - diagnose dry eye,
    - diagnose fatigue,
    - diagnose drowsiness,
    - modify Posture Risk,
    - write database records,
    - show UI,
    - play sound.
    """

    def __init__(
        self,
        config: EyeAlertPolicyConfig | None = None,
    ) -> None:

        self.config = (
            config
            or EyeAlertPolicyConfig()
        )

        self.reset()

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
    ) -> None:

        self._blink_times = deque()
        self._valid_sample_times = deque()

        self._last_sample_at = None

        self._pending_started_at = None

        self._low_blink_active = False

        self._last_alert_at = None

        self._alert_count = 0

        self._last_now = None

    # ========================================================
    # CLOCK
    # ========================================================

    def _resolve_now(
        self,
        now: float | None,
    ) -> float:

        value = (
            time.monotonic()
            if now is None
            else float(now)
        )

        if (
            not math.isfinite(value)
            or
            value < 0.0
        ):

            raise ValueError(
                "now must be a finite non-negative "
                "monotonic timestamp."
            )

        if (
            self._last_now is not None
            and
            value < self._last_now
        ):

            raise ValueError(
                "Eye Alert Policy clock cannot move backwards."
            )

        self._last_now = value

        return value

    # ========================================================
    # WINDOW
    # ========================================================

    def _trim_window(
        self,
        now: float,
    ) -> None:

        cutoff = (
            now
            -
            self.config.window_seconds
        )

        while (
            self._blink_times
            and
            self._blink_times[0] < cutoff
        ):

            self._blink_times.popleft()

        while (
            self._valid_sample_times
            and
            self._valid_sample_times[0] < cutoff
        ):

            self._valid_sample_times.popleft()

    def _valid_observation_seconds(
        self,
    ) -> float:

        if len(
            self._valid_sample_times
        ) < 2:

            return 0.0

        return max(
            0.0,
            float(
                self._valid_sample_times[-1]
                -
                self._valid_sample_times[0]
            ),
        )

    def _blink_rate(
        self,
    ) -> float | None:

        observed_seconds = (
            self._valid_observation_seconds()
        )

        if observed_seconds <= 0.0:

            return None

        return (
            len(self._blink_times)
            /
            observed_seconds
            *
            60.0
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    def _result(
        self,
        *,
        now: float,
        state: str,
        reason: str,
        should_notify: bool = False,
        alert_type: str | None = None,
    ) -> dict[str, Any]:

        blink_rate = (
            self._blink_rate()
        )

        observed_seconds = (
            self._valid_observation_seconds()
        )

        return {
            "eye_alert_policy_version": (
                EYE_ALERT_POLICY_VERSION
            ),

            "timestamp_monotonic": now,

            "state": state,

            "reason": reason,

            "should_notify": (
                should_notify
            ),

            "alert_type": (
                alert_type
            ),

            "blink_rate_per_minute": (
                blink_rate
            ),

            "window_blink_count": (
                len(
                    self._blink_times
                )
            ),

            "valid_observation_seconds": (
                observed_seconds
            ),

            "low_blink_active": (
                self._low_blink_active
            ),

            "alert_count": (
                self._alert_count
            ),

            "policy": {
                "type": (
                    "POSTGUARD_PROTOTYPE_EYE_ALERT_POLICY"
                ),

                "window_seconds": (
                    self.config.window_seconds
                ),

                "minimum_valid_seconds": (
                    self.config.minimum_valid_seconds
                ),

                "low_blink_rate_per_minute": (
                    self.config
                    .low_blink_rate_per_minute
                ),

                "recovery_blink_rate_per_minute": (
                    self.config
                    .recovery_blink_rate_per_minute
                ),

                "confirmation_seconds": (
                    self.config.confirmation_seconds
                ),

                "repeat_cooldown_seconds": (
                    self.config.repeat_cooldown_seconds
                ),

                "is_clinical_threshold": False,
            },
        }

    # ========================================================
    # DATA GAP
    # ========================================================

    def process_data_gap(
        self,
        *,
        now: float | None = None,
        reason: str = "EYE_DATA_UNAVAILABLE",
    ) -> dict[str, Any]:

        now_value = (
            self._resolve_now(
                now
            )
        )

        # Missing data must break temporal confirmation.
        self._pending_started_at = None
        self._last_sample_at = None

        # Window is discarded because we cannot claim a
        # continuous 60-second observation across the gap.
        self._blink_times.clear()
        self._valid_sample_times.clear()

        return self._result(
            now=now_value,
            state=STATE_DATA_GAP,
            reason=reason,
        )

    # ========================================================
    # UPDATE
    # ========================================================

    def update(
        self,
        blink_result: Mapping[str, Any],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:

        if not isinstance(
            blink_result,
            Mapping,
        ):

            raise ValueError(
                "blink_result must be a mapping."
            )

        now_value = (
            self._resolve_now(
                now
            )
        )

        calibrated = (
            blink_result.get(
                "calibrated"
            )
            is True
        )

        eye_state = (
            blink_result.get(
                "eye_state"
            )
        )

        # ====================================================
        # NOT READY
        # ====================================================

        if not calibrated:

            self._pending_started_at = None

            return self._result(
                now=now_value,
                state=STATE_NOT_EVALUATED,
                reason="BLINK_CALIBRATION_NOT_READY",
            )

        # UNKNOWN means current frame does not provide usable
        # eye evidence.
        if eye_state == "UNKNOWN":

            if (
                self._last_sample_at is not None
                and
                now_value
                -
                self._last_sample_at
                >
                self.config.maximum_sample_gap_seconds
            ):

                return self.process_data_gap(
                    now=now_value,
                    reason="EYE_STATE_UNKNOWN",
                )

            return self._result(
                now=now_value,
                state=STATE_NOT_EVALUATED,
                reason="EYE_STATE_UNKNOWN",
            )

        # ====================================================
        # CONTINUITY GAP
        # ====================================================

        if (
            self._last_sample_at is not None
            and
            now_value
            -
            self._last_sample_at
            >
            self.config.maximum_sample_gap_seconds
        ):

            self._blink_times.clear()
            self._valid_sample_times.clear()

            self._pending_started_at = None

        self._last_sample_at = (
            now_value
        )

        # ====================================================
        # RECORD VALID OBSERVATION
        # ====================================================

        self._valid_sample_times.append(
            now_value
        )

        if (
            blink_result.get(
                "blink_event"
            )
            is True
        ):

            self._blink_times.append(
                now_value
            )

        self._trim_window(
            now_value
        )

        observed_seconds = (
            self._valid_observation_seconds()
        )

        # ====================================================
        # WARMUP
        # ====================================================

        if (
            observed_seconds
            <
            self.config.minimum_valid_seconds
        ):

            self._pending_started_at = None

            return self._result(
                now=now_value,
                state=STATE_WARMUP,
                reason="INSUFFICIENT_VALID_OBSERVATION",
            )

        blink_rate = (
            self._blink_rate()
        )

        if blink_rate is None:

            return self._result(
                now=now_value,
                state=STATE_NOT_EVALUATED,
                reason="BLINK_RATE_UNAVAILABLE",
            )

        # ====================================================
        # ACTIVE LOW BLINK CONDITION
        # ====================================================

        if self._low_blink_active:

            # Hysteresis recovery.
            if (
                blink_rate
                >=
                self.config
                .recovery_blink_rate_per_minute
            ):

                self._low_blink_active = False
                self._pending_started_at = None
                self._last_alert_at = None

                return self._result(
                    now=now_value,
                    state=STATE_NORMAL,
                    reason="BLINK_RATE_RECOVERED",
                )

            # Still low but cooldown is active.
            if (
                self._last_alert_at is not None
                and
                now_value
                -
                self._last_alert_at
                <
                self.config.repeat_cooldown_seconds
            ):

                return self._result(
                    now=now_value,
                    state=STATE_LOW_BLINK,
                    reason="LOW_BLINK_REPEAT_COOLDOWN",
                )

            # Repeat reminder.
            self._last_alert_at = (
                now_value
            )

            self._alert_count += 1

            return self._result(
                now=now_value,
                state=STATE_LOW_BLINK,
                reason="LOW_BLINK_REPEAT_READY",
                should_notify=True,
                alert_type=ALERT_REPEAT,
            )

        # ====================================================
        # LOW BLINK CANDIDATE
        # ====================================================

        if (
            blink_rate
            <=
            self.config.low_blink_rate_per_minute
        ):

            if self._pending_started_at is None:

                self._pending_started_at = (
                    now_value
                )

                return self._result(
                    now=now_value,
                    state=STATE_PENDING_LOW_BLINK,
                    reason="LOW_BLINK_CONFIRMATION_STARTED",
                )

            pending_seconds = (
                now_value
                -
                self._pending_started_at
            )

            if (
                pending_seconds
                <
                self.config.confirmation_seconds
            ):

                return self._result(
                    now=now_value,
                    state=STATE_PENDING_LOW_BLINK,
                    reason="LOW_BLINK_CONFIRMATION_ACTIVE",
                )

            # Confirmation completed.
            self._low_blink_active = True

            self._last_alert_at = (
                now_value
            )

            self._alert_count += 1

            return self._result(
                now=now_value,
                state=STATE_LOW_BLINK,
                reason="LOW_BLINK_CONFIRMED",
                should_notify=True,
                alert_type=ALERT_FIRST,
            )

        # ====================================================
        # NORMAL
        # ====================================================

        self._pending_started_at = None

        return self._result(
            now=now_value,
            state=STATE_NORMAL,
            reason="BLINK_RATE_NORMAL",
        )