"""
PostGuard - Camera Roll Real-Camera Diagnostic Validation

Purpose
-------
Validate the production Camera Roll estimator against an external
physical angle measurement (Ground Truth).

IMPORTANT:
- This script DOES NOT modify production Camera Roll logic.
- Production estimate_scene_tilt() is called directly.
- Additional Hough diagnostics reproduce the current production
  line-detection procedure only for analysis.
- Ground Truth must come from an external angle measuring tool.
- No arbitrary PASS/FAIL accuracy threshold is introduced here.

Recommended Ground Truth angles:
    -5, -3, 0, +3, +5 degrees

Run from:
    C:\\project\\PostGuard\\desktop

Example:
    $env:PYTHONPATH = "C:\\project\\PostGuard\\desktop"

    ..\\backend\\.venv\\Scripts\\python.exe `
        tests\\vision_manual\\test_camera_roll_validation.py

Optional:
    ..\\backend\\.venv\\Scripts\\python.exe `
        tests\\vision_manual\\test_camera_roll_validation.py `
        --device 0 `
        --width 1280 `
        --height 720

Controls
--------
1-5 : select Ground Truth
      1 = -5 deg
      2 = -3 deg
      3 =  0 deg
      4 = +3 deg
      5 = +5 deg

SPACE : capture current Ground Truth test
R     : reset samples for current angle
Q/ESC : quit and save results

Output
------
CSV summary and diagnostic images are saved under:

    tests/vision_manual/results/camera_roll/
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from app.vision.camera_setup.camera_roll import (
    estimate_scene_tilt,
)


# ============================================================
# Configuration
# ============================================================

DEFAULT_DEVICE_INDEX = 0
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720

GROUND_TRUTH_OPTIONS = {
    ord("1"): -5.0,
    ord("2"): -3.0,
    ord("3"): 0.0,
    ord("4"): 3.0,
    ord("5"): 5.0,
}

TARGET_VALID_SAMPLES = 30

MAX_CAPTURE_SECONDS = 10.0

TEMPORAL_HISTORY_SIZE = 15

MIN_PRODUCTION_SAMPLES = 5

RESULTS_DIRECTORY = (
    Path(__file__).resolve().parent
    / "results"
    / "camera_roll"
)


# ============================================================
# Arguments
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PostGuard real-camera Camera Roll "
            "diagnostic validation."
        )
    )

    parser.add_argument(
        "--device",
        type=int,
        default=DEFAULT_DEVICE_INDEX,
        help=(
            "OpenCV camera device index. "
            f"Default: {DEFAULT_DEVICE_INDEX}"
        ),
    )

    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help=(
            "Requested camera width. "
            f"Default: {DEFAULT_WIDTH}"
        ),
    )

    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_HEIGHT,
        help=(
            "Requested camera height. "
            f"Default: {DEFAULT_HEIGHT}"
        ),
    )

    return parser.parse_args()


# ============================================================
# Camera
# ============================================================

def open_camera(
    device_index: int,
    width: int,
    height: int,
) -> cv2.VideoCapture:

    capture = cv2.VideoCapture(
        device_index
    )

    if not capture.isOpened():
        capture.release()

        raise RuntimeError(
            f"Unable to open camera device "
            f"{device_index}."
        )

    # Same principle used by PostGuard:
    # set() is only a request.
    # Actual frame shape remains source of truth.
    capture.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        width,
    )

    capture.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        height,
    )

    return capture


# ============================================================
# Diagnostic Hough Analysis
# ============================================================

def analyze_hough_lines(
    frame: np.ndarray,
) -> dict:
    """
    Reproduce the CURRENT production line detection logic.

    This function is intentionally kept separate from
    estimate_scene_tilt().

    It allows us to inspect WHY production returned a value
    or None without changing production behavior.
    """

    height, width = frame.shape[:2]

    x_start = int(
        width * 0.2
    )

    x_end = int(
        width * 0.8
    )

    y_start = int(
        height * 0.2
    )

    y_end = int(
        height * 0.8
    )

    crop = frame[
        y_start:y_end,
        x_start:x_end,
    ]

    gray = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2GRAY,
    )

    blurred = cv2.GaussianBlur(
        gray,
        (5, 5),
        0,
    )

    edges = cv2.Canny(
        blurred,
        50,
        150,
    )

    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=60,
        minLineLength=(
            crop.shape[0] // 4
        ),
        maxLineGap=10,
    )

    accepted = []
    rejected = []

    if lines is not None:

        lines = lines.reshape(
            -1,
            4,
        )

        for line in lines:

            x1, y1, x2, y2 = [
                int(value)
                for value in line
            ]

            dx = (
                x2 - x1
            )

            dy = (
                y2 - y1
            )

            length = math.hypot(
                dx,
                dy,
            )

            raw_angle = math.degrees(
                math.atan2(
                    dy,
                    dx,
                )
            )

            normalized_angle = (
                (raw_angle + 45.0)
                % 90.0
                - 45.0
            )

            line_info = {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,

                "length": float(
                    length
                ),

                "raw_angle": float(
                    raw_angle
                ),

                "normalized_angle": float(
                    normalized_angle
                ),
            }

            if (
                abs(
                    normalized_angle
                )
                <= 15.0
            ):
                accepted.append(
                    line_info
                )

            else:
                rejected.append(
                    line_info
                )

    accepted_angles = [
        item[
            "normalized_angle"
        ]
        for item in accepted
    ]

    diagnostic_median = None

    if accepted_angles:
        diagnostic_median = float(
            np.median(
                accepted_angles
            )
        )

    return {
        "crop": crop,
        "edges": edges,

        "crop_x": x_start,
        "crop_y": y_start,

        "total_lines": (
            len(accepted)
            + len(rejected)
        ),

        "accepted_lines": accepted,
        "rejected_lines": rejected,

        "accepted_count": len(
            accepted
        ),

        "rejected_count": len(
            rejected
        ),

        "accepted_angles": (
            accepted_angles
        ),

        "diagnostic_median": (
            diagnostic_median
        ),
    }


# ============================================================
# Visualization
# ============================================================

def draw_diagnostic_overlay(
    frame: np.ndarray,
    diagnostic: dict,
    production_value,
    ground_truth: float,
    history: deque,
    capture_active: bool,
) -> np.ndarray:

    display = frame.copy()

    crop_x = diagnostic[
        "crop_x"
    ]

    crop_y = diagnostic[
        "crop_y"
    ]

    # --------------------------------------------------------
    # ROI
    # --------------------------------------------------------

    crop = diagnostic[
        "crop"
    ]

    crop_height, crop_width = (
        crop.shape[:2]
    )

    cv2.rectangle(
        display,
        (
            crop_x,
            crop_y,
        ),
        (
            crop_x + crop_width,
            crop_y + crop_height,
        ),
        (255, 255, 0),
        2,
    )

    # --------------------------------------------------------
    # Accepted lines
    # --------------------------------------------------------

    for line in diagnostic[
        "accepted_lines"
    ]:

        cv2.line(
            display,
            (
                crop_x
                + line["x1"],

                crop_y
                + line["y1"],
            ),
            (
                crop_x
                + line["x2"],

                crop_y
                + line["y2"],
            ),
            (0, 255, 0),
            3,
        )

    # --------------------------------------------------------
    # Rejected lines
    # --------------------------------------------------------

    for line in diagnostic[
        "rejected_lines"
    ]:

        cv2.line(
            display,
            (
                crop_x
                + line["x1"],

                crop_y
                + line["y1"],
            ),
            (
                crop_x
                + line["x2"],

                crop_y
                + line["y2"],
            ),
            (0, 0, 255),
            1,
        )

    # --------------------------------------------------------
    # Text
    # --------------------------------------------------------

    if production_value is None:
        production_text = "NONE"
    else:
        production_text = (
            f"{production_value:+.2f} deg"
        )

    if diagnostic[
        "diagnostic_median"
    ] is None:

        diagnostic_text = "NONE"

    else:
        diagnostic_text = (
            f"{diagnostic['diagnostic_median']:+.2f} deg"
        )

    if history:
        temporal_median = float(
            np.median(
                list(history)
            )
        )

        temporal_text = (
            f"{temporal_median:+.2f} deg"
        )

    else:
        temporal_text = "NONE"

    lines = [
        (
            "POSTGUARD CAMERA ROLL "
            "VALIDATION"
        ),

        (
            f"Ground Truth: "
            f"{ground_truth:+.1f} deg"
        ),

        (
            "Production estimate: "
            f"{production_text}"
        ),

        (
            "Diagnostic median: "
            f"{diagnostic_text}"
        ),

        (
            "Hough lines: "
            f"{diagnostic['total_lines']}"
        ),

        (
            "Accepted lines: "
            f"{diagnostic['accepted_count']}"
        ),

        (
            "Rejected lines: "
            f"{diagnostic['rejected_count']}"
        ),

        (
            "Temporal valid samples: "
            f"{len(history)}/"
            f"{TEMPORAL_HISTORY_SIZE}"
        ),

        (
            "Temporal median: "
            f"{temporal_text}"
        ),

        (
            "CAPTURE: "
            + (
                "ACTIVE"
                if capture_active
                else "IDLE"
            )
        ),

        (
            "1=-5  2=-3  3=0  "
            "4=+3  5=+5"
        ),

        (
            "SPACE=capture  "
            "R=reset  Q/ESC=quit"
        ),
    ]

    y = 30

    for text in lines:

        cv2.putText(
            display,
            text,
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        y += 28

    return display


# ============================================================
# Result Helpers
# ============================================================

def calculate_absolute_error(
    estimated_value,
    ground_truth: float,
):
    """
    Raw signed-coordinate comparison.

    IMPORTANT:
    Because the Desktop calibration flow currently uses a
    mirrored setup frame, sign interpretation must be reviewed
    separately.

    Therefore this value is reported as evidence, not used as
    an automatic PASS/FAIL criterion.
    """

    if estimated_value is None:
        return None

    return abs(
        float(estimated_value)
        - float(ground_truth)
    )


def calculate_magnitude_error(
    estimated_value,
    ground_truth: float,
):
    """
    Compare angle magnitudes independently of sign convention.

    This is useful while mirrored/non-mirrored coordinate
    semantics are still being validated.
    """

    if estimated_value is None:
        return None

    return abs(
        abs(
            float(estimated_value)
        )
        - abs(
            float(ground_truth)
        )
    )


def format_optional(
    value,
    digits: int = 3,
) -> str:

    if value is None:
        return "NONE"

    return (
        f"{float(value):.{digits}f}"
    )


# ============================================================
# Capture One Ground Truth Case
# ============================================================

def capture_ground_truth_case(
    capture: cv2.VideoCapture,
    ground_truth: float,
) -> tuple[dict, np.ndarray | None]:

    print()
    print("=" * 72)
    print(
        "CAMERA ROLL CAPTURE"
    )
    print("=" * 72)

    print(
        "Ground Truth     : "
        f"{ground_truth:+.1f} deg"
    )

    print(
        "Keep the camera physically fixed "
        "during this capture."
    )

    print(
        "Collecting up to "
        f"{TARGET_VALID_SAMPLES} valid "
        "production samples..."
    )

    production_values = []

    accepted_line_counts = []

    total_line_counts = []

    diagnostic_medians = []

    total_frames = 0

    none_frames = 0

    best_frame = None

    best_accepted_count = -1

    start_time = time.monotonic()

    while True:

        success, raw_frame = (
            capture.read()
        )

        if (
            not success
            or raw_frame is None
        ):
            continue

        total_frames += 1

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Desktop camera calibration currently sends the
        # MIRRORED setup frame into estimate_scene_tilt().
        #
        # Reproduce that convention here.
        # ----------------------------------------------------

        setup_frame = cv2.flip(
            raw_frame,
            1,
        )

        production_value = (
            estimate_scene_tilt(
                setup_frame
            )
        )

        diagnostic = (
            analyze_hough_lines(
                setup_frame
            )
        )

        accepted_line_counts.append(
            diagnostic[
                "accepted_count"
            ]
        )

        total_line_counts.append(
            diagnostic[
                "total_lines"
            ]
        )

        if (
            diagnostic[
                "diagnostic_median"
            ]
            is not None
        ):
            diagnostic_medians.append(
                diagnostic[
                    "diagnostic_median"
                ]
            )

        if production_value is None:
            none_frames += 1

        else:
            production_values.append(
                float(
                    production_value
                )
            )

        if (
            diagnostic[
                "accepted_count"
            ]
            > best_accepted_count
        ):
            best_accepted_count = (
                diagnostic[
                    "accepted_count"
                ]
            )

            best_frame = (
                setup_frame.copy()
            )

        elapsed = (
            time.monotonic()
            - start_time
        )

        if (
            len(production_values)
            >= TARGET_VALID_SAMPLES
        ):
            break

        if (
            elapsed
            >= MAX_CAPTURE_SECONDS
        ):
            break

    # --------------------------------------------------------
    # Representative values
    # --------------------------------------------------------

    production_median = None
    production_mean = None
    production_std = None

    if production_values:

        production_median = float(
            np.median(
                production_values
            )
        )

        production_mean = float(
            np.mean(
                production_values
            )
        )

        production_std = float(
            np.std(
                production_values
            )
        )

    diagnostic_median = None

    if diagnostic_medians:
        diagnostic_median = float(
            np.median(
                diagnostic_medians
            )
        )

    mean_accepted_lines = (
        float(
            np.mean(
                accepted_line_counts
            )
        )
        if accepted_line_counts
        else 0.0
    )

    median_accepted_lines = (
        float(
            np.median(
                accepted_line_counts
            )
        )
        if accepted_line_counts
        else 0.0
    )

    mean_total_lines = (
        float(
            np.mean(
                total_line_counts
            )
        )
        if total_line_counts
        else 0.0
    )

    valid_samples = len(
        production_values
    )

    detection_rate = (
        valid_samples
        / total_frames
        * 100.0
        if total_frames > 0
        else 0.0
    )

    signed_error = (
        calculate_absolute_error(
            production_median,
            ground_truth,
        )
    )

    magnitude_error = (
        calculate_magnitude_error(
            production_median,
            ground_truth,
        )
    )

    result = {
        "tested_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "ground_truth_deg": (
            float(
                ground_truth
            )
        ),

        "total_frames": (
            total_frames
        ),

        "valid_production_samples": (
            valid_samples
        ),

        "none_frames": (
            none_frames
        ),

        "detection_rate_percent": (
            detection_rate
        ),

        "production_median_deg": (
            production_median
        ),

        "production_mean_deg": (
            production_mean
        ),

        "production_std_deg": (
            production_std
        ),

        "diagnostic_median_deg": (
            diagnostic_median
        ),

        "mean_hough_lines": (
            mean_total_lines
        ),

        "mean_accepted_lines": (
            mean_accepted_lines
        ),

        "median_accepted_lines": (
            median_accepted_lines
        ),

        "max_accepted_lines": (
            max(
                accepted_line_counts
            )
            if accepted_line_counts
            else 0
        ),

        "signed_coordinate_error_deg": (
            signed_error
        ),

        "magnitude_error_deg": (
            magnitude_error
        ),

        "production_returned_value": (
            valid_samples > 0
        ),

        "automatic_pass_fail": (
            "NOT_DEFINED"
        ),
    }

    print()
    print("-" * 72)

    print(
        "Frames            : "
        f"{total_frames}"
    )

    print(
        "Valid samples     : "
        f"{valid_samples}"
    )

    print(
        "None frames       : "
        f"{none_frames}"
    )

    print(
        "Detection rate    : "
        f"{detection_rate:.2f}%"
    )

    print(
        "Production median : "
        f"{format_optional(production_median)} deg"
    )

    print(
        "Production mean   : "
        f"{format_optional(production_mean)} deg"
    )

    print(
        "Production std    : "
        f"{format_optional(production_std)} deg"
    )

    print(
        "Diagnostic median : "
        f"{format_optional(diagnostic_median)} deg"
    )

    print(
        "Mean Hough lines  : "
        f"{mean_total_lines:.2f}"
    )

    print(
        "Mean accepted     : "
        f"{mean_accepted_lines:.2f}"
    )

    print(
        "Median accepted   : "
        f"{median_accepted_lines:.2f}"
    )

    print(
        "Max accepted      : "
        f"{result['max_accepted_lines']}"
    )

    print(
        "Signed error      : "
        f"{format_optional(signed_error)} deg"
    )

    print(
        "Magnitude error   : "
        f"{format_optional(magnitude_error)} deg"
    )

    print(
        "PASS/FAIL         : "
        "NOT DEFINED"
    )

    print("-" * 72)

    return (
        result,
        best_frame,
    )


# ============================================================
# Save Results
# ============================================================

def save_csv(
    rows: list[dict],
    timestamp: str,
) -> Path:

    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        RESULTS_DIRECTORY
        / (
            "camera_roll_validation_"
            f"{timestamp}.csv"
        )
    )

    fieldnames = [
        "tested_at",
        "ground_truth_deg",

        "total_frames",
        "valid_production_samples",
        "none_frames",
        "detection_rate_percent",

        "production_median_deg",
        "production_mean_deg",
        "production_std_deg",

        "diagnostic_median_deg",

        "mean_hough_lines",
        "mean_accepted_lines",
        "median_accepted_lines",
        "max_accepted_lines",

        "signed_coordinate_error_deg",
        "magnitude_error_deg",

        "production_returned_value",

        "automatic_pass_fail",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )

    return output_path


def save_evidence_image(
    frame: np.ndarray | None,
    ground_truth: float,
    timestamp: str,
) -> Path | None:

    if frame is None:
        return None

    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    angle_name = (
        f"{ground_truth:+.1f}"
        .replace("+", "plus_")
        .replace("-", "minus_")
        .replace(".", "_")
    )

    output_path = (
        RESULTS_DIRECTORY
        / (
            "camera_roll_"
            f"{angle_name}_"
            f"{timestamp}.jpg"
        )
    )

    cv2.imwrite(
        str(output_path),
        frame,
    )

    return output_path


# ============================================================
# Summary
# ============================================================

def print_summary(
    rows: list[dict],
) -> None:

    print()
    print()
    print("=" * 88)

    print(
        "POSTGUARD CAMERA ROLL "
        "VALIDATION SUMMARY"
    )

    print("=" * 88)

    header = (
        f"{'GT':>7} | "
        f"{'Detected':>10} | "
        f"{'Valid':>7} | "
        f"{'Rate':>8} | "
        f"{'Mean Lines':>10} | "
        f"{'Mean Accepted':>13} | "
        f"{'Mag Error':>9}"
    )

    print(
        header
    )

    print(
        "-" * len(header)
    )

    for row in rows:

        detected = (
            "NONE"
            if row[
                "production_median_deg"
            ] is None
            else (
                f"{row['production_median_deg']:+.2f}"
            )
        )

        magnitude_error = (
            "NONE"
            if row[
                "magnitude_error_deg"
            ] is None
            else (
                f"{row['magnitude_error_deg']:.2f}"
            )
        )

        print(
            f"{row['ground_truth_deg']:+7.1f} | "
            f"{detected:>10} | "
            f"{row['valid_production_samples']:>7} | "
            f"{row['detection_rate_percent']:>7.2f}% | "
            f"{row['mean_hough_lines']:>10.2f} | "
            f"{row['mean_accepted_lines']:>13.2f} | "
            f"{magnitude_error:>9}"
        )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "- No accuracy PASS/FAIL threshold is "
        "defined by this test."
    )

    print(
        "- Signed error must be interpreted together "
        "with the mirrored Camera Roll convention."
    )

    print(
        "- Magnitude error is reported separately so "
        "sign convention does not hide measurement quality."
    )

    print(
        "- Low detection rate together with low accepted-line "
        "count points toward the scene-line detector."
    )

    print(
        "- A low residual after Auto correction alone does NOT "
        "prove Ground Truth accuracy."
    )

    print("=" * 88)


# ============================================================
# Main
# ============================================================

def main() -> int:

    args = parse_args()

    print()
    print("=" * 72)

    print(
        "POSTGUARD CAMERA ROLL "
        "REAL-CAMERA VALIDATION"
    )

    print("=" * 72)

    print(
        f"Camera device : {args.device}"
    )

    print(
        "Requested     : "
        f"{args.width}x{args.height}"
    )

    print()
    print(
        "Ground Truth must come from an "
        "external physical angle tool."
    )

    print()
    print(
        "Recommended sequence:"
    )

    print(
        "-5 -> -3 -> 0 -> +3 -> +5 degrees"
    )

    capture = None

    rows = []

    selected_ground_truth = 0.0

    temporal_history = deque(
        maxlen=TEMPORAL_HISTORY_SIZE
    )

    session_timestamp = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    try:

        capture = open_camera(
            args.device,
            args.width,
            args.height,
        )

        # Warm up camera
        for _ in range(10):
            capture.read()

        while True:

            success, raw_frame = (
                capture.read()
            )

            if (
                not success
                or raw_frame is None
            ):
                continue

            actual_height, actual_width = (
                raw_frame.shape[:2]
            )

            # Desktop calibration convention:
            # analyze MIRRORED setup frame.
            setup_frame = cv2.flip(
                raw_frame,
                1,
            )

            production_value = (
                estimate_scene_tilt(
                    setup_frame
                )
            )

            if production_value is not None:

                temporal_history.append(
                    float(
                        production_value
                    )
                )

            diagnostic = (
                analyze_hough_lines(
                    setup_frame
                )
            )

            display = (
                draw_diagnostic_overlay(
                    frame=setup_frame,
                    diagnostic=diagnostic,
                    production_value=(
                        production_value
                    ),
                    ground_truth=(
                        selected_ground_truth
                    ),
                    history=(
                        temporal_history
                    ),
                    capture_active=False,
                )
            )

            cv2.putText(
                display,
                (
                    "Actual camera: "
                    f"{actual_width}x"
                    f"{actual_height}"
                ),
                (
                    20,
                    display.shape[0] - 20,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow(
                "PostGuard Camera Roll Validation",
                display,
            )

            key = (
                cv2.waitKey(1)
                & 0xFF
            )

            # ------------------------------------------------
            # Ground Truth selection
            # ------------------------------------------------

            if key in GROUND_TRUTH_OPTIONS:

                selected_ground_truth = (
                    GROUND_TRUTH_OPTIONS[
                        key
                    ]
                )

                temporal_history.clear()

                print()
                print(
                    "Selected Ground Truth: "
                    f"{selected_ground_truth:+.1f} deg"
                )

                print(
                    "Physically set the camera to this "
                    "angle, keep it fixed, then press SPACE."
                )

            # ------------------------------------------------
            # Reset
            # ------------------------------------------------

            elif key in (
                ord("r"),
                ord("R"),
            ):

                temporal_history.clear()

                print(
                    "Temporal samples reset."
                )

            # ------------------------------------------------
            # Capture
            # ------------------------------------------------

            elif key == 32:

                result, evidence_frame = (
                    capture_ground_truth_case(
                        capture=(
                            capture
                        ),
                        ground_truth=(
                            selected_ground_truth
                        ),
                    )
                )

                rows.append(
                    result
                )

                image_path = (
                    save_evidence_image(
                        evidence_frame,
                        selected_ground_truth,
                        session_timestamp,
                    )
                )

                if image_path is not None:
                    print(
                        "Evidence image    : "
                        f"{image_path}"
                    )

                temporal_history.clear()

            # ------------------------------------------------
            # Quit
            # ------------------------------------------------

            elif key in (
                ord("q"),
                ord("Q"),
                27,
            ):
                break

    except KeyboardInterrupt:

        print()
        print(
            "Validation cancelled."
        )

    finally:

        if capture is not None:
            capture.release()

        cv2.destroyAllWindows()

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    if not rows:

        print()
        print(
            "No Ground Truth cases were captured."
        )

        return 0

    print_summary(
        rows
    )

    csv_path = save_csv(
        rows,
        session_timestamp,
    )

    print()
    print(
        "CSV RESULT:"
    )

    print(
        csv_path
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )