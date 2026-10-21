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
# Eye State
# ==========================================================

from mediapipe_detection.eye.eye_state import (
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
)


# ==========================================================
# Eye Closure
# ==========================================================

from mediapipe_detection.eye.eye_closure import (
    EyeClosureDetector
)


# ==========================================================
# Prototype Parameters
# ==========================================================

LONG_CLOSURE_SECONDS = 1.0

DEEP_CLOSE_FACTOR = 0.12


# ==========================================================
# Synthetic Eye State
# ==========================================================

def make_eye_state(
    eye_state,
    calibrated=True,
    right_reference=0.35,
    left_reference=0.35
):

    return {

        "calibrated": calibrated,

        "eye_state": (
            eye_state
        ),

        "right_open_reference": (
            right_reference
        ),

        "left_open_reference": (
            left_reference
        ),
    }


# ==========================================================
# Synthetic Eye Measurement
# ==========================================================

def make_measurement(
    right_ratio,
    left_ratio,
    right_reference=0.35,
    left_reference=0.35
):

    return {

        "right_eye_openness": (

            right_reference
            *
            right_ratio
        ),

        "left_eye_openness": (

            left_reference
            *
            left_ratio
        ),
    }


# ==========================================================
# Feed Helper
# ==========================================================

def feed(
    detector,
    timestamp,
    eye_state,
    right_ratio,
    left_ratio
):

    state_result = (
        make_eye_state(
            eye_state
        )
    )


    measurement = (
        make_measurement(
            right_ratio,
            left_ratio
        )
    )


    return detector.update(

        state_result,

        eye_measurement=(
            measurement
        ),

        timestamp=(
            timestamp
        )
    )


# ==========================================================
# Main
# ==========================================================

def main():

    print(
        "\n"
        "========================================================"
    )


    print(
        "POSTGUARD LONG EYE CLOSURE LOGIC TEST V2"
    )


    print(
        "========================================================"
    )


    results = []


    # ======================================================
    # TEST 1
    # OPEN_ONLY
    # ======================================================

    detector = EyeClosureDetector(

        long_closure_seconds=(
            LONG_CLOSURE_SECONDS
        ),

        deep_close_factor=(
            DEEP_CLOSE_FACTOR
        ),
    )


    result = feed(
        detector,
        0.0,
        EYE_OPEN,
        1.0,
        1.0
    )


    passed = (

        result[
            "long_closure_event"
        ]
        is False

        and

        result[
            "eye_closure_active"
        ]
        is False

        and

        detector.long_closure_count
        ==
        0
    )


    results.append(
        (
            "OPEN_ONLY",
            passed
        )
    )


    # ======================================================
    # TEST 2
    #
    # SHALLOW_BILATERAL_CLOSED
    #
    # จำลองกรณี Wink ที่ Eye State ทั้งสองข้าง
    # กลายเป็น CLOSED
    #
    # แต่ normalized depth ~0.16
    #
    # ต้องไม่เริ่ม Long Closure
    # ======================================================

    detector = EyeClosureDetector(

        long_closure_seconds=(
            LONG_CLOSURE_SECONDS
        ),

        deep_close_factor=(
            DEEP_CLOSE_FACTOR
        ),
    )


    feed(
        detector,
        0.00,
        EYE_OPEN,
        1.0,
        1.0
    )


    feed(
        detector,
        0.10,
        EYE_CLOSED,
        0.16,
        0.16
    )


    result = feed(
        detector,
        1.50,
        EYE_CLOSED,
        0.16,
        0.16
    )


    passed = (

        result[
            "long_closure_event"
        ]
        is False

        and

        result[
            "deep_bilateral_closure"
        ]
        is False

        and

        result[
            "eye_closure_active"
        ]
        is False

        and

        detector.long_closure_count
        ==
        0
    )


    results.append(
        (
            "SHALLOW_BILATERAL_CLOSED",
            passed
        )
    )


    # ======================================================
    # TEST 3
    # TRUE_DEEP_LONG_CLOSURE
    # ======================================================

    detector = EyeClosureDetector(

        long_closure_seconds=(
            LONG_CLOSURE_SECONDS
        ),

        deep_close_factor=(
            DEEP_CLOSE_FACTOR
        ),
    )


    feed(
        detector,
        0.00,
        EYE_OPEN,
        1.0,
        1.0
    )


    feed(
        detector,
        0.10,
        EYE_CLOSED,
        0.05,
        0.07
    )


    feed(
        detector,
        0.60,
        EYE_CLOSED,
        0.04,
        0.08
    )


    result = feed(
        detector,
        1.15,
        EYE_CLOSED,
        0.05,
        0.07
    )


    passed = (

        result[
            "long_closure_event"
        ]
        is True

        and

        result[
            "deep_bilateral_closure"
        ]
        is True

        and

        result[
            "long_closure_count"
        ]
        ==
        1
    )


    results.append(
        (
            "TRUE_DEEP_LONG_CLOSURE",
            passed
        )
    )


    # ======================================================
    # TEST 4
    # EVENT_ONCE_ONLY
    # ======================================================

    result_1 = feed(
        detector,
        1.30,
        EYE_CLOSED,
        0.05,
        0.07
    )


    result_2 = feed(
        detector,
        1.60,
        EYE_CLOSED,
        0.04,
        0.06
    )


    passed = (

        result_1[
            "long_closure_event"
        ]
        is False

        and

        result_2[
            "long_closure_event"
        ]
        is False

        and

        detector.long_closure_count
        ==
        1
    )


    results.append(
        (
            "EVENT_ONCE_ONLY",
            passed
        )
    )


    # ======================================================
    # TEST 5
    # UNILATERAL_DEEP_RIGHT
    #
    # ขวาปิดลึก
    # ซ้ายยังเปิด/หรี่
    #
    # ต้องไม่เป็น Long Closure
    # ======================================================

    detector = EyeClosureDetector(

        long_closure_seconds=(
            LONG_CLOSURE_SECONDS
        ),

        deep_close_factor=(
            DEEP_CLOSE_FACTOR
        ),
    )


    feed(
        detector,
        0.00,
        EYE_OPEN,
        1.0,
        1.0
    )


    feed(
        detector,
        0.10,
        EYE_CLOSED,
        0.05,
        0.60
    )


    result = feed(
        detector,
        1.50,
        EYE_CLOSED,
        0.05,
        0.60
    )


    passed = (

        result[
            "long_closure_event"
        ]
        is False

        and

        result[
            "deep_bilateral_closure"
        ]
        is False

        and

        detector.long_closure_count
        ==
        0
    )


    results.append(
        (
            "UNILATERAL_DEEP_RIGHT",
            passed
        )
    )


    # ======================================================
    # TEST 6
    # REOPEN_SECOND_LONG
    # ======================================================

    detector = EyeClosureDetector(

        long_closure_seconds=(
            LONG_CLOSURE_SECONDS
        ),

        deep_close_factor=(
            DEEP_CLOSE_FACTOR
        ),
    )


    # First closure
    feed(
        detector,
        0.00,
        EYE_CLOSED,
        0.05,
        0.06
    )


    first_event = feed(
        detector,
        1.10,
        EYE_CLOSED,
        0.05,
        0.06
    )


    # Reopen
    feed(
        detector,
        1.30,
        EYE_OPEN,
        1.0,
        1.0
    )


    # Second closure
    feed(
        detector,
        2.00,
        EYE_CLOSED,
        0.04,
        0.07
    )


    second_event = feed(
        detector,
        3.10,
        EYE_CLOSED,
        0.04,
        0.07
    )


    passed = (

        first_event[
            "long_closure_event"
        ]
        is True

        and

        second_event[
            "long_closure_event"
        ]
        is True

        and

        detector.long_closure_count
        ==
        2
    )


    results.append(
        (
            "REOPEN_SECOND_LONG",
            passed
        )
    )


    # ======================================================
    # TEST 7
    # UNKNOWN_CANCEL
    # ======================================================

    detector = EyeClosureDetector(

        long_closure_seconds=(
            LONG_CLOSURE_SECONDS
        ),

        deep_close_factor=(
            DEEP_CLOSE_FACTOR
        ),
    )


    feed(
        detector,
        0.00,
        EYE_CLOSED,
        0.05,
        0.07
    )


    feed(
        detector,
        0.50,
        EYE_CLOSED,
        0.05,
        0.07
    )


    unknown_result = feed(
        detector,
        0.60,
        EYE_UNKNOWN,
        0.05,
        0.07
    )


    new_closed = feed(
        detector,
        0.80,
        EYE_CLOSED,
        0.05,
        0.07
    )


    result = feed(
        detector,
        1.30,
        EYE_CLOSED,
        0.05,
        0.07
    )


    passed = (

        unknown_result[
            "eye_closure_active"
        ]
        is False

        and

        new_closed[
            "eye_closure_active"
        ]
        is True

        and

        result[
            "long_closure_event"
        ]
        is False

        and

        detector.long_closure_count
        ==
        0
    )


    results.append(
        (
            "UNKNOWN_CANCEL",
            passed
        )
    )


    # ======================================================
    # TEST 8
    # MISSING_MEASUREMENT_FAIL_SAFE
    # ======================================================

    detector = EyeClosureDetector(

        long_closure_seconds=(
            LONG_CLOSURE_SECONDS
        ),

        deep_close_factor=(
            DEEP_CLOSE_FACTOR
        ),
    )


    state = (
        make_eye_state(
            EYE_CLOSED
        )
    )


    result = detector.update(

        state,

        eye_measurement=None,

        timestamp=0.0
    )


    passed = (

        result[
            "long_closure_event"
        ]
        is False

        and

        result[
            "eye_closure_active"
        ]
        is False

        and

        result[
            "reason"
        ]
        ==
        "MISSING_EYE_MEASUREMENT"
    )


    results.append(
        (
            "MISSING_MEASUREMENT_FAIL_SAFE",
            passed
        )
    )


    # ======================================================
    # Print
    # ======================================================

    passed_count = 0


    for (
        name,
        passed
    ) in results:

        if passed:

            passed_count += 1


        print(

            f"{name}:",

            (
                "PASS"
                if passed
                else "FAIL"
            )
        )


    print(
        "--------------------------------------------------------"
    )


    print(
        "Logic Tests:",
        f"{passed_count}/{len(results)}"
    )


    final_pass = (

        passed_count
        ==
        len(
            results
        )
    )


    if final_pass:

        print(
            "LONG EYE CLOSURE LOGIC V2: PASS"
        )

    else:

        print(
            "LONG EYE CLOSURE LOGIC V2: FAIL"
        )


    print(
        "========================================================"
    )


    if not final_pass:

        raise AssertionError(
            "Long Eye Closure V2 validation failed."
        )


# ==========================================================
# Entry
# ==========================================================

if __name__ == "__main__":

    main()