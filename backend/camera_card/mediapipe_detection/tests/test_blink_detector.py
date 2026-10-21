from pathlib import Path
import sys


# ==========================================================
# Project Root
# ==========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

sys.path.insert(
    0,
    str(BASE_DIR)
)


# ==========================================================
# Imports
# ==========================================================

from mediapipe_detection.eye.eye_state import (
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
)

from mediapipe_detection.eye.blink_detector import (
    BlinkDetector,
)


# ==========================================================
# Synthetic Open-eye References
#
# ใช้เพื่อจำลอง technical eye calibration
# ไม่ใช่ Personal Baseline
# ==========================================================

RIGHT_OPEN_REFERENCE = 0.30
LEFT_OPEN_REFERENCE = 0.30


# ==========================================================
# Helpers
# ==========================================================

def make_eye_state(
    right_state,
    left_state,
    calibrated=True
):

    # ======================================================
    # Combined State
    # ======================================================

    if (
        right_state == EYE_OPEN
        and
        left_state == EYE_OPEN
    ):

        combined_state = EYE_OPEN


    elif (
        right_state == EYE_CLOSED
        and
        left_state == EYE_CLOSED
    ):

        combined_state = EYE_CLOSED


    else:

        combined_state = EYE_UNKNOWN


    # ======================================================
    # Result compatible with EyeStateDetector
    # ======================================================

    return {

        "calibrated": (
            calibrated
        ),

        "right_eye_state": (
            right_state
        ),

        "left_eye_state": (
            left_state
        ),

        "eye_state": (
            combined_state
        ),

        "right_open_reference": (
            RIGHT_OPEN_REFERENCE
        ),

        "left_open_reference": (
            LEFT_OPEN_REFERENCE
        ),
    }


# ==========================================================
# Eye Measurement
#
# ratio =
#
# current openness
# ----------------
# open reference
#
#
# ดังนั้น:
#
# current openness =
# ratio * open reference
# ==========================================================

def make_eye_measurement(
    right_ratio,
    left_ratio
):

    if (
        right_ratio is None
        or
        left_ratio is None
    ):

        return None


    right_openness = (

        RIGHT_OPEN_REFERENCE
        *
        right_ratio
    )


    left_openness = (

        LEFT_OPEN_REFERENCE
        *
        left_ratio
    )


    return {

        "right_eye_openness": (
            right_openness
        ),

        "left_eye_openness": (
            left_openness
        ),

        "mean_eye_openness": (

            right_openness
            +
            left_openness

        ) / 2.0,
    }


# ==========================================================
# Step Detector
# ==========================================================

def step(
    detector,
    timestamp,

    right_state,
    left_state,

    right_ratio=None,
    left_ratio=None,

    calibrated=True
):

    eye_state_result = (
        make_eye_state(

            right_state,
            left_state,

            calibrated=calibrated
        )
    )


    # ======================================================
    # ถ้าไม่ได้กำหนด ratio
    # ให้สร้างค่าตาม state อัตโนมัติ
    # ======================================================

    if (
        right_ratio is None
        and
        left_ratio is None
    ):

        # --------------------------------------------------
        # UNKNOWN
        # --------------------------------------------------

        if (
            right_state == EYE_UNKNOWN
            or
            left_state == EYE_UNKNOWN
        ):

            eye_measurement = None


        else:

            # ------------------------------------------------
            # Default synthetic ratios
            #
            # OPEN   = 1.00
            # CLOSED = 0.08
            #
            # 0.08 ต่ำกว่า deep-close factor 0.12
            # จึงจำลอง true deep eye closure
            # ------------------------------------------------

            right_ratio = (

                1.00

                if right_state == EYE_OPEN

                else 0.08
            )


            left_ratio = (

                1.00

                if left_state == EYE_OPEN

                else 0.08
            )


            eye_measurement = (
                make_eye_measurement(

                    right_ratio,
                    left_ratio
                )
            )


    else:

        eye_measurement = (
            make_eye_measurement(

                right_ratio,
                left_ratio
            )
        )


    # ======================================================
    # IMPORTANT
    #
    # Blink Detector V2 ต้องรับทั้ง:
    #
    # eye_state_result
    # +
    # eye_measurement
    # ======================================================

    return detector.update(

        eye_state_result,

        eye_measurement=(
            eye_measurement
        ),

        timestamp=(
            timestamp
        )
    )


# ==========================================================
# Test 1 — NO BLINK
# ==========================================================

def test_no_blink():

    detector = BlinkDetector()


    result_1 = step(
        detector,
        0.00,
        EYE_OPEN,
        EYE_OPEN
    )


    result_2 = step(
        detector,
        0.50,
        EYE_OPEN,
        EYE_OPEN
    )


    return (

        result_1[
            "blink_event"
        ]
        is False

        and

        result_2[
            "blink_event"
        ]
        is False

        and

        result_2[
            "blink_count"
        ]
        ==
        0
    )


# ==========================================================
# Test 2 — ONE TRUE BLINK
#
# OPEN
#   ↓
# DEEP CLOSED
#   ↓
# OPEN
#
# duration = 0.15 sec
#
# depth = 0.08
# ==========================================================

def test_one_blink():

    detector = BlinkDetector()


    # OPEN baseline state
    step(
        detector,
        0.00,
        EYE_OPEN,
        EYE_OPEN
    )


    # Both eyes CLOSED deeply
    step(
        detector,
        0.10,
        EYE_CLOSED,
        EYE_CLOSED,
        right_ratio=0.08,
        left_ratio=0.08
    )


    # Still CLOSED
    step(
        detector,
        0.16,
        EYE_CLOSED,
        EYE_CLOSED,
        right_ratio=0.07,
        left_ratio=0.08
    )


    # Reopen
    result = step(
        detector,
        0.25,
        EYE_OPEN,
        EYE_OPEN,
        right_ratio=1.00,
        left_ratio=1.00
    )


    return (

        result[
            "blink_event"
        ]
        is True

        and

        result[
            "blink_count"
        ]
        ==
        1

        and

        result[
            "last_blink_duration"
        ]
        is not None
    )


# ==========================================================
# Test 3 — FIVE TRUE BLINKS
# ==========================================================

def test_five_blinks():

    detector = BlinkDetector()


    current_time = 0.0


    # Initial OPEN
    step(
        detector,
        current_time,
        EYE_OPEN,
        EYE_OPEN
    )


    detected_events = 0


    for _ in range(
        5
    ):

        # --------------------------------------------------
        # Separation between blinks
        # --------------------------------------------------

        current_time += 0.50


        step(
            detector,
            current_time,
            EYE_OPEN,
            EYE_OPEN
        )


        # --------------------------------------------------
        # Deep bilateral CLOSED
        # --------------------------------------------------

        current_time += 0.10


        step(
            detector,
            current_time,
            EYE_CLOSED,
            EYE_CLOSED,
            right_ratio=0.08,
            left_ratio=0.07
        )


        # --------------------------------------------------
        # Still CLOSED
        # --------------------------------------------------

        current_time += 0.06


        step(
            detector,
            current_time,
            EYE_CLOSED,
            EYE_CLOSED,
            right_ratio=0.07,
            left_ratio=0.08
        )


        # --------------------------------------------------
        # OPEN
        # --------------------------------------------------

        current_time += 0.10


        result = step(
            detector,
            current_time,
            EYE_OPEN,
            EYE_OPEN,
            right_ratio=1.00,
            left_ratio=1.00
        )


        if result[
            "blink_event"
        ]:

            detected_events += 1


    return (

        detected_events
        ==
        5

        and

        detector.blink_count
        ==
        5
    )


# ==========================================================
# Test 4 — SHALLOW BILATERAL CLOSED
#
# State บอก CLOSED ทั้งสองข้าง
# แต่ measurement ไม่ได้ปิดลึกพอ
#
# ratio = 0.20
#
# > deep-close factor 0.12
#
# ต้องไม่เป็น Blink
#
# นี่คือ test ใหม่ที่สำคัญที่สุดของ V2
# ==========================================================

def test_shallow_bilateral_reject():

    detector = BlinkDetector()


    step(
        detector,
        0.00,
        EYE_OPEN,
        EYE_OPEN
    )


    step(
        detector,
        0.10,
        EYE_CLOSED,
        EYE_CLOSED,
        right_ratio=0.20,
        left_ratio=0.18
    )


    step(
        detector,
        0.18,
        EYE_CLOSED,
        EYE_CLOSED,
        right_ratio=0.19,
        left_ratio=0.20
    )


    result = step(
        detector,
        0.28,
        EYE_OPEN,
        EYE_OPEN
    )


    return (

        result[
            "blink_event"
        ]
        is False

        and

        result[
            "blink_count"
        ]
        ==
        0

        and

        result.get(
            "reason"
        )
        ==
        "BILATERAL_DEPTH_REJECTED"
    )


# ==========================================================
# Test 5 — RIGHT WINK
#
# RIGHT CLOSED
# LEFT OPEN
#
# ต้องไม่เป็น Blink
# ==========================================================

def test_right_wink():

    detector = BlinkDetector()


    step(
        detector,
        0.00,
        EYE_OPEN,
        EYE_OPEN
    )


    step(
        detector,
        0.10,
        EYE_CLOSED,
        EYE_OPEN,
        right_ratio=0.05,
        left_ratio=1.00
    )


    step(
        detector,
        0.40,
        EYE_CLOSED,
        EYE_OPEN,
        right_ratio=0.05,
        left_ratio=1.00
    )


    result = step(
        detector,
        0.60,
        EYE_OPEN,
        EYE_OPEN
    )


    return (

        result[
            "blink_event"
        ]
        is False

        and

        result[
            "blink_count"
        ]
        ==
        0
    )


# ==========================================================
# Test 6 — LEFT WINK + DELAYED SQUINT
#
# LEFT closes first
#
# RIGHT closes much later
#
# Delay = 0.20 sec
#
# max close sync = 0.12 sec
#
# ต้อง reject
# ==========================================================

def test_left_wink_delayed_squint():

    detector = BlinkDetector()


    step(
        detector,
        0.00,
        EYE_OPEN,
        EYE_OPEN
    )


    # LEFT closes first
    step(
        detector,
        0.10,
        EYE_OPEN,
        EYE_CLOSED,
        right_ratio=1.00,
        left_ratio=0.05
    )


    # RIGHT follows too late
    step(
        detector,
        0.30,
        EYE_CLOSED,
        EYE_CLOSED,
        right_ratio=0.08,
        left_ratio=0.05
    )


    result = step(
        detector,
        0.45,
        EYE_OPEN,
        EYE_OPEN
    )


    return (

        result[
            "blink_event"
        ]
        is False

        and

        result[
            "blink_count"
        ]
        ==
        0
    )


# ==========================================================
# Test 7 — LONG CLOSURE
#
# CLOSED longer than 0.80 sec
#
# ต้องไม่เป็น Blink
# ==========================================================

def test_long_closure():

    detector = BlinkDetector()


    step(
        detector,
        0.00,
        EYE_OPEN,
        EYE_OPEN
    )


    # Start closure
    step(
        detector,
        0.10,
        EYE_CLOSED,
        EYE_CLOSED,
        right_ratio=0.05,
        left_ratio=0.05
    )


    # Candidate > 0.80 sec
    result_long = step(
        detector,
        0.95,
        EYE_CLOSED,
        EYE_CLOSED,
        right_ratio=0.05,
        left_ratio=0.05
    )


    # Open again
    result_open = step(
        detector,
        1.10,
        EYE_OPEN,
        EYE_OPEN
    )


    return (

        result_long[
            "blink_event"
        ]
        is False

        and

        result_open[
            "blink_event"
        ]
        is False

        and

        detector.blink_count
        ==
        0
    )


# ==========================================================
# Test 8 — UNKNOWN CANCEL
#
# OPEN
# ↓
# CLOSED Candidate
# ↓
# UNKNOWN
# ↓
# OPEN
#
# Candidate เดิมต้องถูกยกเลิก
# ==========================================================

def test_unknown_cancel():

    detector = BlinkDetector()


    step(
        detector,
        0.00,
        EYE_OPEN,
        EYE_OPEN
    )


    # Candidate starts
    step(
        detector,
        0.10,
        EYE_CLOSED,
        EYE_CLOSED,
        right_ratio=0.05,
        left_ratio=0.05
    )


    # Face / eye measurement lost
    result_unknown = step(
        detector,
        0.16,
        EYE_UNKNOWN,
        EYE_UNKNOWN
    )


    # Return OPEN
    result_open = step(
        detector,
        0.30,
        EYE_OPEN,
        EYE_OPEN
    )


    return (

        result_unknown[
            "blink_event"
        ]
        is False

        and

        result_open[
            "blink_event"
        ]
        is False

        and

        detector.blink_count
        ==
        0
    )


# ==========================================================
# Run Test Helper
# ==========================================================

def run_test(
    name,
    function
):

    try:

        passed = bool(
            function()
        )


    except Exception as error:

        print(
            f"{name}: ERROR"
        )


        print(
            "   ",
            type(error).__name__,
            ":",
            error
        )


        return False


    print(
        f"{name}:",
        (
            "PASS"
            if passed
            else "FAIL"
        )
    )


    return passed


# ==========================================================
# Main
# ==========================================================

def main():

    print(
        "\n"
        "================================================"
    )


    print(
        "POSTGUARD BLINK LOGIC TEST V2"
    )


    print(
        "================================================"
    )


    tests = [

        (
            "NO_BLINK",
            test_no_blink
        ),

        (
            "ONE_BLINK",
            test_one_blink
        ),

        (
            "FIVE_BLINKS",
            test_five_blinks
        ),

        (
            "SHALLOW_BILATERAL_REJECT",
            test_shallow_bilateral_reject
        ),

        (
            "RIGHT_WINK",
            test_right_wink
        ),

        (
            "LEFT_WINK_DELAYED_SQUINT",
            test_left_wink_delayed_squint
        ),

        (
            "LONG_CLOSURE",
            test_long_closure
        ),

        (
            "UNKNOWN_CANCEL",
            test_unknown_cancel
        ),
    ]


    passed_count = 0


    for (
        name,
        function
    ) in tests:

        if run_test(
            name,
            function
        ):

            passed_count += 1


    total = len(
        tests
    )


    print(
        "------------------------------------------------"
    )


    print(
        f"Logic Tests: {passed_count}/{total}"
    )


    if passed_count == total:

        print(
            "BLINK LOGIC TEST V2: PASS"
        )


    else:

        print(
            "BLINK LOGIC TEST V2: FAIL"
        )


    print(
        "================================================"
    )


    return (
        passed_count
        ==
        total
    )


# ==========================================================
# Entry
# ==========================================================

if __name__ == "__main__":

    success = main()


    if not success:

        print(
            "\nLogic test failed."
        )


        print(
            "Webcam validation will NOT start."
        )