from __future__ import annotations

import csv
import json
import math
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2


# ============================================================
# PATH SETUP
# ============================================================

TEST_FILE = Path(__file__).resolve()

# C:\project\PostGuard\backend
BACKEND_DIR = TEST_FILE.parents[3]

# C:\project\PostGuard\backend\camera_card
CAMERA_CARD_DIR = TEST_FILE.parents[2]

for path in (
    BACKEND_DIR,
    CAMERA_CARD_DIR,
):
    path_str = str(path)

    if path_str not in sys.path:
        sys.path.insert(0, path_str)


from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)


# ============================================================
# CONFIG
# ============================================================

RUNNER_VERSION = "1.0-neck-lateral-raw-components"

CAMERA_ID = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

CAPTURE_SECONDS = 5.0
MIN_VALID_FRAMES = 30

WINDOW_NAME = (
    "PostGuard - Neck Lateral Raw Component Diagnostic"
)

OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "neck_lateral_raw_components"
)


# ============================================================
# TEST CASES
# ============================================================

TEST_CASES = [
    {
        "id": "neutral",
        "title": "Neutral",
        "instruction": (
            "Sit naturally. Keep head straight. "
            "Relax both shoulders."
        ),
    },
    {
        "id": "neck_left_natural",
        "title": "Neck Tilt Left - Natural",
        "instruction": (
            "Tilt HEAD LEFT naturally. "
            "Do not intentionally raise or lower either shoulder."
        ),
    },
]


# ============================================================
# COLORS
# ============================================================

WHITE = (255, 255, 255)
GREEN = (0, 220, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
CYAN = (255, 255, 0)
BLACK = (0, 0, 0)


# ============================================================
# BASIC HELPERS
# ============================================================

def finite_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(number):
        return None

    return number


def percentile(
    values: list[float],
    fraction: float,
) -> float | None:

    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return float(ordered[0])

    position = (
        (len(ordered) - 1)
        * fraction
    )

    lower = int(
        math.floor(position)
    )

    upper = int(
        math.ceil(position)
    )

    if lower == upper:
        return float(
            ordered[lower]
        )

    weight = (
        position
        - lower
    )

    return float(
        ordered[lower]
        * (1.0 - weight)
        +
        ordered[upper]
        * weight
    )


def summarize(
    values,
) -> dict[str, Any]:

    clean = []

    for value in values:

        number = finite_number(
            value
        )

        if number is not None:
            clean.append(number)

    if not clean:

        return {
            "count": 0,
            "mean": None,
            "median": None,
            "sd": None,
            "min": None,
            "max": None,
            "p05": None,
            "p25": None,
            "p75": None,
            "p95": None,
        }

    clean.sort()

    return {
        "count": len(clean),

        "mean": float(
            statistics.mean(clean)
        ),

        "median": float(
            statistics.median(clean)
        ),

        "sd": (
            float(
                statistics.stdev(clean)
            )
            if len(clean) >= 2
            else 0.0
        ),

        "min": float(
            min(clean)
        ),

        "max": float(
            max(clean)
        ),

        "p05": percentile(
            clean,
            0.05,
        ),

        "p25": percentile(
            clean,
            0.25,
        ),

        "p75": percentile(
            clean,
            0.75,
        ),

        "p95": percentile(
            clean,
            0.95,
        ),
    }


# ============================================================
# DISPLAY
# ============================================================

def draw_text(
    frame,
    text,
    x,
    y,
    color=WHITE,
    scale=0.55,
    thickness=1,
):

    cv2.putText(
        frame,
        str(text),
        (int(x), int(y)),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


# ============================================================
# PIPELINE ACCESS
# ============================================================

def get_feature(
    result,
    feature_name,
) -> dict:

    features = (
        result.get("features")
        or {}
    )

    feature = features.get(
        feature_name
    )

    if not isinstance(
        feature,
        dict,
    ):
        return {}

    return feature


def get_feature_value(
    result,
    feature_name,
) -> float | None:

    feature = get_feature(
        result,
        feature_name,
    )

    if feature.get("valid") is not True:
        return None

    return finite_number(
        feature.get("value")
    )


def get_context_state(
    result,
) -> str:

    context = (
        result.get("context")
        or {}
    )

    return str(
        context.get(
            "state",
            "UNKNOWN",
        )
    )


def context_allows_evaluation(
    result,
) -> bool:

    context = (
        result.get("context")
        or {}
    )

    return (
        context.get("state")
        == "VALID"
        and
        context.get(
            "allow_posture_evaluation"
        )
        is True
    )


# ============================================================
# LANDMARK ACCESS
# ============================================================

def get_pose_points(
    result,
) -> dict:

    landmarks = (
        result.get("landmarks")
        or {}
    )

    pose = landmarks.get(
        "pose"
    )

    if not isinstance(
        pose,
        dict,
    ):
        return {}

    return pose


def landmark_number(
    point,
    key,
) -> float | None:

    if not isinstance(
        point,
        dict,
    ):
        return None

    return finite_number(
        point.get(key)
    )


# ============================================================
# ANGLE NORMALIZATION
# ============================================================

def normalize_relative_angle(
    angle,
) -> float | None:

    angle = finite_number(
        angle
    )

    if angle is None:
        return None

    while angle > 90:
        angle -= 180

    while angle < -90:
        angle += 180

    return float(angle)


# ============================================================
# RAW COMPONENT EXTRACTION
# ============================================================

def get_neck_raw_components(
    result,
) -> dict[str, Any]:

    neck_feature = get_feature(
        result,
        "neck_lateral_tilt",
    )

    extra = (
        neck_feature.get("extra")
        or {}
    )

    if not isinstance(
        extra,
        dict,
    ):
        extra = {}

    ear_angle = finite_number(
        extra.get("ear_angle")
    )

    shoulder_angle = finite_number(
        extra.get("shoulder_angle")
    )

    neck_lateral_tilt = None

    if neck_feature.get("valid") is True:
        neck_lateral_tilt = (
            finite_number(
                neck_feature.get("value")
            )
        )

    formula_value = None

    if (
        ear_angle is not None
        and
        shoulder_angle is not None
    ):

        formula_value = (
            normalize_relative_angle(
                ear_angle
                -
                shoulder_angle
            )
        )

    formula_error = None

    if (
        formula_value is not None
        and
        neck_lateral_tilt is not None
    ):

        formula_error = (
            neck_lateral_tilt
            -
            formula_value
        )

    return {
        "ear_angle": ear_angle,

        "shoulder_angle": (
            shoulder_angle
        ),

        "neck_lateral_tilt": (
            neck_lateral_tilt
        ),

        "formula_neck_lateral": (
            formula_value
        ),

        "formula_error": (
            formula_error
        ),
    }


# ============================================================
# SHOULDER LANDMARK GEOMETRY
# ============================================================

def get_shoulder_geometry(
    result,
) -> dict[str, Any]:

    pose = get_pose_points(
        result
    )

    left = pose.get(
        "left_shoulder"
    )

    right = pose.get(
        "right_shoulder"
    )

    left_x = landmark_number(
        left,
        "x",
    )

    left_y = landmark_number(
        left,
        "y",
    )

    right_x = landmark_number(
        right,
        "x",
    )

    right_y = landmark_number(
        right,
        "y",
    )

    if (
        left_x is None
        or left_y is None
        or right_x is None
        or right_y is None
    ):

        return {
            "left_shoulder_x": left_x,
            "left_shoulder_y": left_y,
            "right_shoulder_x": right_x,
            "right_shoulder_y": right_y,

            "landmark_dx_px": None,
            "landmark_dy_px": None,
            "shoulder_width_px": None,
            "normalized_dy": None,
        }

    dx = (
        right_x
        -
        left_x
    )

    dy = (
        right_y
        -
        left_y
    )

    shoulder_width = abs(dx)

    normalized_dy = None

    if shoulder_width > 0:

        normalized_dy = (
            dy
            /
            shoulder_width
        )

    return {
        "left_shoulder_x": left_x,
        "left_shoulder_y": left_y,

        "right_shoulder_x": right_x,
        "right_shoulder_y": right_y,

        "landmark_dx_px": dx,
        "landmark_dy_px": dy,

        "shoulder_width_px": (
            shoulder_width
        ),

        "normalized_dy": (
            normalized_dy
        ),
    }


# ============================================================
# BUILD FRAME ROW
# ============================================================

def build_frame_row(
    *,
    case,
    frame_index,
    elapsed,
    result,
) -> dict[str, Any]:

    raw = get_neck_raw_components(
        result
    )

    geometry = get_shoulder_geometry(
        result
    )

    shoulder_tilt = (
        get_feature_value(
            result,
            "shoulder_tilt",
        )
    )

    shoulder_component_error = None

    if (
        shoulder_tilt is not None
        and
        raw["shoulder_angle"]
        is not None
    ):

        shoulder_component_error = (
            shoulder_tilt
            -
            raw[
                "shoulder_angle"
            ]
        )

    row = {
        "case_id": case["id"],
        "case_title": case["title"],

        "frame_index": frame_index,

        "elapsed_seconds": (
            elapsed
        ),

        "context_state": (
            get_context_state(
                result
            )
        ),

        "allow_posture_evaluation": (
            context_allows_evaluation(
                result
            )
        ),

        # ------------------------------------------
        # Production outputs
        # ------------------------------------------

        "shoulder_tilt": (
            shoulder_tilt
        ),

        "neck_lateral_tilt": (
            raw[
                "neck_lateral_tilt"
            ]
        ),

        # ------------------------------------------
        # Raw components from DetectionPipeline
        # ------------------------------------------

        "ear_angle": (
            raw[
                "ear_angle"
            ]
        ),

        "shoulder_angle": (
            raw[
                "shoulder_angle"
            ]
        ),

        # ------------------------------------------
        # Formula verification
        # ------------------------------------------

        "formula_neck_lateral": (
            raw[
                "formula_neck_lateral"
            ]
        ),

        "formula_error": (
            raw[
                "formula_error"
            ]
        ),

        # ------------------------------------------
        # Compare production shoulder feature
        # against neck-reference shoulder angle
        # ------------------------------------------

        "shoulder_component_error": (
            shoulder_component_error
        ),
    }

    row.update(
        geometry
    )

    return row


# ============================================================
# VALID FRAME
# ============================================================

def row_is_valid(
    row,
) -> bool:

    if (
        row.get(
            "allow_posture_evaluation"
        )
        is not True
    ):
        return False

    required = (
        "ear_angle",
        "shoulder_angle",
        "neck_lateral_tilt",
        "formula_neck_lateral",
        "shoulder_tilt",
        "landmark_dy_px",
    )

    for key in required:

        if finite_number(
            row.get(key)
        ) is None:

            return False

    return True


# ============================================================
# LIVE DISPLAY
# ============================================================

def fmt(
    value,
    digits=3,
):

    number = finite_number(
        value
    )

    if number is None:
        return "N/A"

    return (
        f"{number:+.{digits}f}"
    )


def draw_live_display(
    frame,
    result,
    case,
    *,
    capturing,
    elapsed=0.0,
):

    # Detection uses unmirrored input.
    # Mirror only for display.
    display = cv2.flip(
        frame,
        1,
    )

    overlay = display.copy()

    cv2.rectangle(
        overlay,
        (0, 0),
        (
            min(
                display.shape[1],
                1000,
            ),
            min(
                display.shape[0],
                470,
            ),
        ),
        BLACK,
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.72,
        display,
        0.28,
        0,
        display,
    )

    raw = get_neck_raw_components(
        result
    )

    shoulder = (
        get_feature_value(
            result,
            "shoulder_tilt",
        )
    )

    geometry = (
        get_shoulder_geometry(
            result
        )
    )

    y = 35

    draw_text(
        display,
        "POSTGUARD - NECK LATERAL RAW COMPONENT DIAGNOSTIC",
        20,
        y,
        WHITE,
        0.60,
        2,
    )

    y += 40

    draw_text(
        display,
        case["title"],
        20,
        y,
        YELLOW,
        0.60,
        2,
    )

    y += 30

    draw_text(
        display,
        case["instruction"],
        20,
        y,
        WHITE,
        0.45,
        1,
    )

    y += 40

    valid_context = (
        context_allows_evaluation(
            result
        )
    )

    draw_text(
        display,
        (
            "Context: "
            f"{get_context_state(result)}"
        ),
        20,
        y,
        GREEN
        if valid_context
        else RED,
        0.52,
        2,
    )

    y += 34

    draw_text(
        display,
        (
            "Ear Angle: "
            f"{fmt(raw['ear_angle'])} deg"
        ),
        20,
        y,
        CYAN,
        0.56,
        2,
    )

    y += 34

    draw_text(
        display,
        (
            "Shoulder Angle: "
            f"{fmt(raw['shoulder_angle'])} deg"
        ),
        20,
        y,
        CYAN,
        0.56,
        2,
    )

    y += 34

    draw_text(
        display,
        (
            "Neck Relative: "
            f"{fmt(raw['neck_lateral_tilt'])} deg"
        ),
        20,
        y,
        YELLOW,
        0.56,
        2,
    )

    y += 34

    draw_text(
        display,
        (
            "Ear - Shoulder: "
            f"{fmt(raw['formula_neck_lateral'])} deg"
        ),
        20,
        y,
        WHITE,
        0.52,
        1,
    )

    y += 34

    draw_text(
        display,
        (
            "Formula Error: "
            f"{fmt(raw['formula_error'], 6)} deg"
        ),
        20,
        y,
        GREEN,
        0.52,
        1,
    )

    y += 34

    draw_text(
        display,
        (
            "Shoulder Tilt: "
            f"{fmt(shoulder)} deg"
        ),
        20,
        y,
        WHITE,
        0.52,
        1,
    )

    y += 34

    draw_text(
        display,
        (
            "Landmark dY: "
            f"{fmt(geometry['landmark_dy_px'], 2)} px"
        ),
        20,
        y,
        WHITE,
        0.52,
        1,
    )

    y += 40

    if capturing:

        draw_text(
            display,
            (
                "CAPTURING "
                f"{elapsed:.1f}/"
                f"{CAPTURE_SECONDS:.1f}s"
            ),
            20,
            y,
            CYAN,
            0.56,
            2,
        )

    else:

        draw_text(
            display,
            "Prepare posture then press S",
            20,
            y,
            CYAN,
            0.56,
            2,
        )

    return display


# ============================================================
# CAPTURE ONE CASE
# ============================================================

def capture_case(
    camera,
    pipeline,
    case,
):

    print()
    print("=" * 110)

    print(
        case["title"]
    )

    print(
        case["instruction"]
    )

    print()

    print(
        "Prepare posture naturally."
    )

    print(
        "Press S to capture."
    )

    print("=" * 110)

    # ========================================================
    # WAIT FOR S
    # ========================================================

    while True:

        ok, frame = camera.read()

        if not ok:
            continue

        now = time.perf_counter()

        result = pipeline.process_frame(
            frame,
            timestamp=now,
        )

        display = draw_live_display(
            frame,
            result,
            case,
            capturing=False,
        )

        cv2.imshow(
            WINDOW_NAME,
            display,
        )

        key = (
            cv2.waitKey(1)
            &
            0xFF
        )

        if key in (
            ord("q"),
            ord("Q"),
            27,
        ):
            raise KeyboardInterrupt

        if key in (
            ord("s"),
            ord("S"),
        ):
            break

    # ========================================================
    # CAPTURE
    # ========================================================

    start = time.perf_counter()

    frame_index = 0

    all_rows = []
    valid_rows = []

    while True:

        ok, frame = camera.read()

        if not ok:
            continue

        now = time.perf_counter()

        elapsed = (
            now
            -
            start
        )

        frame_index += 1

        result = pipeline.process_frame(
            frame,
            timestamp=now,
        )

        row = build_frame_row(
            case=case,
            frame_index=frame_index,
            elapsed=elapsed,
            result=result,
        )

        all_rows.append(row)

        if row_is_valid(row):
            valid_rows.append(row)

        display = draw_live_display(
            frame,
            result,
            case,
            capturing=True,
            elapsed=elapsed,
        )

        cv2.imshow(
            WINDOW_NAME,
            display,
        )

        key = (
            cv2.waitKey(1)
            &
            0xFF
        )

        if key in (
            ord("q"),
            ord("Q"),
            27,
        ):
            raise KeyboardInterrupt

        if elapsed >= CAPTURE_SECONDS:
            break

    return (
        all_rows,
        valid_rows,
    )


# ============================================================
# ANALYSIS
# ============================================================

SUMMARY_METRICS = (
    "ear_angle",
    "shoulder_angle",
    "neck_lateral_tilt",
    "formula_neck_lateral",
    "formula_error",

    "shoulder_tilt",
    "shoulder_component_error",

    "landmark_dy_px",
    "shoulder_width_px",
    "normalized_dy",
)


def analyze_case(
    case,
    valid_rows,
):

    statistics_map = {}

    for metric in SUMMARY_METRICS:

        statistics_map[
            metric
        ] = summarize(
            [
                row.get(metric)
                for row
                in valid_rows
            ]
        )

    formula_abs_errors = []

    for row in valid_rows:

        error = finite_number(
            row.get(
                "formula_error"
            )
        )

        if error is not None:

            formula_abs_errors.append(
                abs(error)
            )

    max_abs_formula_error = (
        max(formula_abs_errors)
        if formula_abs_errors
        else None
    )

    return {
        "id": case["id"],
        "title": case["title"],

        "valid_frames": (
            len(valid_rows)
        ),

        "valid_enough": (
            len(valid_rows)
            >= MIN_VALID_FRAMES
        ),

        "statistics": (
            statistics_map
        ),

        "max_abs_formula_error": (
            max_abs_formula_error
        ),
    }


# ============================================================
# PRINT RESULT
# ============================================================

def print_case_result(
    result,
):

    print()
    print("-" * 110)

    print(
        result["title"]
    )

    print(
        "Valid Frames:",
        result["valid_frames"],
    )

    print(
        "Valid Enough:",
        result["valid_enough"],
    )

    print()

    for metric in SUMMARY_METRICS:

        stats = (
            result[
                "statistics"
            ][metric]
        )

        if stats["count"] == 0:

            print(
                f"{metric:<28} N/A"
            )

            continue

        print(
            f"{metric:<28} "
            f"median={stats['median']:+.6f} "
            f"p05={stats['p05']:+.6f} "
            f"p95={stats['p95']:+.6f}"
        )

    print()

    error = result[
        "max_abs_formula_error"
    ]

    if error is None:

        print(
            "Max Absolute Formula Error: N/A"
        )

    else:

        print(
            "Max Absolute Formula Error:",
            f"{error:.10f} deg",
        )

    print("-" * 110)


# ============================================================
# SAME-RUN NEUTRAL DELTA
# ============================================================

def build_neutral_comparison(
    results,
):

    by_id = {
        item["id"]: item
        for item in results
    }

    neutral = by_id.get(
        "neutral"
    )

    neck_left = by_id.get(
        "neck_left_natural"
    )

    if (
        neutral is None
        or
        neck_left is None
    ):
        return {}

    metrics = (
        "ear_angle",
        "shoulder_angle",
        "neck_lateral_tilt",
        "shoulder_tilt",
        "landmark_dy_px",
        "normalized_dy",
    )

    output = {
        "source_case": (
            "neutral"
        ),

        "target_case": (
            "neck_left_natural"
        ),
    }

    for metric in metrics:

        neutral_median = (
            neutral[
                "statistics"
            ][metric][
                "median"
            ]
        )

        neck_median = (
            neck_left[
                "statistics"
            ][metric][
                "median"
            ]
        )

        delta = None

        if (
            neutral_median is not None
            and
            neck_median is not None
        ):

            delta = (
                neck_median
                -
                neutral_median
            )

        output[
            f"neutral_{metric}"
        ] = neutral_median

        output[
            f"neck_left_{metric}"
        ] = neck_median

        output[
            f"delta_{metric}"
        ] = delta

    # --------------------------------------------------------
    # How much of ear-angle change is offset by shoulder-angle
    # change?
    #
    # This is descriptive only.
    # --------------------------------------------------------

    delta_ear = output.get(
        "delta_ear_angle"
    )

    delta_shoulder = output.get(
        "delta_shoulder_angle"
    )

    compensation_ratio = None

    if (
        delta_ear is not None
        and
        delta_shoulder is not None
        and
        abs(delta_ear) > 1e-9
    ):

        compensation_ratio = (
            delta_shoulder
            /
            delta_ear
        )

    output[
        "shoulder_to_ear_change_ratio"
    ] = (
        compensation_ratio
    )

    return output


# ============================================================
# PRINT COMPARISON
# ============================================================

def print_comparison(
    comparison,
):

    print()
    print("=" * 110)

    print(
        "NEUTRAL -> NECK LEFT NATURAL"
    )

    print("=" * 110)

    metrics = (
        "ear_angle",
        "shoulder_angle",
        "neck_lateral_tilt",
        "shoulder_tilt",
        "landmark_dy_px",
        "normalized_dy",
    )

    for metric in metrics:

        neutral = comparison.get(
            f"neutral_{metric}"
        )

        target = comparison.get(
            f"neck_left_{metric}"
        )

        delta = comparison.get(
            f"delta_{metric}"
        )

        print()

        print(metric)

        print(
            "  Neutral :",
            (
                f"{neutral:+.6f}"
                if neutral is not None
                else "N/A"
            ),
        )

        print(
            "  Neck L  :",
            (
                f"{target:+.6f}"
                if target is not None
                else "N/A"
            ),
        )

        print(
            "  Delta   :",
            (
                f"{delta:+.6f}"
                if delta is not None
                else "N/A"
            ),
        )

    ratio = comparison.get(
        "shoulder_to_ear_change_ratio"
    )

    print()
    print(
        "Shoulder/Ear Change Ratio:",
        (
            f"{ratio:+.4f}"
            if ratio is not None
            else "N/A"
        ),
    )

    print("=" * 110)


# ============================================================
# SAVE
# ============================================================

def save_results(
    *,
    all_rows,
    results,
    comparison,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    frames_csv = (
        OUTPUT_DIR
        /
        (
            "neck_lateral_raw_components_frames_"
            f"{timestamp}.csv"
        )
    )

    summary_json = (
        OUTPUT_DIR
        /
        (
            "neck_lateral_raw_components_summary_"
            f"{timestamp}.json"
        )
    )

    comparison_csv = (
        OUTPUT_DIR
        /
        (
            "neck_lateral_raw_components_comparison_"
            f"{timestamp}.csv"
        )
    )

    # ========================================================
    # FRAME CSV
    # ========================================================

    if all_rows:

        with frames_csv.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(
                    all_rows[0].keys()
                ),
            )

            writer.writeheader()

            writer.writerows(
                all_rows
            )

    # ========================================================
    # COMPARISON CSV
    # ========================================================

    if comparison:

        with comparison_csv.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(
                    comparison.keys()
                ),
            )

            writer.writeheader()

            writer.writerow(
                comparison
            )

    # ========================================================
    # SUMMARY JSON
    # ========================================================

    payload = {
        "runner_version": (
            RUNNER_VERSION
        ),

        "created_at": (
            datetime.now()
            .isoformat()
        ),

        "capture_seconds": (
            CAPTURE_SECONDS
        ),

        "min_valid_frames": (
            MIN_VALID_FRAMES
        ),

        "purpose": (
            "Verify per-frame neck lateral raw components "
            "and compare Neutral vs Neck Tilt Left Natural."
        ),

        "results": results,

        "neutral_to_neck_left_comparison": (
            comparison
        ),

        "notes": {
            "production_code_changed": False,
            "assessment_changed": False,
            "threshold_changed": False,
            "risk_used": False,
            "database_used": False,

            "causal_claim": False,

            "interpretation": (
                "This diagnostic verifies component geometry "
                "and relative-angle behavior only. "
                "It does not prove physical causation."
            ),
        },
    }

    with summary_json.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return (
        frames_csv,
        summary_json,
        comparison_csv,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 110)

    print(
        "POSTGUARD - NECK LATERAL RAW COMPONENT DIAGNOSTIC"
    )

    print("=" * 110)

    print(
        "Runner:",
        RUNNER_VERSION,
    )

    print(
        "Tests:"
    )

    print(
        "1. Neutral"
    )

    print(
        "2. Neck Tilt Left - Natural"
    )

    print()

    print(
        "This test does NOT modify production code."
    )

    print(
        "It reads ear_angle and shoulder_angle "
        "already produced by DetectionPipeline."
    )

    print("=" * 110)

    camera = cv2.VideoCapture(
        CAMERA_ID
    )

    if not camera.isOpened():

        raise RuntimeError(
            "Cannot open camera."
        )

    camera.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        FRAME_WIDTH,
    )

    camera.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        FRAME_HEIGHT,
    )

    pipeline = None

    all_rows = []
    results = []

    try:

        pipeline = DetectionPipeline()

        pipeline.reset_runtime()

        cv2.namedWindow(
            WINDOW_NAME,
            cv2.WINDOW_NORMAL,
        )

        cv2.resizeWindow(
            WINDOW_NAME,
            FRAME_WIDTH,
            FRAME_HEIGHT,
        )

        for (
            index,
            case,
        ) in enumerate(
            TEST_CASES,
            start=1,
        ):

            print()
            print(
                f"TEST {index}/"
                f"{len(TEST_CASES)}"
            )

            (
                case_rows,
                valid_rows,
            ) = capture_case(
                camera,
                pipeline,
                case,
            )

            all_rows.extend(
                case_rows
            )

            result = analyze_case(
                case,
                valid_rows,
            )

            results.append(
                result
            )

            print_case_result(
                result
            )

        comparison = (
            build_neutral_comparison(
                results
            )
        )

        print_comparison(
            comparison
        )

        (
            frames_csv,
            summary_json,
            comparison_csv,
        ) = save_results(
            all_rows=all_rows,
            results=results,
            comparison=comparison,
        )

        print()
        print("=" * 110)

        print(
            "RAW COMPONENT DIAGNOSTIC COMPLETE"
        )

        print("=" * 110)

        print(
            "Frames CSV     :",
            frames_csv,
        )

        print(
            "Summary JSON   :",
            summary_json,
        )

        print(
            "Comparison CSV :",
            comparison_csv,
        )

        print()

        print(
            "IMPORTANT:"
        )

        print(
            "- Formula is checked per frame"
        )

        print(
            "- No Assessment threshold is changed"
        )

        print(
            "- No causal conclusion is made"
        )

        print("=" * 110)

    except KeyboardInterrupt:

        print()
        print(
            "Diagnostic interrupted."
        )

    finally:

        if pipeline is not None:
            pipeline.close()

        camera.release()

        cv2.destroyAllWindows()

        print()
        print("=" * 95)

        print(
            "RAW COMPONENT DIAGNOSTIC CLOSED"
        )

        print(
            "DetectionPipeline : CLOSED"
        )

        print(
            "Camera            : RELEASED"
        )

        print(
            "Production Code   : NOT CHANGED"
        )

        print("=" * 95)


if __name__ == "__main__":
    main()