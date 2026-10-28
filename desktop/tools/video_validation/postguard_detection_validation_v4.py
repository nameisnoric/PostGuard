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
# POSTGUARD DETECTION VALIDATION STUDIO v4
#
# เป้าหมาย:
#
# 1. POSTURE
#    Human เห็น posture X
#        ↓
#    PostGuard ตรวจ posture X
#    ภายใน Human Event เดียวกันหรือไม่
#
# 2. BLINK
#    Human เห็น blink ที่เวลา T
#        ↓
#    PostGuard ตรวจ blink ใกล้เวลา T หรือไม่
#
# สิ่งที่ไม่ใช้:
# - Temporal Tracking
# - Risk Evaluation
# - Risk Event
# - Alert Policy
# - Modified RULA
#
# ใช้ production:
# - DetectionService
# - Current Posture Assessment
# - Eye Measurement
# - EyeStateDetector
# ============================================================


APP_TITLE = "PostGuard Detection Validation Studio v4"


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


BLINK_TOLERANCE_SECONDS = 0.25

MAX_BLINK_CLOSED_SECONDS = 1.0


# ============================================================
# PROJECT PATH
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent


def find_project_paths():

    candidates = [
        SCRIPT_DIR,
        *SCRIPT_DIR.parents,
    ]

    for candidate in candidates:

        desktop = (
            candidate
            /
            "desktop"
        )

        if (
            (
                desktop
                /
                "app"
            ).is_dir()
        ):
            return (
                candidate,
                desktop,
            )

        if (
            candidate.name.lower()
            ==
            "desktop"
            and
            (
                candidate
                /
                "app"
            ).is_dir()
        ):
            return (
                candidate.parent,
                candidate,
            )

    raise RuntimeError(
        "Cannot locate PostGuard project.\n\n"
        "Expected:\n"
        "PostGuard\\desktop\\app"
    )


(
    PROJECT_ROOT,
    DESKTOP_DIR,
) = find_project_paths()


# ป้องกัน app.py ใน tools ไปชน desktop/app package
script_dir_text = str(
    SCRIPT_DIR
)

while script_dir_text in sys.path:
    sys.path.remove(
        script_dir_text
    )


for path in (DESKTOP_DIR,):

    value = str(
        path
    )

    while value in sys.path:
        sys.path.remove(
            value
        )

    sys.path.insert(
        0,
        value,
    )


# ============================================================
# REAL POSTGUARD MODULES
# ============================================================

from app.services.detection_service import (
    DetectionService,
)

from app.vision.posture_assessment.current_posture_assessment import (
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
# GENERAL
# ============================================================

def finite_number(value):

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


def safe_divide(
    numerator,
    denominator,
):

    if not denominator:
        return 0.0

    return (
        numerator
        /
        denominator
    )


def format_time(seconds):

    seconds = max(
        0.0,
        float(
            seconds
        ),
    )

    minutes = int(
        seconds
        //
        60
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


def parse_time(text):

    text = (
        text
        or ""
    ).strip()

    if not text:
        return None

    if ":" not in text:
        return finite_number(
            text
        )

    parts = text.split(
        ":"
    )

    if len(parts) != 2:
        return None

    minute = finite_number(
        parts[0]
    )

    second = finite_number(
        parts[1]
    )

    if (
        minute is None
        or
        second is None
        or
        minute < 0
        or
        second < 0
        or
        second >= 60
    ):
        return None

    return (
        minute * 60
        +
        second
    )


# ============================================================
# GROUND TRUTH
# ============================================================

def save_ground_truth(
    path,
    annotations,
):

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "type",
                "start",
                "end",
            ],
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


def load_ground_truth(
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
                "Ground Truth CSV ต้องมี "
                "type,start,end"
            )

        for (
            row_number,
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

            if kind not in ALL_LABELS:

                raise ValueError(
                    f"Line {row_number}: "
                    f"unknown label "
                    f"{kind}"
                )

            if (
                start is None
                or
                end is None
                or
                start < 0
                or
                end < start
            ):

                raise ValueError(
                    f"Line {row_number}: "
                    "invalid time"
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
        key=lambda x: (
            x["start"],
            x["type"],
        )
    )

    return annotations


# ============================================================
# POSTURE LABEL FROM REAL ASSESSMENT
# ============================================================

def get_posture_labels(
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


    # SHOULDER
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


    # NECK LATERAL
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


    # FLEXION / EXTENSION
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


    # NEUTRAL
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
# BLINK EVENT
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
        eye_state,
        timestamp,
    ):

        event = None


        if (
            eye_state
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


        if (
            eye_state
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
                        timestamp
                    ),

                    "closed_start_sec": (
                        self.closed_start
                    ),

                    "closed_duration_sec": (
                        duration
                    ),
                }

                self.events.append(
                    event
                )

            self.closed_start = None


        if (
            eye_state
            ==
            EYE_UNKNOWN
        ):
            self.closed_start = None


        self.previous_state = (
            eye_state
        )

        return event


# ============================================================
# POSTURE EVENT VALIDATION
# ============================================================

def build_system_intervals(
    rows,
    label,
    fps,
):

    frame_duration = (
        1.0
        /
        fps
    )

    intervals = []

    start = None

    previous_time = None


    for row in rows:

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
            start is None
        ):
            start = timestamp


        if (
            not active
            and
            start is not None
        ):

            end = (
                previous_time
                +
                frame_duration
            )

            intervals.append(
                (
                    start,
                    end,
                )
            )

            start = None


        previous_time = (
            timestamp
        )


    if (
        start is not None
        and
        previous_time is not None
    ):

        intervals.append(
            (
                start,
                previous_time
                +
                frame_duration,
            )
        )


    return intervals


def calculate_posture_events(
    rows,
    annotations,
    fps,
):

    summaries = {}

    details = []


    system_intervals = {
        label: (
            build_system_intervals(
                rows,
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
            index,
            human_event,
        ) in enumerate(
            human_events,
            start=1,
        ):

            overlaps = []


            for (
                system_start,
                system_end,
            ) in system_intervals[
                label
            ]:

                overlap_start = max(
                    human_event[0],
                    system_start,
                )

                overlap_end = min(
                    human_event[1],
                    system_end,
                )

                if (
                    overlap_end
                    >
                    overlap_start
                ):

                    overlaps.append(
                        (
                            overlap_start,
                            overlap_end,
                        )
                    )


            detected = bool(
                overlaps
            )


            if detected:
                detected_count += 1


            details.append(
                {
                    "posture": (
                        label
                    ),

                    "human_event": (
                        index
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

                    "system_intervals": (
                        overlaps
                    ),
                }
            )


        human_count = len(
            human_events
        )


        summaries[
            label
        ] = {
            "posture": (
                label
            ),

            "human_events": (
                human_count
            ),

            "detected": (
                detected_count
            ),

            "missed": (
                human_count
                -
                detected_count
            ),

            "detection_rate": (
                safe_divide(
                    detected_count,
                    human_count,
                )
            ),
        }


    human_total = sum(
        item[
            "human_events"
        ]
        for item
        in summaries.values()
    )


    detected_total = sum(
        item[
            "detected"
        ]
        for item
        in summaries.values()
    )


    overall = {
        "human_events": (
            human_total
        ),

        "detected": (
            detected_total
        ),

        "missed": (
            human_total
            -
            detected_total
        ),

        "detection_rate": (
            safe_divide(
                detected_total,
                human_total,
            )
        ),
    }


    return (
        summaries,
        details,
        overall,
    )


# ============================================================
# BLINK MATCH
# ============================================================

def calculate_blink_result(
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


    available = set(
        range(
            len(
                system_times
            )
        )
    )


    detail_rows = []

    matched_count = 0


    for (
        human_index,
        human_time,
    ) in enumerate(
        human_times,
        start=1,
    ):

        candidates = [
            index
            for index
            in available
            if (
                abs(
                    system_times[
                        index
                    ]
                    -
                    human_time
                )
                <=
                BLINK_TOLERANCE_SECONDS
            )
        ]


        if not candidates:

            detail_rows.append(
                {
                    "source": (
                        "HUMAN"
                    ),

                    "human_event": (
                        human_index
                    ),

                    "human_time_sec": (
                        human_time
                    ),

                    "system_time_sec": (
                        None
                    ),

                    "time_error_sec": (
                        None
                    ),

                    "result": (
                        "MISSED"
                    ),
                }
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


        available.remove(
            best
        )


        system_time = (
            system_times[
                best
            ]
        )


        matched_count += 1


        detail_rows.append(
            {
                "source": (
                    "HUMAN"
                ),

                "human_event": (
                    human_index
                ),

                "human_time_sec": (
                    human_time
                ),

                "system_time_sec": (
                    system_time
                ),

                "time_error_sec": abs(
                    system_time
                    -
                    human_time
                ),

                "result": (
                    "MATCH"
                ),
            }
        )


    for index in sorted(
        available
    ):

        detail_rows.append(
            {
                "source": (
                    "SYSTEM"
                ),

                "human_event": (
                    None
                ),

                "human_time_sec": (
                    None
                ),

                "system_time_sec": (
                    system_times[
                        index
                    ]
                ),

                "time_error_sec": (
                    None
                ),

                "result": (
                    "SYSTEM_ONLY"
                ),
            }
        )


    human_count = len(
        human_times
    )

    system_count = len(
        system_times
    )

    human_missed = (
        human_count
        -
        matched_count
    )

    system_only = (
        system_count
        -
        matched_count
    )


    precision = safe_divide(
        matched_count,
        system_count,
    )

    recall = safe_divide(
        matched_count,
        human_count,
    )

    f1 = safe_divide(
        2
        *
        precision
        *
        recall,
        precision
        +
        recall,
    )


    summary = {
        "human_blinks": (
            human_count
        ),

        "system_blinks": (
            system_count
        ),

        "matched": (
            matched_count
        ),

        "human_missed": (
            human_missed
        ),

        "system_only": (
            system_only
        ),

        "precision": (
            precision
        ),

        "recall": (
            recall
        ),

        "f1_score": (
            f1
        ),

        "tolerance_seconds": (
            BLINK_TOLERANCE_SECONDS
        ),
    }


    return (
        summary,
        detail_rows,
    )


# ============================================================
# EXPORTS
# ============================================================

def export_frame_results(
    path,
    rows,
):

    columns = [
        "frame_index",
        "timestamp_sec",
        "pose_detected",
        "face_detected",
        "assessment_status",
        "system_labels",
        "eye_state",
        "blink_event",
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


        for row in rows:

            writer.writerow(
                {
                    "frame_index": (
                        row[
                            "frame_index"
                        ]
                    ),

                    "timestamp_sec": (
                        row[
                            "timestamp_sec"
                        ]
                    ),

                    "pose_detected": (
                        row[
                            "pose_detected"
                        ]
                    ),

                    "face_detected": (
                        row[
                            "face_detected"
                        ]
                    ),

                    "assessment_status": (
                        row[
                            "assessment_status"
                        ]
                    ),

                    "system_labels": (
                        "|".join(
                            row[
                                "system_labels"
                            ]
                        )
                    ),

                    "eye_state": (
                        row[
                            "eye_state"
                        ]
                    ),

                    "blink_event": (
                        row[
                            "blink_event"
                        ]
                    ),
                }
            )


def export_posture_summary(
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


def export_posture_details(
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

            intervals_text = (
                "; ".join(
                    (
                        f"{start:.6f}"
                        "-"
                        f"{end:.6f}"
                    )
                    for (
                        start,
                        end,
                    )
                    in item[
                        "system_intervals"
                    ]
                )
            )


            writer.writerow(
                {
                    "posture": (
                        item[
                            "posture"
                        ]
                    ),

                    "human_event": (
                        item[
                            "human_event"
                        ]
                    ),

                    "human_start_sec": (
                        item[
                            "human_start_sec"
                        ]
                    ),

                    "human_end_sec": (
                        item[
                            "human_end_sec"
                        ]
                    ),

                    "human_duration_sec": (
                        item[
                            "human_duration_sec"
                        ]
                    ),

                    "detected": (
                        item[
                            "detected"
                        ]
                    ),

                    "system_intervals": (
                        intervals_text
                    ),
                }
            )


def export_blink_summary(
    path,
    summary,
):

    rows = [
        (
            "Human Blinks",
            summary[
                "human_blinks"
            ],
        ),

        (
            "System Blinks",
            summary[
                "system_blinks"
            ],
        ),

        (
            "Matched",
            summary[
                "matched"
            ],
        ),

        (
            "Human Missed",
            summary[
                "human_missed"
            ],
        ),

        (
            "System Only",
            summary[
                "system_only"
            ],
        ),

        (
            "Precision",
            summary[
                "precision"
            ],
        ),

        (
            "Recall",
            summary[
                "recall"
            ],
        ),

        (
            "F1 Score",
            summary[
                "f1_score"
            ],
        ),

        (
            "Tolerance Seconds",
            summary[
                "tolerance_seconds"
            ],
        ),
    ]


    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:

        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "metric",
                "value",
            ]
        )

        writer.writerows(
            rows
        )


def export_blink_details(
    path,
    details,
):

    columns = [
        "source",
        "human_event",
        "human_time_sec",
        "system_time_sec",
        "time_error_sec",
        "result",
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

        writer.writerows(
            details
        )


# ============================================================
# RUN REAL POSTGUARD DETECTION
# ============================================================

def run_detection_validation(
    video_path,
    annotations,
    output_dir,
    status_callback=None,
):

    video_path = Path(
        video_path
    )

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
        or
        fps <= 0
        or
        frame_count <= 0
    ):

        capture.release()

        raise RuntimeError(
            "Invalid video information"
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


            # ================================================
            # REAL DETECTION SERVICE
            # ================================================

            detection = (
                detector.process_frame(
                    frame
                )
            )


            # ================================================
            # REAL CURRENT POSTURE ASSESSMENT
            # ================================================

            assessment = (
                assess_current_posture(
                    detection
                )
            )


            labels = (
                get_posture_labels(
                    assessment
                )
            )


            # ================================================
            # REAL EYE MEASUREMENT / STATE
            # ================================================

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


            blink_event = (
                blink_tracker.update(
                    eye_state,
                    timestamp,
                )
            )


            rows.append(
                {
                    "frame_index": (
                        frame_index
                    ),

                    "timestamp_sec": (
                        timestamp
                    ),

                    "pose_detected": bool(
                        detection.get(
                            "pose_detected"
                        )
                    ),

                    "face_detected": bool(
                        detection.get(
                            "face_detected"
                        )
                    ),

                    "assessment_status": (
                        assessment.get(
                            "status"
                        )
                    ),

                    "system_labels": sorted(
                        labels
                    ),

                    "eye_state": (
                        eye_state
                    ),

                    "blink_event": (
                        blink_event
                        is not None
                    ),
                }
            )


            frame_index += 1


            if (
                status_callback
                and
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
                    (
                        f"Processing "
                        f"{frame_index:,}/"
                        f"{frame_count:,} "
                        f"("
                        f"{frame_index / frame_count * 100:.1f}%"
                        f")"
                    )
                )


    finally:

        capture.release()


        if detector is not None:
            detector.close()


    # ========================================================
    # POSTURE RESULT
    # ========================================================

    (
        posture_summary,
        posture_details,
        posture_overall,
    ) = calculate_posture_events(
        rows,
        annotations,
        fps,
    )


    # ========================================================
    # BLINK RESULT
    # ========================================================

    (
        blink_summary,
        blink_details,
    ) = calculate_blink_result(
        annotations,
        blink_tracker.events,
    )


    base = (
        video_path.stem
    )


    ground_truth_path = (
        output_dir
        /
        f"{base}_ground_truth.csv"
    )


    frame_path = (
        output_dir
        /
        f"{base}_frame_results.csv"
    )


    posture_summary_path = (
        output_dir
        /
        f"{base}_posture_event_summary.csv"
    )


    posture_details_path = (
        output_dir
        /
        f"{base}_posture_event_details.csv"
    )


    blink_summary_path = (
        output_dir
        /
        f"{base}_blink_summary.csv"
    )


    blink_details_path = (
        output_dir
        /
        f"{base}_blink_details.csv"
    )


    report_path = (
        output_dir
        /
        f"{base}_validation_report.json"
    )


    save_ground_truth(
        ground_truth_path,
        annotations,
    )


    export_frame_results(
        frame_path,
        rows,
    )


    export_posture_summary(
        posture_summary_path,
        posture_summary,
        posture_overall,
    )


    export_posture_details(
        posture_details_path,
        posture_details,
    )


    export_blink_summary(
        blink_summary_path,
        blink_summary,
    )


    export_blink_details(
        blink_details_path,
        blink_details,
    )


    report = {

        "validation_version": (
            "4.0"
        ),

        "purpose": (
            "Detection validation only"
        ),

        "posture_question": (
            "When Human Ground Truth identifies posture X, "
            "does PostGuard detect the same posture X "
            "inside the same event?"
        ),

        "blink_question": (
            "When Human Ground Truth identifies a blink, "
            "does PostGuard detect a blink within the "
            "matching time tolerance?"
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

        "production_pipeline": {
            "posture": [
                (
                    "DetectionService"
                ),
                (
                    "Current Posture Assessment"
                ),
            ],

            "blink": [
                (
                    "DetectionService face points"
                ),
                (
                    "calculate_eye_openness"
                ),
                (
                    "EyeStateDetector"
                ),
                (
                    "CLOSED to OPEN validation event"
                ),
            ],
        },

        "not_used": [
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

        "posture": {
            "summary": (
                posture_summary
            ),

            "overall": (
                posture_overall
            ),

            "details": (
                posture_details
            ),
        },

        "blink": {
            "summary": (
                blink_summary
            ),

            "details": (
                blink_details
            ),
        },
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
        "posture_summary": (
            posture_summary
        ),

        "posture_overall": (
            posture_overall
        ),

        "blink_summary": (
            blink_summary
        ),

        "output_dir": (
            str(
                output_dir
            )
        ),

        "posture_details_path": (
            str(
                posture_details_path
            )
        ),

        "blink_details_path": (
            str(
                blink_details_path
            )
        ),

        "frame_results_path": (
            str(
                frame_path
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


        self.capture = None

        self.video_path = None

        self.fps = 0.0

        self.frame_count = 0

        self.duration = 0.0

        self.current_frame_index = 0

        self.current_time = 0.0

        self.current_frame = None

        self.playing = False

        self.play_speed = 1.0

        self.internal_seek = False

        self.annotations = []


        self.video_var = (
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


        self.seek_var = (
            tk.DoubleVar(
                value=0.0
            )
        )


        self.blink_count_var = (
            tk.StringVar(
                value=(
                    "Blink marks: 0"
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
                "Import Ground Truth"
            ),
            command=(
                self.import_ground_truth
            ),
        ).pack(
            side="left",
            padx=5,
        )


        ttk.Button(
            top,
            text=(
                "Export Ground Truth"
            ),
            command=(
                self.export_ground_truth
            ),
        ).pack(
            side="left"
        )


        ttk.Label(
            top,
            textvariable=(
                self.video_var
            ),
        ).pack(
            side="left",
            padx=10,
        )


        # ====================================================
        # VIDEO
        # ====================================================

        self.preview = tk.Label(
            self.root,
            background="#111111",
            foreground="white",
            text="Video Preview",
        )


        self.preview.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5,
        )


        self.preview.bind(
            "<Configure>",
            self._resize_preview,
        )


        # ====================================================
        # SEEK
        # ====================================================

        seek_frame = ttk.Frame(
            self.root,
            padding=5,
        )

        seek_frame.pack(
            fill="x"
        )


        self.seek_scale = ttk.Scale(
            seek_frame,
            from_=0,
            to=1,
            variable=(
                self.seek_var
            ),
            command=(
                self._seek_changed
            ),
        )


        self.seek_scale.pack(
            side="left",
            fill="x",
            expand=True,
        )


        ttk.Label(
            seek_frame,
            textvariable=(
                self.time_var
            ),
            width=12,
        ).pack(
            side="left",
            padx=5,
        )


        ttk.Label(
            seek_frame,
            textvariable=(
                self.frame_var
            ),
            width=22,
        ).pack(
            side="left"
        )


        # ====================================================
        # PLAYBACK
        # ====================================================

        transport = ttk.Frame(
            self.root,
            padding=5,
        )

        transport.pack(
            fill="x"
        )


        buttons = [
            (
                "Start",
                self.first_frame,
            ),

            (
                "-5s",
                lambda: (
                    self.jump_seconds(
                        -5
                    )
                ),
            ),

            (
                "-1s",
                lambda: (
                    self.jump_seconds(
                        -1
                    )
                ),
            ),

            (
                "< Frame",
                self.previous_frame,
            ),

            (
                "Play / Pause",
                self.toggle_play,
            ),

            (
                "Frame >",
                self.next_frame,
            ),

            (
                "+1s",
                lambda: (
                    self.jump_seconds(
                        1
                    )
                ),
            ),

            (
                "+5s",
                lambda: (
                    self.jump_seconds(
                        5
                    )
                ),
            ),
        ]


        for (
            text,
            command,
        ) in buttons:

            ttk.Button(
                transport,
                text=text,
                command=command,
            ).pack(
                side="left",
                padx=2,
            )


        ttk.Label(
            transport,
            text="Speed",
        ).pack(
            side="left",
            padx=(10, 3),
        )


        self.speed_box = ttk.Combobox(
            transport,
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
            transport,
            text="Go to",
        ).pack(
            side="left",
            padx=(10, 3),
        )


        ttk.Entry(
            transport,
            textvariable=(
                self.goto_var
            ),
            width=10,
        ).pack(
            side="left"
        )


        ttk.Button(
            transport,
            text="Go",
            command=(
                self.goto_time
            ),
        ).pack(
            side="left"
        )


        # ====================================================
        # NOTEBOOK
        # ====================================================

        notebook = ttk.Notebook(
            self.root
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


        validation_tab = ttk.Frame(
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
            validation_tab,
            text=(
                "Validation"
            ),
        )


        self._build_gt_tab(
            gt_tab
        )


        self._build_validation_tab(
            validation_tab
        )


    # ========================================================
    # GT TAB
    # ========================================================

    def _build_gt_tab(
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


        ttk.Label(
            left,
            text=(
                "Human posture"
            ),
            font=(
                "TkDefaultFont",
                10,
                "bold",
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
                text=label,
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
                padx=4,
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
            padx=4,
            pady=3,
        )


        ttk.Label(
            left,
            text=(
                "LEFT / RIGHT = ด้านของผู้ถูกถ่าย "
                "(anatomical side)\n"
                "ถ้ายกไหล่สองข้างพร้อมกันและไม่มีข้างใดสูงกว่า "
                "อย่าเลือก LEFT + RIGHT พร้อมกัน ให้ IGNORE "
                "สำหรับ shoulder asymmetry"
            ),
            wraplength=750,
        ).grid(
            row=4,
            column=0,
            columnspan=4,
            sticky="w",
            pady=5,
        )


        # START / END

        ttk.Label(
            left,
            text="Start",
        ).grid(
            row=5,
            column=0,
        )


        ttk.Entry(
            left,
            textvariable=(
                self.start_var
            ),
            width=12,
        ).grid(
            row=5,
            column=1,
        )


        ttk.Button(
            left,
            text="Set Start",
            command=(
                self.set_start
            ),
        ).grid(
            row=5,
            column=2,
            padx=3,
        )


        ttk.Label(
            left,
            text="End",
        ).grid(
            row=6,
            column=0,
        )


        ttk.Entry(
            left,
            textvariable=(
                self.end_var
            ),
            width=12,
        ).grid(
            row=6,
            column=1,
        )


        ttk.Button(
            left,
            text="Set End",
            command=(
                self.set_end
            ),
        ).grid(
            row=6,
            column=2,
            padx=3,
        )


        ttk.Button(
            left,
            text=(
                "ADD POSTURE EVENT"
            ),
            command=(
                self.add_posture_event
            ),
        ).grid(
            row=7,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=6,
        )


        ttk.Separator(
            left,
        ).grid(
            row=8,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=5,
        )


        ttk.Button(
            left,
            text=(
                "MARK BLINK AT CURRENT FRAME"
            ),
            command=(
                self.mark_blink
            ),
        ).grid(
            row=9,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=5,
        )


        ttk.Label(
            left,
            textvariable=(
                self.blink_count_var
            ),
        ).grid(
            row=10,
            column=0,
            columnspan=3,
            sticky="w",
        )


        ttk.Label(
            left,
            text=(
                "Shortcut: Space=Play/Pause | "
                "Left/Right=1 frame | "
                "Shift+Left/Right=1s | "
                "S=Start | E=End | B=Blink"
            ),
        ).grid(
            row=11,
            column=0,
            columnspan=4,
            sticky="w",
            pady=4,
        )


        # RIGHT EVENT LIST

        ttk.Label(
            right,
            text="Saved Ground Truth",
        ).pack(
            anchor="w"
        )


        self.event_list = tk.Listbox(
            right,
            height=11,
        )


        self.event_list.pack(
            fill="both",
            expand=True,
        )


        self.event_list.bind(
            "<Double-Button-1>",
            self.jump_selected,
        )


        button_frame = ttk.Frame(
            right
        )


        button_frame.pack(
            fill="x",
            pady=4,
        )


        ttk.Button(
            button_frame,
            text="Jump",
            command=(
                self.jump_selected
            ),
        ).pack(
            side="left"
        )


        ttk.Button(
            button_frame,
            text="Delete",
            command=(
                self.delete_selected
            ),
        ).pack(
            side="left",
            padx=5,
        )


    # ========================================================
    # VALIDATION TAB
    # ========================================================

    def _build_validation_tab(
        self,
        parent,
    ):

        ttk.Label(
            parent,
            text=(
                "Posture Detection"
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
                "Human เห็น posture X → "
                "PostGuard ตรวจ posture X "
                "อย่างน้อยหนึ่งครั้งภายใน Human Event เดียวกันหรือไม่"
            ),
        ).pack(
            anchor="w",
            pady=(2, 10),
        )


        ttk.Label(
            parent,
            text=(
                "Blink Detection"
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
                f"Human mark blink → "
                f"PostGuard มี blink event ภายใน "
                f"±{BLINK_TOLERANCE_SECONDS:.2f} วินาทีหรือไม่"
            ),
        ).pack(
            anchor="w",
            pady=(2, 10),
        )


        ttk.Label(
            parent,
            text=(
                "ไม่ใช้ Temporal Tracking / Risk Evaluation / "
                "Risk Event / Alert Policy / Modified RULA"
            ),
        ).pack(
            anchor="w",
            pady=(0, 10),
        )


        ttk.Button(
            parent,
            text=(
                "RUN DETECTION VALIDATION"
            ),
            command=(
                self.run_validation
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
            filetypes=[
                (
                    "Video",
                    "*.mp4 *.avi *.mov *.mkv",
                ),
                (
                    "All",
                    "*.*",
                ),
            ]
        )


        if not path:
            return


        if self.capture is not None:
            self.capture.release()


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


        count = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )


        if (
            fps is None
            or
            fps <= 0
            or
            count <= 0
        ):

            capture.release()

            messagebox.showerror(
                "Error",
                "Invalid video",
            )

            return


        self.capture = capture

        self.video_path = path

        self.fps = fps

        self.frame_count = count

        self.duration = (
            count
            /
            fps
        )

        self.current_frame_index = 0

        self.current_time = 0.0

        self.playing = False

        self.annotations = []


        self.seek_scale.configure(
            from_=0,
            to=(
                self.duration
            ),
        )


        self.video_var.set(
            (
                f"{Path(path).name} | "
                f"{fps:.3f} FPS | "
                f"{count:,} frames | "
                f"{format_time(self.duration)}"
            )
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
            format_time(
                self.current_time
            )
        )


        self.frame_var.set(
            (
                f"Frame "
                f"{index + 1:,}/"
                f"{self.frame_count:,}"
            )
        )


        self.goto_var.set(
            f"{self.current_time:.3f}"
        )


        self.internal_seek = True

        self.seek_var.set(
            self.current_time
        )

        self.internal_seek = False


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


            rgb = cv2.cvtColor(
                self.current_frame,
                cv2.COLOR_BGR2RGB,
            )


            image = Image.fromarray(
                rgb
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
                image=photo,
                text="",
            )


            self.preview.image = photo


        except ImportError:

            self.preview.configure(
                text=(
                    "Install Pillow"
                )
            )


    def _resize_preview(
        self,
        event=None,
    ):
        self.render_frame()


    # ========================================================
    # PLAYBACK
    # ========================================================

    def _seek_changed(
        self,
        value,
    ):

        if (
            self.internal_seek
            or
            self.capture is None
        ):
            return


        seconds = finite_number(
            value
        )


        if seconds is None:
            return


        self.playing = False


        self.show_frame(
            round(
                seconds
                *
                self.fps
            )
        )


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


        next_index = (
            self.current_frame_index
            +
            1
        )


        if (
            next_index
            >=
            self.frame_count
        ):

            self.playing = False

            return


        self.show_frame(
            next_index
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


    def first_frame(
        self,
    ):

        self.playing = False

        self.show_frame(
            0
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


    def jump_seconds(
        self,
        delta,
    ):

        if self.capture is None:
            return


        self.playing = False


        target = max(
            0,
            min(
                self.duration,
                self.current_time
                +
                delta,
            ),
        )


        self.show_frame(
            round(
                target
                *
                self.fps
            )
        )


    def goto_time(
        self,
    ):

        value = parse_time(
            self.goto_var.get()
        )


        if value is None:

            messagebox.showerror(
                "Time",
                "Use seconds or mm:ss.xxx",
            )

            return


        value = max(
            0,
            min(
                self.duration,
                value,
            ),
        )


        self.show_frame(
            round(
                value
                *
                self.fps
            )
        )


    def _speed_changed(
        self,
        event=None,
    ):

        value = finite_number(
            self.speed_box.get()
            .replace(
                "x",
                "",
            )
        )


        if (
            value is not None
            and
            value > 0
        ):
            self.play_speed = value


    # ========================================================
    # ANNOTATION
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

        start = parse_time(
            self.start_var.get()
        )

        end = parse_time(
            self.end_var.get()
        )


        if (
            start is None
            or
            end is None
            or
            end < start
        ):

            messagebox.showerror(
                "Invalid",
                "Invalid Start / End",
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
                "Posture",
                "Select posture",
            )

            return


        # NEUTRAL ห้ามรวมกับ posture อื่น

        if (
            "NEUTRAL"
            in selected
            and
            len(
                selected
            )
            >
            1
        ):

            messagebox.showerror(
                "Ground Truth",
                "NEUTRAL cannot be combined "
                "with another posture.",
            )

            return


        # ระบบปัจจุบันเป็น shoulder asymmetry
        # จึงไม่ควรใส่ LEFT+RIGHT พร้อมกัน

        if (
            "LEFT_SHOULDER_HIGH"
            in selected
            and
            "RIGHT_SHOULDER_HIGH"
            in selected
        ):

            messagebox.showerror(
                "Shoulder Ground Truth",

                (
                    "ห้ามเลือก LEFT_SHOULDER_HIGH และ "
                    "RIGHT_SHOULDER_HIGH พร้อมกัน\n\n"

                    "PostGuard ปัจจุบันตรวจ shoulder asymmetry "
                    "หรือความต่างระดับระหว่างไหล่สองข้าง\n\n"

                    "ถ้ายกไหล่ทั้งสองข้างพร้อมกันโดยไม่มีข้างใด "
                    "สูงกว่าอย่างชัดเจน ให้ IGNORE "
                    "สำหรับ shoulder feature"
                ),
            )

            return


        for label in selected:

            self.annotations.append(
                {
                    "type": label,

                    "start": float(
                        start
                    ),

                    "end": float(
                        end
                    ),
                }
            )


        self.annotations.sort(
            key=lambda x: (
                x[
                    "start"
                ],
                x[
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


        timestamp = (
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
                    timestamp
                ),

                "end": (
                    timestamp
                ),
            }
        )


        self.annotations.sort(
            key=lambda x: (
                x[
                    "start"
                ],
                x[
                    "type"
                ],
            )
        )


        self.refresh_event_list()


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
                    f"{format_time(item['start'])}"
                )


            else:

                text = (
                    f"{item['type']} | "
                    f"{format_time(item['start'])} "
                    f"-> "
                    f"{format_time(item['end'])}"
                )


            self.event_list.insert(
                tk.END,
                text,
            )


        self.blink_count_var.set(
            f"Blink marks: "
            f"{blink_count}"
        )


    def jump_selected(
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


        self.show_frame(
            round(
                item[
                    "start"
                ]
                *
                self.fps
            )
        )


    def delete_selected(
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
    # IMPORT / EXPORT GT
    # ========================================================

    def import_ground_truth(
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
                load_ground_truth(
                    path
                )
            )


            self.refresh_event_list()


        except Exception as exc:

            messagebox.showerror(
                "Import Error",
                str(
                    exc
                ),
            )


    def export_ground_truth(
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


        save_ground_truth(
            path,
            self.annotations,
        )


    # ========================================================
    # RUN
    # ========================================================

    def run_validation(
        self,
    ):

        if not self.video_path:

            messagebox.showwarning(
                "Video",
                "Select video first",
            )

            return


        output_dir = filedialog.askdirectory(
            title="Select output folder"
        )


        if not output_dir:
            return


        try:

            self.playing = False


            result = run_detection_validation(
                self.video_path,
                self.annotations,
                output_dir,
                status_callback=(
                    self.update_status
                ),
            )


            posture = (
                result[
                    "posture_overall"
                ]
            )


            blink = (
                result[
                    "blink_summary"
                ]
            )


            message = (
                "POSTURE\n"
                f"Human Events: "
                f"{posture['human_events']}\n"

                f"Detected: "
                f"{posture['detected']}\n"

                f"Missed: "
                f"{posture['missed']}\n"

                f"Detection Rate: "
                f"{posture['detection_rate'] * 100:.2f}%\n\n"

                "BLINK\n"

                f"Human: "
                f"{blink['human_blinks']}\n"

                f"System: "
                f"{blink['system_blinks']}\n"

                f"Matched: "
                f"{blink['matched']}\n"

                f"Human Missed: "
                f"{blink['human_missed']}\n"

                f"System Only: "
                f"{blink['system_only']}\n"

                f"Precision: "
                f"{blink['precision'] * 100:.2f}%\n"

                f"Recall: "
                f"{blink['recall'] * 100:.2f}%\n"

                f"F1: "
                f"{blink['f1_score'] * 100:.2f}%"
            )


            self.status_var.set(
                "Validation complete"
            )


            messagebox.showinfo(
                "Validation Result",
                message,
            )


        except Exception as exc:

            traceback.print_exc()


            self.status_var.set(
                "Validation failed"
            )


            messagebox.showerror(
                "Validation Error",
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
    # KEYS
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


    # ========================================================
    # CLOSE
    # ========================================================

    def close(
        self,
    ):

        self.playing = False


        if self.capture is not None:
            self.capture.release()


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
