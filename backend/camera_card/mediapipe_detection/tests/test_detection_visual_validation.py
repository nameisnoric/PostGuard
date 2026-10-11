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

# C:\project\PostGuard\backend
BACKEND_DIR = TEST_FILE.parents[3]

# C:\project\PostGuard\backend\camera_card
CAMERA_CARD_DIR = TEST_FILE.parents[2]

# รองรับทั้ง:
# camera_card.mediapipe_detection...
# mediapipe_detection...
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

# จำนวน valid frames ต่อท่า
TARGET_VALID_FRAMES = 60

# ถ้าเก็บไม่ครบภายในเวลานี้ จะสรุปเท่าที่ได้
MAX_CAPTURE_SECONDS = 20.0

OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "detection_visual_results"
)

IMAGE_DIR = OUTPUT_DIR / "images"

CSV_PATH = (
    OUTPUT_DIR
    / "detection_visual_results.csv"
)


# ============================================================
# TEST CASES
# ============================================================

TEST_CASES = [
    {
        "id": "neutral",
        "name": "Neutral",
        "instruction": (
            "Sit naturally, keep shoulders relaxed, "
            "and look straight."
        ),
        "expected_feature": "reference",
    },

    {
        "id": "shoulder_left",
        "name": "Shoulder Tilt Left",
        "instruction": (
            "Tilt the shoulder line LEFT. "
            "Keep your head as straight as possible."
        ),
        "expected_feature": "shoulder_tilt",
    },

    {
        "id": "shoulder_right",
        "name": "Shoulder Tilt Right",
        "instruction": (
            "Tilt the shoulder line RIGHT. "
            "Keep your head as straight as possible."
        ),
        "expected_feature": "shoulder_tilt",
    },

    {
        "id": "neck_left",
        "name": "Neck Tilt Left",
        "instruction": (
            "Tilt your HEAD LEFT. "
            "Keep both shoulders still."
        ),
        "expected_feature": "neck_lateral_tilt",
    },

    {
        "id": "neck_right",
        "name": "Neck Tilt Right",
        "instruction": (
            "Tilt your HEAD RIGHT. "
            "Keep both shoulders still."
        ),
        "expected_feature": "neck_lateral_tilt",
    },

    {
        "id": "neck_flexion",
        "name": "Neck Flexion",
        "instruction": (
            "Lower your head and look DOWN. "
            "Keep your torso still."
        ),
        "expected_feature": "neck_flexion",
    },

    {
        "id": "neck_extension",
        "name": "Neck Extension",
        "instruction": (
            "Raise your head and look UP. "
            "Keep your torso still."
        ),
        "expected_feature": "neck_flexion",
    },

    {
        "id": "near",
        "name": "Move Near Camera",
        "instruction": (
            "Move your upper body CLOSER to the camera "
            "without changing posture."
        ),
        "expected_feature": "eye_distance",
    },

    {
        "id": "far",
        "name": "Move Far Camera",
        "instruction": (
            "Move your upper body FARTHER from the camera "
            "without changing posture."
        ),
        "expected_feature": "eye_distance",
    },
]


FEATURE_NAMES = [
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
    "eye_distance",
]


# ============================================================
# POSSIBLE FEATURE NAMES
# ============================================================

# รองรับกรณี production code ใช้ชื่อ key ต่างออกไปเล็กน้อย
FEATURE_ALIASES = {
    "shoulder_tilt": [
        "shoulder_tilt",
        "shoulder_tilt_deg",
        "shoulder_angle",
        "shoulder_angle_deg",
    ],

    "neck_lateral_tilt": [
        "neck_lateral_tilt",
        "neck_lateral_tilt_deg",
        "neck_tilt",
        "neck_tilt_deg",
        "lateral_neck_tilt",
    ],

    "neck_flexion": [
        "neck_flexion",
        "neck_flexion_deg",
        "neck_pitch",
        "head_pitch",
        "pitch",
    ],

    "eye_distance": [
        "eye_distance",
        "eye_distance_px",
        "inter_eye_distance",
        "inter_eye_distance_px",
        "ipd",
        "ipd_px",
    ],
}


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_number(value):
    """
    แปลงค่าที่เป็นตัวเลขให้เป็น float

    ป้องกัน:
    - None
    - bool
    - NaN
    - infinity
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        number = float(value)

        if math.isfinite(number):
            return number

    return None


def extract_numeric_value(value):
    """
    รองรับ output หลายแบบ เช่น

    1)
    shoulder_tilt = 4.5

    2)
    shoulder_tilt = {
        "value": 4.5
    }

    3)
    shoulder_tilt = {
        "angle": 4.5,
        "valid": True
    }

    4)
    shoulder_tilt = {
        "raw": 4.5
    }
    """

    direct = safe_number(value)

    if direct is not None:
        return direct

    if not isinstance(value, dict):
        return None

    # ถ้ามี valid=False ชัดเจน
    # ไม่ควรเอาค่านั้นมาทดลอง
    if value.get("valid") is False:
        return None

    possible_value_keys = [
        "value",
        "angle",
        "angle_deg",
        "degrees",
        "deg",
        "raw",
        "score",
        "distance",
        "distance_px",
        "pixels",
        "px",
        "measurement",
    ]

    for key in possible_value_keys:

        if key not in value:
            continue

        number = safe_number(
            value.get(key)
        )

        if number is not None:
            return number

    return None


# ============================================================
# RECURSIVE FEATURE SEARCH
# ============================================================

def recursive_find_feature(data, aliases):
    """
    ค้นหา Feature ลงไปใน dictionary แบบ recursive

    ตัวอย่างที่รองรับ:

    result["features"]["shoulder_tilt"]

    result["posture"]["shoulder_tilt"]

    result["features"]["shoulder_tilt"]["value"]

    result["posture"]["features"]["shoulder_tilt"]
    """

    if not isinstance(data, dict):
        return None

    # --------------------------------------------------------
    # 1. ค้นหา alias ใน dictionary ปัจจุบันก่อน
    # --------------------------------------------------------

    for alias in aliases:

        if alias in data:

            value = extract_numeric_value(
                data[alias]
            )

            if value is not None:
                return value

    # --------------------------------------------------------
    # 2. ถ้ายังไม่เจอ ค้น dictionary ชั้นล่าง
    # --------------------------------------------------------

    for child in data.values():

        if isinstance(child, dict):

            result = recursive_find_feature(
                child,
                aliases,
            )

            if result is not None:
                return result

    return None


def get_feature(result, feature_name):
    """
    ดึงค่าจริงจาก DetectionPipeline

    ไม่บังคับว่าค่าต้องอยู่:
        result["features"]

    เพราะ production output อาจซ้อน dictionary
    """

    aliases = FEATURE_ALIASES.get(
        feature_name,
        [feature_name],
    )

    # --------------------------------------------------------
    # วิธีที่ 1:
    # ลอง result["features"] ก่อน
    # --------------------------------------------------------

    features = result.get("features")

    if isinstance(features, dict):

        for alias in aliases:

            if alias in features:

                value = extract_numeric_value(
                    features[alias]
                )

                if value is not None:
                    return value

    # --------------------------------------------------------
    # วิธีที่ 2:
    # ค้นหา recursive ทั้ง output
    # --------------------------------------------------------

    return recursive_find_feature(
        result,
        aliases,
    )


# ============================================================
# CONTEXT
# ============================================================

def context_is_valid(result):
    """
    รับเฉพาะ Frame ที่ Context Filter อนุญาตให้
    posture evaluation
    """

    context = result.get("context") or {}

    allow = context.get(
        "allow_posture_evaluation"
    )

    if allow is True:
        return True

    return False


def get_context_state(result):
    context = result.get("context") or {}

    state = context.get("state")

    if state is None:
        return "UNKNOWN"

    return str(state)


# ============================================================
# DEBUG OUTPUT
# ============================================================

def describe_structure(data, prefix="", depth=0, max_depth=4):
    """
    แสดงโครงสร้าง DetectionPipeline โดยไม่ print landmark
    หลายร้อยค่าออกมาทั้งหมด

    ใช้กรณี test หา feature ไม่เจอ
    """

    if depth > max_depth:
        return

    if not isinstance(data, dict):
        return

    for key, value in data.items():

        current_path = (
            f"{prefix}.{key}"
            if prefix
            else str(key)
        )

        if isinstance(value, dict):

            print(
                f"  {current_path}: dict"
            )

            describe_structure(
                value,
                current_path,
                depth + 1,
                max_depth,
            )

        elif isinstance(value, (list, tuple)):

            print(
                f"  {current_path}: "
                f"{type(value).__name__}"
                f"(len={len(value)})"
            )

        else:

            value_text = repr(value)

            if len(value_text) > 100:
                value_text = (
                    value_text[:100]
                    + "..."
                )

            print(
                f"  {current_path}: "
                f"{type(value).__name__} "
                f"= {value_text}"
            )


# ============================================================
# STATISTICS
# ============================================================

def calculate_median(values):

    if not values:
        return None

    return float(
        median(values)
    )


def calculate_min(values):

    if not values:
        return None

    return float(
        min(values)
    )


def calculate_max(values):

    if not values:
        return None

    return float(
        max(values)
    )


def calculate_delta(current, reference):

    if current is None:
        return None

    if reference is None:
        return None

    return current - reference


def format_value(value, decimals=2):

    if value is None:
        return "N/A"

    return f"{value:.{decimals}f}"


# ============================================================
# DRAWING
# ============================================================

def draw_text(
    frame,
    text,
    x,
    y,
    scale=0.60,
    thickness=2,
):

    cv2.putText(
        frame,
        str(text),
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def draw_live_panel(
    frame,
    test_case,
    result,
    valid_frames,
    feature_values,
):
    """
    Overlay ตอนกำลังทดสอบ
    """

    output = frame.copy()

    overlay = output.copy()

    cv2.rectangle(
        overlay,
        (0, 0),
        (520, 330),
        (0, 0, 0),
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.60,
        output,
        0.40,
        0,
        output,
    )

    y = 35

    draw_text(
        output,
        f"TEST: {test_case['name']}",
        20,
        y,
        0.70,
    )

    y += 35

    draw_text(
        output,
        f"Context: {get_context_state(result)}",
        20,
        y,
    )

    y += 30

    draw_text(
        output,
        f"Valid Frames: {valid_frames}/{TARGET_VALID_FRAMES}",
        20,
        y,
    )

    y += 45

    for feature in FEATURE_NAMES:

        value = feature_values.get(
            feature
        )

        unit = (
            "px"
            if feature == "eye_distance"
            else "deg"
        )

        draw_text(
            output,
            (
                f"{feature}: "
                f"{format_value(value)} {unit}"
            ),
            20,
            y,
            0.55,
            1,
        )

        y += 30

    draw_text(
        output,
        "ESC = stop test",
        20,
        315,
        0.50,
        1,
    )

    return output


def draw_evidence_panel(
    frame,
    test_case,
    statistics,
    deltas,
    valid_frames,
    total_frames,
):
    """
    สร้างภาพหลักฐานหลังจบแต่ละท่า
    """

    output = frame.copy()

    h, w = output.shape[:2]

    panel_width = min(
        580,
        w,
    )

    overlay = output.copy()

    cv2.rectangle(
        overlay,
        (0, 0),
        (panel_width, h),
        (0, 0, 0),
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.68,
        output,
        0.32,
        0,
        output,
    )

    y = 35

    draw_text(
        output,
        "POSTGUARD DETECTION VALIDATION",
        20,
        y,
        0.70,
    )

    y += 38

    draw_text(
        output,
        f"Pose: {test_case['name']}",
        20,
        y,
    )

    y += 30

    draw_text(
        output,
        (
            "Expected Feature: "
            f"{test_case['expected_feature']}"
        ),
        20,
        y,
        0.55,
    )

    y += 30

    draw_text(
        output,
        (
            f"Valid Frames: "
            f"{valid_frames}/{total_frames}"
        ),
        20,
        y,
        0.55,
    )

    y += 45

    draw_text(
        output,
        "MEDIAN / RANGE",
        20,
        y,
        0.60,
    )

    y += 30

    for feature in FEATURE_NAMES:

        stats = statistics.get(
            feature,
            {}
        )

        med = stats.get("median")
        minimum = stats.get("min")
        maximum = stats.get("max")

        unit = (
            "px"
            if feature == "eye_distance"
            else "deg"
        )

        text = (
            f"{feature}: "
            f"{format_value(med)} {unit} "
            f"[{format_value(minimum)}, "
            f"{format_value(maximum)}]"
        )

        draw_text(
            output,
            text,
            25,
            y,
            0.48,
            1,
        )

        y += 28

    y += 15

    draw_text(
        output,
        "CHANGE FROM NEUTRAL",
        20,
        y,
        0.60,
    )

    y += 30

    for feature in FEATURE_NAMES:

        delta = deltas.get(
            feature
        )

        unit = (
            "px"
            if feature == "eye_distance"
            else "deg"
        )

        if delta is None:
            text = (
                f"Delta {feature}: N/A"
            )
        else:
            text = (
                f"Delta {feature}: "
                f"{delta:+.2f} {unit}"
            )

        draw_text(
            output,
            text,
            25,
            y,
            0.50,
            1,
        )

        y += 28

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

        elapsed = (
            time.time() - start
        )

        remaining = max(
            0,
            COUNTDOWN_SECONDS
            - int(elapsed)
        )

        preview = frame.copy()

        overlay = preview.copy()

        cv2.rectangle(
            overlay,
            (0, 0),
            (preview.shape[1], 220),
            (0, 0, 0),
            -1,
        )

        cv2.addWeighted(
            overlay,
            0.55,
            preview,
            0.45,
            0,
            preview,
        )

        draw_text(
            preview,
            test_case["name"],
            30,
            50,
            0.90,
        )

        draw_text(
            preview,
            test_case["instruction"],
            30,
            95,
            0.55,
        )

        draw_text(
            preview,
            f"Starting in {remaining}...",
            30,
            145,
            1.0,
        )

        draw_text(
            preview,
            "Prepare pose and HOLD STILL",
            30,
            190,
            0.60,
        )

        cv2.imshow(
            "PostGuard Detection Visual Validation",
            preview,
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key == 27:
            return False

        if elapsed >= COUNTDOWN_SECONDS:
            return True


# ============================================================
# CAPTURE TEST CASE
# ============================================================

def capture_test_case(
    cap,
    pipeline,
    test_case,
    neutral_reference,
):

    collected = {
        feature: []
        for feature in FEATURE_NAMES
    }

    valid_frames = 0
    total_frames = 0

    representative_frame = None

    start_time = time.time()

    structure_printed = False

    while (
        valid_frames < TARGET_VALID_FRAMES
        and (
            time.time() - start_time
            < MAX_CAPTURE_SECONDS
        )
    ):

        ok, frame = cap.read()

        if not ok:
            continue

        total_frames += 1

        # ====================================================
        # REAL POSTGUARD DETECTION
        # ====================================================

        result = pipeline.process_frame(
            frame
        )

        if result is None:
            continue

        if not isinstance(result, dict):
            print(
                "\nWARNING:"
                " DetectionPipeline did not return dict."
            )
            print(
                "Returned type:",
                type(result),
            )
            continue

        # ====================================================
        # READ FEATURES
        # ====================================================

        current_values = {}

        for feature in FEATURE_NAMES:

            current_values[feature] = (
                get_feature(
                    result,
                    feature,
                )
            )

        # ====================================================
        # AUTO DEBUG
        # ====================================================

        # ถ้าทุก feature ยัง N/A
        # print โครงสร้าง pipeline 1 ครั้ง
        if (
            not structure_printed
            and all(
                value is None
                for value
                in current_values.values()
            )
        ):

            print()
            print("=" * 80)
            print(
                "DETECTION PIPELINE STRUCTURE"
            )
            print("=" * 80)

            describe_structure(
                result
            )

            print("=" * 80)
            print()

            structure_printed = True

        # ====================================================
        # LIVE DISPLAY
        # ====================================================

        preview = draw_live_panel(
            frame,
            test_case,
            result,
            valid_frames,
            current_values,
        )

        cv2.imshow(
            "PostGuard Detection Visual Validation",
            preview,
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key == 27:
            return None

        # ====================================================
        # CONTEXT VALIDATION
        # ====================================================

        if not context_is_valid(
            result
        ):
            continue

        # ====================================================
        # FEATURE VALIDATION
        # ====================================================

        # ต้องมีอย่างน้อยหนึ่ง feature ที่อ่านได้
        # ถึงจะนับเป็น valid test frame
        has_feature = any(
            value is not None
            for value
            in current_values.values()
        )

        if not has_feature:
            continue

        valid_frames += 1

        # ====================================================
        # REPRESENTATIVE FRAME
        # ====================================================

        if (
            representative_frame is None
            and valid_frames
            >= TARGET_VALID_FRAMES // 2
        ):
            representative_frame = (
                frame.copy()
            )

        # ====================================================
        # COLLECT VALUES
        # ====================================================

        for feature in FEATURE_NAMES:

            value = current_values.get(
                feature
            )

            if value is not None:

                collected[
                    feature
                ].append(value)

    # ========================================================
    # STATISTICS
    # ========================================================

    statistics = {}

    medians = {}

    for feature in FEATURE_NAMES:

        values = collected[
            feature
        ]

        statistics[feature] = {
            "median": calculate_median(
                values
            ),
            "min": calculate_min(
                values
            ),
            "max": calculate_max(
                values
            ),
            "samples": len(values),
        }

        medians[feature] = (
            statistics[
                feature
            ]["median"]
        )

    # ========================================================
    # DELTA FROM NEUTRAL
    # ========================================================

    deltas = {}

    if neutral_reference is None:

        for feature in FEATURE_NAMES:

            if medians[feature] is None:
                deltas[feature] = None
            else:
                deltas[feature] = 0.0

    else:

        for feature in FEATURE_NAMES:

            deltas[feature] = (
                calculate_delta(
                    medians[feature],
                    neutral_reference.get(
                        feature
                    ),
                )
            )

    # ========================================================
    # SAVE IMAGE
    # ========================================================

    image_path = None

    if representative_frame is not None:

        evidence = (
            draw_evidence_panel(
                representative_frame,
                test_case,
                statistics,
                deltas,
                valid_frames,
                total_frames,
            )
        )

        image_path = (
            IMAGE_DIR
            / f"{test_case['id']}.png"
        )

        cv2.imwrite(
            str(image_path),
            evidence,
        )

    # ========================================================
    # TERMINAL RESULT
    # ========================================================

    print()
    print("-" * 70)

    print(
        f"RESULT: {test_case['name']}"
    )

    print(
        f"Valid frames: "
        f"{valid_frames}/"
        f"{total_frames}"
    )

    for feature in FEATURE_NAMES:

        stats = statistics[
            feature
        ]

        print(
            f"{feature:22s} "
            f"Median="
            f"{format_value(stats['median']):>8s} "
            f"Min="
            f"{format_value(stats['min']):>8s} "
            f"Max="
            f"{format_value(stats['max']):>8s} "
            f"Samples="
            f"{stats['samples']:>3d} "
            f"Delta="
            f"{format_value(deltas[feature]):>8s}"
        )

    print("-" * 70)

    return {
        "test_id":
            test_case["id"],

        "test_name":
            test_case["name"],

        "expected_feature":
            test_case["expected_feature"],

        "valid_frames":
            valid_frames,

        "total_frames":
            total_frames,

        "statistics":
            statistics,

        "medians":
            medians,

        "deltas":
            deltas,

        "image_path":
            str(image_path)
            if image_path
            else "",
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

    with CSV_PATH.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()

        for result in results:

            total = result[
                "total_frames"
            ]

            valid = result[
                "valid_frames"
            ]

            if total > 0:
                valid_ratio = (
                    valid / total
                )
            else:
                valid_ratio = 0.0

            row = {
                "test_id":
                    result["test_id"],

                "test_name":
                    result["test_name"],

                "expected_feature":
                    result[
                        "expected_feature"
                    ],

                "valid_frames":
                    valid,

                "total_frames":
                    total,

                "valid_ratio":
                    valid_ratio,

                "image_path":
                    result[
                        "image_path"
                    ],
            }

            for feature in FEATURE_NAMES:

                stats = result[
                    "statistics"
                ][feature]

                row[
                    f"{feature}_median"
                ] = stats["median"]

                row[
                    f"{feature}_min"
                ] = stats["min"]

                row[
                    f"{feature}_max"
                ] = stats["max"]

                row[
                    f"delta_{feature}"
                ] = result[
                    "deltas"
                ][feature]

            writer.writerow(
                row
            )


# ============================================================
# FINAL SUMMARY
# ============================================================

def print_summary(results):

    print()
    print("=" * 100)

    print(
        "POSTGUARD DETECTION "
        "VISUAL VALIDATION SUMMARY"
    )

    print("=" * 100)

    for result in results:

        print()

        print(
            f"[{result['test_name']}]"
        )

        print(
            "Expected Feature : "
            f"{result['expected_feature']}"
        )

        print(
            "Valid Frames     : "
            f"{result['valid_frames']}/"
            f"{result['total_frames']}"
        )

        for feature in FEATURE_NAMES:

            stats = result[
                "statistics"
            ][feature]

            delta = result[
                "deltas"
            ][feature]

            print(
                f"{feature:22s} "
                f"Median="
                f"{format_value(stats['median']):>8s} "
                f"Delta="
                f"{format_value(delta):>8s}"
            )

    print()
    print("=" * 100)

    print(
        f"CSV    : {CSV_PATH}"
    )

    print(
        f"Images : {IMAGE_DIR}"
    )

    print("=" * 100)


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # CREATE OUTPUT DIRECTORY
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # START DETECTION PIPELINE
    # --------------------------------------------------------

    print()
    print(
        "Starting PostGuard DetectionPipeline..."
    )

    pipeline = DetectionPipeline()

    print(
        "DetectionPipeline ready."
    )

    # --------------------------------------------------------
    # OPEN CAMERA
    # --------------------------------------------------------

    cap = cv2.VideoCapture(
        CAMERA_ID,
        cv2.CAP_DSHOW,
    )

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        FRAME_WIDTH,
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        FRAME_HEIGHT,
    )

    if not cap.isOpened():

        raise RuntimeError(
            f"Cannot open camera "
            f"{CAMERA_ID}"
        )

    print(
        f"Camera {CAMERA_ID} opened."
    )

    print()
    print(
        "ESC = stop test"
    )

    results = []

    neutral_reference = None

    try:

        for test_case in TEST_CASES:

            print()
            print("=" * 70)

            print(
                test_case["name"]
            )

            print(
                test_case[
                    "instruction"
                ]
            )

            print("=" * 70)

            ready = countdown(
                cap,
                test_case,
            )

            if not ready:
                break

            result = (
                capture_test_case(
                    cap,
                    pipeline,
                    test_case,
                    neutral_reference,
                )
            )

            if result is None:
                break

            results.append(
                result
            )

            # =================================================
            # SAVE NEUTRAL REFERENCE
            # =================================================

            if (
                test_case["id"]
                == "neutral"
            ):

                neutral_reference = dict(
                    result["medians"]
                )

                print()
                print(
                    "NEUTRAL REFERENCE SAVED"
                )

                for feature in FEATURE_NAMES:

                    print(
                        f"{feature:22s}: "
                        f"{format_value(
                            neutral_reference[
                                feature
                            ]
                        )}"
                    )

                # ถ้า Neutral ยังไม่มีค่าเลย
                # ไม่ควรทำ test ต่อ
                if all(
                    value is None
                    for value
                    in neutral_reference.values()
                ):

                    print()
                    print(
                        "ERROR:"
                        " No detection feature "
                        "could be extracted."
                    )

                    print(
                        "Check the "
                        "'DETECTION PIPELINE STRUCTURE' "
                        "printed above."
                    )

                    break

    finally:

        cap.release()

        cv2.destroyAllWindows()

    # --------------------------------------------------------
    # SAVE RESULTS
    # --------------------------------------------------------

    if results:

        save_csv(
            results
        )

        print_summary(
            results
        )


if __name__ == "__main__":
    main()