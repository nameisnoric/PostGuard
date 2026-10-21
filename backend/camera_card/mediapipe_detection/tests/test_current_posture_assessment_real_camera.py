from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2


from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)

from camera_card.posture_assessment.current_posture_assessment import (
    ASSESSMENT_NOT_EVALUATED,

    SHOULDER_NEAR_LEVEL,
    LEFT_SHOULDER_HIGH,
    RIGHT_SHOULDER_HIGH,

    NECK_LATERAL_NEUTRAL,
    NECK_TILT_LEFT,
    NECK_TILT_RIGHT,

    NECK_FLEXION_NEUTRAL,
    NECK_FLEXION,
    NECK_EXTENSION,

    STATUS_NOT_EVALUATED,

    assess_current_posture,
)


# ============================================================
# CONFIG
# ============================================================

RUNNER_VERSION = (
    "2.0-directional-crosstalk-validation"
)

WINDOW_NAME = (
    "PostGuard - Current Posture Assessment v1.2"
)

CAMERA_INDEX = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

CAPTURE_SECONDS = 5.0

MIN_EVALUABLE_FRAMES = 30

TARGET_PASS_RATE = 0.80


# ============================================================
# RESULTS
# ============================================================

RESULTS_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "current_posture_assessment_directional"
)


# ============================================================
# TEST CASES
# ============================================================

TEST_CASES = (
    {
        "id": "neutral",

        "title": "Neutral",

        "instruction": (
            "Sit naturally. Relax shoulders. "
            "Keep head straight and look forward."
        ),

        "expected": {
            "shoulder_tilt": SHOULDER_NEAR_LEVEL,
            "neck_lateral_tilt": NECK_LATERAL_NEUTRAL,
            "neck_flexion": NECK_FLEXION_NEUTRAL,
        },
    },

    {
        "id": "left_shoulder_high",

        "title": (
            "Left Shoulder High"
        ),

        "instruction": (
            "Raise LEFT shoulder clearly. "
            "Keep head and torso straight. HOLD."
        ),

        "target_feature": "shoulder_tilt",

        "expected_status": (
            LEFT_SHOULDER_HIGH
        ),

        "cross_talk_feature": (
            "neck_lateral_tilt"
        ),

        "cross_talk_neutral": (
            NECK_LATERAL_NEUTRAL
        ),
    },

    {
        "id": "right_shoulder_high",

        "title": (
            "Right Shoulder High"
        ),

        "instruction": (
            "Raise RIGHT shoulder clearly. "
            "Keep head and torso straight. HOLD."
        ),

        "target_feature": "shoulder_tilt",

        "expected_status": (
            RIGHT_SHOULDER_HIGH
        ),

        "cross_talk_feature": (
            "neck_lateral_tilt"
        ),

        "cross_talk_neutral": (
            NECK_LATERAL_NEUTRAL
        ),
    },

    {
        "id": "neck_tilt_left",

        "title": (
            "Neck Tilt Left"
        ),

        "instruction": (
            "Tilt HEAD LEFT naturally. "
            "Keep shoulders still. HOLD."
        ),

        "target_feature": (
            "neck_lateral_tilt"
        ),

        "expected_status": (
            NECK_TILT_LEFT
        ),

        "cross_talk_feature": (
            "shoulder_tilt"
        ),

        "cross_talk_neutral": (
            SHOULDER_NEAR_LEVEL
        ),
    },

    {
        "id": "neck_tilt_right",

        "title": (
            "Neck Tilt Right"
        ),

        "instruction": (
            "Tilt HEAD RIGHT naturally. "
            "Keep shoulders still. HOLD."
        ),

        "target_feature": (
            "neck_lateral_tilt"
        ),

        "expected_status": (
            NECK_TILT_RIGHT
        ),

        "cross_talk_feature": (
            "shoulder_tilt"
        ),

        "cross_talk_neutral": (
            SHOULDER_NEAR_LEVEL
        ),
    },

    {
        "id": "neck_flexion",

        "title": (
            "Neck Flexion"
        ),

        "instruction": (
            "Lower head / look DOWN naturally. "
            "Keep torso still. HOLD."
        ),

        "target_feature": (
            "neck_flexion"
        ),

        "expected_status": (
            NECK_FLEXION
        ),
    },

    {
        "id": "neck_extension",

        "title": (
            "Neck Extension"
        ),

        "instruction": (
            "Raise head / look UP naturally. "
            "Keep torso still. HOLD."
        ),

        "target_feature": (
            "neck_flexion"
        ),

        "expected_status": (
            NECK_EXTENSION
        ),
    },

    {
        "id": "invalid_context",

        "title": (
            "Invalid Context"
        ),

        "instruction": (
            "Move clearly out of usable camera context "
            "and HOLD."
        ),

        "expected_overall": (
            ASSESSMENT_NOT_EVALUATED
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
    value,
):

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        number
    ):
        return None

    return number


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


def statistics_summary(
    values,
):

    values = [
        float(value)
        for value in values
        if finite(value)
        is not None
    ]

    if not values:

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

    sorted_values = sorted(
        values
    )

    def percentile(
        fraction,
    ):

        if len(
            sorted_values
        ) == 1:

            return (
                sorted_values[
                    0
                ]
            )

        position = (
            (
                len(
                    sorted_values
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

            return (
                sorted_values[
                    lower
                ]
            )

        weight = (
            position
            -
            lower
        )

        return (
            sorted_values[
                lower
            ]
            *
            (
                1.0
                -
                weight
            )
            +
            sorted_values[
                upper
            ]
            *
            weight
        )

    return {
        "count": len(values),

        "mean": (
            statistics.mean(
                values
            )
        ),

        "median": (
            statistics.median(
                values
            )
        ),

        "sd": (
            statistics.stdev(
                values
            )
            if len(values) >= 2
            else 0.0
        ),

        "min": min(values),

        "max": max(values),

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
# DISPLAY
# ============================================================

def threshold_text(
    feature_result,
):

    thresholds = (
        feature_result.get(
            "thresholds",
            {}
        )
    )

    negative = finite(
        thresholds.get(
            "negative_threshold"
        )
    )

    positive = finite(
        thresholds.get(
            "positive_threshold"
        )
    )

    if (
        negative is None
        or positive is None
    ):
        return "N/A"

    return (
        f"{negative:+.1f} / "
        f"{positive:+.1f}"
    )


def draw_display(
    frame,
    detection,
    assessment,
    test_case,
    *,
    mode,
    elapsed=0.0,
):

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
                1050,
                display.shape[1],
            ),
            min(
                500,
                display.shape[0],
            ),
        ),
        BLACK,
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.68,
        display,
        0.32,
        0,
        display,
    )

    y = 35

    put(
        display,
        "POSTGUARD - CURRENT POSTURE ASSESSMENT",
        20,
        y,
        WHITE,
        0.64,
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
        0.60,
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

    y += 34

    context = detection.get(
        "context",
        {},
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

    y += 31

    put(
        display,
        (
            f"Assessment: "
            f"{assessment.get('status')}"
        ),
        20,
        y,
        CYAN,
        0.55,
        2,
    )

    y += 38

    put(
        display,
        "Feature",
        20,
        y,
        WHITE,
        0.48,
        2,
    )

    put(
        display,
        "Value",
        270,
        y,
        WHITE,
        0.48,
        2,
    )

    put(
        display,
        "Assessment",
        420,
        y,
        WHITE,
        0.48,
        2,
    )

    put(
        display,
        "Neg / Pos threshold",
        745,
        y,
        WHITE,
        0.45,
        2,
    )

    y += 31

    features = (
        (
            "shoulder_tilt",
            "Shoulder Tilt",
        ),

        (
            "neck_lateral_tilt",
            "Neck Lateral Tilt",
        ),

        (
            "neck_flexion",
            "Neck Flexion",
        ),
    )

    for (
        feature_name,
        label,
    ) in features:

        row = (
            assessment.get(
                "features",
                {},
            ).get(
                feature_name,
                {},
            )
        )

        value = finite(
            row.get(
                "current"
            )
        )

        if value is None:
            value_text = "N/A"

        else:
            value_text = (
                f"{value:+.2f} deg"
            )

        status = row.get(
            "status",
            "N/A",
        )

        if (
            status
            ==
            STATUS_NOT_EVALUATED
        ):
            color = YELLOW

        elif row.get(
            "is_posture_factor"
        ):
            color = RED

        else:
            color = GREEN

        put(
            display,
            label,
            20,
            y,
        )

        put(
            display,
            value_text,
            270,
            y,
        )

        put(
            display,
            status,
            420,
            y,
            color,
            0.46,
            2,
        )

        put(
            display,
            threshold_text(
                row
            ),
            745,
            y,
        )

        y += 31

    y += 18

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
# CAPTURE
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
        "Prepare posture naturally."
    )

    print(
        "Press S to capture."
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

        assessment = (
            assess_current_posture(
                detection
            )
        )

        display = draw_display(
            frame,
            detection,
            assessment,
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

        timestamp = (
            time.perf_counter()
        )

        frame_index += 1

        detection = (
            pipeline.process_frame(
                frame,
                timestamp=timestamp,
            )
        )

        assessment = (
            assess_current_posture(
                detection
            )
        )

        elapsed = (
            time.perf_counter()
            -
            started
        )

        row = {
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
                detection.get(
                    "context",
                    {},
                ).get(
                    "state"
                )
            ),

            "context_allow": (
                detection.get(
                    "context",
                    {},
                ).get(
                    "allow_posture_evaluation"
                )
            ),

            "assessment_status": (
                assessment.get(
                    "status"
                )
            ),
        }

        for feature_name in (
            "shoulder_tilt",
            "neck_lateral_tilt",
            "neck_flexion",
        ):

            feature = (
                assessment.get(
                    "features",
                    {},
                ).get(
                    feature_name,
                    {},
                )
            )

            row[
                f"{feature_name}_value"
            ] = (
                feature.get(
                    "current"
                )
            )

            row[
                f"{feature_name}_status"
            ] = (
                feature.get(
                    "status"
                )
            )

        rows.append(
            row
        )

        display = draw_display(
            frame,
            detection,
            assessment,
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

        "frames": len(
            rows
        ),

        "passed": False,

        "feature_statistics": {},
    }

    # ========================================================
    # FEATURE STATISTICS
    # ========================================================

    for feature_name in (
        "shoulder_tilt",
        "neck_lateral_tilt",
        "neck_flexion",
    ):

        values = [
            row.get(
                f"{feature_name}_value"
            )
            for row in rows
        ]

        result[
            "feature_statistics"
        ][
            feature_name
        ] = (
            statistics_summary(
                values
            )
        )

    # ========================================================
    # INVALID CONTEXT
    # ========================================================

    if (
        test_case[
            "id"
        ]
        ==
        "invalid_context"
    ):

        statuses = [
            row[
                "assessment_status"
            ]
            for row in rows
        ]

        counts = Counter(
            statuses
        )

        matched = counts.get(
            ASSESSMENT_NOT_EVALUATED,
            0,
        )

        rate = percentage(
            matched,
            len(rows),
        )

        result.update({
            "expected": (
                ASSESSMENT_NOT_EVALUATED
            ),

            "match_rate_percent": (
                rate
            ),

            "status_counts": dict(
                counts
            ),

            "passed": (
                len(rows)
                >=
                MIN_EVALUABLE_FRAMES
                and
                rate
                >=
                TARGET_PASS_RATE
                *
                100.0
            ),
        })

        return result

    # ========================================================
    # NEUTRAL
    # ========================================================

    if (
        test_case[
            "id"
        ]
        ==
        "neutral"
    ):

        feature_results = {}

        all_passed = True

        for (
            feature_name,
            expected_status,
        ) in (
            test_case[
                "expected"
            ].items()
        ):

            statuses = [
                row[
                    f"{feature_name}_status"
                ]
                for row in rows
            ]

            counts = Counter(
                statuses
            )

            matched = counts.get(
                expected_status,
                0,
            )

            rate = percentage(
                matched,
                len(rows),
            )

            passed = (
                len(rows)
                >=
                MIN_EVALUABLE_FRAMES
                and
                rate
                >=
                TARGET_PASS_RATE
                *
                100.0
            )

            feature_results[
                feature_name
            ] = {
                "expected": (
                    expected_status
                ),

                "match_rate_percent": (
                    rate
                ),

                "status_counts": dict(
                    counts
                ),

                "passed": (
                    passed
                ),
            }

            all_passed = (
                all_passed
                and
                passed
            )

        result[
            "feature_results"
        ] = (
            feature_results
        )

        result[
            "passed"
        ] = (
            all_passed
        )

        return result

    # ========================================================
    # TARGET
    # ========================================================

    target_feature = (
        test_case[
            "target_feature"
        ]
    )

    expected_status = (
        test_case[
            "expected_status"
        ]
    )

    target_statuses = [
        row[
            f"{target_feature}_status"
        ]
        for row in rows
    ]

    target_evaluable = [
        status
        for status in target_statuses
        if status
        !=
        STATUS_NOT_EVALUATED
    ]

    matched = sum(
        1
        for status in target_evaluable
        if status
        ==
        expected_status
    )

    target_rate = percentage(
        matched,
        len(
            target_evaluable
        ),
    )

    result.update({
        "target_feature": (
            target_feature
        ),

        "expected": (
            expected_status
        ),

        "evaluable_frames": (
            len(
                target_evaluable
            )
        ),

        "match_rate_percent": (
            target_rate
        ),

        "target_status_counts": dict(
            Counter(
                target_statuses
            )
        ),

        "passed": (
            len(
                target_evaluable
            )
            >=
            MIN_EVALUABLE_FRAMES
            and
            target_rate
            >=
            TARGET_PASS_RATE
            *
            100.0
        ),
    })

    # ========================================================
    # CROSS-TALK
    #
    # NOTE:
    # cross-talk does NOT fail the test automatically.
    # We measure it for later Temporal/Risk design.
    # ========================================================

    cross_feature = (
        test_case.get(
            "cross_talk_feature"
        )
    )

    cross_neutral = (
        test_case.get(
            "cross_talk_neutral"
        )
    )

    if (
        cross_feature
        is not None
        and
        cross_neutral
        is not None
    ):

        cross_statuses = [
            row[
                f"{cross_feature}_status"
            ]
            for row in rows
        ]

        cross_evaluable = [
            status
            for status in cross_statuses
            if status
            !=
            STATUS_NOT_EVALUATED
        ]

        cross_factor_frames = sum(
            1
            for status
            in cross_evaluable
            if status
            !=
            cross_neutral
        )

        result[
            "cross_talk"
        ] = {
            "feature": (
                cross_feature
            ),

            "expected_neutral": (
                cross_neutral
            ),

            "evaluable_frames": (
                len(
                    cross_evaluable
                )
            ),

            "factor_frames": (
                cross_factor_frames
            ),

            "factor_rate_percent": (
                percentage(
                    cross_factor_frames,
                    len(
                        cross_evaluable
                    ),
                )
            ),

            "status_counts": dict(
                Counter(
                    cross_statuses
                )
            ),
        }

    return result


# ============================================================
# SAVE
# ============================================================

def save_results(
    rows,
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

    frame_csv = (
        RESULTS_DIR
        /
        (
            "assessment_directional_frames_"
            f"{stamp}.csv"
        )
    )

    summary_json = (
        RESULTS_DIR
        /
        (
            "assessment_directional_summary_"
            f"{stamp}.json"
        )
    )

    if rows:

        with frame_csv.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(
                    rows[
                        0
                    ].keys()
                ),
            )

            writer.writeheader()

            writer.writerows(
                rows
            )

    overall_passed = all(
        result.get(
            "passed"
        )
        is True
        for result in results
    )

    summary = {
        "runner_version": (
            RUNNER_VERSION
        ),

        "created_at": (
            datetime.now()
            .isoformat()
        ),

        "target_pass_rate": (
            TARGET_PASS_RATE
        ),

        "results": (
            results
        ),

        "overall_passed": (
            overall_passed
        ),

        "notes": {
            "medical_threshold": False,

            "rula_threshold": False,

            "risk_evaluation": False,

            "baseline_used": False,

            "measurement_change_gate_used": False,

            "cross_talk_is_diagnostic": True,
        },
    }

    with summary_json.open(
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
        overall_passed,
        frame_csv,
        summary_json,
    )


# ============================================================
# PRINT RESULT
# ============================================================

def print_case_result(
    result,
):

    print()
    print(
        "-" * 105
    )

    print(
        result[
            "title"
        ]
    )

    print(
        f"Frames      : "
        f"{result['frames']}"
    )

    if (
        "match_rate_percent"
        in result
    ):

        print(
            f"Match Rate  : "
            f"{result['match_rate_percent']:.2f}%"
        )

    if (
        "feature_results"
        in result
    ):

        for (
            feature_name,
            feature_result,
        ) in (
            result[
                "feature_results"
            ].items()
        ):

            print(
                f"{feature_name:<24}: "
                f"{feature_result['match_rate_percent']:.2f}% "
                f"{'PASS' if feature_result['passed'] else 'FAIL'}"
            )

    if (
        "cross_talk"
        in result
    ):

        cross = (
            result[
                "cross_talk"
            ]
        )

        print()
        print(
            "Cross-talk"
        )

        print(
            f"Feature     : "
            f"{cross['feature']}"
        )

        print(
            f"Factor Rate : "
            f"{cross['factor_rate_percent']:.2f}%"
        )

        print(
            f"Statuses    : "
            f"{cross['status_counts']}"
        )

    print()

    print(
        "Feature distributions"
    )

    for (
        feature_name,
        stats,
    ) in (
        result[
            "feature_statistics"
        ].items()
    ):

        if (
            stats[
                "count"
            ]
            <= 0
        ):
            continue

        print(
            f"{feature_name:<24}"
            f"median={stats['median']:+.3f} "
            f"p05={stats['p05']:+.3f} "
            f"p95={stats['p95']:+.3f} "
            f"min={stats['min']:+.3f} "
            f"max={stats['max']:+.3f}"
        )

    print()

    print(
        "Result      : "
        +
        (
            "PASS"
            if result[
                "passed"
            ]
            else
            "FAIL"
        )
    )

    print(
        "-" * 105
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
        "POSTGUARD - CURRENT POSTURE ASSESSMENT "
        "DIRECTIONAL + CROSS-TALK VALIDATION"
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
        "Directional candidate rules:"
    )

    print(
        "Shoulder: Left < -2.0 | Right > +4.0"
    )

    print(
        "Neck lateral: Left > +5.0 | Right < -7.0"
    )

    print(
        "Neck flexion: Flexion > +10.0 | Extension < -10.0"
    )

    print()

    print(
        "Cross-talk is measured but does NOT automatically "
        "fail a test."
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

        (
            overall_passed,
            frame_csv,
            summary_json,
        ) = save_results(
            all_rows,
            results,
        )

        print()
        print(
            "=" * 110
        )

        print(
            "POSTGUARD - DIRECTIONAL ASSESSMENT FINAL RESULT"
        )

        print(
            "=" * 110
        )

        for result in results:

            print(
                (
                    "[PASS] "
                    if result[
                        "passed"
                    ]
                    else
                    "[FAIL] "
                )
                +
                result[
                    "title"
                ]
            )

            if (
                "match_rate_percent"
                in result
            ):

                print(
                    f"    Target Match : "
                    f"{result['match_rate_percent']:.2f}%"
                )

            if (
                "cross_talk"
                in result
            ):

                print(
                    f"    Cross-talk   : "
                    f"{result['cross_talk']['factor_rate_percent']:.2f}% "
                    f"({result['cross_talk']['feature']})"
                )

        print()

        print(
            "FINAL RESULT: "
            +
            (
                "PASSED"
                if overall_passed
                else
                "NOT PASSED"
            )
        )

        if overall_passed:

            print(
                "Directional Assessment target classification passed."
            )

            print(
                "Review cross-talk statistics before FREEZE."
            )

        else:

            print(
                "Do NOT freeze Current Posture Assessment v1."
            )

        print()

        print(
            f"Frame CSV   : "
            f"{frame_csv}"
        )

        print(
            f"Summary JSON: "
            f"{summary_json}"
        )

        print(
            "=" * 110
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
                "POSTGUARD DIRECTIONAL TEST COMPLETE",
                20,
                45,
                WHITE,
                0.65,
                2,
            )

            put(
                display,
                (
                    "FINAL RESULT: "
                    +
                    (
                        "PASSED"
                        if overall_passed
                        else
                        "NOT PASSED"
                    )
                ),
                20,
                95,
                (
                    GREEN
                    if overall_passed
                    else
                    RED
                ),
                0.70,
                2,
            )

            put(
                display,
                "Q / ESC = Exit",
                20,
                140,
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
            "Test interrupted."
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
            "CURRENT POSTURE ASSESSMENT "
            "DIRECTIONAL TEST CLOSED"
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