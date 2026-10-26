from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2


# ============================================================
# POSTGUARD DETECTION VALIDATION STUDIO
#
# เป้าหมาย:
#
# Human Ground Truth:
#     ผู้พัฒนาเห็นว่าท่า X เกิดขึ้น
#
# PostGuard:
#     ระบบตรวจพบท่า X ในช่วงเดียวกันหรือไม่
#
# ไม่ประเมิน:
# - Risk Level
# - Duration Risk
# - Risk Event
# - Alert
# - Modified RULA
#
# ใช้เพียง:
# - DetectionService
# - Current Posture Assessment
# - Eye Measurement
# - Eye State
# ============================================================


APP_TITLE = "PostGuard Detection Validation Studio"


# ============================================================
# PROJECT PATH
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent


def find_project_paths():
    """
    หา PostGuard root อัตโนมัติ

    รองรับไฟล์ที่อยู่เช่น:

    desktop/tools/video_validation/app.py
    desktop/tools/video_validation/detection_validation.py
    desktop/tools/detection_validation.py
    """

    candidates = [
        SCRIPT_DIR,
        *SCRIPT_DIR.parents,
    ]

    for candidate in candidates:

        # กรณี candidate = PostGuard
        desktop = (
            candidate
            / "desktop"
        )

        backend = (
            candidate
            / "backend"
        )

        if (
            (
                desktop
                / "app"
            ).is_dir()
            and
            (
                backend
                / "camera_card"
            ).is_dir()
        ):
            return (
                candidate,
                desktop,
                backend,
            )

        # กรณี candidate = desktop
        if (
            candidate.name.lower()
            ==
            "desktop"
            and
            (
                candidate
                / "app"
            ).is_dir()
            and
            (
                candidate.parent
                / "backend"
                / "camera_card"
            ).is_dir()
        ):
            return (
                candidate.parent,
                candidate,
                (
                    candidate.parent
                    / "backend"
                ),
            )

    raise RuntimeError(
        "Cannot locate PostGuard project.\n\n"
        "Expected structure:\n"
        "PostGuard\\desktop\\app\n"
        "PostGuard\\backend\\camera_card\n"
    )


(
    PROJECT_ROOT,
    DESKTOP_DIR,
    BACKEND_DIR,
) = find_project_paths()


# ============================================================
# FIX PYTHON IMPORT PATH
#
# ป้องกัน tools/video_validation/app.py
# ไปชนกับ desktop/app package จริง
# ============================================================

script_dir_text = str(
    SCRIPT_DIR
)

while (
    script_dir_text
    in sys.path
):
    sys.path.remove(
        script_dir_text
    )


for path in (
    DESKTOP_DIR,
    BACKEND_DIR,
):
    value = str(
        path
    )

    while (
        value
        in sys.path
    ):
        sys.path.remove(
            value
        )

    sys.path.insert(
        0,
        value,
    )


# ============================================================
# REAL POSTGUARD CODE
# ============================================================

from app.services.detection_service import (
    DetectionService,
)

from camera_card.posture_assessment.current_posture_assessment import (
    assess_current_posture,
)

from app.vision.mediapipe_detection.eye.eye_measurement import (
    calculate_eye_openness,
)

from app.vision.mediapipe_detection.eye.eye_state import (
    EyeStateDetector,
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
)


# ============================================================
# LABELS
# ============================================================

POSTURE_LABELS = (
    "NEUTRAL",
    "LEFT_SHOULDER_HIGH",
    "RIGHT_SHOULDER_HIGH",
    "TILT_LEFT",
    "TILT_RIGHT",
    "FLEXION",
    "EXTENSION",
)

SPECIAL_LABELS = (
    "IGNORE",
    "BLINK",
)

ALL_LABELS = (
    POSTURE_LABELS
    +
    SPECIAL_LABELS
)


# ============================================================
# BLINK SETTINGS
# ============================================================

BLINK_MATCH_TOLERANCE_SECONDS = (
    0.25
)

MAX_BLINK_CLOSED_SECONDS = (
    1.0
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def finite_number(
    value,
):
    try:
        value = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        value
    ):
        return None

    return value


def safe_divide(
    numerator,
    denominator,
):
    if denominator == 0:
        return 0.0

    return (
        numerator
        /
        denominator
    )


def format_seconds(
    seconds,
):
    seconds = max(
        0.0,
        float(
            seconds
        ),
    )

    minutes = int(
        seconds
        // 60
    )

    remaining = (
        seconds
        -
        minutes * 60
    )

    return (
        f"{minutes:02d}:"
        f"{remaining:06.3f}"
    )


def parse_time_value(
    value,
):
    """
    รองรับ:

    82.5
    01:22.500
    1:22.5
    """

    value = (
        value
        or ""
    ).strip()

    if not value:
        return None

    if ":" not in value:
        return finite_number(
            value
        )

    parts = value.split(
        ":"
    )

    if len(
        parts
    ) != 2:
        return None

    minutes = finite_number(
        parts[0]
    )

    seconds = finite_number(
        parts[1]
    )

    if (
        minutes is None
        or seconds is None
    ):
        return None

    if (
        minutes < 0
        or seconds < 0
        or seconds >= 60
    ):
        return None

    return (
        minutes * 60
        +
        seconds
    )


def interval_overlap(
    first,
    second,
):
    """
    return เวลาที่สองช่วงซ้อนกัน
    """

    return max(
        0.0,
        min(
            first[1],
            second[1],
        )
        -
        max(
            first[0],
            second[0],
        ),
    )


# ============================================================
# HUMAN GROUND TRUTH
# ============================================================

def save_annotations(
    path,
    annotations,
):
    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:

        writer = (
            csv.DictWriter(
                handle,
                fieldnames=[
                    "type",
                    "start",
                    "end",
                ],
            )
        )

        writer.writeheader()

        for item in annotations:

            writer.writerow(
                {
                    "type": (
                        item[
                            "type"
                        ]
                    ),

                    "start": (
                        f"{item['start']:.6f}"
                    ),

                    "end": (
                        f"{item['end']:.6f}"
                    ),
                }
            )


def load_annotations(
    path,
):
    annotations = []

    with open(
        path,
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:

        reader = csv.DictReader(
            handle
        )

        required = {
            "type",
            "start",
            "end",
        }

        if (
            not reader.fieldnames
            or
            not required.issubset(
                reader.fieldnames
            )
        ):
            raise ValueError(
                "Ground Truth CSV "
                "must contain: "
                "type,start,end"
            )

        for (
            line_number,
            row,
        ) in enumerate(
            reader,
            start=2,
        ):

            kind = (
                row.get(
                    "type"
                )
                or ""
            ).strip().upper()

            start = finite_number(
                row.get(
                    "start"
                )
            )

            end = finite_number(
                row.get(
                    "end"
                )
            )

            if (
                kind
                not in
                ALL_LABELS
            ):
                raise ValueError(
                    f"Line "
                    f"{line_number}: "
                    f"unsupported "
                    f"label {kind}"
                )

            if (
                start is None
                or end is None
                or start < 0
                or end < start
            ):
                raise ValueError(
                    f"Line "
                    f"{line_number}: "
                    f"invalid time"
                )

            if kind == "BLINK":
                end = start

            annotations.append(
                {
                    "type": kind,
                    "start": float(
                        start
                    ),
                    "end": float(
                        end
                    ),
                }
            )

    annotations.sort(
        key=lambda item: (
            item[
                "start"
            ],
            item[
                "type"
            ],
        )
    )

    return annotations


# ============================================================
# POSTGUARD POSTURE LABEL
#
# สำคัญ:
#
# ตรงนี้ไม่สร้าง threshold ใหม่
#
# assess_current_posture()
# เป็นตัวตัดสินจากระบบ PostGuard จริง
# ============================================================

def get_system_labels(
    assessment,
):
    labels = set()

    if not isinstance(
        assessment,
        dict,
    ):
        return labels

    features = (
        assessment.get(
            "features"
        )
        or {}
    )


    # --------------------------------------------------------
    # SHOULDER
    # --------------------------------------------------------

    shoulder = (
        features.get(
            "shoulder_tilt"
        )
        or {}
    )

    shoulder_status = (
        shoulder.get(
            "status"
        )
    )

    if (
        shoulder_status
        ==
        "LEFT_SHOULDER_HIGH"
    ):
        labels.add(
            "LEFT_SHOULDER_HIGH"
        )

    elif (
        shoulder_status
        ==
        "RIGHT_SHOULDER_HIGH"
    ):
        labels.add(
            "RIGHT_SHOULDER_HIGH"
        )


    # --------------------------------------------------------
    # NECK LATERAL
    # --------------------------------------------------------

    lateral = (
        features.get(
            "neck_lateral_tilt"
        )
        or {}
    )

    lateral_status = (
        lateral.get(
            "status"
        )
    )

    if (
        lateral_status
        ==
        "TILT_LEFT"
    ):
        labels.add(
            "TILT_LEFT"
        )

    elif (
        lateral_status
        ==
        "TILT_RIGHT"
    ):
        labels.add(
            "TILT_RIGHT"
        )


    # --------------------------------------------------------
    # FLEXION / EXTENSION
    # --------------------------------------------------------

    sagittal = (
        features.get(
            "neck_flexion"
        )
        or {}
    )

    sagittal_status = (
        sagittal.get(
            "status"
        )
    )

    if (
        sagittal_status
        ==
        "FLEXION"
    ):
        labels.add(
            "FLEXION"
        )

    elif (
        sagittal_status
        ==
        "EXTENSION"
    ):
        labels.add(
            "EXTENSION"
        )


    # --------------------------------------------------------
    # NEUTRAL
    # --------------------------------------------------------

    if (
        assessment.get(
            "status"
        )
        ==
        "COMPLETE"
        and
        not labels
    ):
        labels.add(
            "NEUTRAL"
        )


    return labels


# ============================================================
# BLINK EVENT TRACKER
#
# Eye OPEN/CLOSED มาจาก EyeStateDetector จริง
#
# ตัวนี้เพียงนับ:
#
# CLOSED -> OPEN
#
# เป็น Blink event
# ============================================================

class BlinkEventTracker:

    def __init__(
        self,
    ):
        self.previous_state = (
            EYE_UNKNOWN
        )

        self.closed_start = None

        self.events = []


    def update(
        self,
        state,
        timestamp,
    ):

        event = None


        # ----------------------------------------------------
        # เริ่มปิดตา
        # ----------------------------------------------------

        if (
            state
            ==
            EYE_CLOSED
            and
            self.previous_state
            !=
            EYE_CLOSED
        ):
            self.closed_start = (
                timestamp
            )


        # ----------------------------------------------------
        # CLOSED -> OPEN
        # ----------------------------------------------------

        if (
            state
            ==
            EYE_OPEN
            and
            self.previous_state
            ==
            EYE_CLOSED
            and
            self.closed_start
            is not None
        ):

            duration = (
                timestamp
                -
                self.closed_start
            )

            if (
                duration
                <=
                MAX_BLINK_CLOSED_SECONDS
            ):

                event = {
                    "timestamp_sec": (
                        float(
                            timestamp
                        )
                    ),

                    "closed_start_sec": (
                        float(
                            self.closed_start
                        )
                    ),

                    "closed_duration_sec": (
                        float(
                            duration
                        )
                    ),
                }

                self.events.append(
                    event
                )

            self.closed_start = None


        # ----------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------

        if (
            state
            ==
            EYE_UNKNOWN
        ):
            self.closed_start = None


        self.previous_state = (
            state
        )

        return event


# ============================================================
# SYSTEM POSTURE INTERVALS
# ============================================================

def build_system_intervals(
    frame_rows,
    label,
    fps,
):
    """
    รวม frame ต่อเนื่องที่ระบบตรวจ label เดียวกัน
    ให้กลายเป็นช่วงเวลา
    """

    frame_duration = (
        1.0
        /
        fps
    )

    intervals = []

    start_time = None

    previous_time = None


    for row in frame_rows:

        timestamp = (
            row[
                "timestamp_sec"
            ]
        )

        active = (
            label
            in
            row[
                "system_labels"
            ]
        )


        if (
            active
            and
            start_time
            is None
        ):
            start_time = (
                timestamp
            )


        if (
            not active
            and
            start_time
            is not None
        ):

            end_time = (
                previous_time
                +
                frame_duration
            )

            intervals.append(
                (
                    start_time,
                    end_time,
                )
            )

            start_time = None


        previous_time = (
            timestamp
        )


    if (
        start_time
        is not None
        and
        previous_time
        is not None
    ):

        intervals.append(
            (
                start_time,
                previous_time
                +
                frame_duration,
            )
        )


    return intervals


# ============================================================
# EVENT DETECTION METRIC
#
# จุดหลักของงานนี้:
#
# Human เจอท่า X
#
# ถ้า System เจอ X อย่างน้อย 1 ครั้ง
# ในช่วง Human event เดียวกัน
#
# => DETECTED
#
# ไม่เจอเลย
#
# => MISSED
# ============================================================

def calculate_event_detection(
    frame_rows,
    annotations,
    fps,
):

    summary = {}

    details = []


    system_intervals = {
        label: (
            build_system_intervals(
                frame_rows,
                label,
                fps,
            )
        )
        for label
        in POSTURE_LABELS
    }


    for label in POSTURE_LABELS:

        human_events = [
            (
                item[
                    "start"
                ],
                item[
                    "end"
                ],
            )
            for item
            in annotations
            if (
                item[
                    "type"
                ]
                ==
                label
            )
        ]


        detected_count = 0


        for (
            event_number,
            human_event,
        ) in enumerate(
            human_events,
            start=1,
        ):

            matching_intervals = []

            total_overlap = 0.0


            for system_event in (
                system_intervals[
                    label
                ]
            ):

                overlap = (
                    interval_overlap(
                        human_event,
                        system_event,
                    )
                )

                if overlap <= 0:
                    continue


                overlap_start = max(
                    human_event[0],
                    system_event[0],
                )

                overlap_end = min(
                    human_event[1],
                    system_event[1],
                )


                matching_intervals.append(
                    (
                        overlap_start,
                        overlap_end,
                    )
                )


                total_overlap += (
                    overlap
                )


            detected = (
                total_overlap
                >
                0
            )


            if detected:
                detected_count += 1


            details.append(
                {
                    "posture": (
                        label
                    ),

                    "human_event": (
                        event_number
                    ),

                    "human_start_sec": (
                        human_event[0]
                    ),

                    "human_end_sec": (
                        human_event[1]
                    ),

                    "human_duration_sec": (
                        human_event[1]
                        -
                        human_event[0]
                    ),

                    "detected": (
                        detected
                    ),

                    "system_overlap_sec": (
                        total_overlap
                    ),

                    "system_intervals": (
                        matching_intervals
                    ),
                }
            )


        total = len(
            human_events
        )


        summary[
            label
        ] = {
            "posture": (
                label
            ),

            "human_events": (
                total
            ),

            "detected": (
                detected_count
            ),

            "missed": (
                total
                -
                detected_count
            ),

            "detection_rate": (
                safe_divide(
                    detected_count,
                    total,
                )
            ),
        }


    total_human = sum(
        item[
            "human_events"
        ]
        for item
        in summary.values()
    )


    total_detected = sum(
        item[
            "detected"
        ]
        for item
        in summary.values()
    )


    overall = {
        "human_events": (
            total_human
        ),

        "detected": (
            total_detected
        ),

        "missed": (
            total_human
            -
            total_detected
        ),

        "detection_rate": (
            safe_divide(
                total_detected,
                total_human,
            )
        ),
    }


    return (
        summary,
        details,
        overall,
    )


# ============================================================
# BLINK COMPARISON
# ============================================================

def compare_blinks(
    annotations,
    system_events,
):

    human_times = [
        item[
            "start"
        ]
        for item
        in annotations
        if (
            item[
                "type"
            ]
            ==
            "BLINK"
        )
    ]


    system_times = [
        item[
            "timestamp_sec"
        ]
        for item
        in system_events
    ]


    unused_system = set(
        range(
            len(
                system_times
            )
        )
    )


    matches = []

    missed = []


    for human_time in sorted(
        human_times
    ):

        candidates = [
            index
            for index
            in unused_system
            if (
                abs(
                    system_times[
                        index
                    ]
                    -
                    human_time
                )
                <=
                BLINK_MATCH_TOLERANCE_SECONDS
            )
        ]


        if not candidates:

            missed.append(
                human_time
            )

            continue


        best = min(
            candidates,
            key=lambda index: (
                abs(
                    system_times[
                        index
                    ]
                    -
                    human_time
                )
            ),
        )


        unused_system.remove(
            best
        )


        matches.append(
            {
                "human_time": (
                    human_time
                ),

                "system_time": (
                    system_times[
                        best
                    ]
                ),
            }
        )


    return {
        "human_blinks": len(
            human_times
        ),

        "system_blinks": len(
            system_times
        ),

        "matched": len(
            matches
        ),

        "missed": len(
            missed
        ),

        "matches": (
            matches
        ),
    }


# ============================================================
# EXPORT EVENT SUMMARY
# ============================================================

def export_event_summary(
    path,
    summary,
    overall,
):

    columns = [
        "posture",
        "human_events",
        "detected",
        "missed",
        "detection_rate",
    ]


    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
        )


        writer.writeheader()


        for label in POSTURE_LABELS:

            writer.writerow(
                summary[
                    label
                ]
            )


        writer.writerow(
            {
                "posture": (
                    "OVERALL"
                ),

                "human_events": (
                    overall[
                        "human_events"
                    ]
                ),

                "detected": (
                    overall[
                        "detected"
                    ]
                ),

                "missed": (
                    overall[
                        "missed"
                    ]
                ),

                "detection_rate": (
                    overall[
                        "detection_rate"
                    ]
                ),
            }
        )


# ============================================================
# EXPORT EVENT DETAILS
# ============================================================

def export_event_details(
    path,
    details,
):

    columns = [
        "posture",
        "human_event",
        "human_start_sec",
        "human_end_sec",
        "human_duration_sec",
        "detected",
        "system_overlap_sec",
        "system_intervals",
    ]


    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
        )


        writer.writeheader()


        for item in details:

            row = dict(
                item
            )


            row[
                "system_intervals"
            ] = "; ".join(
                (
                    f"{start:.3f}"
                    f"-"
                    f"{end:.3f}"
                )
                for (
                    start,
                    end,
                )
                in item[
                    "system_intervals"
                ]
            )


            writer.writerow(
                row
            )


# ============================================================
# RUN VIDEO THROUGH POSTGUARD
# ============================================================

def run_validation(
    video_path,
    output_dir,
    annotations,
    status_callback,
):

    output_dir = Path(
        output_dir
    )


    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


    capture = cv2.VideoCapture(
        str(
            video_path
        )
    )


    if not capture.isOpened():

        raise RuntimeError(
            "Cannot open video"
        )


    fps = finite_number(
        capture.get(
            cv2.CAP_PROP_FPS
        )
    )


    frame_count = int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )


    if (
        fps is None
        or fps <= 0
        or frame_count <= 0
    ):

        capture.release()

        raise RuntimeError(
            "Invalid video"
        )


    detector = None


    eye_detector = (
        EyeStateDetector()
    )


    blink_tracker = (
        BlinkEventTracker()
    )


    eye_detector.start_calibration(
        timestamp=0.0
    )


    rows = []


    try:

        detector = (
            DetectionService()
        )


        frame_index = 0


        while True:

            ok, frame = (
                capture.read()
            )


            if not ok:
                break


            timestamp = (
                frame_index
                /
                fps
            )


            # =================================================
            # DETECTION
            # =================================================

            detection = (
                detector.process_frame(
                    frame
                )
            )


            # =================================================
            # POSTURE CLASSIFICATION
            #
            # ใช้ Current Posture Assessment จริง
            #
            # ไม่มี Risk Evaluation
            # =================================================

            assessment = (
                assess_current_posture(
                    detection
                )
            )


            labels = (
                get_system_labels(
                    assessment
                )
            )


            # =================================================
            # EYE
            # =================================================

            face_points = (
                detection.get(
                    "face_points"
                )
                or {}
            )


            eye_measurement = (
                calculate_eye_openness(
                    face_points
                )
            )


            eye_result = (
                eye_detector.update(
                    eye_measurement,
                    timestamp=(
                        timestamp
                    ),
                )
            )


            eye_state = (
                eye_result.get(
                    "eye_state",
                    EYE_UNKNOWN,
                )
            )


            blink_tracker.update(
                eye_state,
                timestamp,
            )


            rows.append(
                {
                    "frame_index": (
                        frame_index
                    ),

                    "timestamp_sec": (
                        timestamp
                    ),

                    "system_labels": (
                        sorted(
                            labels
                        )
                    ),
                }
            )


            frame_index += 1


            if (
                frame_index
                %
                max(
                    1,
                    int(
                        fps
                    ),
                )
                ==
                0
            ):

                status_callback(
                    f"Processing "
                    f"{frame_index:,}/"
                    f"{frame_count:,} "
                    f"frames "
                    f"("
                    f"{frame_index / frame_count * 100:.1f}%"
                    f")"
                )


    finally:

        capture.release()


        if detector is not None:

            detector.close()


    (
        summary,
        details,
        overall,
    ) = calculate_event_detection(
        rows,
        annotations,
        fps,
    )


    blink_result = (
        compare_blinks(
            annotations,
            blink_tracker.events,
        )
    )


    video_name = (
        Path(
            video_path
        ).stem
    )


    summary_path = (
        output_dir
        /
        f"{video_name}_event_summary.csv"
    )


    details_path = (
        output_dir
        /
        f"{video_name}_event_details.csv"
    )


    report_path = (
        output_dir
        /
        f"{video_name}_validation_report.json"
    )


    gt_path = (
        output_dir
        /
        f"{video_name}_ground_truth.csv"
    )


    export_event_summary(
        summary_path,
        summary,
        overall,
    )


    export_event_details(
        details_path,
        details,
    )


    save_annotations(
        gt_path,
        annotations,
    )


    report = {
        "validation_type": (
            "POSTURE_EVENT_DETECTION"
        ),

        "question": (
            "When Human Ground Truth "
            "identifies posture X, "
            "does PostGuard detect "
            "the same posture X "
            "inside the same event?"
        ),

        "video": (
            str(
                video_path
            )
        ),

        "fps": (
            fps
        ),

        "frames": (
            len(
                rows
            )
        ),

        "system_pipeline": [
            (
                "DetectionService"
            ),
            (
                "Current Posture Assessment"
            ),
        ],

        "excluded_from_validation": [
            (
                "Temporal Tracking"
            ),
            (
                "Risk Evaluation"
            ),
            (
                "Risk Event"
            ),
            (
                "Alert Policy"
            ),
            (
                "Modified RULA"
            ),
        ],

        "posture_summary": (
            summary
        ),

        "overall": (
            overall
        ),

        "blink": (
            blink_result
        ),
    }


    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            report,
            handle,
            ensure_ascii=False,
            indent=2,
        )


    return {
        "summary": (
            summary
        ),

        "overall": (
            overall
        ),

        "blink": (
            blink_result
        ),

        "output_dir": (
            str(
                output_dir
            )
        ),
    }


# ============================================================
# GUI
# ============================================================

class ValidationApp:

    def __init__(
        self,
        root,
    ):

        self.root = (
            root
        )


        self.root.title(
            APP_TITLE
        )


        try:

            self.root.state(
                "zoomed"
            )

        except tk.TclError:

            self.root.geometry(
                "1450x950"
            )


        self.video_path = None

        self.capture = None

        self.fps = 0.0

        self.frame_count = 0

        self.duration = 0.0

        self.current_frame_index = 0

        self.current_time = 0.0

        self.current_frame = None

        self.playing = False

        self.play_speed = 1.0

        self.annotations = []

        self.internal_seek = False


        # ====================================================
        # VARIABLES
        # ====================================================

        self.video_info_var = (
            tk.StringVar(
                value=(
                    "No video selected"
                )
            )
        )


        self.time_var = (
            tk.StringVar(
                value=(
                    "00:00.000"
                )
            )
        )


        self.frame_var = (
            tk.StringVar(
                value=(
                    "Frame 0 / 0"
                )
            )
        )


        self.start_var = (
            tk.StringVar(
                value=(
                    "0.000"
                )
            )
        )


        self.end_var = (
            tk.StringVar(
                value=(
                    "0.000"
                )
            )
        )


        self.goto_var = (
            tk.StringVar(
                value=(
                    "0.000"
                )
            )
        )


        self.status_var = (
            tk.StringVar(
                value=(
                    "Ready"
                )
            )
        )


        self.blink_count_var = (
            tk.StringVar(
                value=(
                    "Human Blink Marks: 0"
                )
            )
        )


        self.label_vars = {
            label: (
                tk.BooleanVar(
                    value=False
                )
            )
            for label
            in POSTURE_LABELS
        }


        self.ignore_var = (
            tk.BooleanVar(
                value=False
            )
        )


        self.seek_var = (
            tk.DoubleVar(
                value=0.0
            )
        )


        self._build_ui()

        self._bind_keys()


        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close,
        )


    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ):

        # ====================================================
        # FILE BAR
        # ====================================================

        top = ttk.Frame(
            self.root,
            padding=8,
        )


        top.pack(
            fill="x"
        )


        ttk.Button(
            top,
            text=(
                "Browse Video"
            ),
            command=(
                self.open_video
            ),
        ).pack(
            side="left"
        )


        ttk.Button(
            top,
            text=(
                "Import Ground Truth CSV"
            ),
            command=(
                self.import_csv
            ),
        ).pack(
            side="left",
            padx=5,
        )


        ttk.Button(
            top,
            text=(
                "Export Ground Truth CSV"
            ),
            command=(
                self.export_csv
            ),
        ).pack(
            side="left"
        )


        ttk.Label(
            top,
            textvariable=(
                self.video_info_var
            ),
        ).pack(
            side="left",
            padx=12,
        )


        # ====================================================
        # VIDEO AREA
        # ====================================================

        self.preview = (
            tk.Label(
                self.root,
                background="#111111",
                foreground="white",
                text=(
                    "Video Preview"
                ),
                anchor="center",
            )
        )


        self.preview.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 5),
        )


        self.preview.bind(
            "<Configure>",
            self._on_resize,
        )


        # ====================================================
        # TIMELINE
        # ====================================================

        timeline = ttk.Frame(
            self.root,
            padding=5,
        )


        timeline.pack(
            fill="x"
        )


        self.seek_scale = (
            ttk.Scale(
                timeline,
                from_=0,
                to=1,
                variable=(
                    self.seek_var
                ),
                command=(
                    self._seek_changed
                ),
            )
        )


        self.seek_scale.pack(
            side="left",
            fill="x",
            expand=True,
        )


        ttk.Label(
            timeline,
            textvariable=(
                self.time_var
            ),
            width=12,
        ).pack(
            side="left",
            padx=5,
        )


        ttk.Label(
            timeline,
            textvariable=(
                self.frame_var
            ),
            width=22,
        ).pack(
            side="left"
        )


        # ====================================================
        # PLAYBACK CONTROLS
        # ====================================================

        controls = ttk.Frame(
            self.root,
            padding=5,
        )


        controls.pack(
            fill="x"
        )


        ttk.Button(
            controls,
            text="Start",
            command=(
                self.first_frame
            ),
        ).pack(
            side="left",
            padx=2,
        )


        ttk.Button(
            controls,
            text="-5s",
            command=lambda: (
                self.jump_seconds(
                    -5
                )
            ),
        ).pack(
            side="left",
            padx=2,
        )


        ttk.Button(
            controls,
            text="-1s",
            command=lambda: (
                self.jump_seconds(
                    -1
                )
            ),
        ).pack(
            side="left",
            padx=2,
        )


        ttk.Button(
            controls,
            text="< Frame",
            command=(
                self.previous_frame
            ),
        ).pack(
            side="left",
            padx=2,
        )


        ttk.Button(
            controls,
            text="Play / Pause",
            command=(
                self.toggle_play
            ),
        ).pack(
            side="left",
            padx=2,
        )


        ttk.Button(
            controls,
            text="Frame >",
            command=(
                self.next_frame
            ),
        ).pack(
            side="left",
            padx=2,
        )


        ttk.Button(
            controls,
            text="+1s",
            command=lambda: (
                self.jump_seconds(
                    1
                )
            ),
        ).pack(
            side="left",
            padx=2,
        )


        ttk.Button(
            controls,
            text="+5s",
            command=lambda: (
                self.jump_seconds(
                    5
                )
            ),
        ).pack(
            side="left",
            padx=2,
        )


        ttk.Label(
            controls,
            text=(
                "Speed:"
            ),
        ).pack(
            side="left",
            padx=(10, 3),
        )


        self.speed_box = (
            ttk.Combobox(
                controls,
                values=(
                    "0.25x",
                    "0.5x",
                    "1.0x",
                    "1.5x",
                    "2.0x",
                ),
                state="readonly",
                width=7,
            )
        )


        self.speed_box.set(
            "1.0x"
        )


        self.speed_box.pack(
            side="left"
        )


        self.speed_box.bind(
            "<<ComboboxSelected>>",
            self._speed_changed,
        )


        ttk.Label(
            controls,
            text="Go to:",
        ).pack(
            side="left",
            padx=(10, 3),
        )


        ttk.Entry(
            controls,
            textvariable=(
                self.goto_var
            ),
            width=10,
        ).pack(
            side="left"
        )


        ttk.Button(
            controls,
            text="Go",
            command=(
                self.goto_time
            ),
        ).pack(
            side="left",
            padx=3,
        )


        # ====================================================
        # BOTTOM NOTEBOOK
        # ====================================================

        notebook = (
            ttk.Notebook(
                self.root
            )
        )


        notebook.pack(
            fill="x",
            padx=10,
            pady=5,
        )


        gt_tab = ttk.Frame(
            notebook,
            padding=8,
        )


        run_tab = ttk.Frame(
            notebook,
            padding=8,
        )


        notebook.add(
            gt_tab,
            text=(
                "Human Ground Truth"
            ),
        )


        notebook.add(
            run_tab,
            text=(
                "Validation"
            ),
        )


        self._build_ground_truth_tab(
            gt_tab
        )


        self._build_run_tab(
            run_tab
        )


    # ========================================================
    # GT TAB
    # ========================================================

    def _build_ground_truth_tab(
        self,
        parent,
    ):

        left = ttk.Frame(
            parent
        )


        right = ttk.Frame(
            parent
        )


        left.pack(
            side="left",
            fill="both",
            expand=True,
        )


        right.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(10, 0),
        )


        # ====================================================
        # LABELS
        # ====================================================

        ttk.Label(
            left,
            text=(
                "What posture do you see?"
            ),
        ).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
        )


        for (
            index,
            label,
        ) in enumerate(
            POSTURE_LABELS
        ):

            ttk.Checkbutton(
                left,
                text=(
                    label
                ),
                variable=(
                    self.label_vars[
                        label
                    ]
                ),
            ).grid(
                row=(
                    1
                    +
                    index // 4
                ),
                column=(
                    index % 4
                ),
                sticky="w",
                padx=5,
                pady=3,
            )


        ttk.Checkbutton(
            left,
            text=(
                "IGNORE / TRANSITION"
            ),
            variable=(
                self.ignore_var
            ),
        ).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=4,
        )


        # ====================================================
        # START / END
        # ====================================================

        ttk.Label(
            left,
            text=(
                "Start:"
            ),
        ).grid(
            row=4,
            column=0,
        )


        ttk.Entry(
            left,
            textvariable=(
                self.start_var
            ),
            width=12,
        ).grid(
            row=4,
            column=1,
            padx=4,
        )


        ttk.Button(
            left,
            text=(
                "Set Start"
            ),
            command=(
                self.set_start
            ),
        ).grid(
            row=4,
            column=2,
            padx=4,
        )


        ttk.Label(
            left,
            text=(
                "End:"
            ),
        ).grid(
            row=5,
            column=0,
        )


        ttk.Entry(
            left,
            textvariable=(
                self.end_var
            ),
            width=12,
        ).grid(
            row=5,
            column=1,
            padx=4,
        )


        ttk.Button(
            left,
            text=(
                "Set End"
            ),
            command=(
                self.set_end
            ),
        ).grid(
            row=5,
            column=2,
            padx=4,
        )


        ttk.Button(
            left,
            text=(
                "Add Posture Event"
            ),
            command=(
                self.add_posture_event
            ),
        ).grid(
            row=6,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=6,
        )


        # ====================================================
        # BLINK
        # ====================================================

        ttk.Button(
            left,
            text=(
                "MARK BLINK AT CURRENT FRAME"
            ),
            command=(
                self.mark_blink
            ),
        ).grid(
            row=7,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=6,
        )


        ttk.Label(
            left,
            textvariable=(
                self.blink_count_var
            ),
        ).grid(
            row=8,
            column=0,
            columnspan=3,
            sticky="w",
        )


        ttk.Label(
            left,
            text=(
                "Keyboard: Space = Play/Pause | "
                "Left/Right = Frame | "
                "Shift+Left/Right = 1 sec | "
                "B = Blink | S = Start | E = End"
            ),
        ).grid(
            row=9,
            column=0,
            columnspan=4,
            sticky="w",
            pady=5,
        )


        # ====================================================
        # ANNOTATION LIST
        # ====================================================

        ttk.Label(
            right,
            text=(
                "Human Events"
            ),
        ).pack(
            anchor="w"
        )


        list_frame = ttk.Frame(
            right
        )


        list_frame.pack(
            fill="both",
            expand=True,
        )


        scrollbar = ttk.Scrollbar(
            list_frame
        )


        scrollbar.pack(
            side="right",
            fill="y",
        )


        self.event_list = tk.Listbox(
            list_frame,
            height=10,
            yscrollcommand=(
                scrollbar.set
            ),
        )


        self.event_list.pack(
            side="left",
            fill="both",
            expand=True,
        )


        scrollbar.config(
            command=(
                self.event_list.yview
            )
        )


        self.event_list.bind(
            "<Double-Button-1>",
            self.jump_selected_event,
        )


        buttons = ttk.Frame(
            right
        )


        buttons.pack(
            fill="x",
            pady=4,
        )


        ttk.Button(
            buttons,
            text=(
                "Jump to Selected"
            ),
            command=(
                self.jump_selected_event
            ),
        ).pack(
            side="left"
        )


        ttk.Button(
            buttons,
            text=(
                "Delete Selected"
            ),
            command=(
                self.delete_selected_event
            ),
        ).pack(
            side="left",
            padx=5,
        )


    # ========================================================
    # RUN TAB
    # ========================================================

    def _build_run_tab(
        self,
        parent,
    ):

        ttk.Label(
            parent,
            text=(
                "Validation Question"
            ),
            font=(
                "TkDefaultFont",
                11,
                "bold",
            ),
        ).pack(
            anchor="w"
        )


        ttk.Label(
            parent,
            text=(
                "When Human Ground Truth sees posture X, "
                "does PostGuard detect the SAME posture X "
                "inside that Human event?"
            ),
            wraplength=1200,
        ).pack(
            anchor="w",
            pady=(3, 10),
        )


        ttk.Label(
            parent,
            text=(
                "This test does NOT evaluate Risk Level, "
                "Risk Duration, Risk Event, Alert, or Modified RULA."
            ),
            wraplength=1200,
        ).pack(
            anchor="w",
            pady=(0, 10),
        )


        ttk.Button(
            parent,
            text=(
                "RUN POSTURE DETECTION VALIDATION"
            ),
            command=(
                self.run
            ),
        ).pack(
            anchor="w"
        )


        ttk.Label(
            parent,
            textvariable=(
                self.status_var
            ),
        ).pack(
            anchor="w",
            pady=8,
        )


    # ========================================================
    # VIDEO
    # ========================================================

    def open_video(
        self,
    ):

        path = filedialog.askopenfilename(
            title="Choose video",
            filetypes=[
                (
                    "Video",
                    "*.mp4 *.avi *.mov *.mkv",
                ),
                (
                    "All",
                    "*.*",
                ),
            ],
        )


        if not path:
            return


        self._release_capture()


        capture = cv2.VideoCapture(
            path
        )


        if not capture.isOpened():

            messagebox.showerror(
                "Error",
                "Cannot open video",
            )

            return


        fps = finite_number(
            capture.get(
                cv2.CAP_PROP_FPS
            )
        )


        frame_count = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )


        if (
            fps is None
            or fps <= 0
            or frame_count <= 0
        ):

            capture.release()

            messagebox.showerror(
                "Error",
                "Invalid video",
            )

            return


        self.video_path = (
            path
        )


        self.capture = (
            capture
        )


        self.fps = (
            fps
        )


        self.frame_count = (
            frame_count
        )


        self.duration = (
            frame_count
            /
            fps
        )


        self.current_frame_index = 0

        self.current_time = 0.0

        self.annotations = []


        self.seek_scale.configure(
            from_=0,
            to=(
                self.duration
            ),
        )


        self.video_info_var.set(
            f"{Path(path).name} | "
            f"{fps:.3f} FPS | "
            f"{frame_count:,} frames | "
            f"{format_seconds(self.duration)}"
        )


        self.refresh_event_list()


        self.show_frame(
            0
        )


    def show_frame(
        self,
        index,
    ):

        if self.capture is None:
            return


        index = max(
            0,
            min(
                int(
                    index
                ),
                self.frame_count
                -
                1,
            ),
        )


        self.capture.set(
            cv2.CAP_PROP_POS_FRAMES,
            index,
        )


        ok, frame = (
            self.capture.read()
        )


        if not ok:
            return


        self.current_frame_index = (
            index
        )


        self.current_time = (
            index
            /
            self.fps
        )


        self.current_frame = (
            frame
        )


        self.time_var.set(
            format_seconds(
                self.current_time
            )
        )


        self.frame_var.set(
            f"Frame "
            f"{index + 1:,} / "
            f"{self.frame_count:,}"
        )


        self.goto_var.set(
            f"{self.current_time:.3f}"
        )


        self.internal_seek = (
            True
        )


        self.seek_var.set(
            self.current_time
        )


        self.internal_seek = (
            False
        )


        self.render_frame()


    def render_frame(
        self,
    ):

        if self.current_frame is None:
            return


        try:

            from PIL import (
                Image,
                ImageTk,
            )


            frame = cv2.cvtColor(
                self.current_frame,
                cv2.COLOR_BGR2RGB,
            )


            image = Image.fromarray(
                frame
            )


            width = max(
                640,
                self.preview.winfo_width()
                -
                20,
            )


            height = max(
                360,
                self.preview.winfo_height()
                -
                20,
            )


            image.thumbnail(
                (
                    width,
                    height,
                )
            )


            photo = ImageTk.PhotoImage(
                image
            )


            self.preview.configure(
                image=(
                    photo
                ),
                text="",
            )


            self.preview.image = (
                photo
            )


        except ImportError:

            self.preview.configure(
                text=(
                    "Install Pillow"
                )
            )


    def _on_resize(
        self,
        event=None,
    ):

        self.render_frame()


    def _seek_changed(
        self,
        value,
    ):

        if (
            self.internal_seek
            or self.capture is None
        ):
            return


        seconds = finite_number(
            value
        )


        if seconds is None:
            return


        self.playing = False


        frame = round(
            seconds
            *
            self.fps
        )


        self.show_frame(
            frame
        )


    # ========================================================
    # PLAYBACK
    # ========================================================

    def toggle_play(
        self,
    ):

        if self.capture is None:
            return


        self.playing = (
            not self.playing
        )


        if self.playing:

            self._play_tick()


    def _play_tick(
        self,
    ):

        if not self.playing:
            return


        next_frame = (
            self.current_frame_index
            +
            1
        )


        if (
            next_frame
            >=
            self.frame_count
        ):

            self.playing = False

            return


        self.show_frame(
            next_frame
        )


        delay = max(
            1,
            int(
                1000
                /
                (
                    self.fps
                    *
                    self.play_speed
                )
            ),
        )


        self.root.after(
            delay,
            self._play_tick,
        )


    def previous_frame(
        self,
    ):

        self.playing = False


        self.show_frame(
            self.current_frame_index
            -
            1
        )


    def next_frame(
        self,
    ):

        self.playing = False


        self.show_frame(
            self.current_frame_index
            +
            1
        )


    def first_frame(
        self,
    ):

        self.playing = False


        self.show_frame(
            0
        )


    def jump_seconds(
        self,
        seconds,
    ):

        if self.capture is None:
            return


        self.playing = False


        target = (
            self.current_time
            +
            seconds
        )


        target = max(
            0,
            min(
                self.duration,
                target,
            ),
        )


        frame = round(
            target
            *
            self.fps
        )


        self.show_frame(
            frame
        )


    def goto_time(
        self,
    ):

        if self.capture is None:
            return


        seconds = parse_time_value(
            self.goto_var.get()
        )


        if seconds is None:

            messagebox.showerror(
                "Invalid time",
                (
                    "Use seconds "
                    "or mm:ss.xxx"
                ),
            )

            return


        seconds = max(
            0,
            min(
                self.duration,
                seconds,
            ),
        )


        self.playing = False


        self.show_frame(
            round(
                seconds
                *
                self.fps
            )
        )


    def _speed_changed(
        self,
        event=None,
    ):

        value = (
            self.speed_box.get()
            .replace(
                "x",
                "",
            )
        )


        speed = finite_number(
            value
        )


        if (
            speed is not None
            and speed > 0
        ):

            self.play_speed = (
                speed
            )


    # ========================================================
    # HUMAN EVENT
    # ========================================================

    def set_start(
        self,
    ):

        self.start_var.set(
            f"{self.current_time:.3f}"
        )


    def set_end(
        self,
    ):

        self.end_var.set(
            f"{self.current_time:.3f}"
        )


    def add_posture_event(
        self,
    ):

        start = parse_time_value(
            self.start_var.get()
        )


        end = parse_time_value(
            self.end_var.get()
        )


        if (
            start is None
            or end is None
            or end < start
        ):

            messagebox.showerror(
                "Invalid",
                "Check Start / End",
            )

            return


        if self.ignore_var.get():

            selected = [
                "IGNORE"
            ]


        else:

            selected = [
                label
                for (
                    label,
                    variable,
                )
                in self.label_vars.items()
                if variable.get()
            ]


        if not selected:

            messagebox.showwarning(
                "No label",
                "Select posture",
            )

            return


        if (
            "NEUTRAL"
            in selected
            and len(
                selected
            )
            >
            1
        ):

            messagebox.showerror(
                "Invalid",
                (
                    "NEUTRAL cannot be "
                    "combined with "
                    "another posture."
                ),
            )

            return


        for label in selected:

            self.annotations.append(
                {
                    "type": (
                        label
                    ),

                    "start": float(
                        start
                    ),

                    "end": float(
                        end
                    ),
                }
            )


        self.annotations.sort(
            key=lambda item: (
                item[
                    "start"
                ],
                item[
                    "type"
                ],
            )
        )


        self.refresh_event_list()


    def mark_blink(
        self,
    ):

        if self.capture is None:
            return


        time = (
            self.current_frame_index
            /
            self.fps
        )


        self.annotations.append(
            {
                "type": (
                    "BLINK"
                ),

                "start": (
                    time
                ),

                "end": (
                    time
                ),
            }
        )


        self.annotations.sort(
            key=lambda item: (
                item[
                    "start"
                ],
                item[
                    "type"
                ],
            )
        )


        self.refresh_event_list()


        self.status_var.set(
            f"Blink marked "
            f"@ "
            f"{format_seconds(time)}"
        )


    def refresh_event_list(
        self,
    ):

        if not hasattr(
            self,
            "event_list",
        ):
            return


        self.event_list.delete(
            0,
            tk.END,
        )


        blink_count = 0


        for item in self.annotations:

            if (
                item[
                    "type"
                ]
                ==
                "BLINK"
            ):

                blink_count += 1


                text = (
                    f"BLINK @ "
                    f"{format_seconds(item['start'])}"
                )


            else:

                text = (
                    f"{item['type']} | "
                    f"{format_seconds(item['start'])}"
                    f" -> "
                    f"{format_seconds(item['end'])}"
                )


            self.event_list.insert(
                tk.END,
                text,
            )


        self.blink_count_var.set(
            f"Human Blink Marks: "
            f"{blink_count}"
        )


    def jump_selected_event(
        self,
        event=None,
    ):

        selection = (
            self.event_list.curselection()
        )


        if not selection:
            return


        item = (
            self.annotations[
                selection[0]
            ]
        )


        self.playing = False


        self.show_frame(
            round(
                item[
                    "start"
                ]
                *
                self.fps
            )
        )


    def delete_selected_event(
        self,
    ):

        selection = (
            self.event_list.curselection()
        )


        if not selection:
            return


        del self.annotations[
            selection[0]
        ]


        self.refresh_event_list()


    # ========================================================
    # CSV
    # ========================================================

    def import_csv(
        self,
    ):

        path = filedialog.askopenfilename(
            filetypes=[
                (
                    "CSV",
                    "*.csv",
                )
            ]
        )


        if not path:
            return


        try:

            self.annotations = (
                load_annotations(
                    path
                )
            )


            self.refresh_event_list()


        except Exception as exc:

            messagebox.showerror(
                "Import error",
                str(
                    exc
                ),
            )


    def export_csv(
        self,
    ):

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                (
                    "CSV",
                    "*.csv",
                )
            ],
        )


        if not path:
            return


        save_annotations(
            path,
            self.annotations,
        )


    # ========================================================
    # VALIDATION
    # ========================================================

    def run(
        self,
    ):

        if self.video_path is None:

            messagebox.showwarning(
                "No video",
                "Select video",
            )

            return


        output_dir = filedialog.askdirectory(
            title=(
                "Select output folder"
            )
        )


        if not output_dir:
            return


        try:

            self.playing = False


            report = run_validation(
                self.video_path,
                output_dir,
                self.annotations,
                self.update_status,
            )


            overall = (
                report[
                    "overall"
                ]
            )


            lines = [
                "POSTURE DETECTION VALIDATION",
                "",
                (
                    f"Human Events: "
                    f"{overall['human_events']}"
                ),
                (
                    f"Detected: "
                    f"{overall['detected']}"
                ),
                (
                    f"Missed: "
                    f"{overall['missed']}"
                ),
                (
                    f"Detection Rate: "
                    f"{overall['detection_rate'] * 100:.2f}%"
                ),
                "",
            ]


            for label in POSTURE_LABELS:

                item = (
                    report[
                        "summary"
                    ][
                        label
                    ]
                )


                lines.append(
                    f"{label}: "
                    f"{item['detected']}/"
                    f"{item['human_events']} "
                    f"("
                    f"{item['detection_rate'] * 100:.2f}%"
                    f")"
                )


            blink = (
                report[
                    "blink"
                ]
            )


            lines.extend(
                [
                    "",
                    "BLINK",
                    (
                        f"Human marks: "
                        f"{blink['human_blinks']}"
                    ),
                    (
                        f"System events: "
                        f"{blink['system_blinks']}"
                    ),
                    (
                        f"Matched: "
                        f"{blink['matched']}"
                    ),
                    (
                        f"Missed: "
                        f"{blink['missed']}"
                    ),
                ]
            )


            messagebox.showinfo(
                "Validation Result",
                "\n".join(
                    lines
                ),
            )


        except Exception as exc:

            traceback.print_exc()


            messagebox.showerror(
                "Validation failed",
                str(
                    exc
                ),
            )


    def update_status(
        self,
        text,
    ):

        self.status_var.set(
            text
        )


        self.root.update_idletasks()


    # ========================================================
    # KEYBOARD
    # ========================================================

    def _bind_keys(
        self,
    ):

        self.root.bind(
            "<space>",
            lambda event: (
                self.toggle_play()
            ),
        )


        self.root.bind(
            "<Left>",
            lambda event: (
                self.previous_frame()
            ),
        )


        self.root.bind(
            "<Right>",
            lambda event: (
                self.next_frame()
            ),
        )


        self.root.bind(
            "<Shift-Left>",
            lambda event: (
                self.jump_seconds(
                    -1
                )
            ),
        )


        self.root.bind(
            "<Shift-Right>",
            lambda event: (
                self.jump_seconds(
                    1
                )
            ),
        )


        self.root.bind(
            "b",
            lambda event: (
                self.mark_blink()
            ),
        )


        self.root.bind(
            "B",
            lambda event: (
                self.mark_blink()
            ),
        )


        self.root.bind(
            "s",
            lambda event: (
                self.set_start()
            ),
        )


        self.root.bind(
            "S",
            lambda event: (
                self.set_start()
            ),
        )


        self.root.bind(
            "e",
            lambda event: (
                self.set_end()
            ),
        )


        self.root.bind(
            "E",
            lambda event: (
                self.set_end()
            ),
        )


    # ========================================================
    # CLEANUP
    # ========================================================

    def _release_capture(
        self,
    ):

        if self.capture is not None:

            self.capture.release()

            self.capture = None


    def close(
        self,
    ):

        self.playing = False


        self._release_capture()


        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()


    ValidationApp(
        root
    )


    root.mainloop()


if __name__ == "__main__":
    main()