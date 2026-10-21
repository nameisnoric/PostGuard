import math
import time


from mediapipe_detection.eye.eye_state import (
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
)


# ==========================================================
# Detector States
# ==========================================================

EYE_CLOSURE_IDLE = "IDLE"

EYE_CLOSURE_TRACKING = "TRACKING"

EYE_CLOSURE_LONG = "LONG_CLOSURE"


# ==========================================================
# Prototype Parameters
#
# IMPORTANT:
#
# These are prototype detection parameters.
#
# They are NOT medical thresholds.
# They are NOT drowsiness thresholds.
#
# LONG_CLOSURE_SECONDS:
# ต้องปิดตาลึกต่อเนื่องนานเท่าไร
#
# DEEP_CLOSE_FACTOR:
# current openness / open reference
#
# จาก diagnostic:
#
# TRUE_LONG_CLOSURE
# R median ~ 0.041
# L median ~ 0.069
#
# LEFT_WINK
# R median ~ 0.162
# L median ~ 0.164
#
# จึงทดลอง boundary = 0.12
#
# ต้องผ่าน webcam validation ก่อน LOCK
# ==========================================================

DEFAULT_LONG_CLOSURE_SECONDS = 1.0

DEFAULT_DEEP_CLOSE_FACTOR = 0.12


# ==========================================================
# Numeric Validation
# ==========================================================

def _is_finite_number(
    value
):

    return (

        isinstance(
            value,
            (int, float)
        )

        and

        math.isfinite(
            float(value)
        )
    )


# ==========================================================
# Eye Closure Detector
# ==========================================================

class EyeClosureDetector:

    def __init__(
        self,
        long_closure_seconds=(
            DEFAULT_LONG_CLOSURE_SECONDS
        ),
        deep_close_factor=(
            DEFAULT_DEEP_CLOSE_FACTOR
        ),
    ):

        # ==================================================
        # Validate Parameters
        # ==================================================

        if (
            not _is_finite_number(
                long_closure_seconds
            )

            or

            long_closure_seconds
            <=
            0
        ):

            raise ValueError(
                "long_closure_seconds must be > 0"
            )


        if (
            not _is_finite_number(
                deep_close_factor
            )

            or

            deep_close_factor
            <=
            0

            or

            deep_close_factor
            >=
            1
        ):

            raise ValueError(
                "deep_close_factor must be between 0 and 1"
            )


        # ==================================================
        # Configuration
        # ==================================================

        self.long_closure_seconds = float(
            long_closure_seconds
        )


        self.deep_close_factor = float(
            deep_close_factor
        )


        # ==================================================
        # Runtime
        # ==================================================

        self.reset()


    # ======================================================
    # Reset
    # ======================================================

    def reset(
        self,
        preserve_count=False
    ):

        # --------------------------------------------------
        # Count
        # --------------------------------------------------

        if (
            not preserve_count

            or

            not hasattr(
                self,
                "long_closure_count"
            )
        ):

            self.long_closure_count = 0


        # --------------------------------------------------
        # Current Closure
        # --------------------------------------------------

        self.closure_active = False

        self.closure_started_at = None


        # --------------------------------------------------
        # One Event Per Continuous Closure
        # --------------------------------------------------

        self.long_event_reported = False


        # --------------------------------------------------
        # Last Event
        # --------------------------------------------------

        self.last_long_closure_time = None

        self.last_long_closure_duration = None


        # --------------------------------------------------
        # Latest Diagnostic Values
        # --------------------------------------------------

        self.right_depth_ratio = None

        self.left_depth_ratio = None

        self.deep_bilateral_closure = False


        self.last_reason = (
            "RESET"
        )


    # ======================================================
    # Timestamp
    # ======================================================

    def _get_timestamp(
        self,
        timestamp
    ):

        if timestamp is None:

            return float(
                time.perf_counter()
            )


        return float(
            timestamp
        )


    # ======================================================
    # Clear Current Closure
    # ======================================================

    def _clear_current_closure(
        self
    ):

        self.closure_active = False

        self.closure_started_at = None

        self.long_event_reported = False


    # ======================================================
    # Closure Duration
    # ======================================================

    def _get_closure_duration(
        self,
        timestamp
    ):

        if (
            not self.closure_active

            or

            self.closure_started_at
            is None
        ):

            return 0.0


        return max(

            0.0,

            float(timestamp)
            -
            float(
                self.closure_started_at
            )
        )


    # ======================================================
    # Calculate Normalized Eye Depth
    #
    # ratio =
    #
    # current eye openness
    # --------------------
    # open-eye reference
    #
    # OPEN:
    # ratio ≈ 1.0
    #
    # Deep CLOSED:
    # ratio เข้าใกล้ 0
    # ======================================================

    def _calculate_depth_ratios(
        self,
        eye_state_result,
        eye_measurement
    ):

        # --------------------------------------------------
        # Measurement Required
        # --------------------------------------------------

        if not isinstance(
            eye_measurement,
            dict
        ):

            return (
                None,
                None,
                False,
                "MISSING_EYE_MEASUREMENT"
            )


        # --------------------------------------------------
        # Current Openness
        # --------------------------------------------------

        right_openness = (
            eye_measurement.get(
                "right_eye_openness"
            )
        )


        left_openness = (
            eye_measurement.get(
                "left_eye_openness"
            )
        )


        # --------------------------------------------------
        # Personal Open References
        #
        # มาจาก technical open-eye calibration
        # ไม่ใช่ Personal Baseline ของ posture
        # --------------------------------------------------

        right_reference = (
            eye_state_result.get(
                "right_open_reference"
            )
        )


        left_reference = (
            eye_state_result.get(
                "left_open_reference"
            )
        )


        # --------------------------------------------------
        # Validate
        # --------------------------------------------------

        values = (

            right_openness,
            left_openness,

            right_reference,
            left_reference,
        )


        if not all(
            _is_finite_number(
                value
            )
            for value in values
        ):

            return (
                None,
                None,
                False,
                "INVALID_DEPTH_INPUT"
            )


        right_openness = float(
            right_openness
        )


        left_openness = float(
            left_openness
        )


        right_reference = float(
            right_reference
        )


        left_reference = float(
            left_reference
        )


        if (
            right_reference
            <=
            0

            or

            left_reference
            <=
            0
        ):

            return (
                None,
                None,
                False,
                "INVALID_OPEN_REFERENCE"
            )


        # --------------------------------------------------
        # Normalized Ratios
        # --------------------------------------------------

        right_ratio = (

            right_openness
            /
            right_reference
        )


        left_ratio = (

            left_openness
            /
            left_reference
        )


        # --------------------------------------------------
        # Deep Bilateral Closure
        #
        # BOTH eyes must be deeply closed.
        #
        # ไม่ใช้แค่:
        #
        # Eye State == CLOSED
        #
        # เพราะ diagnostic พบว่า Wink
        # สามารถทำให้ Eye State ทั้งคู่ CLOSED ได้
        # --------------------------------------------------

        deep_bilateral = (

            right_ratio
            <=
            self.deep_close_factor

            and

            left_ratio
            <=
            self.deep_close_factor
        )


        return (
            float(
                right_ratio
            ),

            float(
                left_ratio
            ),

            bool(
                deep_bilateral
            ),

            "OK"
        )


    # ======================================================
    # Build Result
    # ======================================================

    def _build_result(
        self,
        timestamp,
        long_closure_event=False,
        reason=None
    ):

        closure_duration = (
            self._get_closure_duration(
                timestamp
            )
        )


        # --------------------------------------------------
        # Detector State
        # --------------------------------------------------

        if (
            self.closure_active

            and

            self.long_event_reported
        ):

            detector_state = (
                EYE_CLOSURE_LONG
            )


        elif self.closure_active:

            detector_state = (
                EYE_CLOSURE_TRACKING
            )


        else:

            detector_state = (
                EYE_CLOSURE_IDLE
            )


        return {

            # ------------------------------------------------
            # Closure Runtime
            # ------------------------------------------------

            "eye_closure_active": bool(
                self.closure_active
            ),

            "eye_closure_duration": float(
                closure_duration
            ),


            # ------------------------------------------------
            # Event
            # ------------------------------------------------

            "long_closure_event": bool(
                long_closure_event
            ),

            "long_closure_count": int(
                self.long_closure_count
            ),

            "long_closure_detected": bool(
                self.long_event_reported
            ),


            # ------------------------------------------------
            # Bilateral Depth
            # ------------------------------------------------

            "right_depth_ratio": (
                self.right_depth_ratio
            ),

            "left_depth_ratio": (
                self.left_depth_ratio
            ),

            "deep_bilateral_closure": bool(
                self.deep_bilateral_closure
            ),

            "deep_close_factor": float(
                self.deep_close_factor
            ),


            # ------------------------------------------------
            # Detector
            # ------------------------------------------------

            "detector_state": (
                detector_state
            ),

            "closure_started_at": (
                self.closure_started_at
            ),

            "long_closure_threshold": float(
                self.long_closure_seconds
            ),


            # ------------------------------------------------
            # Last Event
            # ------------------------------------------------

            "last_long_closure_time": (
                self.last_long_closure_time
            ),

            "last_long_closure_duration": (
                self.last_long_closure_duration
            ),


            # ------------------------------------------------
            # Diagnostic
            # ------------------------------------------------

            "reason": (

                reason

                if reason is not None

                else self.last_reason
            ),
        }


    # ======================================================
    # Update
    # ======================================================

    def update(
        self,
        eye_state_result,
        eye_measurement=None,
        timestamp=None
    ):

        now = (
            self._get_timestamp(
                timestamp
            )
        )


        long_closure_event = False


        # Reset latest depth diagnostic
        self.right_depth_ratio = None

        self.left_depth_ratio = None

        self.deep_bilateral_closure = False


        # ==================================================
        # 1. Validate Eye State Input
        # ==================================================

        if not isinstance(
            eye_state_result,
            dict
        ):

            self._clear_current_closure()


            self.last_reason = (
                "INVALID_INPUT"
            )


            return self._build_result(
                timestamp=now,
                reason=self.last_reason
            )


        # ==================================================
        # 2. Calibration Required
        # ==================================================

        if not eye_state_result.get(
            "calibrated",
            False
        ):

            self._clear_current_closure()


            self.last_reason = (
                "NOT_CALIBRATED"
            )


            return self._build_result(
                timestamp=now,
                reason=self.last_reason
            )


        # ==================================================
        # 3. Combined Eye State
        # ==================================================

        eye_state = (
            eye_state_result.get(
                "eye_state"
            )
        )


        if eye_state not in {

            EYE_OPEN,
            EYE_CLOSED,
            EYE_UNKNOWN,

        }:

            self._clear_current_closure()


            self.last_reason = (
                "INVALID_EYE_STATE"
            )


            return self._build_result(
                timestamp=now,
                reason=self.last_reason
            )


        # ==================================================
        # 4. UNKNOWN
        #
        # Missing face / landmarks must not bridge time.
        # ==================================================

        if eye_state == EYE_UNKNOWN:

            was_active = (
                self.closure_active
            )


            self._clear_current_closure()


            if was_active:

                self.last_reason = (
                    "UNKNOWN_CANCELLED_CLOSURE"
                )

            else:

                self.last_reason = (
                    "UNKNOWN_STATE"
                )


            return self._build_result(
                timestamp=now,
                reason=self.last_reason
            )


        # ==================================================
        # 5. OPEN
        # ==================================================

        if eye_state == EYE_OPEN:

            was_active = (
                self.closure_active
            )


            self._clear_current_closure()


            if was_active:

                self.last_reason = (
                    "CLOSURE_ENDED"
                )

            else:

                self.last_reason = (
                    "EYES_OPEN"
                )


            return self._build_result(
                timestamp=now,
                reason=self.last_reason
            )


        # ==================================================
        # 6. CLOSED
        #
        # Eye State CLOSED อย่างเดียวไม่พออีกแล้ว
        # ==================================================

        (
            right_ratio,
            left_ratio,
            deep_bilateral,
            depth_reason,

        ) = self._calculate_depth_ratios(

            eye_state_result,
            eye_measurement
        )


        self.right_depth_ratio = (
            right_ratio
        )


        self.left_depth_ratio = (
            left_ratio
        )


        self.deep_bilateral_closure = (
            deep_bilateral
        )


        # ==================================================
        # 7. Measurement Missing / Invalid
        #
        # Fail safe:
        # ไม่สร้าง Long Closure ถ้าไม่มีข้อมูลจริง
        # ==================================================

        if (
            depth_reason
            !=
            "OK"
        ):

            self._clear_current_closure()


            self.last_reason = (
                depth_reason
            )


            return self._build_result(
                timestamp=now,
                reason=self.last_reason
            )


        # ==================================================
        # 8. CLOSED but NOT deeply closed in BOTH eyes
        #
        # นี่คือสิ่งที่ใช้ reject Wink false positive
        # ==================================================

        if not deep_bilateral:

            was_active = (
                self.closure_active
            )


            self._clear_current_closure()


            if was_active:

                self.last_reason = (
                    "DEEP_CLOSURE_INTERRUPTED"
                )

            else:

                self.last_reason = (
                    "CLOSED_NOT_DEEP_BILATERAL"
                )


            return self._build_result(
                timestamp=now,
                reason=self.last_reason
            )


        # ==================================================
        # 9. Deep Bilateral Closure Starts
        # ==================================================

        if not self.closure_active:

            self.closure_active = True


            self.closure_started_at = (
                now
            )


            self.long_event_reported = False


            self.last_reason = (
                "DEEP_CLOSURE_STARTED"
            )


            return self._build_result(
                timestamp=now,
                reason=self.last_reason
            )


        # ==================================================
        # 10. Continue Deep Bilateral Closure
        # ==================================================

        closure_duration = (
            self._get_closure_duration(
                now
            )
        )


        # ==================================================
        # 11. Long Closure Event
        #
        # Event only once per continuous closure
        # ==================================================

        if (
            closure_duration
            >=
            self.long_closure_seconds

            and

            not self.long_event_reported
        ):

            long_closure_event = True


            self.long_event_reported = True


            self.long_closure_count += 1


            self.last_long_closure_time = (
                now
            )


            self.last_long_closure_duration = float(
                closure_duration
            )


            self.last_reason = (
                "LONG_CLOSURE_DETECTED"
            )


        elif self.long_event_reported:

            self.last_reason = (
                "LONG_CLOSURE_CONTINUING"
            )


        else:

            self.last_reason = (
                "DEEP_CLOSURE_TRACKING"
            )


        # ==================================================
        # Return
        # ==================================================

        return self._build_result(

            timestamp=now,

            long_closure_event=(
                long_closure_event
            ),

            reason=self.last_reason
        )