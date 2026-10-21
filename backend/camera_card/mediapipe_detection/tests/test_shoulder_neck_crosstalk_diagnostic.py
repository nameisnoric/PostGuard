from __future__ import annotations

import csv
import json
import math
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2


from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)


# ============================================================
# CONFIG
# ============================================================

RUNNER_VERSION = (
    "1.0-shoulder-neck-crosstalk-diagnostic"
)

WINDOW_NAME = (
    "PostGuard - Shoulder Neck Cross-talk Diagnostic"
)

CAMERA_INDEX = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

CAPTURE_SECONDS = 5.0

MIN_VALID_FRAMES = 30


# ============================================================
# RESULT PATH
# ============================================================

RESULTS_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "shoulder_neck_crosstalk"
)


# ============================================================
# TEST CASES
#
# สำคัญ:
# เราไม่ได้พยายามให้ Assessment ผ่าน
# เราต้องการดู LANDMARK + FEATURE จริง
# ============================================================

TEST_CASES = (
    {
        "id": "neutral",
        "title": "Neutral",
        "instruction": (
            "Sit naturally. Keep head straight. "
            "Relax both shoulders."
        ),
    },

    {
        "id": "neck_right_natural",
        "title": "Neck Tilt Right - Natural",
        "instruction": (
            "Tilt HEAD RIGHT naturally. "
            "Do not intentionally move your shoulders."
        ),
    },

    {
        "id": "neck_right_shoulders_level",
        "title": "Neck Tilt Right - Keep Shoulders Level",
        "instruction": (
            "Tilt HEAD RIGHT naturally while consciously "
            "keeping both shoulders LEVEL and still."
        ),
    },

    {
        "id": "left_shoulder_high",
        "title": "Left Shoulder High - Head Straight",
        "instruction": (
            "Keep HEAD STRAIGHT. Raise LEFT shoulder clearly. "
            "Do not tilt your head."
        ),
    },
)


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
# HELPERS
# ============================================================

def finite(
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


def put(
    frame,
    text,
    x,
    y,
    color=WHITE,
    scale=0.50,
    thickness=1,
):

    cv2.putText(
        frame,
        str(text),
        (
            int(x),
            int(y),
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def get_feature_value(
    detection_result,
    feature_name,
):

    features = (
        detection_result.get(
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

    return finite(
        feature.get(
            "value"
        )
    )


def get_pose_landmark(
    detection_result,
    name,
):

    landmarks = (
        detection_result.get(
            "landmarks"
        )
        or {}
    )

    pose = landmarks.get(
        "pose"
    )

    if not isinstance(
        pose,
        dict,
    ):
        return None

    point = pose.get(
        name
    )

    if not isinstance(
        point,
        dict,
    ):
        return None

    x = finite(
        point.get(
            "x"
        )
    )

    y = finite(
        point.get(
            "y"
        )
    )

    if (
        x is None
        or
        y is None
    ):
        return None

    return {
        "x": x,
        "y": y,
    }


# ============================================================
# LANDMARK GEOMETRY
#
# ค่านี้เป็น diagnostic เท่านั้น
#
# image_line_angle:
# atan2(dy, dx) จาก landmark pixel coordinate
#
# ไม่ใช้แทน production shoulder_tilt
# ============================================================

def calculate_landmark_geometry(
    left_shoulder,
    right_shoulder,
):

    if (
        left_shoulder is None
        or
        right_shoulder is None
    ):
        return {
            "dx_px": None,
            "dy_px": None,
            "shoulder_width_px": None,
            "normalized_dy": None,
            "image_line_angle_deg": None,
        }

    dx = (
        right_shoulder[
            "x"
        ]
        -
        left_shoulder[
            "x"
        ]
    )

    dy = (
        right_shoulder[
            "y"
        ]
        -
        left_shoulder[
            "y"
        ]
    )

    width = abs(
        dx
    )

    if width > 1e-6:
        normalized_dy = (
            dy
            /
            width
        )
    else:
        normalized_dy = None

    angle = math.degrees(
        math.atan2(
            dy,
            dx,
        )
    )

    return {
        "dx_px": dx,
        "dy_px": dy,
        "shoulder_width_px": width,
        "normalized_dy": normalized_dy,
        "image_line_angle_deg": angle,
    }


# ============================================================
# STATISTICS
# ============================================================

def stats(
    values,
):

    clean = [
        float(value)
        for value in values
        if finite(value)
        is not None
    ]

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

    def percentile(
        fraction,
    ):

        if len(clean) == 1:
            return clean[0]

        position = (
            (
                len(clean)
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
            return clean[
                lower
            ]

        weight = (
            position
            -
            lower
        )

        return (
            clean[lower]
            *
            (
                1.0
                -
                weight
            )
            +
            clean[upper]
            *
            weight
        )

    return {
        "count": len(clean),

        "mean": statistics.mean(
            clean
        ),

        "median": statistics.median(
            clean
        ),

        "sd": (
            statistics.stdev(
                clean
            )
            if len(clean) >= 2
            else 0.0
        ),

        "min": min(
            clean
        ),

        "max": max(
            clean
        ),

        "p05": percentile(
            0.05
        ),

        "p25": percentile(
            0.25
        ),

        "p75": percentile(
            0.75
        ),

        "p95": percentile(
            0.95
        ),
    }


# ============================================================
# DRAW LANDMARKS
# ============================================================

def draw_shoulder_landmarks(
    display,
    left_shoulder,
    right_shoulder,
):

    # ภาพถูก flip แล้ว
    # จึงต้อง flip x ของ landmark ด้วยตอนวาด
    frame_width = (
        display.shape[
            1
        ]
    )

    def mirrored_point(
        point,
    ):

        if point is None:
            return None

        x = int(
            round(
                frame_width
                -
                point[
                    "x"
                ]
            )
        )

        y = int(
            round(
                point[
                    "y"
                ]
            )
        )

        return (
            x,
            y,
        )

    left_point = (
        mirrored_point(
            left_shoulder
        )
    )

    right_point = (
        mirrored_point(
            right_shoulder
        )
    )

    if left_point is not None:

        cv2.circle(
            display,
            left_point,
            8,
            GREEN,
            -1,
        )

        put(
            display,
            "L",
            left_point[0] + 10,
            left_point[1],
            GREEN,
            0.6,
            2,
        )

    if right_point is not None:

        cv2.circle(
            display,
            right_point,
            8,
            RED,
            -1,
        )

        put(
            display,
            "R",
            right_point[0] + 10,
            right_point[1],
            RED,
            0.6,
            2,
        )

    if (
        left_point is not None
        and
        right_point is not None
    ):

        cv2.line(
            display,
            left_point,
            right_point,
            CYAN,
            3,
        )


# ============================================================
# DISPLAY
# ============================================================

def draw_display(
    frame,
    detection,
    test_case,
    *,
    mode,
    elapsed=0.0,
):

    display = cv2.flip(
        frame,
        1,
    )

    left_shoulder = (
        get_pose_landmark(
            detection,
            "left_shoulder",
        )
    )

    right_shoulder = (
        get_pose_landmark(
            detection,
            "right_shoulder",
        )
    )

    geometry = (
        calculate_landmark_geometry(
            left_shoulder,
            right_shoulder,
        )
    )

    shoulder_tilt = (
        get_feature_value(
            detection,
            "shoulder_tilt",
        )
    )

    neck_lateral = (
        get_feature_value(
            detection,
            "neck_lateral_tilt",
        )
    )

    draw_shoulder_landmarks(
        display,
        left_shoulder,
        right_shoulder,
    )

    overlay = (
        display.copy()
    )

    cv2.rectangle(
        overlay,
        (0, 0),
        (
            min(
                850,
                display.shape[1],
            ),
            min(
                430,
                display.shape[0],
            ),
        ),
        BLACK,
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.70,
        display,
        0.30,
        0,
        display,
    )

    y = 35

    put(
        display,
        "POSTGUARD - SHOULDER/NECK CROSS-TALK",
        20,
        y,
        WHITE,
        0.63,
        2,
    )

    y += 38

    put(
        display,
        test_case[
            "title"
        ],
        20,
        y,
        YELLOW,
        0.58,
        2,
    )

    y += 30

    put(
        display,
        test_case[
            "instruction"
        ],
        20,
        y,
        WHITE,
        0.42,
    )

    y += 40

    context = (
        detection.get(
            "context",
            {}
        )
    )

    put(
        display,
        (
            f"Context: "
            f"{context.get('state')} | "
            f"Allow: "
            f"{context.get('allow_posture_evaluation')}"
        ),
        20,
        y,
    )

    y += 34

    put(
        display,
        (
            "Production Shoulder Tilt : "
            +
            (
                f"{shoulder_tilt:+.3f} deg"
                if shoulder_tilt
                is not None
                else "N/A"
            )
        ),
        20,
        y,
        CYAN,
        0.53,
        2,
    )

    y += 31

    put(
        display,
        (
            "Neck Lateral Tilt        : "
            +
            (
                f"{neck_lateral:+.3f} deg"
                if neck_lateral
                is not None
                else "N/A"
            )
        ),
        20,
        y,
    )

    y += 31

    put(
        display,
        (
            "Landmark dy              : "
            +
            (
                f"{geometry['dy_px']:+.2f} px"
                if geometry[
                    "dy_px"
                ]
                is not None
                else "N/A"
            )
        ),
        20,
        y,
    )

    y += 31

    put(
        display,
        (
            "Shoulder Width           : "
            +
            (
                f"{geometry['shoulder_width_px']:.2f} px"
                if geometry[
                    "shoulder_width_px"
                ]
                is not None
                else "N/A"
            )
        ),
        20,
        y,
    )

    y += 31

    put(
        display,
        (
            "Normalized dy            : "
            +
            (
                f"{geometry['normalized_dy']:+.5f}"
                if geometry[
                    "normalized_dy"
                ]
                is not None
                else "N/A"
            )
        ),
        20,
        y,
    )

    y += 31

    put(
        display,
        (
            "Image Line Angle         : "
            +
            (
                f"{geometry['image_line_angle_deg']:+.3f} deg"
                if geometry[
                    "image_line_angle_deg"
                ]
                is not None
                else "N/A"
            )
        ),
        20,
        y,
    )

    y += 38

    if mode == "WAIT":

        put(
            display,
            "Prepare posture, then press S",
            20,
            y,
            CYAN,
            0.55,
            2,
        )

    else:

        put(
            display,
            (
                f"CAPTURING "
                f"{elapsed:.1f} / "
                f"{CAPTURE_SECONDS:.1f} sec"
            ),
            20,
            y,
            CYAN,
            0.55,
            2,
        )

    return display


# ============================================================
# BUILD ROW
# ============================================================

def build_row(
    *,
    test_case,
    frame_index,
    elapsed,
    detection,
):

    left_shoulder = (
        get_pose_landmark(
            detection,
            "left_shoulder",
        )
    )

    right_shoulder = (
        get_pose_landmark(
            detection,
            "right_shoulder",
        )
    )

    geometry = (
        calculate_landmark_geometry(
            left_shoulder,
            right_shoulder,
        )
    )

    context = (
        detection.get(
            "context",
            {}
        )
    )

    return {
        "case_id": (
            test_case[
                "id"
            ]
        ),

        "case_title": (
            test_case[
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
            context.get(
                "state"
            )
        ),

        "context_allow": (
            context.get(
                "allow_posture_evaluation"
            )
        ),

        "left_shoulder_x": (
            left_shoulder[
                "x"
            ]
            if left_shoulder
            else None
        ),

        "left_shoulder_y": (
            left_shoulder[
                "y"
            ]
            if left_shoulder
            else None
        ),

        "right_shoulder_x": (
            right_shoulder[
                "x"
            ]
            if right_shoulder
            else None
        ),

        "right_shoulder_y": (
            right_shoulder[
                "y"
            ]
            if right_shoulder
            else None
        ),

        "landmark_dx_px": (
            geometry[
                "dx_px"
            ]
        ),

        "landmark_dy_px": (
            geometry[
                "dy_px"
            ]
        ),

        "shoulder_width_px": (
            geometry[
                "shoulder_width_px"
            ]
        ),

        "normalized_dy": (
            geometry[
                "normalized_dy"
            ]
        ),

        "image_line_angle_deg": (
            geometry[
                "image_line_angle_deg"
            ]
        ),

        "shoulder_tilt": (
            get_feature_value(
                detection,
                "shoulder_tilt",
            )
        ),

        "neck_lateral_tilt": (
            get_feature_value(
                detection,
                "neck_lateral_tilt",
            )
        ),

        "neck_flexion": (
            get_feature_value(
                detection,
                "neck_flexion",
            )
        ),
    }


# ============================================================
# CAPTURE CASE
# ============================================================

def capture_case(
    camera,
    pipeline,
    test_case,
):

    rows = []

    print()
    print(
        "=" * 105
    )

    print(
        test_case[
            "title"
        ]
    )

    print(
        test_case[
            "instruction"
        ]
    )

    print()

    print(
        "Do not try to make numbers pass."
    )

    print(
        "Perform the posture naturally."
    )

    print(
        "Press S when ready."
    )

    print(
        "=" * 105
    )

    # ========================================================
    # WAIT
    # ========================================================

    while True:

        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        detection = (
            pipeline.process_frame(
                frame,
                timestamp=(
                    time.perf_counter()
                ),
            )
        )

        display = draw_display(
            frame,
            detection,
            test_case,
            mode="WAIT",
        )

        cv2.imshow(
            WINDOW_NAME,
            display,
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
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

    started = (
        time.perf_counter()
    )

    frame_index = 0

    while True:

        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        frame_index += 1

        timestamp = (
            time.perf_counter()
        )

        detection = (
            pipeline.process_frame(
                frame,
                timestamp=timestamp,
            )
        )

        elapsed = (
            time.perf_counter()
            -
            started
        )

        rows.append(
            build_row(
                test_case=(
                    test_case
                ),

                frame_index=(
                    frame_index
                ),

                elapsed=(
                    elapsed
                ),

                detection=(
                    detection
                ),
            )
        )

        display = draw_display(
            frame,
            detection,
            test_case,
            mode="CAPTURE",
            elapsed=elapsed,
        )

        cv2.imshow(
            WINDOW_NAME,
            display,
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key in (
            ord("q"),
            ord("Q"),
            27,
        ):
            raise KeyboardInterrupt

        if elapsed >= CAPTURE_SECONDS:
            break

    return rows


# ============================================================
# ANALYZE
# ============================================================

def analyze_case(
    test_case,
    rows,
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

    result = {
        "id": (
            test_case[
                "id"
            ]
        ),

        "title": (
            test_case[
                "title"
            ]
        ),

        "frames": (
            len(
                rows
            )
        ),

        "valid_enough": (
            len(
                rows
            )
            >=
            MIN_VALID_FRAMES
        ),

        "statistics": {},
    }

    for metric in metrics:

        values = [
            row.get(
                metric
            )
            for row in rows
        ]

        result[
            "statistics"
        ][
            metric
        ] = stats(
            values
        )

    return result


# ============================================================
# PRINT RESULT
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
        f"Frames : "
        f"{result['frames']}"
    )

    print()

    important = (
        "shoulder_tilt",
        "neck_lateral_tilt",
        "landmark_dy_px",
        "normalized_dy",
        "image_line_angle_deg",
    )

    for metric in important:

        s = (
            result[
                "statistics"
            ][
                metric
            ]
        )

        if s[
            "count"
        ] <= 0:
            continue

        print(
            f"{metric:<24}"
            f"median={s['median']:+.4f} "
            f"p05={s['p05']:+.4f} "
            f"p95={s['p95']:+.4f} "
            f"min={s['min']:+.4f} "
            f"max={s['max']:+.4f}"
        )

    print(
        "-" * 110
    )


# ============================================================
# SAVE
# ============================================================

def save_results(
    all_rows,
    results,
):

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    csv_path = (
        RESULTS_DIR
        /
        (
            "shoulder_neck_crosstalk_frames_"
            f"{stamp}.csv"
        )
    )

    json_path = (
        RESULTS_DIR
        /
        (
            "shoulder_neck_crosstalk_summary_"
            f"{stamp}.json"
        )
    )

    if all_rows:

        with csv_path.open(
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

    summary = {
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

        "results": (
            results
        ),

        "notes": {
            "diagnostic_only": True,

            "assessment_threshold_changed": False,

            "measurement_gate_changed": False,

            "database_used": False,

            "image_line_angle_is_debug_metric": True,
        },
    }

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return (
        csv_path,
        json_path,
    )


# ============================================================
# COMPARISON
# ============================================================

def median_of(
    result,
    metric,
):

    return (
        result[
            "statistics"
        ][
            metric
        ][
            "median"
        ]
    )


def print_comparison(
    results,
):

    by_id = {
        result[
            "id"
        ]: result
        for result
        in results
    }

    neutral = (
        by_id[
            "neutral"
        ]
    )

    natural = (
        by_id[
            "neck_right_natural"
        ]
    )

    level = (
        by_id[
            "neck_right_shoulders_level"
        ]
    )

    shoulder = (
        by_id[
            "left_shoulder_high"
        ]
    )

    print()
    print(
        "=" * 110
    )

    print(
        "CROSS-TALK COMPARISON"
    )

    print(
        "=" * 110
    )

    for metric in (
        "shoulder_tilt",
        "landmark_dy_px",
        "normalized_dy",
        "image_line_angle_deg",
    ):

        print()
        print(
            metric
        )

        print(
            f"  Neutral                     : "
            f"{median_of(neutral, metric)}"
        )

        print(
            f"  Neck Right Natural          : "
            f"{median_of(natural, metric)}"
        )

        print(
            f"  Neck Right Shoulders Level  : "
            f"{median_of(level, metric)}"
        )

        print(
            f"  Left Shoulder High          : "
            f"{median_of(shoulder, metric)}"
        )

    print()
    print(
        "INTERPRETATION GUIDE"
    )

    print(
        "-" * 110
    )

    print(
        "If Neck Right Natural AND Neck Right Shoulders Level "
        "both show shoulder landmark slope similar to Left Shoulder High:"
    )

    print(
        "  -> likely measurement / geometry / pose-landmark cross-talk."
    )

    print()

    print(
        "If Neck Right Natural shows large shoulder slope, "
        "but Shoulders-Level version returns close to Neutral:"
    )

    print(
        "  -> likely real body compensation during natural neck tilt."
    )

    print()

    print(
        "If production shoulder_tilt changes strongly but landmark_dy/"
        "image-line metrics stay near Neutral:"
    )

    print(
        "  -> inspect shoulder_tilt production geometry implementation."
    )

    print(
        "=" * 110
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
        "POSTGUARD - SHOULDER / NECK CROSS-TALK DIAGNOSTIC"
    )

    print(
        "=" * 110
    )

    print(
        f"Runner Version : "
        f"{RUNNER_VERSION}"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "- Diagnostic only"
    )

    print(
        "- No Assessment threshold changes"
    )

    print(
        "- No Measurement Gate changes"
    )

    print(
        "- No Database"
    )

    print(
        "- Do not force values to pass"
    )

    print(
        "=" * 110
    )

    camera = cv2.VideoCapture(
        CAMERA_INDEX
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
            1280,
            720,
        )

        for (
            index,
            test_case,
        ) in enumerate(
            TEST_CASES,
            start=1,
        ):

            print()
            print(
                f"TEST {index}/"
                f"{len(TEST_CASES)}"
            )

            rows = capture_case(
                camera,
                pipeline,
                test_case,
            )

            result = analyze_case(
                test_case,
                rows,
            )

            all_rows.extend(
                rows
            )

            results.append(
                result
            )

            print_case_result(
                result
            )

        print_comparison(
            results
        )

        (
            csv_path,
            json_path,
        ) = save_results(
            all_rows,
            results,
        )

        print()
        print(
            "RESULT FILES"
        )

        print(
            f"CSV  : "
            f"{csv_path}"
        )

        print(
            f"JSON : "
            f"{json_path}"
        )

        print()
        print(
            "Press Q / ESC to exit."
        )

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

            put(
                display,
                "POSTGUARD CROSS-TALK DIAGNOSTIC COMPLETE",
                20,
                45,
                WHITE,
                0.65,
                2,
            )

            put(
                display,
                "Q / ESC = Exit",
                20,
                90,
                CYAN,
                0.55,
                2,
            )

            cv2.imshow(
                WINDOW_NAME,
                display,
            )

            key = (
                cv2.waitKey(1)
                & 0xFF
            )

            if key in (
                ord("q"),
                ord("Q"),
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
            "SHOULDER / NECK DIAGNOSTIC CLOSED"
        )

        print(
            "DetectionPipeline : CLOSED"
        )

        print(
            "Camera            : RELEASED"
        )

        print(
            "Database          : NOT USED"
        )

        print(
            "=" * 95
        )


if __name__ == "__main__":
    main()