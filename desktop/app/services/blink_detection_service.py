from __future__ import annotations

import math
import time
from typing import Any, Mapping

from app.vision.mediapipe_detection.eye.eye_measurement import (
    calculate_eye_openness,
)
from app.vision.mediapipe_detection.eye.eye_state import (
    EyeStateDetector,
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
)


BLINK_DETECTION_SERVICE_VERSION = "1.0"

DEFAULT_MAX_CLOSED_SECONDS = 1.0


class BlinkDetectionService:
    """
    Runtime Blink Detection adapter.

    Pipeline:

        DetectionService.face_points
                ↓
        calculate_eye_openness()
                ↓
        EyeStateDetector
                ↓
        OPEN / CLOSED / UNKNOWN
                ↓
        CLOSED -> OPEN
                ↓
             Blink Event

    Important:
    - ไม่เกี่ยวกับ Risk Evaluation
    - ไม่เกี่ยวกับ Alert Policy
    - ไม่ตีความ fatigue/drowsiness
    - Blink count ใช้เพื่อ Session Summary เท่านั้น
    """

    def __init__(
        self,
        *,
        max_closed_seconds: float = (
            DEFAULT_MAX_CLOSED_SECONDS
        ),
    ) -> None:

        self.max_closed_seconds = float(
            max_closed_seconds
        )

        if (
            not math.isfinite(
                self.max_closed_seconds
            )
            or
            self.max_closed_seconds <= 0
        ):
            raise ValueError(
                "max_closed_seconds must be > 0"
            )

        self.eye_state_detector = (
            EyeStateDetector()
        )

        self.total_blinks = 0

        self.previous_state = (
            EYE_UNKNOWN
        )

        self.closed_started_at = None

        self.last_result = None

        self.reset(
            preserve_count=False
        )

    def reset(
        self,
        *,
        preserve_count: bool = False,
        now: float | None = None,
    ) -> None:

        if not preserve_count:
            self.total_blinks = 0

        if now is None:
            now = time.monotonic()

        self.eye_state_detector.reset()

        self.eye_state_detector.start_calibration(
            timestamp=float(now)
        )

        self.previous_state = (
            EYE_UNKNOWN
        )

        self.closed_started_at = None

        self.last_result = None

    def process_detection(
        self,
        detection_result: Mapping[str, Any],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:

        if not isinstance(
            detection_result,
            Mapping,
        ):
            raise ValueError(
                "detection_result must be mapping"
            )

        if now is None:
            now = time.monotonic()

        now_value = float(
            now
        )

        face_points = (
            detection_result.get(
                "face_points"
            )
            or {}
        )

        measurement = (
            calculate_eye_openness(
                face_points
            )
        )

        eye_result = (
            self.eye_state_detector.update(
                measurement,
                timestamp=now_value,
            )
        )

        eye_state = (
            eye_result.get(
                "eye_state",
                EYE_UNKNOWN,
            )
        )

        calibrated = (
            eye_result.get(
                "calibrated"
            )
            is True
        )

        blink_event = False

        blink_duration = None

        # ====================================================
        # CLOSED START
        # ====================================================

        if (
            calibrated
            and
            eye_state == EYE_CLOSED
            and
            self.previous_state
            != EYE_CLOSED
        ):
            self.closed_started_at = (
                now_value
            )

        # ====================================================
        # CLOSED -> OPEN = BLINK
        # ====================================================

        elif (
            calibrated
            and
            eye_state == EYE_OPEN
            and
            self.previous_state
            == EYE_CLOSED
            and
            self.closed_started_at
            is not None
        ):

            blink_duration = max(
                0.0,
                now_value
                -
                self.closed_started_at,
            )

            if (
                blink_duration
                <=
                self.max_closed_seconds
            ):
                self.total_blinks += 1

                blink_event = True

            self.closed_started_at = None

        # ====================================================
        # UNKNOWN
        # ====================================================

        elif (
            eye_state
            ==
            EYE_UNKNOWN
        ):
            self.closed_started_at = None

        self.previous_state = (
            eye_state
        )

        result = {
            "service_version": (
                BLINK_DETECTION_SERVICE_VERSION
            ),

            "timestamp_monotonic": (
                now_value
            ),

            "calibrated": (
                calibrated
            ),

            "calibration_status": (
                eye_result.get(
                    "calibration_status"
                )
            ),

            "calibration_progress": (
                eye_result.get(
                    "calibration_progress"
                )
            ),

            "eye_state": (
                eye_state
            ),

            "right_eye_state": (
                eye_result.get(
                    "right_eye_state"
                )
            ),

            "left_eye_state": (
                eye_result.get(
                    "left_eye_state"
                )
            ),

            "measurement": (
                measurement
            ),

            "blink_event": (
                blink_event
            ),

            "blink_duration_seconds": (
                blink_duration
            ),

            "blink_count": (
                self.total_blinks
            ),
        }

        self.last_result = result

        return result

    def blink_rate_per_minute(
        self,
        active_seconds: float | None,
    ) -> float | None:

        if (
            active_seconds is None
            or
            isinstance(
                active_seconds,
                bool,
            )
        ):
            return None

        try:
            seconds = float(
                active_seconds
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

        if (
            not math.isfinite(
                seconds
            )
            or
            seconds <= 0
        ):
            return None

        return (
            self.total_blinks
            /
            seconds
            *
            60.0
        )