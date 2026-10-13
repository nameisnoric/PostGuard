from __future__ import annotations

import sys
from pathlib import Path

import cv2

THIS_FILE = Path(__file__).resolve()
BACKEND_DIR = THIS_FILE.parents[3]
CAMERA_CARD_DIR = THIS_FILE.parents[2]

for path in (BACKEND_DIR, CAMERA_CARD_DIR):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from camera_card.mediapipe_detection.detection_pipeline import DetectionPipeline
from camera_card.baseline.personal_baseline import (
    PersonalBaselineCollector,
    PersonalBaselineConfig,
    BASELINE_COLLECTING,
    BASELINE_SUCCESS,
    BASELINE_NEED_CONFIRMATION,
    BASELINE_FAILED,
)

CAMERA_ID = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
WINDOW_NAME = "PostGuard Personal Baseline Test"

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
RED = (0, 0, 255)
CYAN = (255, 255, 0)


def put(frame, text, x, y, color=WHITE, scale=0.55, thickness=1):
    cv2.putText(
        frame,
        str(text),
        (int(x), int(y)),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_panel(frame, height=330):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (860, height), BLACK, -1)
    cv2.addWeighted(overlay, 0.68, frame, 0.32, 0, frame)


def read_feature(detection_result, feature_name):
    if not isinstance(detection_result, dict):
        return None

    features = detection_result.get("features") or {}
    feature = features.get(feature_name)

    if not isinstance(feature, dict):
        return None

    if feature.get("valid") is not True:
        return None

    value = feature.get("value")

    if not isinstance(value, (int, float)):
        return None

    return float(value)


def format_value(value, unit, signed=True):
    if value is None:
        return "N/A"

    if signed:
        return f"{value:+.2f} {unit}"

    return f"{value:.2f} {unit}"


def print_baseline_result(result):
    print()
    print("=" * 78)
    print("POSTGUARD PERSONAL BASELINE RESULT")
    print("=" * 78)

    print(f"Status           : {result.get('status')}")
    print(
        "Samples          : "
        f"{result.get('sample_count')}/{result.get('target_samples')}"
    )
    print(f"Total Frames     : {result.get('total_frames')}")
    print(f"Rejected Frames  : {result.get('rejected_frames')}")

    valid_ratio = result.get("valid_ratio")
    if isinstance(valid_ratio, (int, float)):
        print(f"Valid Ratio      : {valid_ratio:.2%}")

    duration = result.get("duration_seconds")
    if isinstance(duration, (int, float)):
        print(f"Valid Duration   : {duration:.2f} sec")

    baseline = result.get("baseline") or {}
    stability = result.get("stability") or {}

    print()
    print("BASELINE")
    print("-" * 78)
    print(f"Shoulder Tilt     : {baseline.get('shoulder_tilt', 0.0):+.3f} deg")
    print(f"Neck Lateral      : {baseline.get('neck_lateral_tilt', 0.0):+.3f} deg")
    print(f"Neck Flexion      : {baseline.get('neck_flexion', 0.0):+.3f} deg")
    print(f"Eye Distance      : {baseline.get('eye_distance', 0.0):.3f} px")

    print()
    print("STABILITY")
    print("-" * 78)
    print(f"Shoulder SD       : {stability.get('shoulder_tilt_sd', 0.0):.3f} deg")
    print(f"Neck Lateral SD   : {stability.get('neck_lateral_tilt_sd', 0.0):.3f} deg")
    print(f"Neck Flexion SD   : {stability.get('neck_flexion_sd', 0.0):.3f} deg")
    print(f"Eye Distance SD   : {stability.get('eye_distance_sd', 0.0):.3f} px")

    validation = result.get("validation") or {}
    print()
    print("VALIDATION")
    print("-" * 78)
    print(f"Passed            : {validation.get('passed')}")
    print(f"Issues            : {validation.get('issues')}")

    confirmation = result.get("confirmation") or {}
    print()
    print("CONFIRMATION")
    print("-" * 78)
    print(f"Required          : {confirmation.get('required')}")
    print(f"Status            : {confirmation.get('status')}")
    print(f"Reason            : {confirmation.get('reason')}")

    print()
    print("REJECTION REASONS")
    print("-" * 78)
    rejection_reasons = result.get("rejection_reasons") or {}
    if rejection_reasons:
        for reason, count in rejection_reasons.items():
            print(f"{reason}: {count}")
    else:
        print("None")

    print("=" * 78)
    print()


def draw_live_detection(frame, detection_result, collector_status):
    display = cv2.flip(frame, 1)
    draw_panel(display, height=390)

    sample_count = collector_status.get("sample_count", 0)
    target_samples = collector_status.get("target_samples", 60)
    valid_ratio = collector_status.get("valid_ratio", 0.0)

    context = detection_result.get("context") or {}
    context_state = context.get("state", "UNKNOWN")
    context_reason = context.get("reason", "N/A")
    allow = context.get("allow_posture_evaluation") is True

    shoulder = read_feature(detection_result, "shoulder_tilt")
    neck_lateral = read_feature(detection_result, "neck_lateral_tilt")
    neck_flexion = read_feature(detection_result, "neck_flexion")
    eye_distance = read_feature(detection_result, "eye_distance")

    put(display, "POSTGUARD PERSONAL BASELINE", 20, 35, YELLOW, 0.72, 2)
    put(
        display,
        "Sit naturally and look forward. Stay reasonably still.",
        20,
        70,
        WHITE,
        0.50,
        1,
    )
    put(
        display,
        f"Collecting: {sample_count}/{target_samples}",
        20,
        115,
        GREEN,
        0.62,
        2,
    )
    put(display, f"Valid Ratio: {valid_ratio:.1%}", 20, 148, WHITE, 0.52, 1)

    context_color = GREEN if allow else YELLOW
    put(
        display,
        f"Context: {context_state} ({context_reason})",
        20,
        185,
        context_color,
        0.50,
        1,
    )

    put(
        display,
        f"Shoulder Tilt: {format_value(shoulder, 'deg')}",
        20,
        225,
        WHITE,
        0.52,
        1,
    )
    put(
        display,
        f"Neck Lateral: {format_value(neck_lateral, 'deg')}",
        20,
        258,
        WHITE,
        0.52,
        1,
    )
    put(
        display,
        f"Neck Flexion: {format_value(neck_flexion, 'deg')}",
        20,
        291,
        WHITE,
        0.52,
        1,
    )
    put(
        display,
        f"Eye Distance: {format_value(eye_distance, 'px', signed=False)}",
        20,
        324,
        WHITE,
        0.52,
        1,
    )

    put(
        display,
        "R = Restart Calibration    ESC = Exit",
        20,
        368,
        CYAN,
        0.48,
        1,
    )

    return display


def draw_final_result(frame, result):
    display = cv2.flip(frame, 1)
    draw_panel(display, height=535)

    status = result.get("status")
    baseline = result.get("baseline") or {}
    stability = result.get("stability") or {}
    validation = result.get("validation") or {}

    if status == BASELINE_SUCCESS:
        status_color = GREEN
    elif status == BASELINE_NEED_CONFIRMATION:
        status_color = YELLOW
    else:
        status_color = RED

    put(display, "PERSONAL BASELINE RESULT", 20, 35, WHITE, 0.72, 2)
    put(display, f"Status: {status}", 20, 75, status_color, 0.68, 2)

    put(
        display,
        f"Shoulder Tilt: {baseline.get('shoulder_tilt', 0.0):+.2f} deg",
        20,
        125,
        WHITE,
        0.55,
        1,
    )
    put(
        display,
        f"Neck Lateral: {baseline.get('neck_lateral_tilt', 0.0):+.2f} deg",
        20,
        158,
        WHITE,
        0.55,
        1,
    )
    put(
        display,
        f"Neck Flexion: {baseline.get('neck_flexion', 0.0):+.2f} deg",
        20,
        191,
        WHITE,
        0.55,
        1,
    )
    put(
        display,
        f"Eye Distance: {baseline.get('eye_distance', 0.0):.2f} px",
        20,
        224,
        WHITE,
        0.55,
        1,
    )

    put(display, "Stability (SD)", 20, 270, CYAN, 0.55, 2)
    put(
        display,
        f"Shoulder SD: {stability.get('shoulder_tilt_sd', 0.0):.2f} deg",
        20,
        303,
        WHITE,
        0.50,
        1,
    )
    put(
        display,
        f"Neck Lateral SD: {stability.get('neck_lateral_tilt_sd', 0.0):.2f} deg",
        20,
        333,
        WHITE,
        0.50,
        1,
    )
    put(
        display,
        f"Neck Flexion SD: {stability.get('neck_flexion_sd', 0.0):.2f} deg",
        20,
        363,
        WHITE,
        0.50,
        1,
    )
    put(
        display,
        f"Eye Distance SD: {stability.get('eye_distance_sd', 0.0):.2f} px",
        20,
        393,
        WHITE,
        0.50,
        1,
    )

    if status == BASELINE_NEED_CONFIRMATION:
        put(
            display,
            "The detected shoulder baseline is noticeably tilted.",
            20,
            438,
            YELLOW,
            0.50,
            1,
        )
        put(
            display,
            "Is this your normal sitting posture?",
            20,
            468,
            YELLOW,
            0.52,
            2,
        )
        put(
            display,
            "Y = Confirm    N = Reject & Recalibrate",
            20,
            505,
            CYAN,
            0.52,
            2,
        )

    elif status == BASELINE_SUCCESS:
        put(
            display,
            "Baseline passed validation.",
            20,
            450,
            GREEN,
            0.55,
            2,
        )
        put(
            display,
            "R = Run again    ESC = Exit",
            20,
            500,
            CYAN,
            0.50,
            1,
        )

    else:
        issues = validation.get("issues") or []
        put(
            display,
            "Calibration failed validation.",
            20,
            440,
            RED,
            0.55,
            2,
        )
        put(
            display,
            "Issues: " + ", ".join(issues),
            20,
            475,
            RED,
            0.45,
            1,
        )
        put(
            display,
            "R = Recalibrate    ESC = Exit",
            20,
            510,
            CYAN,
            0.50,
            1,
        )

    return display


def main():
    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    if not cap.isOpened():
        raise RuntimeError("Cannot open camera.")

    pipeline = DetectionPipeline()

    config = PersonalBaselineConfig(
        target_samples=60,
    )

    collector = PersonalBaselineCollector(
        config=config,
    )

    pipeline.reset_runtime()

    cv2.namedWindow(
        WINDOW_NAME,
        cv2.WINDOW_NORMAL,
    )

    print()
    print("=" * 78)
    print("POSTGUARD PERSONAL BASELINE TEST")
    print("=" * 78)
    print("Sit naturally and look forward.")
    print("The system will collect 60 valid samples.")
    print("=" * 78)
    print()

    printed_result = False

    try:
        while True:
            ok, raw_frame = cap.read()

            if not ok:
                continue

            # IMPORTANT:
            # DetectionPipeline ต้องรับภาพ UNMIRRORED
            detection_result = pipeline.process_frame(
                raw_frame
            )

            current_status = collector.get_status()
            status_name = current_status.get("status")

            if status_name == BASELINE_COLLECTING:
                current_status = collector.add_detection_result(
                    detection_result
                )

                display = draw_live_detection(
                    raw_frame,
                    detection_result,
                    current_status,
                )

            else:
                result = collector.get_result()

                if result is None:
                    display = draw_live_detection(
                        raw_frame,
                        detection_result,
                        current_status,
                    )

                else:
                    display = draw_final_result(
                        raw_frame,
                        result,
                    )

                    if not printed_result:
                        print_baseline_result(
                            result
                        )
                        printed_result = True

            cv2.imshow(
                WINDOW_NAME,
                display,
            )

            key = cv2.waitKey(1) & 0xFF

            if key == 27:
                break

            if key in (ord("r"), ord("R")):
                collector.reset()
                pipeline.reset_runtime()
                printed_result = False
                print()
                print("Calibration restarted.")
                continue

            result = collector.get_result()

            if (
                result is not None
                and result.get("status")
                == BASELINE_NEED_CONFIRMATION
            ):
                if key in (ord("y"), ord("Y")):
                    confirmed_result = collector.confirm()
                    printed_result = False

                    print()
                    print("User confirmed the baseline.")
                    print_baseline_result(
                        confirmed_result
                    )

                    printed_result = True

                elif key in (ord("n"), ord("N")):
                    rejected_result = collector.reject()

                    print()
                    print("User rejected the baseline.")
                    print_baseline_result(
                        rejected_result
                    )

                    print("Restarting calibration...")

                    collector.reset()
                    pipeline.reset_runtime()
                    printed_result = False

    finally:
        pipeline.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
