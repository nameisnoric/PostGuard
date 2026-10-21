from __future__ import annotations

import csv
import math
import sys
import time
from pathlib import Path
from statistics import median

import cv2


# ============================================================
# PATH SETUP
# ============================================================
TEST_FILE = Path(__file__).resolve()
BACKEND_DIR = TEST_FILE.parents[3]
CAMERA_CARD_DIR = TEST_FILE.parents[2]

for path in (BACKEND_DIR, CAMERA_CARD_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from camera_card.mediapipe_detection.detection_pipeline import DetectionPipeline


# ============================================================
# CONFIG
# ============================================================
CAMERA_ID = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
COUNTDOWN_SECONDS = 3
TARGET_VALID_FRAMES = 60
MAX_CAPTURE_SECONDS = 20.0

OUTPUT_DIR = Path(__file__).resolve().parent / "detection_visual_results"
IMAGE_DIR = OUTPUT_DIR / "images"
CSV_PATH = OUTPUT_DIR / "detection_visual_results.csv"

FEATURE_NAMES = [
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
    "eye_distance",
]

TEST_CASES = [
    {
        "id": "neutral",
        "name": "Neutral",
        "instruction": "Sit naturally, shoulders relaxed, head straight, look forward.",
        "expected_feature": "reference",
    },
    {
        "id": "shoulder_left",
        "name": "Left Shoulder Raised",
        "instruction": "Raise LEFT shoulder only. Keep head and torso straight. HOLD.",
        "expected_feature": "shoulder_tilt",
    },
    {
        "id": "shoulder_right",
        "name": "Right Shoulder Raised",
        "instruction": "Raise RIGHT shoulder only. Keep head and torso straight. HOLD.",
        "expected_feature": "shoulder_tilt",
    },
    {
        "id": "neck_left",
        "name": "Neck Tilt Left",
        "instruction": "Tilt HEAD LEFT. Keep shoulders still. HOLD.",
        "expected_feature": "neck_lateral_tilt",
    },
    {
        "id": "neck_right",
        "name": "Neck Tilt Right",
        "instruction": "Tilt HEAD RIGHT. Keep shoulders still. HOLD.",
        "expected_feature": "neck_lateral_tilt",
    },
    {
        "id": "neck_flexion",
        "name": "Neck Flexion",
        "instruction": "Lower your head and look DOWN. Keep torso still. HOLD.",
        "expected_feature": "neck_flexion",
    },
    {
        "id": "neck_extension",
        "name": "Neck Extension",
        "instruction": "Raise your head and look UP. Keep torso still. HOLD.",
        "expected_feature": "neck_flexion",
    },
    {
        "id": "near",
        "name": "Move Near Camera",
        "instruction": "Move upper body CLOSER without changing posture. HOLD.",
        "expected_feature": "eye_distance",
    },
    {
        "id": "far",
        "name": "Move Far Camera",
        "instruction": "Move upper body FARTHER without changing posture. HOLD.",
        "expected_feature": "eye_distance",
    },
]


# ============================================================
# DATA HELPERS
# ============================================================
def safe_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        if math.isfinite(value):
            return value
    return None


def get_feature(result, feature_name):
    """Read Detection Contract 1.0 feature value directly."""
    features = result.get("features") or {}
    feature = features.get(feature_name)

    if not isinstance(feature, dict):
        return safe_number(feature)

    if feature.get("valid") is False:
        return None

    return safe_number(feature.get("value"))


def context_is_valid(result):
    context = result.get("context") or {}
    return context.get("allow_posture_evaluation") is True


def get_context_state(result):
    context = result.get("context") or {}
    return str(context.get("state", "UNKNOWN"))


def get_pose_points(result):
    landmarks = result.get("landmarks") or {}
    points = landmarks.get("pose")
    return points if isinstance(points, dict) else {}


def get_face_points(result):
    landmarks = result.get("landmarks") or {}
    points = landmarks.get("face")
    return points if isinstance(points, dict) else {}


def point_xy(point):
    if not isinstance(point, dict):
        return None
    try:
        x = float(point["x"])
        y = float(point["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return int(round(x)), int(round(y))


def midpoint_xy(point_a, point_b):
    a = point_xy(point_a)
    b = point_xy(point_b)
    if a is None or b is None:
        return None
    return int(round((a[0] + b[0]) / 2)), int(round((a[1] + b[1]) / 2))


def calculate_median(values):
    return float(median(values)) if values else None


def calculate_min(values):
    return float(min(values)) if values else None


def calculate_max(values):
    return float(max(values)) if values else None


def calculate_delta(current, reference):
    if current is None or reference is None:
        return None
    return current - reference


def format_value(value, decimals=2):
    return "N/A" if value is None else f"{value:.{decimals}f}"


# ============================================================
# DRAW HELPERS
# ============================================================
def draw_text(frame, text, x, y, scale=0.55, thickness=1):
    cv2.putText(
        frame,
        str(text),
        (int(x), int(y)),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def draw_point(frame, point, label=None, radius=5):
    if point is None:
        return
    cv2.circle(frame, point, radius + 2, (0, 0, 0), -1)
    cv2.circle(frame, point, radius, (255, 255, 255), -1)
    if label:
        draw_text(frame, label, point[0] + 8, point[1] - 8, 0.42, 1)


def draw_line(frame, point_a, point_b, thickness=3):
    if point_a is None or point_b is None:
        return
    cv2.line(frame, point_a, point_b, (255, 255, 255), thickness, cv2.LINE_AA)


def draw_horizontal_reference(frame, center, half_length=100):
    if center is None:
        return
    x, y = center
    cv2.line(
        frame,
        (x - half_length, y),
        (x + half_length, y),
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )


def draw_vertical_reference(frame, center, half_length=90):
    if center is None:
        return
    x, y = center
    cv2.line(
        frame,
        (x, y - half_length),
        (x, y + half_length),
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )


# ============================================================
# FEATURE GEOMETRY
# ============================================================
def draw_shoulder_tilt_geometry(frame, result, value):
    """
    EXACT production geometry:
    shoulder_tilt = angle(left_shoulder -> right_shoulder)
    """
    pose = get_pose_points(result)
    left = point_xy(pose.get("left_shoulder"))
    right = point_xy(pose.get("right_shoulder"))

    if left is None or right is None:
        return

    draw_point(frame, left, "L Shoulder")
    draw_point(frame, right, "R Shoulder")
    draw_line(frame, left, right, 4)

    center = (
        int((left[0] + right[0]) / 2),
        int((left[1] + right[1]) / 2),
    )
    draw_horizontal_reference(frame, center, 120)
    draw_text(
        frame,
        f"Shoulder line = {format_value(value)} deg",
        center[0] + 10,
        center[1] - 18,
        0.52,
        2,
    )


def draw_neck_lateral_geometry(frame, result, value):
    """
    EXACT production geometry:
    neck_lateral_tilt = ear_line_angle - shoulder_line_angle
    """
    pose = get_pose_points(result)

    left_ear = point_xy(pose.get("left_ear"))
    right_ear = point_xy(pose.get("right_ear"))
    left_shoulder = point_xy(pose.get("left_shoulder"))
    right_shoulder = point_xy(pose.get("right_shoulder"))

    if any(
        p is None
        for p in (left_ear, right_ear, left_shoulder, right_shoulder)
    ):
        return

    draw_point(frame, left_ear, "L Ear")
    draw_point(frame, right_ear, "R Ear")
    draw_point(frame, left_shoulder, "L Shoulder")
    draw_point(frame, right_shoulder, "R Shoulder")

    draw_line(frame, left_ear, right_ear, 4)
    draw_line(frame, left_shoulder, right_shoulder, 3)

    ear_center = (
        int((left_ear[0] + right_ear[0]) / 2),
        int((left_ear[1] + right_ear[1]) / 2),
    )
    shoulder_center = (
        int((left_shoulder[0] + right_shoulder[0]) / 2),
        int((left_shoulder[1] + right_shoulder[1]) / 2),
    )

    draw_horizontal_reference(frame, ear_center, 90)
    draw_horizontal_reference(frame, shoulder_center, 120)

    draw_text(
        frame,
        "Neck lateral = Ear angle - Shoulder angle",
        25,
        frame.shape[0] - 65,
        0.52,
        2,
    )
    draw_text(
        frame,
        f"Relative neck tilt = {format_value(value)} deg",
        25,
        frame.shape[0] - 35,
        0.58,
        2,
    )


def draw_neck_flexion_geometry(frame, result, value):
    """
    IMPORTANT:
    Production neck_flexion is NOT calculated from a 2D landmark line.

    Actual calculation:
      MediaPipe Facial Transformation Matrix
      -> remove scale / obtain rotation matrix
      -> Euler pitch

    nose_tip -> chin below is only a VISUAL GUIDE.
    """
    face = get_face_points(result)
    nose = point_xy(face.get("nose_tip"))
    chin = point_xy(face.get("chin"))

    if nose is not None and chin is not None:
        draw_point(frame, nose, "Nose")
        draw_point(frame, chin, "Chin")
        draw_line(frame, nose, chin, 3)

        center = (
            int((nose[0] + chin[0]) / 2),
            int((nose[1] + chin[1]) / 2),
        )
        draw_vertical_reference(frame, center, 100)

    draw_text(frame, "Neck Flexion / Extension", 25, frame.shape[0] - 95, 0.58, 2)
    draw_text(
        frame,
        f"Pitch = {format_value(value)} deg",
        25,
        frame.shape[0] - 65,
        0.58,
        2,
    )
    draw_text(
        frame,
        "Actual metric: Facial Transformation Matrix -> Rotation -> Pitch",
        25,
        frame.shape[0] - 35,
        0.46,
        1,
    )


def draw_eye_distance_geometry(frame, result, value):
    """
    EXACT production geometry:

    left_eye_center  = midpoint(left_eye_outer, left_eye_inner)
    right_eye_center = midpoint(right_eye_inner, right_eye_outer)
    eye_distance_px  = Euclidean distance(left_eye_center, right_eye_center)
    """
    face = get_face_points(result)

    left_outer_raw = face.get("left_eye_outer")
    left_inner_raw = face.get("left_eye_inner")
    right_inner_raw = face.get("right_eye_inner")
    right_outer_raw = face.get("right_eye_outer")

    left_outer = point_xy(left_outer_raw)
    left_inner = point_xy(left_inner_raw)
    right_inner = point_xy(right_inner_raw)
    right_outer = point_xy(right_outer_raw)

    left_center = midpoint_xy(left_outer_raw, left_inner_raw)
    right_center = midpoint_xy(right_inner_raw, right_outer_raw)

    if any(
        p is None
        for p in (
            left_outer,
            left_inner,
            right_inner,
            right_outer,
            left_center,
            right_center,
        )
    ):
        return

    draw_point(frame, left_outer, "L outer", 4)
    draw_point(frame, left_inner, "L inner", 4)
    draw_point(frame, right_inner, "R inner", 4)
    draw_point(frame, right_outer, "R outer", 4)

    draw_line(frame, left_outer, left_inner, 2)
    draw_line(frame, right_inner, right_outer, 2)

    draw_point(frame, left_center, "L Eye Center", 6)
    draw_point(frame, right_center, "R Eye Center", 6)
    draw_line(frame, left_center, right_center, 4)

    center = (
        int((left_center[0] + right_center[0]) / 2),
        int((left_center[1] + right_center[1]) / 2),
    )
    draw_text(
        frame,
        f"Inter-Eye Distance = {format_value(value)} px",
        center[0] - 115,
        center[1] - 20,
        0.50,
        2,
    )


def draw_feature_geometry(frame, result, feature_name, current_values):
    """Draw only the geometry relevant to the current test to avoid clutter."""
    if feature_name == "reference":
        draw_shoulder_tilt_geometry(
            frame,
            result,
            current_values.get("shoulder_tilt"),
        )
        draw_eye_distance_geometry(
            frame,
            result,
            current_values.get("eye_distance"),
        )

    elif feature_name == "shoulder_tilt":
        draw_shoulder_tilt_geometry(
            frame,
            result,
            current_values.get("shoulder_tilt"),
        )

    elif feature_name == "neck_lateral_tilt":
        draw_neck_lateral_geometry(
            frame,
            result,
            current_values.get("neck_lateral_tilt"),
        )

    elif feature_name == "neck_flexion":
        draw_neck_flexion_geometry(
            frame,
            result,
            current_values.get("neck_flexion"),
        )

    elif feature_name == "eye_distance":
        draw_eye_distance_geometry(
            frame,
            result,
            current_values.get("eye_distance"),
        )


# ============================================================
# LIVE / EVIDENCE PANELS
# ============================================================
def draw_live_panel(frame, test_case, result, valid_frames, feature_values):
    output = frame.copy()

    draw_feature_geometry(
        output,
        result,
        test_case["expected_feature"],
        feature_values,
    )

    overlay = output.copy()
    cv2.rectangle(overlay, (0, 0), (520, 330), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.60, output, 0.40, 0, output)

    y = 35
    draw_text(output, f"TEST: {test_case['name']}", 20, y, 0.68, 2)
    y += 32
    draw_text(
        output,
        f"Expected: {test_case['expected_feature']}",
        20,
        y,
        0.50,
        1,
    )
    y += 28
    draw_text(output, f"Context: {get_context_state(result)}", 20, y)
    y += 28
    draw_text(
        output,
        f"Valid Frames: {valid_frames}/{TARGET_VALID_FRAMES}",
        20,
        y,
    )
    y += 38

    for feature in FEATURE_NAMES:
        value = feature_values.get(feature)
        unit = "px" if feature == "eye_distance" else "deg"
        draw_text(
            output,
            f"{feature}: {format_value(value)} {unit}",
            20,
            y,
            0.50,
            1,
        )
        y += 27

    draw_text(output, "ESC = stop test", 20, 312, 0.46, 1)
    return output


def draw_evidence_panel(
    frame,
    result,
    test_case,
    statistics,
    deltas,
    valid_frames,
    total_frames,
):
    output = frame.copy()

    median_values = {
        feature: statistics[feature]["median"]
        for feature in FEATURE_NAMES
    }

    draw_feature_geometry(
        output,
        result,
        test_case["expected_feature"],
        median_values,
    )

    h, w = output.shape[:2]
    panel_width = min(610, w)

    overlay = output.copy()
    cv2.rectangle(overlay, (0, 0), (panel_width, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.68, output, 0.32, 0, output)

    y = 35
    draw_text(output, "POSTGUARD DETECTION VALIDATION", 20, y, 0.66, 2)
    y += 36
    draw_text(output, f"Pose: {test_case['name']}", 20, y, 0.56, 2)
    y += 28
    draw_text(
        output,
        f"Expected Feature: {test_case['expected_feature']}",
        20,
        y,
        0.49,
        1,
    )
    y += 27
    draw_text(output, f"Valid Frames: {valid_frames}/{total_frames}", 20, y, 0.49, 1)
    y += 38

    draw_text(output, "MEDIAN / RANGE", 20, y, 0.56, 2)
    y += 28

    for feature in FEATURE_NAMES:
        stats = statistics[feature]
        unit = "px" if feature == "eye_distance" else "deg"
        draw_text(
            output,
            (
                f"{feature}: {format_value(stats['median'])} {unit} "
                f"[{format_value(stats['min'])}, {format_value(stats['max'])}]"
            ),
            25,
            y,
            0.44,
            1,
        )
        y += 25

    y += 8
    draw_text(output, "CHANGE FROM NEUTRAL", 20, y, 0.56, 2)
    y += 28

    for feature in FEATURE_NAMES:
        delta = deltas.get(feature)
        unit = "px" if feature == "eye_distance" else "deg"
        text = (
            f"Delta {feature}: N/A"
            if delta is None
            else f"Delta {feature}: {delta:+.2f} {unit}"
        )
        draw_text(output, text, 25, y, 0.45, 1)
        y += 25

    return output


# ============================================================
# COUNTDOWN
# ============================================================
def countdown(cap, test_case):
    start = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        elapsed = time.time() - start
        remaining = max(0, COUNTDOWN_SECONDS - int(elapsed))

        preview = frame.copy()
        overlay = preview.copy()
        cv2.rectangle(overlay, (0, 0), (preview.shape[1], 220), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, preview, 0.45, 0, preview)

        draw_text(preview, test_case["name"], 30, 50, 0.88, 2)
        draw_text(preview, test_case["instruction"], 30, 95, 0.50, 1)
        draw_text(preview, f"Starting in {remaining}...", 30, 145, 0.95, 2)
        draw_text(
            preview,
            "Prepare pose and HOLD until 60 valid frames.",
            30,
            190,
            0.56,
            1,
        )

        cv2.imshow("PostGuard Detection Visual Validation", preview)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            return False
        if elapsed >= COUNTDOWN_SECONDS:
            return True


# ============================================================
# CAPTURE TEST
# ============================================================
def capture_test_case(cap, pipeline, test_case, neutral_reference):
    collected = {feature: [] for feature in FEATURE_NAMES}

    valid_frames = 0
    total_frames = 0
    representative_frame = None
    representative_result = None
    start_time = time.time()

    while (
        valid_frames < TARGET_VALID_FRAMES
        and time.time() - start_time < MAX_CAPTURE_SECONDS
    ):
        ok, frame = cap.read()
        if not ok:
            continue

        total_frames += 1
        result = pipeline.process_frame(frame)

        if not isinstance(result, dict):
            continue

        current_values = {
            feature: get_feature(result, feature)
            for feature in FEATURE_NAMES
        }

        preview = draw_live_panel(
            frame,
            test_case,
            result,
            valid_frames,
            current_values,
        )
        cv2.imshow("PostGuard Detection Visual Validation", preview)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            return None

        if not context_is_valid(result):
            continue

        if not any(value is not None for value in current_values.values()):
            continue

        valid_frames += 1

        if representative_frame is None and valid_frames >= TARGET_VALID_FRAMES // 2:
            representative_frame = frame.copy()
            representative_result = result

        for feature in FEATURE_NAMES:
            value = current_values.get(feature)
            if value is not None:
                collected[feature].append(value)

    statistics = {}
    medians = {}

    for feature in FEATURE_NAMES:
        values = collected[feature]
        statistics[feature] = {
            "median": calculate_median(values),
            "min": calculate_min(values),
            "max": calculate_max(values),
            "samples": len(values),
        }
        medians[feature] = statistics[feature]["median"]

    deltas = {}
    if neutral_reference is None:
        for feature in FEATURE_NAMES:
            deltas[feature] = 0.0 if medians[feature] is not None else None
    else:
        for feature in FEATURE_NAMES:
            deltas[feature] = calculate_delta(
                medians[feature],
                neutral_reference.get(feature),
            )

    image_path = None
    if representative_frame is not None and representative_result is not None:
        evidence = draw_evidence_panel(
            representative_frame,
            representative_result,
            test_case,
            statistics,
            deltas,
            valid_frames,
            total_frames,
        )
        image_path = IMAGE_DIR / f"{test_case['id']}.png"
        cv2.imwrite(str(image_path), evidence)

    print("\n" + "-" * 80)
    print(f"RESULT: {test_case['name']}")
    print(f"Valid frames: {valid_frames}/{total_frames}")

    for feature in FEATURE_NAMES:
        stats = statistics[feature]
        print(
            f"{feature:22s} "
            f"Median={format_value(stats['median']):>8s} "
            f"Min={format_value(stats['min']):>8s} "
            f"Max={format_value(stats['max']):>8s} "
            f"Samples={stats['samples']:>3d} "
            f"Delta={format_value(deltas[feature]):>8s}"
        )

    print("-" * 80)

    return {
        "test_id": test_case["id"],
        "test_name": test_case["name"],
        "expected_feature": test_case["expected_feature"],
        "valid_frames": valid_frames,
        "total_frames": total_frames,
        "statistics": statistics,
        "medians": medians,
        "deltas": deltas,
        "image_path": str(image_path) if image_path else "",
    }


# ============================================================
# CSV
# ============================================================
def save_csv(results):
    fields = [
        "test_id",
        "test_name",
        "expected_feature",
        "valid_frames",
        "total_frames",
        "valid_ratio",
        "shoulder_tilt_median",
        "shoulder_tilt_min",
        "shoulder_tilt_max",
        "delta_shoulder_tilt",
        "neck_lateral_tilt_median",
        "neck_lateral_tilt_min",
        "neck_lateral_tilt_max",
        "delta_neck_lateral_tilt",
        "neck_flexion_median",
        "neck_flexion_min",
        "neck_flexion_max",
        "delta_neck_flexion",
        "eye_distance_median",
        "eye_distance_min",
        "eye_distance_max",
        "delta_eye_distance",
        "image_path",
    ]

    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for result in results:
            total = result["total_frames"]
            valid = result["valid_frames"]

            row = {
                "test_id": result["test_id"],
                "test_name": result["test_name"],
                "expected_feature": result["expected_feature"],
                "valid_frames": valid,
                "total_frames": total,
                "valid_ratio": valid / total if total > 0 else 0.0,
                "image_path": result["image_path"],
            }

            for feature in FEATURE_NAMES:
                stats = result["statistics"][feature]
                row[f"{feature}_median"] = stats["median"]
                row[f"{feature}_min"] = stats["min"]
                row[f"{feature}_max"] = stats["max"]
                row[f"delta_{feature}"] = result["deltas"][feature]

            writer.writerow(row)


# ============================================================
# SUMMARY
# ============================================================
def print_summary(results):
    print("\n" + "=" * 100)
    print("POSTGUARD DETECTION VISUAL VALIDATION SUMMARY")
    print("=" * 100)

    for result in results:
        print(f"\n[{result['test_name']}]")
        print(f"Expected Feature : {result['expected_feature']}")
        print(f"Valid Frames     : {result['valid_frames']}/{result['total_frames']}")

        for feature in FEATURE_NAMES:
            stats = result["statistics"][feature]
            delta = result["deltas"][feature]
            print(
                f"{feature:22s} "
                f"Median={format_value(stats['median']):>8s} "
                f"Delta={format_value(delta):>8s}"
            )

    print("\n" + "=" * 100)
    print(f"CSV    : {CSV_PATH}")
    print(f"Images : {IMAGE_DIR}")
    print("=" * 100)


# ============================================================
# MAIN
# ============================================================
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    print("\nStarting PostGuard DetectionPipeline...")
    pipeline = DetectionPipeline()
    print("DetectionPipeline ready.")

    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {CAMERA_ID}")

    print(f"Camera {CAMERA_ID} opened.")
    print("\nESC = stop test")

    results = []
    neutral_reference = None

    try:
        for test_case in TEST_CASES:
            print("\n" + "=" * 70)
            print(test_case["name"])
            print(test_case["instruction"])
            print("=" * 70)

            if not countdown(cap, test_case):
                break

            result = capture_test_case(
                cap,
                pipeline,
                test_case,
                neutral_reference,
            )

            if result is None:
                break

            results.append(result)

            if test_case["id"] == "neutral":
                neutral_reference = dict(result["medians"])

                print("\nNEUTRAL REFERENCE SAVED")
                for feature in FEATURE_NAMES:
                    print(
                        f"{feature:22s}: "
                        f"{format_value(neutral_reference[feature])}"
                    )

                if all(value is None for value in neutral_reference.values()):
                    print("ERROR: No detection feature could be extracted.")
                    break

    finally:
        cap.release()
        try:
            pipeline.close()
        except Exception:
            pass
        cv2.destroyAllWindows()

    if results:
        save_csv(results)
        print_summary(results)


if __name__ == "__main__":
    main()
