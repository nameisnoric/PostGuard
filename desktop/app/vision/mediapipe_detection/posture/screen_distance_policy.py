"""
PostGuard Screen Distance Policy v1.0

Purpose
-------
Convert Personal-Baseline-relative eye-distance measurements into a
stable screen-distance state.

This module is intentionally separate from Posture Risk / RULA.

Input:
    current_eye_distance_px
    baseline_eye_distance_px

Core measurement:
    ratio = current_eye_distance_px / baseline_eye_distance_px

Important:
    The thresholds in this policy are CONFIGURABLE POLICY VALUES.
    They are NOT validated physical-distance or ergonomic thresholds.

State machine:
    NORMAL
        |
        | ratio >= enter_ratio continuously for confirmation_seconds
        v
    TOO_CLOSE
        |
        | ratio <= exit_ratio
        v
    NORMAL

The difference between enter_ratio and exit_ratio provides hysteresis.
"""

import math
from dataclasses import dataclass
from typing import Optional


SCREEN_DISTANCE_POLICY_VERSION = "1.0"

STATE_NORMAL = "NORMAL"
STATE_TOO_CLOSE = "TOO_CLOSE"
STATE_PENDING = "PENDING"
STATE_NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class ScreenDistancePolicyConfig:
    """
    Configuration for Screen Distance Policy.

    IMPORTANT:
    These defaults are candidate engineering values only.

    They must not be described as validated ergonomic thresholds.
    """

    enter_ratio: float = 1.25
    exit_ratio: float = 1.15
    confirmation_seconds: float = 3.0


def _is_finite_positive_number(value) -> bool:
    """
    Return True only for finite positive numeric values.

    bool is rejected because bool is a subclass of int in Python.
    """

    if isinstance(value, bool):
        return False

    try:
        number = float(value)
    except (TypeError, ValueError):
        return False

    return (
        math.isfinite(number)
        and number > 0.0
    )


def _validate_config(
    config: ScreenDistancePolicyConfig,
) -> None:
    """
    Validate policy configuration.

    Requirements:
        enter_ratio > 1
        exit_ratio > 1
        exit_ratio < enter_ratio
        confirmation_seconds >= 0
    """

    if not _is_finite_positive_number(
        config.enter_ratio
    ):
        raise ValueError(
            "enter_ratio must be a finite positive number"
        )

    if not _is_finite_positive_number(
        config.exit_ratio
    ):
        raise ValueError(
            "exit_ratio must be a finite positive number"
        )

    if isinstance(
        config.confirmation_seconds,
        bool,
    ):
        raise ValueError(
            "confirmation_seconds must be a finite "
            "non-negative number"
        )

    try:
        confirmation_seconds = float(
            config.confirmation_seconds
        )
    except (TypeError, ValueError):
        raise ValueError(
            "confirmation_seconds must be a finite "
            "non-negative number"
        )

    if (
        not math.isfinite(
            confirmation_seconds
        )
        or confirmation_seconds < 0.0
    ):
        raise ValueError(
            "confirmation_seconds must be a finite "
            "non-negative number"
        )

    enter_ratio = float(
        config.enter_ratio
    )

    exit_ratio = float(
        config.exit_ratio
    )

    if enter_ratio <= 1.0:
        raise ValueError(
            "enter_ratio must be greater than 1.0"
        )

    if exit_ratio <= 1.0:
        raise ValueError(
            "exit_ratio must be greater than 1.0"
        )

    if exit_ratio >= enter_ratio:
        raise ValueError(
            "exit_ratio must be lower than enter_ratio "
            "to provide hysteresis"
        )


def calculate_screen_distance_ratio(
    current_eye_distance_px,
    baseline_eye_distance_px,
) -> Optional[float]:
    """
    Calculate current/baseline eye-distance ratio.

    This is a relative measurement only.

    It does NOT estimate physical distance in centimeters.
    """

    if not _is_finite_positive_number(
        current_eye_distance_px
    ):
        return None

    if not _is_finite_positive_number(
        baseline_eye_distance_px
    ):
        return None

    return (
        float(current_eye_distance_px)
        /
        float(baseline_eye_distance_px)
    )


class ScreenDistancePolicy:
    """
    Stateful Screen Distance Policy.

    Responsibilities:
        - relative ratio
        - candidate threshold classification
        - temporal confirmation
        - hysteresis
        - data-gap handling

    It does NOT:
        - calculate posture risk
        - calculate RULA
        - estimate centimeters
        - send notifications
    """

    def __init__(
        self,
        config: Optional[
            ScreenDistancePolicyConfig
        ] = None,
    ):
        self.config = (
            config
            if config is not None
            else ScreenDistancePolicyConfig()
        )

        _validate_config(
            self.config
        )

        self.reset()

    def reset(self) -> None:
        """
        Reset runtime state.

        Baseline itself is NOT stored here.
        It must come from Personal Baseline.
        """

        self._state = STATE_NORMAL
        self._candidate_started_at = None
        self._last_timestamp = None

    @property
    def state(self) -> str:
        return self._state

    def _not_evaluated_result(
        self,
        reason: str,
        current_eye_distance_px=None,
        baseline_eye_distance_px=None,
    ) -> dict:
        """
        Build a NOT_EVALUATED result.

        Missing measurement must never be interpreted
        as NORMAL.
        """

        return {
            "contract_version": (
                SCREEN_DISTANCE_POLICY_VERSION
            ),
            "evaluated": False,
            "state": STATE_NOT_EVALUATED,
            "stable_state": self._state,
            "reason": reason,
            "current_eye_distance_px": (
                current_eye_distance_px
            ),
            "baseline_eye_distance_px": (
                baseline_eye_distance_px
            ),
            "ratio": None,
            "percent_change": None,
            "candidate_seconds": None,
            "enter_ratio": float(
                self.config.enter_ratio
            ),
            "exit_ratio": float(
                self.config.exit_ratio
            ),
            "confirmation_seconds": float(
                self.config.confirmation_seconds
            ),
            "threshold_status": (
                "candidate_policy"
            ),
        }

    def update(
        self,
        current_eye_distance_px,
        baseline_eye_distance_px,
        now: float,
    ) -> dict:
        """
        Evaluate one Screen Distance observation.

        NORMAL:
            ratio < enter_ratio
                -> NORMAL

            ratio >= enter_ratio
                -> PENDING until confirmation duration passes

        TOO_CLOSE:
            ratio > exit_ratio
                -> remain TOO_CLOSE

            ratio <= exit_ratio
                -> NORMAL

        Missing/invalid data:
            -> NOT_EVALUATED

        Data gaps do not become NORMAL automatically.
        """

        if isinstance(now, bool):
            raise ValueError(
                "now must be a finite number"
            )

        try:
            now = float(now)
        except (TypeError, ValueError):
            raise ValueError(
                "now must be a finite number"
            )

        if not math.isfinite(now):
            raise ValueError(
                "now must be a finite number"
            )

        if (
            self._last_timestamp is not None
            and now < self._last_timestamp
        ):
            raise ValueError(
                "now must not move backwards"
            )

        self._last_timestamp = now

        if not _is_finite_positive_number(
            current_eye_distance_px
        ):
            self._candidate_started_at = None

            return self._not_evaluated_result(
                reason=(
                    "CURRENT_EYE_DISTANCE_INVALID"
                ),
                current_eye_distance_px=(
                    current_eye_distance_px
                ),
                baseline_eye_distance_px=(
                    baseline_eye_distance_px
                ),
            )

        if not _is_finite_positive_number(
            baseline_eye_distance_px
        ):
            self._candidate_started_at = None

            return self._not_evaluated_result(
                reason=(
                    "BASELINE_EYE_DISTANCE_INVALID"
                ),
                current_eye_distance_px=(
                    current_eye_distance_px
                ),
                baseline_eye_distance_px=(
                    baseline_eye_distance_px
                ),
            )

        current_eye_distance_px = float(
            current_eye_distance_px
        )

        baseline_eye_distance_px = float(
            baseline_eye_distance_px
        )

        ratio = calculate_screen_distance_ratio(
            current_eye_distance_px=(
                current_eye_distance_px
            ),
            baseline_eye_distance_px=(
                baseline_eye_distance_px
            ),
        )

        percent_change = (
            ratio - 1.0
        ) * 100.0

        candidate_seconds = 0.0

        # ==================================================
        # Already TOO_CLOSE
        # ==================================================
        #
        # Hysteresis:
        #
        # We do not return to NORMAL at enter_ratio.
        # We require the lower exit_ratio.
        # ==================================================

        if self._state == STATE_TOO_CLOSE:

            self._candidate_started_at = None

            if ratio <= float(
                self.config.exit_ratio
            ):
                self._state = STATE_NORMAL

                output_state = (
                    STATE_NORMAL
                )

                reason = (
                    "RECOVERED_BELOW_EXIT_RATIO"
                )

            else:
                output_state = (
                    STATE_TOO_CLOSE
                )

                reason = (
                    "TOO_CLOSE_MAINTAINED"
                )

        # ==================================================
        # Currently NORMAL
        # ==================================================

        else:

            if ratio >= float(
                self.config.enter_ratio
            ):

                if (
                    self._candidate_started_at
                    is None
                ):
                    self._candidate_started_at = now

                candidate_seconds = max(
                    0.0,
                    now
                    -
                    self._candidate_started_at,
                )

                if (
                    candidate_seconds
                    >=
                    float(
                        self.config.confirmation_seconds
                    )
                ):
                    self._state = (
                        STATE_TOO_CLOSE
                    )

                    self._candidate_started_at = None

                    output_state = (
                        STATE_TOO_CLOSE
                    )

                    reason = (
                        "TOO_CLOSE_CONFIRMED"
                    )

                else:
                    output_state = (
                        STATE_PENDING
                    )

                    reason = (
                        "WAITING_FOR_CONFIRMATION"
                    )

            else:
                self._candidate_started_at = None

                output_state = (
                    STATE_NORMAL
                )

                reason = (
                    "BELOW_ENTER_RATIO"
                )

        return {
            "contract_version": (
                SCREEN_DISTANCE_POLICY_VERSION
            ),
            "evaluated": True,
            "state": output_state,
            "stable_state": self._state,
            "reason": reason,

            "current_eye_distance_px": (
                current_eye_distance_px
            ),

            "baseline_eye_distance_px": (
                baseline_eye_distance_px
            ),

            "ratio": float(
                ratio
            ),

            "percent_change": float(
                percent_change
            ),

            "candidate_seconds": float(
                candidate_seconds
            ),

            "enter_ratio": float(
                self.config.enter_ratio
            ),

            "exit_ratio": float(
                self.config.exit_ratio
            ),

            "confirmation_seconds": float(
                self.config.confirmation_seconds
            ),

            "threshold_status": (
                "candidate_policy"
            ),
        }