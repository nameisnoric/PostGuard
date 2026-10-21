from __future__ import annotations

import csv
import json
import math
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)

from camera_card.posture_assessment.current_posture_assessment import (
    assess_current_posture,
)

from camera_card.temporal_tracking.temporal_posture_tracker import (
    TEMPORAL_ACTIVE,
    TEMPORAL_NEUTRAL,
    TEMPORAL_NOT_EVALUATED,
    TemporalPostureTracker,
)


# ============================================================
# CONFIG
# ============================================================

RUNNER_VERSION = "1.0-temporal-real-camera"

CAMERA_ID = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

WINDOW_NAME = (
    "PostGuard - Temporal Tracking Real Camera Validation"
)

RESULTS_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "temporal_tracking_real_camera"
)

MIN_VALID_FRAMES = 30

# Real-camera validation tolerance.
#
# These are TEST PASS criteria only.
# They are NOT posture/risk thresholds.
ACTIVE_PASS_RATE = 0.70
NEUTRAL_PASS_RATE = 0.80
NOT_EVALUATED_PASS_RATE = 0.70

# For a 5-second held pose, we expect at least ~3 sec
# of uninterrupted active tracking.
MIN_HOLD_DURATION_SECONDS = 3.0

# First active frame after reset should begin close to 0.
MAX_RESTART_DURATION_SECONDS = 0.50


# ============================================================
# TEST STEPS
# ============================================================

TEST_STEPS = [
    {
        "id": "neutral_initial",
        "title": "Initial Neutral",
        "duration": 3.0,
        "instruction": (
            "Sit naturally. Keep head straight and relax shoulders."
        ),
        "expected": "NEUTRAL",
    },

    {
        "id": "neck_left_hold_1",
        "title": "Neck Left Hold #1",
        "duration": 5.0,
        "instruction": (
            "Tilt HEAD LEFT clearly and naturally. HOLD."
        ),
        "expected": "ACTIVE_LEFT",
    },

    {
        "id": "neutral_reset",
        "title": "Neutral Reset",
        "duration": 3.0,
        "instruction": (
            "Return head to neutral naturally. HOLD."
        ),
        "expected": "NEUTRAL",
    },

    {
        "id": "neck_left_hold_2",
        "title": "Neck Left Hold #2",
        "duration": 5.0,
        "instruction": (
            "Tilt HEAD LEFT clearly and naturally again. HOLD."
        ),
        "expected": "ACTIVE_LEFT_RESTART",
    },

    {
        "id": "invalid_context",
        "title": "Invalid Context Reset",
        "duration": 3.0,
        "instruction": (
            "Move clearly out of usable camera context. HOLD."
        ),
        "expected": "NOT_EVALUATED",
    },

    {
        "id": "neck_left_hold_after_invalid",
        "title": "Neck Left After Invalid Context",
        "duration": 5.0,
        "instruction": (
            "Return to camera, wait until usable, "
            "then tilt HEAD LEFT clearly and naturally. HOLD."
        ),
        "expected": "ACTIVE_LEFT_RESTART",
    },
]


# ============================================================
# HELPERS
# ============================================================

def finite_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if not isinstance(
        value,
        (int, float),
    ):
        return None

    number = float(value)

    if not math.isfinite(number):
        return None

    return number


def percent(
    numerator: int,
    denominator: int,
) -> float:

    if denominator <= 0:
        return 0.0

    return (
        float(numerator)
        /
        float(denominator)
        *
        100.0
    )


# ============================================================
# DISPLAY
# ============================================================

def put_text(
    frame,
    text,
    y,
    color=(255, 255, 255),
    scale=0.55,
):

    cv2.putText(
        frame,
        str(text),
        (20, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        1,
        cv2.LINE_AA,
    )


def format_number(
    value,
    digits=2,
):

    number = finite_number(
        value
    )

    if number is None:
        return "N/A"

    return (
        f"{number:+.{digits}f}"
    )


def draw_display(
    frame,
    *,
    step,
    assessment,
    temporal,
    capturing,
    elapsed=0.0,
):

    # Calculation remains unmirrored.
    # Mirror display only.
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
                1100,
            ),
            min(
                display.shape[0],
                510,
            ),
        ),
        (0, 0, 0),
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

    neck_assessment = (
        assessment
        .get(
            "features",
            {},
        )
        .get(
            "neck_lateral_tilt",
            {},
        )
    )

    neck_temporal = (
        temporal
        .get(
            "features",
            {},
        )
        .get(
            "neck_lateral_tilt",
            {},
        )
    )

    y = 35

    put_text(
        display,
        "POSTGUARD - TEMPORAL TRACKING REAL CAMERA",
        y,
        scale=0.65,
    )

    y += 40

    put_text(
        display,
        step["title"],
        y,
        color=(0, 255, 255),
        scale=0.62,
    )

    y += 30

    put_text(
        display,
        step["instruction"],
        y,
    )

    y += 40

    put_text(
        display,
        (
            "Assessment Overall: "
            f"{assessment.get('status')}"
        ),
        y,
    )

    y += 32

    put_text(
        display,
        (
            "Neck Angle: "
            f"{format_number(neck_assessment.get('current'))} deg"
        ),
        y,
    )

    y += 32

    put_text(
        display,
        (
            "Neck Classification: "
            f"{neck_assessment.get('status')}"
        ),
        y,
    )

    y += 32

    put_text(
        display,
        (
            "Temporal Overall: "
            f"{temporal.get('status')}"
        ),
        y,
    )

    y += 32

    put_text(
        display,
        (
            "Temporal Neck State: "
            f"{neck_temporal.get('state')}"
        ),
        y,
    )

    y += 32

    put_text(
        display,
        (
            "Temporal Factor: "
            f"{neck_temporal.get('factor')}"
        ),
        y,
    )

    y += 32

    duration = (
        neck_temporal.get(
            "continuous_seconds"
        )
    )

    duration_text = (
        "N/A"
        if duration is None
        else f"{duration:.2f} s"
    )

    put_text(
        display,
        (
            "Continuous Duration: "
            f"{duration_text}"
        ),
        y,
        color=(255, 255, 0),
        scale=0.60,
    )

    y += 45

    if capturing:

        put_text(
            display,
            (
                "CAPTURING: "
                f"{elapsed:.1f} / "
                f"{step['duration']:.1f} s"
            ),
            y,
            color=(0, 255, 0),
            scale=0.60,
        )

    else:

        put_text(
            display,
            "Prepare posture then press S",
            y,
            color=(0, 255, 0),
            scale=0.60,
        )

    return display


# ============================================================
# FRAME RESULT
# ============================================================

def build_row(
    *,
    step,
    frame_index,
    elapsed,
    assessment,
    temporal,
):

    neck_assessment = (
        assessment
        .get(
            "features",
            {},
        )
        .get(
            "neck_lateral_tilt",
            {},
        )
    )

    neck_temporal = (
        temporal
        .get(
            "features",
            {},
        )
        .get(
            "neck_lateral_tilt",
            {},
        )
    )

    shoulder_temporal = (
        temporal
        .get(
            "features",
            {},
        )
        .get(
            "shoulder_tilt",
            {},
        )
    )

    flexion_temporal = (
        temporal
        .get(
            "features",
            {},
        )
        .get(
            "neck_flexion",
            {},
        )
    )

    return {
        "step_id": step["id"],
        "step_title": step["title"],
        "expected": step["expected"],

        "frame_index": frame_index,
        "elapsed_seconds": elapsed,

        "assessment_status": (
            assessment.get(
                "status"
            )
        ),

        "neck_value": (
            neck_assessment.get(
                "current"
            )
        ),

        "neck_classification": (
            neck_assessment.get(
                "status"
            )
        ),

        "neck_assessment_evaluated": (
            neck_assessment.get(
                "evaluated"
            )
        ),

        "temporal_status": (
            temporal.get(
                "status"
            )
        ),

        "neck_temporal_state": (
            neck_temporal.get(
                "state"
            )
        ),

        "neck_temporal_factor": (
            neck_temporal.get(
                "factor"
            )
        ),

        "neck_continuous_seconds": (
            neck_temporal.get(
                "continuous_seconds"
            )
        ),

        "shoulder_temporal_state": (
            shoulder_temporal.get(
                "state"
            )
        ),

        "shoulder_factor": (
            shoulder_temporal.get(
                "factor"
            )
        ),

        "shoulder_continuous_seconds": (
            shoulder_temporal.get(
                "continuous_seconds"
            )
        ),

        "flexion_temporal_state": (
            flexion_temporal.get(
                "state"
            )
        ),

        "flexion_factor": (
            flexion_temporal.get(
                "factor"
            )
        ),

        "flexion_continuous_seconds": (
            flexion_temporal.get(
                "continuous_seconds"
            )
        ),

        "active_factor_count": (
            temporal.get(
                "active_factor_count"
            )
        ),
    }


# ============================================================
# CAPTURE STEP
# ============================================================

def capture_step(
    *,
    camera,
    pipeline,
    tracker,
    step,
):

    print()
    print("=" * 105)

    print(
        step["title"]
    )

    print(
        step["instruction"]
    )

    print()

    print(
        "Prepare posture naturally."
    )

    print(
        "Press S to begin capture."
    )

    print("=" * 105)

    # ========================================================
    # WAIT
    # ========================================================

    while True:

        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        now = (
            time.monotonic()
        )

        detection = (
            pipeline.process_frame(
                frame,
                timestamp=now,
            )
        )

        assessment = (
            assess_current_posture(
                detection
            )
        )

        # IMPORTANT:
        #
        # Do NOT update real tracker while user is preparing.
        #
        # Use a temporary tracker only for display.
        preview_tracker = (
            TemporalPostureTracker()
        )

        temporal = (
            preview_tracker.update(
                assessment,
                now=now,
            )
        )

        display = draw_display(
            frame,
            step=step,
            assessment=assessment,
            temporal=temporal,
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

    start = (
        time.monotonic()
    )

    rows = []

    frame_index = 0

    while True:

        ok, frame = (
            camera.read()
        )

        if not ok:
            continue

        now = (
            time.monotonic()
        )

        elapsed = (
            now
            -
            start
        )

        frame_index += 1

        detection = (
            pipeline.process_frame(
                frame,
                timestamp=now,
            )
        )

        assessment = (
            assess_current_posture(
                detection
            )
        )

        temporal = (
            tracker.update(
                assessment,
                now=now,
            )
        )

        row = build_row(
            step=step,
            frame_index=frame_index,
            elapsed=elapsed,
            assessment=assessment,
            temporal=temporal,
        )

        rows.append(
            row
        )

        display = draw_display(
            frame,
            step=step,
            assessment=assessment,
            temporal=temporal,
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

        if (
            elapsed
            >=
            step["duration"]
        ):
            break

    return rows


# ============================================================
# STEP ANALYSIS
# ============================================================

def analyze_step(
    step,
    rows,
):

    total = len(
        rows
    )

    neck_states = Counter(
        row[
            "neck_temporal_state"
        ]
        for row
        in rows
    )

    factors = Counter(
        row[
            "neck_temporal_factor"
        ]
        for row
        in rows
        if row[
            "neck_temporal_factor"
        ]
        is not None
    )

    durations = [
        value

        for value in (
            finite_number(
                row[
                    "neck_continuous_seconds"
                ]
            )
            for row in rows
        )

        if value is not None
    ]

    active_left_count = sum(
        1
        for row
        in rows
        if (
            row[
                "neck_temporal_state"
            ]
            ==
            TEMPORAL_ACTIVE
            and
            row[
                "neck_temporal_factor"
            ]
            ==
            "TILT_LEFT"
        )
    )

    neutral_count = sum(
        1
        for row
        in rows
        if (
            row[
                "neck_temporal_state"
            ]
            ==
            TEMPORAL_NEUTRAL
        )
    )

    not_evaluated_count = sum(
        1
        for row
        in rows
        if (
            row[
                "neck_temporal_state"
            ]
            ==
            TEMPORAL_NOT_EVALUATED
        )
    )

    active_left_rate = (
        active_left_count
        /
        total
        if total
        else 0.0
    )

    neutral_rate = (
        neutral_count
        /
        total
        if total
        else 0.0
    )

    not_evaluated_rate = (
        not_evaluated_count
        /
        total
        if total
        else 0.0
    )

    max_duration = (
        max(
            durations
        )
        if durations
        else None
    )

    first_active_duration = None

    for row in rows:

        if (
            row[
                "neck_temporal_state"
            ]
            ==
            TEMPORAL_ACTIVE
            and
            row[
                "neck_temporal_factor"
            ]
            ==
            "TILT_LEFT"
        ):

            first_active_duration = (
                finite_number(
                    row[
                        "neck_continuous_seconds"
                    ]
                )
            )

            break

    expected = (
        step[
            "expected"
        ]
    )

    passed = False

    criteria = []

    if expected == "NEUTRAL":

        enough_frames = (
            total
            >=
            MIN_VALID_FRAMES
        )

        enough_neutral = (
            neutral_rate
            >=
            NEUTRAL_PASS_RATE
        )

        passed = (
            enough_frames
            and
            enough_neutral
        )

        criteria = [
            (
                "min_frames",
                enough_frames,
            ),
            (
                "neutral_rate",
                enough_neutral,
            ),
        ]

    elif expected == "ACTIVE_LEFT":

        enough_frames = (
            total
            >=
            MIN_VALID_FRAMES
        )

        enough_active = (
            active_left_rate
            >=
            ACTIVE_PASS_RATE
        )

        enough_duration = (
            max_duration is not None
            and
            max_duration
            >=
            MIN_HOLD_DURATION_SECONDS
        )

        passed = (
            enough_frames
            and
            enough_active
            and
            enough_duration
        )

        criteria = [
            (
                "min_frames",
                enough_frames,
            ),
            (
                "active_left_rate",
                enough_active,
            ),
            (
                "continuous_duration",
                enough_duration,
            ),
        ]

    elif (
        expected
        ==
        "ACTIVE_LEFT_RESTART"
    ):

        enough_frames = (
            total
            >=
            MIN_VALID_FRAMES
        )

        enough_active = (
            active_left_rate
            >=
            ACTIVE_PASS_RATE
        )

        enough_duration = (
            max_duration is not None
            and
            max_duration
            >=
            MIN_HOLD_DURATION_SECONDS
        )

        restarted_near_zero = (
            first_active_duration
            is not None
            and
            first_active_duration
            <=
            MAX_RESTART_DURATION_SECONDS
        )

        passed = (
            enough_frames
            and
            enough_active
            and
            enough_duration
            and
            restarted_near_zero
        )

        criteria = [
            (
                "min_frames",
                enough_frames,
            ),
            (
                "active_left_rate",
                enough_active,
            ),
            (
                "continuous_duration",
                enough_duration,
            ),
            (
                "restart_near_zero",
                restarted_near_zero,
            ),
        ]

    elif (
        expected
        ==
        "NOT_EVALUATED"
    ):

        enough_frames = (
            total
            >=
            MIN_VALID_FRAMES
        )

        enough_invalid = (
            not_evaluated_rate
            >=
            NOT_EVALUATED_PASS_RATE
        )

        passed = (
            enough_frames
            and
            enough_invalid
        )

        criteria = [
            (
                "min_frames",
                enough_frames,
            ),
            (
                "not_evaluated_rate",
                enough_invalid,
            ),
        ]

    return {
        "step_id": (
            step[
                "id"
            ]
        ),

        "title": (
            step[
                "title"
            ]
        ),

        "expected": (
            expected
        ),

        "frames": (
            total
        ),

        "passed": (
            passed
        ),

        "neck_state_counts": (
            dict(
                neck_states
            )
        ),

        "neck_factor_counts": (
            dict(
                factors
            )
        ),

        "active_left_rate_percent": (
            percent(
                active_left_count,
                total,
            )
        ),

        "neutral_rate_percent": (
            percent(
                neutral_count,
                total,
            )
        ),

        "not_evaluated_rate_percent": (
            percent(
                not_evaluated_count,
                total,
            )
        ),

        "first_active_duration": (
            first_active_duration
        ),

        "max_continuous_duration": (
            max_duration
        ),

        "criteria": [
            {
                "name": name,
                "passed": status,
            }

            for (
                name,
                status,
            )
            in criteria
        ],
    }


# ============================================================
# PRINT
# ============================================================

def print_summary(
    result,
):

    print()
    print("-" * 105)

    print(
        result[
            "title"
        ]
    )

    print(
        "Frames          :",
        result[
            "frames"
        ],
    )

    print(
        "Expected        :",
        result[
            "expected"
        ],
    )

    print(
        "Neck States     :",
        result[
            "neck_state_counts"
        ],
    )

    print(
        "Neck Factors    :",
        result[
            "neck_factor_counts"
        ],
    )

    print(
        "ACTIVE LEFT     :",
        (
            f"{result['active_left_rate_percent']:.2f}%"
        ),
    )

    print(
        "NEUTRAL         :",
        (
            f"{result['neutral_rate_percent']:.2f}%"
        ),
    )

    print(
        "NOT EVALUATED   :",
        (
            f"{result['not_evaluated_rate_percent']:.2f}%"
        ),
    )

    print(
        "First Active    :",
        result[
            "first_active_duration"
        ],
    )

    print(
        "Max Duration    :",
        result[
            "max_continuous_duration"
        ],
    )

    print()

    for criterion in (
        result[
            "criteria"
        ]
    ):

        print(
            (
                "[PASS]"
                if criterion[
                    "passed"
                ]
                else
                "[FAIL]"
            ),
            criterion[
                "name"
            ],
        )

    print()

    print(
        "Result          :",
        (
            "PASS"
            if result[
                "passed"
            ]
            else
            "FAIL"
        ),
    )

    print("-" * 105)


# ============================================================
# SAVE
# ============================================================

def save_results(
    *,
    all_rows,
    summaries,
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

    frames_csv = (
        RESULTS_DIR
        /
        f"temporal_frames_{stamp}.csv"
    )

    summary_json = (
        RESULTS_DIR
        /
        f"temporal_summary_{stamp}.json"
    )

    if all_rows:

        with frames_csv.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = (
                csv.DictWriter(
                    file,
                    fieldnames=list(
                        all_rows[0].keys()
                    ),
                )
            )

            writer.writeheader()

            writer.writerows(
                all_rows
            )

    overall_passed = all(
        result[
            "passed"
        ]
        for result
        in summaries
    )

    payload = {
        "runner_version": (
            RUNNER_VERSION
        ),

        "created_at": (
            datetime.now()
            .isoformat()
        ),

        "overall_passed": (
            overall_passed
        ),

        "results": (
            summaries
        ),

        "criteria": {
            "active_pass_rate": (
                ACTIVE_PASS_RATE
            ),

            "neutral_pass_rate": (
                NEUTRAL_PASS_RATE
            ),

            "not_evaluated_pass_rate": (
                NOT_EVALUATED_PASS_RATE
            ),

            "minimum_hold_duration_seconds": (
                MIN_HOLD_DURATION_SECONDS
            ),

            "maximum_restart_duration_seconds": (
                MAX_RESTART_DURATION_SECONDS
            ),
        },

        "notes": {
            "risk_evaluation": False,
            "alert": False,
            "duration_threshold_for_risk": False,
            "baseline_used": False,
            "measurement_change_gate_used": False,

            "purpose": (
                "Validate real-camera temporal runtime "
                "accumulation and reset behavior only."
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
        overall_passed,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 105)

    print(
        "POSTGUARD - TEMPORAL TRACKING REAL CAMERA VALIDATION"
    )

    print("=" * 105)

    print(
        "Runner:",
        RUNNER_VERSION,
    )

    print()

    print(
        "Purpose:"
    )

    print(
        "- validate real runtime duration accumulation"
    )

    print(
        "- validate neutral reset"
    )

    print(
        "- validate invalid-context reset"
    )

    print(
        "- NO risk evaluation"
    )

    print(
        "- NO alert"
    )

    print("=" * 105)

    camera = (
        cv2.VideoCapture(
            CAMERA_ID
        )
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

    tracker = (
        TemporalPostureTracker()
    )

    all_rows = []

    summaries = []

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
            FRAME_WIDTH,
            FRAME_HEIGHT,
        )

        for (
            index,
            step,
        ) in enumerate(
            TEST_STEPS,
            start=1,
        ):

            print()
            print(
                f"TEST {index}/"
                f"{len(TEST_STEPS)}"
            )

            rows = capture_step(
                camera=camera,
                pipeline=pipeline,
                tracker=tracker,
                step=step,
            )

            all_rows.extend(
                rows
            )

            summary = (
                analyze_step(
                    step,
                    rows,
                )
            )

            summaries.append(
                summary
            )

            print_summary(
                summary
            )

        (
            frames_csv,
            summary_json,
            overall_passed,
        ) = save_results(
            all_rows=all_rows,
            summaries=summaries,
        )

        print()
        print("=" * 105)

        print(
            "TEMPORAL TRACKING REAL CAMERA FINAL RESULT"
        )

        print("=" * 105)

        for result in summaries:

            print(
                (
                    "[PASS]"
                    if result[
                        "passed"
                    ]
                    else
                    "[FAIL]"
                ),
                result[
                    "title"
                ],
            )

        print()
        print(
            "OVERALL:",
            (
                "PASSED"
                if overall_passed
                else
                "NOT PASSED"
            ),
        )

        print()
        print(
            "Frames CSV :",
            frames_csv,
        )

        print(
            "Summary    :",
            summary_json,
        )

        print("=" * 105)

    except KeyboardInterrupt:

        print()
        print(
            "Temporal runtime validation interrupted."
        )

    finally:

        if pipeline is not None:

            pipeline.close()

        camera.release()

        cv2.destroyAllWindows()

        print()
        print("=" * 90)

        print(
            "TEMPORAL REAL CAMERA TEST CLOSED"
        )

        print(
            "DetectionPipeline       : CLOSED"
        )

        print(
            "TemporalPostureTracker  : CLOSED"
        )

        print(
            "Camera                  : RELEASED"
        )

        print(
            "Risk                    : NOT USED"
        )

        print(
            "Alert                   : NOT USED"
        )

        print("=" * 90)


if __name__ == "__main__":

    main()