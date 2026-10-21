from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time

from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import engine
from app.models.personal_baseline import PersonalBaseline
from app.models.session import PostureSession

from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)

from camera_card.session_monitoring.session_monitor import (
    build_session_monitoring_snapshot,
)


# ============================================================
# PostGuard Final Measurement-Change Validation Runner
# ============================================================

RUNNER_VERSION = "3.0-final-validation"

WINDOW_NAME = (
    "PostGuard - Measurement Change Final Validation"
)

DEFAULT_CAMERA_INDEX = 0

CAPTURE_SECONDS = 8.0

SETTLING_SECONDS = 1.5

REQUIRED_STABLE_ROUNDS = 3

MIN_VALID_SAMPLES_PER_CAPTURE = 30


# ============================================================
# Features
# ============================================================

POSTURE_FEATURES = {
    "shoulder_tilt": {
        "label": "Shoulder Tilt",
        "unit": "deg",
        "small_instruction": (
            "Raise/tilt one shoulder slightly and HOLD."
        ),
        "medium_instruction": (
            "Raise/tilt one shoulder moderately and HOLD."
        ),
        "large_instruction": (
            "Raise/tilt one shoulder clearly and HOLD."
        ),
    },

    "neck_lateral_tilt": {
        "label": "Neck Lateral Tilt",
        "unit": "deg",
        "small_instruction": (
            "Tilt your head sideways slightly and HOLD."
        ),
        "medium_instruction": (
            "Tilt your head sideways moderately and HOLD."
        ),
        "large_instruction": (
            "Tilt your head sideways clearly and HOLD."
        ),
    },

    "neck_flexion": {
        "label": "Neck Flexion",
        "unit": "deg",
        "small_instruction": (
            "Flex/extend your head slightly and HOLD."
        ),
        "medium_instruction": (
            "Flex/extend your head moderately and HOLD."
        ),
        "large_instruction": (
            "Flex/extend your head clearly and HOLD."
        ),
    },
}

POSTURE_FEATURE_ORDER = list(
    POSTURE_FEATURES.keys()
)

ALL_LOG_FEATURES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
    "eye_distance",
)

CHANGE_LEVELS = (
    "small",
    "medium",
    "large",
)


# ============================================================
# Output
# ============================================================

RESULTS_DIR = (
    Path(__file__)
    .resolve()
    .parent
    /
    "results"
    /
    "measurement_change_final_validation"
)


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "PostGuard Measurement-Change "
            "Final Validation Runner"
        )
    )

    parser.add_argument(
        "--session-id",
        type=int,
        default=None,
        help=(
            "RUNNING Session ID. "
            "If omitted, latest RUNNING session is used."
        ),
    )

    parser.add_argument(
        "--camera-index",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
    )

    return parser.parse_args()


# ============================================================
# Numeric Helpers
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


def percentile(
    values,
    percentile_value,
):
    clean_values = []

    for value in values:
        number = finite_number(
            value
        )

        if number is None:
            continue

        clean_values.append(
            float(number)
        )

    if not clean_values:
        return None

    clean_values.sort()

    if len(clean_values) == 1:
        return clean_values[0]

    position = (
        (len(clean_values) - 1)
        *
        percentile_value
        /
        100.0
    )

    lower = math.floor(
        position
    )

    upper = math.ceil(
        position
    )

    if lower == upper:
        return clean_values[
            lower
        ]

    fraction = (
        position
        -
        lower
    )

    return (
        clean_values[lower]
        +
        fraction
        *
        (
            clean_values[upper]
            -
            clean_values[lower]
        )
    )


def safe_mean(
    values,
):
    if not values:
        return None

    return statistics.mean(
        values
    )


def safe_sd(
    values,
):
    if len(values) < 2:
        return None

    return statistics.stdev(
        values
    )


def safe_percentage(
    numerator,
    denominator,
):
    if denominator <= 0:
        return None

    return (
        numerator
        /
        denominator
        *
        100.0
    )


# ============================================================
# Database
# ============================================================

def load_session_and_baseline(
    session_id=None,
):
    with Session(engine) as db:

        if session_id is None:

            statement = (
                select(
                    PostureSession
                )
                .where(
                    PostureSession.status
                    ==
                    "RUNNING"
                )
                .order_by(
                    PostureSession.session_id.desc()
                )
                .limit(1)
            )

            session_obj = (
                db.execute(
                    statement
                )
                .scalars()
                .first()
            )

        else:

            session_obj = db.get(
                PostureSession,
                session_id,
            )

        if session_obj is None:
            raise RuntimeError(
                "No Session was found."
            )

        if (
            str(
                session_obj.status
            ).upper()
            !=
            "RUNNING"
        ):
            raise RuntimeError(
                f"Session "
                f"{session_obj.session_id} "
                f"is {session_obj.status!r}, "
                "not RUNNING."
            )

        baseline_obj = db.get(
            PersonalBaseline,
            session_obj.baseline_id,
        )

        if baseline_obj is None:
            raise RuntimeError(
                f"PersonalBaseline "
                f"{session_obj.baseline_id} "
                "was not found."
            )

        session_data = {
            "session_id": (
                session_obj.session_id
            ),

            "user_id": (
                session_obj.user_id
            ),

            "camera_id": (
                session_obj.camera_id
            ),

            "baseline_id": (
                session_obj.baseline_id
            ),

            "status": (
                session_obj.status
            ),
        }

        baseline_data = {
            "baseline_id": (
                baseline_obj.baseline_id
            ),

            "user_id": (
                baseline_obj.user_id
            ),

            "camera_id": (
                baseline_obj.camera_id
            ),

            "shoulder_angle": (
                baseline_obj.shoulder_angle
            ),

            "lateral_tilt_baseline": (
                baseline_obj.lateral_tilt_baseline
            ),

            "neck_flexion_baseline": (
                baseline_obj.neck_flexion_baseline
            ),

            "eye_distance_baseline_px": (
                baseline_obj.eye_distance_baseline_px
            ),
        }

    validate_locked_relationship(
        session_data,
        baseline_data,
    )

    return (
        session_data,
        baseline_data,
    )


def validate_locked_relationship(
    session_data,
    baseline_data,
):
    if (
        session_data[
            "baseline_id"
        ]
        !=
        baseline_data[
            "baseline_id"
        ]
    ):
        raise RuntimeError(
            "Session/Baseline mismatch."
        )

    if (
        session_data[
            "camera_id"
        ]
        !=
        baseline_data[
            "camera_id"
        ]
    ):
        raise RuntimeError(
            "Session/Baseline camera mismatch."
        )

    if (
        session_data[
            "user_id"
        ]
        !=
        baseline_data[
            "user_id"
        ]
    ):
        raise RuntimeError(
            "Session/Baseline user mismatch."
        )

    if (
        str(
            session_data[
                "status"
            ]
        ).upper()
        !=
        "RUNNING"
    ):
        raise RuntimeError(
            "Session is no longer RUNNING."
        )


def verify_session_still_locked(
    locked_session,
    locked_baseline,
):
    (
        current_session,
        current_baseline,
    ) = load_session_and_baseline(
        locked_session[
            "session_id"
        ]
    )

    if (
        current_session[
            "session_id"
        ]
        !=
        locked_session[
            "session_id"
        ]
    ):
        raise RuntimeError(
            "Session changed during experiment."
        )

    if (
        current_session[
            "baseline_id"
        ]
        !=
        locked_session[
            "baseline_id"
        ]
    ):
        raise RuntimeError(
            "Baseline changed during experiment."
        )

    if (
        current_baseline[
            "baseline_id"
        ]
        !=
        locked_baseline[
            "baseline_id"
        ]
    ):
        raise RuntimeError(
            "Loaded baseline changed during experiment."
        )


# ============================================================
# Experiment State
# ============================================================

def create_sample_store():
    return {
        feature_name: {
            "stable_rounds": [
                [],
                [],
                [],
            ],

            "changes": {
                "small": [],
                "medium": [],
                "large": [],
            },
        }

        for feature_name
        in POSTURE_FEATURE_ORDER
    }


def create_eye_distance_store():
    return {
        "stable_rounds": [
            [],
            [],
            [],
        ],

        "changes": {
            feature_name: {
                level: []
                for level
                in CHANGE_LEVELS
            }

            for feature_name
            in POSTURE_FEATURE_ORDER
        },
    }


# ============================================================
# Rejection Classification
# ============================================================

def classify_frame(
    snapshot,
    target_feature,
):
    context = (
        snapshot.get(
            "context",
            {}
        )
    )

    context_state = (
        context.get(
            "state"
        )
    )

    allow = (
        context.get(
            "allow_posture_evaluation"
        )
        is True
    )

    row = (
        snapshot.get(
            "features",
            {}
        )
        .get(
            target_feature
        )
    )

    if not isinstance(
        row,
        dict,
    ):
        return (
            False,
            "FEATURE_MISSING",
        )

    if (
        context_state
        !=
        "VALID"
    ):
        if (
            context_state
            ==
            "TRANSITION"
        ):
            return (
                False,
                "CONTEXT_TRANSITION",
            )

        return (
            False,
            "CONTEXT_NOT_VALID",
        )

    if not allow:
        return (
            False,
            "CONTEXT_EVALUATION_NOT_ALLOWED",
        )

    if (
        row.get(
            "measurement_valid"
        )
        is not True
    ):
        return (
            False,
            "MEASUREMENT_INVALID",
        )

    if (
        row.get(
            "baseline_comparison_eligible"
        )
        is not True
    ):
        return (
            False,
            "BASELINE_COMPARISON_NOT_ELIGIBLE",
        )

    delta = finite_number(
        row.get(
            "delta"
        )
    )

    if delta is None:
        return (
            False,
            "DELTA_INVALID",
        )

    return (
        True,
        "",
    )


# ============================================================
# Frame Logging
# ============================================================

FRAME_LOG_COLUMNS = [
    "experiment_timestamp",
    "runner_version",
    "session_id",
    "baseline_id",
    "camera_id",
    "frame_index",
    "pipeline_timestamp",
    "experiment_state",
    "phase",
    "stable_round",
    "target_feature",
    "change_level",
    "context_state",
    "context_allow",
    "context_reason",
    "feature",
    "baseline",
    "current",
    "delta",
    "absolute_delta",
    "measurement_valid",
    "comparison_eligible",
    "accepted_for_target_capture",
    "rejection_reason",
]


def build_frame_log_rows(
    *,
    session_data,
    snapshot,
    frame_index,
    pipeline_timestamp,
    experiment_state,
    phase,
    stable_round,
    target_feature,
    change_level,
):
    rows = []

    context = (
        snapshot.get(
            "context",
            {}
        )
    )

    context_state = (
        context.get(
            "state"
        )
    )

    context_allow = (
        context.get(
            "allow_posture_evaluation"
        )
    )

    context_reason = (
        context.get(
            "reason"
        )
    )

    for feature_name in ALL_LOG_FEATURES:

        feature = (
            snapshot.get(
                "features",
                {}
            )
            .get(
                feature_name,
                {}
            )
        )

        baseline_value = finite_number(
            feature.get(
                "baseline"
            )
        )

        current_value = finite_number(
            feature.get(
                "current"
            )
        )

        delta = finite_number(
            feature.get(
                "delta"
            )
        )

        absolute_delta = (
            abs(delta)
            if delta is not None
            else None
        )

        is_capture_target = False

        if phase == "stable":
            is_capture_target = (
                feature_name
                in
                POSTURE_FEATURE_ORDER
            )

        elif phase == "change":
            is_capture_target = (
                feature_name
                ==
                target_feature
            )

        accepted = False
        rejection_reason = ""

        if is_capture_target:

            (
                accepted,
                rejection_reason,
            ) = classify_frame(
                snapshot,
                feature_name,
            )

        else:
            rejection_reason = (
                "NOT_TARGET_OF_CURRENT_CAPTURE"
            )

        rows.append(
            {
                "experiment_timestamp": (
                    datetime.now()
                    .isoformat()
                ),

                "runner_version": (
                    RUNNER_VERSION
                ),

                "session_id": (
                    session_data[
                        "session_id"
                    ]
                ),

                "baseline_id": (
                    session_data[
                        "baseline_id"
                    ]
                ),

                "camera_id": (
                    session_data[
                        "camera_id"
                    ]
                ),

                "frame_index": (
                    frame_index
                ),

                "pipeline_timestamp": (
                    pipeline_timestamp
                ),

                "experiment_state": (
                    experiment_state
                ),

                "phase": (
                    phase or ""
                ),

                "stable_round": (
                    stable_round
                    if stable_round
                    is not None
                    else ""
                ),

                "target_feature": (
                    target_feature or ""
                ),

                "change_level": (
                    change_level or ""
                ),

                "context_state": (
                    context_state
                ),

                "context_allow": (
                    context_allow
                ),

                "context_reason": (
                    context_reason
                ),

                "feature": (
                    feature_name
                ),

                "baseline": (
                    baseline_value
                ),

                "current": (
                    current_value
                ),

                "delta": (
                    delta
                ),

                "absolute_delta": (
                    absolute_delta
                ),

                "measurement_valid": (
                    feature.get(
                        "measurement_valid"
                    )
                ),

                "comparison_eligible": (
                    feature.get(
                        "baseline_comparison_eligible"
                    )
                ),

                "accepted_for_target_capture": (
                    accepted
                ),

                "rejection_reason": (
                    rejection_reason
                ),
            }
        )

    return rows


# ============================================================
# Display
# ============================================================

def resize_keep_aspect_ratio(
    frame,
    max_width=1280,
    max_height=720,
):
    height, width = (
        frame.shape[:2]
    )

    scale = min(
        max_width / width,
        max_height / height,
        1.0,
    )

    new_width = max(
        1,
        int(
            width
            *
            scale
        ),
    )

    new_height = max(
        1,
        int(
            height
            *
            scale
        ),
    )

    return cv2.resize(
        frame,
        (
            new_width,
            new_height,
        ),
        interpolation=(
            cv2.INTER_LINEAR
        ),
    )


def draw_text(
    frame,
    text,
    x,
    y,
    *,
    scale=0.48,
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
        (
            255,
            255,
            255,
        ),
        thickness,
        cv2.LINE_AA,
    )


# ============================================================
# Stable Round Helpers
# ============================================================

def next_stable_round(
    samples,
):
    for round_index in range(
        REQUIRED_STABLE_ROUNDS
    ):

        complete = all(
            len(
                samples[
                    feature_name
                ][
                    "stable_rounds"
                ][
                    round_index
                ]
            )
            >=
            MIN_VALID_SAMPLES_PER_CAPTURE

            for feature_name
            in POSTURE_FEATURE_ORDER
        )

        if not complete:
            return round_index

    return None


def stable_round_count(
    samples,
):
    count = 0

    for round_index in range(
        REQUIRED_STABLE_ROUNDS
    ):

        complete = all(
            len(
                samples[
                    feature_name
                ][
                    "stable_rounds"
                ][
                    round_index
                ]
            )
            >=
            MIN_VALID_SAMPLES_PER_CAPTURE

            for feature_name
            in POSTURE_FEATURE_ORDER
        )

        if complete:
            count += 1

    return count


# ============================================================
# Analysis
# ============================================================

def summarize_rejections(
    frame_log_rows,
):
    summary = {}

    for row in frame_log_rows:

        if (
            row[
                "accepted_for_target_capture"
            ]
            is True
        ):
            continue

        reason = (
            row[
                "rejection_reason"
            ]
        )

        if (
            not reason
            or
            reason
            ==
            "NOT_TARGET_OF_CURRENT_CAPTURE"
        ):
            continue

        summary[
            reason
        ] = (
            summary.get(
                reason,
                0,
            )
            +
            1
        )

    return summary


def analyze_feature(
    feature_name,
    feature_samples,
):
    stable_rounds = (
        feature_samples[
            "stable_rounds"
        ]
    )

    stable_round_results = []

    pooled_stable = []

    for (
        round_index,
        raw_values,
    ) in enumerate(
        stable_rounds
    ):

        values = []

        for value in raw_values:

            number = finite_number(
                value
            )

            if number is None:
                continue

            values.append(
                abs(number)
            )

        if (
            len(values)
            <
            MIN_VALID_SAMPLES_PER_CAPTURE
        ):
            return {
                "status": (
                    "INSUFFICIENT_STABLE_SAMPLES"
                ),

                "failed_round": (
                    round_index
                    +
                    1
                ),

                "candidate_threshold": None,
            }

        pooled_stable.extend(
            values
        )

        stable_round_results.append(
            {
                "round": (
                    round_index
                    +
                    1
                ),

                "samples": (
                    len(values)
                ),

                "median_abs_delta": (
                    percentile(
                        values,
                        50.0,
                    )
                ),

                "p95_abs_delta": (
                    percentile(
                        values,
                        95.0,
                    )
                ),

                "max_abs_delta": (
                    max(
                        values
                    )
                ),
            }
        )

    round_p95_values = [
        item[
            "p95_abs_delta"
        ]
        for item
        in stable_round_results
    ]

    candidate_threshold = max(
        round_p95_values
    )

    mean_round_p95 = safe_mean(
        round_p95_values
    )

    sd_round_p95 = safe_sd(
        round_p95_values
    )

    if (
        mean_round_p95
        and
        sd_round_p95
        is not None
    ):
        cv_percent = (
            sd_round_p95
            /
            mean_round_p95
            *
            100.0
        )

    else:
        cv_percent = None

    false_positive_count = sum(
        1
        for value
        in pooled_stable
        if value
        >
        candidate_threshold
    )

    change_validation = {}

    completed_levels = 0

    for level in CHANGE_LEVELS:

        values = []

        for value in (
            feature_samples[
                "changes"
            ][
                level
            ]
        ):

            number = finite_number(
                value
            )

            if number is None:
                continue

            values.append(
                abs(number)
            )

        if (
            len(values)
            <
            MIN_VALID_SAMPLES_PER_CAPTURE
        ):
            change_validation[
                level
            ] = {
                "status": (
                    "INSUFFICIENT_SAMPLES"
                ),

                "samples": (
                    len(values)
                ),

                "detection_rate_percent": None,
            }

            continue

        completed_levels += 1

        detected = sum(
            1
            for value
            in values
            if value
            >
            candidate_threshold
        )

        change_validation[
            level
        ] = {
            "status": "VALID",

            "samples": (
                len(values)
            ),

            "median_abs_delta": (
                percentile(
                    values,
                    50.0,
                )
            ),

            "p05_abs_delta": (
                percentile(
                    values,
                    5.0,
                )
            ),

            "p95_abs_delta": (
                percentile(
                    values,
                    95.0,
                )
            ),

            "detected_samples": (
                detected
            ),

            "detection_rate_percent": (
                safe_percentage(
                    detected,
                    len(values),
                )
            ),
        }

    status = (
        "READY_FOR_REVIEW"
        if completed_levels
        ==
        len(
            CHANGE_LEVELS
        )
        else
        "INCOMPLETE_CHANGE_VALIDATION"
    )

    return {
        "status": (
            status
        ),

        "feature": (
            feature_name
        ),

        "candidate_threshold": (
            candidate_threshold
        ),

        "threshold_method": (
            "max_stable_round_p95"
        ),

        "stable": {
            "total_samples": (
                len(
                    pooled_stable
                )
            ),

            "rounds": (
                stable_round_results
            ),

            "pooled_median_abs_delta": (
                percentile(
                    pooled_stable,
                    50.0,
                )
            ),

            "pooled_p95_abs_delta": (
                percentile(
                    pooled_stable,
                    95.0,
                )
            ),

            "mean_round_p95": (
                mean_round_p95
            ),

            "sd_round_p95": (
                sd_round_p95
            ),

            "min_round_p95": (
                min(
                    round_p95_values
                )
            ),

            "max_round_p95": (
                max(
                    round_p95_values
                )
            ),

            "round_p95_range": (
                max(
                    round_p95_values
                )
                -
                min(
                    round_p95_values
                )
            ),

            "round_p95_cv_percent": (
                cv_percent
            ),

            "false_positive_count": (
                false_positive_count
            ),

            "false_positive_rate_percent": (
                safe_percentage(
                    false_positive_count,
                    len(
                        pooled_stable
                    ),
                )
            ),
        },

        "change_validation": (
            change_validation
        ),

        "risk_interpretation": (
            "NOT_APPLICABLE"
        ),
    }


def analyze_eye_distance(
    eye_store,
):
    stable_rounds = []

    pooled = []

    for (
        index,
        values,
    ) in enumerate(
        eye_store[
            "stable_rounds"
        ]
    ):

        clean = []

        for value in values:

            number = finite_number(
                value
            )

            if number is None:
                continue

            clean.append(
                abs(number)
            )

        pooled.extend(
            clean
        )

        stable_rounds.append(
            {
                "round": (
                    index
                    +
                    1
                ),

                "samples": (
                    len(
                        clean
                    )
                ),

                "median_abs_delta": (
                    percentile(
                        clean,
                        50.0,
                    )
                ),

                "p95_abs_delta": (
                    percentile(
                        clean,
                        95.0,
                    )
                ),
            }
        )

    return {
        "status": (
            "OBSERVATION_ONLY"
        ),

        "role": (
            "camera_position_monitoring_candidate"
        ),

        "threshold": None,

        "stable_rounds": (
            stable_rounds
        ),

        "pooled_samples": (
            len(
                pooled
            )
        ),

        "pooled_median_abs_delta": (
            percentile(
                pooled,
                50.0,
            )
        ),

        "pooled_p95_abs_delta": (
            percentile(
                pooled,
                95.0,
            )
        ),
    }


# ============================================================
# Save Results
# ============================================================

def save_results(
    *,
    session_data,
    baseline_data,
    samples,
    eye_store,
    frame_log_rows,
    processed_frames,
):
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    frame_csv_path = (
        RESULTS_DIR
        /
        (
            "final_validation_frames_"
            f"{timestamp}.csv"
        )
    )

    summary_json_path = (
        RESULTS_DIR
        /
        (
            "final_validation_summary_"
            f"{timestamp}.json"
        )
    )

    summary_csv_path = (
        RESULTS_DIR
        /
        (
            "final_validation_summary_"
            f"{timestamp}.csv"
        )
    )

    # --------------------------------------------------------
    # Full Frame CSV
    # --------------------------------------------------------

    with frame_csv_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=(
                FRAME_LOG_COLUMNS
            ),
        )

        writer.writeheader()

        writer.writerows(
            frame_log_rows
        )

    # --------------------------------------------------------
    # Analysis
    # --------------------------------------------------------

    rejection_summary = (
        summarize_rejections(
            frame_log_rows
        )
    )

    feature_analysis = {}

    for feature_name in POSTURE_FEATURE_ORDER:

        feature_analysis[
            feature_name
        ] = (
            analyze_feature(
                feature_name,
                samples[
                    feature_name
                ],
            )
        )

    eye_analysis = (
        analyze_eye_distance(
            eye_store
        )
    )

    target_rows = [
        row
        for row
        in frame_log_rows
        if (
            row[
                "rejection_reason"
            ]
            !=
            "NOT_TARGET_OF_CURRENT_CAPTURE"
        )
        and
        row[
            "phase"
        ]
        in (
            "stable",
            "change",
        )
    ]

    accepted_rows = [
        row
        for row
        in target_rows
        if (
            row[
                "accepted_for_target_capture"
            ]
            is True
        )
    ]

    rejected_rows = [
        row
        for row
        in target_rows
        if (
            row[
                "accepted_for_target_capture"
            ]
            is not True
        )
    ]

    result = {
        "contract_version": (
            "3.0"
        ),

        "runner_version": (
            RUNNER_VERSION
        ),

        "source": (
            "postguard_measurement_change_"
            "final_validation_real_camera"
        ),

        "created_at": (
            datetime.now()
            .isoformat()
        ),

        "session": (
            session_data
        ),

        "baseline": {
            "baseline_id": (
                baseline_data[
                    "baseline_id"
                ]
            ),

            "user_id": (
                baseline_data[
                    "user_id"
                ]
            ),

            "camera_id": (
                baseline_data[
                    "camera_id"
                ]
            ),

            "shoulder_angle": (
                baseline_data[
                    "shoulder_angle"
                ]
            ),

            "lateral_tilt_baseline": (
                baseline_data[
                    "lateral_tilt_baseline"
                ]
            ),

            "neck_flexion_baseline": (
                baseline_data[
                    "neck_flexion_baseline"
                ]
            ),

            "eye_distance_baseline_px": (
                baseline_data[
                    "eye_distance_baseline_px"
                ]
            ),
        },

        "experiment_configuration": {
            "capture_seconds": (
                CAPTURE_SECONDS
            ),

            "settling_seconds": (
                SETTLING_SECONDS
            ),

            "required_stable_rounds": (
                REQUIRED_STABLE_ROUNDS
            ),

            "min_valid_samples_per_capture": (
                MIN_VALID_SAMPLES_PER_CAPTURE
            ),

            "threshold_filter_used_during_collection": (
                False
            ),

            "eye_distance_in_posture_gate": (
                False
            ),
        },

        "frame_statistics": {
            "processed_camera_frames": (
                processed_frames
            ),

            "logged_feature_rows": (
                len(
                    frame_log_rows
                )
            ),

            "target_capture_rows": (
                len(
                    target_rows
                )
            ),

            "accepted_target_rows": (
                len(
                    accepted_rows
                )
            ),

            "rejected_target_rows": (
                len(
                    rejected_rows
                )
            ),

            "acceptance_rate_percent": (
                safe_percentage(
                    len(
                        accepted_rows
                    ),
                    len(
                        target_rows
                    ),
                )
            ),

            "rejection_reasons": (
                rejection_summary
            ),
        },

        "posture_features": (
            feature_analysis
        ),

        "eye_distance": (
            eye_analysis
        ),

        "interpretation": {
            "changed_means_risk": (
                False
            ),

            "stable_means_safe": (
                False
            ),

            "threshold_role": (
                "measurement_change_from_personal_baseline"
            ),
        },
    }

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    with summary_json_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # Summary CSV
    # --------------------------------------------------------

    with summary_csv_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.writer(
            file
        )

        writer.writerow(
            [
                "session_id",
                "baseline_id",
                "feature",
                "status",
                "candidate_threshold",
                "stable_total_samples",
                "stable_pooled_p95",
                "stable_max_round_p95",
                "stable_p95_range",
                "stable_p95_cv_percent",
                "stable_false_positive_rate_percent",
                "small_samples",
                "small_detection_rate_percent",
                "medium_samples",
                "medium_detection_rate_percent",
                "large_samples",
                "large_detection_rate_percent",
            ]
        )

        for feature_name in POSTURE_FEATURE_ORDER:

            analysis = (
                feature_analysis[
                    feature_name
                ]
            )

            stable = (
                analysis.get(
                    "stable",
                    {},
                )
            )

            changes = (
                analysis.get(
                    "change_validation",
                    {},
                )
            )

            small = (
                changes.get(
                    "small",
                    {},
                )
            )

            medium = (
                changes.get(
                    "medium",
                    {},
                )
            )

            large = (
                changes.get(
                    "large",
                    {},
                )
            )

            writer.writerow(
                [
                    session_data[
                        "session_id"
                    ],

                    session_data[
                        "baseline_id"
                    ],

                    feature_name,

                    analysis.get(
                        "status"
                    ),

                    analysis.get(
                        "candidate_threshold"
                    ),

                    stable.get(
                        "total_samples"
                    ),

                    stable.get(
                        "pooled_p95_abs_delta"
                    ),

                    stable.get(
                        "max_round_p95"
                    ),

                    stable.get(
                        "round_p95_range"
                    ),

                    stable.get(
                        "round_p95_cv_percent"
                    ),

                    stable.get(
                        "false_positive_rate_percent"
                    ),

                    small.get(
                        "samples"
                    ),

                    small.get(
                        "detection_rate_percent"
                    ),

                    medium.get(
                        "samples"
                    ),

                    medium.get(
                        "detection_rate_percent"
                    ),

                    large.get(
                        "samples"
                    ),

                    large.get(
                        "detection_rate_percent"
                    ),
                ]
            )

    # --------------------------------------------------------
    # Console
    # --------------------------------------------------------

    print()
    print("=" * 100)

    print(
        "POSTGUARD - FINAL MEASUREMENT CHANGE VALIDATION"
    )

    print("=" * 100)

    print(
        f"Session ID        : "
        f"{session_data['session_id']}"
    )

    print(
        f"Baseline ID       : "
        f"{session_data['baseline_id']}"
    )

    print(
        f"Processed Frames  : "
        f"{processed_frames}"
    )

    print(
        f"Target Rows       : "
        f"{len(target_rows)}"
    )

    print(
        f"Accepted Rows     : "
        f"{len(accepted_rows)}"
    )

    print(
        f"Rejected Rows     : "
        f"{len(rejected_rows)}"
    )

    acceptance_rate = (
        result[
            "frame_statistics"
        ][
            "acceptance_rate_percent"
        ]
    )

    if acceptance_rate is not None:

        print(
            f"Acceptance Rate   : "
            f"{acceptance_rate:.2f}%"
        )

    print()
    print(
        "Rejection Reasons"
    )

    if rejection_summary:

        for (
            reason,
            count,
        ) in sorted(
            rejection_summary.items()
        ):

            print(
                f"  {reason:<40}"
                f"{count}"
            )

    else:

        print(
            "  None"
        )

    for feature_name in POSTURE_FEATURE_ORDER:

        analysis = (
            feature_analysis[
                feature_name
            ]
        )

        print()
        print(
            POSTURE_FEATURES[
                feature_name
            ][
                "label"
            ]
        )

        print(
            "-" * 100
        )

        threshold = (
            analysis.get(
                "candidate_threshold"
            )
        )

        print(
            f"Status              : "
            f"{analysis.get('status')}"
        )

        if threshold is not None:

            print(
                f"Candidate Threshold : "
                f"{threshold:.4f} deg"
            )

        stable = (
            analysis.get(
                "stable",
                {}
            )
        )

        if stable:

            print(
                f"Stable Pooled P95   : "
                f"{stable.get('pooled_p95_abs_delta'):.4f}"
            )

            print(
                f"Stable Max Round P95: "
                f"{stable.get('max_round_p95'):.4f}"
            )

            print(
                f"Stable P95 Range    : "
                f"{stable.get('round_p95_range'):.4f}"
            )

            cv = (
                stable.get(
                    "round_p95_cv_percent"
                )
            )

            if cv is not None:

                print(
                    f"Stable P95 CV       : "
                    f"{cv:.2f}%"
                )

            fp = (
                stable.get(
                    "false_positive_rate_percent"
                )
            )

            if fp is not None:

                print(
                    f"Stable False Positive: "
                    f"{fp:.2f}%"
                )

        changes = (
            analysis.get(
                "change_validation",
                {}
            )
        )

        for level in CHANGE_LEVELS:

            entry = (
                changes.get(
                    level,
                    {}
                )
            )

            rate = (
                entry.get(
                    "detection_rate_percent"
                )
            )

            rate_text = (
                f"{rate:.2f}%"
                if rate is not None
                else
                "N/A"
            )

            print(
                f"{level.upper():<6} Change       : "
                f"{entry.get('samples', 0):>4} samples | "
                f"Detection Rate = "
                f"{rate_text}"
            )

    print()
    print(
        "Eye Distance"
    )

    print(
        "-" * 100
    )

    print(
        "Status              : OBSERVATION_ONLY"
    )

    print(
        "Role                : Camera / Position Monitoring candidate"
    )

    print(
        "Posture Gate        : NOT INCLUDED"
    )

    print()
    print("=" * 100)

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

    print("=" * 100)

    return result


# ============================================================
# Overlay
# ============================================================

def draw_overlay(
    frame,
    *,
    session_data,
    snapshot,
    samples,
    selected_feature,
    experiment_state,
    phase,
    stable_round,
    change_level,
    settling_elapsed,
    capture_elapsed,
):
    overlay = (
        frame.copy()
    )

    panel_width = min(
        930,
        frame.shape[
            1
        ],
    )

    panel_height = min(
        680,
        frame.shape[
            0
        ],
    )

    cv2.rectangle(
        overlay,
        (0, 0),
        (
            panel_width,
            panel_height,
        ),
        (
            0,
            0,
            0,
        ),
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.65,
        frame,
        0.35,
        0,
        frame,
    )

    y = 28

    draw_text(
        frame,
        (
            "POSTGUARD - FINAL "
            "MEASUREMENT CHANGE VALIDATION"
        ),
        18,
        y,
        scale=0.60,
        thickness=2,
    )

    y += 30

    draw_text(
        frame,
        (
            f"Session: "
            f"{session_data['session_id']} | "
            f"Baseline: "
            f"{session_data['baseline_id']}"
        ),
        18,
        y,
    )

    y += 27

    context = (
        snapshot.get(
            "context",
            {}
        )
    )

    draw_text(
        frame,
        (
            f"Context: "
            f"{context.get('state')} | "
            f"Allow: "
            f"{context.get('allow_posture_evaluation')} | "
            f"Reason: "
            f"{context.get('reason')}"
        ),
        18,
        y,
    )

    y += 30

    draw_text(
        frame,
        (
            f"State: "
            f"{experiment_state}"
        ),
        18,
        y,
        thickness=2,
    )

    y += 28

    if experiment_state == "SETTLING":

        draw_text(
            frame,
            (
                "Settling VALID time: "
                f"{settling_elapsed:.2f} / "
                f"{SETTLING_SECONDS:.2f} sec"
            ),
            18,
            y,
        )

    elif experiment_state == "CAPTURING":

        draw_text(
            frame,
            (
                "Capture elapsed: "
                f"{capture_elapsed:.2f} / "
                f"{CAPTURE_SECONDS:.2f} sec"
            ),
            18,
            y,
        )

    else:

        draw_text(
            frame,
            (
                f"Stable Rounds: "
                f"{stable_round_count(samples)}/"
                f"{REQUIRED_STABLE_ROUNDS}"
            ),
            18,
            y,
        )

    y += 34

    draw_text(
        frame,
        (
            "Selected Feature: "
            f"{POSTURE_FEATURES[selected_feature]['label']}"
        ),
        18,
        y,
        thickness=2,
    )

    y += 28

    if phase:

        phase_text = (
            f"Phase: {phase.upper()}"
        )

        if (
            phase
            ==
            "stable"
            and
            stable_round
            is not None
        ):
            phase_text += (
                f" | Round "
                f"{stable_round}"
            )

        if (
            phase
            ==
            "change"
            and
            change_level
        ):
            phase_text += (
                f" | "
                f"{change_level.upper()}"
            )

        draw_text(
            frame,
            phase_text,
            18,
            y,
        )

    y += 38

    draw_text(
        frame,
        "Feature",
        18,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Baseline",
        220,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Current",
        335,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Delta",
        445,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Eligible",
        560,
        y,
        thickness=2,
    )

    y += 30

    for feature_name in ALL_LOG_FEATURES:

        row = (
            snapshot.get(
                "features",
                {}
            )
            .get(
                feature_name,
                {}
            )
        )

        label = (
            POSTURE_FEATURES.get(
                feature_name,
                {
                    "label": (
                        "Eye Distance"
                    )
                },
            )[
                "label"
            ]
        )

        baseline = finite_number(
            row.get(
                "baseline"
            )
        )

        current = finite_number(
            row.get(
                "current"
            )
        )

        delta = finite_number(
            row.get(
                "delta"
            )
        )

        baseline_text = (
            f"{baseline:.2f}"
            if baseline is not None
            else
            "N/A"
        )

        current_text = (
            f"{current:.2f}"
            if current is not None
            else
            "N/A"
        )

        delta_text = (
            f"{delta:+.2f}"
            if delta is not None
            else
            "N/A"
        )

        draw_text(
            frame,
            label,
            18,
            y,
        )

        draw_text(
            frame,
            baseline_text,
            220,
            y,
        )

        draw_text(
            frame,
            current_text,
            335,
            y,
        )

        draw_text(
            frame,
            delta_text,
            445,
            y,
        )

        draw_text(
            frame,
            (
                "YES"
                if row.get(
                    "baseline_comparison_eligible"
                )
                is True
                else
                "NO"
            ),
            570,
            y,
        )

        y += 28

    y += 22

    controls = [
        "S = next STABLE round",
        "1 = Shoulder | 2 = Neck Lateral | 3 = Neck Flexion",
        "Z = SMALL | X = MEDIUM | C = LARGE",
        "A = analyze + save | Q / ESC = exit",
        (
            "Every capture waits for Context VALID "
            f"continuously for {SETTLING_SECONDS:.1f}s."
        ),
    ]

    for text in controls:

        draw_text(
            frame,
            text,
            18,
            y,
            scale=0.43,
        )

        y += 22


# ============================================================
# Main
# ============================================================

def main():
    args = (
        parse_args()
    )

    (
        session_data,
        baseline_data,
    ) = (
        load_session_and_baseline(
            args.session_id
        )
    )

    locked_session = dict(
        session_data
    )

    locked_baseline = dict(
        baseline_data
    )

    print()
    print("=" * 96)

    print(
        "POSTGUARD - FINAL MEASUREMENT CHANGE "
        "VALIDATION RUNNER"
    )

    print("=" * 96)

    print(
        f"Runner Version : "
        f"{RUNNER_VERSION}"
    )

    print(
        f"Session ID     : "
        f"{session_data['session_id']}"
    )

    print(
        f"Baseline ID    : "
        f"{session_data['baseline_id']}"
    )

    print(
        f"Camera ID      : "
        f"{session_data['camera_id']}"
    )

    print(
        f"Settling       : "
        f"{SETTLING_SECONDS:.1f} sec continuous VALID"
    )

    print(
        f"Capture        : "
        f"{CAPTURE_SECONDS:.1f} sec"
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "- No experimental threshold is used to filter frames."
    )

    print(
        "- Context VALID does not mean close to Baseline."
    )

    print(
        "- All processed frames are logged."
    )

    print(
        "- Eye Distance is observation-only."
    )

    print("=" * 96)

    samples = (
        create_sample_store()
    )

    eye_store = (
        create_eye_distance_store()
    )

    frame_log_rows = []

    selected_feature = (
        POSTURE_FEATURE_ORDER[
            0
        ]
    )

    experiment_state = (
        "IDLE"
    )

    phase = None

    active_stable_round_index = None

    active_change_level = None

    settling_valid_started_at = None

    capture_started_at = None

    frame_index = 0

    processed_frames = 0

    pipeline = (
        DetectionPipeline()
    )

    pipeline.reset_runtime()

    camera = cv2.VideoCapture(
        args.camera_index
    )

    if not camera.isOpened():

        pipeline.close()

        raise RuntimeError(
            "Cannot open camera."
        )

    def start_settling(
        *,
        new_phase,
        stable_round_index=None,
        change_level=None,
    ):
        nonlocal experiment_state
        nonlocal phase
        nonlocal active_stable_round_index
        nonlocal active_change_level
        nonlocal settling_valid_started_at
        nonlocal capture_started_at

        verify_session_still_locked(
            locked_session,
            locked_baseline,
        )

        phase = (
            new_phase
        )

        active_stable_round_index = (
            stable_round_index
        )

        active_change_level = (
            change_level
        )

        experiment_state = (
            "SETTLING"
        )

        settling_valid_started_at = (
            None
        )

        capture_started_at = (
            None
        )

    try:

        while True:

            ok, frame = (
                camera.read()
            )

            if not ok:
                continue

            frame_index += 1

            pipeline_timestamp = (
                time.perf_counter()
            )

            detection_result = (
                pipeline.process_frame(
                    frame,
                    timestamp=(
                        pipeline_timestamp
                    ),
                )
            )

            processed_frames += 1

            snapshot = (
                build_session_monitoring_snapshot(
                    session=session_data,
                    baseline=baseline_data,
                    detection_result=(
                        detection_result
                    ),
                )
            )

            context = (
                snapshot.get(
                    "context",
                    {}
                )
            )

            context_valid = (
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

            now = (
                pipeline_timestamp
            )

            settling_elapsed = 0.0

            capture_elapsed = 0.0

            # =================================================
            # Settling
            # =================================================

            if (
                experiment_state
                ==
                "SETTLING"
            ):

                if context_valid:

                    if (
                        settling_valid_started_at
                        is None
                    ):
                        settling_valid_started_at = (
                            now
                        )

                    settling_elapsed = (
                        now
                        -
                        settling_valid_started_at
                    )

                    if (
                        settling_elapsed
                        >=
                        SETTLING_SECONDS
                    ):

                        experiment_state = (
                            "CAPTURING"
                        )

                        capture_started_at = (
                            now
                        )

                        print()
                        print(
                            "[SETTLING PASSED]"
                        )

                        print(
                            f"Context remained VALID "
                            f"for {SETTLING_SECONDS:.1f}s."
                        )

                        print(
                            "[CAPTURE STARTED]"
                        )

                else:

                    settling_valid_started_at = (
                        None
                    )

                    settling_elapsed = (
                        0.0
                    )

            # =================================================
            # Capture
            # =================================================

            if (
                experiment_state
                ==
                "CAPTURING"
                and
                capture_started_at
                is not None
            ):

                capture_elapsed = (
                    now
                    -
                    capture_started_at
                )

                if (
                    phase
                    ==
                    "stable"
                ):

                    for feature_name in POSTURE_FEATURE_ORDER:

                        (
                            accepted,
                            _reason,
                        ) = classify_frame(
                            snapshot,
                            feature_name,
                        )

                        if not accepted:
                            continue

                        delta = finite_number(
                            snapshot[
                                "features"
                            ][
                                feature_name
                            ].get(
                                "delta"
                            )
                        )

                        if delta is None:
                            continue

                        samples[
                            feature_name
                        ][
                            "stable_rounds"
                        ][
                            active_stable_round_index
                        ].append(
                            delta
                        )

                    eye_row = (
                        snapshot.get(
                            "features",
                            {}
                        )
                        .get(
                            "eye_distance",
                            {}
                        )
                    )

                    eye_delta = finite_number(
                        eye_row.get(
                            "delta"
                        )
                    )

                    if eye_delta is not None:

                        eye_store[
                            "stable_rounds"
                        ][
                            active_stable_round_index
                        ].append(
                            eye_delta
                        )

                elif (
                    phase
                    ==
                    "change"
                ):

                    (
                        accepted,
                        _reason,
                    ) = classify_frame(
                        snapshot,
                        selected_feature,
                    )

                    if accepted:

                        delta = finite_number(
                            snapshot[
                                "features"
                            ][
                                selected_feature
                            ].get(
                                "delta"
                            )
                        )

                        if delta is not None:

                            samples[
                                selected_feature
                            ][
                                "changes"
                            ][
                                active_change_level
                            ].append(
                                delta
                            )

                    eye_row = (
                        snapshot.get(
                            "features",
                            {}
                        )
                        .get(
                            "eye_distance",
                            {}
                        )
                    )

                    eye_delta = finite_number(
                        eye_row.get(
                            "delta"
                        )
                    )

                    if eye_delta is not None:

                        eye_store[
                            "changes"
                        ][
                            selected_feature
                        ][
                            active_change_level
                        ].append(
                            eye_delta
                        )

                if (
                    capture_elapsed
                    >=
                    CAPTURE_SECONDS
                ):

                    print()
                    print(
                        "[CAPTURE COMPLETE]"
                    )

                    if (
                        phase
                        ==
                        "stable"
                    ):

                        round_number = (
                            active_stable_round_index
                            +
                            1
                        )

                        print(
                            f"Stable Round: "
                            f"{round_number}"
                        )

                        for feature_name in POSTURE_FEATURE_ORDER:

                            count = len(
                                samples[
                                    feature_name
                                ][
                                    "stable_rounds"
                                ][
                                    active_stable_round_index
                                ]
                            )

                            print(
                                f"  "
                                f"{POSTURE_FEATURES[feature_name]['label']:<24}"
                                f"{count} accepted samples"
                            )

                    elif (
                        phase
                        ==
                        "change"
                    ):

                        count = len(
                            samples[
                                selected_feature
                            ][
                                "changes"
                            ][
                                active_change_level
                            ]
                        )

                        print(
                            f"Feature : "
                            f"{POSTURE_FEATURES[selected_feature]['label']}"
                        )

                        print(
                            f"Level   : "
                            f"{active_change_level.upper()}"
                        )

                        print(
                            f"Accepted: "
                            f"{count}"
                        )

                    experiment_state = (
                        "IDLE"
                    )

                    phase = None

                    active_stable_round_index = (
                        None
                    )

                    active_change_level = (
                        None
                    )

                    settling_valid_started_at = (
                        None
                    )

                    capture_started_at = (
                        None
                    )

            # =================================================
            # Log EVERY processed frame
            # =================================================

            log_rows = (
                build_frame_log_rows(
                    session_data=(
                        session_data
                    ),

                    snapshot=(
                        snapshot
                    ),

                    frame_index=(
                        frame_index
                    ),

                    pipeline_timestamp=(
                        pipeline_timestamp
                    ),

                    experiment_state=(
                        experiment_state
                    ),

                    phase=(
                        phase
                    ),

                    stable_round=(
                        (
                            active_stable_round_index
                            +
                            1
                        )
                        if active_stable_round_index
                        is not None
                        else None
                    ),

                    target_feature=(
                        (
                            selected_feature
                        )
                        if phase
                        ==
                        "change"
                        else None
                    ),

                    change_level=(
                        active_change_level
                    ),
                )
            )

            frame_log_rows.extend(
                log_rows
            )

            # =================================================
            # Display
            # =================================================

            display_frame = (
                cv2.flip(
                    frame,
                    1,
                )
            )

            display_frame = (
                resize_keep_aspect_ratio(
                    display_frame
                )
            )

            draw_overlay(
                display_frame,

                session_data=(
                    session_data
                ),

                snapshot=(
                    snapshot
                ),

                samples=(
                    samples
                ),

                selected_feature=(
                    selected_feature
                ),

                experiment_state=(
                    experiment_state
                ),

                phase=(
                    phase
                ),

                stable_round=(
                    (
                        active_stable_round_index
                        +
                        1
                    )
                    if active_stable_round_index
                    is not None
                    else None
                ),

                change_level=(
                    active_change_level
                ),

                settling_elapsed=(
                    settling_elapsed
                ),

                capture_elapsed=(
                    capture_elapsed
                ),
            )

            cv2.imshow(
                WINDOW_NAME,
                display_frame,
            )

            key = (
                cv2.waitKey(1)
                &
                0xFF
            )

            # =================================================
            # Exit
            # =================================================

            if key in (
                ord("q"),
                ord("Q"),
                27,
            ):
                break

            if (
                experiment_state
                !=
                "IDLE"
            ):
                continue

            # =================================================
            # Stable
            # =================================================

            if key in (
                ord("s"),
                ord("S"),
            ):

                round_index = (
                    next_stable_round(
                        samples
                    )
                )

                if round_index is None:

                    print(
                        "[INFO] All stable rounds "
                        "are complete."
                    )

                    continue

                for feature_name in POSTURE_FEATURE_ORDER:

                    samples[
                        feature_name
                    ][
                        "stable_rounds"
                    ][
                        round_index
                    ].clear()

                eye_store[
                    "stable_rounds"
                ][
                    round_index
                ].clear()

                print()
                print(
                    f"[STABLE ROUND "
                    f"{round_index + 1}]"
                )

                print(
                    "Return to your natural "
                    "baseline-like posture."
                )

                print(
                    f"Waiting for Context VALID "
                    f"continuously for "
                    f"{SETTLING_SECONDS:.1f}s..."
                )

                start_settling(
                    new_phase=(
                        "stable"
                    ),

                    stable_round_index=(
                        round_index
                    ),
                )

            # =================================================
            # Feature Selection
            # =================================================

            elif key == ord("1"):

                selected_feature = (
                    "shoulder_tilt"
                )

                print(
                    "[SELECTED] Shoulder Tilt"
                )

            elif key == ord("2"):

                selected_feature = (
                    "neck_lateral_tilt"
                )

                print(
                    "[SELECTED] Neck Lateral Tilt"
                )

            elif key == ord("3"):

                selected_feature = (
                    "neck_flexion"
                )

                print(
                    "[SELECTED] Neck Flexion"
                )

            # =================================================
            # Small / Medium / Large
            # =================================================

            elif key in (
                ord("z"),
                ord("Z"),
                ord("x"),
                ord("X"),
                ord("c"),
                ord("C"),
            ):

                if key in (
                    ord("z"),
                    ord("Z"),
                ):
                    level = (
                        "small"
                    )

                elif key in (
                    ord("x"),
                    ord("X"),
                ):
                    level = (
                        "medium"
                    )

                else:
                    level = (
                        "large"
                    )

                samples[
                    selected_feature
                ][
                    "changes"
                ][
                    level
                ].clear()

                eye_store[
                    "changes"
                ][
                    selected_feature
                ][
                    level
                ].clear()

                instruction_key = (
                    f"{level}_instruction"
                )

                print()
                print(
                    f"[{level.upper()} CHANGE]"
                )

                print(
                    f"Feature: "
                    f"{POSTURE_FEATURES[selected_feature]['label']}"
                )

                print(
                    POSTURE_FEATURES[
                        selected_feature
                    ][
                        instruction_key
                    ]
                )

                print(
                    "Set the posture first, HOLD it, "
                    "then keep still."
                )

                print(
                    f"Runner waits for Context VALID "
                    f"continuously for "
                    f"{SETTLING_SECONDS:.1f}s "
                    "before collecting."
                )

                start_settling(
                    new_phase=(
                        "change"
                    ),

                    change_level=(
                        level
                    ),
                )

            # =================================================
            # Analyze + Save
            # =================================================

            elif key in (
                ord("a"),
                ord("A"),
            ):

                verify_session_still_locked(
                    locked_session,
                    locked_baseline,
                )

                save_results(
                    session_data=(
                        session_data
                    ),

                    baseline_data=(
                        baseline_data
                    ),

                    samples=(
                        samples
                    ),

                    eye_store=(
                        eye_store
                    ),

                    frame_log_rows=(
                        frame_log_rows
                    ),

                    processed_frames=(
                        processed_frames
                    ),
                )

    finally:

        camera.release()

        pipeline.close()

        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()