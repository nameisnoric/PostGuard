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

# backend/
BACKEND_DIR = TEST_FILE.parents[3]

# backend/camera_card/
CAMERA_CARD_DIR = TEST_FILE.parents[2]

for path in (
    BACKEND_DIR,
    CAMERA_CARD_DIR,
):
    path_str = str(path)

    if path_str not in sys.path:
        sys.path.insert(
            0,
            path_str,
        )


from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)


# ============================================================
# RUNNER INFO
# ============================================================

RUNNER_VERSION = (
    "1.0-shoulder-neck-left-crosstalk-diagnostic"
)


# ============================================================
# CAMERA CONFIG
# ============================================================

CAMERA_ID = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

CAPTURE_SECONDS = 5.0

MIN_VALID_FRAMES = 30


# ============================================================
# WINDOW
# ============================================================

WINDOW_NAME = (
    "PostGuard - Neck Left Cross-talk Diagnostic"
)


# ============================================================
# OUTPUT
# ============================================================

OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "shoulder_neck_left_crosstalk"
)


# ============================================================
# TEST CASES
# ============================================================

TEST_CASES = [
    {
        "id": "neutral",
        "title": "Neutral",
        "instruction": (
            "Sit naturally. Relax shoulders. "
            "Keep head straight and look forward."
        ),
    },

    {
        "id": "neck_left_natural",
        "title": "Neck Tilt Left - Natural",
        "instruction": (
            "Tilt HEAD LEFT naturally. "
            "Do not intentionally move shoulders. HOLD."
        ),
    },

    {
        "id": "neck_left_shoulders_level",
        "title": "Neck Tilt Left - Keep Shoulders Level",
        "instruction": (
            "Tilt HEAD LEFT. "
            "Try to keep both shoulders level and still. HOLD."
        ),
    },

    {
        "id": "right_shoulder_high",
        "title": "Right Shoulder High - Head Straight",
        "instruction": (
            "Keep HEAD STRAIGHT. "
            "Raise RIGHT shoulder clearly. HOLD."
        ),
    },
]


# ============================================================
# COLORS
# ============================================================

WHITE = (
    255,
    255,
    255,
)

GREEN = (
    0,
    220,
    0,
)

RED = (
    0,
    0,
    255,
)

YELLOW = (
    0,
    255,
    255,
)

CYAN = (
    255,
    255,
    0,
)

BLACK = (
    0,
    0,
    0,
)


# ============================================================
# GENERIC NUMBER HELPERS
# ============================================================

def finite_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        value = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        value
    ):
        return None

    return value


# ============================================================
# PERCENTILE
# ============================================================

def percentile(
    values: list[float],
    fraction: float,
) -> float | None:

    if not values:
        return None

    ordered = sorted(
        values
    )

    if len(
        ordered
    ) == 1:
        return float(
            ordered[
                0
            ]
        )

    position = (
        (
            len(
                ordered
            )
            - 1
        )
        *
        fraction
    )

    lower = int(
        math.floor(
            position
        )
    )

    upper = int(
        math.ceil(
            position
        )
    )

    if lower == upper:
        return float(
            ordered[
                lower
            ]
        )

    weight = (
        position
        -
        lower
    )

    return float(
        ordered[
            lower
        ]
        *
        (
            1.0
            -
            weight
        )
        +
        ordered[
            upper
        ]
        *
        weight
    )


# ============================================================
# SUMMARY STATISTICS
# ============================================================

def summarize(
    values,
) -> dict[str, Any]:

    clean = []

    for value in values:

        number = finite_number(
            value
        )

        if number is not None:

            clean.append(
                number
            )

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
        "count": len(
            clean
        ),

        "mean": float(
            statistics.mean(
                clean
            )
        ),

        "median": float(
            statistics.median(
                clean
            )
        ),

        "sd": (
            float(
                statistics.stdev(
                    clean
                )
            )
            if len(
                clean
            ) >= 2
            else 0.0
        ),

        "min": float(
            min(
                clean
            )
        ),

        "max": float(
            max(
                clean
            )
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
# DISPLAY HELPERS
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
        str(
            text
        ),
        (
            int(
                x
            ),
            int(
                y
            ),
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


# ============================================================
# CONTRACT ACCESS
# ============================================================

def get_pose_points(
    result,
) -> dict:

    landmarks = (
        result.get(
            "landmarks"
        )
        or {}
    )

    points = landmarks.get(
        "pose"
    )

    if not isinstance(
        points,
        dict,
    ):
        return {}

    return points


def get_feature_value(
    result,
    feature_name,
) -> float | None:

    features = (
        result.get(
            "features"
        )
        or {}
    )

    feature = features.get(
        feature_name
    )

    if not isinstance(
        feature,
        dict,
    ):
        return None

    if feature.get(
        "valid"
    ) is not True:

        return None

    return finite_number(
        feature.get(
            "value"
        )
    )


# ============================================================
# CONTEXT
# ============================================================

def get_context_state(
    result,
) -> str:

    context = (
        result.get(
            "context"
        )
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
        result.get(
            "context"
        )
        or {}
    )

    return (
        context.get(
            "state"
        )
        ==
        "VALID"
        and
        context.get(
            "allow_posture_evaluation"
        )
        is True
    )


# ============================================================
# LANDMARK ACCESS
# ============================================================

def get_landmark_number(
    point,
    key,
) -> float | None:

    if not isinstance(
        point,
        dict,
    ):
        return None

    return finite_number(
        point.get(
            key
        )
    )


# ============================================================
# SHOULDER GEOMETRY
# ============================================================

def calculate_shoulder_geometry(
    left_shoulder,
    right_shoulder,
) -> dict[str, Any]:

    left_x = get_landmark_number(
        left_shoulder,
        "x",
    )

    left_y = get_landmark_number(
        left_shoulder,
        "y",
    )

    right_x = get_landmark_number(
        right_shoulder,
        "x",
    )

    right_y = get_landmark_number(
        right_shoulder,
        "y",
    )

    if (
        left_x is None
        or left_y is None
        or right_x is None
        or right_y is None
    ):

        return {
            "left_shoulder_x": (
                left_x
            ),

            "left_shoulder_y": (
                left_y
            ),

            "right_shoulder_x": (
                right_x
            ),

            "right_shoulder_y": (
                right_y
            ),

            "landmark_dx_px": None,
            "landmark_dy_px": None,
            "shoulder_width_px": None,
            "normalized_dy": None,
            "image_line_angle_deg": None,
        }

    # --------------------------------------------------------
    # IMPORTANT
    #
    # Keep landmark order exactly as returned by PostGuard.
    #
    # dx = right - left
    # dy = right - left
    #
    # We do NOT swap them for display orientation.
    # --------------------------------------------------------

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

    shoulder_width = abs(
        dx
    )

    normalized_dy = None

    if shoulder_width > 0:

        normalized_dy = (
            dy
            /
            shoulder_width
        )

    image_angle = None

    if not (
        dx == 0
        and dy == 0
    ):

        image_angle = math.degrees(
            math.atan2(
                dy,
                dx,
            )
        )

    return {
        "left_shoulder_x": (
            left_x
        ),

        "left_shoulder_y": (
            left_y
        ),

        "right_shoulder_x": (
            right_x
        ),

        "right_shoulder_y": (
            right_y
        ),

        "landmark_dx_px": (
            dx
        ),

        "landmark_dy_px": (
            dy
        ),

        "shoulder_width_px": (
            shoulder_width
        ),

        "normalized_dy": (
            normalized_dy
        ),

        # Diagnostic raw line angle.
        #
        # Because MediaPipe image X orientation and landmark
        # ordering can place this near ±180°, do NOT interpret
        # this directly as anatomical shoulder angle.
        #
        # Production shoulder_tilt remains the authoritative
        # PostGuard metric for this diagnostic.
        "image_line_angle_deg": (
            image_angle
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

    pose = get_pose_points(
        result
    )

    left_shoulder = (
        pose.get(
            "left_shoulder"
        )
    )

    right_shoulder = (
        pose.get(
            "right_shoulder"
        )
    )

    geometry = (
        calculate_shoulder_geometry(
            left_shoulder,
            right_shoulder,
        )
    )

    row = {
        "case_id": (
            case[
                "id"
            ]
        ),

        "case_title": (
            case[
                "title"
            ]
        ),

        "frame_index": (
            frame_index
        ),

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

        "shoulder_tilt": (
            get_feature_value(
                result,
                "shoulder_tilt",
            )
        ),

        "neck_lateral_tilt": (
            get_feature_value(
                result,
                "neck_lateral_tilt",
            )
        ),

        "neck_flexion": (
            get_feature_value(
                result,
                "neck_flexion",
            )
        ),
    }

    row.update(
        geometry
    )

    return row


# ============================================================
# FRAME VALIDITY
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
        "shoulder_tilt",
        "neck_lateral_tilt",
        "landmark_dx_px",
        "landmark_dy_px",
        "normalized_dy",
    )

    for key in required:

        if finite_number(
            row.get(
                key
            )
        ) is None:

            return False

    return True


# ============================================================
# DRAW LIVE DISPLAY
# ============================================================

def draw_live_display(
    frame,
    result,
    case,
    *,
    capturing,
    elapsed=0.0,
):

    # --------------------------------------------------------
    # Mirror for USER DISPLAY ONLY.
    #
    # DetectionPipeline already processed the unmirrored frame.
    # --------------------------------------------------------

    display = cv2.flip(
        frame,
        1,
    )

    overlay = display.copy()

    cv2.rectangle(
        overlay,
        (
            0,
            0,
        ),
        (
            min(
                display.shape[
                    1
                ],
                1000,
            ),
            min(
                display.shape[
                    0
                ],
                430,
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

    shoulder = get_feature_value(
        result,
        "shoulder_tilt",
    )

    neck = get_feature_value(
        result,
        "neck_lateral_tilt",
    )

    flexion = get_feature_value(
        result,
        "neck_flexion",
    )

    pose = get_pose_points(
        result
    )

    geometry = calculate_shoulder_geometry(
        pose.get(
            "left_shoulder"
        ),
        pose.get(
            "right_shoulder"
        ),
    )

    y = 35

    draw_text(
        display,
        (
            "POSTGUARD - "
            "NECK LEFT CROSS-TALK DIAGNOSTIC"
        ),
        20,
        y,
        WHITE,
        0.62,
        2,
    )

    y += 40

    draw_text(
        display,
        case[
            "title"
        ],
        20,
        y,
        YELLOW,
        0.60,
        2,
    )

    y += 30

    draw_text(
        display,
        case[
            "instruction"
        ],
        20,
        y,
        WHITE,
        0.45,
        1,
    )

    y += 42

    draw_text(
        display,
        (
            "Context: "
            f"{get_context_state(result)}"
        ),
        20,
        y,
        GREEN
        if context_allows_evaluation(
            result
        )
        else RED,
        0.52,
        2,
    )

    y += 32

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

    draw_text(
        display,
        (
            "Shoulder Tilt: "
            f"{fmt(shoulder)} deg"
        ),
        20,
        y,
        CYAN,
        0.55,
        2,
    )

    y += 32

    draw_text(
        display,
        (
            "Neck Lateral: "
            f"{fmt(neck)} deg"
        ),
        20,
        y,
        WHITE,
        0.52,
        1,
    )

    y += 32

    draw_text(
        display,
        (
            "Neck Flexion: "
            f"{fmt(flexion)} deg"
        ),
        20,
        y,
        WHITE,
        0.52,
        1,
    )

    y += 32

    draw_text(
        display,
        (
            "Shoulder dY: "
            f"{fmt(geometry['landmark_dy_px'], 2)} px"
        ),
        20,
        y,
        WHITE,
        0.52,
        1,
    )

    y += 32

    draw_text(
        display,
        (
            "Normalized dY: "
            f"{fmt(geometry['normalized_dy'], 4)}"
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
# CAPTURE CASE
# ============================================================

def capture_case(
    camera,
    pipeline,
    case,
):

    print()
    print(
        "=" * 110
    )

    print(
        case[
            "title"
        ]
    )

    print(
        case[
            "instruction"
        ]
    )

    print()

    print(
        "Prepare posture naturally."
    )

    print(
        "Press S to capture."
    )

    print(
        "=" * 110
    )

    # ========================================================
    # WAIT FOR USER
    # ========================================================

    while True:

        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        now = (
            time.perf_counter()
        )

        result = (
            pipeline.process_frame(
                frame,
                timestamp=now,
            )
        )

        display = (
            draw_live_display(
                frame,
                result,
                case,
                capturing=False,
            )
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
            ord(
                "q"
            ),
            ord(
                "Q"
            ),
            27,
        ):
            raise KeyboardInterrupt

        if key in (
            ord(
                "s"
            ),
            ord(
                "S"
            ),
        ):
            break

    # ========================================================
    # CAPTURE
    # ========================================================

    start = (
        time.perf_counter()
    )

    frame_index = 0

    all_rows = []

    valid_rows = []

    while True:

        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        frame_index += 1

        now = (
            time.perf_counter()
        )

        elapsed = (
            now
            -
            start
        )

        result = (
            pipeline.process_frame(
                frame,
                timestamp=now,
            )
        )

        row = build_frame_row(
            case=case,
            frame_index=frame_index,
            elapsed=elapsed,
            result=result,
        )

        all_rows.append(
            row
        )

        if row_is_valid(
            row
        ):

            valid_rows.append(
                row
            )

        display = (
            draw_live_display(
                frame,
                result,
                case,
                capturing=True,
                elapsed=elapsed,
            )
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
            ord(
                "q"
            ),
            ord(
                "Q"
            ),
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
# ANALYZE CASE
# ============================================================

def analyze_case(
    case,
    valid_rows,
):

    metrics = (
        "shoulder_tilt",
        "neck_lateral_tilt",
        "neck_flexion",

        "left_shoulder_x",
        "left_shoulder_y",

        "right_shoulder_x",
        "right_shoulder_y",

        "landmark_dx_px",
        "landmark_dy_px",

        "shoulder_width_px",
        "normalized_dy",

        "image_line_angle_deg",
    )

    statistics_map = {}

    for metric in metrics:

        statistics_map[
            metric
        ] = summarize(
            [
                row.get(
                    metric
                )
                for row
                in valid_rows
            ]
        )

    return {
        "id": (
            case[
                "id"
            ]
        ),

        "title": (
            case[
                "title"
            ]
        ),

        "frames": (
            len(
                valid_rows
            )
        ),

        "valid_enough": (
            len(
                valid_rows
            )
            >=
            MIN_VALID_FRAMES
        ),

        "statistics": (
            statistics_map
        ),
    }


# ============================================================
# PRINT CASE RESULT
# ============================================================

def print_case_result(
    result,
):

    print()
    print(
        "-" * 110
    )

    print(
        result[
            "title"
        ]
    )

    print(
        "Valid Frames:",
        result[
            "frames"
        ],
    )

    print(
        "Valid Enough:",
        result[
            "valid_enough"
        ],
    )

    print()

    metrics = (
        "shoulder_tilt",
        "neck_lateral_tilt",
        "neck_flexion",

        "landmark_dy_px",
        "shoulder_width_px",
        "normalized_dy",

        "image_line_angle_deg",
    )

    for metric in metrics:

        stats = (
            result[
                "statistics"
            ][
                metric
            ]
        )

        if stats[
            "count"
        ] == 0:

            print(
                f"{metric:<26} N/A"
            )

            continue

        print(
            f"{metric:<26} "
            f"median={stats['median']:+.4f} "
            f"p05={stats['p05']:+.4f} "
            f"p95={stats['p95']:+.4f} "
            f"min={stats['min']:+.4f} "
            f"max={stats['max']:+.4f}"
        )

    print(
        "-" * 110
    )


# ============================================================
# SAME-RUN NEUTRAL DELTA
# ============================================================

def calculate_same_run_comparison(
    results,
):

    by_id = {
        result[
            "id"
        ]:
        result
        for result
        in results
    }

    neutral = by_id.get(
        "neutral"
    )

    if neutral is None:
        return []

    metrics = (
        "shoulder_tilt",
        "landmark_dy_px",
        "normalized_dy",
    )

    comparisons = []

    for case_id in (
        "neck_left_natural",
        "neck_left_shoulders_level",
        "right_shoulder_high",
    ):

        current = by_id.get(
            case_id
        )

        if current is None:
            continue

        row = {
            "case_id": (
                case_id
            ),

            "case_title": (
                current[
                    "title"
                ]
            ),
        }

        for metric in metrics:

            neutral_median = (
                neutral[
                    "statistics"
                ][
                    metric
                ][
                    "median"
                ]
            )

            current_median = (
                current[
                    "statistics"
                ][
                    metric
                ][
                    "median"
                ]
            )

            delta = None

            if (
                neutral_median
                is not None
                and
                current_median
                is not None
            ):

                delta = (
                    current_median
                    -
                    neutral_median
                )

            row[
                f"neutral_{metric}"
            ] = (
                neutral_median
            )

            row[
                f"current_{metric}"
            ] = (
                current_median
            )

            row[
                f"delta_{metric}"
            ] = (
                delta
            )

        comparisons.append(
            row
        )

    return comparisons


# ============================================================
# PRINT SAME-RUN COMPARISON
# ============================================================

def print_comparisons(
    comparisons,
):

    print()
    print(
        "=" * 110
    )

    print(
        "SAME-RUN NEUTRAL-NORMALIZED COMPARISON"
    )

    print(
        "=" * 110
    )

    for comparison in comparisons:

        print()

        print(
            comparison[
                "case_title"
            ]
        )

        print(
            (
                "Delta Shoulder Tilt : "
                f"{comparison['delta_shoulder_tilt']:+.4f}"
            )
            if comparison[
                "delta_shoulder_tilt"
            ]
            is not None
            else
            "Delta Shoulder Tilt : N/A"
        )

        print(
            (
                "Delta Landmark dY   : "
                f"{comparison['delta_landmark_dy_px']:+.4f}"
            )
            if comparison[
                "delta_landmark_dy_px"
            ]
            is not None
            else
            "Delta Landmark dY   : N/A"
        )

        print(
            (
                "Delta Normalized dY : "
                f"{comparison['delta_normalized_dy']:+.6f}"
            )
            if comparison[
                "delta_normalized_dy"
            ]
            is not None
            else
            "Delta Normalized dY : N/A"
        )

    print(
        "=" * 110
    )


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(
    *,
    all_rows,
    case_results,
    comparisons,
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

    frame_csv = (
        OUTPUT_DIR
        /
        (
            "shoulder_neck_left_crosstalk_frames_"
            f"{timestamp}.csv"
        )
    )

    summary_json = (
        OUTPUT_DIR
        /
        (
            "shoulder_neck_left_crosstalk_summary_"
            f"{timestamp}.json"
        )
    )

    comparison_csv = (
        OUTPUT_DIR
        /
        (
            "shoulder_neck_left_crosstalk_comparison_"
            f"{timestamp}.csv"
        )
    )

    # ========================================================
    # FRAME CSV
    # ========================================================

    if all_rows:

        with frame_csv.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(
                    all_rows[
                        0
                    ].keys()
                ),
            )

            writer.writeheader()

            writer.writerows(
                all_rows
            )

    # ========================================================
    # COMPARISON CSV
    # ========================================================

    if comparisons:

        with comparison_csv.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(
                    comparisons[
                        0
                    ].keys()
                ),
            )

            writer.writeheader()

            writer.writerows(
                comparisons
            )

    # ========================================================
    # JSON
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

        "results": (
            case_results
        ),

        "same_run_neutral_comparison": (
            comparisons
        ),

        "notes": {
            "purpose": (
                "Diagnostic Neck Tilt Left and "
                "shoulder geometry interaction"
            ),

            "production_code_changed": False,

            "assessment_changed": False,

            "threshold_changed": False,

            "measurement_change_gate_changed": False,

            "risk_used": False,

            "database_used": False,

            "causal_claim": False,
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
        frame_csv,
        summary_json,
        comparison_csv,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=" * 110
    )

    print(
        "POSTGUARD - NECK LEFT / SHOULDER CROSS-TALK DIAGNOSTIC"
    )

    print(
        "=" * 110
    )

    print(
        "Runner Version :",
        RUNNER_VERSION,
    )

    print(
        "Capture Seconds:",
        CAPTURE_SECONDS,
    )

    print(
        "Min Valid Frames:",
        MIN_VALID_FRAMES,
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "- Diagnostic only"
    )

    print(
        "- Do NOT intentionally make values pass"
    )

    print(
        "- No DetectionPipeline changes"
    )

    print(
        "- No Assessment changes"
    )

    print(
        "- No Threshold changes"
    )

    print(
        "- No Measurement-Change Gate changes"
    )

    print(
        "=" * 110
    )

    # ========================================================
    # CAMERA
    # ========================================================

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

    case_results = []

    try:

        # ====================================================
        # PIPELINE
        # ====================================================

        pipeline = (
            DetectionPipeline()
        )

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

        # ====================================================
        # TEST CASES
        # ====================================================

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
                raw_rows,
                valid_rows,
            ) = capture_case(
                camera,
                pipeline,
                case,
            )

            all_rows.extend(
                raw_rows
            )

            result = (
                analyze_case(
                    case,
                    valid_rows,
                )
            )

            case_results.append(
                result
            )

            print_case_result(
                result
            )

        # ====================================================
        # SAME-RUN DELTA
        # ====================================================

        comparisons = (
            calculate_same_run_comparison(
                case_results
            )
        )

        print_comparisons(
            comparisons
        )

        # ====================================================
        # SAVE
        # ====================================================

        (
            frame_csv,
            summary_json,
            comparison_csv,
        ) = save_results(
            all_rows=all_rows,
            case_results=case_results,
            comparisons=comparisons,
        )

        print()
        print(
            "=" * 110
        )

        print(
            "NECK LEFT CROSS-TALK DIAGNOSTIC COMPLETE"
        )

        print(
            "=" * 110
        )

        print(
            "Frame CSV     :",
            frame_csv,
        )

        print(
            "Summary JSON  :",
            summary_json,
        )

        print(
            "Comparison CSV:",
            comparison_csv,
        )

        print()

        print(
            "IMPORTANT:"
        )

        print(
            "This diagnostic does NOT prove whether "
            "the cause is body movement, biomechanics, "
            "projection, or pose-estimation interaction."
        )

        print()

        print(
            "It only measures whether Neck Tilt Left "
            "is associated with a repeatable shoulder "
            "geometry shift in PostGuard data."
        )

        print(
            "=" * 110
        )

        print()
        print(
            "Press Q / ESC to exit."
        )

        # ====================================================
        # END SCREEN
        # ====================================================

        while True:

            ok, frame = (
                camera.read()
            )

            if not ok:
                continue

            display = cv2.flip(
                frame,
                1,
            )

            draw_text(
                display,
                "DIAGNOSTIC COMPLETE",
                30,
                50,
                GREEN,
                0.70,
                2,
            )

            draw_text(
                display,
                "Q / ESC = Exit",
                30,
                95,
                CYAN,
                0.60,
                2,
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
                ord(
                    "q"
                ),
                ord(
                    "Q"
                ),
                27,
            ):
                break

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
        print(
            "=" * 95
        )

        print(
            "NECK LEFT CROSS-TALK DIAGNOSTIC CLOSED"
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

        print(
            "Database          : NOT USED"
        )

        print(
            "=" * 95
        )


if __name__ == "__main__":

    main()