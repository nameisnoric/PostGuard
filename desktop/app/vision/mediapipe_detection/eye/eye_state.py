import math
import time

from statistics import median


# ==========================================================
# Eye State Constants
# ==========================================================

EYE_OPEN = "OPEN"
EYE_CLOSED = "CLOSED"
EYE_UNKNOWN = "UNKNOWN"


# ==========================================================
# Calibration Status
# ==========================================================

CALIBRATION_NOT_STARTED = "NOT_STARTED"
CALIBRATION_RUNNING = "CALIBRATING"
CALIBRATION_READY = "READY"


# ==========================================================
# Prototype Parameters
#
# IMPORTANT:
#
# ค่านี้เป็น Prototype Detection Parameters
#
# ไม่ใช่:
#
# - Medical threshold
# - Eye fatigue threshold
# - Drowsiness threshold
#
# ต้องผ่าน validation ของ PostGuard ก่อน LOCK
# ==========================================================

DEFAULT_CALIBRATION_SECONDS = 3.0

DEFAULT_MIN_CALIBRATION_SAMPLES = 30


# Openness ลดลงเหลือ 55%
# ของ Open Reference
# จึงเปลี่ยน OPEN -> CLOSED
DEFAULT_CLOSE_FACTOR = 0.55


# ตอน CLOSED
# ต้องกลับขึ้นถึง 70%
# จึงเปลี่ยน CLOSED -> OPEN
DEFAULT_REOPEN_FACTOR = 0.70


# ==========================================================
# Numeric Helper
# ==========================================================

def _is_finite_number(
    value
):
    """
    ตรวจว่าค่าเป็น finite number

    ป้องกัน:
    - None
    - NaN
    - inf
    - invalid type
    """

    if value is None:

        return False


    try:

        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError
    ):

        return False


# ==========================================================
# Eye State Detector
# ==========================================================

class EyeStateDetector:
    """
    Eye Openness
        ↓
    Open-Eye Calibration
        ↓
    Relative Threshold
        ↓
    Hysteresis
        ↓
    OPEN / CLOSED / UNKNOWN


    การรวมตาทั้งสองข้าง:

    RIGHT CLOSED
    AND
    LEFT CLOSED
        ↓
    CLOSED


    RIGHT OPEN
    AND
    LEFT OPEN
        ↓
    OPEN


    ข้างหนึ่ง OPEN
    อีกข้าง CLOSED
        ↓
    UNKNOWN


    เหตุผล:

    การขยิบตาข้างเดียว
    ต้องไม่ถูกมองว่าเป็น
    bilateral eye closure
    """

    def __init__(
        self,
        calibration_seconds=(
            DEFAULT_CALIBRATION_SECONDS
        ),
        min_calibration_samples=(
            DEFAULT_MIN_CALIBRATION_SAMPLES
        ),
        close_factor=(
            DEFAULT_CLOSE_FACTOR
        ),
        reopen_factor=(
            DEFAULT_REOPEN_FACTOR
        ),
    ):

        # ==================================================
        # Configuration
        # ==================================================

        self.calibration_seconds = float(
            calibration_seconds
        )


        self.min_calibration_samples = int(
            min_calibration_samples
        )


        self.close_factor = float(
            close_factor
        )


        self.reopen_factor = float(
            reopen_factor
        )


        # ==================================================
        # Validate Configuration
        # ==================================================

        if self.calibration_seconds <= 0:

            raise ValueError(
                "calibration_seconds must be > 0"
            )


        if self.min_calibration_samples <= 0:

            raise ValueError(
                "min_calibration_samples must be > 0"
            )


        if (
            self.close_factor <= 0
            or
            self.reopen_factor <= 0
        ):

            raise ValueError(
                "Eye state factors must be > 0"
            )


        if (
            self.close_factor
            >=
            self.reopen_factor
        ):

            raise ValueError(
                "close_factor must be smaller "
                "than reopen_factor"
            )


        # ==================================================
        # Runtime
        # ==================================================

        self.reset()


    # ======================================================
    # Reset
    # ======================================================

    def reset(
        self
    ):
        """
        Reset Calibration + Eye State ทั้งหมด
        """

        # --------------------------------------------------
        # Calibration
        # --------------------------------------------------

        self.calibration_status = (
            CALIBRATION_NOT_STARTED
        )


        self.calibration_started_at = None


        self.right_calibration_samples = []

        self.left_calibration_samples = []


        # --------------------------------------------------
        # Open Reference
        # --------------------------------------------------

        self.right_open_reference = None

        self.left_open_reference = None


        # --------------------------------------------------
        # Thresholds
        # --------------------------------------------------

        self.right_close_threshold = None

        self.left_close_threshold = None


        self.right_reopen_threshold = None

        self.left_reopen_threshold = None


        # --------------------------------------------------
        # Current State
        # --------------------------------------------------

        self.right_eye_state = (
            EYE_UNKNOWN
        )

        self.left_eye_state = (
            EYE_UNKNOWN
        )


    # ======================================================
    # Start Calibration
    # ======================================================

    def start_calibration(
        self,
        timestamp=None
    ):
        """
        เริ่ม Open-Eye Calibration ใหม่

        ผู้ใช้ต้อง:
        - มองตรง
        - เปิดตาธรรมชาติ
        - พยายามไม่กระพริบ
        """

        if timestamp is None:

            timestamp = (
                time.perf_counter()
            )


        # Reset ค่าเก่าก่อน
        self.reset()


        self.calibration_started_at = float(
            timestamp
        )


        self.calibration_status = (
            CALIBRATION_RUNNING
        )


    # ======================================================
    # Validate Measurement
    # ======================================================

    def _measurement_valid(
        self,
        measurement
    ):

        if measurement is None:

            return False


        required_keys = (
            "right_eye_openness",
            "left_eye_openness",
        )


        for key in required_keys:

            if key not in measurement:

                return False


            value = measurement[
                key
            ]


            if not _is_finite_number(
                value
            ):

                return False


            if float(
                value
            ) < 0:

                return False


        return True


    # ======================================================
    # Calibration Progress
    # ======================================================

    def _get_calibration_progress(
        self,
        timestamp
    ):

        if (
            self.calibration_status
            ==
            CALIBRATION_READY
        ):

            return 1.0


        if (
            self.calibration_started_at
            is None
        ):

            return 0.0


        elapsed = max(
            0.0,
            float(timestamp)
            -
            self.calibration_started_at
        )


        return min(
            elapsed
            /
            self.calibration_seconds,
            1.0
        )


    # ======================================================
    # Calibration Sample Count
    # ======================================================

    def _get_calibration_sample_count(
        self
    ):

        return min(
            len(
                self.right_calibration_samples
            ),
            len(
                self.left_calibration_samples
            ),
        )


    # ======================================================
    # Finish Calibration
    # ======================================================

    def _finish_calibration(
        self
    ):
        """
        ใช้ median เป็น Open Reference

        Median ทนต่อ frame ที่มี blink หลุดเข้ามา
        ได้ดีกว่า mean
        """

        sample_count = (
            self._get_calibration_sample_count()
        )


        if (
            sample_count
            <
            self.min_calibration_samples
        ):

            return False


        # ==================================================
        # Open Reference
        # ==================================================

        right_reference = float(
            median(
                self.right_calibration_samples
            )
        )


        left_reference = float(
            median(
                self.left_calibration_samples
            )
        )


        # ==================================================
        # Reference Validation
        # ==================================================

        if (
            not _is_finite_number(
                right_reference
            )
            or
            not _is_finite_number(
                left_reference
            )
        ):

            return False


        if (
            right_reference <= 1e-6
            or
            left_reference <= 1e-6
        ):

            return False


        # ==================================================
        # Save Reference
        # ==================================================

        self.right_open_reference = (
            right_reference
        )


        self.left_open_reference = (
            left_reference
        )


        # ==================================================
        # CLOSED Threshold
        #
        # OPEN -> CLOSED
        # ==================================================

        self.right_close_threshold = (
            right_reference
            *
            self.close_factor
        )


        self.left_close_threshold = (
            left_reference
            *
            self.close_factor
        )


        # ==================================================
        # REOPEN Threshold
        #
        # CLOSED -> OPEN
        # ==================================================

        self.right_reopen_threshold = (
            right_reference
            *
            self.reopen_factor
        )


        self.left_reopen_threshold = (
            left_reference
            *
            self.reopen_factor
        )


        # ==================================================
        # Initial State
        #
        # Calibration ทำตอนเปิดตา
        # ดังนั้น initial state = OPEN
        # ==================================================

        self.right_eye_state = (
            EYE_OPEN
        )


        self.left_eye_state = (
            EYE_OPEN
        )


        self.calibration_status = (
            CALIBRATION_READY
        )


        return True


    # ======================================================
    # Single Eye Classification
    # ======================================================

    def _classify_single_eye(
        self,
        openness,
        previous_state,
        close_threshold,
        reopen_threshold
    ):
        """
        Hysteresis State Machine


        ถ้า state เดิม OPEN:

        OPEN
          ↓
        openness <= close_threshold
          ↓
        CLOSED


        ถ้า state เดิม CLOSED:

        CLOSED
          ↓
        openness >= reopen_threshold
          ↓
        OPEN


        จุดสำคัญ:

        close_threshold
        <
        reopen_threshold

        ทำให้ค่าที่แกว่งแถว threshold
        ไม่เปลี่ยน OPEN/CLOSED ไปมาทุก frame
        """

        # ==================================================
        # Previous = OPEN
        # ==================================================

        if (
            previous_state
            ==
            EYE_OPEN
        ):

            if (
                openness
                <=
                close_threshold
            ):

                return EYE_CLOSED


            return EYE_OPEN


        # ==================================================
        # Previous = CLOSED
        # ==================================================

        if (
            previous_state
            ==
            EYE_CLOSED
        ):

            if (
                openness
                >=
                reopen_threshold
            ):

                return EYE_OPEN


            return EYE_CLOSED


        # ==================================================
        # Previous = UNKNOWN
        #
        # ต้องอยู่ชัดเจนด้านใดด้านหนึ่ง
        # ==================================================

        if (
            openness
            <=
            close_threshold
        ):

            return EYE_CLOSED


        if (
            openness
            >=
            reopen_threshold
        ):

            return EYE_OPEN


        return EYE_UNKNOWN


    # ======================================================
    # Combined Bilateral State
    # ======================================================

    def _combine_eye_states(
        self
    ):
        """
        รวม state ของตาทั้งสองข้าง

        BOTH OPEN
        -> OPEN

        BOTH CLOSED
        -> CLOSED

        MIXED
        -> UNKNOWN
        """

        if (
            self.right_eye_state
            ==
            EYE_OPEN

            and

            self.left_eye_state
            ==
            EYE_OPEN
        ):

            return EYE_OPEN


        if (
            self.right_eye_state
            ==
            EYE_CLOSED

            and

            self.left_eye_state
            ==
            EYE_CLOSED
        ):

            return EYE_CLOSED


        return EYE_UNKNOWN


    # ======================================================
    # Build Result
    # ======================================================

    def _build_result(
        self,
        timestamp
    ):

        combined_state = (
            self._combine_eye_states()
        )


        return {

            # ----------------------------------------------
            # Calibration
            # ----------------------------------------------

            "calibration_status": (
                self.calibration_status
            ),

            "calibrated": (
                self.calibration_status
                ==
                CALIBRATION_READY
            ),

            "calibration_progress": (
                self._get_calibration_progress(
                    timestamp
                )
            ),

            "calibration_samples": (
                self._get_calibration_sample_count()
            ),


            # ----------------------------------------------
            # Reference
            # ----------------------------------------------

            "right_open_reference": (
                self.right_open_reference
            ),

            "left_open_reference": (
                self.left_open_reference
            ),


            # ----------------------------------------------
            # CLOSED Threshold
            # ----------------------------------------------

            "right_close_threshold": (
                self.right_close_threshold
            ),

            "left_close_threshold": (
                self.left_close_threshold
            ),


            # ----------------------------------------------
            # REOPEN Threshold
            # ----------------------------------------------

            "right_reopen_threshold": (
                self.right_reopen_threshold
            ),

            "left_reopen_threshold": (
                self.left_reopen_threshold
            ),


            # ----------------------------------------------
            # Individual Eye State
            # ----------------------------------------------

            "right_eye_state": (
                self.right_eye_state
            ),

            "left_eye_state": (
                self.left_eye_state
            ),


            # ----------------------------------------------
            # Bilateral State
            # ----------------------------------------------

            "eye_state": (
                combined_state
            ),
        }


    # ======================================================
    # Update
    # ======================================================

    def update(
        self,
        measurement,
        timestamp=None
    ):
        """
        รับผลจาก eye_measurement.py
        แล้วคืน Eye State
        """

        if timestamp is None:

            timestamp = (
                time.perf_counter()
            )


        timestamp = float(
            timestamp
        )


        # ==================================================
        # Measurement Invalid
        #
        # Face หาย / landmark หาย / measurement ใช้ไม่ได้
        #
        # ต้องเป็น UNKNOWN
        #
        # ห้ามตีความเป็น CLOSED
        # ==================================================

        if not self._measurement_valid(
            measurement
        ):

            self.right_eye_state = (
                EYE_UNKNOWN
            )


            self.left_eye_state = (
                EYE_UNKNOWN
            )


            return self._build_result(
                timestamp
            )


        # ==================================================
        # Get Current Openness
        # ==================================================

        right_openness = float(
            measurement[
                "right_eye_openness"
            ]
        )


        left_openness = float(
            measurement[
                "left_eye_openness"
            ]
        )


        # ==================================================
        # Calibration NOT Started
        # ==================================================

        if (
            self.calibration_status
            ==
            CALIBRATION_NOT_STARTED
        ):

            self.right_eye_state = (
                EYE_UNKNOWN
            )


            self.left_eye_state = (
                EYE_UNKNOWN
            )


            return self._build_result(
                timestamp
            )


        # ==================================================
        # Calibration Running
        # ==================================================

        if (
            self.calibration_status
            ==
            CALIBRATION_RUNNING
        ):

            # ----------------------------------------------
            # เก็บตัวอย่างตาเปิด
            # ----------------------------------------------

            self.right_calibration_samples.append(
                right_openness
            )


            self.left_calibration_samples.append(
                left_openness
            )


            elapsed = (
                timestamp
                -
                self.calibration_started_at
            )


            sample_count = (
                self._get_calibration_sample_count()
            )


            # ----------------------------------------------
            # ต้องครบทั้ง:
            #
            # 1. เวลา
            # 2. จำนวน sample ขั้นต่ำ
            # ----------------------------------------------

            if (
                elapsed
                >=
                self.calibration_seconds

                and

                sample_count
                >=
                self.min_calibration_samples
            ):

                self._finish_calibration()


            # ----------------------------------------------
            # Calibration ยังไม่เสร็จ
            # ----------------------------------------------

            if (
                self.calibration_status
                !=
                CALIBRATION_READY
            ):

                self.right_eye_state = (
                    EYE_UNKNOWN
                )


                self.left_eye_state = (
                    EYE_UNKNOWN
                )


            return self._build_result(
                timestamp
            )


        # ==================================================
        # READY
        # ==================================================

        self.right_eye_state = (
            self._classify_single_eye(

                openness=(
                    right_openness
                ),

                previous_state=(
                    self.right_eye_state
                ),

                close_threshold=(
                    self.right_close_threshold
                ),

                reopen_threshold=(
                    self.right_reopen_threshold
                ),
            )
        )


        self.left_eye_state = (
            self._classify_single_eye(

                openness=(
                    left_openness
                ),

                previous_state=(
                    self.left_eye_state
                ),

                close_threshold=(
                    self.left_close_threshold
                ),

                reopen_threshold=(
                    self.left_reopen_threshold
                ),
            )
        )


        return self._build_result(
            timestamp
        )