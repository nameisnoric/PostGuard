from pathlib import Path

import sys
import time
import csv

from datetime import datetime

import cv2


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
# Face
# ==========================================================

from mediapipe_detection.face.face_detector import (
    FaceDetector
)

from mediapipe_detection.face.face_points import (
    extract_face_points
)


# ==========================================================
# Eye Measurement
# ==========================================================

from mediapipe_detection.eye.eye_measurement import (
    calculate_eye_openness
)


# ==========================================================
# Eye State
# ==========================================================

from mediapipe_detection.eye.eye_state import (
    EyeStateDetector,
    EYE_UNKNOWN,
    CALIBRATION_READY,
)


# ==========================================================
# Blink
# ==========================================================

from mediapipe_detection.eye.blink_detector import (
    BlinkDetector
)


# ==========================================================
# Long Eye Closure V2
# ==========================================================

from mediapipe_detection.eye.eye_closure import (
    EyeClosureDetector
)


# ==========================================================
# Model
# ==========================================================

FACE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "face_landmarker.task"
)


# ==========================================================
# Eye State Parameters
#
# ใช้ค่าเดิมที่ LOCK แล้ว
# ==========================================================

CALIBRATION_SECONDS = 3.0

MIN_CALIBRATION_SAMPLES = 30

CLOSE_FACTOR = 0.55

REOPEN_FACTOR = 0.70


# ==========================================================
# Blink Parameters
#
# ใช้ค่าที่ Blink Detector ผ่าน validation แล้ว
# ==========================================================

MIN_BLINK_SECONDS = 0.05

MAX_BLINK_SECONDS = 0.80

MAX_CLOSE_SYNC_SECONDS = 0.12


# ==========================================================
# Long Closure V2 Parameters
#
# Prototype parameters
#
# 1.0 sec:
# duration ของ sustained deep closure
#
# 0.12:
# bilateral deep-close factor
#
# ยังไม่ใช่ Medical / Drowsiness threshold
# ==========================================================

LONG_CLOSURE_SECONDS = 1.0

DEEP_CLOSE_FACTOR = 0.12


# ==========================================================
# Test Timing
# ==========================================================

AUTO_CALIBRATION_DELAY = 2.0

PREPARE_SECONDS = 1.5


# ==========================================================
# Validation Sequence
#
# สำคัญ:
#
# TRUE LONG  = 3/3
# LEFT WINK  = 3/3
# RIGHT WINK = 3/3
#
# ทุก round ต้องผ่าน
# ==========================================================

TEST_SEQUENCE = [

    # ------------------------------------------------------
    # Basic
    # ------------------------------------------------------

    {
        "name": "NORMAL_OPEN",
        "group": "NORMAL_OPEN",
        "round": 1,

        "duration": 2.5,

        "expected_blinks": 0,
        "expected_long_closures": 0,

        "require_face_loss": False,

        "instruction": (
            "KEEP BOTH EYES NATURALLY OPEN"
        ),
    },


    {
        "name": "ONE_BLINK",
        "group": "ONE_BLINK",
        "round": 1,

        "duration": 2.5,

        "expected_blinks": 1,
        "expected_long_closures": 0,

        "require_face_loss": False,

        "instruction": (
            "BLINK NATURALLY EXACTLY ONCE"
        ),
    },


    # ------------------------------------------------------
    # TRUE LONG CLOSURE × 3
    # ------------------------------------------------------

    {
        "name": "TRUE_LONG_CLOSURE_R1",
        "group": "TRUE_LONG_CLOSURE",
        "round": 1,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 1,

        "require_face_loss": False,

        "instruction": (
            "CLOSE BOTH EYES FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    {
        "name": "TRUE_LONG_CLOSURE_R2",
        "group": "TRUE_LONG_CLOSURE",
        "round": 2,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 1,

        "require_face_loss": False,

        "instruction": (
            "CLOSE BOTH EYES FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    {
        "name": "TRUE_LONG_CLOSURE_R3",
        "group": "TRUE_LONG_CLOSURE",
        "round": 3,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 1,

        "require_face_loss": False,

        "instruction": (
            "CLOSE BOTH EYES FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    # ------------------------------------------------------
    # LEFT WINK × 3
    # ------------------------------------------------------

    {
        "name": "LEFT_WINK_R1",
        "group": "LEFT_WINK",
        "round": 1,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 0,

        "require_face_loss": False,

        "instruction": (
            "CLOSE LEFT EYE ONLY FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    {
        "name": "LEFT_WINK_R2",
        "group": "LEFT_WINK",
        "round": 2,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 0,

        "require_face_loss": False,

        "instruction": (
            "CLOSE LEFT EYE ONLY FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    {
        "name": "LEFT_WINK_R3",
        "group": "LEFT_WINK",
        "round": 3,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 0,

        "require_face_loss": False,

        "instruction": (
            "CLOSE LEFT EYE ONLY FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    # ------------------------------------------------------
    # RIGHT WINK × 3
    # ------------------------------------------------------

    {
        "name": "RIGHT_WINK_R1",
        "group": "RIGHT_WINK",
        "round": 1,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 0,

        "require_face_loss": False,

        "instruction": (
            "CLOSE RIGHT EYE ONLY FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    {
        "name": "RIGHT_WINK_R2",
        "group": "RIGHT_WINK",
        "round": 2,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 0,

        "require_face_loss": False,

        "instruction": (
            "CLOSE RIGHT EYE ONLY FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    {
        "name": "RIGHT_WINK_R3",
        "group": "RIGHT_WINK",
        "round": 3,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 0,

        "require_face_loss": False,

        "instruction": (
            "CLOSE RIGHT EYE ONLY FOR 1.2-1.5 SEC THEN OPEN"
        ),
    },


    # ------------------------------------------------------
    # Face Lost
    # ------------------------------------------------------

    {
        "name": "FACE_LOST",
        "group": "FACE_LOST",
        "round": 1,

        "duration": 3.5,

        "expected_blinks": 0,
        "expected_long_closures": 0,

        "require_face_loss": True,

        "instruction": (
            "MOVE YOUR ENTIRE FACE OUT OF CAMERA VIEW "
            "FOR ABOUT 1.5 SEC THEN RETURN"
        ),
    },
]


# ==========================================================
# Format Helper
# ==========================================================

def format_optional(
    value,
    digits=3
):

    if value is None:

        return "N/A"


    return (
        f"{value:.{digits}f}"
    )


# ==========================================================
# Save Results
# ==========================================================

def save_results(
    results
):

    output_dir = (
        BASE_DIR
        / "mediapipe_detection"
        / "tests"
        / "results"
    )


    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )


    output_path = (
        output_dir
        /
        (
            "eye_detection_integration_v2_"
            +
            timestamp
            +
            ".csv"
        )
    )


    fieldnames = [

        "name",
        "group",
        "round",

        "expected_blinks",
        "detected_blinks",

        "expected_long_closures",
        "detected_long_closures",

        "face_missing_frames",

        "min_right_depth_ratio",
        "min_left_depth_ratio",

        "deep_bilateral_frames",

        "pass",
    ]


    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )


        writer.writeheader()


        for result in results:

            writer.writerow(
                result
            )


    print(
        "\nResults saved:"
    )


    print(
        output_path
    )


# ==========================================================
# Strict Final Report
# ==========================================================

def print_final_report(
    results
):

    print(
        "\n\n"
        "########################################################"
    )


    print(
        "POSTGUARD EYE DETECTION INTEGRATION V2 REPORT"
    )


    print(
        "########################################################"
    )


    # ======================================================
    # Individual Tests
    # ======================================================

    for result in results:

        print(
            f"{result['name']}:",
            (
                "PASS"
                if result[
                    "pass"
                ]
                else "FAIL"
            )
        )


    # ======================================================
    # Group Validation
    #
    # ทุก test ในกลุ่มต้อง PASS
    # ======================================================

    print(
        "--------------------------------------------------------"
    )


    groups = [

        (
            "NORMAL_OPEN",
            1
        ),

        (
            "ONE_BLINK",
            1
        ),

        (
            "TRUE_LONG_CLOSURE",
            3
        ),

        (
            "LEFT_WINK",
            3
        ),

        (
            "RIGHT_WINK",
            3
        ),

        (
            "FACE_LOST",
            1
        ),
    ]


    group_results = {}


    for (
        group_name,
        required_count
    ) in groups:

        group_rows = [

            result

            for result in results

            if result[
                "group"
            ]
            ==
            group_name
        ]


        passed_count = sum(

            1

            for result in group_rows

            if result[
                "pass"
            ]
        )


        group_pass = (

            len(
                group_rows
            )
            ==
            required_count

            and

            passed_count
            ==
            required_count
        )


        group_results[
            group_name
        ] = (
            group_pass
        )


        print(
            (
                f"{group_name}: "
                f"{passed_count}/{required_count} "
            )
            +
            (
                "PASS"
                if group_pass
                else "FAIL"
            )
        )


    # ======================================================
    # Final
    # ======================================================

    final_pass = all(
        group_results.values()
    )


    print(
        "--------------------------------------------------------"
    )


    if final_pass:

        print(
            "EYE DETECTION INTEGRATION V2: PASS"
        )


        print(
            "Long Eye Closure V2: VALIDATED"
        )


        print(
            "Long Eye Closure can now be LOCKED."
        )


        print(
            "Eye Detection Layer can now be LOCKED."
        )


    else:

        print(
            "EYE DETECTION INTEGRATION V2: FAIL"
        )


        print(
            "Do NOT lock Long Eye Closure yet."
        )


        print(
            "Review failed round(s)."
        )


    print(
        "########################################################"
    )


    return final_pass


# ==========================================================
# Main
# ==========================================================

def main():

    # ======================================================
    # Model Check
    # ======================================================

    if not FACE_MODEL_PATH.exists():

        print(
            "Face model not found:"
        )


        print(
            FACE_MODEL_PATH
        )


        return


    # ======================================================
    # Detectors
    # ======================================================

    face_detector = (
        FaceDetector(
            FACE_MODEL_PATH
        )
    )


    eye_state_detector = (
        EyeStateDetector(

            calibration_seconds=(
                CALIBRATION_SECONDS
            ),

            min_calibration_samples=(
                MIN_CALIBRATION_SAMPLES
            ),

            close_factor=(
                CLOSE_FACTOR
            ),

            reopen_factor=(
                REOPEN_FACTOR
            ),
        )
    )


    blink_detector = (
        BlinkDetector(

            min_blink_seconds=(
                MIN_BLINK_SECONDS
            ),

            max_blink_seconds=(
                MAX_BLINK_SECONDS
            ),

            max_close_sync_seconds=(
                MAX_CLOSE_SYNC_SECONDS
            ),
        )
    )


    closure_detector = (
        EyeClosureDetector(

            long_closure_seconds=(
                LONG_CLOSURE_SECONDS
            ),

            deep_close_factor=(
                DEEP_CLOSE_FACTOR
            ),
        )
    )


    # ======================================================
    # Camera
    # ======================================================

    cap = cv2.VideoCapture(
        0
    )


    if not cap.isOpened():

        print(
            "Cannot open camera."
        )


        face_detector.close()

        return


    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )


    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )


    # ======================================================
    # Runtime
    # ======================================================

    program_started_at = (
        time.perf_counter()
    )


    calibration_started = False

    calibration_printed = False


    test_index = 0


    preparing = False

    collecting = False


    prepare_started_at = None

    capture_started_at = None


    captured_blinks = 0

    captured_long_closures = 0

    face_missing_frames = 0


    deep_bilateral_frames = 0


    min_right_depth_ratio = None

    min_left_depth_ratio = None


    results = []


    validation_complete = False


    status_message = (
        "Preparing automatic calibration..."
    )


    # ======================================================
    # Instructions
    # ======================================================

    print(
        "\n"
        "========================================================\n"
        "POSTGUARD EYE DETECTION INTEGRATION V2\n"
        "========================================================\n"
        "\n"
        "STRICT VALIDATION\n"
        "\n"
        "TRUE_LONG_CLOSURE = 3/3 required\n"
        "LEFT_WINK         = 3/3 required\n"
        "RIGHT_WINK        = 3/3 required\n"
        "\n"
        "There is NO retry-until-pass rule.\n"
        "Each round is recorded once.\n"
        "\n"
        "If you make a mistake, press R and restart\n"
        "the ENTIRE validation.\n"
        "\n"
        "SPACE = start next test\n"
        "R     = restart entire validation\n"
        "Q/ESC = quit\n"
        "\n"
        "Sit in your NATURAL working position.\n"
        "========================================================\n"
    )


    # ======================================================
    # Camera Loop
    # ======================================================

    while True:

        ret, raw_frame = (
            cap.read()
        )


        if not ret:

            print(
                "Cannot read camera frame."
            )

            break


        frame_height, frame_width = (
            raw_frame.shape[:2]
        )


        now = (
            time.perf_counter()
        )


        # ==================================================
        # Face
        # ==================================================

        face_result = (
            face_detector.detect(
                raw_frame
            )
        )


        face_points = (
            extract_face_points(

                face_result,

                frame_width,

                frame_height
            )
        )


        # ==================================================
        # Eye Measurement
        # ==================================================

        eye_measurement = (
            calculate_eye_openness(
                face_points
            )
        )


        measurement_valid = (
            eye_measurement
            is not None
        )


        # ==================================================
        # Automatic Calibration
        # ==================================================

        if (
            not calibration_started

            and

            measurement_valid

            and

            (
                now
                -
                program_started_at
            )
            >=
            AUTO_CALIBRATION_DELAY
        ):

            eye_state_detector.start_calibration(
                timestamp=now
            )


            blink_detector.reset()

            closure_detector.reset()


            calibration_started = True


            status_message = (
                "CALIBRATING - KEEP BOTH EYES OPEN"
            )


            print(
                "\nCalibration started."
            )


            print(
                "Keep BOTH eyes naturally OPEN."
            )


        # ==================================================
        # Eye State
        # ==================================================

        eye_state_result = (
            eye_state_detector.update(

                eye_measurement,

                timestamp=now
            )
        )


        # ==================================================
        # Blink Detector
        # ==================================================

        blink_result = (
            blink_detector.update(
                eye_state_result,
                eye_measurement=eye_measurement,
                timestamp=now
            )
        )


        # ==================================================
        # Long Closure V2
        #
        # IMPORTANT:
        #
        # ต้องส่ง eye_measurement เข้าไปด้วย
        # ==================================================

        closure_result = (
            closure_detector.update(

                eye_state_result,

                eye_measurement=(
                    eye_measurement
                ),

                timestamp=now
            )
        )


        # ==================================================
        # Calibration Ready
        # ==================================================

        if (
            eye_state_result[
                "calibration_status"
            ]
            ==
            CALIBRATION_READY

            and

            not calibration_printed
        ):

            calibration_printed = True


            blink_detector.reset()

            closure_detector.reset()


            status_message = (
                "READY - Press SPACE"
            )


            print(
                "\n"
                "=============================================="
            )


            print(
                "CALIBRATION READY"
            )


            print(
                "=============================================="
            )


            print(
                "RIGHT Reference:",
                f"{eye_state_result['right_open_reference']:.5f}"
            )


            print(
                "RIGHT Close:",
                f"{eye_state_result['right_close_threshold']:.5f}"
            )


            print(
                "RIGHT Reopen:",
                f"{eye_state_result['right_reopen_threshold']:.5f}"
            )


            print(
                "\nLEFT Reference:",
                f"{eye_state_result['left_open_reference']:.5f}"
            )


            print(
                "LEFT Close:",
                f"{eye_state_result['left_close_threshold']:.5f}"
            )


            print(
                "LEFT Reopen:",
                f"{eye_state_result['left_reopen_threshold']:.5f}"
            )


            print(
                "\nDeep Close Factor:",
                DEEP_CLOSE_FACTOR
            )


            print(
                "Long Closure Seconds:",
                LONG_CLOSURE_SECONDS
            )


            print(
                "=============================================="
            )


            print(
                "\nPress SPACE to start:"
            )


            print(
                TEST_SEQUENCE[
                    test_index
                ][
                    "name"
                ]
            )


        # ==================================================
        # PREPARE
        # ==================================================

        if preparing:

            prepare_elapsed = (
                now
                -
                prepare_started_at
            )


            if (
                prepare_elapsed
                >=
                PREPARE_SECONDS
            ):

                preparing = False

                collecting = True


                capture_started_at = (
                    now
                )


                # ------------------------------------------
                # Reset counters only
                #
                # ห้าม reset detector ตรงนี้
                # เพื่อให้ detector เห็น OPEN จาก PREPARE
                # ------------------------------------------

                captured_blinks = 0

                captured_long_closures = 0

                face_missing_frames = 0

                deep_bilateral_frames = 0


                min_right_depth_ratio = None

                min_left_depth_ratio = None


                current_test = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                print(
                    "\n"
                    "=============================================="
                )


                print(
                    "CAPTURE STARTED"
                )


                print(
                    "TEST:",
                    current_test[
                        "name"
                    ]
                )


                print(
                    current_test[
                        "instruction"
                    ]
                )


                print(
                    "=============================================="
                )


        # ==================================================
        # COLLECT
        # ==================================================

        if collecting:

            current_test = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            elapsed = (
                now
                -
                capture_started_at
            )


            # ==============================================
            # Blink
            # ==============================================

            if blink_result[
                "blink_event"
            ]:

                captured_blinks += 1


                print(
                    "BLINK EVENT",
                    f"duration="
                    f"{blink_result['last_blink_duration']:.3f}s",
                    f"count={captured_blinks}"
                )


            # ==============================================
            # Long Closure
            # ==============================================

            if closure_result[
                "long_closure_event"
            ]:

                captured_long_closures += 1


                print(
                    "LONG CLOSURE EVENT",
                    f"duration="
                    f"{closure_result['eye_closure_duration']:.3f}s",
                    f"count={captured_long_closures}"
                )


            # ==============================================
            # Deep Bilateral Diagnostic
            # ==============================================

            if closure_result[
                "deep_bilateral_closure"
            ]:

                deep_bilateral_frames += 1


            right_depth = (
                closure_result[
                    "right_depth_ratio"
                ]
            )


            left_depth = (
                closure_result[
                    "left_depth_ratio"
                ]
            )


            if right_depth is not None:

                if (
                    min_right_depth_ratio
                    is None

                    or

                    right_depth
                    <
                    min_right_depth_ratio
                ):

                    min_right_depth_ratio = (
                        right_depth
                    )


            if left_depth is not None:

                if (
                    min_left_depth_ratio
                    is None

                    or

                    left_depth
                    <
                    min_left_depth_ratio
                ):

                    min_left_depth_ratio = (
                        left_depth
                    )


            # ==============================================
            # Face Lost
            # ==============================================

            if not measurement_valid:

                face_missing_frames += 1


            # ==============================================
            # Finish Current Test
            # ==============================================

            if (
                elapsed
                >=
                current_test[
                    "duration"
                ]
            ):

                collecting = False


                expected_blinks = (
                    current_test[
                        "expected_blinks"
                    ]
                )


                expected_long_closures = (
                    current_test[
                        "expected_long_closures"
                    ]
                )


                # ==========================================
                # Event Criteria
                # ==========================================

                event_pass = (

                    captured_blinks
                    ==
                    expected_blinks

                    and

                    captured_long_closures
                    ==
                    expected_long_closures
                )


                # ==========================================
                # FACE_LOST must actually lose face
                # ==========================================

                face_loss_pass = True


                if current_test[
                    "require_face_loss"
                ]:

                    face_loss_pass = (
                        face_missing_frames
                        >=
                        10
                    )


                passed = (

                    event_pass

                    and

                    face_loss_pass
                )


                result = {

                    "name": (
                        current_test[
                            "name"
                        ]
                    ),

                    "group": (
                        current_test[
                            "group"
                        ]
                    ),

                    "round": (
                        current_test[
                            "round"
                        ]
                    ),

                    "expected_blinks": (
                        expected_blinks
                    ),

                    "detected_blinks": (
                        captured_blinks
                    ),

                    "expected_long_closures": (
                        expected_long_closures
                    ),

                    "detected_long_closures": (
                        captured_long_closures
                    ),

                    "face_missing_frames": (
                        face_missing_frames
                    ),

                    "min_right_depth_ratio": (
                        min_right_depth_ratio
                    ),

                    "min_left_depth_ratio": (
                        min_left_depth_ratio
                    ),

                    "deep_bilateral_frames": (
                        deep_bilateral_frames
                    ),

                    "pass": (
                        passed
                    ),
                }


                results.append(
                    result
                )


                print(
                    "\n"
                    "=============================================="
                )


                print(
                    "RESULT:"
                )


                print(
                    "TEST:",
                    current_test[
                        "name"
                    ]
                )


                print(
                    "Blink Expected:",
                    expected_blinks
                )


                print(
                    "Blink Detected:",
                    captured_blinks
                )


                print(
                    "Long Expected:",
                    expected_long_closures
                )


                print(
                    "Long Detected:",
                    captured_long_closures
                )


                print(
                    "Min Right Depth Ratio:",
                    format_optional(
                        min_right_depth_ratio
                    )
                )


                print(
                    "Min Left Depth Ratio:",
                    format_optional(
                        min_left_depth_ratio
                    )
                )


                print(
                    "Deep Bilateral Frames:",
                    deep_bilateral_frames
                )


                if current_test[
                    "require_face_loss"
                ]:

                    print(
                        "Face Missing Frames:",
                        face_missing_frames
                    )


                print(
                    "RESULT:",
                    (
                        "PASS"
                        if passed
                        else "FAIL"
                    )
                )


                print(
                    "=============================================="
                )


                # ==========================================
                # Go to next test regardless of PASS/FAIL
                #
                # สำคัญ:
                # ไม่มี retry-until-pass
                # ==========================================

                test_index += 1


                if (
                    test_index
                    >=
                    len(
                        TEST_SEQUENCE
                    )
                ):

                    validation_complete = True


                    final_pass = (
                        print_final_report(
                            results
                        )
                    )


                    save_results(
                        results
                    )


                    if final_pass:

                        status_message = (
                            "EYE DETECTION V2 COMPLETE"
                        )

                    else:

                        status_message = (
                            "VALIDATION FAILED"
                        )


                else:

                    next_test = (
                        TEST_SEQUENCE[
                            test_index
                        ]
                    )


                    status_message = (

                        "NEXT: "

                        +

                        next_test[
                            "name"
                        ]

                        +

                        " - Press SPACE"
                    )


                    print(
                        "\nNext test:"
                    )


                    print(
                        next_test[
                            "name"
                        ]
                    )


                    print(
                        next_test[
                            "instruction"
                        ]
                    )


                    print(
                        "\nPress SPACE when ready."
                    )


        # ==================================================
        # Display
        # ==================================================

        display_frame = (
            cv2.flip(
                raw_frame,
                1
            )
        )


        # ==================================================
        # Current Test
        # ==================================================

        if (
            not validation_complete

            and

            test_index
            <
            len(
                TEST_SEQUENCE
            )
        ):

            current_test = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            test_name = (
                current_test[
                    "name"
                ]
            )


            instruction = (
                current_test[
                    "instruction"
                ]
            )


        else:

            test_name = (
                "COMPLETE"
            )


            instruction = (
                "VALIDATION COMPLETE"
            )


        # ==================================================
        # Eye Openness
        # ==================================================

        if eye_measurement is not None:

            cv2.putText(
                display_frame,
                (
                    "R Openness: "
                    f"{eye_measurement['right_eye_openness']:.3f}"
                ),
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                1
            )


            cv2.putText(
                display_frame,
                (
                    "L Openness: "
                    f"{eye_measurement['left_eye_openness']:.3f}"
                ),
                (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                1
            )


        else:

            cv2.putText(
                display_frame,
                "Eye Measurement: UNKNOWN",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 255),
                2
            )


        # ==================================================
        # Eye States
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "R State: "
                +
                str(
                    eye_state_result.get(
                        "right_eye_state",
                        EYE_UNKNOWN
                    )
                )
            ),
            (20, 105),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            (
                "L State: "
                +
                str(
                    eye_state_result.get(
                        "left_eye_state",
                        EYE_UNKNOWN
                    )
                )
            ),
            (20, 135),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            (
                "Combined: "
                +
                str(
                    eye_state_result.get(
                        "eye_state",
                        EYE_UNKNOWN
                    )
                )
            ),
            (20, 165),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Depth Ratios
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "R Depth Ratio: "
                +
                format_optional(
                    closure_result[
                        "right_depth_ratio"
                    ]
                )
            ),
            (20, 205),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (0, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            (
                "L Depth Ratio: "
                +
                format_optional(
                    closure_result[
                        "left_depth_ratio"
                    ]
                )
            ),
            (20, 235),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (0, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            (
                "Deep Bilateral: "
                +
                str(
                    closure_result[
                        "deep_bilateral_closure"
                    ]
                )
            ),
            (20, 265),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (0, 255, 255),
            1
        )


        # ==================================================
        # Counters
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "Blink Events: "
                +
                str(
                    captured_blinks
                )
            ),
            (20, 305),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            (
                "Long Events: "
                +
                str(
                    captured_long_closures
                )
            ),
            (20, 335),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            (
                "Closure Duration: "
                f"{closure_result['eye_closure_duration']:.2f}s"
            ),
            (20, 365),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Test Info
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "TEST: "
                +
                test_name
            ),
            (20, 415),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            instruction,
            (20, 445),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Runtime
        # ==================================================

        if preparing:

            remaining = max(

                0.0,

                PREPARE_SECONDS
                -
                (
                    now
                    -
                    prepare_started_at
                )
            )


            runtime_text = (

                "PREPARE - KEEP BOTH EYES OPEN "

                f"{remaining:.1f}s"
            )


        elif collecting:

            elapsed = (
                now
                -
                capture_started_at
            )


            runtime_text = (

                "CAPTURE "

                f"{elapsed:.1f}/"

                f"{current_test['duration']:.1f}s"
            )


        else:

            runtime_text = (
                status_message
            )


        cv2.putText(
            display_frame,
            runtime_text,
            (20, 480),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (0, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            "SPACE=Start  R=Restart All  Q=Quit",
            (
                20,
                frame_height - 25
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1
        )


        cv2.imshow(
            "PostGuard - Eye Detection Integration V2",
            display_frame
        )


        # ==================================================
        # Keyboard
        # ==================================================

        key = (
            cv2.waitKey(1)
            &
            0xFF
        )


        # ==================================================
        # Quit
        # ==================================================

        if key in (
            ord("q"),
            ord("Q"),
            27
        ):

            break


        # ==================================================
        # SPACE
        #
        # Reset temporal detectors BEFORE PREPARE
        # ==================================================

        if (
            key
            ==
            ord(" ")

            and

            eye_state_result.get(
                "calibrated",
                False
            )

            and

            not validation_complete

            and

            not preparing

            and

            not collecting
        ):

            blink_detector.reset(
                preserve_count=True
            )


            closure_detector.reset(
                preserve_count=True
            )


            captured_blinks = 0

            captured_long_closures = 0

            face_missing_frames = 0

            deep_bilateral_frames = 0


            min_right_depth_ratio = None

            min_left_depth_ratio = None


            preparing = True


            prepare_started_at = (
                now
            )


            current_test = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            status_message = (

                "PREPARING "

                +

                current_test[
                    "name"
                ]
            )


            print(
                "\nPrepare:"
            )


            print(
                current_test[
                    "name"
                ]
            )


            print(
                "KEEP BOTH EYES NATURALLY OPEN."
            )


            print(
                "When CAPTURE starts:"
            )


            print(
                current_test[
                    "instruction"
                ]
            )


        # ==================================================
        # Restart Entire Validation
        # ==================================================

        if key in (
            ord("r"),
            ord("R")
        ):

            eye_state_detector.reset()

            blink_detector.reset()

            closure_detector.reset()


            program_started_at = (
                time.perf_counter()
            )


            calibration_started = False

            calibration_printed = False


            test_index = 0


            preparing = False

            collecting = False


            prepare_started_at = None

            capture_started_at = None


            captured_blinks = 0

            captured_long_closures = 0

            face_missing_frames = 0

            deep_bilateral_frames = 0


            min_right_depth_ratio = None

            min_left_depth_ratio = None


            results = []


            validation_complete = False


            status_message = (
                "RESET - Preparing automatic calibration..."
            )


            print(
                "\nENTIRE VALIDATION RESET"
            )


    # ======================================================
    # Cleanup
    # ======================================================

    cap.release()

    face_detector.close()

    cv2.destroyAllWindows()


# ==========================================================
# Entry
# ==========================================================

if __name__ == "__main__":

    main()