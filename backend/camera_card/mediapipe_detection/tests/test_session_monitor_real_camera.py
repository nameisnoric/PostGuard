import argparse
import math
import sys
import time

import cv2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import engine
from app.models.session import PostureSession
from app.models.personal_baseline import PersonalBaseline

from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)

from camera_card.session_monitoring.session_monitor import (
    build_session_monitoring_snapshot,
)


# ============================================================
# Configuration
# ============================================================

WINDOW_NAME = "PostGuard - Real Session Monitoring"

DEFAULT_CAMERA_INDEX = 0

DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 720


# ============================================================
# Feature Display Configuration
# ============================================================

FEATURE_DISPLAY = {
    "shoulder_tilt": {
        "label": "Shoulder Tilt",
        "decimals": 2,
    },

    "neck_lateral_tilt": {
        "label": "Neck Lateral",
        "decimals": 2,
    },

    "neck_flexion": {
        "label": "Neck Flexion",
        "decimals": 2,
    },

    "eye_distance": {
        "label": "Eye Distance",
        "decimals": 2,
    },
}


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "PostGuard Real Camera "
            "Session Monitoring Test"
        )
    )

    parser.add_argument(
        "--session-id",
        type=int,
        default=None,
        help=(
            "Session ID to monitor. "
            "If omitted, latest RUNNING session is used."
        ),
    )

    parser.add_argument(
        "--camera-index",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
        help="OpenCV camera index. Default: 0",
    )

    return parser.parse_args()


# ============================================================
# Numeric Formatting
# ============================================================

def format_number(
    value,
    decimals=2,
):
    if value is None:
        return "N/A"

    if isinstance(value, bool):
        return "N/A"

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return "N/A"

    if not math.isfinite(number):
        return "N/A"

    return f"{number:.{decimals}f}"


def format_delta(
    value,
    decimals=2,
):
    if value is None:
        return "N/A"

    if isinstance(value, bool):
        return "N/A"

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return "N/A"

    if not math.isfinite(number):
        return "N/A"

    return f"{number:+.{decimals}f}"


# ============================================================
# Database
# ============================================================

def load_session_and_baseline(
    session_id=None,
):
    """
    Load the real PostureSession and its exact PersonalBaseline.

    Important:
    - We do not assume Session #18 is still RUNNING.
    - If --session-id is omitted, use latest RUNNING Session.
    - Baseline is loaded through session.baseline_id.
    """

    with Session(engine) as db:

        # ----------------------------------------------------
        # Load Session
        # ----------------------------------------------------

        if session_id is not None:

            session_obj = db.get(
                PostureSession,
                session_id,
            )

            if session_obj is None:
                raise RuntimeError(
                    f"Session {session_id} was not found"
                )

        else:

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

            if session_obj is None:
                raise RuntimeError(
                    "No RUNNING session was found. "
                    "Create/start a Session first."
                )

        # ----------------------------------------------------
        # Monitoring requires RUNNING
        # ----------------------------------------------------

        if (
            str(
                session_obj.status
            ).upper()
            !=
            "RUNNING"
        ):
            raise RuntimeError(
                f"Session {session_obj.session_id} "
                f"is {session_obj.status!r}, not RUNNING."
            )

        # ----------------------------------------------------
        # Load EXACT baseline linked by Session
        # ----------------------------------------------------

        baseline_obj = db.get(
            PersonalBaseline,
            session_obj.baseline_id,
        )

        if baseline_obj is None:
            raise RuntimeError(
                "PersonalBaseline "
                f"{session_obj.baseline_id} "
                "linked to this Session was not found."
            )

        # ----------------------------------------------------
        # Copy values before SQLAlchemy Session closes
        #
        # We intentionally convert ORM objects to plain dicts.
        # This keeps the real-time loop independent from a
        # long-lived database transaction.
        # ----------------------------------------------------

        session_data = {
            "session_id": (
                session_obj.session_id
            ),

            "user_id": (
                session_obj.user_id
            ),

            "baseline_id": (
                session_obj.baseline_id
            ),

            "camera_id": (
                session_obj.camera_id
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

    # --------------------------------------------------------
    # Extra integration checks
    # --------------------------------------------------------

    if (
        session_data["baseline_id"]
        !=
        baseline_data["baseline_id"]
    ):
        raise RuntimeError(
            "Session baseline_id does not match "
            "loaded PersonalBaseline."
        )

    if (
        session_data["camera_id"]
        !=
        baseline_data["camera_id"]
    ):
        raise RuntimeError(
            "Session and PersonalBaseline "
            "camera_id do not match."
        )

    if (
        session_data["user_id"]
        !=
        baseline_data["user_id"]
    ):
        raise RuntimeError(
            "Session and PersonalBaseline "
            "user_id do not match."
        )

    return (
        session_data,
        baseline_data,
    )


# ============================================================
# Console Information
# ============================================================

def print_loaded_data(
    session_data,
    baseline_data,
):
    print()
    print("=" * 72)
    print(
        "POSTGUARD - REAL CAMERA SESSION MONITORING"
    )
    print("=" * 72)

    print(
        f"Session ID  : "
        f"{session_data['session_id']}"
    )

    print(
        f"User ID     : "
        f"{session_data['user_id']}"
    )

    print(
        f"Camera ID   : "
        f"{session_data['camera_id']}"
    )

    print(
        f"Baseline ID : "
        f"{session_data['baseline_id']}"
    )

    print(
        f"Status      : "
        f"{session_data['status']}"
    )

    print("-" * 72)

    print(
        "Baseline Values"
    )

    print(
        "Shoulder Tilt       : "
        f"{format_number(baseline_data['shoulder_angle'])} deg"
    )

    print(
        "Neck Lateral Tilt   : "
        f"{format_number(baseline_data['lateral_tilt_baseline'])} deg"
    )

    print(
        "Neck Flexion        : "
        f"{format_number(baseline_data['neck_flexion_baseline'])} deg"
    )

    print(
        "Eye Distance        : "
        f"{format_number(baseline_data['eye_distance_baseline_px'])} px"
    )

    print("=" * 72)
    print()
    print("Controls:")
    print("  Q / ESC = Exit")
    print()


# ============================================================
# Drawing Helper
# ============================================================

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
# Monitoring Overlay
# ============================================================

def draw_monitoring_overlay(
    frame,
    snapshot,
    fps,
):
    """
    Draw Session Monitoring values.

    Important:
    This is display only.

    It does not calculate:
    - risk
    - RULA
    - alerts
    - changed/stable threshold
    """

    height, width = frame.shape[
        :2
    ]

    # --------------------------------------------------------
    # Dark panel
    # --------------------------------------------------------

    overlay = frame.copy()

    panel_width = min(
        760,
        width,
    )

    panel_height = min(
        430,
        height,
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
        0.60,
        frame,
        0.40,
        0,
        frame,
    )

    session_info = snapshot[
        "session"
    ]

    context = snapshot[
        "context"
    ]

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    draw_text(
        frame,
        "POSTGUARD - SESSION MONITORING",
        20,
        30,
        scale=0.70,
        thickness=2,
    )

    draw_text(
        frame,
        (
            f"Session: "
            f"{session_info['session_id']}   "
            f"Baseline: "
            f"{session_info['baseline_id']}   "
            f"Camera: "
            f"{session_info['camera_id']}"
        ),
        20,
        58,
    )

    draw_text(
        frame,
        (
            f"Context: "
            f"{context['state']}   "
            f"Allow Evaluation: "
            f"{context['allow_posture_evaluation']}   "
            f"FPS: {fps:.1f}"
        ),
        20,
        84,
    )

    reason = context.get(
        "reason"
    )

    draw_text(
        frame,
        f"Context Reason: {reason}",
        20,
        108,
        scale=0.48,
    )

    # --------------------------------------------------------
    # Table Header
    # --------------------------------------------------------

    y = 145

    draw_text(
        frame,
        "Feature",
        20,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Baseline",
        235,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Current",
        350,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Delta",
        465,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Valid",
        575,
        y,
        thickness=2,
    )

    draw_text(
        frame,
        "Compare",
        640,
        y,
        thickness=2,
    )

    # --------------------------------------------------------
    # Feature Rows
    # --------------------------------------------------------

    y += 34

    for (
        feature_name,
        config,
    ) in FEATURE_DISPLAY.items():

        row = snapshot[
            "features"
        ][
            feature_name
        ]

        unit = row[
            "unit"
        ]

        baseline_text = (
            format_number(
                row[
                    "baseline"
                ],
                config[
                    "decimals"
                ],
            )
        )

        current_text = (
            format_number(
                row[
                    "current"
                ],
                config[
                    "decimals"
                ],
            )
        )

        delta_text = (
            format_delta(
                row[
                    "delta"
                ],
                config[
                    "decimals"
                ],
            )
        )

        valid_text = (
            "YES"
            if row[
                "measurement_valid"
            ]
            else
            "NO"
        )

        compare_text = (
            "YES"
            if row[
                "baseline_comparison_eligible"
            ]
            else
            "NO"
        )

        draw_text(
            frame,
            config[
                "label"
            ],
            20,
            y,
        )

        draw_text(
            frame,
            f"{baseline_text} {unit}",
            235,
            y,
        )

        draw_text(
            frame,
            f"{current_text} {unit}",
            350,
            y,
        )

        draw_text(
            frame,
            f"{delta_text} {unit}",
            465,
            y,
        )

        draw_text(
            frame,
            valid_text,
            575,
            y,
        )

        draw_text(
            frame,
            compare_text,
            650,
            y,
        )

        y += 34

    # --------------------------------------------------------
    # Explicit boundary
    # --------------------------------------------------------

    y += 12

    draw_text(
        frame,
        (
            "Change Gate: "
            f"{snapshot['measurement_change_gate_status']}"
        ),
        20,
        y,
        scale=0.50,
    )

    y += 24

    draw_text(
        frame,
        (
            "Posture Assessment: "
            f"{snapshot['posture_assessment_status']}"
        ),
        20,
        y,
        scale=0.50,
    )

    y += 24

    draw_text(
        frame,
        (
            "Risk Score: "
            f"{snapshot['risk_score_status']}   "
            "Alert: "
            f"{snapshot['alert_status']}"
        ),
        20,
        y,
        scale=0.50,
    )

    # --------------------------------------------------------
    # Controls
    # --------------------------------------------------------

    draw_text(
        frame,
        "Q / ESC = Exit",
        20,
        min(
            height - 20,
            panel_height - 12,
        ),
        scale=0.45,
    )


# ============================================================
# Console Snapshot
# ============================================================

def print_snapshot(
    snapshot,
):
    context = snapshot[
        "context"
    ]

    print()
    print("-" * 92)

    print(
        f"Context: "
        f"{context['state']} | "
        f"allow="
        f"{context['allow_posture_evaluation']} | "
        f"reason="
        f"{context['reason']}"
    )

    print("-" * 92)

    print(
        f"{'Feature':<22}"
        f"{'Baseline':>14}"
        f"{'Current':>14}"
        f"{'Delta':>14}"
        f"{'Valid':>10}"
        f"{'Compare':>10}"
    )

    print("-" * 92)

    for (
        feature_name,
        config,
    ) in FEATURE_DISPLAY.items():

        row = snapshot[
            "features"
        ][
            feature_name
        ]

        print(
            f"{config['label']:<22}"
            f"{format_number(row['baseline']):>14}"
            f"{format_number(row['current']):>14}"
            f"{format_delta(row['delta']):>14}"
            f"{str(row['measurement_valid']):>10}"
            f"{str(row['baseline_comparison_eligible']):>10}"
        )

    print("-" * 92)


# ============================================================
# Main
# ============================================================

def main():
    args = parse_args()

    pipeline = None
    camera = None

    try:
        # ====================================================
        # Database
        # ====================================================

        (
            session_data,
            baseline_data,
        ) = load_session_and_baseline(
            session_id=(
                args.session_id
            )
        )

        print_loaded_data(
            session_data,
            baseline_data,
        )

        # ====================================================
        # DetectionPipeline
        # ====================================================

        print(
            "[INFO] Initializing DetectionPipeline..."
        )

        pipeline = DetectionPipeline()

        # New real-time monitoring lifecycle.
        pipeline.reset_runtime()

        print(
            "[OK] DetectionPipeline initialized."
        )

        # ====================================================
        # Camera
        # ====================================================

        print(
            f"[INFO] Opening camera index "
            f"{args.camera_index}..."
        )

        camera = cv2.VideoCapture(
            args.camera_index
        )

        if not camera.isOpened():
            raise RuntimeError(
                f"Cannot open camera index "
                f"{args.camera_index}"
            )

        print(
            "[OK] Camera opened."
        )

        print()
        print(
            "Real Session Monitoring started."
        )
        print(
            "Move naturally, then remain still "
            "and observe Context returning to VALID."
        )
        print()

        # ====================================================
        # Runtime
        # ====================================================

        previous_time = (
            time.perf_counter()
        )

        last_console_print = 0.0

        frame_count = 0

        while True:

            success, frame = (
                camera.read()
            )

            if not success:
                print(
                    "[WARN] Camera frame "
                    "could not be read."
                )
                continue

            timestamp = (
                time.perf_counter()
            )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # DetectionPipeline receives ORIGINAL,
            # UNMIRRORED frame.
            # ------------------------------------------------

            detection_result = (
                pipeline.process_frame(
                    frame,
                    timestamp=timestamp,
                )
            )

            # ------------------------------------------------
            # Session Monitoring Core
            # ------------------------------------------------

            snapshot = (
                build_session_monitoring_snapshot(
                    session=session_data,
                    baseline=baseline_data,
                    detection_result=(
                        detection_result
                    ),
                )
            )

            # ------------------------------------------------
            # FPS
            # ------------------------------------------------

            elapsed = max(
                timestamp
                -
                previous_time,
                1e-9,
            )

            fps = (
                1.0
                /
                elapsed
            )

            previous_time = (
                timestamp
            )

            frame_count += 1

            # ------------------------------------------------
            # Mirror ONLY for user display
            # ------------------------------------------------

            display_frame = (
                cv2.flip(
                    frame,
                    1,
                )
            )

            display_frame = resize_keep_aspect_ratio(
                display_frame,
                max_width=1280,
                max_height=720,
            )

            # ------------------------------------------------
            # Overlay
            # ------------------------------------------------

            draw_monitoring_overlay(
                display_frame,
                snapshot,
                fps,
            )

            cv2.imshow(
                WINDOW_NAME,
                display_frame,
            )

            # ------------------------------------------------
            # Console snapshot once per ~2 seconds
            # ------------------------------------------------

            if (
                timestamp
                -
                last_console_print
                >=
                2.0
            ):
                print_snapshot(
                    snapshot
                )

                last_console_print = (
                    timestamp
                )

            # ------------------------------------------------
            # Keyboard
            # ------------------------------------------------

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
                break

        # ====================================================
        # Completed
        # ====================================================

        print()
        print("=" * 72)

        print(
            "REAL CAMERA SESSION MONITORING: PASSED"
        )

        print(
            f"Processed Frames: "
            f"{frame_count}"
        )

        print(
            f"Session ID      : "
            f"{session_data['session_id']}"
        )

        print(
            f"Baseline ID     : "
            f"{session_data['baseline_id']}"
        )

        print("=" * 72)

        return 0

    except KeyboardInterrupt:
        print()
        print(
            "[INFO] Monitoring interrupted "
            "by user."
        )

        return 0

    except Exception as exc:
        print()
        print("=" * 72)
        print(
            "REAL CAMERA SESSION MONITORING: FAILED"
        )
        print("=" * 72)

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print("=" * 72)

        return 1

    finally:

        if camera is not None:
            camera.release()

        if pipeline is not None:
            pipeline.close()

        cv2.destroyAllWindows()


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    sys.exit(
        main()
    )