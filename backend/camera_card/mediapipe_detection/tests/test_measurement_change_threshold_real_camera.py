from __future__ import annotations

import argparse
import csv
import json
import math
import time
from datetime import datetime
from pathlib import Path

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

from camera_card.session_monitoring.measurement_change_gate import (
    derive_threshold_from_samples,
)


# ============================================================
# Configuration
# ============================================================

WINDOW_NAME = (
    "PostGuard - Measurement Change Threshold Validation"
)

DEFAULT_CAMERA_INDEX = 0

CAPTURE_SECONDS = 10.0

MIN_SAMPLES = 30


FEATURES = {
    "shoulder_tilt": {
        "label": "Shoulder Tilt",
        "unit": "deg",
        "instruction": (
            "Raise/tilt one shoulder and HOLD still."
        ),
    },

    "neck_lateral_tilt": {
        "label": "Neck Lateral Tilt",
        "unit": "deg",
        "instruction": (
            "Tilt your head sideways and HOLD still."
        ),
    },

    "neck_flexion": {
        "label": "Neck Flexion",
        "unit": "deg",
        "instruction": (
            "Flex/extend your head and HOLD still."
        ),
    },

    "eye_distance": {
        "label": "Eye Distance",
        "unit": "px",
        "instruction": (
            "Move closer/farther from camera and HOLD still."
        ),
    },
}


FEATURE_ORDER = list(
    FEATURES.keys()
)


RESULTS_DIR = (
    Path(__file__)
    .resolve()
    .parent
    /
    "results"
    /
    "measurement_change"
)


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "PostGuard Measurement-Change "
            "Threshold Validation"
        )
    )

    parser.add_argument(
        "--session-id",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--camera-index",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
    )

    return parser.parse_args()


# ============================================================
# Utility
# ============================================================

def finite_number(
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


def resize_keep_aspect_ratio(
    frame,
    max_width=1280,
    max_height=720,
):
    """
    Resize DISPLAY ONLY while preserving aspect ratio.

    Detection always uses the original frame.
    """

    height, width = (
        frame.shape[:2]
    )

    scale = min(
        max_width / width,
        max_height / height,
    )

    # Do not force enlargement if not necessary.
    if scale > 1.0:
        scale = 1.0

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
    scale=0.55,
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
                "RUNNING Session not found."
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
                f"is not RUNNING."
            )

        baseline_obj = db.get(
            PersonalBaseline,
            session_obj.baseline_id,
        )

        if baseline_obj is None:
            raise RuntimeError(
                "PersonalBaseline not found."
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
            "Baseline mismatch."
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
            "Camera mismatch."
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
            "User mismatch."
        )

    return (
        session_data,
        baseline_data,
    )


# ============================================================
# Storage
# ============================================================

def create_sample_store():
    return {
        feature_name: {
            "stable": [],
            "changed": [],
        }
        for feature_name
        in FEATURE_ORDER
    }


def save_results(
    session_data,
    samples,
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

    csv_path = (
        RESULTS_DIR
        /
        (
            "measurement_change_samples_"
            f"{timestamp}.csv"
        )
    )

    json_path = (
        RESULTS_DIR
        /
        (
            "measurement_change_thresholds_"
            f"{timestamp}.json"
        )
    )

    # ========================================================
    # Raw CSV
    # ========================================================

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(
            file
        )

        writer.writerow(
            [
                "session_id",
                "baseline_id",
                "feature",
                "sample_type",
                "delta",
                "absolute_delta",
            ]
        )

        for feature_name in FEATURE_ORDER:

            for sample_type in (
                "stable",
                "changed",
            ):

                for delta in (
                    samples[
                        feature_name
                    ][
                        sample_type
                    ]
                ):

                    writer.writerow(
                        [
                            session_data[
                                "session_id"
                            ],

                            session_data[
                                "baseline_id"
                            ],

                            feature_name,

                            sample_type,

                            delta,

                            abs(delta),
                        ]
                    )

    # ========================================================
    # Threshold analysis
    # ========================================================

    config = {
        "contract_version": "1.0",

        "source": (
            "postguard_real_camera_"
            "measurement_change_validation"
        ),

        "created_at": (
            datetime.now()
            .isoformat()
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

        "features": {},
    }

    print()
    print("=" * 84)
    print(
        "MEASUREMENT-CHANGE THRESHOLD ANALYSIS"
    )
    print("=" * 84)

    for feature_name in FEATURE_ORDER:

        metadata = (
            FEATURES[
                feature_name
            ]
        )

        stable_values = [
            abs(value)
            for value
            in samples[
                feature_name
            ][
                "stable"
            ]
        ]

        changed_values = [
            abs(value)
            for value
            in samples[
                feature_name
            ][
                "changed"
            ]
        ]

        analysis = (
            derive_threshold_from_samples(
                stable_values,
                changed_values,
                min_samples=MIN_SAMPLES,
            )
        )

        entry = {
            "status": (
                analysis[
                    "status"
                ]
            ),

            "threshold": (
                analysis.get(
                    "threshold"
                )
            ),

            "unit": (
                metadata[
                    "unit"
                ]
            ),

            "stable_samples": (
                analysis.get(
                    "stable_samples",
                    0,
                )
            ),

            "changed_samples": (
                analysis.get(
                    "changed_samples",
                    0,
                )
            ),

            "stable_median_abs_delta": (
                analysis.get(
                    "stable_median_abs_delta"
                )
            ),

            "stable_p95_abs_delta": (
                analysis.get(
                    "stable_p95_abs_delta"
                )
            ),

            "changed_median_abs_delta": (
                analysis.get(
                    "changed_median_abs_delta"
                )
            ),

            "changed_p05_abs_delta": (
                analysis.get(
                    "changed_p05_abs_delta"
                )
            ),

            "separation_margin": (
                analysis.get(
                    "separation_margin"
                )
            ),

            "stable_accuracy": (
                analysis.get(
                    "stable_accuracy"
                )
            ),

            "changed_accuracy": (
                analysis.get(
                    "changed_accuracy"
                )
            ),

            "total_accuracy": (
                analysis.get(
                    "total_accuracy"
                )
            ),

            "method": (
                analysis.get(
                    "method"
                )
            ),
        }

        config[
            "features"
        ][
            feature_name
        ] = entry

        threshold = (
            entry[
                "threshold"
            ]
        )

        if threshold is None:
            threshold_text = (
                "N/A"
            )

        else:
            threshold_text = (
                f"{threshold:.4f}"
            )

        print(
            f"{metadata['label']:<24}"
            f"status="
            f"{entry['status']:<24}"
            f"threshold="
            f"{threshold_text} "
            f"{metadata['unit']}"
        )

    # ========================================================
    # JSON Config
    # ========================================================

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            config,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 84)

    print(
        f"Raw samples : {csv_path}"
    )

    print(
        f"Thresholds  : {json_path}"
    )

    print("=" * 84)

    return (
        csv_path,
        json_path,
        config,
    )


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
    mode,
    remaining_seconds,
):
    overlay = (
        frame.copy()
    )

    panel_width = min(
        900,
        frame.shape[1],
    )

    panel_height = min(
        600,
        frame.shape[0],
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

    y = 30

    draw_text(
        frame,
        (
            "POSTGUARD - "
            "MEASUREMENT CHANGE THRESHOLD VALIDATION"
        ),
        18,
        y,
        scale=0.65,
        thickness=2,
    )

    y += 34

    draw_text(
        frame,
        (
            f"Session: "
            f"{session_data['session_id']}   "
            f"Baseline: "
            f"{session_data['baseline_id']}"
        ),
        18,
        y,
    )

    y += 28

    context = (
        snapshot[
            "context"
        ]
    )

    draw_text(
        frame,
        (
            f"Context: "
            f"{context['state']}   "
            f"Allow: "
            f"{context['allow_posture_evaluation']}"
        ),
        18,
        y,
    )

    y += 40

    selected_metadata = (
        FEATURES[
            selected_feature
        ]
    )

    draw_text(
        frame,
        (
            "Selected Feature: "
            f"{selected_metadata['label']}"
        ),
        18,
        y,
        scale=0.60,
        thickness=2,
    )

    y += 28

    draw_text(
        frame,
        (
            "Changed instruction: "
            f"{selected_metadata['instruction']}"
        ),
        18,
        y,
        scale=0.48,
    )

    y += 38

    if mode is None:
        mode_text = (
            "IDLE"
        )

    else:
        mode_text = (
            f"{mode.upper()} "
            f"({remaining_seconds:.1f}s remaining)"
        )

    draw_text(
        frame,
        (
            f"Capture Mode: "
            f"{mode_text}"
        ),
        18,
        y,
        thickness=2,
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
        "Delta",
        280,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Stable N",
        410,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Changed N",
        540,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Eligible",
        680,
        y,
        thickness=2,
    )

    y += 32

    for feature_name in FEATURE_ORDER:

        row = (
            snapshot[
                "features"
            ][
                feature_name
            ]
        )

        delta = finite_number(
            row[
                "delta"
            ]
        )

        if delta is None:
            delta_text = (
                "N/A"
            )
        else:
            delta_text = (
                f"{delta:+.2f}"
            )

        eligible = (
            row[
                "baseline_comparison_eligible"
            ]
        )

        prefix = (
            ">"
            if feature_name
            ==
            selected_feature
            else " "
        )

        draw_text(
            frame,
            (
                f"{prefix} "
                f"{FEATURES[feature_name]['label']}"
            ),
            18,
            y,
        )

        draw_text(
            frame,
            delta_text,
            280,
            y,
        )

        draw_text(
            frame,
            str(
                len(
                    samples[
                        feature_name
                    ][
                        "stable"
                    ]
                )
            ),
            430,
            y,
        )

        draw_text(
            frame,
            str(
                len(
                    samples[
                        feature_name
                    ][
                        "changed"
                    ]
                )
            ),
            565,
            y,
        )

        draw_text(
            frame,
            (
                "YES"
                if eligible
                else "NO"
            ),
            700,
            y,
        )

        y += 32

    y += 16

    draw_text(
        frame,
        (
            "S = collect STABLE for ALL features "
            f"({CAPTURE_SECONDS:.0f}s)"
        ),
        18,
        y,
        scale=0.48,
    )

    y += 25

    draw_text(
        frame,
        (
            "1/2/3/4 = select target feature"
        ),
        18,
        y,
        scale=0.48,
    )

    y += 25

    draw_text(
        frame,
        (
            "C = collect INTENTIONAL CHANGE "
            "for selected feature"
        ),
        18,
        y,
        scale=0.48,
    )

    y += 25

    draw_text(
        frame,
        (
            "A = analyze + save thresholds"
        ),
        18,
        y,
        scale=0.48,
    )

    y += 25

    draw_text(
        frame,
        "Q / ESC = exit",
        18,
        y,
        scale=0.48,
    )


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

    print()
    print("=" * 84)

    print(
        "POSTGUARD - MEASUREMENT CHANGE "
        "THRESHOLD VALIDATION"
    )

    print("=" * 84)

    print(
        f"Session ID  : "
        f"{session_data['session_id']}"
    )

    print(
        f"Baseline ID : "
        f"{session_data['baseline_id']}"
    )

    print()
    print(
        "TEST PROCEDURE"
    )

    print()
    print(
        "1. Sit in your normal baseline-like posture."
    )

    print(
        "2. Press S and remain stable."
    )

    print(
        "3. Select feature using 1 / 2 / 3 / 4."
    )

    print(
        "4. Perform the instructed intentional change."
    )

    print(
        "5. HOLD the changed posture and press C."
    )

    print(
        "6. Repeat for all 4 features."
    )

    print(
        "7. Press A to analyze and save."
    )

    print("=" * 84)
    print()

    samples = (
        create_sample_store()
    )

    selected_feature = (
        FEATURE_ORDER[
            0
        ]
    )

    mode = None

    capture_started_at = None

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

    try:

        while True:

            ok, frame = (
                camera.read()
            )

            if not ok:
                continue

            timestamp = (
                time.perf_counter()
            )

            # =================================================
            # Detection uses ORIGINAL frame.
            # =================================================

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

            # =================================================
            # Active Capture
            # =================================================

            remaining_seconds = 0.0

            if (
                mode is not None
                and
                capture_started_at
                is not None
            ):
                elapsed = (
                    timestamp
                    -
                    capture_started_at
                )

                remaining_seconds = max(
                    0.0,
                    CAPTURE_SECONDS
                    -
                    elapsed,
                )

                # ---------------------------------------------
                # STABLE:
                # collect all features simultaneously
                # ---------------------------------------------

                if mode == "stable":

                    for feature_name in FEATURE_ORDER:

                        row = (
                            snapshot[
                                "features"
                            ][
                                feature_name
                            ]
                        )

                        if not (
                            row[
                                "baseline_comparison_eligible"
                            ]
                        ):
                            continue

                        delta = finite_number(
                            row[
                                "delta"
                            ]
                        )

                        if delta is None:
                            continue

                        samples[
                            feature_name
                        ][
                            "stable"
                        ].append(
                            delta
                        )

                # ---------------------------------------------
                # CHANGED:
                # collect selected feature only
                # ---------------------------------------------

                elif mode == "changed":

                    row = (
                        snapshot[
                            "features"
                        ][
                            selected_feature
                        ]
                    )

                    if (
                        row[
                            "baseline_comparison_eligible"
                        ]
                    ):
                        delta = (
                            finite_number(
                                row[
                                    "delta"
                                ]
                            )
                        )

                        if (
                            delta
                            is not None
                        ):
                            samples[
                                selected_feature
                            ][
                                "changed"
                            ].append(
                                delta
                            )

                # ---------------------------------------------
                # Capture finished
                # ---------------------------------------------

                if (
                    elapsed
                    >=
                    CAPTURE_SECONDS
                ):
                    print()

                    print(
                        f"[CAPTURE COMPLETE] "
                        f"{mode.upper()}"
                    )

                    if (
                        mode
                        ==
                        "stable"
                    ):
                        for (
                            feature_name
                        ) in FEATURE_ORDER:

                            print(
                                f"  "
                                f"{FEATURES[feature_name]['label']:<24}"
                                f"{len(samples[feature_name]['stable'])} samples"
                            )

                    else:
                        print(
                            f"  "
                            f"{FEATURES[selected_feature]['label']} "
                            f"{len(samples[selected_feature]['changed'])} "
                            "samples"
                        )

                    mode = None

                    capture_started_at = (
                        None
                    )

            # =================================================
            # Display only
            # =================================================

            display_frame = (
                cv2.flip(
                    frame,
                    1,
                )
            )

            # Preserve aspect ratio.
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

                mode=(
                    mode
                ),

                remaining_seconds=(
                    remaining_seconds
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

            # Do not change mode during active capture.
            if mode is not None:
                continue

            # =================================================
            # Stable Capture
            # =================================================

            if key in (
                ord("s"),
                ord("S"),
            ):
                print()

                print(
                    "[STABLE CAPTURE STARTED]"
                )

                print(
                    "Remain in your natural "
                    "baseline-like posture."
                )

                # Stable capture represents the current run.
                # Clear previous stable samples.
                for feature_name in FEATURE_ORDER:

                    samples[
                        feature_name
                    ][
                        "stable"
                    ].clear()

                mode = (
                    "stable"
                )

                capture_started_at = (
                    timestamp
                )

            # =================================================
            # Feature Selection
            # =================================================

            elif key == ord("1"):
                selected_feature = (
                    FEATURE_ORDER[
                        0
                    ]
                )

                print(
                    "[SELECTED] "
                    "Shoulder Tilt"
                )

            elif key == ord("2"):
                selected_feature = (
                    FEATURE_ORDER[
                        1
                    ]
                )

                print(
                    "[SELECTED] "
                    "Neck Lateral Tilt"
                )

            elif key == ord("3"):
                selected_feature = (
                    FEATURE_ORDER[
                        2
                    ]
                )

                print(
                    "[SELECTED] "
                    "Neck Flexion"
                )

            elif key == ord("4"):
                selected_feature = (
                    FEATURE_ORDER[
                        3
                    ]
                )

                print(
                    "[SELECTED] "
                    "Eye Distance"
                )

            # =================================================
            # Changed Capture
            # =================================================

            elif key in (
                ord("c"),
                ord("C"),
            ):

                metadata = (
                    FEATURES[
                        selected_feature
                    ]
                )

                print()
                print(
                    "[INTENTIONAL CHANGE CAPTURE STARTED]"
                )

                print(
                    f"Feature: "
                    f"{metadata['label']}"
                )

                print(
                    metadata[
                        "instruction"
                    ]
                )

                # Replace the previous changed run for
                # this selected feature.
                samples[
                    selected_feature
                ][
                    "changed"
                ].clear()

                mode = (
                    "changed"
                )

                capture_started_at = (
                    timestamp
                )

            # =================================================
            # Analyze
            # =================================================

            elif key in (
                ord("a"),
                ord("A"),
            ):

                save_results(
                    session_data,
                    samples,
                )

    finally:

        camera.release()

        pipeline.close()

        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()