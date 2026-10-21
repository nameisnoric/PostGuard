from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2


# ==========================================================
# PATH SETUP
# ==========================================================

TEST_FILE = Path(__file__).resolve()

# backend/camera_card/
CAMERA_CARD_DIR = TEST_FILE.parents[2]

# backend/
BACKEND_DIR = CAMERA_CARD_DIR.parent

for path in (
    BACKEND_DIR,
    CAMERA_CARD_DIR,
):
    path_text = str(path)

    if path_text not in sys.path:
        sys.path.insert(
            0,
            path_text,
        )


# ==========================================================
# POSTGUARD IMPORTS
# ==========================================================

from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)

from camera_card.session_monitoring.session_monitor import (
    build_session_monitoring_snapshot,
)

from camera_card.session_monitoring.measurement_change_gate import (
    STATUS_CHANGED,
    STATUS_NOT_EVALUATED,
    STATUS_STABLE,
    evaluate_measurement_change,
    load_threshold_config,
)


# ==========================================================
# PERSONAL BASELINE MODULE
# ==========================================================

PERSONAL_BASELINE_PATH = (
    CAMERA_CARD_DIR
    / "baseline"
    / "personal_baseline.py"
)

if not PERSONAL_BASELINE_PATH.exists():
    raise FileNotFoundError(
        "Cannot find Personal Baseline module.\n"
        f"Expected: {PERSONAL_BASELINE_PATH}"
    )


spec = importlib.util.spec_from_file_location(
    "personal_baseline_shoulder_recovery_test",
    PERSONAL_BASELINE_PATH,
)

if (
    spec is None
    or spec.loader is None
):
    raise ImportError(
        "Cannot load Personal Baseline module.\n"
        f"Path: {PERSONAL_BASELINE_PATH}"
    )


pb = importlib.util.module_from_spec(
    spec
)

sys.modules[
    spec.name
] = pb

spec.loader.exec_module(
    pb
)


# ==========================================================
# CONFIGURATION
# ==========================================================

RUNNER_VERSION = (
    "3.0-shoulder-recovery-initial-stable-gate"
)

WINDOW_NAME = (
    "PostGuard - Shoulder Return Recovery"
)

CAMERA_INDEX = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720


# ----------------------------------------------------------
# Test durations
# ----------------------------------------------------------

INITIAL_STABLE_SECONDS = 5.0

SHOULDER_CHANGED_SECONDS = 5.0

RECOVERY_SECONDS = 10.0


# ----------------------------------------------------------
# Initial Stable acceptance
#
# ต้องผ่าน 2 เงื่อนไข
#
# 1. STABLE >= 80%
# 2. มี STABLE ต่อเนื่อง >= 1.5 sec
# ----------------------------------------------------------

INITIAL_STABLE_PASS_RATE = 0.80

INITIAL_STABLE_CONTINUOUS_SECONDS = 1.5


# ----------------------------------------------------------
# Shoulder Changed acceptance
# ----------------------------------------------------------

SHOULDER_CHANGED_PASS_RATE = 0.80


# ----------------------------------------------------------
# Recovery definition
# ----------------------------------------------------------

RECOVERY_STABLE_HOLD_SECONDS = 1.5


# ==========================================================
# PATHS
# ==========================================================

THRESHOLD_CONFIG_PATH = (
    CAMERA_CARD_DIR
    / "session_monitoring"
    / "measurement_change_thresholds.json"
)

RESULTS_DIR = (
    TEST_FILE.parent
    / "results"
    / "shoulder_return_recovery"
)


# ==========================================================
# COLORS
# OpenCV = BGR
# ==========================================================

WHITE = (
    255,
    255,
    255,
)

BLACK = (
    0,
    0,
    0,
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

MAGENTA = (
    255,
    0,
    255,
)

GRAY = (
    150,
    150,
    150,
)

DARK_GRAY = (
    35,
    35,
    35,
)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "PostGuard Shoulder Return / "
            "Recovery Diagnostic Test "
            "(Memory Only - Initial Stable Gate)"
        )
    )

    parser.add_argument(
        "--camera-index",
        type=int,
        default=CAMERA_INDEX,
    )

    return parser.parse_args()


# ==========================================================
# NUMERIC HELPERS
# ==========================================================

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

    if not isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return None

    number = float(
        value
    )

    if not math.isfinite(
        number
    ):
        return None

    return number


def safe_percent(
    numerator: int,
    denominator: int,
) -> float:

    if denominator <= 0:
        return 0.0

    return (
        numerator
        / denominator
        * 100.0
    )


def safe_median(
    values,
):
    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return float(
        statistics.median(
            clean
        )
    )


def safe_max(
    values,
):
    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return float(
        max(
            clean
        )
    )


# ==========================================================
# PERSONAL BASELINE COLLECTOR
# ==========================================================

def create_collector():
    config = (
        pb.PersonalBaselineConfig(
            target_samples=60,

            minimum_valid_ratio=0.70,

            min_calibration_seconds=15.0,

            max_calibration_seconds=30.0,

            max_shoulder_sd_deg=2.0,

            max_neck_lateral_sd_deg=2.0,

            max_neck_flexion_sd_deg=3.0,

            max_eye_distance_sd_px=5.0,
        )
    )

    return (
        pb.PersonalBaselineCollector(
            config
        )
    )


# ==========================================================
# IN-MEMORY SESSION / BASELINE
# ==========================================================

def create_memory_session_data(
    usable: dict[str, float],
):
    """
    ใช้ Dummy Positive IDs เพื่อให้ผ่าน
    Session Monitoring Contract

    ไม่มีการเขียน Database
    """

    TEST_SESSION_ID = 900001
    TEST_BASELINE_ID = 900002
    TEST_USER_ID = 900003
    TEST_CAMERA_ID = 900004

    baseline_data = {
        "baseline_id": (
            TEST_BASELINE_ID
        ),

        "user_id": (
            TEST_USER_ID
        ),

        "camera_id": (
            TEST_CAMERA_ID
        ),

        "shoulder_angle": (
            usable[
                "shoulder_tilt"
            ]
        ),

        "lateral_tilt_baseline": (
            usable[
                "neck_lateral_tilt"
            ]
        ),

        "neck_flexion_baseline": (
            usable[
                "neck_flexion"
            ]
        ),

        "eye_distance_baseline_px": (
            usable[
                "eye_distance"
            ]
        ),
    }

    session_data = {
        "session_id": (
            TEST_SESSION_ID
        ),

        "user_id": (
            TEST_USER_ID
        ),

        "camera_id": (
            TEST_CAMERA_ID
        ),

        "baseline_id": (
            TEST_BASELINE_ID
        ),

        "status": "RUNNING",
    }

    assert (
        session_data[
            "baseline_id"
        ]
        ==
        baseline_data[
            "baseline_id"
        ]
    )

    assert (
        session_data[
            "user_id"
        ]
        ==
        baseline_data[
            "user_id"
        ]
    )

    assert (
        session_data[
            "camera_id"
        ]
        ==
        baseline_data[
            "camera_id"
        ]
    )

    print()
    print(
        "=" * 90
    )

    print(
        "IN-MEMORY SESSION CONTRACT READY"
    )

    print(
        "=" * 90
    )

    print(
        f"Test Session ID  : "
        f"{TEST_SESSION_ID}"
    )

    print(
        f"Test Baseline ID : "
        f"{TEST_BASELINE_ID}"
    )

    print(
        f"Test User ID     : "
        f"{TEST_USER_ID}"
    )

    print(
        f"Test Camera ID   : "
        f"{TEST_CAMERA_ID}"
    )

    print()

    print(
        "Database INSERT : NO"
    )

    print(
        "Database UPDATE : NO"
    )

    print(
        "Database QUERY  : NO"
    )

    print(
        "=" * 90
    )

    return (
        session_data,
        baseline_data,
    )


# ==========================================================
# DRAW HELPERS
# ==========================================================

def put(
    frame,
    text,
    x,
    y,
    color=WHITE,
    scale=0.52,
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


def draw_point(
    frame,
    point,
    color,
    label=None,
):
    if point is None:
        return

    x, y = point

    cv2.circle(
        frame,
        (
            int(x),
            int(y),
        ),
        8,
        BLACK,
        -1,
        cv2.LINE_AA,
    )

    cv2.circle(
        frame,
        (
            int(x),
            int(y),
        ),
        5,
        color,
        -1,
        cv2.LINE_AA,
    )

    if label:
        put(
            frame,
            label,
            x + 8,
            y - 8,
            color,
            0.43,
            1,
        )


# ==========================================================
# LANDMARK HELPERS
# ==========================================================

def get_pose_point(
    detection_result,
    point_name,
):
    if not isinstance(
        detection_result,
        dict,
    ):
        return None

    landmarks = (
        detection_result.get(
            "landmarks"
        )
        or {}
    )

    pose = (
        landmarks.get(
            "pose"
        )
        or {}
    )

    point = pose.get(
        point_name
    )

    if not isinstance(
        point,
        dict,
    ):
        return None

    try:
        x = float(
            point["x"]
        )

        y = float(
            point["y"]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return None

    if not (
        math.isfinite(x)
        and
        math.isfinite(y)
    ):
        return None

    return (
        int(round(x)),
        int(round(y)),
    )


def mirror_point(
    point,
    frame_width,
):
    if point is None:
        return None

    x, y = point

    return (
        int(
            frame_width
            - 1
            - x
        ),
        int(y),
    )


def midpoint(
    point_a,
    point_b,
):
    if (
        point_a is None
        or point_b is None
    ):
        return None

    return (
        int(
            round(
                (
                    point_a[0]
                    + point_b[0]
                )
                / 2
            )
        ),

        int(
            round(
                (
                    point_a[1]
                    + point_b[1]
                )
                / 2
            )
        ),
    )


# ==========================================================
# SHOULDER LINE HELPERS
# ==========================================================

def visual_shoulder_line_angle(
    left,
    right,
):
    if (
        left is None
        or right is None
    ):
        return None

    dx = (
        right[0]
        - left[0]
    )

    dy = (
        right[1]
        - left[1]
    )

    if (
        dx == 0
        and dy == 0
    ):
        return None

    return float(
        math.degrees(
            math.atan2(
                dy,
                dx,
            )
        )
    )


def lower_side_label(
    left,
    right,
    tolerance_px=3,
):
    if (
        left is None
        or right is None
    ):
        return (
            "SHOULDER LANDMARK unavailable"
        )

    difference = (
        left[1]
        - right[1]
    )

    if (
        abs(difference)
        <= tolerance_px
    ):
        return (
            "DISPLAY SHOULDERS: NEAR LEVEL"
        )

    if difference > 0:
        return (
            "DISPLAY LEFT SIDE LOWER"
        )

    return (
        "DISPLAY RIGHT SIDE LOWER"
    )


def draw_horizontal_reference(
    frame,
    center,
    half_length=170,
):
    if center is None:
        return

    x, y = center

    cv2.line(
        frame,
        (
            x - half_length,
            y,
        ),
        (
            x + half_length,
            y,
        ),
        GRAY,
        1,
        cv2.LINE_AA,
    )


def draw_baseline_reference(
    frame,
    center,
    baseline_angle_deg,
    half_length=160,
):
    if (
        center is None
        or baseline_angle_deg is None
    ):
        return

    display_angle = (
        -baseline_angle_deg
    )

    radians = math.radians(
        display_angle
    )

    dx = (
        math.cos(radians)
        * half_length
    )

    dy = (
        math.sin(radians)
        * half_length
    )

    cx, cy = center

    point_1 = (
        int(round(cx - dx)),
        int(round(cy - dy)),
    )

    point_2 = (
        int(round(cx + dx)),
        int(round(cy + dy)),
    )

    cv2.line(
        frame,
        point_1,
        point_2,
        CYAN,
        2,
        cv2.LINE_AA,
    )


# ==========================================================
# BASELINE DISPLAY
# ==========================================================

def draw_baseline_display(
    frame,
    detection_result,
    state,
):
    display = cv2.flip(
        frame,
        1,
    )

    height, width = (
        display.shape[:2]
    )

    left = mirror_point(
        get_pose_point(
            detection_result,
            "left_shoulder",
        ),
        width,
    )

    right = mirror_point(
        get_pose_point(
            detection_result,
            "right_shoulder",
        ),
        width,
    )

    center = midpoint(
        left,
        right,
    )

    if (
        left is not None
        and right is not None
    ):
        draw_point(
            display,
            left,
            MAGENTA,
            "L",
        )

        draw_point(
            display,
            right,
            MAGENTA,
            "R",
        )

        cv2.line(
            display,
            left,
            right,
            GREEN,
            4,
            cv2.LINE_AA,
        )

        draw_horizontal_reference(
            display,
            center,
        )

    status = state.get(
        "status",
        "UNKNOWN",
    )

    samples = state.get(
        "sample_count",
        0,
    )

    elapsed = float(
        state.get(
            "elapsed_seconds",
            0.0,
        )
    )

    cv2.rectangle(
        display,
        (
            10,
            10,
        ),
        (
            580,
            220,
        ),
        DARK_GRAY,
        -1,
    )

    put(
        display,
        "POSTGUARD - FRESH BASELINE (RAM)",
        20,
        40,
        WHITE,
        0.62,
        2,
    )

    put(
        display,
        (
            f"Status        : "
            f"{status}"
        ),
        20,
        78,
        YELLOW,
        0.52,
        2,
    )

    put(
        display,
        (
            f"Valid Samples : "
            f"{samples}"
        ),
        20,
        112,
    )

    put(
        display,
        (
            f"Elapsed       : "
            f"{elapsed:.1f} sec"
        ),
        20,
        144,
    )

    if (
        status
        == pb.BASELINE_NEED_CONFIRMATION
    ):
        put(
            display,
            "Technical PASS - Press Y",
            20,
            185,
            GREEN,
            0.58,
            2,
        )

    else:
        put(
            display,
            (
                "S Start | R Restart "
                "| Q/ESC Exit"
            ),
            20,
            185,
        )

    return display


# ==========================================================
# SHOULDER DISPLAY
# ==========================================================

def draw_shoulder_display(
    frame,
    *,
    detection_result,
    phase_name,
    elapsed,
    snapshot,
    gate_result,
    shoulder_threshold,
):
    display = cv2.flip(
        frame,
        1,
    )

    height, width = (
        display.shape[:2]
    )

    left = mirror_point(
        get_pose_point(
            detection_result,
            "left_shoulder",
        ),
        width,
    )

    right = mirror_point(
        get_pose_point(
            detection_result,
            "right_shoulder",
        ),
        width,
    )

    center = midpoint(
        left,
        right,
    )

    shoulder = (
        snapshot.get(
            "features",
            {},
        ).get(
            "shoulder_tilt",
            {},
        )
    )

    baseline = finite_number(
        shoulder.get(
            "baseline"
        )
    )

    current = finite_number(
        shoulder.get(
            "current"
        )
    )

    delta = finite_number(
        shoulder.get(
            "delta"
        )
    )

    eligible = (
        shoulder.get(
            "baseline_comparison_eligible"
        )
    )

    shoulder_gate = (
        gate_result.get(
            "features",
            {},
        ).get(
            "shoulder_tilt",
            {},
        ).get(
            "status"
        )
    )

    overall_gate = (
        gate_result.get(
            "overall_status"
        )
    )

    if (
        shoulder_gate
        == STATUS_CHANGED
    ):
        current_color = RED

    elif (
        shoulder_gate
        == STATUS_STABLE
    ):
        current_color = GREEN

    else:
        current_color = YELLOW

    if (
        left is not None
        and
        right is not None
    ):
        draw_point(
            display,
            left,
            MAGENTA,
            "L",
        )

        draw_point(
            display,
            right,
            MAGENTA,
            "R",
        )

        cv2.line(
            display,
            left,
            right,
            current_color,
            4,
            cv2.LINE_AA,
        )

        draw_horizontal_reference(
            display,
            center,
        )

        draw_baseline_reference(
            display,
            center,
            baseline,
        )

    visual_angle = (
        visual_shoulder_line_angle(
            left,
            right,
        )
    )

    cv2.rectangle(
        display,
        (
            10,
            10,
        ),
        (
            540,
            325,
        ),
        DARK_GRAY,
        -1,
    )

    y = 38

    put(
        display,
        "POSTGUARD - SHOULDER RECOVERY",
        20,
        y,
        WHITE,
        0.62,
        2,
    )

    y += 34

    put(
        display,
        f"Phase      : {phase_name}",
        20,
        y,
        YELLOW,
        0.52,
        2,
    )

    y += 29

    put(
        display,
        f"Time       : {elapsed:.2f} sec",
        20,
        y,
    )

    y += 29

    put(
        display,
        (
            "Baseline   : "
            + (
                f"{baseline:+.3f} deg"
                if baseline is not None
                else "N/A"
            )
        ),
        20,
        y,
        CYAN,
    )

    y += 29

    put(
        display,
        (
            "Current    : "
            + (
                f"{current:+.3f} deg"
                if current is not None
                else "N/A"
            )
        ),
        20,
        y,
        current_color,
        0.54,
        2,
    )

    y += 29

    put(
        display,
        (
            "Delta      : "
            + (
                f"{delta:+.3f} deg"
                if delta is not None
                else "N/A"
            )
        ),
        20,
        y,
    )

    y += 29

    put(
        display,
        (
            f"Threshold  : "
            f"{shoulder_threshold:.3f} deg"
        ),
        20,
        y,
    )

    y += 29

    put(
        display,
        (
            f"Gate       : "
            f"{shoulder_gate}"
        ),
        20,
        y,
        current_color,
        0.54,
        2,
    )

    y += 29

    put(
        display,
        (
            f"Overall    : "
            f"{overall_gate}"
        ),
        20,
        y,
    )

    y += 29

    put(
        display,
        (
            f"Eligible   : "
            f"{eligible}"
        ),
        20,
        y,
    )

    put(
        display,
        (
            "Visual line angle: "
            + (
                f"{visual_angle:+.2f} deg"
                if visual_angle is not None
                else "N/A"
            )
        ),
        20,
        height - 88,
        WHITE,
        0.47,
        1,
    )

    put(
        display,
        lower_side_label(
            left,
            right,
        ),
        20,
        height - 58,
        YELLOW,
        0.50,
        2,
    )

    put(
        display,
        "Q / ESC = interrupt",
        20,
        height - 28,
        WHITE,
        0.43,
        1,
    )

    put(
        display,
        "CURRENT LINE",
        width - 250,
        35,
        current_color,
        0.48,
        2,
    )

    put(
        display,
        "BASELINE LINE",
        width - 250,
        62,
        CYAN,
        0.48,
        2,
    )

    put(
        display,
        "HORIZONTAL",
        width - 250,
        89,
        GRAY,
        0.48,
        1,
    )

    return display


# ==========================================================
# FRAME DATA
# ==========================================================

def build_frame_row(
    *,
    phase_name,
    phase_elapsed,
    snapshot,
    gate_result,
):
    context = (
        snapshot.get(
            "context",
            {},
        )
    )

    feature = (
        snapshot.get(
            "features",
            {},
        ).get(
            "shoulder_tilt",
            {},
        )
    )

    gate_feature = (
        gate_result.get(
            "features",
            {},
        ).get(
            "shoulder_tilt",
            {},
        )
    )

    return {
        "phase": (
            phase_name
        ),

        "phase_elapsed_seconds": (
            phase_elapsed
        ),

        "context_state": (
            context.get(
                "state"
            )
        ),

        "allow_posture_evaluation": (
            context.get(
                "allow_posture_evaluation"
            )
        ),

        "shoulder_baseline": (
            feature.get(
                "baseline"
            )
        ),

        "shoulder_current": (
            feature.get(
                "current"
            )
        ),

        "shoulder_delta": (
            feature.get(
                "delta"
            )
        ),

        "shoulder_eligible": (
            feature.get(
                "baseline_comparison_eligible"
            )
        ),

        "shoulder_gate_status": (
            gate_feature.get(
                "status"
            )
        ),

        "overall_gate_status": (
            gate_result.get(
                "overall_status"
            )
        ),
    }


# ==========================================================
# WAIT FOR PHASE
# ==========================================================

def wait_for_phase(
    *,
    camera,
    pipeline,
    title,
    instruction,
    key_char,
):
    print()
    print(
        "=" * 90
    )

    print(
        title
    )

    print(
        instruction
    )

    print(
        f"Press {key_char.upper()} when ready."
    )

    print(
        "=" * 90
    )

    valid_keys = (
        ord(
            key_char.lower()
        ),
        ord(
            key_char.upper()
        ),
    )

    while True:
        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        timestamp = (
            time.perf_counter()
        )

        result = (
            pipeline.process_frame(
                frame,
                timestamp=timestamp,
            )
        )

        display = cv2.flip(
            frame,
            1,
        )

        height, width = (
            display.shape[:2]
        )

        left = mirror_point(
            get_pose_point(
                result,
                "left_shoulder",
            ),
            width,
        )

        right = mirror_point(
            get_pose_point(
                result,
                "right_shoulder",
            ),
            width,
        )

        center = midpoint(
            left,
            right,
        )

        if (
            left is not None
            and
            right is not None
        ):
            draw_point(
                display,
                left,
                MAGENTA,
            )

            draw_point(
                display,
                right,
                MAGENTA,
            )

            cv2.line(
                display,
                left,
                right,
                GREEN,
                4,
                cv2.LINE_AA,
            )

            draw_horizontal_reference(
                display,
                center,
            )

        cv2.rectangle(
            display,
            (
                10,
                10,
            ),
            (
                1000,
                145,
            ),
            DARK_GRAY,
            -1,
        )

        put(
            display,
            title,
            20,
            42,
            WHITE,
            0.63,
            2,
        )

        put(
            display,
            instruction,
            20,
            82,
            YELLOW,
            0.47,
            1,
        )

        put(
            display,
            (
                f"Press "
                f"{key_char.upper()} "
                "when ready"
            ),
            20,
            118,
            GREEN,
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
            raise KeyboardInterrupt

        if key in valid_keys:
            return


# ==========================================================
# RUN PHASE
# ==========================================================

def run_phase(
    *,
    phase_name,
    duration_seconds,
    camera,
    pipeline,
    session_data,
    baseline_data,
    threshold_config,
    shoulder_threshold,
):
    """
    คืน rows ของ phase นี้โดยเฉพาะ
    """

    rows = []

    print()
    print(
        "=" * 90
    )

    print(
        f"START: {phase_name}"
    )

    print(
        f"Capture: "
        f"{duration_seconds:.1f} sec"
    )

    print(
        "=" * 90
    )

    started_at = (
        time.perf_counter()
    )

    while True:
        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        timestamp = (
            time.perf_counter()
        )

        elapsed = (
            timestamp
            - started_at
        )

        detection_result = (
            pipeline.process_frame(
                frame,
                timestamp=timestamp,
            )
        )

        snapshot = (
            build_session_monitoring_snapshot(
                session=(
                    session_data
                ),

                baseline=(
                    baseline_data
                ),

                detection_result=(
                    detection_result
                ),
            )
        )

        gate_result = (
            evaluate_measurement_change(
                snapshot,
                threshold_config,
            )
        )

        rows.append(
            build_frame_row(
                phase_name=(
                    phase_name
                ),

                phase_elapsed=(
                    elapsed
                ),

                snapshot=(
                    snapshot
                ),

                gate_result=(
                    gate_result
                ),
            )
        )

        display = (
            draw_shoulder_display(
                frame,

                detection_result=(
                    detection_result
                ),

                phase_name=(
                    phase_name
                ),

                elapsed=(
                    elapsed
                ),

                snapshot=(
                    snapshot
                ),

                gate_result=(
                    gate_result
                ),

                shoulder_threshold=(
                    shoulder_threshold
                ),
            )
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

        if (
            elapsed
            >= duration_seconds
        ):
            break

    print(
        f"COMPLETE: "
        f"{phase_name}"
    )

    return rows


# ==========================================================
# PHASE ANALYSIS
# ==========================================================

def analyze_phase(
    rows,
    phase_name,
):
    phase_rows = [
        row
        for row in rows
        if (
            row["phase"]
            == phase_name
        )
    ]

    statuses = [
        row.get(
            "shoulder_gate_status"
        )
        for row in phase_rows
    ]

    status_counts = dict(
        Counter(
            statuses
        )
    )

    stable_count = (
        status_counts.get(
            STATUS_STABLE,
            0,
        )
    )

    changed_count = (
        status_counts.get(
            STATUS_CHANGED,
            0,
        )
    )

    evaluable_count = (
        stable_count
        + changed_count
    )

    stable_rate = (
        stable_count
        / evaluable_count
        if evaluable_count
        else 0.0
    )

    changed_rate = (
        changed_count
        / evaluable_count
        if evaluable_count
        else 0.0
    )

    deltas = []

    currents = []

    for row in phase_rows:
        delta = finite_number(
            row.get(
                "shoulder_delta"
            )
        )

        current = finite_number(
            row.get(
                "shoulder_current"
            )
        )

        if delta is not None:
            deltas.append(
                delta
            )

        if current is not None:
            currents.append(
                current
            )

    abs_deltas = [
        abs(
            value
        )
        for value in deltas
    ]

    return {
        "phase": (
            phase_name
        ),

        "frames": (
            len(
                phase_rows
            )
        ),

        "status_counts": (
            status_counts
        ),

        "stable_rate": (
            stable_rate
        ),

        "stable_rate_percent": (
            stable_rate
            * 100.0
        ),

        "changed_rate": (
            changed_rate
        ),

        "changed_rate_percent": (
            changed_rate
            * 100.0
        ),

        "current_median_deg": (
            safe_median(
                currents
            )
        ),

        "delta_median_deg": (
            safe_median(
                deltas
            )
        ),

        "absolute_delta_median_deg": (
            safe_median(
                abs_deltas
            )
        ),

        "absolute_delta_max_deg": (
            safe_max(
                abs_deltas
            )
        ),
    }


# ==========================================================
# CONTINUOUS STABLE ANALYSIS
# ==========================================================

def find_continuous_stable(
    rows,
    required_seconds,
):
    """
    หา STABLE ต่อเนื่อง

    Return:
        start_time
        confirmed_at

    start_time:
        เวลาที่ continuous stable เริ่ม

    confirmed_at:
        เวลาที่ครบ required_seconds
    """

    stable_started_at = None

    for row in rows:
        elapsed = finite_number(
            row.get(
                "phase_elapsed_seconds"
            )
        )

        if elapsed is None:
            continue

        status = row.get(
            "shoulder_gate_status"
        )

        if (
            status
            == STATUS_STABLE
        ):
            if (
                stable_started_at
                is None
            ):
                stable_started_at = (
                    elapsed
                )

            stable_duration = (
                elapsed
                - stable_started_at
            )

            if (
                stable_duration
                >= required_seconds
            ):
                return (
                    stable_started_at,
                    elapsed,
                )

        else:
            stable_started_at = None

    return (
        None,
        None,
    )


# ==========================================================
# INITIAL STABLE VALIDATION
# ==========================================================

def validate_initial_stable(
    rows,
):
    result = analyze_phase(
        rows,
        "INITIAL_STABLE",
    )

    (
        continuous_start,
        continuous_confirmed,
    ) = (
        find_continuous_stable(
            rows,
            INITIAL_STABLE_CONTINUOUS_SECONDS,
        )
    )

    rate_passed = (
        result[
            "stable_rate"
        ]
        >= INITIAL_STABLE_PASS_RATE
    )

    continuous_passed = (
        continuous_confirmed
        is not None
    )

    passed = (
        rate_passed
        and
        continuous_passed
    )

    result.update({
        "required_stable_rate_percent": (
            INITIAL_STABLE_PASS_RATE
            * 100.0
        ),

        "required_continuous_stable_seconds": (
            INITIAL_STABLE_CONTINUOUS_SECONDS
        ),

        "continuous_stable_start_seconds": (
            continuous_start
        ),

        "continuous_stable_confirmed_seconds": (
            continuous_confirmed
        ),

        "stable_rate_passed": (
            rate_passed
        ),

        "continuous_stable_passed": (
            continuous_passed
        ),

        "passed": (
            passed
        ),
    })

    return result


# ==========================================================
# SHOULDER CHANGED VALIDATION
# ==========================================================

def validate_shoulder_changed(
    rows,
):
    result = analyze_phase(
        rows,
        "SHOULDER_CHANGED",
    )

    passed = (
        result[
            "changed_rate"
        ]
        >= SHOULDER_CHANGED_PASS_RATE
    )

    result.update({
        "required_changed_rate_percent": (
            SHOULDER_CHANGED_PASS_RATE
            * 100.0
        ),

        "passed": (
            passed
        ),
    })

    return result


# ==========================================================
# RECOVERY ANALYSIS
# ==========================================================

def analyze_recovery(
    rows,
):
    result = analyze_phase(
        rows,
        "RECOVERY",
    )

    recovery_rows = [
        row
        for row in rows
        if (
            row["phase"]
            == "RECOVERY"
        )
    ]

    first_stable_time = None

    for row in recovery_rows:
        if (
            row.get(
                "shoulder_gate_status"
            )
            == STATUS_STABLE
        ):
            first_stable_time = (
                finite_number(
                    row.get(
                        "phase_elapsed_seconds"
                    )
                )
            )

            break

    (
        stable_start,
        stable_confirmed_at,
    ) = (
        find_continuous_stable(
            recovery_rows,
            RECOVERY_STABLE_HOLD_SECONDS,
        )
    )

    result.update({
        "first_stable_time_seconds": (
            first_stable_time
        ),

        "required_continuous_stable_seconds": (
            RECOVERY_STABLE_HOLD_SECONDS
        ),

        "confirmed_recovery_start_seconds": (
            stable_start
        ),

        "confirmed_recovery_at_seconds": (
            stable_confirmed_at
        ),

        "recovered": (
            stable_confirmed_at
            is not None
        ),
    })

    return result


# ==========================================================
# INITIAL STABLE FAILURE MENU
# ==========================================================

def initial_stable_failure_menu(
    result,
):
    print()
    print(
        "=" * 90
    )

    print(
        "INITIAL STABLE: NOT PASSED"
    )

    print(
        "=" * 90
    )

    print(
        f"Stable Rate       : "
        f"{result['stable_rate_percent']:.2f}%"
    )

    print(
        f"Required          : "
        f">= "
        f"{INITIAL_STABLE_PASS_RATE * 100:.2f}%"
    )

    print()

    print(
        "Continuous Stable : "
        f"{result['continuous_stable_passed']}"
    )

    print(
        "Required          : "
        f">= "
        f"{INITIAL_STABLE_CONTINUOUS_SECONDS:.1f} sec"
    )

    print()

    print(
        "DO NOT continue to Shoulder Changed."
    )

    print()

    print(
        "T = Test Initial Stable again"
    )

    print(
        "R = Recalibrate Fresh Baseline"
    )

    print(
        "Q = Quit test"
    )

    print(
        "=" * 90
    )

    while True:
        key = (
            cv2.waitKey(0)
            & 0xFF
        )

        if key in (
            ord("t"),
            ord("T"),
        ):
            return "RETEST"

        if key in (
            ord("r"),
            ord("R"),
        ):
            return "REBASELINE"

        if key in (
            ord("q"),
            ord("Q"),
            27,
        ):
            return "QUIT"


# ==========================================================
# BASELINE CALIBRATION
# ==========================================================

def collect_fresh_baseline(
    *,
    camera,
    pipeline,
):
    collector = (
        create_collector()
    )

    print()
    print(
        "=" * 90
    )

    print(
        "PHASE 0 - FRESH PERSONAL BASELINE"
    )

    print(
        "=" * 90
    )

    print(
        "Sit naturally."
    )

    print(
        "Relax both shoulders."
    )

    print(
        "Look forward."
    )

    print(
        "Do NOT force shoulders level."
    )

    print()

    print(
        "Press S to start."
    )

    print(
        "=" * 90
    )

    baseline_started = False

    while True:
        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        timestamp = (
            time.perf_counter()
        )

        detection_result = (
            pipeline.process_frame(
                frame,
                timestamp=timestamp,
            )
        )

        if (
            baseline_started
            and
            not collector.completed
        ):
            state = (
                collector.add_detection_result(
                    detection_result
                )
            )

        else:
            state = (
                collector.get_status()
            )

        display = (
            draw_baseline_display(
                frame,
                detection_result,
                state,
            )
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
            collector = (
                create_collector()
            )

            pipeline.reset_context()

            baseline_started = True

            print()
            print(
                "CALIBRATION STARTED"
            )

            continue

        if key in (
            ord("r"),
            ord("R"),
        ):
            collector = (
                create_collector()
            )

            pipeline.reset_context()

            baseline_started = True

            print()
            print(
                "CALIBRATION RESTARTED"
            )

            continue

        if key in (
            ord("y"),
            ord("Y"),
        ):
            current_state = (
                collector.get_status()
            )

            if not (
                collector.completed
                and
                current_state.get(
                    "status"
                )
                == pb.BASELINE_NEED_CONFIRMATION
            ):
                print(
                    "Confirm ignored: "
                    "Baseline is not ready."
                )

                continue

            collector.confirm()

            usable_baseline = (
                collector.get_usable_baseline()
            )

            print()
            print(
                "=" * 90
            )

            print(
                "PERSONAL BASELINE CONFIRMED "
                "- MEMORY ONLY"
            )

            print(
                "=" * 90
            )

            for (
                feature_name,
                feature_value,
            ) in usable_baseline.items():

                print(
                    f"{feature_name:<24}: "
                    f"{feature_value}"
                )

            print()

            print(
                "Nothing was saved to Database."
            )

            print(
                "=" * 90
            )

            return (
                usable_baseline
            )


# ==========================================================
# SAVE RESULTS
# ==========================================================

def save_results(
    *,
    rows,
    usable_baseline,
    shoulder_threshold,
    initial_validation,
    changed_validation,
    recovery_result,
):
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp_text = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    csv_path = (
        RESULTS_DIR
        / (
            "shoulder_recovery_frames_"
            f"{timestamp_text}.csv"
        )
    )

    json_path = (
        RESULTS_DIR
        / (
            "shoulder_recovery_summary_"
            f"{timestamp_text}.json"
        )
    )

    if rows:
        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(
                    rows[0].keys()
                ),
            )

            writer.writeheader()

            writer.writerows(
                rows
            )

    summary = {
        "runner_version": (
            RUNNER_VERSION
        ),

        "created_at": (
            datetime.now()
            .isoformat()
        ),

        "database_used": False,

        "personal_baseline": (
            usable_baseline
        ),

        "shoulder_threshold_deg": (
            shoulder_threshold
        ),

        "configuration": {
            "initial_stable_seconds": (
                INITIAL_STABLE_SECONDS
            ),

            "initial_stable_pass_rate": (
                INITIAL_STABLE_PASS_RATE
            ),

            "initial_stable_continuous_seconds": (
                INITIAL_STABLE_CONTINUOUS_SECONDS
            ),

            "shoulder_changed_seconds": (
                SHOULDER_CHANGED_SECONDS
            ),

            "shoulder_changed_pass_rate": (
                SHOULDER_CHANGED_PASS_RATE
            ),

            "recovery_seconds": (
                RECOVERY_SECONDS
            ),

            "recovery_stable_hold_seconds": (
                RECOVERY_STABLE_HOLD_SECONDS
            ),
        },

        "initial_stable": (
            initial_validation
        ),

        "shoulder_changed": (
            changed_validation
        ),

        "recovery": (
            recovery_result
        ),

        "interpretation": {
            "changed_means_risk": False,

            "stable_means_safe": False,

            "test_role": (
                "diagnostic_shoulder_"
                "return_recovery"
            ),

            "baseline_persisted": False,

            "session_persisted": False,
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

    print()
    print(
        "=" * 100
    )

    print(
        "POSTGUARD - SHOULDER RECOVERY RESULT"
    )

    print(
        "=" * 100
    )

    print(
        "DATABASE USED : NO"
    )

    print(
        f"Baseline      : "
        f"{usable_baseline['shoulder_tilt']:+.6f} deg"
    )

    print(
        f"Threshold     : "
        f"{shoulder_threshold:.6f} deg"
    )

    print()

    print(
        "[INITIAL_STABLE]"
    )

    print(
        f"  Frames              : "
        f"{initial_validation['frames']}"
    )

    print(
        f"  Status Count        : "
        f"{initial_validation['status_counts']}"
    )

    print(
        f"  Stable Rate         : "
        f"{initial_validation['stable_rate_percent']:.2f}%"
    )

    print(
        f"  Required Stable     : "
        f"{INITIAL_STABLE_PASS_RATE * 100:.2f}%"
    )

    print(
        f"  Continuous Stable   : "
        f"{initial_validation['continuous_stable_passed']}"
    )

    print(
        f"  Initial Result      : "
        f"{'PASS' if initial_validation['passed'] else 'FAIL'}"
    )

    print()

    print(
        "[SHOULDER_CHANGED]"
    )

    print(
        f"  Frames              : "
        f"{changed_validation['frames']}"
    )

    print(
        f"  Status Count        : "
        f"{changed_validation['status_counts']}"
    )

    print(
        f"  Changed Rate        : "
        f"{changed_validation['changed_rate_percent']:.2f}%"
    )

    print(
        f"  Required Changed    : "
        f"{SHOULDER_CHANGED_PASS_RATE * 100:.2f}%"
    )

    print(
        f"  Changed Result      : "
        f"{'PASS' if changed_validation['passed'] else 'FAIL'}"
    )

    print()

    print(
        "[RECOVERY]"
    )

    print(
        f"  Frames              : "
        f"{recovery_result['frames']}"
    )

    print(
        f"  Status Count        : "
        f"{recovery_result['status_counts']}"
    )

    print(
        f"  Stable Rate         : "
        f"{recovery_result['stable_rate_percent']:.2f}%"
    )

    print(
        f"  Changed Rate        : "
        f"{recovery_result['changed_rate_percent']:.2f}%"
    )

    print(
        f"  Current Median      : "
        f"{recovery_result['current_median_deg']}"
    )

    print(
        f"  Delta Median        : "
        f"{recovery_result['delta_median_deg']}"
    )

    print(
        f"  Median |Delta|      : "
        f"{recovery_result['absolute_delta_median_deg']}"
    )

    print(
        f"  Max |Delta|         : "
        f"{recovery_result['absolute_delta_max_deg']}"
    )

    print()

    print(
        "RECOVERY DETAIL"
    )

    print(
        f"  First STABLE        : "
        f"{recovery_result['first_stable_time_seconds']}"
    )

    print(
        "  Recovery Start      : "
        f"{recovery_result['confirmed_recovery_start_seconds']}"
    )

    print(
        "  Recovery Confirmed  : "
        f"{recovery_result['confirmed_recovery_at_seconds']}"
    )

    print(
        f"  Recovered           : "
        f"{recovery_result['recovered']}"
    )

    print()

    print(
        f"CSV  : {csv_path}"
    )

    print(
        f"JSON : {json_path}"
    )

    print(
        "=" * 100
    )


# ==========================================================
# MAIN
# ==========================================================

def main():
    args = parse_args()

    # ======================================================
    # THRESHOLD
    # ======================================================

    if (
        not THRESHOLD_CONFIG_PATH.exists()
    ):
        raise RuntimeError(
            "Measurement Change threshold config "
            "not found:\n"
            f"{THRESHOLD_CONFIG_PATH}"
        )

    threshold_config = (
        load_threshold_config(
            THRESHOLD_CONFIG_PATH
        )
    )

    shoulder_threshold = (
        finite_number(
            threshold_config.get(
                "features",
                {},
            ).get(
                "shoulder_tilt",
                {},
            ).get(
                "threshold"
            )
        )
    )

    if (
        shoulder_threshold is None
        or
        shoulder_threshold <= 0
    ):
        raise RuntimeError(
            "Invalid shoulder_tilt threshold."
        )

    # ======================================================
    # INFO
    # ======================================================

    print()
    print(
        "=" * 100
    )

    print(
        "POSTGUARD - SHOULDER RETURN / "
        "RECOVERY DIAGNOSTIC"
    )

    print(
        "=" * 100
    )

    print(
        f"Runner Version : "
        f"{RUNNER_VERSION}"
    )

    print(
        f"Threshold      : "
        f"{shoulder_threshold:.6f} deg"
    )

    print()

    print(
        "DATABASE:"
    )

    print(
        "  PersonalBaseline INSERT : NO"
    )

    print(
        "  PostureSession INSERT    : NO"
    )

    print(
        "  PostgreSQL test data     : NO"
    )

    print()

    print(
        "FLOW:"
    )

    print(
        "Fresh Baseline (RAM)"
    )

    print(
        "  -> Initial Stable 5 sec"
    )

    print(
        f"  -> MUST PASS >= "
        f"{INITIAL_STABLE_PASS_RATE * 100:.0f}% STABLE"
    )

    print(
        f"  -> AND continuous STABLE "
        f">= {INITIAL_STABLE_CONTINUOUS_SECONDS:.1f} sec"
    )

    print(
        "  -> Shoulder Down 5 sec"
    )

    print(
        "  -> Natural Recovery 10 sec"
    )

    print(
        "=" * 100
    )

    # ======================================================
    # CAMERA
    # ======================================================

    camera = cv2.VideoCapture(
        args.camera_index
    )

    if not camera.isOpened():
        raise RuntimeError(
            f"Cannot open camera index "
            f"{args.camera_index}"
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

    final_rows = []

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

        # ==================================================
        # OUTER LOOP
        #
        # ถ้า Initial Stable fail
        # ผู้ใช้สามารถกลับมาเก็บ Baseline ใหม่ได้
        # ==================================================

        while True:

            # ==============================================
            # FRESH BASELINE
            # ==============================================

            usable_baseline = (
                collect_fresh_baseline(
                    camera=camera,
                    pipeline=pipeline,
                )
            )

            (
                session_data,
                baseline_data,
            ) = (
                create_memory_session_data(
                    usable_baseline
                )
            )

            # ==============================================
            # INITIAL STABLE LOOP
            # ==============================================

            rebaseline_requested = False

            while True:
                wait_for_phase(
                    camera=camera,

                    pipeline=pipeline,

                    title=(
                        "PHASE 1 - INITIAL STABLE"
                    ),

                    instruction=(
                        "Stay naturally in the SAME "
                        "posture used for Baseline."
                    ),

                    key_char="1",
                )

                initial_rows = (
                    run_phase(
                        phase_name=(
                            "INITIAL_STABLE"
                        ),

                        duration_seconds=(
                            INITIAL_STABLE_SECONDS
                        ),

                        camera=camera,

                        pipeline=pipeline,

                        session_data=(
                            session_data
                        ),

                        baseline_data=(
                            baseline_data
                        ),

                        threshold_config=(
                            threshold_config
                        ),

                        shoulder_threshold=(
                            shoulder_threshold
                        ),
                    )
                )

                initial_validation = (
                    validate_initial_stable(
                        initial_rows
                    )
                )

                print()
                print(
                    "=" * 90
                )

                print(
                    "INITIAL STABLE VALIDATION"
                )

                print(
                    "=" * 90
                )

                print(
                    f"Stable Rate       : "
                    f"{initial_validation['stable_rate_percent']:.2f}%"
                )

                print(
                    f"Required          : "
                    f">= "
                    f"{INITIAL_STABLE_PASS_RATE * 100:.2f}%"
                )

                print(
                    "Continuous Stable : "
                    f"{initial_validation['continuous_stable_passed']}"
                )

                print(
                    f"Required          : "
                    f">= "
                    f"{INITIAL_STABLE_CONTINUOUS_SECONDS:.1f} sec"
                )

                print(
                    "Result            : "
                    f"{'PASS' if initial_validation['passed'] else 'FAIL'}"
                )

                print(
                    "=" * 90
                )

                if (
                    initial_validation[
                        "passed"
                    ]
                ):
                    final_rows = list(
                        initial_rows
                    )

                    break

                action = (
                    initial_stable_failure_menu(
                        initial_validation
                    )
                )

                if (
                    action
                    == "RETEST"
                ):
                    print()
                    print(
                        "Retry Initial Stable "
                        "using the SAME Baseline."
                    )

                    continue

                if (
                    action
                    == "REBASELINE"
                ):
                    print()
                    print(
                        "Discarding current "
                        "in-memory Baseline."
                    )

                    print(
                        "Starting Fresh Baseline."
                    )

                    pipeline.reset_context()

                    rebaseline_requested = True

                    break

                if (
                    action
                    == "QUIT"
                ):
                    raise KeyboardInterrupt

            # ------------------------------------------------
            # Fresh baseline requested
            # ------------------------------------------------

            if rebaseline_requested:
                continue

            # ------------------------------------------------
            # Initial Stable PASSED
            # Exit outer baseline loop
            # ------------------------------------------------

            break

        # ==================================================
        # PHASE 2
        # SHOULDER CHANGED
        # ==================================================

        wait_for_phase(
            camera=camera,

            pipeline=pipeline,

            title=(
                "PHASE 2 - SHOULDER DOWN"
            ),

            instruction=(
                "Lower ONE shoulder clearly. "
                "Keep head/neck straight. HOLD."
            ),

            key_char="2",
        )

        changed_rows = (
            run_phase(
                phase_name=(
                    "SHOULDER_CHANGED"
                ),

                duration_seconds=(
                    SHOULDER_CHANGED_SECONDS
                ),

                camera=camera,

                pipeline=pipeline,

                session_data=(
                    session_data
                ),

                baseline_data=(
                    baseline_data
                ),

                threshold_config=(
                    threshold_config
                ),

                shoulder_threshold=(
                    shoulder_threshold
                ),
            )
        )

        changed_validation = (
            validate_shoulder_changed(
                changed_rows
            )
        )

        final_rows.extend(
            changed_rows
        )

        print()
        print(
            "=" * 90
        )

        print(
            "SHOULDER CHANGED VALIDATION"
        )

        print(
            "=" * 90
        )

        print(
            f"Changed Rate : "
            f"{changed_validation['changed_rate_percent']:.2f}%"
        )

        print(
            f"Required     : "
            f">= "
            f"{SHOULDER_CHANGED_PASS_RATE * 100:.2f}%"
        )

        print(
            f"Result       : "
            f"{'PASS' if changed_validation['passed'] else 'FAIL'}"
        )

        print(
            "=" * 90
        )

        # ==================================================
        # ถ้า Shoulder Changed ไม่ผ่าน
        #
        # ยังเก็บ Recovery ได้
        # แต่ Console จะเตือนว่าผลควรตีความด้วยความระวัง
        # ==================================================

        if not (
            changed_validation[
                "passed"
            ]
        ):
            print()
            print(
                "WARNING:"
            )

            print(
                "Shoulder Changed did not meet "
                "the required changed rate."
            )

            print(
                "Recovery will still be captured, "
                "but this run should not be used "
                "as final validation evidence."
            )

        # ==================================================
        # PHASE 3
        # RECOVERY
        # ==================================================

        wait_for_phase(
            camera=camera,

            pipeline=pipeline,

            title=(
                "PHASE 3 - NATURAL RECOVERY"
            ),

            instruction=(
                "Release shoulder naturally. "
                "Do NOT aim at baseline line. "
                "Press 3 immediately after release."
            ),

            key_char="3",
        )

        recovery_rows = (
            run_phase(
                phase_name=(
                    "RECOVERY"
                ),

                duration_seconds=(
                    RECOVERY_SECONDS
                ),

                camera=camera,

                pipeline=pipeline,

                session_data=(
                    session_data
                ),

                baseline_data=(
                    baseline_data
                ),

                threshold_config=(
                    threshold_config
                ),

                shoulder_threshold=(
                    shoulder_threshold
                ),
            )
        )

        final_rows.extend(
            recovery_rows
        )

        recovery_result = (
            analyze_recovery(
                recovery_rows
            )
        )

        # ==================================================
        # SAVE
        # ==================================================

        save_results(
            rows=(
                final_rows
            ),

            usable_baseline=(
                usable_baseline
            ),

            shoulder_threshold=(
                shoulder_threshold
            ),

            initial_validation=(
                initial_validation
            ),

            changed_validation=(
                changed_validation
            ),

            recovery_result=(
                recovery_result
            ),
        )

    except KeyboardInterrupt:
        print()
        print(
            "Test interrupted."
        )

    finally:
        if pipeline is not None:
            pipeline.close()

        camera.release()

        cv2.destroyAllWindows()

        print()
        print(
            "=" * 90
        )

        print(
            "POSTGUARD SHOULDER TEST CLOSED"
        )

        print(
            "=" * 90
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
            "Baseline DB       : NOT CREATED"
        )

        print(
            "Session DB        : NOT CREATED"
        )

        print(
            "=" * 90
        )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    main()