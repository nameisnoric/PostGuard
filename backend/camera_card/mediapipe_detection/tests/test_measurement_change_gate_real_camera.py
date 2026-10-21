from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2


# ============================================================
# PATH SETUP
# ============================================================

TEST_FILE = Path(__file__).resolve()

CURRENT_DIR = TEST_FILE.parent

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


# ============================================================
# POSTGUARD IMPORTS
# ============================================================

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


# ============================================================
# PERSONAL BASELINE MODULE
# ============================================================

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
    "personal_baseline_e2e_gate_test",
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


# ============================================================
# RUNNER CONFIG
# ============================================================

RUNNER_VERSION = (
    "3.0-e2e-gate-recovery-protocol"
)

WINDOW_NAME = (
    "PostGuard - E2E Measurement Change Gate v3"
)

DEFAULT_CAMERA_INDEX = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720


# ============================================================
# TEST CONFIG
# ============================================================

CAPTURE_SECONDS = 5.0

RECOVERY_TIMEOUT_SECONDS = 10.0

RECOVERY_REQUIRED_STABLE_SECONDS = 1.5

MIN_CAPTURE_FRAMES = 30


# ------------------------------------------------------------
# Pass criteria
# ------------------------------------------------------------

STABLE_PASS_RATE = 0.80

CHANGED_PASS_RATE = 0.80

NOT_EVALUATED_PASS_RATE = 0.70


# ============================================================
# PATHS
# ============================================================

THRESHOLD_CONFIG_PATH = (
    CAMERA_CARD_DIR
    / "session_monitoring"
    / "measurement_change_thresholds.json"
)

RESULTS_DIR = (
    CURRENT_DIR
    / "results"
    / "measurement_change_gate_real_camera_v3"
)


# ============================================================
# FEATURES
# ============================================================

POSTURE_FEATURES = {
    "shoulder_tilt": {
        "label": "Shoulder Tilt",
        "unit": "deg",
    },

    "neck_lateral_tilt": {
        "label": "Neck Lateral Tilt",
        "unit": "deg",
    },

    "neck_flexion": {
        "label": "Neck Flexion",
        "unit": "deg",
    },
}

POSTURE_FEATURE_ORDER = list(
    POSTURE_FEATURES.keys()
)


# ============================================================
# TEST STEPS
#
# 8 Gate validation steps
#
# Recovery phases are stored separately.
# ============================================================

TEST_STEPS = [
    {
        "id": "initial_stable",

        "title": (
            "Initial Stable"
        ),

        "test_type": (
            "stable"
        ),

        "target_feature": None,

        "instruction": (
            "Remain in the SAME natural posture "
            "used for the Personal Baseline."
        ),
    },

    {
        "id": "shoulder_changed",

        "title": (
            "Shoulder Tilt Changed"
        ),

        "test_type": (
            "changed"
        ),

        "target_feature": (
            "shoulder_tilt"
        ),

        "instruction": (
            "Lower or tilt ONE shoulder clearly. "
            "Keep head and neck straight. HOLD."
        ),
    },

    {
        "id": "return_after_shoulder",

        "title": (
            "Stable Hold After Shoulder Recovery"
        ),

        "test_type": (
            "stable"
        ),

        "target_feature": None,

        "instruction": (
            "Keep the naturally recovered posture "
            "still for the Stable Hold validation."
        ),
    },

    {
        "id": "neck_lateral_changed",

        "title": (
            "Neck Lateral Tilt Changed"
        ),

        "test_type": (
            "changed"
        ),

        "target_feature": (
            "neck_lateral_tilt"
        ),

        "instruction": (
            "Tilt your HEAD sideways clearly. "
            "Keep shoulders still. HOLD."
        ),
    },

    {
        "id": "return_after_lateral",

        "title": (
            "Stable Hold After Neck Lateral Recovery"
        ),

        "test_type": (
            "stable"
        ),

        "target_feature": None,

        "instruction": (
            "Keep the naturally recovered posture "
            "still for the Stable Hold validation."
        ),
    },

    {
        "id": "neck_flexion_changed",

        "title": (
            "Neck Flexion Changed"
        ),

        "test_type": (
            "changed"
        ),

        "target_feature": (
            "neck_flexion"
        ),

        "instruction": (
            "Flex or extend your head clearly. "
            "Keep shoulders stable. HOLD."
        ),
    },

    {
        "id": "return_after_flexion",

        "title": (
            "Stable Hold After Neck Flexion Recovery"
        ),

        "test_type": (
            "stable"
        ),

        "target_feature": None,

        "instruction": (
            "Keep the naturally recovered posture "
            "still for the Stable Hold validation."
        ),
    },

    {
        "id": "invalid_context",

        "title": (
            "Invalid Context"
        ),

        "test_type": (
            "invalid"
        ),

        "target_feature": None,

        "instruction": (
            "Move clearly OUT of usable camera context. "
            "Move most of face/body out of frame "
            "or turn far away and HOLD."
        ),
    },
]


# ============================================================
# RECOVERY PHASE CONFIG
# ============================================================

RECOVERY_PHASES = {
    "shoulder_changed": {
        "id": (
            "recovery_after_shoulder"
        ),

        "title": (
            "Recovery After Shoulder"
        ),

        "target_feature": (
            "shoulder_tilt"
        ),

        "instruction": (
            "Release the shoulder naturally. "
            "Do NOT aim at the baseline line."
        ),
    },

    "neck_lateral_changed": {
        "id": (
            "recovery_after_lateral"
        ),

        "title": (
            "Recovery After Neck Lateral"
        ),

        "target_feature": (
            "neck_lateral_tilt"
        ),

        "instruction": (
            "Return your head naturally to the "
            "original forward posture."
        ),
    },

    "neck_flexion_changed": {
        "id": (
            "recovery_after_flexion"
        ),

        "title": (
            "Recovery After Neck Flexion"
        ),

        "target_feature": (
            "neck_flexion"
        ),

        "instruction": (
            "Return your head naturally to the "
            "original neutral posture."
        ),
    },
}


# ============================================================
# COMMAND LINE
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "PostGuard E2E Measurement-Change Gate "
            "Recovery Protocol v3"
        )
    )

    parser.add_argument(
        "--camera-index",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
    )

    return parser.parse_args()


# ============================================================
# NUMERIC
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


def percentage(
    numerator,
    denominator,
):
    if denominator <= 0:
        return 0.0

    return (
        numerator
        /
        denominator
        *
        100.0
    )


# ============================================================
# PERSONAL BASELINE
# ============================================================

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


# ============================================================
# IN-MEMORY SESSION
#
# Session Monitor requires positive integer IDs.
# They are TEST ONLY.
# ============================================================

def create_memory_session_data(
    usable_baseline,
):
    TEST_SESSION_ID = 900001
    TEST_BASELINE_ID = 900002
    TEST_USER_ID = 900003
    TEST_CAMERA_ID = 900004

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
            usable_baseline[
                "shoulder_tilt"
            ]
        ),

        "lateral_tilt_baseline": (
            usable_baseline[
                "neck_lateral_tilt"
            ]
        ),

        "neck_flexion_baseline": (
            usable_baseline[
                "neck_flexion"
            ]
        ),

        "eye_distance_baseline_px": (
            usable_baseline[
                "eye_distance"
            ]
        ),
    }

    return (
        session_data,
        baseline_data,
    )


# ============================================================
# DRAW
# ============================================================

WHITE = (255, 255, 255)
GREEN = (0, 220, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
CYAN = (255, 255, 0)
GRAY = (160, 160, 160)
BLACK = (0, 0, 0)


def draw_text(
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


def format_number(
    value,
    digits=3,
    signed=False,
):
    value = finite_number(
        value
    )

    if value is None:
        return "N/A"

    if signed:
        return (
            f"{value:+.{digits}f}"
        )

    return (
        f"{value:.{digits}f}"
    )


# ============================================================
# DISPLAY
# ============================================================

def draw_gate_display(
    frame,
    *,
    title,
    instruction,
    snapshot,
    gate_result,
    elapsed=None,
    duration=None,
    extra_text=None,
):
    display = cv2.flip(
        frame,
        1,
    )

    overlay = (
        display.copy()
    )

    panel_width = min(
        900,
        display.shape[1],
    )

    panel_height = min(
        500,
        display.shape[0],
    )

    cv2.rectangle(
        overlay,
        (
            0,
            0,
        ),
        (
            panel_width,
            panel_height,
        ),
        BLACK,
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.66,
        display,
        0.34,
        0,
        display,
    )

    context = (
        snapshot.get(
            "context",
            {},
        )
    )

    y = 32

    draw_text(
        display,
        "POSTGUARD - E2E GATE v3",
        20,
        y,
        WHITE,
        0.64,
        2,
    )

    y += 34

    draw_text(
        display,
        title,
        20,
        y,
        YELLOW,
        0.58,
        2,
    )

    y += 30

    draw_text(
        display,
        instruction,
        20,
        y,
        WHITE,
        0.43,
        1,
    )

    y += 35

    draw_text(
        display,
        (
            f"Context: "
            f"{context.get('state')} "
            f"| Allow: "
            f"{context.get('allow_posture_evaluation')}"
        ),
        20,
        y,
    )

    y += 30

    if (
        elapsed is not None
        and
        duration is not None
    ):
        draw_text(
            display,
            (
                f"Time: "
                f"{elapsed:.2f} / "
                f"{duration:.2f} sec"
            ),
            20,
            y,
        )

        y += 32

    draw_text(
        display,
        "Feature",
        20,
        y,
        WHITE,
        0.48,
        2,
    )

    draw_text(
        display,
        "Baseline",
        230,
        y,
        WHITE,
        0.48,
        2,
    )

    draw_text(
        display,
        "Current",
        345,
        y,
        WHITE,
        0.48,
        2,
    )

    draw_text(
        display,
        "Delta",
        455,
        y,
        WHITE,
        0.48,
        2,
    )

    draw_text(
        display,
        "Threshold",
        570,
        y,
        WHITE,
        0.48,
        2,
    )

    draw_text(
        display,
        "Gate",
        700,
        y,
        WHITE,
        0.48,
        2,
    )

    y += 29

    for feature_name in (
        POSTURE_FEATURE_ORDER
    ):
        snapshot_feature = (
            snapshot.get(
                "features",
                {},
            ).get(
                feature_name,
                {},
            )
        )

        gate_feature = (
            gate_result.get(
                "features",
                {},
            ).get(
                feature_name,
                {},
            )
        )

        status = (
            gate_feature.get(
                "status",
                "N/A",
            )
        )

        if status == STATUS_STABLE:
            status_color = GREEN

        elif status == STATUS_CHANGED:
            status_color = RED

        else:
            status_color = YELLOW

        draw_text(
            display,
            POSTURE_FEATURES[
                feature_name
            ][
                "label"
            ],
            20,
            y,
        )

        draw_text(
            display,
            format_number(
                snapshot_feature.get(
                    "baseline"
                )
            ),
            230,
            y,
        )

        draw_text(
            display,
            format_number(
                snapshot_feature.get(
                    "current"
                )
            ),
            345,
            y,
        )

        draw_text(
            display,
            format_number(
                snapshot_feature.get(
                    "delta"
                ),
                signed=True,
            ),
            455,
            y,
        )

        draw_text(
            display,
            format_number(
                gate_feature.get(
                    "threshold"
                )
            ),
            570,
            y,
        )

        draw_text(
            display,
            status,
            700,
            y,
            status_color,
            0.48,
            2,
        )

        y += 29

    y += 10

    overall = (
        gate_result.get(
            "overall_status"
        )
    )

    if overall == STATUS_STABLE:
        overall_color = GREEN

    elif overall == STATUS_CHANGED:
        overall_color = RED

    else:
        overall_color = YELLOW

    draw_text(
        display,
        (
            f"Overall Gate: "
            f"{overall}"
        ),
        20,
        y,
        overall_color,
        0.57,
        2,
    )

    if extra_text:

        y += 32

        draw_text(
            display,
            extra_text,
            20,
            y,
            CYAN,
            0.48,
            2,
        )

    return display


# ============================================================
# BASELINE DISPLAY
# ============================================================

def draw_baseline_display(
    frame,
    state,
):
    display = cv2.flip(
        frame,
        1,
    )

    overlay = (
        display.copy()
    )

    cv2.rectangle(
        overlay,
        (
            0,
            0,
        ),
        (
            min(
                700,
                display.shape[1],
            ),
            240,
        ),
        BLACK,
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.66,
        display,
        0.34,
        0,
        display,
    )

    status = state.get(
        "status",
        "UNKNOWN",
    )

    sample_count = state.get(
        "sample_count",
        0,
    )

    elapsed = finite_number(
        state.get(
            "elapsed_seconds"
        )
    )

    if elapsed is None:
        elapsed = 0.0

    draw_text(
        display,
        "POSTGUARD - FRESH PERSONAL BASELINE",
        20,
        40,
        WHITE,
        0.65,
        2,
    )

    draw_text(
        display,
        (
            f"Status: "
            f"{status}"
        ),
        20,
        80,
        YELLOW,
        0.56,
        2,
    )

    draw_text(
        display,
        (
            f"Valid Samples: "
            f"{sample_count}"
        ),
        20,
        120,
    )

    draw_text(
        display,
        (
            f"Elapsed: "
            f"{elapsed:.1f} sec"
        ),
        20,
        155,
    )

    if (
        status
        == pb.BASELINE_NEED_CONFIRMATION
    ):
        draw_text(
            display,
            "Technical PASS - Press Y to confirm",
            20,
            200,
            GREEN,
            0.57,
            2,
        )

    else:
        draw_text(
            display,
            (
                "S = Start | R = Restart "
                "| Q/ESC = Exit"
            ),
            20,
            200,
        )

    return display


# ============================================================
# SNAPSHOT
# ============================================================

def process_frame(
    *,
    pipeline,
    frame,
    session_data,
    baseline_data,
    threshold_config,
):
    timestamp = (
        time.perf_counter()
    )

    detection_result = (
        pipeline.process_frame(
            frame,
            timestamp=timestamp,
        )
    )

    snapshot = (
        build_session_monitoring_snapshot(
            session=session_data,
            baseline=baseline_data,
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

    return (
        timestamp,
        detection_result,
        snapshot,
        gate_result,
    )


# ============================================================
# BUILD RESULT ROW
# ============================================================

def build_row(
    *,
    phase_id,
    phase_title,
    phase_type,
    target_feature,
    frame_index,
    elapsed,
    timestamp,
    snapshot,
    gate_result,
):
    context = (
        snapshot.get(
            "context",
            {},
        )
    )

    row = {
        "recorded_at": (
            datetime.now()
            .isoformat()
        ),

        "pipeline_timestamp": (
            timestamp
        ),

        "phase_id": (
            phase_id
        ),

        "phase_title": (
            phase_title
        ),

        "phase_type": (
            phase_type
        ),

        "target_feature": (
            target_feature
            or ""
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

        "context_reason": (
            context.get(
                "reason"
            )
        ),

        "overall_status": (
            gate_result.get(
                "overall_status"
            )
        ),
    }

    for feature_name in (
        POSTURE_FEATURE_ORDER
    ):
        snapshot_feature = (
            snapshot.get(
                "features",
                {},
            ).get(
                feature_name,
                {},
            )
        )

        gate_feature = (
            gate_result.get(
                "features",
                {},
            ).get(
                feature_name,
                {},
            )
        )

        row[
            f"{feature_name}_baseline"
        ] = finite_number(
            snapshot_feature.get(
                "baseline"
            )
        )

        row[
            f"{feature_name}_current"
        ] = finite_number(
            snapshot_feature.get(
                "current"
            )
        )

        row[
            f"{feature_name}_delta"
        ] = finite_number(
            snapshot_feature.get(
                "delta"
            )
        )

        row[
            f"{feature_name}_threshold"
        ] = finite_number(
            gate_feature.get(
                "threshold"
            )
        )

        row[
            f"{feature_name}_status"
        ] = gate_feature.get(
            "status"
        )

        row[
            f"{feature_name}_reason"
        ] = gate_feature.get(
            "reason"
        )

    return row


# ============================================================
# USER READY
# ============================================================

def wait_until_ready(
    *,
    camera,
    pipeline,
    session_data,
    baseline_data,
    threshold_config,
    title,
    instruction,
    key_char,
):
    print()
    print(
        "=" * 100
    )

    print(
        title
    )

    print(
        instruction
    )

    print(
        f"Press {key_char.upper()} "
        "when ready."
    )

    print(
        "=" * 100
    )

    wanted_keys = (
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

        (
            _,
            _,
            snapshot,
            gate_result,
        ) = process_frame(
            pipeline=pipeline,
            frame=frame,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
        )

        display = draw_gate_display(
            frame,

            title=title,

            instruction=instruction,

            snapshot=snapshot,

            gate_result=gate_result,

            extra_text=(
                f"Press "
                f"{key_char.upper()} "
                "when ready"
            ),
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

        if key in wanted_keys:
            return


# ============================================================
# CAPTURE FIXED PHASE
# ============================================================

def capture_fixed_phase(
    *,
    camera,
    pipeline,
    session_data,
    baseline_data,
    threshold_config,
    phase_id,
    phase_title,
    phase_type,
    target_feature,
    instruction,
    duration_seconds,
):
    rows = []

    started_at = (
        time.perf_counter()
    )

    frame_index = 0

    print()
    print(
        "-" * 100
    )

    print(
        f"CAPTURE STARTED: "
        f"{phase_title}"
    )

    print(
        "-" * 100
    )

    while True:
        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        frame_index += 1

        (
            timestamp,
            _,
            snapshot,
            gate_result,
        ) = process_frame(
            pipeline=pipeline,
            frame=frame,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
        )

        elapsed = (
            time.perf_counter()
            -
            started_at
        )

        rows.append(
            build_row(
                phase_id=(
                    phase_id
                ),

                phase_title=(
                    phase_title
                ),

                phase_type=(
                    phase_type
                ),

                target_feature=(
                    target_feature
                ),

                frame_index=(
                    frame_index
                ),

                elapsed=(
                    elapsed
                ),

                timestamp=(
                    timestamp
                ),

                snapshot=(
                    snapshot
                ),

                gate_result=(
                    gate_result
                ),
            )
        )

        display = draw_gate_display(
            frame,

            title=phase_title,

            instruction=instruction,

            snapshot=snapshot,

            gate_result=gate_result,

            elapsed=elapsed,

            duration=duration_seconds,
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
        f"CAPTURE COMPLETE: "
        f"{phase_title}"
    )

    return rows


# ============================================================
# FIXED PHASE ANALYSIS
# ============================================================

def analyze_fixed_phase(
    step,
    rows,
):
    total = len(
        rows
    )

    result = {
        "id": (
            step[
                "id"
            ]
        ),

        "title": (
            step[
                "title"
            ]
        ),

        "test_type": (
            step[
                "test_type"
            ]
        ),

        "target_feature": (
            step.get(
                "target_feature"
            )
        ),

        "frames": (
            total
        ),

        "passed": False,

        "matched_frames": 0,

        "match_rate_percent": 0.0,

        "status_counts": {},
    }

    if (
        total
        < MIN_CAPTURE_FRAMES
    ):
        result[
            "failure_reason"
        ] = (
            "INSUFFICIENT_CAPTURE_FRAMES"
        )

        return result

    test_type = (
        step[
            "test_type"
        ]
    )

    # ========================================================
    # STABLE
    # ========================================================

    if test_type == "stable":

        statuses = [
            row.get(
                "overall_status"
            )
            for row
            in rows
        ]

        counts = Counter(
            statuses
        )

        stable_frames = (
            counts.get(
                STATUS_STABLE,
                0,
            )
        )

        rate = (
            stable_frames
            /
            total
        )

        result[
            "expected_status"
        ] = (
            STATUS_STABLE
        )

        result[
            "matched_frames"
        ] = (
            stable_frames
        )

        result[
            "match_rate_percent"
        ] = percentage(
            stable_frames,
            total,
        )

        result[
            "status_counts"
        ] = dict(
            counts
        )

        result[
            "passed"
        ] = (
            rate
            >= STABLE_PASS_RATE
        )

        if not result[
            "passed"
        ]:
            result[
                "failure_reason"
            ] = (
                "STABLE_RATE_BELOW_REQUIRED"
            )

        return result

    # ========================================================
    # CHANGED
    # ========================================================

    if test_type == "changed":

        target_feature = (
            step[
                "target_feature"
            ]
        )

        status_field = (
            f"{target_feature}_status"
        )

        statuses = [
            row.get(
                status_field
            )
            for row
            in rows
        ]

        counts = Counter(
            statuses
        )

        stable_frames = (
            counts.get(
                STATUS_STABLE,
                0,
            )
        )

        changed_frames = (
            counts.get(
                STATUS_CHANGED,
                0,
            )
        )

        evaluable_frames = (
            stable_frames
            +
            changed_frames
        )

        result[
            "expected_status"
        ] = (
            STATUS_CHANGED
        )

        result[
            "status_counts"
        ] = dict(
            counts
        )

        result[
            "evaluable_frames"
        ] = (
            evaluable_frames
        )

        result[
            "matched_frames"
        ] = (
            changed_frames
        )

        if (
            evaluable_frames
            <= 0
        ):
            result[
                "failure_reason"
            ] = (
                "NO_EVALUABLE_TARGET_FRAMES"
            )

            return result

        rate = (
            changed_frames
            /
            evaluable_frames
        )

        result[
            "match_rate_percent"
        ] = percentage(
            changed_frames,
            evaluable_frames,
        )

        result[
            "passed"
        ] = (
            rate
            >= CHANGED_PASS_RATE
        )

        if not result[
            "passed"
        ]:
            result[
                "failure_reason"
            ] = (
                "CHANGED_RATE_BELOW_REQUIRED"
            )

        return result

    # ========================================================
    # INVALID
    # ========================================================

    if test_type == "invalid":

        statuses = [
            row.get(
                "overall_status"
            )
            for row
            in rows
        ]

        counts = Counter(
            statuses
        )

        not_evaluated = (
            counts.get(
                STATUS_NOT_EVALUATED,
                0,
            )
        )

        rate = (
            not_evaluated
            /
            total
        )

        result[
            "expected_status"
        ] = (
            STATUS_NOT_EVALUATED
        )

        result[
            "matched_frames"
        ] = (
            not_evaluated
        )

        result[
            "match_rate_percent"
        ] = percentage(
            not_evaluated,
            total,
        )

        result[
            "status_counts"
        ] = dict(
            counts
        )

        result[
            "passed"
        ] = (
            rate
            >= NOT_EVALUATED_PASS_RATE
        )

        if not result[
            "passed"
        ]:
            result[
                "failure_reason"
            ] = (
                "NOT_EVALUATED_RATE_BELOW_REQUIRED"
            )

        return result

    result[
        "failure_reason"
    ] = (
        "UNKNOWN_TEST_TYPE"
    )

    return result


# ============================================================
# RECOVERY
#
# IMPORTANT:
#
# บันทึกทุก frame ตั้งแต่ผู้ใช้กดเริ่ม Recovery
#
# ไม่รอจน STABLE ก่อนแล้วค่อย record
#
# Recovery succeeds when TARGET FEATURE is STABLE
# continuously >= 1.5 sec.
# ============================================================

def capture_recovery(
    *,
    camera,
    pipeline,
    session_data,
    baseline_data,
    threshold_config,
    recovery_config,
):
    rows = []

    target_feature = (
        recovery_config[
            "target_feature"
        ]
    )

    status_field = (
        f"{target_feature}_status"
    )

    started_at = (
        time.perf_counter()
    )

    stable_started_at = None

    first_stable_time = None

    confirmed_at = None

    frame_index = 0

    print()
    print(
        "=" * 100
    )

    print(
        recovery_config[
            "title"
        ]
    )

    print(
        recovery_config[
            "instruction"
        ]
    )

    print(
        "Recording ALL recovery frames now."
    )

    print(
        "Do not adjust your posture to make "
        "the Gate pass."
    )

    print(
        "=" * 100
    )

    while True:
        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        frame_index += 1

        (
            timestamp,
            _,
            snapshot,
            gate_result,
        ) = process_frame(
            pipeline=pipeline,
            frame=frame,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
        )

        elapsed = (
            time.perf_counter()
            -
            started_at
        )

        row = build_row(
            phase_id=(
                recovery_config[
                    "id"
                ]
            ),

            phase_title=(
                recovery_config[
                    "title"
                ]
            ),

            phase_type=(
                "recovery"
            ),

            target_feature=(
                target_feature
            ),

            frame_index=(
                frame_index
            ),

            elapsed=(
                elapsed
            ),

            timestamp=(
                timestamp
            ),

            snapshot=(
                snapshot
            ),

            gate_result=(
                gate_result
            ),
        )

        rows.append(
            row
        )

        target_status = (
            row.get(
                status_field
            )
        )

        # ----------------------------------------------------
        # Continuous STABLE tracking
        # ----------------------------------------------------

        if (
            target_status
            == STATUS_STABLE
        ):
            if (
                first_stable_time
                is None
            ):
                first_stable_time = (
                    elapsed
                )

            if (
                stable_started_at
                is None
            ):
                stable_started_at = (
                    elapsed
                )

            stable_duration = (
                elapsed
                -
                stable_started_at
            )

            if (
                stable_duration
                >=
                RECOVERY_REQUIRED_STABLE_SECONDS
            ):
                confirmed_at = (
                    elapsed
                )

        else:
            stable_started_at = (
                None
            )

            stable_duration = 0.0

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        if (
            stable_started_at
            is None
        ):
            current_stable_duration = (
                0.0
            )

        else:
            current_stable_duration = (
                elapsed
                -
                stable_started_at
            )

        display = draw_gate_display(
            frame,

            title=(
                recovery_config[
                    "title"
                ]
            ),

            instruction=(
                recovery_config[
                    "instruction"
                ]
            ),

            snapshot=snapshot,

            gate_result=gate_result,

            elapsed=elapsed,

            duration=(
                RECOVERY_TIMEOUT_SECONDS
            ),

            extra_text=(
                f"{POSTURE_FEATURES[target_feature]['label']} "
                f"continuous STABLE: "
                f"{current_stable_duration:.2f} / "
                f"{RECOVERY_REQUIRED_STABLE_SECONDS:.2f}s"
            ),
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

        # ----------------------------------------------------
        # Recovery confirmed
        # ----------------------------------------------------

        if (
            confirmed_at
            is not None
        ):
            break

        # ----------------------------------------------------
        # Timeout
        # ----------------------------------------------------

        if (
            elapsed
            >=
            RECOVERY_TIMEOUT_SECONDS
        ):
            break

    statuses = [
        row.get(
            status_field
        )
        for row
        in rows
    ]

    counts = Counter(
        statuses
    )

    stable_count = (
        counts.get(
            STATUS_STABLE,
            0,
        )
    )

    changed_count = (
        counts.get(
            STATUS_CHANGED,
            0,
        )
    )

    evaluable_count = (
        stable_count
        +
        changed_count
    )

    result = {
        "id": (
            recovery_config[
                "id"
            ]
        ),

        "title": (
            recovery_config[
                "title"
            ]
        ),

        "test_type": (
            "recovery"
        ),

        "target_feature": (
            target_feature
        ),

        "frames": (
            len(
                rows
            )
        ),

        "status_counts": (
            dict(
                counts
            )
        ),

        "stable_rate_percent": (
            percentage(
                stable_count,
                evaluable_count,
            )
        ),

        "changed_rate_percent": (
            percentage(
                changed_count,
                evaluable_count,
            )
        ),

        "first_stable_time_seconds": (
            first_stable_time
        ),

        "required_continuous_stable_seconds": (
            RECOVERY_REQUIRED_STABLE_SECONDS
        ),

        "confirmed_recovery_at_seconds": (
            confirmed_at
        ),

        "timeout_seconds": (
            RECOVERY_TIMEOUT_SECONDS
        ),

        "passed": (
            confirmed_at
            is not None
        ),
    }

    if not result[
        "passed"
    ]:
        result[
            "failure_reason"
        ] = (
            "RECOVERY_NOT_CONFIRMED_BEFORE_TIMEOUT"
        )

    print()
    print(
        "-" * 100
    )

    print(
        f"RECOVERY RESULT: "
        f"{recovery_config['title']}"
    )

    print(
        f"Frames              : "
        f"{result['frames']}"
    )

    print(
        f"Status Count        : "
        f"{result['status_counts']}"
    )

    print(
        f"First STABLE        : "
        f"{result['first_stable_time_seconds']}"
    )

    print(
        f"Recovery Confirmed  : "
        f"{result['confirmed_recovery_at_seconds']}"
    )

    print(
        "Result              : "
        + (
            "PASS"
            if result[
                "passed"
            ]
            else "FAIL"
        )
    )

    print(
        "-" * 100
    )

    return (
        rows,
        result,
    )


# ============================================================
# PRINT STEP RESULT
# ============================================================

def print_step_result(
    result,
):
    print()
    print(
        "-" * 100
    )

    print(
        f"STEP COMPLETE: "
        f"{result['title']}"
    )

    print(
        f"Frames       : "
        f"{result['frames']}"
    )

    print(
        f"Expected     : "
        f"{result.get('expected_status')}"
    )

    print(
        f"Match Rate   : "
        f"{result.get('match_rate_percent', 0.0):.2f}%"
    )

    print(
        f"Status Count : "
        f"{result.get('status_counts')}"
    )

    print(
        "Result       : "
        + (
            "PASS"
            if result[
                "passed"
            ]
            else "FAIL"
        )
    )

    if not result[
        "passed"
    ]:
        print(
            f"Reason       : "
            f"{result.get('failure_reason')}"
        )

    print(
        "-" * 100
    )


# ============================================================
# FRESH BASELINE COLLECTION
# ============================================================

def collect_fresh_baseline(
    *,
    camera,
    pipeline,
):
    collector = (
        create_collector()
    )

    started = False

    print()
    print(
        "=" * 100
    )

    print(
        "PHASE 1 - FRESH PERSONAL BASELINE"
    )

    print(
        "=" * 100
    )

    print(
        "Sit naturally in the posture you want "
        "to use as this Session Calibration Snapshot."
    )

    print(
        "Relax shoulders and look forward."
    )

    print(
        "Do NOT force the posture to zero degrees."
    )

    print()

    print(
        "S = Start Calibration"
    )

    print(
        "R = Restart"
    )

    print(
        "Y = Confirm"
    )

    print(
        "Q / ESC = Exit"
    )

    print(
        "=" * 100
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

        detection_result = (
            pipeline.process_frame(
                frame,
                timestamp=timestamp,
            )
        )

        if (
            started
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

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        if key in (
            ord("s"),
            ord("S"),
        ):
            collector = (
                create_collector()
            )

            pipeline.reset_context()

            started = True

            print()
            print(
                "CALIBRATION STARTED"
            )

            continue

        # ----------------------------------------------------
        # RESTART
        # ----------------------------------------------------

        if key in (
            ord("r"),
            ord("R"),
        ):
            collector = (
                create_collector()
            )

            pipeline.reset_context()

            started = True

            print()
            print(
                "CALIBRATION RESTARTED"
            )

            continue

        # ----------------------------------------------------
        # CONFIRM
        # ----------------------------------------------------

        if key in (
            ord("y"),
            ord("Y"),
        ):
            current = (
                collector.get_status()
            )

            if not (
                collector.completed
                and
                current.get(
                    "status"
                )
                ==
                pb.BASELINE_NEED_CONFIRMATION
            ):
                print(
                    "Confirm ignored: "
                    "Baseline is not ready."
                )

                continue

            collector.confirm()

            usable = (
                collector.get_usable_baseline()
            )

            print()
            print(
                "=" * 100
            )

            print(
                "FRESH PERSONAL BASELINE CONFIRMED"
            )

            print(
                "=" * 100
            )

            for (
                name,
                value,
            ) in usable.items():

                print(
                    f"{name:<24}: "
                    f"{value}"
                )

            print(
                "=" * 100
            )

            return usable


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(
    *,
    usable_baseline,
    threshold_config,
    all_rows,
    step_results,
    recovery_results,
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

    frame_csv_path = (
        RESULTS_DIR
        /
        (
            "e2e_gate_v3_frames_"
            f"{stamp}.csv"
        )
    )

    summary_csv_path = (
        RESULTS_DIR
        /
        (
            "e2e_gate_v3_summary_"
            f"{stamp}.csv"
        )
    )

    summary_json_path = (
        RESULTS_DIR
        /
        (
            "e2e_gate_v3_summary_"
            f"{stamp}.json"
        )
    )

    # ========================================================
    # FRAME CSV
    # ========================================================

    if all_rows:

        with frame_csv_path.open(
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
    # OVERALL RESULT
    #
    # ต้องผ่าน:
    # - 8 Gate Steps
    # - 3 Recovery Validations
    # ========================================================

    gate_passed = all(
        result.get(
            "passed"
        )
        is True
        for result in step_results
    )

    recovery_passed = all(
        result.get(
            "passed"
        )
        is True
        for result in recovery_results
    )

    overall_passed = (
        gate_passed
        and
        recovery_passed
    )

    # ========================================================
    # SUMMARY CSV
    # ========================================================

    summary_rows = []

    for result in (
        step_results
        +
        recovery_results
    ):

        summary_rows.append({
            "id": (
                result.get(
                    "id"
                )
            ),

            "title": (
                result.get(
                    "title"
                )
            ),

            "test_type": (
                result.get(
                    "test_type"
                )
            ),

            "target_feature": (
                result.get(
                    "target_feature"
                )
            ),

            "frames": (
                result.get(
                    "frames"
                )
            ),

            "expected_status": (
                result.get(
                    "expected_status"
                )
            ),

            "match_rate_percent": (
                result.get(
                    "match_rate_percent"
                )
            ),

            "first_stable_time_seconds": (
                result.get(
                    "first_stable_time_seconds"
                )
            ),

            "confirmed_recovery_at_seconds": (
                result.get(
                    "confirmed_recovery_at_seconds"
                )
            ),

            "passed": (
                result.get(
                    "passed"
                )
            ),

            "failure_reason": (
                result.get(
                    "failure_reason",
                    ""
                )
            ),

            "status_counts": json.dumps(
                result.get(
                    "status_counts",
                    {},
                ),
                ensure_ascii=False,
            ),
        })

    if summary_rows:

        with summary_csv_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(
                    summary_rows[
                        0
                    ].keys()
                ),
            )

            writer.writeheader()

            writer.writerows(
                summary_rows
            )

    # ========================================================
    # JSON
    # ========================================================

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

        "threshold_config": (
            threshold_config
        ),

        "configuration": {
            "capture_seconds": (
                CAPTURE_SECONDS
            ),

            "recovery_timeout_seconds": (
                RECOVERY_TIMEOUT_SECONDS
            ),

            "recovery_required_stable_seconds": (
                RECOVERY_REQUIRED_STABLE_SECONDS
            ),

            "minimum_capture_frames": (
                MIN_CAPTURE_FRAMES
            ),

            "stable_pass_rate": (
                STABLE_PASS_RATE
            ),

            "changed_pass_rate": (
                CHANGED_PASS_RATE
            ),

            "not_evaluated_pass_rate": (
                NOT_EVALUATED_PASS_RATE
            ),
        },

        "gate_steps": (
            step_results
        ),

        "recovery_validations": (
            recovery_results
        ),

        "gate_steps_passed": (
            gate_passed
        ),

        "recovery_validations_passed": (
            recovery_passed
        ),

        "overall_passed": (
            overall_passed
        ),

        "interpretation": {
            "stable_means_safe": False,

            "changed_means_risk": False,

            "recovery_is_separate_from_stable_hold": True,

            "gate_core_modified": False,

            "thresholds_modified": False,
        },
    }

    with summary_json_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # ========================================================
    # PRINT FINAL
    # ========================================================

    print()
    print(
        "=" * 110
    )

    print(
        "POSTGUARD - E2E MEASUREMENT CHANGE "
        "GATE v3 RESULT"
    )

    print(
        "=" * 110
    )

    print(
        "DATABASE USED : NO"
    )

    print()

    print(
        "GATE STEPS"
    )

    print(
        "-" * 110
    )

    for result in (
        step_results
    ):
        print(
            (
                "[PASS] "
                if result[
                    "passed"
                ]
                else "[FAIL] "
            )
            +
            result[
                "title"
            ]
        )

        print(
            f"    Frames       : "
            f"{result['frames']}"
        )

        print(
            f"    Expected     : "
            f"{result.get('expected_status')}"
        )

        print(
            f"    Match Rate   : "
            f"{result.get('match_rate_percent', 0.0):.2f}%"
        )

        print(
            f"    Status Count : "
            f"{result.get('status_counts')}"
        )

        if not result[
            "passed"
        ]:
            print(
                f"    Reason       : "
                f"{result.get('failure_reason')}"
            )

        print()

    print(
        "RECOVERY VALIDATIONS"
    )

    print(
        "-" * 110
    )

    for result in (
        recovery_results
    ):
        print(
            (
                "[PASS] "
                if result[
                    "passed"
                ]
                else "[FAIL] "
            )
            +
            result[
                "title"
            ]
        )

        print(
            f"    Frames              : "
            f"{result['frames']}"
        )

        print(
            f"    First STABLE        : "
            f"{result.get('first_stable_time_seconds')}"
        )

        print(
            f"    Recovery Confirmed  : "
            f"{result.get('confirmed_recovery_at_seconds')}"
        )

        print(
            f"    Status Count        : "
            f"{result.get('status_counts')}"
        )

        if not result[
            "passed"
        ]:
            print(
                f"    Reason              : "
                f"{result.get('failure_reason')}"
            )

        print()

    print(
        "-" * 110
    )

    print(
        f"8 Gate Steps Passed     : "
        f"{gate_passed}"
    )

    print(
        f"3 Recoveries Passed     : "
        f"{recovery_passed}"
    )

    print()

    if overall_passed:

        print(
            "FINAL RESULT: PASSED"
        )

        print(
            "Measurement-Change Gate v1 "
            "is ready to FREEZE based on "
            "this E2E protocol."
        )

    else:

        print(
            "FINAL RESULT: NOT PASSED"
        )

        print(
            "Do NOT freeze Measurement-Change Gate v1."
        )

    print(
        "-" * 110
    )

    print(
        f"Frame CSV   : "
        f"{frame_csv_path}"
    )

    print(
        f"Summary CSV : "
        f"{summary_csv_path}"
    )

    print(
        f"Summary JSON: "
        f"{summary_json_path}"
    )

    print(
        "=" * 110
    )

    return summary


# ============================================================
# MAIN
# ============================================================

def main():
    args = parse_args()

    # ========================================================
    # THRESHOLD CONFIG
    # ========================================================

    if not (
        THRESHOLD_CONFIG_PATH.exists()
    ):
        raise RuntimeError(
            "Threshold config not found:\n"
            f"{THRESHOLD_CONFIG_PATH}"
        )

    threshold_config = (
        load_threshold_config(
            THRESHOLD_CONFIG_PATH
        )
    )

    print()
    print(
        "=" * 110
    )

    print(
        "POSTGUARD - E2E FRESH BASELINE "
        "MEASUREMENT CHANGE GATE v3"
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
        "PROTOCOL"
    )

    print(
        "Fresh Baseline"
    )

    print(
        " -> Initial Stable"
    )

    print(
        " -> Shoulder Changed"
    )

    print(
        " -> Shoulder Recovery"
    )

    print(
        " -> Stable Hold"
    )

    print(
        " -> Neck Lateral Changed"
    )

    print(
        " -> Neck Lateral Recovery"
    )

    print(
        " -> Stable Hold"
    )

    print(
        " -> Neck Flexion Changed"
    )

    print(
        " -> Neck Flexion Recovery"
    )

    print(
        " -> Stable Hold"
    )

    print(
        " -> Invalid Context"
    )

    print()

    print(
        "IMPORTANT"
    )

    print(
        "- Recovery records ALL frames."
    )

    print(
        "- Recovery and Stable Hold are separate."
    )

    print(
        "- Gate Core is NOT modified."
    )

    print(
        "- Thresholds are NOT modified."
    )

    print(
        "- CHANGED does NOT mean RISK."
    )

    print(
        "- STABLE does NOT mean SAFE."
    )

    print(
        "- Database is NOT used."
    )

    print()

    print(
        "THRESHOLDS"
    )

    for feature_name in (
        POSTURE_FEATURE_ORDER
    ):
        config = (
            threshold_config.get(
                "features",
                {},
            ).get(
                feature_name,
                {},
            )
        )

        print(
            f"  "
            f"{feature_name:<24}"
            f"{config.get('threshold')} "
            f"{config.get('unit')}"
        )

    print(
        "=" * 110
    )

    # ========================================================
    # CAMERA
    # ========================================================

    camera = (
        cv2.VideoCapture(
            args.camera_index
        )
    )

    if not (
        camera.isOpened()
    ):
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

    step_results = []

    recovery_results = []

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
            1280,
            720,
        )

        # ====================================================
        # FRESH BASELINE
        # ====================================================

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

        print()
        print(
            "=" * 110
        )

        print(
            "IN-MEMORY MONITORING CONTRACT READY"
        )

        print(
            "=" * 110
        )

        print(
            f"Shoulder Baseline : "
            f"{baseline_data['shoulder_angle']:+.4f}"
        )

        print(
            f"Lateral Baseline  : "
            f"{baseline_data['lateral_tilt_baseline']:+.4f}"
        )

        print(
            f"Flexion Baseline  : "
            f"{baseline_data['neck_flexion_baseline']:+.4f}"
        )

        print(
            "=" * 110
        )

        # ====================================================
        # STEP 1
        # INITIAL STABLE
        # ====================================================

        step = (
            TEST_STEPS[
                0
            ]
        )

        wait_until_ready(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            title=step["title"],
            instruction=step["instruction"],
            key_char="1",
        )

        rows = capture_fixed_phase(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            phase_id=step["id"],
            phase_title=step["title"],
            phase_type=step["test_type"],
            target_feature=step["target_feature"],
            instruction=step["instruction"],
            duration_seconds=CAPTURE_SECONDS,
        )

        result = analyze_fixed_phase(
            step,
            rows,
        )

        all_rows.extend(
            rows
        )

        step_results.append(
            result
        )

        print_step_result(
            result
        )

        # Initial Stable must pass.
        if not result[
            "passed"
        ]:
            raise RuntimeError(
                "INITIAL_STABLE_FAILED. "
                "Recalibrate and run the test again. "
                "Do not continue to intentional changes."
            )

        # ====================================================
        # STEP 2
        # SHOULDER CHANGED
        # ====================================================

        step = (
            TEST_STEPS[
                1
            ]
        )

        wait_until_ready(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            title=step["title"],
            instruction=step["instruction"],
            key_char="2",
        )

        rows = capture_fixed_phase(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            phase_id=step["id"],
            phase_title=step["title"],
            phase_type=step["test_type"],
            target_feature=step["target_feature"],
            instruction=step["instruction"],
            duration_seconds=CAPTURE_SECONDS,
        )

        result = analyze_fixed_phase(
            step,
            rows,
        )

        all_rows.extend(
            rows
        )

        step_results.append(
            result
        )

        print_step_result(
            result
        )

        # ====================================================
        # SHOULDER RECOVERY
        # ====================================================

        recovery = (
            RECOVERY_PHASES[
                "shoulder_changed"
            ]
        )

        wait_until_ready(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            title=recovery["title"],
            instruction=(
                recovery["instruction"]
                +
                " Release first, then press 3 immediately."
            ),
            key_char="3",
        )

        (
            recovery_rows,
            recovery_result,
        ) = capture_recovery(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            recovery_config=recovery,
        )

        all_rows.extend(
            recovery_rows
        )

        recovery_results.append(
            recovery_result
        )

        # ====================================================
        # STEP 3
        # SHOULDER STABLE HOLD
        #
        # Starts ONLY after Recovery validation finished.
        # ====================================================

        step = (
            TEST_STEPS[
                2
            ]
        )

        if recovery_result[
            "passed"
        ]:

            print()
            print(
                "Shoulder Recovery PASSED."
            )

            print(
                "Starting Stable Hold validation "
                "immediately."
            )

            rows = capture_fixed_phase(
                camera=camera,
                pipeline=pipeline,
                session_data=session_data,
                baseline_data=baseline_data,
                threshold_config=threshold_config,
                phase_id=step["id"],
                phase_title=step["title"],
                phase_type=step["test_type"],
                target_feature=step["target_feature"],
                instruction=step["instruction"],
                duration_seconds=CAPTURE_SECONDS,
            )

        else:

            print()
            print(
                "Shoulder Recovery FAILED."
            )

            print(
                "Stable Hold will still be recorded "
                "for diagnostic evidence."
            )

            rows = capture_fixed_phase(
                camera=camera,
                pipeline=pipeline,
                session_data=session_data,
                baseline_data=baseline_data,
                threshold_config=threshold_config,
                phase_id=step["id"],
                phase_title=step["title"],
                phase_type=step["test_type"],
                target_feature=step["target_feature"],
                instruction=step["instruction"],
                duration_seconds=CAPTURE_SECONDS,
            )

        result = analyze_fixed_phase(
            step,
            rows,
        )

        all_rows.extend(
            rows
        )

        step_results.append(
            result
        )

        print_step_result(
            result
        )

        # ====================================================
        # STEP 4
        # NECK LATERAL CHANGED
        # ====================================================

        step = (
            TEST_STEPS[
                3
            ]
        )

        wait_until_ready(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            title=step["title"],
            instruction=step["instruction"],
            key_char="4",
        )

        rows = capture_fixed_phase(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            phase_id=step["id"],
            phase_title=step["title"],
            phase_type=step["test_type"],
            target_feature=step["target_feature"],
            instruction=step["instruction"],
            duration_seconds=CAPTURE_SECONDS,
        )

        result = analyze_fixed_phase(
            step,
            rows,
        )

        all_rows.extend(
            rows
        )

        step_results.append(
            result
        )

        print_step_result(
            result
        )

        # ====================================================
        # NECK LATERAL RECOVERY
        # ====================================================

        recovery = (
            RECOVERY_PHASES[
                "neck_lateral_changed"
            ]
        )

        wait_until_ready(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            title=recovery["title"],
            instruction=(
                recovery["instruction"]
                +
                " Return first, then press 5 immediately."
            ),
            key_char="5",
        )

        (
            recovery_rows,
            recovery_result,
        ) = capture_recovery(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            recovery_config=recovery,
        )

        all_rows.extend(
            recovery_rows
        )

        recovery_results.append(
            recovery_result
        )

        # ====================================================
        # STEP 5
        # LATERAL STABLE HOLD
        # ====================================================

        step = (
            TEST_STEPS[
                4
            ]
        )

        rows = capture_fixed_phase(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            phase_id=step["id"],
            phase_title=step["title"],
            phase_type=step["test_type"],
            target_feature=step["target_feature"],
            instruction=step["instruction"],
            duration_seconds=CAPTURE_SECONDS,
        )

        result = analyze_fixed_phase(
            step,
            rows,
        )

        all_rows.extend(
            rows
        )

        step_results.append(
            result
        )

        print_step_result(
            result
        )

        # ====================================================
        # STEP 6
        # NECK FLEXION CHANGED
        # ====================================================

        step = (
            TEST_STEPS[
                5
            ]
        )

        wait_until_ready(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            title=step["title"],
            instruction=step["instruction"],
            key_char="6",
        )

        rows = capture_fixed_phase(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            phase_id=step["id"],
            phase_title=step["title"],
            phase_type=step["test_type"],
            target_feature=step["target_feature"],
            instruction=step["instruction"],
            duration_seconds=CAPTURE_SECONDS,
        )

        result = analyze_fixed_phase(
            step,
            rows,
        )

        all_rows.extend(
            rows
        )

        step_results.append(
            result
        )

        print_step_result(
            result
        )

        # ====================================================
        # NECK FLEXION RECOVERY
        # ====================================================

        recovery = (
            RECOVERY_PHASES[
                "neck_flexion_changed"
            ]
        )

        wait_until_ready(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            title=recovery["title"],
            instruction=(
                recovery["instruction"]
                +
                " Return first, then press 7 immediately."
            ),
            key_char="7",
        )

        (
            recovery_rows,
            recovery_result,
        ) = capture_recovery(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            recovery_config=recovery,
        )

        all_rows.extend(
            recovery_rows
        )

        recovery_results.append(
            recovery_result
        )

        # ====================================================
        # STEP 7
        # FLEXION STABLE HOLD
        # ====================================================

        step = (
            TEST_STEPS[
                6
            ]
        )

        rows = capture_fixed_phase(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            phase_id=step["id"],
            phase_title=step["title"],
            phase_type=step["test_type"],
            target_feature=step["target_feature"],
            instruction=step["instruction"],
            duration_seconds=CAPTURE_SECONDS,
        )

        result = analyze_fixed_phase(
            step,
            rows,
        )

        all_rows.extend(
            rows
        )

        step_results.append(
            result
        )

        print_step_result(
            result
        )

        # ====================================================
        # STEP 8
        # INVALID CONTEXT
        # ====================================================

        step = (
            TEST_STEPS[
                7
            ]
        )

        wait_until_ready(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            title=step["title"],
            instruction=step["instruction"],
            key_char="8",
        )

        rows = capture_fixed_phase(
            camera=camera,
            pipeline=pipeline,
            session_data=session_data,
            baseline_data=baseline_data,
            threshold_config=threshold_config,
            phase_id=step["id"],
            phase_title=step["title"],
            phase_type=step["test_type"],
            target_feature=step["target_feature"],
            instruction=step["instruction"],
            duration_seconds=CAPTURE_SECONDS,
        )

        result = analyze_fixed_phase(
            step,
            rows,
        )

        all_rows.extend(
            rows
        )

        step_results.append(
            result
        )

        print_step_result(
            result
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        summary = save_results(
            usable_baseline=(
                usable_baseline
            ),

            threshold_config=(
                threshold_config
            ),

            all_rows=(
                all_rows
            ),

            step_results=(
                step_results
            ),

            recovery_results=(
                recovery_results
            ),
        )

        # ====================================================
        # FINAL CAMERA SCREEN
        # ====================================================

        print()
        print(
            "Press Q / ESC in camera window to exit."
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

            draw_text(
                display,
                "POSTGUARD E2E GATE v3 FINISHED",
                20,
                45,
                WHITE,
                0.68,
                2,
            )

            final_passed = (
                summary.get(
                    "overall_passed"
                )
            )

            draw_text(
                display,
                (
                    "FINAL RESULT: "
                    +
                    (
                        "PASSED"
                        if final_passed
                        else "NOT PASSED"
                    )
                ),
                20,
                90,
                (
                    GREEN
                    if final_passed
                    else RED
                ),
                0.72,
                2,
            )

            draw_text(
                display,
                (
                    "Gate v1: "
                    +
                    (
                        "READY TO FREEZE"
                        if final_passed
                        else "DO NOT FREEZE"
                    )
                ),
                20,
                135,
                YELLOW,
                0.60,
                2,
            )

            draw_text(
                display,
                "Q / ESC = Exit",
                20,
                185,
                WHITE,
                0.50,
                1,
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
            "E2E test interrupted."
        )

    finally:

        if pipeline is not None:
            pipeline.close()

        camera.release()

        cv2.destroyAllWindows()

        print()
        print(
            "=" * 100
        )

        print(
            "POSTGUARD E2E GATE v3 RUNTIME CLOSED"
        )

        print(
            "=" * 100
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
            "=" * 100
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()