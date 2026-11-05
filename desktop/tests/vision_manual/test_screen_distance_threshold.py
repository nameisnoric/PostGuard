import csv
import math
import statistics
import time
from datetime import datetime
from pathlib import Path

import cv2

from app.vision.mediapipe_detection.face.face_detector import (
    FaceDetector,
)

from app.vision.mediapipe_detection.face.face_points import (
    extract_face_points,
)

from app.vision.mediapipe_detection.posture.relative_distance import (
    calculate_eye_distance,
)


# ==========================================================
# Screen Distance Threshold Validation
# ==========================================================
#
# PURPOSE
#
# Collect real experimental evidence for selecting a future
# Personal-Baseline-relative Screen Distance threshold.
#
# IMPORTANT:
#
# - Physical centimeters are EXPERIMENTAL GROUND TRUTH only.
# - Production PostGuard does NOT estimate centimeters.
# - Production logic remains:
#
#       current_eye_distance_px
#       -----------------------
#       baseline_eye_distance_px
#
# - This test does NOT define TOO_CLOSE.
# - This test does NOT define hysteresis.
# - This test does NOT modify Risk/RULA.
#
# ==========================================================


# ==========================================================
# Configuration
# ==========================================================

CAMERA_INDEX = 0

CAPTURE_SECONDS = 3.0

MIN_VALID_SAMPLES = 15

TOTAL_ROUNDS = 3


# ==========================================================
# Fixed Ground-Truth States
# ==========================================================
#
# BASELINE:
#     User's normal sitting position.
#     Actual distance is measured manually.
#
# Fixed states:
#     Must be positioned using a measuring tape.
#
# RETURN_BASELINE:
#     Return to the SAME baseline distance from the
#     beginning of that round.
# ==========================================================

TEST_STATES = (
    ("BASELINE", None),
    ("DISTANCE_70_CM", 70.0),
    ("DISTANCE_60_CM", 60.0),
    ("DISTANCE_50_CM", 50.0),
    ("DISTANCE_40_CM", 40.0),
    ("DISTANCE_30_CM", 30.0),
    ("RETURN_BASELINE", None),
)


# ==========================================================
# Helpers
# ==========================================================

def is_finite_number(value):
    """
    Return True only for usable finite numeric values.

    Rejects:
    - None
    - NaN
    - +/- Infinity
    - invalid strings
    """

    try:
        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError,
    ):
        return False


def calculate_ratio(
    current_eye_distance_px,
    baseline_eye_distance_px,
):
    """
    Calculate eye-distance ratio relative to the
    Personal Baseline of the SAME round.

    Example:

        baseline = 70 px
        current  = 91 px

        ratio = 91 / 70
              = 1.30

    A larger ratio means the face appears larger in
    the image relative to baseline.

    This is NOT physical distance estimation.
    """

    if not is_finite_number(
        current_eye_distance_px
    ):
        return None

    if not is_finite_number(
        baseline_eye_distance_px
    ):
        return None

    current_eye_distance_px = float(
        current_eye_distance_px
    )

    baseline_eye_distance_px = float(
        baseline_eye_distance_px
    )

    if current_eye_distance_px <= 0:
        return None

    if baseline_eye_distance_px <= 0:
        return None

    return (
        current_eye_distance_px
        /
        baseline_eye_distance_px
    )


def calculate_percent_change(ratio):
    """
    Convert ratio into percent change from baseline.

    1.00 ->   0%
    1.10 -> +10%
    1.25 -> +25%
    0.90 -> -10%
    """

    if not is_finite_number(ratio):
        return None

    return (
        float(ratio) - 1.0
    ) * 100.0


def get_face_model_path():
    """
    Resolve:

        desktop/app/vision/models/face_landmarker.task

    from:

        desktop/tests/vision_manual/
        test_screen_distance_threshold.py
    """

    desktop_root = (
        Path(__file__).resolve().parents[2]
    )

    model_path = (
        desktop_root
        / "app"
        / "vision"
        / "models"
        / "face_landmarker.task"
    )

    if not model_path.exists():
        raise FileNotFoundError(
            "Face Landmarker model not found: "
            f"{model_path}"
        )

    return model_path


def read_positive_distance(
    prompt,
):
    """
    Ask the tester to enter a manually measured
    physical distance in centimeters.

    This value is Ground Truth for the experiment only.
    """

    while True:
        raw_value = input(
            prompt
        ).strip()

        try:
            value = float(
                raw_value
            )

        except ValueError:
            print(
                "Invalid value. "
                "Enter distance in centimeters."
            )
            continue

        if (
            not math.isfinite(value)
            or value <= 0
        ):
            print(
                "Distance must be a positive "
                "finite number."
            )
            continue

        return value


# ==========================================================
# Eye Distance Measurement
# ==========================================================

def measure_eye_distance(
    frame,
    face_detector,
):
    """
    Correct current PostGuard contract:

        OpenCV frame
            ↓
        FaceDetector.detect(frame)
            ↓
        MediaPipe FaceLandmarkerResult
            ↓
        extract_face_points(
            result,
            frame_width,
            frame_height
        )
            ↓
        face_points dictionary
            ↓
        calculate_eye_distance(face_points)
            ↓
        eye_distance_px

    Returns:

        {
            "valid": True,
            "reason": "OK",
            "eye_distance_px": ...
        }

    or:

        {
            "valid": False,
            "reason": "...",
            "eye_distance_px": None
        }
    """

    if frame is None:
        return {
            "valid": False,
            "reason": "FRAME_NOT_AVAILABLE",
            "eye_distance_px": None,
        }

    try:
        frame_height, frame_width = (
            frame.shape[:2]
        )

    except (
        AttributeError,
        ValueError,
    ):
        return {
            "valid": False,
            "reason": "FRAME_SHAPE_INVALID",
            "eye_distance_px": None,
        }

    if (
        frame_width <= 0
        or frame_height <= 0
    ):
        return {
            "valid": False,
            "reason": "FRAME_SIZE_INVALID",
            "eye_distance_px": None,
        }

    # ------------------------------------------------------
    # MediaPipe FaceLandmarkerResult
    # ------------------------------------------------------

    face_result = face_detector.detect(
        frame
    )

    if face_result is None:
        return {
            "valid": False,
            "reason": "FACE_RESULT_NOT_AVAILABLE",
            "eye_distance_px": None,
        }

    # ------------------------------------------------------
    # FaceLandmarkerResult -> PostGuard face_points
    # ------------------------------------------------------

    face_points = extract_face_points(
        result=face_result,
        frame_width=frame_width,
        frame_height=frame_height,
    )

    if face_points is None:
        return {
            "valid": False,
            "reason": "FACE_POINTS_NOT_AVAILABLE",
            "eye_distance_px": None,
        }

    # ------------------------------------------------------
    # PostGuard Inter-Eye Distance / IPD Proxy
    # ------------------------------------------------------

    eye_distance_result = (
        calculate_eye_distance(
            face_points
        )
    )

    if not isinstance(
        eye_distance_result,
        dict,
    ):
        return {
            "valid": False,
            "reason": "EYE_DISTANCE_NOT_AVAILABLE",
            "eye_distance_px": None,
        }

    eye_distance_px = (
        eye_distance_result.get(
            "eye_distance_px"
        )
    )

    if not is_finite_number(
        eye_distance_px
    ):
        return {
            "valid": False,
            "reason": "EYE_DISTANCE_INVALID",
            "eye_distance_px": None,
        }

    eye_distance_px = float(
        eye_distance_px
    )

    if eye_distance_px <= 0:
        return {
            "valid": False,
            "reason": "EYE_DISTANCE_NON_POSITIVE",
            "eye_distance_px": None,
        }

    return {
        "valid": True,
        "reason": "OK",
        "eye_distance_px": eye_distance_px,
    }


# ==========================================================
# State Preparation
# ==========================================================

def print_state_instruction(
    state_name,
    measured_distance_cm,
    baseline_distance_cm,
):
    """
    Print measurement instructions before each capture.
    """

    print()
    print("=" * 72)
    print(
        f"STATE: {state_name}"
    )
    print("=" * 72)

    if state_name == "BASELINE":
        print(
            "Sit in your normal working position."
        )

        print(
            "The baseline distance has been "
            "measured manually."
        )

        print(
            "Measured baseline distance: "
            f"{measured_distance_cm:.1f} cm"
        )

    elif state_name == "RETURN_BASELINE":
        print(
            "Return to the SAME baseline distance "
            "used at the beginning of this round."
        )

        print(
            "Target baseline distance: "
            f"{baseline_distance_cm:.1f} cm"
        )

        print(
            "Measure the distance again before "
            "starting capture."
        )

    else:
        print(
            "Use a measuring tape."
        )

        print(
            "Measure from the webcam lens to the "
            "midpoint between the eyes."
        )

        print(
            "Target physical distance: "
            f"{measured_distance_cm:.1f} cm"
        )

    print()
    print(
        "Keep the camera position and zoom unchanged."
    )

    print(
        "Keep the face approximately facing the camera."
    )

    print()


# ==========================================================
# Capture One State
# ==========================================================

def capture_state(
    cap,
    face_detector,
    state_name,
    measured_distance_cm,
    baseline_distance_cm,
):
    """
    Capture eye-distance samples for one experimental state.
    """

    print_state_instruction(
        state_name=state_name,
        measured_distance_cm=measured_distance_cm,
        baseline_distance_cm=baseline_distance_cm,
    )

    print(
        "Press SPACE when the measured position "
        "is ready."
    )

    print(
        "Press ESC to cancel the experiment."
    )

    print()

    # ======================================================
    # Preparation Screen
    # ======================================================

    while True:
        ok, frame = cap.read()

        if not ok:
            raise RuntimeError(
                "Could not read frame from camera."
            )

        display = frame.copy()

        cv2.putText(
            display,
            state_name,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            display,
            (
                "Measured target: "
                f"{measured_distance_cm:.1f} cm"
            ),
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            display,
            (
                "Baseline: "
                f"{baseline_distance_cm:.1f} cm"
            ),
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        # --------------------------------------------------
        # Preview current eye measurement
        # --------------------------------------------------

        preview_result = measure_eye_distance(
            frame=frame,
            face_detector=face_detector,
        )

        if preview_result["valid"]:
            preview_text = (
                "Eye distance: "
                f"{preview_result['eye_distance_px']:.2f} px"
            )

        else:
            preview_text = (
                "Eye distance: unavailable"
            )

        cv2.putText(
            display,
            preview_text,
            (20, 160),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            display,
            "SPACE = capture | ESC = cancel",
            (20, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )

        cv2.imshow(
            "PostGuard Screen Distance Threshold Test",
            display,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            raise KeyboardInterrupt

        if key == 32:
            break

    # ======================================================
    # Capture
    # ======================================================

    samples = []

    invalid_reason_counts = {}

    start_time = time.monotonic()

    while (
        time.monotonic() - start_time
        <
        CAPTURE_SECONDS
    ):
        ok, frame = cap.read()

        if not ok:
            invalid_reason_counts[
                "CAMERA_FRAME_NOT_AVAILABLE"
            ] = (
                invalid_reason_counts.get(
                    "CAMERA_FRAME_NOT_AVAILABLE",
                    0,
                )
                + 1
            )

            continue

        measurement = measure_eye_distance(
            frame=frame,
            face_detector=face_detector,
        )

        if measurement["valid"]:
            samples.append(
                measurement[
                    "eye_distance_px"
                ]
            )

        else:
            reason = measurement[
                "reason"
            ]

            invalid_reason_counts[
                reason
            ] = (
                invalid_reason_counts.get(
                    reason,
                    0,
                )
                + 1
            )

        elapsed = (
            time.monotonic()
            -
            start_time
        )

        remaining = max(
            0.0,
            CAPTURE_SECONDS - elapsed,
        )

        display = frame.copy()

        cv2.putText(
            display,
            f"Capturing: {state_name}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            display,
            (
                "Ground truth: "
                f"{measured_distance_cm:.1f} cm"
            ),
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            display,
            (
                "Valid samples: "
                f"{len(samples)}"
            ),
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        if measurement["valid"]:
            measurement_text = (
                "Eye distance: "
                f"{measurement['eye_distance_px']:.2f} px"
            )

        else:
            measurement_text = (
                "Measurement: "
                f"{measurement['reason']}"
            )

        cv2.putText(
            display,
            measurement_text,
            (20, 160),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            display,
            f"Remaining: {remaining:.1f}s",
            (20, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        cv2.imshow(
            "PostGuard Screen Distance Threshold Test",
            display,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            raise KeyboardInterrupt

    # ======================================================
    # Validate Sample Count
    # ======================================================

    if len(samples) < MIN_VALID_SAMPLES:
        print()
        print(
            "CAPTURE STATUS: INVALID"
        )

        print(
            "Valid samples: "
            f"{len(samples)}"
        )

        print(
            "Required samples: "
            f"{MIN_VALID_SAMPLES}"
        )

        if invalid_reason_counts:
            print(
                "Invalid reasons:"
            )

            for (
                reason,
                count,
            ) in sorted(
                invalid_reason_counts.items()
            ):
                print(
                    f"  {reason}: {count}"
                )

        return {
            "status": "INVALID",
            "reason": "INSUFFICIENT_VALID_SAMPLES",
            "valid_samples": len(samples),
            "median": None,
            "mean": None,
            "std": None,
        }

    # ======================================================
    # Statistics
    # ======================================================

    median_value = statistics.median(
        samples
    )

    mean_value = statistics.mean(
        samples
    )

    if len(samples) >= 2:
        std_value = statistics.stdev(
            samples
        )

    else:
        std_value = 0.0

    print()
    print(
        "CAPTURE STATUS: VALID"
    )

    print(
        "Valid Samples: "
        f"{len(samples)}"
    )

    print(
        "Median Eye Distance: "
        f"{median_value:.3f} px"
    )

    print(
        "Mean Eye Distance: "
        f"{mean_value:.3f} px"
    )

    print(
        "Std Eye Distance: "
        f"{std_value:.3f} px"
    )

    return {
        "status": "VALID",
        "reason": "OK",
        "valid_samples": len(samples),
        "median": float(
            median_value
        ),
        "mean": float(
            mean_value
        ),
        "std": float(
            std_value
        ),
    }


# ==========================================================
# Run One Round
# ==========================================================

def run_round(
    round_number,
    cap,
    face_detector,
):
    """
    Run one independent experimental round.

    Baseline belongs only to this round.
    """

    print()
    print()
    print("#" * 72)
    print(
        f"ROUND {round_number}/{TOTAL_ROUNDS}"
    )
    print("#" * 72)

    print()
    print(
        "Set your NORMAL working position."
    )

    print(
        "Measure from the webcam lens to the "
        "midpoint between your eyes."
    )

    print()

    baseline_distance_cm = (
        read_positive_distance(
            "Enter measured BASELINE distance (cm): "
        )
    )

    print()
    print(
        "Baseline Ground Truth: "
        f"{baseline_distance_cm:.1f} cm"
    )

    round_results = []

    baseline_eye_distance_px = None

    for (
        state_name,
        fixed_distance_cm,
    ) in TEST_STATES:

        # ==================================================
        # Determine Ground Truth Distance
        # ==================================================

        if state_name == "BASELINE":
            measured_distance_cm = (
                baseline_distance_cm
            )

        elif state_name == "RETURN_BASELINE":
            measured_distance_cm = (
                baseline_distance_cm
            )

        else:
            measured_distance_cm = float(
                fixed_distance_cm
            )

        # ==================================================
        # Capture
        # ==================================================

        result = capture_state(
            cap=cap,
            face_detector=face_detector,
            state_name=state_name,
            measured_distance_cm=measured_distance_cm,
            baseline_distance_cm=baseline_distance_cm,
        )

        # ==================================================
        # Invalid Capture
        # ==================================================

        if result["status"] != "VALID":
            round_results.append({
                "round": round_number,
                "state": state_name,

                "measured_distance_cm": (
                    measured_distance_cm
                ),

                "baseline_distance_cm": (
                    baseline_distance_cm
                ),

                "eye_distance_px": None,

                "eye_distance_median_px": None,

                "eye_distance_mean_px": None,

                "eye_distance_std_px": None,

                "baseline_eye_distance_px": (
                    baseline_eye_distance_px
                ),

                "ratio": None,

                "percent_change": None,

                "valid_samples": result[
                    "valid_samples"
                ],

                "status": result[
                    "status"
                ],

                "reason": result[
                    "reason"
                ],
            })

            continue

        # ==================================================
        # Current Measurement
        # ==================================================

        current_eye_distance_px = (
            result["median"]
        )

        # ==================================================
        # Establish Baseline Pixel Measurement
        # ==================================================

        if state_name == "BASELINE":
            baseline_eye_distance_px = (
                current_eye_distance_px
            )

        # IMPORTANT:
        #
        # RETURN_BASELINE does NOT overwrite the baseline.
        #
        # It must compare against the ORIGINAL baseline
        # measurement from this round.

        # ==================================================
        # Relative Ratio
        # ==================================================

        ratio = calculate_ratio(
            current_eye_distance_px=(
                current_eye_distance_px
            ),
            baseline_eye_distance_px=(
                baseline_eye_distance_px
            ),
        )

        percent_change = (
            calculate_percent_change(
                ratio
            )
        )

        print()

        if ratio is not None:
            print(
                "Baseline Eye Distance: "
                f"{baseline_eye_distance_px:.3f} px"
            )

            print(
                "Relative Ratio: "
                f"{ratio:.4f}"
            )

            print(
                "Change from Baseline: "
                f"{percent_change:+.2f}%"
            )

        else:
            print(
                "Relative Ratio: NOT AVAILABLE"
            )

        # ==================================================
        # Save State Result
        # ==================================================

        round_results.append({
            "round": round_number,

            "state": state_name,

            "measured_distance_cm": (
                measured_distance_cm
            ),

            "baseline_distance_cm": (
                baseline_distance_cm
            ),

            # Primary representative value = median
            "eye_distance_px": (
                current_eye_distance_px
            ),

            "eye_distance_median_px": (
                result["median"]
            ),

            "eye_distance_mean_px": (
                result["mean"]
            ),

            "eye_distance_std_px": (
                result["std"]
            ),

            "baseline_eye_distance_px": (
                baseline_eye_distance_px
            ),

            "ratio": ratio,

            "percent_change": (
                percent_change
            ),

            "valid_samples": result[
                "valid_samples"
            ],

            "status": "VALID",

            "reason": "OK",
        })

    return round_results


# ==========================================================
# Summary Helpers
# ==========================================================

def get_valid_rows(
    all_results,
    state_name,
):
    return [
        row
        for row in all_results
        if (
            row["state"] == state_name
            and row["status"] == "VALID"
            and is_finite_number(
                row["eye_distance_px"]
            )
        )
    ]


def print_state_summary(
    all_results,
    state_name,
    distance_label,
):
    rows = get_valid_rows(
        all_results,
        state_name,
    )

    print()
    print("-" * 72)
    print(
        distance_label
    )

    print(
        "Valid rounds: "
        f"{len(rows)}/{TOTAL_ROUNDS}"
    )

    if not rows:
        return

    eye_values = [
        float(
            row["eye_distance_px"]
        )
        for row in rows
    ]

    ratios = [
        float(
            row["ratio"]
        )
        for row in rows
        if is_finite_number(
            row["ratio"]
        )
    ]

    print(
        "Median Eye Distance across rounds: "
        f"{statistics.median(eye_values):.3f} px"
    )

    if ratios:
        ratio_median = statistics.median(
            ratios
        )

        print(
            "Median Ratio: "
            f"{ratio_median:.4f}"
        )

        print(
            "Ratio Range: "
            f"{min(ratios):.4f}"
            " to "
            f"{max(ratios):.4f}"
        )

        print(
            "Median Change: "
            f"{calculate_percent_change(ratio_median):+.2f}%"
        )


# ==========================================================
# Print Final Summary
# ==========================================================

def print_summary(all_results):
    print()
    print()
    print("#" * 72)
    print(
        "POSTGUARD SCREEN DISTANCE "
        "THRESHOLD VALIDATION"
    )
    print("#" * 72)

    print_state_summary(
        all_results,
        "BASELINE",
        "BASELINE",
    )

    for distance in (
        70,
        60,
        50,
        40,
        30,
    ):
        print_state_summary(
            all_results,
            f"DISTANCE_{distance}_CM",
            f"DISTANCE_{distance}_CM ({distance} cm)",
        )

    print_state_summary(
        all_results,
        "RETURN_BASELINE",
        "RETURN_BASELINE",
    )

    # ======================================================
    # Distance / Ratio Summary
    # ======================================================

    print()
    print("=" * 72)
    print(
        "DISTANCE / RATIO SUMMARY"
    )
    print("=" * 72)

    distance_medians = {}

    for distance in (
        70,
        60,
        50,
        40,
        30,
    ):
        state_name = (
            f"DISTANCE_{distance}_CM"
        )

        rows = get_valid_rows(
            all_results,
            state_name,
        )

        ratios = [
            float(
                row["ratio"]
            )
            for row in rows
            if is_finite_number(
                row["ratio"]
            )
        ]

        if ratios:
            ratio_median = statistics.median(
                ratios
            )

            distance_medians[
                distance
            ] = ratio_median

            print(
                f"{distance:>2} cm -> "
                f"median ratio {ratio_median:.4f}"
            )

        else:
            print(
                f"{distance:>2} cm -> "
                "NO VALID DATA"
            )

    # ======================================================
    # Trend Check
    # ======================================================
    #
    # This is deliberately NOT a strict pass/fail criterion.
    #
    # Real measurements contain:
    # - head movement
    # - face rotation
    # - landmark noise
    # - camera perspective
    #
    # We report the trend instead of forcing strict
    # monotonicity.
    # ======================================================

    available_distances = [
        distance
        for distance in (
            70,
            60,
            50,
            40,
            30,
        )
        if distance in distance_medians
    ]

    if len(available_distances) >= 2:
        ordered_ratios = [
            distance_medians[
                distance
            ]
            for distance in available_distances
        ]

        non_decreasing_steps = 0

        total_steps = (
            len(ordered_ratios) - 1
        )

        for index in range(
            total_steps
        ):
            if (
                ordered_ratios[index + 1]
                >=
                ordered_ratios[index]
            ):
                non_decreasing_steps += 1

        print()
        print(
            "Closer-distance increasing steps: "
            f"{non_decreasing_steps}/{total_steps}"
        )

        if (
            non_decreasing_steps
            ==
            total_steps
        ):
            print(
                "Observed trend: CONSISTENT"
            )

        else:
            print(
                "Observed trend: "
                "NOT STRICTLY MONOTONIC"
            )

            print(
                "Review the per-round CSV before "
                "selecting any threshold."
            )

    # ======================================================
    # Return Baseline Reproducibility
    # ======================================================

    print()
    print("=" * 72)
    print(
        "RETURN-TO-BASELINE REPRODUCIBILITY"
    )
    print("=" * 72)

    return_rows = get_valid_rows(
        all_results,
        "RETURN_BASELINE",
    )

    return_ratios = [
        float(
            row["ratio"]
        )
        for row in return_rows
        if is_finite_number(
            row["ratio"]
        )
    ]

    if return_ratios:
        return_median = statistics.median(
            return_ratios
        )

        return_change = (
            calculate_percent_change(
                return_median
            )
        )

        print(
            "Median Return Ratio: "
            f"{return_median:.4f}"
        )

        print(
            "Median Return Change: "
            f"{return_change:+.2f}%"
        )

        print(
            "Return Ratio Range: "
            f"{min(return_ratios):.4f}"
            " to "
            f"{max(return_ratios):.4f}"
        )

    else:
        print(
            "No valid return-baseline data."
        )

    # ======================================================
    # Threshold Notice
    # ======================================================

    print()
    print("=" * 72)
    print(
        "THRESHOLD STATUS"
    )
    print("=" * 72)

    print(
        "TOO_CLOSE threshold: NOT SELECTED"
    )

    print(
        "Hysteresis threshold: NOT SELECTED"
    )

    print()
    print(
        "Physical centimeters are experimental "
        "Ground Truth only."
    )

    print(
        "Production remains Personal-"
        "Baseline-relative."
    )

    print()
    print(
        "Review all 3 rounds before selecting "
        "a production threshold."
    )


# ==========================================================
# Save CSV
# ==========================================================

def save_results(
    all_results,
):
    results_dir = (
        Path(__file__).resolve().parent
        /
        "results"
    )

    results_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        results_dir
        /
        (
            "screen_distance_threshold_v2_"
            f"{timestamp}.csv"
        )
    )

    fieldnames = [
        "round",
        "state",
        "measured_distance_cm",
        "baseline_distance_cm",
        "eye_distance_px",
        "eye_distance_median_px",
        "eye_distance_mean_px",
        "eye_distance_std_px",
        "baseline_eye_distance_px",
        "ratio",
        "percent_change",
        "valid_samples",
        "status",
        "reason",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            all_results
        )

    return output_path


# ==========================================================
# Main
# ==========================================================

def main():
    print()
    print("=" * 72)
    print(
        "POSTGUARD SCREEN DISTANCE "
        "THRESHOLD VALIDATION V2"
    )
    print("=" * 72)

    print()
    print(
        "Protocol:"
    )

    print(
        "3 rounds x 7 states = 21 captures"
    )

    print()

    print(
        "BASELINE -> 70 -> 60 -> 50 -> "
        "40 -> 30 cm -> RETURN_BASELINE"
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "Measure physical distance with a "
        "measuring tape."
    )

    print(
        "Measure from the webcam lens to the "
        "midpoint between the eyes."
    )

    print(
        "Centimeters are Ground Truth for "
        "validation only."
    )

    print(
        "PostGuard production does NOT estimate "
        "physical centimeters."
    )

    print()

    # ======================================================
    # Model
    # ======================================================

    model_path = get_face_model_path()

    print(
        f"Face model: {model_path}"
    )

    # ======================================================
    # Camera
    # ======================================================

    cap = cv2.VideoCapture(
        CAMERA_INDEX
    )

    if not cap.isOpened():
        raise RuntimeError(
            "Could not open webcam."
        )

    face_detector = None

    try:
        # ==================================================
        # Face Detector
        # ==================================================

        face_detector = FaceDetector(
            model_path=model_path
        )

        all_results = []

        # ==================================================
        # Three Independent Rounds
        # ==================================================

        for round_number in range(
            1,
            TOTAL_ROUNDS + 1,
        ):
            round_results = run_round(
                round_number=round_number,
                cap=cap,
                face_detector=face_detector,
            )

            all_results.extend(
                round_results
            )

        # ==================================================
        # Summary
        # ==================================================

        print_summary(
            all_results
        )

        # ==================================================
        # CSV
        # ==================================================

        output_path = save_results(
            all_results
        )

        print()
        print("=" * 72)
        print(
            "RESULT SAVED"
        )
        print("=" * 72)

        print(
            output_path
        )

    except KeyboardInterrupt:
        print()
        print(
            "Validation cancelled."
        )

    finally:
        cap.release()

        cv2.destroyAllWindows()

        if face_detector is not None:
            close_method = getattr(
                face_detector,
                "close",
                None,
            )

            if callable(
                close_method
            ):
                close_method()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":
    main()