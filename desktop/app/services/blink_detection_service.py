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


BLINK_DETECTION_SERVICE_VERSION = "1.1"

DEFAULT_MAX_CLOSED_SECONDS = 1.0


class BlinkDetectionService:
    """
    PostGuard runtime eye/blink adapter.

    Pipeline:

        DetectionService
              ↓
          face_points
              ↓
      calculate_eye_openness()
              ↓
      ┌──────────────────┐
      │                  │
    RIGHT              LEFT
    openness           openness
      │                  │
      ↓                  ↓
    OPEN/CLOSED       OPEN/CLOSED
      │                  │
      └────────┬─────────┘
               ↓
        Bilateral State
               ↓
        CLOSED -> OPEN
               ↓
            BLINK

    Important:

    - Blink ต้องเกิดจาก bilateral CLOSED -> bilateral OPEN
    - ปิดตาข้างเดียวไม่ใช่ Blink
    - Wink แสดงเป็นข้อมูล diagnostic/runtime
    - Eye feature ไม่เข้า Risk Evaluation
    - ไม่ตีความ fatigue หรือ drowsiness
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

    # ========================================================
    # RESET
    # ========================================================

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

    # ========================================================
    # WINK CLASSIFICATION
    # ========================================================

    @staticmethod
    def _classify_eye_pattern(
        *,
        right_eye_state: str,
        left_eye_state: str,
    ) -> str:
        """
        แยก pattern ของตาสองข้าง

        BOTH_OPEN
            ตาทั้งสองเปิด

        BOTH_CLOSED
            ตาทั้งสองปิด

        RIGHT_ONLY_CLOSED
            เฉพาะตาขวาปิด

        LEFT_ONLY_CLOSED
            เฉพาะตาซ้ายปิด

        UNKNOWN
            ข้อมูลไม่สมบูรณ์
        """

        if (
            right_eye_state == EYE_OPEN
            and
            left_eye_state == EYE_OPEN
        ):
            return "BOTH_OPEN"

        if (
            right_eye_state == EYE_CLOSED
            and
            left_eye_state == EYE_CLOSED
        ):
            return "BOTH_CLOSED"

        if (
            right_eye_state == EYE_CLOSED
            and
            left_eye_state == EYE_OPEN
        ):
            return "RIGHT_ONLY_CLOSED"

        if (
            right_eye_state == EYE_OPEN
            and
            left_eye_state == EYE_CLOSED
        ):
            return "LEFT_ONLY_CLOSED"

        return "UNKNOWN"

    # ========================================================
    # PROCESS DETECTION
    # ========================================================

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

        # ====================================================
        # FACE POINTS
        # ====================================================

        face_points = (
            detection_result.get(
                "face_points"
            )
            or {}
        )

        # ====================================================
        # EYE MEASUREMENT
        #
        # ของเดิม PostGuard แยก:
        #
        # right_eye_openness
        # left_eye_openness
        # ====================================================

        measurement = (
            calculate_eye_openness(
                face_points
            )
        )

        # ====================================================
        # EYE STATE
        # ====================================================

        eye_result = (
            self.eye_state_detector.update(
                measurement,
                timestamp=now_value,
            )
        )

        calibrated = (
            eye_result.get(
                "calibrated"
            )
            is True
        )

        eye_state = (
            eye_result.get(
                "eye_state",
                EYE_UNKNOWN,
            )
        )

        right_eye_state = (
            eye_result.get(
                "right_eye_state",
                EYE_UNKNOWN,
            )
        )

        left_eye_state = (
            eye_result.get(
                "left_eye_state",
                EYE_UNKNOWN,
            )
        )

        # ====================================================
        # EYE PATTERN
        # ====================================================

        eye_pattern = (
            self._classify_eye_pattern(
                right_eye_state=(
                    right_eye_state
                ),
                left_eye_state=(
                    left_eye_state
                ),
            )
        )

        # ====================================================
        # OPENNESS
        # ====================================================

        right_eye_openness = None
        left_eye_openness = None
        mean_eye_openness = None

        if isinstance(
            measurement,
            Mapping,
        ):

            right_eye_openness = (
                measurement.get(
                    "right_eye_openness"
                )
            )

            left_eye_openness = (
                measurement.get(
                    "left_eye_openness"
                )
            )

            mean_eye_openness = (
                measurement.get(
                    "mean_eye_openness"
                )
            )

        # ====================================================
        # BLINK EVENT
        # ====================================================

        blink_event = False
        blink_duration = None

        # ----------------------------------------------------
        # Bilateral CLOSED starts
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Bilateral CLOSED -> OPEN
        #
        # เท่านั้นที่ถือเป็น Blink
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # UNKNOWN
        #
        # รวมถึง:
        # - face loss
        # - landmark invalid
        # - left/right mismatch
        # - wink
        #
        # ต้องตัด blink continuity
        # ----------------------------------------------------

        elif (
            eye_state
            ==
            EYE_UNKNOWN
        ):

            self.closed_started_at = None

        # ====================================================
        # SAVE PREVIOUS BILATERAL STATE
        # ====================================================

        self.previous_state = (
            eye_state
        )

        # ====================================================
        # RESULT
        # ====================================================

        result = {
            "service_version": (
                BLINK_DETECTION_SERVICE_VERSION
            ),

            "timestamp_monotonic": (
                now_value
            ),

            # ------------------------------------------------
            # Calibration
            # ------------------------------------------------

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

            "calibration_samples": (
                eye_result.get(
                    "calibration_samples"
                )
            ),

            # ------------------------------------------------
            # Bilateral State
            # ------------------------------------------------

            "eye_state": (
                eye_state
            ),

            # ------------------------------------------------
            # Individual Eye State
            # ------------------------------------------------

            "right_eye_state": (
                right_eye_state
            ),

            "left_eye_state": (
                left_eye_state
            ),

            # ------------------------------------------------
            # Eye Pattern
            # ------------------------------------------------

            "eye_pattern": (
                eye_pattern
            ),

            "is_right_only_closed": (
                eye_pattern
                ==
                "RIGHT_ONLY_CLOSED"
            ),

            "is_left_only_closed": (
                eye_pattern
                ==
                "LEFT_ONLY_CLOSED"
            ),

            "is_bilateral_closed": (
                eye_pattern
                ==
                "BOTH_CLOSED"
            ),

            # ------------------------------------------------
            # Openness
            # ------------------------------------------------

            "right_eye_openness": (
                right_eye_openness
            ),

            "left_eye_openness": (
                left_eye_openness
            ),

            "mean_eye_openness": (
                mean_eye_openness
            ),

            "measurement": (
                measurement
            ),

            # ------------------------------------------------
            # Blink
            # ------------------------------------------------

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

        self.last_result = (
            result
        )

        return result

    # ========================================================
    # BLINK RATE
    # ========================================================

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