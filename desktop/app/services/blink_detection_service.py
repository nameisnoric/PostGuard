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
    - Blink Detection แยกจาก Posture Risk
    - ไม่ถูกส่งเข้า Risk Evaluation
    - ไม่ถูกส่งเข้า Alert Policy
    - ไม่ตีความ fatigue / drowsiness
    - Blink count ใช้เป็น Session wellness metric
    """

    def __init__(
        self,
        *,
        max_closed_seconds: float = DEFAULT_MAX_CLOSED_SECONDS,
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
        """
        Reset temporal Blink state.

        preserve_count=False
            ใช้ตอนเริ่ม Session ใหม่ / จบ Session

        preserve_count=True
            ใช้ตอน Pause / Resume
            เพื่อตัด temporal continuity
            แต่ไม่ทำให้จำนวน Blink ของ Session หาย
        """

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
    # EYE PATTERN
    # ========================================================

    @staticmethod
    def _eye_pattern(
        right_state: str | None,
        left_state: str | None,
    ) -> str:
        """
        แปลงสถานะตาซ้าย/ขวาเป็นรูปแบบที่ UI ใช้

        BOTH_OPEN
        BOTH_CLOSED
        RIGHT_ONLY_CLOSED
        LEFT_ONLY_CLOSED
        UNKNOWN
        """

        if (
            right_state == EYE_OPEN
            and
            left_state == EYE_OPEN
        ):
            return "BOTH_OPEN"

        if (
            right_state == EYE_CLOSED
            and
            left_state == EYE_CLOSED
        ):
            return "BOTH_CLOSED"

        if (
            right_state == EYE_CLOSED
            and
            left_state == EYE_OPEN
        ):
            return "RIGHT_ONLY_CLOSED"

        if (
            right_state == EYE_OPEN
            and
            left_state == EYE_CLOSED
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
        # 1. FACE LANDMARKS
        # ====================================================

        face_points = (
            detection_result.get(
                "face_points"
            )
            or {}
        )

        # ====================================================
        # 2. EYE OPENNESS MEASUREMENT
        # ====================================================

        measurement = (
            calculate_eye_openness(
                face_points
            )
        )

        # ====================================================
        # 3. EYE STATE
        # ====================================================

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

        calibrated = (
            eye_result.get(
                "calibrated"
            )
            is True
        )

        # ====================================================
        # 4. EXPOSE EYE OPENNESS TO MONITORING UI
        #
        # เดิม measurement มีค่าเหล่านี้อยู่แล้ว
        # แต่ไม่ได้ expose ที่ระดับบนของ result
        # ทำให้ MonitoringPage อ่านไม่เจอ
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
        # 5. EYE PATTERN FOR UI
        # ====================================================

        eye_pattern = (
            self._eye_pattern(
                right_eye_state,
                left_eye_state,
            )
        )

        # ====================================================
        # 6. BLINK STATE MACHINE
        # ====================================================

        blink_event = False

        blink_duration = None

        # ----------------------------------------------------
        # CLOSED START
        # ----------------------------------------------------

        if (
            calibrated
            and
            eye_state == EYE_CLOSED
            and
            self.previous_state != EYE_CLOSED
        ):

            self.closed_started_at = (
                now_value
            )

        # ----------------------------------------------------
        # CLOSED -> OPEN = BLINK
        # ----------------------------------------------------

        elif (
            calibrated
            and
            eye_state == EYE_OPEN
            and
            self.previous_state == EYE_CLOSED
            and
            self.closed_started_at is not None
        ):

            blink_duration = max(
                0.0,
                now_value
                -
                self.closed_started_at,
            )

            # การปิดตานานเกิน max_closed_seconds
            # ไม่ถือเป็น Blink ปกติ
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
        # landmark หาย / face หาย
        # ต้องตัด continuity เพื่อไม่สร้าง Blink ปลอม
        # ----------------------------------------------------

        elif (
            eye_state
            ==
            EYE_UNKNOWN
        ):

            self.closed_started_at = None

        self.previous_state = (
            eye_state
        )

        # ====================================================
        # 7. RESULT CONTRACT
        # ====================================================

        result = {

            "service_version": (
                BLINK_DETECTION_SERVICE_VERSION
            ),

            "timestamp_monotonic": (
                now_value
            ),

            # ------------------------------------------------
            # CALIBRATION
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
            # EYE STATE
            # ------------------------------------------------

            "eye_state": (
                eye_state
            ),

            "right_eye_state": (
                right_eye_state
            ),

            "left_eye_state": (
                left_eye_state
            ),

            "eye_pattern": (
                eye_pattern
            ),

            # ------------------------------------------------
            # EYE OPENNESS
            #
            # Expose โดยตรงเพื่อให้ MonitoringPage
            # ใช้งานได้โดยไม่ต้องรู้ internal measurement
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

            # เก็บ raw measurement ไว้สำหรับ
            # debug / validation / camera test
            "measurement": (
                measurement
            ),

            # ------------------------------------------------
            # REFERENCE / THRESHOLDS
            # ------------------------------------------------

            "right_open_reference": (
                eye_result.get(
                    "right_open_reference"
                )
            ),

            "left_open_reference": (
                eye_result.get(
                    "left_open_reference"
                )
            ),

            "right_close_threshold": (
                eye_result.get(
                    "right_close_threshold"
                )
            ),

            "left_close_threshold": (
                eye_result.get(
                    "left_close_threshold"
                )
            ),

            "right_reopen_threshold": (
                eye_result.get(
                    "right_reopen_threshold"
                )
            ),

            "left_reopen_threshold": (
                eye_result.get(
                    "left_reopen_threshold"
                )
            ),

            # ------------------------------------------------
            # BLINK
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

        self.last_result = result

        return result

    # ========================================================
    # BLINK RATE
    # ========================================================

    def blink_rate_per_minute(
        self,
        active_seconds: float | None,
    ) -> float | None:
        """
        Blink Rate = Blink Count / Active Minutes

        active_seconds ต้องไม่รวม Pause time
        """

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