import sys
import time
from pathlib import Path

import cv2
import numpy as np


# ==========================================================
# Project Root
# ==========================================================

CAMERA_CARD_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

if str(CAMERA_CARD_DIR) not in sys.path:

    sys.path.insert(
        0,
        str(CAMERA_CARD_DIR)
    )


# ==========================================================
# Detection Pipeline
# ==========================================================

from mediapipe_detection.detection_pipeline import (
    DetectionPipeline
)

from mediapipe_detection.posture.forward_head_candidates import (
    calculate_forward_head_candidates
)


# ==========================================================
# Configuration
# ==========================================================

CAMERA_INDEX = 0

CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

WINDOW_NAME = (
    "PostGuard - Forward Head Candidate Test"
)

CAPTURE_SECONDS = 2.0

MIN_SAMPLES = 15


# ==========================================================
# Test Sequence
# ==========================================================

TEST_SEQUENCE = []


for round_number in range(
    1,
    4
):

    TEST_SEQUENCE.extend(
        [
            {
                "round": round_number,
                "state": "NORMAL_1",
            },

            {
                "round": round_number,
                "state": "FORWARD_HEAD",
            },

            {
                "round": round_number,
                "state": "NORMAL_2",
            },
        ]
    )


TEST_SEQUENCE.extend(
    [
        {
            "round": 0,
            "state": "FLEXION_NORMAL",
        },

        {
            "round": 0,
            "state": "FLEXION",
        },

        {
            "round": 0,
            "state": "TORSO_NORMAL",
        },

        {
            "round": 0,
            "state": "TORSO_LEAN",
        },
    ]
)


# ==========================================================
# Colors
# ==========================================================

WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
RED = (0, 0, 255)
CYAN = (255, 255, 0)


# ==========================================================
# Draw Helper
# ==========================================================

def put(
    frame,
    text,
    y,
    color=WHITE,
    scale=0.6,
    thickness=1,
):

    cv2.putText(
        frame,
        str(text),
        (20, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


# ==========================================================
# Summary
# ==========================================================

def summarize(values):

    values = np.asarray(
        values,
        dtype=np.float64
    )

    return {
        "median": float(
            np.median(values)
        ),

        "mean": float(
            np.mean(values)
        ),

        "std": float(
            np.std(values)
        ),
    }


def summarize_samples(samples):

    return {
        "eye_ratio": summarize(
            [
                s[
                    "eye_shoulder_ratio"
                ]
                for s in samples
            ]
        ),

        "face_ratio": summarize(
            [
                s[
                    "face_shoulder_ratio"
                ]
                for s in samples
            ]
        ),

        "shoulder_width": summarize(
            [
                s[
                    "shoulder_width_px"
                ]
                for s in samples
            ]
        ),

        "eye_distance": summarize(
            [
                s[
                    "inter_eye_distance_px"
                ]
                for s in samples
            ]
        ),

        "face_width": summarize(
            [
                s[
                    "face_width_px"
                ]
                for s in samples
            ]
        ),

        "pitch": summarize(
            [
                s[
                    "pitch"
                ]
                for s in samples
            ]
        ),

        "samples": len(
            samples
        ),
    }


# ==========================================================
# Find Result
# ==========================================================

def find_result(
    results,
    round_number,
    state,
):

    for result in results:

        if (
            result[
                "round"
            ]
            ==
            round_number

            and

            result[
                "state"
            ]
            ==
            state
        ):

            return result

    return None


# ==========================================================
# Analyse Candidate
# ==========================================================

def analyse_candidate(
    results,
    metric_name,
):

    reports = []


    for round_number in range(
        1,
        4
    ):

        normal_1 = find_result(
            results,
            round_number,
            "NORMAL_1"
        )

        forward = find_result(
            results,
            round_number,
            "FORWARD_HEAD"
        )

        normal_2 = find_result(
            results,
            round_number,
            "NORMAL_2"
        )


        if (
            normal_1 is None
            or
            forward is None
            or
            normal_2 is None
        ):

            continue


        n1 = (
            normal_1[
                "summary"
            ][
                metric_name
            ][
                "median"
            ]
        )

        fwd = (
            forward[
                "summary"
            ][
                metric_name
            ][
                "median"
            ]
        )

        n2 = (
            normal_2[
                "summary"
            ][
                metric_name
            ][
                "median"
            ]
        )


        normal_reference = float(
            np.median(
                [
                    n1,
                    n2,
                ]
            )
        )


        normal_min = min(
            n1,
            n2
        )

        normal_max = max(
            n1,
            n2
        )


        delta = (
            fwd
            -
            normal_reference
        )


        if fwd > normal_max:

            direction = 1

            separated = True

        elif fwd < normal_min:

            direction = -1

            separated = True

        else:

            direction = 0

            separated = False


        reports.append(
            {
                "round": (
                    round_number
                ),

                "normal_1": (
                    n1
                ),

                "normal_2": (
                    n2
                ),

                "forward": (
                    fwd
                ),

                "delta": (
                    delta
                ),

                "direction": (
                    direction
                ),

                "separated": (
                    separated
                ),
            }
        )


    return reports


# ==========================================================
# Direction Consistency
# ==========================================================

def get_direction(
    reports
):

    if len(
        reports
    ) != 3:

        return 0


    directions = [
        report[
            "direction"
        ]
        for report in reports
    ]


    if all(
        value == 1
        for value in directions
    ):

        return 1


    if all(
        value == -1
        for value in directions
    ):

        return -1


    return 0


# ==========================================================
# Distractor Check
# ==========================================================

def analyse_distractor(
    results,
    metric_name,
    main_reports,
    direction,
):

    flex_normal = find_result(
        results,
        0,
        "FLEXION_NORMAL"
    )

    flexion = find_result(
        results,
        0,
        "FLEXION"
    )

    torso_normal = find_result(
        results,
        0,
        "TORSO_NORMAL"
    )

    torso_lean = find_result(
        results,
        0,
        "TORSO_LEAN"
    )


    if any(
        item is None
        for item in (
            flex_normal,
            flexion,
            torso_normal,
            torso_lean,
        )
    ):

        return None


    true_responses = [
        abs(
            report[
                "delta"
            ]
        )
        for report in main_reports
    ]


    true_response_median = float(
        np.median(
            true_responses
        )
    )


    flex_delta = (
        flexion[
            "summary"
        ][
            metric_name
        ][
            "median"
        ]
        -
        flex_normal[
            "summary"
        ][
            metric_name
        ][
            "median"
        ]
    )


    torso_delta = (
        torso_lean[
            "summary"
        ][
            metric_name
        ][
            "median"
        ]
        -
        torso_normal[
            "summary"
        ][
            metric_name
        ][
            "median"
        ]
    )


    flex_mimic = max(
        0.0,
        direction
        *
        flex_delta
    )


    torso_mimic = max(
        0.0,
        direction
        *
        torso_delta
    )


    return {
        "true_response": (
            true_response_median
        ),

        "flex_delta": (
            flex_delta
        ),

        "flex_mimic": (
            flex_mimic
        ),

        "torso_delta": (
            torso_delta
        ),

        "torso_mimic": (
            torso_mimic
        ),

        "flex_pass": (
            true_response_median
            >
            flex_mimic
        ),

        "torso_pass": (
            true_response_median
            >
            torso_mimic
        ),
    }


# ==========================================================
# Print Candidate Report
# ==========================================================

def print_candidate_report(
    results,
    metric_name,
    display_name,
):

    print()
    print(
        "============================================"
    )

    print(
        display_name
    )

    print(
        "============================================"
    )


    reports = analyse_candidate(
        results,
        metric_name
    )


    for report in reports:

        print()
        print(
            "ROUND",
            report[
                "round"
            ]
        )

        print(
            "Normal 1:",
            f"{report['normal_1']:.6f}"
        )

        print(
            "Forward :",
            f"{report['forward']:.6f}"
        )

        print(
            "Normal 2:",
            f"{report['normal_2']:.6f}"
        )

        print(
            "Delta   :",
            f"{report['delta']:+.6f}"
        )

        print(
            "Separated:",
            (
                "PASS"
                if report[
                    "separated"
                ]
                else "FAIL"
            )
        )


    direction = get_direction(
        reports
    )


    print()


    if direction == 1:

        print(
            "Direction: CONSISTENT POSITIVE"
        )

    elif direction == -1:

        print(
            "Direction: CONSISTENT NEGATIVE"
        )

    else:

        print(
            "Direction: INCONSISTENT"
        )


    separation_count = sum(
        1
        for report in reports
        if report[
            "separated"
        ]
    )


    print(
        "Separation:",
        f"{separation_count}/3"
    )


    # ======================================================
    # Distractor
    # ==========================================================

    distractor = None


    if direction != 0:

        distractor = (
            analyse_distractor(
                results,
                metric_name,
                reports,
                direction,
            )
        )


    if distractor is not None:

        print()
        print(
            "True Forward response:",
            f"{distractor['true_response']:.6f}"
        )

        print()

        print(
            "Flexion delta:",
            f"{distractor['flex_delta']:+.6f}"
        )

        print(
            "Flexion mimic:",
            f"{distractor['flex_mimic']:.6f}"
        )

        print(
            "Flexion specificity:",
            (
                "PASS"
                if distractor[
                    "flex_pass"
                ]
                else "FAIL"
            )
        )


        print()

        print(
            "Torso Lean delta:",
            f"{distractor['torso_delta']:+.6f}"
        )

        print(
            "Torso mimic:",
            f"{distractor['torso_mimic']:.6f}"
        )

        print(
            "Torso specificity:",
            (
                "PASS"
                if distractor[
                    "torso_pass"
                ]
                else "FAIL"
            )
        )


    final_pass = (
        len(
            reports
        ) == 3
        and
        separation_count == 3
        and
        direction != 0
        and
        distractor is not None
        and
        distractor[
            "flex_pass"
        ]
        and
        distractor[
            "torso_pass"
        ]
    )


    print()


    if final_pass:

        print(
            "CANDIDATE RESULT: PASS"
        )

    else:

        print(
            "CANDIDATE RESULT: NEEDS REVIEW"
        )


    return {
        "pass": (
            final_pass
        ),

        "direction": (
            direction
        ),

        "reports": (
            reports
        ),

        "distractor": (
            distractor
        ),
    }


# ==========================================================
# State Instruction
# ==========================================================

def get_instruction(
    state
):

    if state in (
        "NORMAL_1",
        "NORMAL_2",
        "FLEXION_NORMAL",
        "TORSO_NORMAL",
    ):

        return (
            "Natural posture, look straight"
        )


    if state == "FORWARD_HEAD":

        return (
            "Push HEAD forward; keep torso and pitch stable"
        )


    if state == "FLEXION":

        return (
            "Bend neck DOWN; do not push head forward"
        )


    if state == "TORSO_LEAN":

        return (
            "Lean WHOLE torso forward; keep neck neutral"
        )


    return state


# ==========================================================
# Main
# ==========================================================

def main():

    capture = cv2.VideoCapture(
        CAMERA_INDEX
    )


    if not capture.isOpened():

        raise RuntimeError(
            "Cannot open webcam"
        )


    capture.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        CAMERA_WIDTH
    )

    capture.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        CAMERA_HEIGHT
    )


    pipeline = (
        DetectionPipeline()
    )


    cv2.namedWindow(
        WINDOW_NAME,
        cv2.WINDOW_NORMAL
    )

    cv2.resizeWindow(
        WINDOW_NAME,
        CAMERA_WIDTH,
        CAMERA_HEIGHT
    )


    test_index = 0

    collecting = False

    collection_start = None

    current_samples = []

    results = []

    test_complete = False

    report_printed = False


    print()
    print(
        "============================================"
    )

    print(
        "POSTGUARD FORWARD HEAD CANDIDATE TEST"
    )

    print(
        "============================================"
    )

    print()

    print(
        "Testing:"
    )

    print(
        "A = Eye / Shoulder Ratio"
    )

    print(
        "B = Face / Shoulder Ratio"
    )

    print()

    print(
        "SPACE = Capture"
    )

    print(
        "R = Reset"
    )

    print(
        "Q / ESC = Quit"
    )

    print()


    try:

        while True:

            success, raw_frame = (
                capture.read()
            )


            if (
                not success
                or
                raw_frame is None
            ):

                break


            timestamp = (
                time.perf_counter()
            )


            detection = (
                pipeline.process_frame(
                    raw_frame,
                    timestamp=timestamp
                )
            )


            pose_points = (
                detection[
                    "landmarks"
                ][
                    "pose"
                ]
            )

            face_points = (
                detection[
                    "landmarks"
                ][
                    "face"
                ]
            )


            candidates = (
                calculate_forward_head_candidates(
                    pose_points,
                    face_points,
                )
            )


            pitch_feature = (
                detection[
                    "features"
                ][
                    "neck_flexion"
                ]
            )


            current_pitch = None


            if pitch_feature.get(
                "valid",
                False
            ):

                current_pitch = (
                    pitch_feature[
                        "value"
                    ]
                )


            # ==================================================
            # Collection
            # ==========================================================

            if collecting:

                elapsed = (
                    timestamp
                    -
                    collection_start
                )


                if (
                    candidates is not None
                    and
                    current_pitch is not None
                ):

                    current_samples.append(
                        {
                            **candidates,

                            "pitch": float(
                                current_pitch
                            ),
                        }
                    )


                if (
                    elapsed
                    >=
                    CAPTURE_SECONDS
                ):

                    step = (
                        TEST_SEQUENCE[
                            test_index
                        ]
                    )


                    if (
                        len(
                            current_samples
                        )
                        <
                        MIN_SAMPLES
                    ):

                        print()
                        print(
                            "CAPTURE FAILED"
                        )

                        print(
                            "Valid samples:",
                            len(
                                current_samples
                            )
                        )

                        print(
                            "Repeat same state."
                        )


                        collecting = False

                        current_samples = []


                    else:

                        summary = (
                            summarize_samples(
                                current_samples
                            )
                        )


                        results.append(
                            {
                                "round": (
                                    step[
                                        "round"
                                    ]
                                ),

                                "state": (
                                    step[
                                        "state"
                                    ]
                                ),

                                "summary": (
                                    summary
                                ),
                            }
                        )


                        print()
                        print(
                            "--------------------------------------------"
                        )

                        print(
                            "State:",
                            step[
                                "state"
                            ]
                        )

                        print(
                            "Round:",
                            step[
                                "round"
                            ]
                        )

                        print(
                            "Samples:",
                            summary[
                                "samples"
                            ]
                        )

                        print()

                        print(
                            "Eye/Shoulder:",
                            f"{summary['eye_ratio']['median']:.6f}",
                            "Std:",
                            f"{summary['eye_ratio']['std']:.6f}"
                        )

                        print(
                            "Face/Shoulder:",
                            f"{summary['face_ratio']['median']:.6f}",
                            "Std:",
                            f"{summary['face_ratio']['std']:.6f}"
                        )

                        print(
                            "Shoulder Width:",
                            f"{summary['shoulder_width']['median']:.2f}"
                        )

                        print(
                            "Eye Distance:",
                            f"{summary['eye_distance']['median']:.2f}"
                        )

                        print(
                            "Face Width:",
                            f"{summary['face_width']['median']:.2f}"
                        )

                        print(
                            "Pitch:",
                            f"{summary['pitch']['median']:+.2f}"
                        )

                        print(
                            "--------------------------------------------"
                        )


                        test_index += 1

                        collecting = False

                        current_samples = []


                        if (
                            test_index
                            >=
                            len(
                                TEST_SEQUENCE
                            )
                        ):

                            test_complete = True


            # ==================================================
            # Display
            # ==========================================================

            display = cv2.flip(
                raw_frame.copy(),
                1
            )


            put(
                display,
                "POSTGUARD - FORWARD HEAD CANDIDATES",
                30,
                CYAN,
                scale=0.7,
                thickness=2,
            )


            if not test_complete:

                step = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                put(
                    display,
                    (
                        f"ROUND: "
                        f"{step['round']}"
                    ),
                    65,
                )

                put(
                    display,
                    (
                        f"STATE: "
                        f"{step['state']}"
                    ),
                    95,
                    YELLOW,
                )

                put(
                    display,
                    get_instruction(
                        step[
                            "state"
                        ]
                    ),
                    125,
                )


            if candidates is not None:

                put(
                    display,
                    (
                        "Eye/Shoulder Ratio: "
                        f"{candidates['eye_shoulder_ratio']:.6f}"
                    ),
                    180,
                    GREEN,
                )

                put(
                    display,
                    (
                        "Face/Shoulder Ratio: "
                        f"{candidates['face_shoulder_ratio']:.6f}"
                    ),
                    210,
                    GREEN,
                )

                put(
                    display,
                    (
                        "Shoulder Width: "
                        f"{candidates['shoulder_width_px']:.2f} px"
                    ),
                    240,
                )

                put(
                    display,
                    (
                        "Eye Distance: "
                        f"{candidates['inter_eye_distance_px']:.2f} px"
                    ),
                    270,
                )

                put(
                    display,
                    (
                        "Face Width: "
                        f"{candidates['face_width_px']:.2f} px"
                    ),
                    300,
                )


            else:

                put(
                    display,
                    "Forward Head Candidates: INVALID",
                    180,
                    RED,
                )


            if current_pitch is not None:

                put(
                    display,
                    (
                        "Pitch: "
                        f"{current_pitch:+.2f} deg"
                    ),
                    335,
                )


            if collecting:

                elapsed = (
                    timestamp
                    -
                    collection_start
                )

                progress = min(
                    elapsed
                    /
                    CAPTURE_SECONDS,
                    1.0
                )


                put(
                    display,
                    (
                        "COLLECTING "
                        f"{progress * 100:.0f}% "
                        f"samples={len(current_samples)}"
                    ),
                    390,
                    GREEN,
                    thickness=2,
                )


            put(
                display,
                (
                    "SPACE Capture | "
                    "R Reset | "
                    "Q/ESC Quit"
                ),
                display.shape[
                    0
                ]
                -
                40,
            )


            cv2.imshow(
                WINDOW_NAME,
                display
            )


            # ==================================================
            # Final Report
            # ==========================================================

            if (
                test_complete
                and
                not report_printed
            ):

                print()
                print()
                print(
                    "############################################"
                )

                print(
                    "FINAL CANDIDATE COMPARISON"
                )

                print(
                    "############################################"
                )


                result_a = (
                    print_candidate_report(
                        results,
                        "eye_ratio",
                        (
                            "CANDIDATE A: "
                            "EYE / SHOULDER RATIO"
                        ),
                    )
                )


                result_b = (
                    print_candidate_report(
                        results,
                        "face_ratio",
                        (
                            "CANDIDATE B: "
                            "FACE / SHOULDER RATIO"
                        ),
                    )
                )


                print()
                print(
                    "############################################"
                )

                print(
                    "FINAL DECISION"
                )

                print(
                    "############################################"
                )


                if (
                    result_a[
                        "pass"
                    ]
                    and
                    not result_b[
                        "pass"
                    ]
                ):

                    print(
                        "Candidate A is currently stronger."
                    )


                elif (
                    result_b[
                        "pass"
                    ]
                    and
                    not result_a[
                        "pass"
                    ]
                ):

                    print(
                        "Candidate B is currently stronger."
                    )


                elif (
                    result_a[
                        "pass"
                    ]
                    and
                    result_b[
                        "pass"
                    ]
                ):

                    print(
                        "Both candidates PASS."
                    )

                    print(
                        "Compare variability and "
                        "distractor response before selection."
                    )


                else:

                    print(
                        "Neither candidate PASS."
                    )

                    print(
                        "Do NOT integrate Forward Head yet."
                    )


                report_printed = True


            # ==================================================
            # Keyboard
            # ==========================================================

            key = (
                cv2.waitKey(1)
                &
                0xFF
            )


            if (
                key == 32
                and
                not collecting
                and
                not test_complete
            ):

                collecting = True

                collection_start = (
                    time.perf_counter()
                )

                current_samples = []


                print()
                print(
                    "CAPTURE START:",
                    TEST_SEQUENCE[
                        test_index
                    ][
                        "state"
                    ]
                )


            elif key in (
                ord("r"),
                ord("R"),
            ):

                test_index = 0

                collecting = False

                collection_start = None

                current_samples = []

                results = []

                test_complete = False

                report_printed = False


                print()
                print(
                    "TEST RESET"
                )


            elif key in (
                ord("q"),
                ord("Q"),
                27,
            ):

                break


    finally:

        pipeline.close()

        capture.release()

        cv2.destroyAllWindows()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()