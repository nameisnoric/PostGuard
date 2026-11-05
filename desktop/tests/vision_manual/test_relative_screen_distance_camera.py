import csv
import math
import statistics
import time
from collections import Counter
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
# PostGuard
# Relative Screen Distance Camera Validation
# ==========================================================
#
# PURPOSE
#
# Validate that PostGuard's pixel-based inter-eye distance
# responds consistently when the user moves closer to the
# camera relative to their own baseline.
#
# This validation tests:
#
#   1. Measurement availability
#   2. Relative direction
#   3. Repeatability
#   4. Return-to-baseline recovery
#
# IMPORTANT
#
# This validation DOES NOT:
#
#   - estimate physical distance in centimeters
#   - define an ergonomic unsafe distance
#   - define TOO_CLOSE threshold
#   - define hysteresis
#   - modify posture Risk / RULA
#
# Production Screen Distance remains:
#
#       current_eye_distance_px
#       -----------------------
#       baseline_eye_distance_px
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
# Test States
# ==========================================================
#
# The tester controls the physical movement manually.
#
# No centimeters are assigned.
#
# CLOSER_1:
#     Move slightly closer than baseline.
#
# CLOSER_2:
#     Move clearly closer than CLOSER_1.
#
# CLOSER_3:
#     Move clearly closer than CLOSER_2.
#
# RETURN_BASELINE:
#     Return as closely as possible to the ORIGINAL
#     baseline position of the current round.
# ==========================================================

TEST_STATES = (
    "BASELINE",
    "CLOSER_1",
    "CLOSER_2",
    "CLOSER_3",
    "RETURN_BASELINE",
)


# ==========================================================
# Numeric Helpers
# ==========================================================

def is_finite_number(value):
    """
    Return True only when value is a usable finite number.
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
    Calculate relative screen-distance ratio.

        ratio =
            current_eye_distance_px
            /
            baseline_eye_distance_px

    Interpretation:

        ratio ~= 1.0
            similar apparent face scale to baseline

        ratio > 1.0
            face appears larger than baseline

        ratio < 1.0
            face appears smaller than baseline

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
    Convert ratio to percentage change from baseline.

        1.00 ->   0%
        1.10 -> +10%
        1.25 -> +25%
        0.90 -> -10%
    """

    if not is_finite_number(
        ratio
    ):
        return None

    return (
        float(ratio) - 1.0
    ) * 100.0


# ==========================================================
# Model
# ==========================================================

def get_face_model_path():
    """
    Resolve:

        desktop/app/vision/models/face_landmarker.task
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


# ==========================================================
# Measurement
# ==========================================================

def measure_eye_distance(
    frame,
    face_detector,
):
    """
    Run the REAL current PostGuard measurement chain:

        frame
          ↓
        FaceDetector.detect(frame)
          ↓
        MediaPipe FaceLandmarkerResult
          ↓
        extract_face_points(...)
          ↓
        face_points
          ↓
        calculate_eye_distance(...)
          ↓
        eye_distance_px

    Returns a small validation contract so failures can be
    counted separately from successful measurements.
    """

    if frame is None:
        return {
            "valid": False,
            "reason": "FRAME_NOT_AVAILABLE",
            "eye_distance_px": None,
        }

    # ------------------------------------------------------
    # Frame dimensions
    # ------------------------------------------------------

    try:
        frame_height, frame_width = (
            frame.shape[:2]
        )

    except (
        AttributeError,
        TypeError,
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
    # Face Landmarker
    # ------------------------------------------------------

    try:
        face_result = face_detector.detect(
            frame
        )

    except Exception as exc:
        return {
            "valid": False,
            "reason": (
                "FACE_DETECTOR_ERROR:"
                f"{type(exc).__name__}"
            ),
            "eye_distance_px": None,
        }

    if face_result is None:
        return {
            "valid": False,
            "reason": "FACE_RESULT_NOT_AVAILABLE",
            "eye_distance_px": None,
        }

    # ------------------------------------------------------
    # FaceLandmarkerResult -> selected face points
    # ------------------------------------------------------

    try:
        face_points = extract_face_points(
            result=face_result,
            frame_width=frame_width,
            frame_height=frame_height,
        )

    except Exception as exc:
        return {
            "valid": False,
            "reason": (
                "FACE_POINT_EXTRACTION_ERROR:"
                f"{type(exc).__name__}"
            ),
            "eye_distance_px": None,
        }

    if face_points is None:
        return {
            "valid": False,
            "reason": "FACE_POINTS_NOT_AVAILABLE",
            "eye_distance_px": None,
        }

    # ------------------------------------------------------
    # Inter-Eye Distance / IPD Proxy
    # ------------------------------------------------------

    try:
        eye_distance_result = (
            calculate_eye_distance(
                face_points
            )
        )

    except Exception as exc:
        return {
            "valid": False,
            "reason": (
                "EYE_DISTANCE_ERROR:"
                f"{type(exc).__name__}"
            ),
            "eye_distance_px": None,
        }

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
# Instructions
# ==========================================================

def get_state_instruction(state_name):
    """
    Return human-readable instructions for each state.
    """

    instructions = {
        "BASELINE": (
            "Sit in your NORMAL working position. "
            "Keep your head approximately facing the camera."
        ),

        "CLOSER_1": (
            "Move SLIGHTLY closer to the camera than BASELINE. "
            "Keep approximately the same head orientation."
        ),

        "CLOSER_2": (
            "Move clearly closer than CLOSER_1. "
            "Keep approximately the same head orientation."
        ),

        "CLOSER_3": (
            "Move clearly closer than CLOSER_2. "
            "This should be the closest state in this round."
        ),

        "RETURN_BASELINE": (
            "Return to the SAME normal sitting position used "
            "for BASELINE in this round."
        ),
    }

    return instructions.get(
        state_name,
        state_name,
    )


# ==========================================================
# Preview
# ==========================================================

def wait_for_capture(
    cap,
    face_detector,
    state_name,
):
    """
    Show live preview before capture.

    SPACE:
        begin the 3-second capture

    ESC:
        cancel validation
    """

    instruction = get_state_instruction(
        state_name
    )

    print()
    print("=" * 72)
    print(
        f"STATE: {state_name}"
    )
    print("=" * 72)

    print()
    print(
        instruction
    )

    print()
    print(
        "Do NOT rotate the head intentionally."
    )

    print(
        "Try to change only your distance "
        "from the camera."
    )

    print()
    print(
        "SPACE = start capture"
    )

    print(
        "ESC   = cancel"
    )

    print()

    while True:
        ok, frame = cap.read()

        if not ok:
            raise RuntimeError(
                "Could not read frame from camera."
            )

        measurement = measure_eye_distance(
            frame=frame,
            face_detector=face_detector,
        )

        display = frame.copy()

        # --------------------------------------------------
        # State
        # --------------------------------------------------

        cv2.putText(
            display,
            state_name,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            (255, 255, 255),
            2,
        )

        # --------------------------------------------------
        # Current measurement
        # --------------------------------------------------

        if measurement["valid"]:
            measurement_text = (
                "Eye distance: "
                f"{measurement['eye_distance_px']:.2f} px"
            )

        else:
            measurement_text = (
                "Eye distance: unavailable"
            )

        cv2.putText(
            display,
            measurement_text,
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        # --------------------------------------------------
        # Controls
        # --------------------------------------------------

        cv2.putText(
            display,
            "SPACE = capture | ESC = cancel",
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )

        cv2.imshow(
            "PostGuard Relative Screen Distance Validation",
            display,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            raise KeyboardInterrupt

        if key == 32:
            return


# ==========================================================
# Capture State
# ==========================================================

def capture_state(
    cap,
    face_detector,
    state_name,
):
    """
    Capture one state for CAPTURE_SECONDS.

    The state is valid only when at least
    MIN_VALID_SAMPLES measurements are available.
    """

    wait_for_capture(
        cap=cap,
        face_detector=face_detector,
        state_name=state_name,
    )

    samples = []

    invalid_reasons = Counter()

    total_frames = 0

    start_time = time.monotonic()

    while (
        time.monotonic() - start_time
        <
        CAPTURE_SECONDS
    ):
        ok, frame = cap.read()

        total_frames += 1

        if not ok:
            invalid_reasons[
                "CAMERA_FRAME_NOT_AVAILABLE"
            ] += 1

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
            invalid_reasons[
                measurement["reason"]
            ] += 1

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
                "Valid samples: "
                f"{len(samples)}"
            ),
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        invalid_count = sum(
            invalid_reasons.values()
        )

        cv2.putText(
            display,
            (
                "Invalid samples: "
                f"{invalid_count}"
            ),
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        if measurement["valid"]:
            value_text = (
                "Eye distance: "
                f"{measurement['eye_distance_px']:.2f} px"
            )

        else:
            value_text = (
                "Measurement: "
                f"{measurement['reason']}"
            )

        cv2.putText(
            display,
            value_text,
            (20, 160),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
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
            "PostGuard Relative Screen Distance Validation",
            display,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            raise KeyboardInterrupt

    # ======================================================
    # Capture Statistics
    # ======================================================

    valid_samples = len(
        samples
    )

    invalid_samples = sum(
        invalid_reasons.values()
    )

    # ------------------------------------------------------
    # Not enough valid samples
    # ------------------------------------------------------

    if valid_samples < MIN_VALID_SAMPLES:
        if invalid_reasons:
            primary_reason = (
                invalid_reasons.most_common(
                    1
                )[0][0]
            )

            reason = (
                "INSUFFICIENT_VALID_SAMPLES:"
                f"{primary_reason}"
            )

        else:
            reason = (
                "INSUFFICIENT_VALID_SAMPLES"
            )

        print()
        print(
            "CAPTURE STATUS: INVALID"
        )

        print(
            "Valid Samples: "
            f"{valid_samples}"
        )

        print(
            "Invalid Samples: "
            f"{invalid_samples}"
        )

        print(
            "Required Samples: "
            f"{MIN_VALID_SAMPLES}"
        )

        print(
            f"Reason: {reason}"
        )

        if invalid_reasons:
            print(
                "Failure breakdown:"
            )

            for (
                failure_reason,
                count,
            ) in invalid_reasons.most_common():
                print(
                    f"  {failure_reason}: {count}"
                )

        return {
            "status": "INVALID",
            "reason": reason,

            "total_frames": total_frames,
            "valid_samples": valid_samples,
            "invalid_samples": invalid_samples,

            "median": None,
            "mean": None,
            "std": None,
        }

    # ------------------------------------------------------
    # Valid capture
    # ------------------------------------------------------

    median_value = statistics.median(
        samples
    )

    mean_value = statistics.mean(
        samples
    )

    if valid_samples >= 2:
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
        f"{valid_samples}"
    )

    print(
        "Invalid Samples: "
        f"{invalid_samples}"
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

        "total_frames": total_frames,
        "valid_samples": valid_samples,
        "invalid_samples": invalid_samples,

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
    Run one independent validation round.

    Each round creates its own baseline.

    RETURN_BASELINE always compares against the original
    BASELINE measurement of the same round.
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
        "This round has its own independent baseline."
    )

    print(
        "Start from your normal working position."
    )

    round_results = []

    baseline_eye_distance_px = None

    for state_name in TEST_STATES:

        result = capture_state(
            cap=cap,
            face_detector=face_detector,
            state_name=state_name,
        )

        # ==================================================
        # Invalid State
        # ==================================================

        if result["status"] != "VALID":
            round_results.append({
                "round": round_number,
                "state": state_name,

                "status": result[
                    "status"
                ],

                "reason": result[
                    "reason"
                ],

                "total_frames": result[
                    "total_frames"
                ],

                "valid_samples": result[
                    "valid_samples"
                ],

                "invalid_samples": result[
                    "invalid_samples"
                ],

                "baseline_eye_distance_px": (
                    baseline_eye_distance_px
                ),

                "current_eye_distance_px": None,

                "eye_distance_median_px": None,
                "eye_distance_mean_px": None,
                "eye_distance_std_px": None,

                "ratio": None,
                "percent_change": None,
            })

            continue

        # ==================================================
        # Representative Measurement
        # ==================================================
        #
        # Median is used as the representative value because
        # it is less sensitive to occasional landmark noise.
        # ==================================================

        current_eye_distance_px = (
            result["median"]
        )

        # ==================================================
        # Establish Round Baseline
        # ==================================================

        if state_name == "BASELINE":
            baseline_eye_distance_px = (
                current_eye_distance_px
            )

        # IMPORTANT:
        #
        # RETURN_BASELINE must NOT overwrite this value.
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

        # ==================================================
        # Console Result
        # ==================================================

        print()

        if baseline_eye_distance_px is not None:
            print(
                "Round Baseline: "
                f"{baseline_eye_distance_px:.3f} px"
            )

        if ratio is not None:
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
        # Store Result
        # ==================================================

        round_results.append({
            "round": round_number,
            "state": state_name,

            "status": "VALID",
            "reason": "OK",

            "total_frames": result[
                "total_frames"
            ],

            "valid_samples": result[
                "valid_samples"
            ],

            "invalid_samples": result[
                "invalid_samples"
            ],

            "baseline_eye_distance_px": (
                baseline_eye_distance_px
            ),

            "current_eye_distance_px": (
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

            "ratio": ratio,

            "percent_change": (
                percent_change
            ),
        })

    return round_results


# ==========================================================
# Result Helpers
# ==========================================================

def get_valid_row(
    all_results,
    round_number,
    state_name,
):
    """
    Get one valid row for a round/state.
    """

    for row in all_results:
        if (
            row["round"] == round_number
            and
            row["state"] == state_name
            and
            row["status"] == "VALID"
        ):
            return row

    return None


def get_valid_ratios(
    all_results,
    state_name,
):
    """
    Collect valid ratios for one state across rounds.
    """

    ratios = []

    for row in all_results:
        if row["state"] != state_name:
            continue

        if row["status"] != "VALID":
            continue

        if not is_finite_number(
            row["ratio"]
        ):
            continue

        ratios.append(
            float(
                row["ratio"]
            )
        )

    return ratios


# ==========================================================
# Per-Round Analysis
# ==========================================================

def analyze_round(
    all_results,
    round_number,
):
    """
    Analyze one round without inventing an ergonomic
    threshold.

    Direction is considered supportive when:

        CLOSER_1 > BASELINE
        CLOSER_2 > BASELINE
        CLOSER_3 > BASELINE

    We additionally report whether:

        CLOSER_1 <= CLOSER_2 <= CLOSER_3

    but strict step-by-step ordering is NOT required for
    overall validation because movement is manually
    controlled and has no physical ground truth.
    """

    baseline = get_valid_row(
        all_results,
        round_number,
        "BASELINE",
    )

    closer_1 = get_valid_row(
        all_results,
        round_number,
        "CLOSER_1",
    )

    closer_2 = get_valid_row(
        all_results,
        round_number,
        "CLOSER_2",
    )

    closer_3 = get_valid_row(
        all_results,
        round_number,
        "CLOSER_3",
    )

    returned = get_valid_row(
        all_results,
        round_number,
        "RETURN_BASELINE",
    )

    required_rows = (
        baseline,
        closer_1,
        closer_2,
        closer_3,
        returned,
    )

    if any(
        row is None
        for row in required_rows
    ):
        return {
            "complete": False,
            "direction_supported": False,
            "strict_order": False,
            "return_ratio": None,
        }

    closer_ratios = [
        float(
            closer_1["ratio"]
        ),
        float(
            closer_2["ratio"]
        ),
        float(
            closer_3["ratio"]
        ),
    ]

    # ------------------------------------------------------
    # Every manually closer state should be above baseline.
    # ------------------------------------------------------

    direction_supported = all(
        ratio > 1.0
        for ratio in closer_ratios
    )

    # ------------------------------------------------------
    # Informational only.
    #
    # Since no ruler / physical ground truth is available,
    # we do NOT require this for final validation.
    # ------------------------------------------------------

    strict_order = (
        closer_ratios[0]
        <= closer_ratios[1]
        <= closer_ratios[2]
    )

    return {
        "complete": True,

        "direction_supported": (
            direction_supported
        ),

        "strict_order": (
            strict_order
        ),

        "return_ratio": float(
            returned["ratio"]
        ),
    }


# ==========================================================
# Summary
# ==========================================================

def print_summary(
    all_results,
):
    print()
    print()
    print("#" * 72)
    print(
        "POSTGUARD RELATIVE SCREEN DISTANCE "
        "CAMERA VALIDATION"
    )
    print("#" * 72)

    # ======================================================
    # State Summary
    # ======================================================

    print()
    print("=" * 72)
    print(
        "STATE SUMMARY"
    )
    print("=" * 72)

    for state_name in TEST_STATES:
        rows = [
            row
            for row in all_results
            if (
                row["state"] == state_name
                and
                row["status"] == "VALID"
            )
        ]

        ratios = get_valid_ratios(
            all_results,
            state_name,
        )

        print()
        print(
            state_name
        )

        print(
            "Valid rounds: "
            f"{len(rows)}/{TOTAL_ROUNDS}"
        )

        if rows:
            eye_values = [
                float(
                    row[
                        "current_eye_distance_px"
                    ]
                )
                for row in rows
                if is_finite_number(
                    row[
                        "current_eye_distance_px"
                    ]
                )
            ]

            if eye_values:
                print(
                    "Median Eye Distance "
                    "across rounds: "
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

    # ======================================================
    # Per-Round Direction
    # ======================================================

    print()
    print("=" * 72)
    print(
        "PER-ROUND DIRECTION"
    )
    print("=" * 72)

    round_analyses = []

    for round_number in range(
        1,
        TOTAL_ROUNDS + 1,
    ):
        analysis = analyze_round(
            all_results,
            round_number,
        )

        round_analyses.append(
            analysis
        )

        print()
        print(
            f"ROUND {round_number}"
        )

        if not analysis["complete"]:
            print(
                "Complete data: NO"
            )

            print(
                "Direction: NOT EVALUATED"
            )

            continue

        print(
            "Complete data: YES"
        )

        print(
            "All closer states > baseline: "
            + (
                "YES"
                if analysis[
                    "direction_supported"
                ]
                else
                "NO"
            )
        )

        print(
            "CLOSER_1 <= CLOSER_2 <= CLOSER_3: "
            + (
                "YES"
                if analysis[
                    "strict_order"
                ]
                else
                "NO"
            )
        )

        print(
            "Return ratio: "
            f"{analysis['return_ratio']:.4f}"
        )

    # ======================================================
    # Repeatability
    # ======================================================

    complete_rounds = [
        analysis
        for analysis in round_analyses
        if analysis["complete"]
    ]

    direction_rounds = [
        analysis
        for analysis in complete_rounds
        if analysis[
            "direction_supported"
        ]
    ]

    strict_rounds = [
        analysis
        for analysis in complete_rounds
        if analysis[
            "strict_order"
        ]
    ]

    print()
    print("=" * 72)
    print(
        "REPEATABILITY"
    )
    print("=" * 72)

    print(
        "Complete rounds: "
        f"{len(complete_rounds)}/{TOTAL_ROUNDS}"
    )

    print(
        "Rounds supporting closer direction: "
        f"{len(direction_rounds)}/{TOTAL_ROUNDS}"
    )

    print(
        "Rounds with strict closer ordering: "
        f"{len(strict_rounds)}/{TOTAL_ROUNDS}"
    )

    # ======================================================
    # Return Recovery
    # ======================================================

    return_ratios = get_valid_ratios(
        all_results,
        "RETURN_BASELINE",
    )

    print()
    print("=" * 72)
    print(
        "RETURN-TO-BASELINE RECOVERY"
    )
    print("=" * 72)

    if return_ratios:
        return_median = statistics.median(
            return_ratios
        )

        print(
            "Median Return Ratio: "
            f"{return_median:.4f}"
        )

        print(
            "Median Return Change: "
            f"{calculate_percent_change(return_median):+.2f}%"
        )

        print(
            "Return Ratio Range: "
            f"{min(return_ratios):.4f}"
            " to "
            f"{max(return_ratios):.4f}"
        )

        print()
        print(
            "No arbitrary recovery tolerance is "
            "applied in this validation."
        )

    else:
        print(
            "Return recovery: NOT EVALUATED"
        )

    # ======================================================
    # Measurement Quality
    # ======================================================

    total_valid_samples = sum(
        row["valid_samples"]
        for row in all_results
    )

    total_invalid_samples = sum(
        row["invalid_samples"]
        for row in all_results
    )

    total_samples = (
        total_valid_samples
        +
        total_invalid_samples
    )

    print()
    print("=" * 72)
    print(
        "MEASUREMENT QUALITY"
    )
    print("=" * 72)

    print(
        "Valid samples: "
        f"{total_valid_samples}"
    )

    print(
        "Invalid samples: "
        f"{total_invalid_samples}"
    )

    if total_samples > 0:
        valid_percent = (
            total_valid_samples
            /
            total_samples
            *
            100.0
        )

        print(
            "Valid sample rate: "
            f"{valid_percent:.2f}%"
        )

    # ======================================================
    # Evidence Conclusion
    # ======================================================

    print()
    print("=" * 72)
    print(
        "VALIDATION EVIDENCE"
    )
    print("=" * 72)

    evidence_supported = (
        len(complete_rounds)
        ==
        TOTAL_ROUNDS
        and
        len(direction_rounds)
        ==
        TOTAL_ROUNDS
    )

    if evidence_supported:
        print(
            "RELATIVE DIRECTION EVIDENCE: PASS"
        )

        print(
            "All 3 rounds produced complete data and "
            "all manually closer states were above "
            "their round baseline."
        )

    else:
        print(
            "RELATIVE DIRECTION EVIDENCE: "
            "CHECK REQUIRED"
        )

        print(
            "Do not lock the metric until the "
            "incomplete or inconsistent rounds "
            "have been reviewed."
        )

    print()
    print(
        "Strict CLOSER_1/2/3 ordering is reported "
        "as supporting evidence only."
    )

    print(
        "RETURN_BASELINE is reported numerically; "
        "no unsupported tolerance is invented."
    )

    print()
    print(
        "TOO_CLOSE THRESHOLD: NOT VALIDATED"
    )

    print(
        "HYSTERESIS: NOT VALIDATED"
    )

    print(
        "PHYSICAL DISTANCE (cm): NOT ESTIMATED"
    )


# ==========================================================
# CSV
# ==========================================================

def save_results(
    all_results,
):
    """
    Save validation evidence separately from old
    threshold experiments.
    """

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
            "relative_screen_distance_camera_"
            f"{timestamp}.csv"
        )
    )

    fieldnames = [
        "round",
        "state",
        "status",
        "reason",

        "total_frames",
        "valid_samples",
        "invalid_samples",

        "baseline_eye_distance_px",
        "current_eye_distance_px",

        "eye_distance_median_px",
        "eye_distance_mean_px",
        "eye_distance_std_px",

        "ratio",
        "percent_change",
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
        "POSTGUARD RELATIVE SCREEN DISTANCE "
        "CAMERA VALIDATION"
    )
    print("=" * 72)

    print()
    print(
        "Protocol:"
    )

    print(
        "BASELINE -> CLOSER_1 -> CLOSER_2 -> "
        "CLOSER_3 -> RETURN_BASELINE"
    )

    print(
        f"Rounds: {TOTAL_ROUNDS}"
    )

    print(
        "Capture per state: "
        f"{CAPTURE_SECONDS:.1f} seconds"
    )

    print()

    print(
        "No ruler or centimeter measurement "
        "is required."
    )

    print(
        "Move mainly forward/backward and avoid "
        "intentional head rotation."
    )

    print()

    # ======================================================
    # Face Model
    # ======================================================

    model_path = get_face_model_path()

    print(
        "Face model:"
    )

    print(
        model_path
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
        # Run 3 Independent Rounds
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
        # Save Evidence
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