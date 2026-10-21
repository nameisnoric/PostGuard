from __future__ import annotations

import csv
import math
import sys
import time
from pathlib import Path
from statistics import median

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
# IMPORT POSTGUARD
# ==========================================================

from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)

from camera_card.visualization.feature_visualizer import (
    draw_feature,
)

from camera_card.validation.accuracy_metrics import (
    absolute_error,
    summarize_by_feature,
)


# ==========================================================
# CONFIG
# ==========================================================

CAMERA_ID = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

TARGET_VALID_FRAMES = 60

MAX_CAPTURE_SECONDS = 20.0


# ==========================================================
# WINDOW NAME
# ==========================================================

WINDOW_NAME = (
    "PostGuard Accuracy Validation"
)

GROUND_TRUTH_WINDOW = (
    "Ground Truth"
)


# ==========================================================
# OUTPUT
# ==========================================================

OUTPUT_DIR = (
    THIS_FILE.parent
    / "accuracy_visual_results"
)

IMAGE_DIR = (
    OUTPUT_DIR
    / "images"
)

CSV_PATH = (
    OUTPUT_DIR
    / "accuracy_results.csv"
)


# ==========================================================
# FEATURE CONFIG
# ==========================================================
#
# Angle slider:
#
# 0 ... 120
#
# midpoint = 60
#
# 60 = 0 degree
#
# Step = 0.5 degree
#
#
# Example:
#
# 40
# -> -10 degree
#
# 60
# -> 0 degree
#
# 80
# -> +10 degree
#
# ==========================================================

FEATURE_CONFIG = {

    "1": {

        "feature":
            "shoulder_tilt",

        "title":
            "Shoulder Tilt",

        "unit":
            "deg",

        "slider_max":
            120,

        "slider_default":
            60,

        "slider_to_value":
            lambda position:
            (
                position
                - 60
            )
            * 0.5,
    },


    "2": {

        "feature":
            "neck_lateral_tilt",

        "title":
            "Neck Lateral Tilt",

        "unit":
            "deg",

        "slider_max":
            120,

        "slider_default":
            60,

        "slider_to_value":
            lambda position:
            (
                position
                - 60
            )
            * 0.5,
    },


    "3": {

        "feature":
            "neck_flexion",

        "title":
            (
                "Neck Flexion / "
                "Extension"
            ),

        "unit":
            "deg",

        "slider_max":
            120,

        "slider_default":
            60,

        "slider_to_value":
            lambda position:
            (
                position
                - 60
            )
            * 0.5,
    },


    "4": {

        "feature":
            "eye_distance",

        "title":
            "Eye Distance",

        "unit":
            "px",

        "slider_max":
            400,

        "slider_default":
            130,

        "slider_to_value":
            lambda position:
            float(
                position
            ),
    },
}


# ==========================================================
# EMPTY TRACKBAR CALLBACK
# ==========================================================

def nothing(_):
    pass


# ==========================================================
# DRAW TEXT
# ==========================================================

def put(
    frame,
    text,
    y,
    color=(255, 255, 255),
    scale=0.55,
    thickness=1,
):
    """
    Helper สำหรับเขียนข้อความบน Frame
    """

    cv2.putText(

        frame,

        str(
            text
        ),

        (
            20,
            int(
                y
            ),
        ),

        cv2.FONT_HERSHEY_SIMPLEX,

        scale,

        color,

        thickness,

        cv2.LINE_AA,
    )


# ==========================================================
# READ FEATURE VALUE
# ==========================================================

def get_feature_value(
    result,
    feature_name,
):
    """
    อ่านค่าจาก DetectionPipeline

    Expected:

    result["features"][feature_name]

    เช่น:

    result["features"]["shoulder_tilt"]

    {
        "valid": True,
        "value": -3.42,
        "unit": "deg"
    }
    """

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


    # Feature ต้อง valid
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


# ==========================================================
# CONTEXT VALID
# ==========================================================

def context_is_valid(
    result,
):
    """
    ใช้ Context Filter อยู่เบื้องหลัง

    ไม่แสดงให้ผู้ใช้เห็น

    Frame จะถูกนำไปเก็บเฉพาะเมื่อ:

    allow_posture_evaluation == True
    """

    if not isinstance(
        result,
        dict,
    ):
        return False


    context = (
        result.get(
            "context"
        )
        or {}
    )


    return (
        context.get(
            "allow_posture_evaluation"
        )
        is True
    )


# ==========================================================
# SAFE FILE LABEL
# ==========================================================

def safe_label(
    text,
):
    """
    เปลี่ยน Trial Label
    ให้ใช้เป็นชื่อไฟล์ได้
    """

    allowed = []


    for char in str(
        text
    ):

        if (
            char.isalnum()

            or

            char in (
                "-",
                "_",
            )
        ):

            allowed.append(
                char
            )

        elif char == " ":

            allowed.append(
                "_"
            )


    result = "".join(
        allowed
    ).strip(
        "_"
    )


    return (
        result
        or
        "trial"
    )


# ==========================================================
# GROUND TRUTH WINDOW
# ==========================================================

def open_ground_truth_window(
    config,
):
    """
    เปิด Slider สำหรับกำหนด Ground Truth

    Angle:
        -30 ... +30 degree

    Eye Distance:
        0 ... 400 px
    """

    try:

        cv2.destroyWindow(
            GROUND_TRUTH_WINDOW
        )

    except cv2.error:

        pass


    cv2.namedWindow(

        GROUND_TRUTH_WINDOW,

        cv2.WINDOW_NORMAL,
    )


    cv2.resizeWindow(

        GROUND_TRUTH_WINDOW,

        560,

        100,
    )


    cv2.createTrackbar(

        "Value",

        GROUND_TRUTH_WINDOW,

        int(
            config[
                "slider_default"
            ]
        ),

        int(
            config[
                "slider_max"
            ]
        ),

        nothing,
    )


# ==========================================================
# CLOSE GROUND TRUTH WINDOW
# ==========================================================

def close_ground_truth_window():

    try:

        cv2.destroyWindow(
            GROUND_TRUTH_WINDOW
        )

    except cv2.error:

        pass


# ==========================================================
# READ GROUND TRUTH
# ==========================================================

def read_ground_truth(
    config,
):
    """
    อ่าน Ground Truth
    จากตำแหน่ง Slider
    """

    position = (

        cv2.getTrackbarPos(

            "Value",

            GROUND_TRUTH_WINDOW,
        )
    )


    value = (

        config[
            "slider_to_value"
        ](
            position
        )
    )


    return float(
        value
    )


# ==========================================================
# DRAW MAIN MENU
# ==========================================================

def draw_menu(
    frame,
):
    """
    หน้าแรกของโปรแกรม

    ไม่ต้องใช้ input() ใน Terminal

    เลือก Feature
    ด้วย Keyboard บน OpenCV Window
    """

    output = (
        frame.copy()
    )


    overlay = (
        output.copy()
    )


    cv2.rectangle(

        overlay,

        (
            0,
            0,
        ),

        (
            720,
            370,
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

        output,

        0.35,

        0,

        output,
    )


    put(

        output,

        (
            "POSTGUARD FEATURE "
            "ACCURACY VALIDATION"
        ),

        40,

        (
            0,
            255,
            255,
        ),

        0.72,

        2,
    )


    put(

        output,

        (
            "Click this camera window "
            "and press a number:"
        ),

        85,

        (
            255,
            255,
            255,
        ),

        0.55,

        2,
    )


    put(

        output,

        "1 = Shoulder Tilt",

        130,
    )


    put(

        output,

        "2 = Neck Lateral Tilt",

        165,
    )


    put(

        output,

        (
            "3 = Neck Flexion / "
            "Extension"
        ),

        200,
    )


    put(

        output,

        "4 = Eye Distance",

        235,
    )


    put(

        output,

        (
            "Q = Finish and "
            "show summary"
        ),

        290,

        (
            0,
            255,
            255,
        ),

        0.58,

        2,
    )


    put(

        output,

        "ESC = Exit",

        330,

        (
            255,
            255,
            255,
        ),

        0.52,

        1,
    )


    return output


# ==========================================================
# PREPARE TRIAL
# ==========================================================

def prepare_trial(
    cap,
    pipeline,
    feature_key,
    trial_index,
):
    """
    ขั้นเตรียม Trial

    1. เลือก Feature
    2. เปิด Ground Truth Slider
    3. แสดง Detected แบบ Live
    4. ผู้ใช้ปรับค่า Ground Truth
    5. ENTER เพื่อเริ่มเก็บ 60 Frames
    """

    config = (
        FEATURE_CONFIG[
            feature_key
        ]
    )


    feature_name = (
        config[
            "feature"
        ]
    )


    title = (
        config[
            "title"
        ]
    )


    unit = (
        config[
            "unit"
        ]
    )


    # เปิด Slider
    open_ground_truth_window(
        config
    )


    while True:

        ok, frame = (
            cap.read()
        )


        if not ok:

            continue


        # ==============================================
        # Detection
        # ==============================================

        result = (

            pipeline.process_frame(
                frame
            )
        )


        # ==============================================
        # Draw Feature Geometry
        # ==============================================

        visual = (

            draw_feature(

                frame,

                result,

                feature_name,
            )
        )


        # ==============================================
        # Ground Truth
        # ==============================================

        ground_truth = (

            read_ground_truth(
                config
            )
        )


        # ==============================================
        # Current Detected
        # ==============================================

        detected = (

            get_feature_value(

                result,

                feature_name,
            )
        )


        # ==============================================
        # Display
        # ==============================================

        put(

            visual,

            (
                "Selected: "
                f"{title}"
            ),

            110,

            (
                255,
                255,
                255,
            ),

            0.62,

            2,
        )


        put(

            visual,

            (
                "Ground Truth: "
                f"{ground_truth:+.2f} "
                f"{unit}"
            ),

            145,

            (
                0,
                255,
                255,
            ),

            0.62,

            2,
        )


        if detected is None:

            detected_text = (
                "N/A"
            )

        else:

            detected_text = (

                f"{detected:+.2f} "
                f"{unit}"
            )


        put(

            visual,

            (
                "Live Detected: "
                f"{detected_text}"
            ),

            180,

            (
                255,
                255,
                255,
            ),

            0.58,

            1,
        )


        put(

            visual,

            (
                "Adjust Ground Truth "
                "with the slider."
            ),

            230,

            (
                255,
                255,
                255,
            ),

            0.52,

            1,
        )


        put(

            visual,

            (
                "ENTER = start "
                "60-frame capture"
            ),

            265,

            (
                0,
                255,
                255,
            ),

            0.58,

            2,
        )


        put(

            visual,

            (
                "BACKSPACE = "
                "choose another feature"
            ),

            300,

            (
                255,
                255,
                255,
            ),

            0.50,

            1,
        )


        cv2.imshow(

            WINDOW_NAME,

            visual,
        )


        # ==============================================
        # Keyboard
        # ==============================================

        key = (

            cv2.waitKey(1)

            &

            0xFF
        )


        # ==============================================
        # ENTER
        # Start Trial
        # ==============================================

        if key == 13:

            close_ground_truth_window()


            label = (

                f"trial_"
                f"{trial_index:02d}_"
                f"{ground_truth:+.1f}"
                f"{unit}"
            )


            return {

                "feature":
                    feature_name,

                "title":
                    title,

                "unit":
                    unit,

                "label":
                    label,

                "ground_truth":
                    ground_truth,
            }


        # ==============================================
        # Back
        # ==============================================

        if key in (

            8,

            ord(
                "q"
            ),

            ord(
                "Q"
            ),

            27,
        ):

            close_ground_truth_window()

            return None


# ==========================================================
# CAPTURE TRIAL
# ==========================================================

def capture_trial(
    cap,
    pipeline,
    trial,
):
    """
    เก็บ Feature 60 Valid Frames

    แล้วคำนวณ:

    - Median
    - Min
    - Max
    - Absolute Error
    - Valid Ratio
    """


    feature_name = (
        trial[
            "feature"
        ]
    )


    title = (
        trial[
            "title"
        ]
    )


    unit = (
        trial[
            "unit"
        ]
    )


    ground_truth = (
        trial[
            "ground_truth"
        ]
    )


    label = (
        trial[
            "label"
        ]
    )


    # ==============================================
    # Storage
    # ==============================================

    values = []


    total_frames = 0

    valid_frames = 0


    representative_frame = None

    representative_result = None


    start_time = (
        time.time()
    )


    # ==============================================
    # Capture Loop
    # ==============================================

    while (

        valid_frames
        < TARGET_VALID_FRAMES

        and

        (
            time.time()
            - start_time
        )
        < MAX_CAPTURE_SECONDS

    ):

        ok, frame = (
            cap.read()
        )


        if not ok:

            continue


        total_frames += 1


        # ==========================================
        # Detection
        #
        # IMPORTANT:
        #
        # frame ต้อง UNMIRRORED
        # ==========================================

        result = (

            pipeline.process_frame(
                frame
            )
        )


        # ==========================================
        # Get Feature
        # ==========================================

        detected = (

            get_feature_value(

                result,

                feature_name,
            )
        )


        # ==========================================
        # Draw Geometry
        # ==========================================

        visual = (

            draw_feature(

                frame,

                result,

                feature_name,
            )
        )


        # ==========================================
        # UI
        # ==========================================

        put(

            visual,

            (
                "Ground Truth: "
                f"{ground_truth:+.2f} "
                f"{unit}"
            ),

            110,

            (
                0,
                255,
                255,
            ),

            0.62,

            2,
        )


        if detected is None:

            detected_text = (
                "N/A"
            )

        else:

            detected_text = (

                f"{detected:+.2f} "
                f"{unit}"
            )


        put(

            visual,

            (
                "Detected: "
                f"{detected_text}"
            ),

            145,

            (
                255,
                255,
                255,
            ),

            0.60,

            2,
        )


        put(

            visual,

            (
                "Collecting: "
                f"{valid_frames}/"
                f"{TARGET_VALID_FRAMES}"
            ),

            180,

            (
                255,
                255,
                255,
            ),

            0.58,

            2,
        )


        put(

            visual,

            (
                "Hold the target "
                "posture still."
            ),

            215,

            (
                255,
                255,
                255,
            ),

            0.50,

            1,
        )


        put(

            visual,

            "ESC = cancel trial",

            250,

            (
                255,
                255,
                255,
            ),

            0.48,

            1,
        )


        cv2.imshow(

            WINDOW_NAME,

            visual,
        )


        key = (

            cv2.waitKey(1)

            &

            0xFF
        )


        # ==========================================
        # Cancel
        # ==========================================

        if key == 27:

            return None


        # ==========================================
        # Context Filter
        #
        # ใช้อยู่เบื้องหลัง
        #
        # ไม่แสดงใน UI
        # ==========================================

        if not context_is_valid(
            result
        ):

            continue


        # Feature ต้องอ่านได้
        if detected is None:

            continue


        # ==========================================
        # Valid Frame
        # ==========================================

        valid_frames += 1


        values.append(
            detected
        )


        # ==========================================
        # Representative Evidence Frame
        #
        # เลือก Frame กลาง Trial
        # ==========================================

        if (

            representative_frame
            is None

            and

            valid_frames
            >= TARGET_VALID_FRAMES // 2

        ):

            representative_frame = (

                frame.copy()
            )


            representative_result = (

                result
            )


    # ======================================================
    # ไม่มีค่า
    # ======================================================

    if not values:

        print(
            "No valid measurement collected."
        )

        return None


    # ======================================================
    # STATISTICS
    # ======================================================

    detected_median = float(

        median(
            values
        )
    )


    minimum = float(

        min(
            values
        )
    )


    maximum = float(

        max(
            values
        )
    )


    # ======================================================
    # ABSOLUTE ERROR
    # ======================================================

    error = absolute_error(

        detected_median,

        ground_truth,
    )


    # ======================================================
    # VALID RATIO
    # ======================================================

    if total_frames > 0:

        valid_ratio = (

            valid_frames

            /

            total_frames
        )

    else:

        valid_ratio = (
            0.0
        )


    # ======================================================
    # SAVE IMAGE
    # ======================================================

    image_path = ""


    if (

        representative_frame
        is not None

        and

        representative_result
        is not None

    ):

        evidence = (

            draw_feature(

                representative_frame,

                representative_result,

                feature_name,
            )
        )


        put(

            evidence,

            (
                "Ground Truth: "
                f"{ground_truth:+.2f} "
                f"{unit}"
            ),

            110,

            (
                0,
                255,
                255,
            ),

            0.62,

            2,
        )


        put(

            evidence,

            (
                "Detected Median: "
                f"{detected_median:+.2f} "
                f"{unit}"
            ),

            145,

            (
                255,
                255,
                255,
            ),

            0.62,

            2,
        )


        put(

            evidence,

            (
                "Absolute Error: "
                f"{error:.2f} "
                f"{unit}"
            ),

            180,

            (
                255,
                255,
                255,
            ),

            0.62,

            2,
        )


        filename = (

            f"{feature_name}__"

            f"{safe_label(label)}"

            ".png"
        )


        path = (

            IMAGE_DIR

            /

            filename
        )


        cv2.imwrite(

            str(
                path
            ),

            evidence,
        )


        image_path = str(
            path
        )


    # ======================================================
    # TERMINAL RESULT
    # ======================================================

    print()

    print(
        "-" * 72
    )


    print(
        f"Feature         : {title}"
    )


    print(
        (
            "Ground Truth    : "
            f"{ground_truth:.3f} "
            f"{unit}"
        )
    )


    print(
        (
            "Detected Median : "
            f"{detected_median:.3f} "
            f"{unit}"
        )
    )


    print(
        (
            "Range           : "
            f"{minimum:.3f} "
            ".. "
            f"{maximum:.3f} "
            f"{unit}"
        )
    )


    print(
        (
            "Absolute Error  : "
            f"{error:.3f} "
            f"{unit}"
        )
    )


    print(
        (
            "Valid Ratio     : "
            f"{valid_ratio:.2%}"
        )
    )


    print(
        "-" * 72
    )


    # ======================================================
    # RESULT
    # ======================================================

    return {

        "timestamp":

            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),


        "feature":

            feature_name,


        "label":

            label,


        "unit":

            unit,


        "ground_truth":

            ground_truth,


        "detected_median":

            detected_median,


        "detected_min":

            minimum,


        "detected_max":

            maximum,


        "absolute_error":

            error,


        "valid_frames":

            valid_frames,


        "total_frames":

            total_frames,


        "valid_ratio":

            valid_ratio,


        "image_path":

            image_path,
    }


# ==========================================================
# SAVE CSV
# ==========================================================

def save_csv(
    records,
):

    fields = [

        "timestamp",

        "feature",

        "label",

        "unit",

        "ground_truth",

        "detected_median",

        "detected_min",

        "detected_max",

        "absolute_error",

        "valid_frames",

        "total_frames",

        "valid_ratio",

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
# PRINT SUMMARY
# ==========================================================

def print_summary(
    records,
):
    """
    สรุป Accuracy ราย Feature

    ใช้:

    - MAE
    - RMSE
    """


    if not records:

        print(
            "No completed trials."
        )

        return


    summary = (

        summarize_by_feature(
            records
        )
    )


    print()

    print(
        "=" * 72
    )


    print(
        "ACCURACY SUMMARY"
    )


    print(
        "=" * 72
    )


    for feature, item in (
        summary.items()
    ):

        print()

        print(
            feature
        )


        print(
            (
                "  Trials : "
                f"{item['count']}"
            )
        )


        if item[
            "mae"
        ] is not None:

            print(
                (
                    "  MAE    : "
                    f"{item['mae']:.3f}"
                )
            )


        if item[
            "rmse"
        ] is not None:

            print(
                (
                    "  RMSE   : "
                    f"{item['rmse']:.3f}"
                )
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

    # ======================================================
    # Create Output Folder
    # ======================================================

    OUTPUT_DIR.mkdir(

        parents=True,

        exist_ok=True,
    )


    IMAGE_DIR.mkdir(

        parents=True,

        exist_ok=True,
    )


    # ======================================================
    # Open Camera
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
    # Detection Pipeline
    # ======================================================

    pipeline = (

        DetectionPipeline()
    )


    # ======================================================
    # Open Main Window
    # ======================================================

    cv2.namedWindow(

        WINDOW_NAME,

        cv2.WINDOW_NORMAL,
    )


    # ======================================================
    # Runtime
    # ======================================================

    records = []

    trial_index = 1


    try:

        # ==================================================
        # MAIN LOOP
        # ==================================================

        while True:

            # ==============================================
            # Camera Preview
            # ==============================================

            ok, frame = (

                cap.read()
            )


            if not ok:

                continue


            # ==============================================
            # Menu
            # ==============================================

            menu = (

                draw_menu(
                    frame
                )
            )


            cv2.imshow(

                WINDOW_NAME,

                menu,
            )


            # ==============================================
            # Keyboard
            # ==============================================

            key = (

                cv2.waitKey(1)

                &

                0xFF
            )


            # ==============================================
            # Finish
            # ==============================================

            if key in (

                ord(
                    "q"
                ),

                ord(
                    "Q"
                ),

            ):

                break


            # ESC
            if key == 27:

                break


            # ==============================================
            # Feature Select
            # ==============================================

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


            elif key == ord(
                "3"
            ):

                feature_key = (
                    "3"
                )


            elif key == ord(
                "4"
            ):

                feature_key = (
                    "4"
                )


            # ไม่ได้เลือกอะไร
            if feature_key is None:

                continue


            # ==============================================
            # Reset Context
            # ==============================================

            pipeline.reset_context()


            # ==============================================
            # Prepare Trial
            # ==============================================

            trial = (

                prepare_trial(

                    cap,

                    pipeline,

                    feature_key,

                    trial_index,
                )
            )


            # กลับเมนู
            if trial is None:

                continue


            # ==============================================
            # Reset Context ก่อนเก็บจริง
            # ==============================================

            pipeline.reset_context()


            # ==============================================
            # Capture
            # ==============================================

            record = (

                capture_trial(

                    cap,

                    pipeline,

                    trial,
                )
            )


            if record is None:

                continue


            # ==============================================
            # Save Record
            # ==============================================

            records.append(
                record
            )


            save_csv(
                records
            )


            trial_index += 1


    # ======================================================
    # CLEANUP
    # ======================================================

    finally:

        close_ground_truth_window()


        pipeline.close()


        cap.release()


        cv2.destroyAllWindows()


    # ======================================================
    # SUMMARY
    # ======================================================

    print_summary(
        records
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    main()