from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import cv2


# ==========================================================
# PATH
# ==========================================================

TEST_FILE = Path(
    __file__
).resolve()

CAMERA_CARD_DIR = (
    TEST_FILE.parents[2]
)


camera_card_path = str(
    CAMERA_CARD_DIR
)

if (
    camera_card_path
    not in sys.path
):

    sys.path.insert(
        0,
        camera_card_path,
    )


# ==========================================================
# DETECTION PIPELINE
# ==========================================================

from mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)


# ==========================================================
# PERSONAL BASELINE
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


spec = (
    importlib.util
    .spec_from_file_location(
        "personal_baseline_real_camera",
        PERSONAL_BASELINE_PATH,
    )
)


if (
    spec is None
    or
    spec.loader is None
):

    raise ImportError(
        "Cannot load Personal Baseline module.\n"
        f"Path: {PERSONAL_BASELINE_PATH}"
    )


pb = (
    importlib.util
    .module_from_spec(
        spec
    )
)

sys.modules[
    spec.name
] = pb

spec.loader.exec_module(
    pb
)


# ==========================================================
# CAMERA CONFIG
# ==========================================================

CAMERA_INDEX = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720


# ==========================================================
# COLORS
# OpenCV = BGR
# ==========================================================

WHITE = (
    255,
    255,
    255,
)

GREEN = (
    0,
    255,
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

BLUE = (
    255,
    150,
    0,
)

GRAY = (
    180,
    180,
    180,
)


# ==========================================================
# DRAW TEXT
# ==========================================================

def put_text(
    frame,
    text,
    x,
    y,
    color=WHITE,
    scale=0.60,
    thickness=2,
):

    cv2.putText(
        frame,
        str(text),
        (
            int(x),
            int(y),
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        float(scale),
        color,
        int(thickness),
        cv2.LINE_AA,
    )


# ==========================================================
# FEATURE DISPLAY
# ==========================================================

def format_feature(
    detection_result,
    feature_name,
):

    if not isinstance(
        detection_result,
        dict,
    ):
        return "N/A"

    features = (
        detection_result.get(
            "features"
        )
    )

    if not isinstance(
        features,
        dict,
    ):
        return "N/A"

    feature = (
        features.get(
            feature_name
        )
    )

    if not isinstance(
        feature,
        dict,
    ):
        return "N/A"

    if (
        feature.get(
            "valid"
        )
        is not True
    ):

        return (
            "INVALID ("
            +
            str(
                feature.get(
                    "reason"
                )
                or
                "unknown"
            )
            +
            ")"
        )

    value = (
        feature.get(
            "value"
        )
    )

    unit = (
        feature.get(
            "unit"
        )
        or
        ""
    )

    try:

        return (
            f"{float(value):+.2f} "
            f"{unit}"
        )

    except (
        TypeError,
        ValueError,
    ):

        return "INVALID VALUE"


# ==========================================================
# COLLECTOR
# ==========================================================

def create_collector():

    config = (
        pb.PersonalBaselineConfig(

            target_samples=
                60,

            minimum_valid_ratio=
                0.70,

            min_calibration_seconds=
                15.0,

            max_calibration_seconds=
                30.0,

            max_shoulder_sd_deg=
                2.0,

            max_neck_lateral_sd_deg=
                2.0,

            max_neck_flexion_sd_deg=
                3.0,

            max_eye_distance_sd_px=
                5.0,
        )
    )

    return (
        pb.PersonalBaselineCollector(
            config
        )
    )


# ==========================================================
# PRINT STATISTICS
# ==========================================================

def print_feature_statistics(
    result,
):

    statistics_data = (
        result.get(
            "statistics"
        )
    )

    if not isinstance(
        statistics_data,
        dict,
    ):
        return

    print()

    print(
        "FEATURE STATISTICS"
    )

    print(
        "-" * 70
    )

    units = {
        "shoulder_tilt":
            "deg",

        "neck_lateral_tilt":
            "deg",

        "neck_flexion":
            "deg",

        "eye_distance":
            "px",
    }

    names = {
        "shoulder_tilt":
            "Shoulder Tilt",

        "neck_lateral_tilt":
            "Neck Lateral",

        "neck_flexion":
            "Neck Flexion",

        "eye_distance":
            "Eye Distance",
    }

    for feature_name in (
        pb.REQUIRED_FEATURES
    ):

        stats = (
            statistics_data.get(
                feature_name
            )
            or
            {}
        )

        unit = (
            units[
                feature_name
            ]
        )

        print()

        print(
            names[
                feature_name
            ]
        )

        for key in (
            "min",
            "median",
            "mean",
            "max",
            "sd",
        ):

            value = (
                stats.get(
                    key
                )
            )

            if value is None:

                print(
                    f"  {key:<6}: N/A"
                )

            else:

                print(
                    f"  {key:<6}: "
                    f"{float(value):+.4f} "
                    f"{unit}"
                )


# ==========================================================
# PRINT FULL RESULT
# ==========================================================

def print_result(
    result,
):

    print()

    print(
        "=" * 70
    )

    print(
        "POSTGUARD PERSONAL BASELINE RESULT"
    )

    print(
        "=" * 70
    )

    print(
        "Status              :",
        result.get(
            "status"
        ),
    )

    print(
        "Ready for Session   :",
        result.get(
            "ready_for_session"
        ),
    )

    print(
        "Samples             :",
        result.get(
            "sample_count"
        ),
        (
            "(minimum "
            f"{result.get('target_samples')})"
        ),
    )

    print(
        "Total Frames        :",
        result.get(
            "total_frames"
        ),
    )

    print(
        "Rejected Frames     :",
        result.get(
            "rejected_frames"
        ),
    )

    valid_ratio = (
        result.get(
            "valid_ratio"
        )
    )

    if valid_ratio is not None:

        print(
            "Valid Ratio        :",
            f"{valid_ratio * 100:.2f}%",
        )

    elapsed = (
        result.get(
            "elapsed_seconds"
        )
    )

    if elapsed is not None:

        print(
            "Total Elapsed      :",
            f"{float(elapsed):.3f} sec",
        )

    valid_span = (
        result.get(
            "valid_sample_span_seconds"
        )
    )

    if valid_span is None:

        print(
            "Valid Sample Span  : N/A"
        )

    else:

        print(
            "Valid Sample Span  :",
            f"{float(valid_span):.3f} sec",
        )

    print(
        "Failure Reason      :",
        result.get(
            "failure_reason"
        ),
    )

    print()

    print(
        "CANDIDATE BASELINE"
    )

    print(
        "-" * 70
    )

    baseline = (
        result.get(
            "baseline"
        )
        or
        {}
    )

    for (
        feature_name,
        value,
    ) in baseline.items():

        print(
            f"{feature_name:<24}: "
            f"{value}"
        )

    print_feature_statistics(
        result
    )

    print()

    print(
        "TECHNICAL VALIDATION"
    )

    print(
        "-" * 70
    )

    print(
        result.get(
            "validation"
        )
    )

    print()

    print(
        "USER CONFIRMATION"
    )

    print(
        "-" * 70
    )

    print(
        result.get(
            "confirmation"
        )
    )

    print()

    print(
        "USABLE BASELINE"
    )

    print(
        "-" * 70
    )

    usable = (
        result.get(
            "usable_baseline"
        )
    )

    if usable is None:

        print(
            "None"
        )

    else:

        for (
            feature_name,
            value,
        ) in usable.items():

            print(
                f"{feature_name:<24}: "
                f"{value}"
            )

    print()

    print(
        "REJECTION REASONS"
    )

    print(
        "-" * 70
    )

    print(
        result.get(
            "rejection_reasons"
        )
    )

    print(
        "=" * 70
    )

    print()


# ==========================================================
# MAIN
# ==========================================================

def main():

    print()

    print(
        "=" * 70
    )

    print(
        "POSTGUARD - FINAL PERSONAL BASELINE REAL CAMERA TEST"
    )

    print(
        "=" * 70
    )

    print(
        "Requirements:"
    )

    print(
        "- Minimum 60 valid samples"
    )

    print(
        "- Minimum 15 seconds"
    )

    print(
        "- Maximum 30 seconds"
    )

    print(
        "- Technical PASS -> User Confirmation"
    )

    print()

    print(
        "Controls:"
    )

    print(
        "S = Start"
    )

    print(
        "R = Restart"
    )

    print(
        "Y = Confirm Candidate"
    )

    print(
        "N = Reject Candidate"
    )

    print(
        "P = Print Status / Result"
    )

    print(
        "Q / ESC = Exit"
    )

    print(
        "=" * 70
    )

    print()

    # ======================================================
    # CAMERA
    # ======================================================

    cap = (
        cv2.VideoCapture(
            CAMERA_INDEX
        )
    )

    if not cap.isOpened():

        raise RuntimeError(
            "Cannot open camera "
            f"index {CAMERA_INDEX}"
        )

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        FRAME_WIDTH,
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        FRAME_HEIGHT,
    )

    # ======================================================
    # PIPELINE
    # ======================================================

    detection_pipeline = None

    try:

        detection_pipeline = (
            DetectionPipeline()
        )

        print(
            "DetectionPipeline: READY"
        )

        collector = (
            create_collector()
        )

        started = False
        final_printed = False

        window_name = (
            "PostGuard - "
            "Final Personal Baseline Test"
        )

        cv2.namedWindow(
            window_name,
            cv2.WINDOW_NORMAL,
        )

        cv2.resizeWindow(
            window_name,
            1280,
            720,
        )

        # ==================================================
        # LOOP
        # ==================================================

        while True:

            ok, raw_frame = (
                cap.read()
            )

            if not ok:

                print(
                    "ERROR: Cannot read camera frame."
                )

                break

            # ------------------------------------------------
            # IMPORTANT
            #
            # Detection ใช้ UNMIRRORED frame
            #
            # ใน App จริง detection_frame ตรงนี้
            # ควรเป็น Frame หลัง Camera Setup /
            # Roll Correction แล้ว
            #
            # Acceptance Test นี้ไม่รื้อ Camera Setup
            # ที่ทดสอบแยกไว้แล้ว
            # ------------------------------------------------

            detection_frame = (
                raw_frame
            )

            timestamp = (
                time.perf_counter()
            )

            detection_result = (
                detection_pipeline
                .process_frame(
                    detection_frame,
                    timestamp=
                        timestamp,
                )
            )

            # ------------------------------------------------
            # Mirror เฉพาะภาพ Display
            # ------------------------------------------------

            display = (
                cv2.flip(
                    raw_frame,
                    1,
                )
            )

            # ------------------------------------------------
            # Baseline State
            # ------------------------------------------------

            if started:

                if not collector.completed:

                    state = (
                        collector
                        .add_detection_result(
                            detection_result
                        )
                    )

                else:

                    state = (
                        collector
                        .get_status()
                    )

            else:

                state = {
                    "status":
                        "IDLE",

                    "sample_count":
                        0,

                    "target_samples":
                        60,

                    "total_frames":
                        0,

                    "rejected_frames":
                        0,

                    "valid_ratio":
                        0.0,

                    "elapsed_seconds":
                        0.0,

                    "min_calibration_seconds":
                        15.0,

                    "ready_for_session":
                        False,
                }

            status = (
                state.get(
                    "status"
                )
                or
                "UNKNOWN"
            )

            # ------------------------------------------------
            # Context
            # ------------------------------------------------

            context = (
                detection_result.get(
                    "context"
                )
                if isinstance(
                    detection_result,
                    dict,
                )
                else
                {}
            )

            if not isinstance(
                context,
                dict,
            ):

                context = {}

            context_state = (
                context.get(
                    "state"
                )
                or
                "UNKNOWN"
            )

            allow = (
                context.get(
                    "allow_posture_evaluation"
                )
                is True
            )

            context_reason = (
                context.get(
                    "reason"
                )
                or
                "N/A"
            )

            # ------------------------------------------------
            # Status Color
            # ------------------------------------------------

            if (
                status
                ==
                pb.BASELINE_SUCCESS
            ):

                status_color = GREEN

            elif (
                status
                ==
                pb.BASELINE_FAILED
            ):

                status_color = RED

            elif (
                status
                ==
                pb.BASELINE_NEED_CONFIRMATION
            ):

                status_color = YELLOW

            elif (
                status
                ==
                pb.BASELINE_COLLECTING
            ):

                status_color = BLUE

            else:

                status_color = GRAY

            # ==================================================
            # LEFT PANEL
            # ==================================================

            put_text(
                display,
                "POSTGUARD - PERSONAL BASELINE",
                20,
                35,
                WHITE,
                0.75,
            )

            put_text(
                display,
                f"Status: {status}",
                20,
                70,
                status_color,
                0.75,
            )

            put_text(
                display,
                (
                    "Context: "
                    f"{context_state}"
                ),
                20,
                105,
                (
                    GREEN
                    if allow
                    else
                    YELLOW
                ),
            )

            put_text(
                display,
                (
                    "Context Reason: "
                    f"{context_reason}"
                ),
                20,
                135,
                GRAY,
                0.48,
                1,
            )

            # ------------------------------------------------
            # Current Features
            # ------------------------------------------------

            put_text(
                display,
                (
                    "Shoulder: "
                    +
                    format_feature(
                        detection_result,
                        "shoulder_tilt",
                    )
                ),
                20,
                180,
            )

            put_text(
                display,
                (
                    "Neck Lateral: "
                    +
                    format_feature(
                        detection_result,
                        "neck_lateral_tilt",
                    )
                ),
                20,
                210,
            )

            put_text(
                display,
                (
                    "Neck Flexion: "
                    +
                    format_feature(
                        detection_result,
                        "neck_flexion",
                    )
                ),
                20,
                240,
            )

            put_text(
                display,
                (
                    "Eye Distance: "
                    +
                    format_feature(
                        detection_result,
                        "eye_distance",
                    )
                ),
                20,
                270,
            )

            # ------------------------------------------------
            # Collection
            # ------------------------------------------------

            sample_count = int(
                state.get(
                    "sample_count"
                )
                or
                0
            )

            target_samples = int(
                state.get(
                    "target_samples"
                )
                or
                60
            )

            elapsed = float(
                state.get(
                    "elapsed_seconds"
                )
                or
                0.0
            )

            min_seconds = float(
                state.get(
                    "min_calibration_seconds"
                )
                or
                15.0
            )

            valid_ratio = float(
                state.get(
                    "valid_ratio"
                )
                or
                0.0
            )

            put_text(
                display,
                (
                    "Valid Samples: "
                    f"{sample_count} "
                    f"(minimum {target_samples})"
                ),
                20,
                320,
            )

            put_text(
                display,
                (
                    "Elapsed: "
                    f"{elapsed:.1f} / "
                    f"{min_seconds:.1f} sec"
                ),
                20,
                350,
            )

            put_text(
                display,
                (
                    "Valid Ratio: "
                    f"{valid_ratio * 100:.1f}%"
                ),
                20,
                380,
            )

            put_text(
                display,
                (
                    "Total Frames: "
                    f"{state.get('total_frames', 0)}"
                ),
                20,
                410,
            )

            put_text(
                display,
                (
                    "Rejected: "
                    f"{state.get('rejected_frames', 0)}"
                ),
                20,
                440,
            )

            # ------------------------------------------------
            # Combined Progress
            # ------------------------------------------------

            sample_progress = min(
                1.0,

                (
                    sample_count
                    /
                    target_samples
                )
                if target_samples > 0
                else
                0.0,
            )

            time_progress = min(
                1.0,

                (
                    elapsed
                    /
                    min_seconds
                )
                if min_seconds > 0
                else
                0.0,
            )

            progress = min(
                sample_progress,
                time_progress,
            )

            bar_x = 20
            bar_y = 470
            bar_width = 500
            bar_height = 22

            cv2.rectangle(
                display,
                (
                    bar_x,
                    bar_y,
                ),
                (
                    bar_x
                    +
                    bar_width,

                    bar_y
                    +
                    bar_height,
                ),
                WHITE,
                1,
            )

            fill_width = int(
                bar_width
                *
                progress
            )

            if fill_width > 0:

                cv2.rectangle(
                    display,
                    (
                        bar_x,
                        bar_y,
                    ),
                    (
                        bar_x
                        +
                        fill_width,

                        bar_y
                        +
                        bar_height,
                    ),
                    GREEN,
                    -1,
                )

            put_text(
                display,
                (
                    "Collection Progress: "
                    f"{progress * 100:.1f}%"
                ),
                20,
                525,
                WHITE,
                0.55,
            )

            # ==================================================
            # RIGHT PANEL
            # ==================================================

            if not started:

                put_text(
                    display,
                    (
                        "Sit naturally and "
                        "look forward."
                    ),
                    650,
                    80,
                    YELLOW,
                    0.72,
                )

                put_text(
                    display,
                    "Press S to start",
                    650,
                    120,
                    GREEN,
                    0.72,
                )

            elif (
                status
                ==
                pb.BASELINE_COLLECTING
            ):

                put_text(
                    display,
                    "COLLECTING BASELINE",
                    650,
                    80,
                    BLUE,
                    0.75,
                )

                if (
                    sample_count
                    >=
                    target_samples
                    and
                    elapsed
                    <
                    min_seconds
                ):

                    put_text(
                        display,
                        (
                            "60+ samples reached."
                        ),
                        650,
                        120,
                        GREEN,
                    )

                    put_text(
                        display,
                        (
                            "Continue until 15 sec."
                        ),
                        650,
                        155,
                        YELLOW,
                    )

                else:

                    put_text(
                        display,
                        (
                            "Stay in your natural "
                            "working posture."
                        ),
                        650,
                        120,
                        WHITE,
                    )

            elif (
                status
                ==
                pb.BASELINE_NEED_CONFIRMATION
            ):

                put_text(
                    display,
                    "TECHNICAL VALIDATION: PASS",
                    650,
                    80,
                    GREEN,
                    0.65,
                )

                put_text(
                    display,
                    "USER REVIEW REQUIRED",
                    650,
                    120,
                    YELLOW,
                    0.75,
                )

                put_text(
                    display,
                    (
                        "Use this starting posture "
                        "for this Session?"
                    ),
                    650,
                    160,
                    WHITE,
                    0.52,
                )

                put_text(
                    display,
                    "Y = Confirm",
                    650,
                    205,
                    GREEN,
                )

                put_text(
                    display,
                    "N = Reject",
                    650,
                    240,
                    RED,
                )

                put_text(
                    display,
                    "Session is BLOCKED",
                    650,
                    285,
                    RED,
                )

            elif (
                status
                ==
                pb.BASELINE_SUCCESS
            ):

                put_text(
                    display,
                    "BASELINE SUCCESS",
                    650,
                    80,
                    GREEN,
                    0.80,
                )

                put_text(
                    display,
                    "READY FOR SESSION",
                    650,
                    125,
                    GREEN,
                    0.80,
                )

                put_text(
                    display,
                    (
                        "get_usable_baseline() "
                        "is allowed"
                    ),
                    650,
                    170,
                    GREEN,
                    0.55,
                )

            elif (
                status
                ==
                pb.BASELINE_FAILED
            ):

                put_text(
                    display,
                    "BASELINE FAILED",
                    650,
                    80,
                    RED,
                    0.80,
                )

                put_text(
                    display,
                    (
                        "Reason: "
                        f"{state.get('failure_reason')}"
                    ),
                    650,
                    125,
                    RED,
                    0.50,
                )

                put_text(
                    display,
                    "Session is BLOCKED",
                    650,
                    170,
                    RED,
                )

                put_text(
                    display,
                    "R = Recalibrate",
                    650,
                    215,
                    YELLOW,
                )

            # ------------------------------------------------
            # Candidate Baseline
            # ------------------------------------------------

            candidate = (
                state.get(
                    "baseline"
                )
            )

            if isinstance(
                candidate,
                dict,
            ):

                y = 350

                put_text(
                    display,
                    "Candidate Baseline",
                    650,
                    y,
                    WHITE,
                    0.62,
                )

                y += 35

                for feature_name in (
                    pb.REQUIRED_FEATURES
                ):

                    value = (
                        candidate.get(
                            feature_name
                        )
                    )

                    if value is None:

                        text_value = "N/A"

                    else:

                        text_value = (
                            f"{float(value):+.2f}"
                        )

                    put_text(
                        display,
                        (
                            f"{feature_name}: "
                            f"{text_value}"
                        ),
                        650,
                        y,
                        WHITE,
                        0.52,
                    )

                    y += 30

            # ==================================================
            # CONTROLS
            # ==================================================

            put_text(
                display,
                (
                    "S Start | R Restart | "
                    "Y Confirm | N Reject | "
                    "P Print | Q/ESC Exit"
                ),
                20,
                695,
                WHITE,
                0.48,
                1,
            )

            # ==================================================
            # SHOW
            # ==================================================

            cv2.imshow(
                window_name,
                display,
            )

            # ------------------------------------------------
            # Print Final Result Once
            # ------------------------------------------------

            if (
                started
                and
                collector.completed
                and
                not final_printed
            ):

                print_result(
                    collector.get_status()
                )

                final_printed = True

            # ==================================================
            # KEYBOARD
            # ==================================================

            key = (
                cv2.waitKey(
                    1
                )
                &
                0xFF
            )

            # ------------------------------------------------
            # EXIT
            # ------------------------------------------------

            if key in (
                ord("q"),
                ord("Q"),
                27,
            ):

                break

            # ------------------------------------------------
            # START
            # ------------------------------------------------

            elif key in (
                ord("s"),
                ord("S"),
            ):

                collector = (
                    create_collector()
                )

                detection_pipeline.reset_context()

                started = True
                final_printed = False

                print()

                print(
                    "=" * 70
                )

                print(
                    "CALIBRATION STARTED"
                )

                print(
                    "Sit naturally and "
                    "look forward."
                )

                print(
                    "Minimum 60 valid samples "
                    "+ minimum 15 seconds."
                )

                print(
                    "=" * 70
                )

                print()

            # ------------------------------------------------
            # RESTART
            # ------------------------------------------------

            elif key in (
                ord("r"),
                ord("R"),
            ):

                collector = (
                    create_collector()
                )

                detection_pipeline.reset_context()

                started = True
                final_printed = False

                print()

                print(
                    "=" * 70
                )

                print(
                    "CALIBRATION RESTARTED"
                )

                print(
                    "=" * 70
                )

                print()

            # ------------------------------------------------
            # CONFIRM
            # ------------------------------------------------

            elif key in (
                ord("y"),
                ord("Y"),
            ):

                current = (
                    collector.get_status()
                )

                if (
                    collector.completed
                    and
                    current.get(
                        "status"
                    )
                    ==
                    pb.BASELINE_NEED_CONFIRMATION
                ):

                    result = (
                        collector.confirm()
                    )

                    print()

                    print(
                        "USER CONFIRMED BASELINE"
                    )

                    print_result(
                        result
                    )

                    final_printed = True

                else:

                    print(
                        "Confirm ignored: "
                        "Baseline is not waiting "
                        "for confirmation."
                    )

            # ------------------------------------------------
            # REJECT
            # ------------------------------------------------

            elif key in (
                ord("n"),
                ord("N"),
            ):

                current = (
                    collector.get_status()
                )

                if (
                    collector.completed
                    and
                    current.get(
                        "status"
                    )
                    ==
                    pb.BASELINE_NEED_CONFIRMATION
                ):

                    result = (
                        collector.reject()
                    )

                    print()

                    print(
                        "USER REJECTED BASELINE"
                    )

                    print_result(
                        result
                    )

                    final_printed = True

                else:

                    print(
                        "Reject ignored: "
                        "Baseline is not waiting "
                        "for confirmation."
                    )

            # ------------------------------------------------
            # PRINT
            # ------------------------------------------------

            elif key in (
                ord("p"),
                ord("P"),
            ):

                print_result(
                    collector.get_status()
                )

    # ======================================================
    # CLEANUP
    # ======================================================

    finally:

        if (
            detection_pipeline
            is not None
        ):

            detection_pipeline.close()

        cap.release()

        cv2.destroyAllWindows()

        print()

        print(
            "Real Camera Test closed."
        )

        print()


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    main()