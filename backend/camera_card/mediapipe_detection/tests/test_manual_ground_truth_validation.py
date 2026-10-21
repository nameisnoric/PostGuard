from __future__ import annotations

import csv
import math
import sys
import time
from pathlib import Path

import cv2


# ==========================================================
# PATH SETUP
# ==========================================================

THIS_FILE = Path(__file__).resolve()

# backend/
BACKEND_DIR = THIS_FILE.parents[3]

# backend/camera_card/
CAMERA_CARD_DIR = THIS_FILE.parents[2]

for path in (
    BACKEND_DIR,
    CAMERA_CARD_DIR,
):
    path_text = str(path)

    if path_text not in sys.path:
        sys.path.insert(
            0,
            path_text,
        )


# ==========================================================
# POSTGUARD
# ==========================================================

from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)


# ==========================================================
# CONFIG
# ==========================================================

CAMERA_ID = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

WINDOW_NAME = (
    "PostGuard Manual Ground Truth Validation"
)

OUTPUT_DIR = (
    THIS_FILE.parent
    / "manual_ground_truth_results"
)

IMAGE_DIR = (
    OUTPUT_DIR
    / "images"
)

CSV_PATH = (
    OUTPUT_DIR
    / "manual_ground_truth_results.csv"
)


# ==========================================================
# COLOR
# OpenCV = BGR
# ==========================================================

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

GREEN = (0, 255, 0)       # MediaPipe
YELLOW = (0, 255, 255)    # Manual Ground Truth
CYAN = (255, 255, 0)
RED = (0, 0, 255)


# ==========================================================
# FEATURE CONFIG
# ==========================================================

FEATURES = {

    "1": {
        "feature":
            "shoulder_tilt",

        "title":
            "Shoulder Tilt",

        "manual_points": [
            "Left Shoulder",
            "Right Shoulder",
        ],
    },


    "2": {
        "feature":
            "neck_lateral_tilt",

        "title":
            "Neck Lateral Tilt",

        "manual_points": [
            "Left Ear",
            "Right Ear",
            "Left Shoulder",
            "Right Shoulder",
        ],
    },
}


# ==========================================================
# RUNTIME CLICK STATE
# ==========================================================

clicked_points = []

expected_point_names = []


# ==========================================================
# BASIC UI
# ==========================================================

def put(
    frame,
    text,
    position,
    color=WHITE,
    scale=0.55,
    thickness=1,
):
    cv2.putText(
        frame,
        str(text),
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_point(
    frame,
    point,
    color,
    label=None,
    radius=6,
):
    if point is None:
        return

    x = int(
        round(
            point[0]
        )
    )

    y = int(
        round(
            point[1]
        )
    )

    cv2.circle(
        frame,
        (x, y),
        radius + 2,
        BLACK,
        -1,
        cv2.LINE_AA,
    )

    cv2.circle(
        frame,
        (x, y),
        radius,
        color,
        -1,
        cv2.LINE_AA,
    )

    if label:

        put(
            frame,
            label,
            (
                x + 9,
                y - 9,
            ),
            color,
            0.46,
            1,
        )


def draw_line(
    frame,
    point_a,
    point_b,
    color,
    thickness=2,
):
    if (
        point_a is None
        or point_b is None
    ):
        return

    a = (
        int(round(point_a[0])),
        int(round(point_a[1])),
    )

    b = (
        int(round(point_b[0])),
        int(round(point_b[1])),
    )

    cv2.line(
        frame,
        a,
        b,
        color,
        thickness,
        cv2.LINE_AA,
    )


# ==========================================================
# GEOMETRY
# ==========================================================

def normalize_line_angle(
    angle,
):
    """
    Normalize ให้แนวนอนอยู่ใกล้ 0°

    Result:
        -90 .. +90
    """

    angle = float(
        angle
    )

    if angle > 90.0:
        angle -= 180.0

    elif angle < -90.0:
        angle += 180.0

    return angle


def line_angle(
    point_a,
    point_b,
):
    """
    angle(
        point_a -> point_b
    )
    """

    dx = (
        float(
            point_b[0]
        )
        -
        float(
            point_a[0]
        )
    )

    dy = (
        float(
            point_b[1]
        )
        -
        float(
            point_a[1]
        )
    )

    if (
        dx == 0.0
        and dy == 0.0
    ):
        return None

    angle = math.degrees(
        math.atan2(
            dy,
            dx,
        )
    )

    return normalize_line_angle(
        angle
    )


def normalize_difference(
    value,
):
    """
    Normalize angular difference
    ให้อยู่ช่วง -90..+90 โดยประมาณ
    """

    value = float(
        value
    )

    while value > 90.0:
        value -= 180.0

    while value < -90.0:
        value += 180.0

    return value


def manual_shoulder_tilt(
    points,
):
    """
    points:
        0 = Left Shoulder
        1 = Right Shoulder
    """

    if len(points) < 2:
        return None

    return line_angle(
        points[0],
        points[1],
    )


def manual_neck_lateral(
    points,
):
    """
    points:
        0 = Left Ear
        1 = Right Ear
        2 = Left Shoulder
        3 = Right Shoulder

    Formula:
        Ear Line Angle
        -
        Shoulder Line Angle
    """

    if len(points) < 4:
        return None

    ear_angle = line_angle(
        points[0],
        points[1],
    )

    shoulder_angle = line_angle(
        points[2],
        points[3],
    )

    if (
        ear_angle is None
        or shoulder_angle is None
    ):
        return None

    return normalize_difference(
        ear_angle
        -
        shoulder_angle
    )


# ==========================================================
# POSTGUARD RESULT HELPERS
# ==========================================================

def get_feature_value(
    result,
    feature_name,
):
    if not isinstance(
        result,
        dict,
    ):
        return None

    features = (
        result.get(
            "features"
        )
        or {}
    )

    feature = (
        features.get(
            feature_name
        )
    )

    if not isinstance(
        feature,
        dict,
    ):
        return None

    if feature.get(
        "valid"
    ) is not True:
        return None

    value = (
        feature.get(
            "value"
        )
    )

    if not isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return None

    value = float(
        value
    )

    if not math.isfinite(
        value
    ):
        return None

    return value


def get_pose_point(
    result,
    name,
):
    """
    DetectionPipeline:
        result["landmarks"]["pose"][name]
    """

    if not isinstance(
        result,
        dict,
    ):
        return None

    landmarks = (
        result.get(
            "landmarks"
        )
        or {}
    )

    pose = (
        landmarks.get(
            "pose"
        )
        or {}
    )

    point = (
        pose.get(
            name
        )
    )

    if not isinstance(
        point,
        dict,
    ):
        return None

    try:

        return (
            float(
                point[
                    "x"
                ]
            ),
            float(
                point[
                    "y"
                ]
            ),
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return None


# ==========================================================
# MOUSE CALLBACK
# ==========================================================

def mouse_callback(
    event,
    x,
    y,
    flags,
    userdata,
):
    """
    Left Click:
        เพิ่ม Manual Ground Truth Point

    Right Click:
        ลบจุดล่าสุด
    """

    global clicked_points


    if event == cv2.EVENT_LBUTTONDOWN:

        if len(
            clicked_points
        ) < len(
            expected_point_names
        ):

            clicked_points.append(
                (
                    int(x),
                    int(y),
                )
            )


    elif event == cv2.EVENT_RBUTTONDOWN:

        if clicked_points:

            clicked_points.pop()


# ==========================================================
# DRAW MEDIAPIPE GEOMETRY
# ==========================================================

def draw_mediapipe_geometry(
    frame,
    result,
    feature_name,
):
    """
    สีเขียว = MediaPipe / PostGuard
    """

    output = frame.copy()


    if (
        feature_name
        == "shoulder_tilt"
    ):

        left = get_pose_point(
            result,
            "left_shoulder",
        )

        right = get_pose_point(
            result,
            "right_shoulder",
        )

        draw_point(
            output,
            left,
            GREEN,
            "MP Left Shoulder",
        )

        draw_point(
            output,
            right,
            GREEN,
            "MP Right Shoulder",
        )

        draw_line(
            output,
            left,
            right,
            GREEN,
            3,
        )


    elif (
        feature_name
        == "neck_lateral_tilt"
    ):

        left_ear = get_pose_point(
            result,
            "left_ear",
        )

        right_ear = get_pose_point(
            result,
            "right_ear",
        )

        left_shoulder = get_pose_point(
            result,
            "left_shoulder",
        )

        right_shoulder = get_pose_point(
            result,
            "right_shoulder",
        )

        for point, label in (
            (
                left_ear,
                "MP Left Ear",
            ),
            (
                right_ear,
                "MP Right Ear",
            ),
            (
                left_shoulder,
                "MP Left Shoulder",
            ),
            (
                right_shoulder,
                "MP Right Shoulder",
            ),
        ):

            draw_point(
                output,
                point,
                GREEN,
                label,
            )

        draw_line(
            output,
            left_ear,
            right_ear,
            GREEN,
            3,
        )

        draw_line(
            output,
            left_shoulder,
            right_shoulder,
            GREEN,
            3,
        )


    return output


# ==========================================================
# DRAW MANUAL GEOMETRY
# ==========================================================

def draw_manual_geometry(
    frame,
    feature_name,
):
    """
    สีเหลือง = จุดที่ผู้ทดสอบ Click เอง
    """

    output = frame.copy()


    for index, point in enumerate(
        clicked_points
    ):

        label = (
            expected_point_names[
                index
            ]
            if index
            < len(
                expected_point_names
            )
            else f"P{index + 1}"
        )

        draw_point(
            output,
            point,
            YELLOW,
            f"GT {label}",
        )


    if (
        feature_name
        == "shoulder_tilt"
        and
        len(
            clicked_points
        ) >= 2
    ):

        draw_line(
            output,
            clicked_points[0],
            clicked_points[1],
            YELLOW,
            3,
        )


    elif (
        feature_name
        == "neck_lateral_tilt"
        and
        len(
            clicked_points
        ) >= 4
    ):

        draw_line(
            output,
            clicked_points[0],
            clicked_points[1],
            YELLOW,
            3,
        )

        draw_line(
            output,
            clicked_points[2],
            clicked_points[3],
            YELLOW,
            3,
        )


    return output


# ==========================================================
# MANUAL VALUE
# ==========================================================

def calculate_manual_value(
    feature_name,
):
    if (
        feature_name
        == "shoulder_tilt"
    ):

        return manual_shoulder_tilt(
            clicked_points
        )


    if (
        feature_name
        == "neck_lateral_tilt"
    ):

        return manual_neck_lateral(
            clicked_points
        )


    return None


# ==========================================================
# MAIN MENU
# ==========================================================

def draw_menu(
    frame,
):
    output = frame.copy()


    cv2.rectangle(
        output,
        (
            0,
            0,
        ),
        (
            850,
            330,
        ),
        (
            0,
            0,
            0,
        ),
        -1,
    )


    put(
        output,
        (
            "POSTGUARD MANUAL "
            "GROUND TRUTH VALIDATION"
        ),
        (
            20,
            40,
        ),
        YELLOW,
        0.72,
        2,
    )


    put(
        output,
        (
            "1 = Shoulder Tilt"
        ),
        (
            20,
            100,
        ),
        WHITE,
        0.62,
        2,
    )


    put(
        output,
        (
            "2 = Neck Lateral Tilt"
        ),
        (
            20,
            140,
        ),
        WHITE,
        0.62,
        2,
    )


    put(
        output,
        (
            "After selecting, press SPACE "
            "to freeze one frame."
        ),
        (
            20,
            200,
        ),
        CYAN,
        0.54,
        1,
    )


    put(
        output,
        (
            "Green = MediaPipe   "
            "Yellow = Manual Ground Truth"
        ),
        (
            20,
            240,
        ),
        WHITE,
        0.50,
        1,
    )


    put(
        output,
        (
            "Q / ESC = Exit"
        ),
        (
            20,
            290,
        ),
        WHITE,
        0.50,
        1,
    )


    return output


# ==========================================================
# SELECT AND FREEZE FRAME
# ==========================================================

def capture_frozen_frame(
    cap,
    pipeline,
    feature_config,
):
    """
    Live Preview
    แล้ว SPACE เพื่อหยุดภาพ
    """

    feature_name = (
        feature_config[
            "feature"
        ]
    )

    title = (
        feature_config[
            "title"
        ]
    )


    while True:

        ok, frame = (
            cap.read()
        )

        if not ok:
            continue


        result = (
            pipeline.process_frame(
                frame
            )
        )


        display = (
            draw_mediapipe_geometry(
                frame,
                result,
                feature_name,
            )
        )


        detected = (
            get_feature_value(
                result,
                feature_name,
            )
        )


        cv2.rectangle(
            display,
            (
                0,
                0,
            ),
            (
                760,
                145,
            ),
            (
                0,
                0,
                0,
            ),
            -1,
        )


        put(
            display,
            f"Feature: {title}",
            (
                20,
                35,
            ),
            WHITE,
            0.65,
            2,
        )


        if detected is None:

            detected_text = (
                "N/A"
            )

        else:

            detected_text = (
                f"{detected:+.3f} deg"
            )


        put(
            display,
            (
                "PostGuard Live: "
                f"{detected_text}"
            ),
            (
                20,
                72,
            ),
            GREEN,
            0.58,
            2,
        )


        put(
            display,
            (
                "SPACE = freeze frame   "
                "BACKSPACE = menu"
            ),
            (
                20,
                115,
            ),
            CYAN,
            0.52,
            1,
        )


        cv2.imshow(
            WINDOW_NAME,
            display,
        )


        key = (
            cv2.waitKey(1)
            & 0xFF
        )


        if key == 32:

            # สำคัญ:
            # Freeze ทั้ง frame + result จาก Frame เดียวกัน
            return (
                frame.copy(),
                result,
            )


        if key in (
            8,
            ord("q"),
            ord("Q"),
            27,
        ):

            return (
                None,
                None,
            )


# ==========================================================
# ANNOTATION
# ==========================================================

def annotate_frame(
    frozen_frame,
    frozen_result,
    feature_config,
):
    """
    ผู้ใช้ Click Landmark ด้วยมือ
    บน Frame เดียวกับ MediaPipe
    """

    global clicked_points
    global expected_point_names


    clicked_points = []

    expected_point_names = list(
        feature_config[
            "manual_points"
        ]
    )


    feature_name = (
        feature_config[
            "feature"
        ]
    )

    title = (
        feature_config[
            "title"
        ]
    )


    cv2.setMouseCallback(
        WINDOW_NAME,
        mouse_callback,
    )


    while True:

        display = (
            draw_mediapipe_geometry(
                frozen_frame,
                frozen_result,
                feature_name,
            )
        )


        display = (
            draw_manual_geometry(
                display,
                feature_name,
            )
        )


        detected = (
            get_feature_value(
                frozen_result,
                feature_name,
            )
        )


        manual_value = (
            calculate_manual_value(
                feature_name
            )
        )


        if (
            detected is not None
            and
            manual_value is not None
        ):

            error = abs(
                detected
                -
                manual_value
            )

        else:

            error = None


        # ==========================================
        # Top Information Panel
        # ==========================================

        cv2.rectangle(
            display,
            (
                0,
                0,
            ),
            (
                900,
                205,
            ),
            (
                0,
                0,
                0,
            ),
            -1,
        )


        put(
            display,
            f"Feature: {title}",
            (
                20,
                32,
            ),
            WHITE,
            0.62,
            2,
        )


        if detected is None:

            detected_text = (
                "N/A"
            )

        else:

            detected_text = (
                f"{detected:+.3f} deg"
            )


        put(
            display,
            (
                "PostGuard / MediaPipe: "
                f"{detected_text}"
            ),
            (
                20,
                68,
            ),
            GREEN,
            0.56,
            2,
        )


        if manual_value is None:

            manual_text = (
                "waiting for clicks"
            )

        else:

            manual_text = (
                f"{manual_value:+.3f} deg"
            )


        put(
            display,
            (
                "Manual Ground Truth: "
                f"{manual_text}"
            ),
            (
                20,
                102,
            ),
            YELLOW,
            0.56,
            2,
        )


        if error is not None:

            put(
                display,
                (
                    "Absolute Error: "
                    f"{error:.3f} deg"
                ),
                (
                    20,
                    136,
                ),
                WHITE,
                0.56,
                2,
            )


        current_index = (
            len(
                clicked_points
            )
        )


        if current_index < len(
            expected_point_names
        ):

            instruction = (
                "CLICK: "
                f"{expected_point_names[current_index]}"
            )

        else:

            instruction = (
                "Annotation complete"
            )


        put(
            display,
            instruction,
            (
                20,
                172,
            ),
            CYAN,
            0.58,
            2,
        )


        put(
            display,
            (
                "Left Click = add point   "
                "Right Click = undo   "
                "R = reset   "
                "ENTER = save   "
                "BACKSPACE = cancel"
            ),
            (
                20,
                198,
            ),
            WHITE,
            0.43,
            1,
        )


        cv2.imshow(
            WINDOW_NAME,
            display,
        )


        key = (
            cv2.waitKey(20)
            & 0xFF
        )


        # ==========================================
        # RESET MANUAL POINTS
        # ==========================================

        if key in (
            ord("r"),
            ord("R"),
        ):

            clicked_points = []

            continue


        # ==========================================
        # CANCEL
        # ==========================================

        if key in (
            8,
            27,
        ):

            return None


        # ==========================================
        # SAVE
        # ==========================================

        if key == 13:

            if (
                len(
                    clicked_points
                )
                !=
                len(
                    expected_point_names
                )
            ):

                continue


            if (
                detected is None
                or
                manual_value is None
                or
                error is None
            ):

                continue


            return {

                "display":
                    display.copy(),

                "feature":
                    feature_name,

                "title":
                    title,

                "detected":
                    detected,

                "manual_ground_truth":
                    manual_value,

                "absolute_error":
                    error,

                "manual_points":
                    list(
                        clicked_points
                    ),
            }


# ==========================================================
# SAVE RECORD
# ==========================================================

def save_records(
    records,
):
    fields = [
        "timestamp",
        "feature",
        "trial",
        "manual_ground_truth_deg",
        "postguard_detected_deg",
        "absolute_error_deg",
        "manual_points",
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

        writer.writerows(
            records
        )


# ==========================================================
# SUMMARY
# ==========================================================

def print_summary(
    records,
):
    if not records:

        print(
            "No completed annotations."
        )

        return


    grouped = {}


    for record in records:

        grouped.setdefault(
            record[
                "feature"
            ],
            [],
        ).append(
            record
        )


    print()

    print(
        "=" * 72
    )

    print(
        "MANUAL GROUND TRUTH ACCURACY SUMMARY"
    )

    print(
        "=" * 72
    )


    for feature, items in (
        grouped.items()
    ):

        errors = [
            float(
                item[
                    "absolute_error_deg"
                ]
            )
            for item in items
        ]


        mae = (
            sum(
                errors
            )
            /
            len(
                errors
            )
        )


        rmse = math.sqrt(

            sum(
                error ** 2
                for error in errors
            )
            /
            len(
                errors
            )
        )


        max_error = max(
            errors
        )


        print()

        print(
            feature
        )

        print(
            f"  Trials    : {len(items)}"
        )

        print(
            f"  MAE       : {mae:.3f} deg"
        )

        print(
            f"  RMSE      : {rmse:.3f} deg"
        )

        print(
            f"  Max Error : {max_error:.3f} deg"
        )


    print()

    print(
        f"CSV    : {CSV_PATH}"
    )

    print(
        f"Images : {IMAGE_DIR}"
    )

    print(
        "=" * 72
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    # ======================================================
    # OPEN CAMERA
    # ======================================================

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
            "Cannot open camera."
        )


    # ======================================================
    # DETECTION PIPELINE
    # ======================================================

    pipeline = (
        DetectionPipeline()
    )


    cv2.namedWindow(
        WINDOW_NAME,
        cv2.WINDOW_NORMAL,
    )


    records = []

    trial_number = 1


    try:

        while True:

            # ==============================================
            # MAIN MENU
            # ==============================================

            ok, frame = (
                cap.read()
            )


            if not ok:

                continue


            display = draw_menu(
                frame
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


            feature_key = None


            if key == ord(
                "1"
            ):

                feature_key = (
                    "1"
                )


            elif key == ord(
                "2"
            ):

                feature_key = (
                    "2"
                )


            if feature_key is None:

                continue


            feature_config = (
                FEATURES[
                    feature_key
                ]
            )


            # ==============================================
            # RESET TEMPORAL CONTEXT
            # ==============================================

            pipeline.reset_context()


            # ==============================================
            # GET ONE FROZEN FRAME
            # ==============================================

            (
                frozen_frame,
                frozen_result,
            ) = capture_frozen_frame(
                cap,
                pipeline,
                feature_config,
            )


            if frozen_frame is None:

                continue


            # ==============================================
            # MANUAL ANNOTATION
            # ==============================================

            annotation = annotate_frame(
                frozen_frame,
                frozen_result,
                feature_config,
            )


            if annotation is None:

                continue


            # ==============================================
            # SAVE IMAGE
            # ==============================================

            feature_name = (
                annotation[
                    "feature"
                ]
            )


            filename = (
                f"{feature_name}"
                f"__trial_{trial_number:03d}"
                ".png"
            )


            image_path = (
                IMAGE_DIR
                /
                filename
            )


            cv2.imwrite(
                str(
                    image_path
                ),
                annotation[
                    "display"
                ],
            )


            # ==============================================
            # SAVE RECORD
            # ==============================================

            record = {

                "timestamp":
                    time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),

                "feature":
                    feature_name,

                "trial":
                    trial_number,

                "manual_ground_truth_deg":
                    annotation[
                        "manual_ground_truth"
                    ],

                "postguard_detected_deg":
                    annotation[
                        "detected"
                    ],

                "absolute_error_deg":
                    annotation[
                        "absolute_error"
                    ],

                "manual_points":
                    str(
                        annotation[
                            "manual_points"
                        ]
                    ),

                "image_path":
                    str(
                        image_path
                    ),
            }


            records.append(
                record
            )


            save_records(
                records
            )


            print()

            print(
                "-" * 72
            )

            print(
                (
                    f"Feature       : "
                    f"{annotation['title']}"
                )
            )

            print(
                (
                    "Manual GT      : "
                    f"{annotation['manual_ground_truth']:+.3f} deg"
                )
            )

            print(
                (
                    "PostGuard      : "
                    f"{annotation['detected']:+.3f} deg"
                )
            )

            print(
                (
                    "Absolute Error : "
                    f"{annotation['absolute_error']:.3f} deg"
                )
            )

            print(
                "-" * 72
            )


            trial_number += 1


            # หลังจบ annotation
            # ยกเลิก Mouse Callback เดิม
            cv2.setMouseCallback(
                WINDOW_NAME,
                lambda *args:
                    None,
            )


    finally:

        pipeline.close()

        cap.release()

        cv2.destroyAllWindows()


    print_summary(
        records
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    main()
