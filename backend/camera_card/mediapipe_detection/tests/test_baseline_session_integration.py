from __future__ import annotations

import importlib.util
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
from sqlalchemy import select


# ==========================================================
# PATH SETUP
# ==========================================================

TEST_FILE = Path(__file__).resolve()

CAMERA_CARD_DIR = TEST_FILE.parents[2]
BACKEND_DIR = CAMERA_CARD_DIR.parent

camera_card_path = str(CAMERA_CARD_DIR)
backend_path = str(BACKEND_DIR)

if camera_card_path not in sys.path:
    sys.path.insert(0, camera_card_path)

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


# ==========================================================
# DETECTION PIPELINE
# ==========================================================

from camera_card.mediapipe_detection.detection_pipeline import (
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


spec = importlib.util.spec_from_file_location(
    "personal_baseline_session_integration",
    PERSONAL_BASELINE_PATH,
)

if spec is None or spec.loader is None:
    raise ImportError(
        "Cannot load Personal Baseline module.\n"
        f"Path: {PERSONAL_BASELINE_PATH}"
    )


pb = importlib.util.module_from_spec(spec)

sys.modules[spec.name] = pb

spec.loader.exec_module(pb)


# ==========================================================
# DATABASE
# ==========================================================

from app.database.database import SessionLocal
from app.models.camera import Camera
from app.models.personal_baseline import PersonalBaseline
from app.models.session import PostureSession
from app.models.user import User


# ==========================================================
# CONFIG
# ==========================================================

USER_ID = 1
CAMERA_ID = 1

CAMERA_INDEX = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

WINDOW_NAME = (
    "PostGuard - Baseline Session Lifecycle Integration"
)


# ==========================================================
# PERSONAL BASELINE COLLECTOR
# ==========================================================

def create_collector():
    """
    สร้าง PersonalBaselineCollector ตามค่าที่เรา validate ไว้แล้ว

    IMPORTANT:
    - Collector ยังเป็น Candidate เท่านั้น
    - ยังไม่มีการบันทึก Database ที่ขั้นตอนนี้
    """

    config = pb.PersonalBaselineConfig(
        target_samples=60,
        minimum_valid_ratio=0.70,
        min_calibration_seconds=15.0,
        max_calibration_seconds=30.0,

        max_shoulder_sd_deg=2.0,
        max_neck_lateral_sd_deg=2.0,
        max_neck_flexion_sd_deg=3.0,
        max_eye_distance_sd_px=5.0,
    )

    return pb.PersonalBaselineCollector(
        config
    )


# ==========================================================
# ACTIVE SESSION HELPER
# ==========================================================

def find_active_session(db):
    """
    หา Session ที่ยัง Active ของ User

    Active:
    - RUNNING
    - PAUSED
    """

    statement = (
        select(PostureSession)
        .where(
            PostureSession.user_id == USER_ID,
            PostureSession.status.in_(
                [
                    "RUNNING",
                    "PAUSED",
                ]
            ),
        )
        .order_by(
            PostureSession.session_id.desc()
        )
        .limit(1)
    )

    return db.scalar(
        statement
    )


# ==========================================================
# PREFLIGHT VALIDATION
# ==========================================================

def preflight_validation():
    """
    ตรวจทุกอย่างก่อนเปิดกล้อง

    กฎสำคัญ:
    ถ้ามี RUNNING / PAUSED Session
    ห้ามเริ่ม Calibration ใหม่
    """

    db = SessionLocal()

    try:
        # --------------------------------------------------
        # Validate User
        # --------------------------------------------------

        user = db.scalar(
            select(User).where(
                User.id == USER_ID
            )
        )

        if user is None:
            raise RuntimeError(
                f"User ID {USER_ID} does not exist."
            )

        # --------------------------------------------------
        # Validate Camera ownership
        # --------------------------------------------------

        camera = db.scalar(
            select(Camera).where(
                Camera.camera_id == CAMERA_ID,
                Camera.user_id == USER_ID,
            )
        )

        if camera is None:
            raise RuntimeError(
                f"Camera ID {CAMERA_ID} "
                f"does not belong to "
                f"User ID {USER_ID}."
            )

        # --------------------------------------------------
        # IMPORTANT:
        # Check Active Session BEFORE Camera / Calibration
        # --------------------------------------------------

        active_session = find_active_session(
            db
        )

        if active_session is not None:
            raise RuntimeError(
                "\n"
                "Cannot start a new PostGuard flow.\n"
                "An active Session already exists.\n"
                "\n"
                f"Session ID : "
                f"{active_session.session_id}\n"
                f"Status     : "
                f"{active_session.status}\n"
                f"Baseline   : "
                f"{active_session.baseline_id}\n"
                "\n"
                "Complete or interrupt the existing "
                "Session before starting a new one."
            )

        print()
        print("=" * 78)
        print("POSTGUARD PREFLIGHT")
        print("=" * 78)

        print(
            "User validation        : PASSED"
        )

        print(
            "Camera ownership       : PASSED"
        )

        print(
            "Active Session check   : PASSED"
        )

        print(
            "No RUNNING / PAUSED Session found."
        )

        print("=" * 78)

    finally:
        db.close()


# ==========================================================
# ATOMIC BASELINE + SESSION PERSISTENCE
# ==========================================================

def create_baseline_and_session_atomic(
    usable: dict[str, float],
) -> tuple[int, int]:
    """
    บันทึก PersonalBaseline + PostureSession
    ด้วย Database Transaction เดียว

    Flow:

        LOCK User
            ↓
        Re-check Active Session
            ↓
        INSERT Baseline
            ↓
        flush() -> ได้ baseline_id
            ↓
        INSERT Session
            ↓
        flush()
            ↓
        Validate relationship
            ↓
        COMMIT

    ถ้ามี Exception:
        ROLLBACK ทั้ง Baseline และ Session

    ดังนั้นจะไม่เกิด:
        Baseline Saved
        แต่ Session ไม่ถูกสร้าง
    """

    db = SessionLocal()

    try:
        # --------------------------------------------------
        # Lock User row
        #
        # ช่วย serialize การเริ่ม Session
        # สำหรับ User คนเดียวกัน
        # --------------------------------------------------

        user_statement = (
            select(User)
            .where(
                User.id == USER_ID
            )
            .with_for_update()
        )

        user = db.scalar(
            user_statement
        )

        if user is None:
            raise RuntimeError(
                f"User ID {USER_ID} does not exist."
            )

        # --------------------------------------------------
        # Validate Camera again inside Transaction
        # --------------------------------------------------

        camera = db.scalar(
            select(Camera).where(
                Camera.camera_id == CAMERA_ID,
                Camera.user_id == USER_ID,
            )
        )

        if camera is None:
            raise RuntimeError(
                "Camera ownership changed "
                "during Session startup."
            )

        # --------------------------------------------------
        # IMPORTANT:
        # Re-check Active Session while User row is locked
        # --------------------------------------------------

        active_session = find_active_session(
            db
        )

        if active_session is not None:
            raise RuntimeError(
                "\n"
                "Active Session appeared while "
                "Calibration was running.\n"
                "\n"
                f"Session ID : "
                f"{active_session.session_id}\n"
                f"Status     : "
                f"{active_session.status}\n"
                "\n"
                "Baseline + Session transaction "
                "will be rolled back."
            )

        # --------------------------------------------------
        # Validate usable baseline values
        # --------------------------------------------------

        required_features = (
            "shoulder_tilt",
            "neck_lateral_tilt",
            "neck_flexion",
            "eye_distance",
        )

        for feature_name in required_features:
            if feature_name not in usable:
                raise RuntimeError(
                    "Usable Personal Baseline "
                    f"is missing {feature_name!r}."
                )

        # --------------------------------------------------
        # INSERT PersonalBaseline
        #
        # IMPORTANT:
        # NO COMMIT HERE
        # --------------------------------------------------

        baseline = PersonalBaseline(
            user_id=USER_ID,
            camera_id=CAMERA_ID,

            shoulder_angle=(
                usable["shoulder_tilt"]
            ),

            lateral_tilt_baseline=(
                usable[
                    "neck_lateral_tilt"
                ]
            ),

            neck_flexion_baseline=(
                usable[
                    "neck_flexion"
                ]
            ),

            eye_distance_baseline_px=(
                usable[
                    "eye_distance"
                ]
            ),
        )

        db.add(
            baseline
        )

        # --------------------------------------------------
        # flush:
        # ส่ง INSERT ไป DB เพื่อให้ได้ baseline_id
        #
        # แต่ยังไม่ COMMIT
        # --------------------------------------------------

        db.flush()

        baseline_id = (
            baseline.baseline_id
        )

        if baseline_id is None:
            raise RuntimeError(
                "Database did not generate "
                "a baseline_id."
            )

        # --------------------------------------------------
        # INSERT PostureSession
        # using THIS baseline_id
        # --------------------------------------------------

        posture_session = PostureSession(
            user_id=USER_ID,
            camera_id=CAMERA_ID,

            baseline_id=(
                baseline_id
            ),

            status="RUNNING",

            total_duration=0,
            paused_duration=0,
            pause_count=0,
        )

        db.add(
            posture_session
        )

        db.flush()

        session_id = (
            posture_session.session_id
        )

        if session_id is None:
            raise RuntimeError(
                "Database did not generate "
                "a session_id."
            )

        # --------------------------------------------------
        # Relationship validation BEFORE COMMIT
        # --------------------------------------------------

        if (
            posture_session.baseline_id
            != baseline.baseline_id
        ):
            raise RuntimeError(
                "Session/Baseline ID relationship "
                "is invalid."
            )

        if (
            posture_session.user_id
            != baseline.user_id
        ):
            raise RuntimeError(
                "Session/Baseline User mismatch."
            )

        if (
            posture_session.camera_id
            != baseline.camera_id
        ):
            raise RuntimeError(
                "Session/Baseline Camera mismatch."
            )

        if (
            posture_session.status
            != "RUNNING"
        ):
            raise RuntimeError(
                "New Session did not start "
                "as RUNNING."
            )

        # --------------------------------------------------
        # ONE COMMIT ONLY
        # --------------------------------------------------

        db.commit()

        # --------------------------------------------------
        # Refresh committed rows
        # --------------------------------------------------

        db.refresh(
            baseline
        )

        db.refresh(
            posture_session
        )

        # --------------------------------------------------
        # Console result
        # --------------------------------------------------

        print()
        print("=" * 78)
        print(
            "BASELINE + SESSION "
            "ATOMIC TRANSACTION: COMMITTED"
        )
        print("=" * 78)

        print(
            f"Baseline ID          : "
            f"{baseline.baseline_id}"
        )

        print(
            f"Session ID           : "
            f"{posture_session.session_id}"
        )

        print(
            f"User ID              : "
            f"{posture_session.user_id}"
        )

        print(
            f"Camera ID            : "
            f"{posture_session.camera_id}"
        )

        print(
            f"Session Baseline ID  : "
            f"{posture_session.baseline_id}"
        )

        print(
            f"Status               : "
            f"{posture_session.status}"
        )

        print()

        print(
            "Shoulder Tilt        : "
            f"{baseline.shoulder_angle:+.4f} deg"
        )

        print(
            "Neck Lateral Tilt    : "
            f"{baseline.lateral_tilt_baseline:+.4f} deg"
        )

        print(
            "Neck Flexion         : "
            f"{baseline.neck_flexion_baseline:+.4f} deg"
        )

        print(
            "Eye Distance         : "
            f"{baseline.eye_distance_baseline_px:.4f} px"
        )

        print("=" * 78)

        print(
            "SESSION INTEGRATION: PASSED"
        )

        print(
            "The Session is using the "
            "fresh Baseline created in this flow."
        )

        print("=" * 78)

        return (
            int(baseline.baseline_id),
            int(posture_session.session_id),
        )

    except Exception:
        # --------------------------------------------------
        # Atomic rollback
        # --------------------------------------------------

        db.rollback()

        print()
        print("=" * 78)
        print(
            "ATOMIC TRANSACTION: ROLLED BACK"
        )
        print("=" * 78)

        print(
            "No new Baseline + Session pair "
            "was committed."
        )

        print("=" * 78)

        raise

    finally:
        db.close()


# ==========================================================
# NORMAL SESSION END
# ==========================================================

def complete_session(
    session_id: int,
) -> None:
    """
    Normal End

    ใช้เมื่อผู้ใช้ตั้งใจจบการทดสอบด้วย E

    Session:
        RUNNING / PAUSED
            ↓
        COMPLETED
    """

    db = SessionLocal()

    try:
        posture_session = db.scalar(
            select(PostureSession)
            .where(
                PostureSession.session_id
                == session_id,
                PostureSession.user_id
                == USER_ID,
            )
            .with_for_update()
        )

        if posture_session is None:
            raise RuntimeError(
                f"Session {session_id} "
                "cannot be found."
            )

        if (
            posture_session.status
            == "COMPLETED"
        ):
            return

        if (
            posture_session.status
            not in (
                "RUNNING",
                "PAUSED",
            )
        ):
            raise RuntimeError(
                "Only RUNNING / PAUSED Session "
                "can be completed normally.\n"
                f"Current Status: "
                f"{posture_session.status}"
            )

        now = datetime.now(
            timezone.utc
        )

        # --------------------------------------------------
        # If ending while PAUSED,
        # add final pause duration
        # --------------------------------------------------

        if (
            posture_session.status
            == "PAUSED"
        ):
            paused_at = (
                posture_session.paused_at
            )

            if paused_at is not None:
                pause_seconds = int(
                    (
                        now
                        - paused_at
                    ).total_seconds()
                )

                posture_session.paused_duration += (
                    pause_seconds
                )

                posture_session.paused_at = None

        # --------------------------------------------------
        # Total duration
        # --------------------------------------------------

        if (
            posture_session.started_at
            is not None
        ):
            total_seconds = int(
                (
                    now
                    - posture_session.started_at
                ).total_seconds()
            )

            posture_session.total_duration = (
                max(
                    0,
                    total_seconds,
                )
            )

        posture_session.ended_at = (
            now
        )

        posture_session.status = (
            "COMPLETED"
        )

        db.commit()

        print()
        print("=" * 78)
        print("SESSION COMPLETED")
        print("=" * 78)

        print(
            f"Session ID : "
            f"{session_id}"
        )

        print(
            "Status     : COMPLETED"
        )

        print("=" * 78)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ==========================================================
# ABNORMAL / CANCELLED SESSION END
# ==========================================================

def interrupt_session(
    session_id: int,
) -> None:
    """
    ใช้เมื่อ Session ถูกสร้างแล้ว
    แต่ผู้ใช้ปิด Test ด้วย Q / ESC

    เราไม่เรียกว่า COMPLETED
    เพราะไม่ได้จบ Normal Session Flow

    IMPORTANT:
    ไม่สร้าง ended_at ปลอม
    """

    db = SessionLocal()

    try:
        posture_session = db.scalar(
            select(PostureSession)
            .where(
                PostureSession.session_id
                == session_id,
                PostureSession.user_id
                == USER_ID,
            )
            .with_for_update()
        )

        if posture_session is None:
            return

        if (
            posture_session.status
            == "INTERRUPTED"
        ):
            return

        if (
            posture_session.status
            not in (
                "RUNNING",
                "PAUSED",
            )
        ):
            return

        posture_session.status = (
            "INTERRUPTED"
        )

        # Do not fabricate ended_at
        # because this is not a normal End Session.

        db.commit()

        print()
        print("=" * 78)
        print("SESSION INTERRUPTED")
        print("=" * 78)

        print(
            f"Session ID : "
            f"{session_id}"
        )

        print(
            "Status     : INTERRUPTED"
        )

        print("=" * 78)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ==========================================================
# SIMPLE DISPLAY
# ==========================================================

def draw_status(
    frame,
    *,
    status_value: str,
    sample_count: int,
    elapsed: float,
    session_id: int | None,
    baseline_id: int | None,
):
    """
    UI สำหรับ Integration Test
    """

    display = cv2.flip(
        frame,
        1,
    )

    white = (
        255,
        255,
        255,
    )

    yellow = (
        0,
        255,
        255,
    )

    green = (
        0,
        255,
        0,
    )

    red = (
        0,
        0,
        255,
    )

    cv2.putText(
        display,
        "POSTGUARD - BASELINE / SESSION LIFECYCLE",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        white,
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        display,
        f"Baseline Status: {status_value}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.64,
        yellow,
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        display,
        f"Valid Samples: {sample_count}",
        (20, 115),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        white,
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        display,
        f"Elapsed: {elapsed:.1f} sec",
        (20, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        white,
        2,
        cv2.LINE_AA,
    )

    if (
        status_value
        == pb.BASELINE_NEED_CONFIRMATION
    ):
        cv2.putText(
            display,
            "Technical PASS - Press Y to Confirm",
            (20, 205),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            yellow,
            2,
            cv2.LINE_AA,
        )

    elif (
        status_value
        == pb.BASELINE_SUCCESS
    ):
        cv2.putText(
            display,
            "BASELINE CONFIRMED",
            (20, 205),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            green,
            2,
            cv2.LINE_AA,
        )

    elif (
        status_value
        == pb.BASELINE_FAILED
    ):
        cv2.putText(
            display,
            "BASELINE FAILED - Press R",
            (20, 205),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            red,
            2,
            cv2.LINE_AA,
        )

    # ------------------------------------------------------
    # Session info
    # ------------------------------------------------------

    if session_id is not None:
        cv2.putText(
            display,
            (
                f"Session ID: {session_id} "
                f"| Baseline ID: {baseline_id}"
            ),
            (20, 255),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.63,
            green,
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            display,
            "Session Status: RUNNING",
            (20, 290),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.63,
            green,
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            display,
            (
                "E = Normal End (COMPLETED) "
                "| Q/ESC = Interrupt"
            ),
            (20, 680),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            white,
            1,
            cv2.LINE_AA,
        )

    else:
        cv2.putText(
            display,
            (
                "S Start | Y Confirm | "
                "R Restart | Q/ESC Cancel"
            ),
            (20, 680),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            white,
            1,
            cv2.LINE_AA,
        )

    return display


# ==========================================================
# MAIN
# ==========================================================

def main():
    print()
    print("=" * 78)

    print(
        "POSTGUARD - PERSONAL BASELINE "
        "+ SESSION LIFECYCLE TEST"
    )

    print("=" * 78)

    # ------------------------------------------------------
    # STEP 1:
    # Preflight BEFORE opening Camera
    # ------------------------------------------------------

    preflight_validation()

    print()
    print("Controls:")
    print(
        "S     = Start Personal Baseline"
    )
    print(
        "Y     = Confirm Personal Baseline"
    )
    print(
        "R     = Restart Calibration"
    )
    print(
        "E     = Normal End Session"
    )
    print(
        "Q/ESC = Cancel / Interrupt"
    )
    print()

    # ------------------------------------------------------
    # Open Camera only AFTER Preflight passed
    # ------------------------------------------------------

    cap = cv2.VideoCapture(
        CAMERA_INDEX
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open camera index "
            f"{CAMERA_INDEX}"
        )

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        FRAME_WIDTH,
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        FRAME_HEIGHT,
    )

    detection_pipeline = None

    current_session_id: int | None = (
        None
    )

    current_baseline_id: int | None = (
        None
    )

    normal_end_completed = False

    try:
        # --------------------------------------------------
        # Runtime resources ready
        # --------------------------------------------------

        detection_pipeline = (
            DetectionPipeline()
        )

        collector = create_collector()

        started = False

        cv2.namedWindow(
            WINDOW_NAME,
            cv2.WINDOW_NORMAL,
        )

        cv2.resizeWindow(
            WINDOW_NAME,
            1280,
            720,
        )

        print()
        print(
            "Camera + Detection Runtime: READY"
        )

        print(
            "Press S when you are seated "
            "naturally and ready."
        )

        # --------------------------------------------------
        # Main Runtime Loop
        # --------------------------------------------------

        while True:
            ok, raw_frame = cap.read()

            if not ok:
                print(
                    "ERROR: Cannot read camera frame."
                )
                break

            # ------------------------------------------------
            # Detection MUST use unmirrored frame
            # ------------------------------------------------

            timestamp = time.perf_counter()

            detection_result = (
                detection_pipeline.process_frame(
                    raw_frame,
                    timestamp=timestamp,
                )
            )

            # ------------------------------------------------
            # Candidate Baseline collection
            #
            # Only before Session is created
            # ------------------------------------------------

            if (
                current_session_id is None
                and
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

            status_value = state.get(
                "status",
                "UNKNOWN",
            )

            sample_count = state.get(
                "sample_count",
                0,
            )

            elapsed = float(
                state.get(
                    "elapsed_seconds",
                    0.0,
                )
            )

            # ------------------------------------------------
            # Display
            # ------------------------------------------------

            display = draw_status(
                raw_frame,

                status_value=(
                    status_value
                ),

                sample_count=(
                    sample_count
                ),

                elapsed=elapsed,

                session_id=(
                    current_session_id
                ),

                baseline_id=(
                    current_baseline_id
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

            # =================================================
            # Q / ESC
            # =================================================

            if key in (
                ord("q"),
                ord("Q"),
                27,
            ):
                if (
                    current_session_id
                    is None
                ):
                    # ------------------------------------------
                    # Candidate only.
                    # Nothing has been persisted.
                    # ------------------------------------------

                    print()
                    print(
                        "Calibration flow cancelled."
                    )

                    print(
                        "No new Baseline or Session "
                        "was created."
                    )

                else:
                    # ------------------------------------------
                    # Session exists.
                    # This is NOT a normal completed End.
                    # ------------------------------------------

                    interrupt_session(
                        current_session_id
                    )

                break

            # =================================================
            # S = Start Calibration
            # =================================================

            elif key in (
                ord("s"),
                ord("S"),
            ):
                if (
                    current_session_id
                    is not None
                ):
                    print(
                        "Ignored: Session is "
                        "already RUNNING."
                    )

                    continue

                collector = (
                    create_collector()
                )

                detection_pipeline.reset_context()

                started = True

                print()
                print("=" * 78)

                print(
                    "PERSONAL BASELINE "
                    "CALIBRATION STARTED"
                )

                print("=" * 78)

                print(
                    "Sit naturally and "
                    "look forward."
                )

                print(
                    "Candidate data is NOT "
                    "saved to Database yet."
                )

                print("=" * 78)

            # =================================================
            # R = Restart Calibration
            # =================================================

            elif key in (
                ord("r"),
                ord("R"),
            ):
                if (
                    current_session_id
                    is not None
                ):
                    print(
                        "Restart ignored: "
                        "Session already exists."
                    )

                    continue

                collector = (
                    create_collector()
                )

                detection_pipeline.reset_context()

                started = True

                print()
                print(
                    "CALIBRATION RESTARTED"
                )

                print(
                    "Previous Candidate discarded."
                )

            # =================================================
            # Y = Confirm
            # =================================================

            elif key in (
                ord("y"),
                ord("Y"),
            ):
                if (
                    current_session_id
                    is not None
                ):
                    print(
                        "Confirm ignored: "
                        "Session already exists."
                    )

                    continue

                current = (
                    collector.get_status()
                )

                if not (
                    collector.completed
                    and
                    current.get("status")
                    == pb.BASELINE_NEED_CONFIRMATION
                ):
                    print(
                        "Confirm ignored: "
                        "Baseline is not waiting "
                        "for confirmation."
                    )

                    continue

                # --------------------------------------------
                # User confirms Candidate
                # --------------------------------------------

                collector.confirm()

                usable = (
                    collector.get_usable_baseline()
                )

                print()
                print("=" * 78)

                print(
                    "USABLE PERSONAL BASELINE"
                )

                print("=" * 78)

                for (
                    name,
                    value,
                ) in usable.items():
                    print(
                        f"{name:<24}: "
                        f"{value}"
                    )

                print("=" * 78)

                # --------------------------------------------
                # IMPORTANT:
                #
                # ONE atomic operation:
                #
                # Candidate
                #   ↓
                # INSERT Baseline
                #   ↓
                # INSERT Session
                #   ↓
                # COMMIT
                #
                # Failure = ROLLBACK both
                # --------------------------------------------

                (
                    current_baseline_id,
                    current_session_id,
                ) = (
                    create_baseline_and_session_atomic(
                        usable
                    )
                )

                print()
                print(
                    "SESSION RUNTIME IS NOW ACTIVE"
                )

                print(
                    "This Session is locked to "
                    f"Baseline "
                    f"{current_baseline_id}."
                )

                print()

                print(
                    "Press E for normal End Session."
                )

                print(
                    "Press Q/ESC for interrupted End."
                )

            # =================================================
            # E = Normal End
            # =================================================

            elif key in (
                ord("e"),
                ord("E"),
            ):
                if (
                    current_session_id
                    is None
                ):
                    print(
                        "End ignored: "
                        "No Session is running."
                    )

                    continue

                complete_session(
                    current_session_id
                )

                normal_end_completed = True

                break

    except Exception as error:
        # --------------------------------------------------
        # Runtime failure AFTER Session creation
        #
        # Transaction cannot be rolled back anymore
        # because Session was already committed.
        #
        # Therefore mark it INTERRUPTED.
        # --------------------------------------------------

        if (
            current_session_id
            is not None
            and
            not normal_end_completed
        ):
            try:
                interrupt_session(
                    current_session_id
                )

            except Exception as cleanup_error:
                print()
                print(
                    "WARNING: Unable to mark "
                    "Session as INTERRUPTED."
                )

                print(
                    cleanup_error
                )

        raise error

    finally:
        # --------------------------------------------------
        # Runtime cleanup
        # --------------------------------------------------

        if (
            detection_pipeline
            is not None
        ):
            detection_pipeline.close()

        cap.release()

        cv2.destroyAllWindows()

        print()
        print("=" * 78)

        print(
            "POSTGUARD RUNTIME CLOSED"
        )

        print("=" * 78)

        print(
            "DetectionPipeline : CLOSED"
        )

        print(
            "Camera            : RELEASED"
        )

        print(
            "OpenCV Windows    : CLOSED"
        )

        if (
            current_session_id
            is None
        ):
            print(
                "Session           : "
                "NOT CREATED"
            )

        elif normal_end_completed:
            print(
                "Session           : "
                "COMPLETED"
            )

        else:
            print(
                "Session           : "
                "INTERRUPTED / CHECK DB"
            )

        print("=" * 78)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    main()