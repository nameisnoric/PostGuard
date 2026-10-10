import math
import time


from mediapipe_detection.eye.eye_state import (
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
)


# ==========================================================
# Blink Detector States
# ==========================================================

BLINK_IDLE = "IDLE"

BLINK_CANDIDATE = "CANDIDATE"


# ==========================================================
# Existing Prototype Parameters
#
# ไม่ใช่ medical thresholds
# ==========================================================

DEFAULT_MIN_BLINK_SECONDS = 0.05

DEFAULT_MAX_BLINK_SECONDS = 0.80

DEFAULT_MAX_CLOSE_SYNC_SECONDS = 0.12


# ==========================================================
# Bilateral Deep-Close Gate
#
# Diagnostic 2026-10-09:
#
# TRUE_BLINK:
#   deepest bilateral max
#   0.0573
#   0.1008
#   0.0728
#   0.1036
#   0.0957
#
# False / intended wink:
#   0.1249
#   0.1738
#   0.2413
#   ...
#
# Prototype boundary:
#   0.12
#
# IMPORTANT:
# - ไม่ใช่ค่าทางการแพทย์
# - ต้องผ่าน webcam validation ก่อน LOCK
# ==========================================================

DEFAULT_DEEP_CLOSE_FACTOR = 0.12


# ==========================================================
# Number Validation
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
# Blink Detector
# ==========================================================

class BlinkDetector:

    def __init__(
        self,
        min_blink_seconds=(
            DEFAULT_MIN_BLINK_SECONDS
        ),
        max_blink_seconds=(
            DEFAULT_MAX_BLINK_SECONDS
        ),
        max_close_sync_seconds=(
            DEFAULT_MAX_CLOSE_SYNC_SECONDS
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
                min_blink_seconds
            )

            or

            min_blink_seconds
            <=
            0
        ):

            raise ValueError(
                "min_blink_seconds must be > 0"
            )


        if (
            not _is_finite_number(
                max_blink_seconds
            )

            or

            max_blink_seconds
            <=
            min_blink_seconds
        ):

            raise ValueError(
                "max_blink_seconds must be > min_blink_seconds"
            )


        if (
            not _is_finite_number(
                max_close_sync_seconds
            )

            or

            max_close_sync_seconds
            < 0
        ):

            raise ValueError(
                "max_close_sync_seconds must be >= 0"
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

        self.min_blink_seconds = float(
            min_blink_seconds
        )


        self.max_blink_seconds = float(
            max_blink_seconds
        )


        self.max_close_sync_seconds = float(
            max_close_sync_seconds
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
        # Counter
        # --------------------------------------------------

        if (
            not preserve_count

            or

            not hasattr(
                self,
                "blink_count"
            )
        ):

            self.blink_count = 0


        # --------------------------------------------------
        # Previous Per-eye State
        # --------------------------------------------------

        self.previous_right_state = None

        self.previous_left_state = None


        # --------------------------------------------------
        # Per-eye Closing Transition
        # --------------------------------------------------

        self.right_closed_at = None

        self.left_closed_at = None


        # --------------------------------------------------
        # Blink Candidate
        # --------------------------------------------------

        self.candidate_active = False

        self.candidate_started_at = None


        # --------------------------------------------------
        # Deepest Bilateral Closure Seen
        #
        # ค่า max(R_ratio, L_ratio)
        # ที่ต่ำที่สุดภายใน candidate
        # --------------------------------------------------

        self.candidate_min_bilateral_max = None


        # --------------------------------------------------
        # Suppress
        #
        # ใช้หลัง candidate ยาวเกิน max
        # เพื่อไม่ให้ event เก่า bridge ไป event ใหม่
        # --------------------------------------------------

        self.suppress_until_open = False


        # --------------------------------------------------
        # Last Event
        # --------------------------------------------------

        self.last_blink_time = None

        self.last_blink_duration = None


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
    # Clear Candidate
    # ======================================================

    def _clear_candidate(
        self
    ):

        self.candidate_active = False

        self.candidate_started_at = None

        self.candidate_min_bilateral_max = None


    # ======================================================
    # Clear Closing Transitions
    # ======================================================

    def _clear_close_times(
        self
    ):

        self.right_closed_at = None

        self.left_closed_at = None


    # ======================================================
    # Calculate Normalized Bilateral Depth
    #
    # right_ratio =
    #
    # current right openness
    # ----------------------
    # right open reference
    #
    #
    # left_ratio =
    #
    # current left openness
    # ---------------------
    # left open reference
    #
    #
    # bilateral_max =
    #
    # max(right_ratio, left_ratio)
    #
    #
    # ถ้า bilateral_max ต่ำ
    # หมายความว่าทั้งสองตาปิดลึกพร้อมกัน
    # ======================================================

    def _calculate_bilateral_depth(
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
                None,
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
        # Open-eye Technical Calibration
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
                None,
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
                None,
                "INVALID_OPEN_REFERENCE"
            )


        # --------------------------------------------------
        # Normalize
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


        bilateral_max = max(
            right_ratio,
            left_ratio
        )


        return (
            float(
                right_ratio
            ),

            float(
                left_ratio
            ),

            float(
                bilateral_max
            ),

            "OK"
        )


    # ======================================================
    # Build Result
    # ======================================================

    def _build_result(
        self,
        blink_event=False,
        reason=None
    ):

        depth_gate_passed = False


        if (
            self.candidate_min_bilateral_max
            is not None
        ):

            depth_gate_passed = (

                self.candidate_min_bilateral_max
                <=
                self.deep_close_factor
            )


        return {

            # ------------------------------------------------
            # Blink Event
            # ------------------------------------------------

            "blink_event": bool(
                blink_event
            ),

            "blink_count": int(
                self.blink_count
            ),


            # ------------------------------------------------
            # Last Blink
            # ------------------------------------------------

            "last_blink_time": (
                self.last_blink_time
            ),

            "last_blink_duration": (
                self.last_blink_duration
            ),


            # ------------------------------------------------
            # Detector Runtime
            # ------------------------------------------------

            "detector_state": (

                BLINK_CANDIDATE

                if self.candidate_active

                else BLINK_IDLE
            ),

            "candidate_started_at": (
                self.candidate_started_at
            ),

            "suppress_until_open": bool(
                self.suppress_until_open
            ),


            # ------------------------------------------------
            # Candidate Depth
            # ------------------------------------------------

            "candidate_min_bilateral_max": (
                self.candidate_min_bilateral_max
            ),

            "deep_close_factor": float(
                self.deep_close_factor
            ),

            "depth_gate_passed": bool(
                depth_gate_passed
            ),


            # ------------------------------------------------
            # Parameters
            # ------------------------------------------------

            "min_blink_seconds": float(
                self.min_blink_seconds
            ),

            "max_blink_seconds": float(
                self.max_blink_seconds
            ),

            "max_close_sync_seconds": float(
                self.max_close_sync_seconds
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


        blink_event = False


        # ==================================================
        # 1. Validate Input
        # ==================================================

        if not isinstance(
            eye_state_result,
            dict
        ):

            self._clear_candidate()

            self._clear_close_times()


            self.previous_right_state = None

            self.previous_left_state = None


            self.last_reason = (
                "INVALID_INPUT"
            )


            return self._build_result(
                reason=self.last_reason
            )


        # ==================================================
        # 2. Calibration Required
        # ==================================================

        if not eye_state_result.get(
            "calibrated",
            False
        ):

            self._clear_candidate()

            self._clear_close_times()


            self.previous_right_state = None

            self.previous_left_state = None


            self.last_reason = (
                "NOT_CALIBRATED"
            )


            return self._build_result(
                reason=self.last_reason
            )


        # ==================================================
        # 3. Per-eye States
        # ==================================================

        right_state = (
            eye_state_result.get(
                "right_eye_state",
                EYE_UNKNOWN
            )
        )


        left_state = (
            eye_state_result.get(
                "left_eye_state",
                EYE_UNKNOWN
            )
        )


        valid_states = {

            EYE_OPEN,
            EYE_CLOSED,
            EYE_UNKNOWN,
        }


        if (
            right_state
            not in
            valid_states

            or

            left_state
            not in
            valid_states
        ):

            self._clear_candidate()

            self._clear_close_times()


            self.previous_right_state = None

            self.previous_left_state = None


            self.last_reason = (
                "INVALID_EYE_STATE"
            )


            return self._build_result(
                reason=self.last_reason
            )


        # ==================================================
        # 4. UNKNOWN
        #
        # Landmark/face loss ต้องยกเลิก candidate
        # เพื่อไม่ให้เวลา bridge ข้าม missing frame
        # ==================================================

        if (
            right_state
            ==
            EYE_UNKNOWN

            or

            left_state
            ==
            EYE_UNKNOWN
        ):

            self._clear_candidate()

            self._clear_close_times()


            self.suppress_until_open = False


            self.previous_right_state = (
                right_state
            )

            self.previous_left_state = (
                left_state
            )


            self.last_reason = (
                "UNKNOWN_CANCELLED"
            )


            return self._build_result(
                reason=self.last_reason
            )


        # ==================================================
        # 5. Detect OPEN -> CLOSED Transitions
        # ==================================================

        right_close_transition = (

            self.previous_right_state
            ==
            EYE_OPEN

            and

            right_state
            ==
            EYE_CLOSED
        )


        left_close_transition = (

            self.previous_left_state
            ==
            EYE_OPEN

            and

            left_state
            ==
            EYE_CLOSED
        )


        if right_close_transition:

            self.right_closed_at = (
                now
            )


        if left_close_transition:

            self.left_closed_at = (
                now
            )


        # ==================================================
        # 6. Clear stale transition when an eye reopens
        #
        # ทำเฉพาะตอนยังไม่มี candidate
        # ==================================================

        if not self.candidate_active:

            if (
                self.previous_right_state
                ==
                EYE_CLOSED

                and

                right_state
                ==
                EYE_OPEN
            ):

                self.right_closed_at = None


            if (
                self.previous_left_state
                ==
                EYE_CLOSED

                and

                left_state
                ==
                EYE_OPEN
            ):

                self.left_closed_at = None


        # ==================================================
        # 7. Both OPEN
        # ==================================================

        both_open = (

            right_state
            ==
            EYE_OPEN

            and

            left_state
            ==
            EYE_OPEN
        )


        if both_open:

            # ==============================================
            # Suppressed Event Finished
            # ==============================================

            if self.suppress_until_open:

                self.suppress_until_open = False


                self._clear_candidate()

                self._clear_close_times()


                self.previous_right_state = (
                    right_state
                )

                self.previous_left_state = (
                    left_state
                )


                self.last_reason = (
                    "SUPPRESSION_CLEARED"
                )


                return self._build_result(
                    reason=self.last_reason
                )


            # ==============================================
            # Finish Blink Candidate
            # ==============================================

            if (
                self.candidate_active

                and

                self.candidate_started_at
                is not None
            ):

                blink_duration = (

                    now

                    -

                    self.candidate_started_at
                )


                # ------------------------------------------
                # Duration Gate
                # ------------------------------------------

                duration_valid = (

                    blink_duration
                    >=
                    self.min_blink_seconds

                    and

                    blink_duration
                    <=
                    self.max_blink_seconds
                )


                # ------------------------------------------
                # Bilateral Depth Gate
                # ------------------------------------------

                depth_valid = (

                    self.candidate_min_bilateral_max
                    is not None

                    and

                    self.candidate_min_bilateral_max
                    <=
                    self.deep_close_factor
                )


                # ------------------------------------------
                # Valid Blink
                # ------------------------------------------

                if (
                    duration_valid

                    and

                    depth_valid
                ):

                    blink_event = True


                    self.blink_count += 1


                    self.last_blink_time = (
                        now
                    )


                    self.last_blink_duration = float(
                        blink_duration
                    )


                    reason = (
                        "BLINK_DETECTED"
                    )


                elif not duration_valid:

                    if (
                        blink_duration
                        <
                        self.min_blink_seconds
                    ):

                        reason = (
                            "BLINK_TOO_SHORT"
                        )


                    else:

                        reason = (
                            "BLINK_TOO_LONG"
                        )


                else:

                    reason = (
                        "BILATERAL_DEPTH_REJECTED"
                    )


                # ------------------------------------------
                # Save diagnostic value before clear
                # ------------------------------------------

                candidate_depth = (
                    self.candidate_min_bilateral_max
                )


                # ------------------------------------------
                # Clear Candidate
                # ------------------------------------------

                self._clear_candidate()

                self._clear_close_times()


                # restore latest depth for result
                self.candidate_min_bilateral_max = (
                    candidate_depth
                )


                self.previous_right_state = (
                    right_state
                )

                self.previous_left_state = (
                    left_state
                )


                self.last_reason = (
                    reason
                )


                result = (
                    self._build_result(

                        blink_event=(
                            blink_event
                        ),

                        reason=(
                            reason
                        )
                    )
                )


                # หลัง build แล้วค่อย clear diagnostic
                self.candidate_min_bilateral_max = (
                    None
                )


                return result


            # ==============================================
            # Nothing Happening
            # ==============================================

            self._clear_close_times()


            self.previous_right_state = (
                right_state
            )

            self.previous_left_state = (
                left_state
            )


            self.last_reason = (
                "EYES_OPEN"
            )


            return self._build_result(
                reason=self.last_reason
            )


        # ==================================================
        # 8. Suppression
        # ==================================================

        if self.suppress_until_open:

            self.previous_right_state = (
                right_state
            )

            self.previous_left_state = (
                left_state
            )


            self.last_reason = (
                "SUPPRESSED_UNTIL_OPEN"
            )


            return self._build_result(
                reason=self.last_reason
            )


        # ==================================================
        # 9. Both CLOSED
        # ==================================================

        both_closed = (

            right_state
            ==
            EYE_CLOSED

            and

            left_state
            ==
            EYE_CLOSED
        )


        if both_closed:

            # ==============================================
            # Candidate not started yet
            # ==============================================

            if not self.candidate_active:

                # ------------------------------------------
                # Need both transition timestamps
                # ------------------------------------------

                if (
                    self.right_closed_at
                    is None

                    or

                    self.left_closed_at
                    is None
                ):

                    self.previous_right_state = (
                        right_state
                    )

                    self.previous_left_state = (
                        left_state
                    )


                    self.last_reason = (
                        "WAITING_CLOSE_TRANSITIONS"
                    )


                    return self._build_result(
                        reason=self.last_reason
                    )


                # ------------------------------------------
                # Closing Synchronization
                # ------------------------------------------

                close_sync = abs(

                    self.right_closed_at

                    -

                    self.left_closed_at
                )


                if (
                    close_sync
                    >
                    self.max_close_sync_seconds
                ):

                    # --------------------------------------
                    # This bilateral close is too
                    # asynchronous to be a Blink Candidate.
                    # --------------------------------------

                    self._clear_close_times()


                    self.previous_right_state = (
                        right_state
                    )

                    self.previous_left_state = (
                        left_state
                    )


                    self.last_reason = (
                        "CLOSE_SYNC_REJECTED"
                    )


                    return self._build_result(
                        reason=self.last_reason
                    )


                # ------------------------------------------
                # Start Candidate
                # ------------------------------------------

                self.candidate_active = True


                self.candidate_started_at = min(

                    self.right_closed_at,

                    self.left_closed_at
                )


                self.candidate_min_bilateral_max = (
                    None
                )


            # ==============================================
            # Update Candidate Depth
            # ==============================================

            (
                right_ratio,
                left_ratio,
                bilateral_max,
                depth_reason,

            ) = self._calculate_bilateral_depth(

                eye_state_result,

                eye_measurement
            )


            if (
                depth_reason
                ==
                "OK"

                and

                bilateral_max
                is not None
            ):

                if (
                    self.candidate_min_bilateral_max
                    is None

                    or

                    bilateral_max
                    <
                    self.candidate_min_bilateral_max
                ):

                    self.candidate_min_bilateral_max = (
                        bilateral_max
                    )


            # ==============================================
            # Candidate Duration
            # ==============================================

            candidate_duration = (

                now

                -

                self.candidate_started_at
            )


            # ==============================================
            # Too Long
            #
            # Long eye closure ไม่ใช่ normal blink
            # =================================================

            if (
                candidate_duration
                >
                self.max_blink_seconds
            ):

                self._clear_candidate()

                self._clear_close_times()


                self.suppress_until_open = True


                self.previous_right_state = (
                    right_state
                )

                self.previous_left_state = (
                    left_state
                )


                self.last_reason = (
                    "CANDIDATE_TOO_LONG"
                )


                return self._build_result(
                    reason=self.last_reason
                )


            # ==============================================
            # Candidate Continuing
            # ==============================================

            self.previous_right_state = (
                right_state
            )

            self.previous_left_state = (
                left_state
            )


            if (
                self.candidate_min_bilateral_max
                is None
            ):

                self.last_reason = (
                    "CANDIDATE_NO_DEPTH"
                )


            elif (
                self.candidate_min_bilateral_max
                <=
                self.deep_close_factor
            ):

                self.last_reason = (
                    "CANDIDATE_DEEP_BILATERAL"
                )


            else:

                self.last_reason = (
                    "CANDIDATE_SHALLOW"
                )


            return self._build_result(
                reason=self.last_reason
            )


        # ==================================================
        # 10. Mixed OPEN / CLOSED
        #
        # ไม่ถือเป็น Blink Event
        #
        # แต่ยังเก็บ transition timestamp เพื่อรอดูว่า
        # อีกตาจะ CLOSED ภายใน sync window หรือไม่
        # ==================================================

        self.previous_right_state = (
            right_state
        )


        self.previous_left_state = (
            left_state
        )


        self.last_reason = (
            "ASYMMETRIC_EYE_STATE"
        )


        return self._build_result(
            reason=self.last_reason
        )