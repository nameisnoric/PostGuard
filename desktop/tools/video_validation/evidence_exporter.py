from __future__ import annotations

import csv
import html
import math
import os
import shutil
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2

# ============================================================
# POSTGUARD EVIDENCE EXPORTER
#
# ใช้ผล Validation เดิม:
#
#   Original Video
#       +
#   event_details.csv
#       ↓
#   ดึงภาพ / คลิปหลักฐาน
#
# ไม่ rerun Detection
# ไม่ต้อง annotate ใหม่
#
# จุดประสงค์:
#
# Human เห็นท่า X
#       VS
# PostGuard ตรวจเจอ X หรือไม่
# ============================================================


APP_TITLE = "PostGuard Detection Evidence Exporter"

# ดึงคลิปก่อนและหลัง Human Event เพิ่ม
CLIP_PADDING_SECONDS = 1.0


# ============================================================
# HELPERS
# ============================================================

def finite_number(value):
    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(number):
        return None

    return number


def parse_bool(value):
    text = str(
        value
    ).strip().lower()

    return text in {
        "1",
        "true",
        "yes",
        "y",
        "detected",
    }


def format_time(seconds):
    seconds = max(
        0.0,
        float(seconds),
    )

    minutes = int(
        seconds // 60
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


def safe_name(text):
    result = []

    for char in str(text):

        if (
            char.isalnum()
            or char in (
                "-",
                "_",
            )
        ):
            result.append(
                char
            )

        else:
            result.append(
                "_"
            )

    return "".join(
        result
    ).strip(
        "_"
    )


# ============================================================
# PARSE SYSTEM INTERVALS
# ============================================================

def parse_intervals(text):
    """
    รองรับรูปแบบ:

    39.190-39.380; 40.400-40.830
    """

    intervals = []

    text = (
        text
        or ""
    ).strip()

    if (
        not text
        or text == "-"
    ):
        return intervals

    for piece in text.split(
        ";"
    ):

        piece = piece.strip()

        if (
            not piece
            or "-" not in piece
        ):
            continue

        start_text, end_text = (
            piece.split(
                "-",
                1,
            )
        )

        start = finite_number(
            start_text
        )

        end = finite_number(
            end_text
        )

        if (
            start is None
            or end is None
            or start < 0
            or end < start
        ):
            continue

        intervals.append(
            (
                start,
                end,
            )
        )

    return intervals


# ============================================================
# LOAD EVENT DETAILS
# ============================================================

def load_event_details(path):
    """
    รองรับ event_details.csv จาก Validation ล่าสุด

    ต้องมีอย่างน้อย:

    posture
    human_start_sec
    human_end_sec
    detected

    รองรับชื่อ column ได้ทั้ง:

    human_event
    human_event_index

    system_intervals
    system_overlap_intervals
    """

    events = []

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
            "posture",
            "human_start_sec",
            "human_end_sec",
            "detected",
        }

        if (
            not reader.fieldnames
            or
            not required.issubset(
                reader.fieldnames
            )
        ):

            raise ValueError(
                "event_details.csv ต้องมีอย่างน้อย:\n\n"
                "posture\n"
                "human_start_sec\n"
                "human_end_sec\n"
                "detected"
            )

        for (
            row_number,
            row,
        ) in enumerate(
            reader,
            start=1,
        ):

            posture = (
                row.get(
                    "posture"
                )
                or ""
            ).strip()

            human_start = finite_number(
                row.get(
                    "human_start_sec"
                )
            )

            human_end = finite_number(
                row.get(
                    "human_end_sec"
                )
            )

            if (
                not posture
                or human_start is None
                or human_end is None
            ):
                continue

            event_number = (
                row.get(
                    "human_event"
                )
                or
                row.get(
                    "human_event_index"
                )
                or
                row_number
            )

            try:

                event_number = int(
                    event_number
                )

            except (
                TypeError,
                ValueError,
            ):

                event_number = (
                    row_number
                )

            interval_text = (
                row.get(
                    "system_intervals"
                )
                or
                row.get(
                    "system_overlap_intervals"
                )
                or
                ""
            )

            intervals = (
                parse_intervals(
                    interval_text
                )
            )

            overlap = finite_number(
                row.get(
                    "system_overlap_sec"
                )
                or
                row.get(
                    "system_overlap_total_sec"
                )
            )

            events.append(
                {
                    "posture": posture,

                    "event_number": (
                        event_number
                    ),

                    "human_start_sec": (
                        human_start
                    ),

                    "human_end_sec": (
                        human_end
                    ),

                    "human_duration_sec": max(
                        0.0,
                        human_end
                        -
                        human_start,
                    ),

                    "detected": (
                        parse_bool(
                            row.get(
                                "detected"
                            )
                        )
                    ),

                    "system_overlap_sec": (
                        overlap
                    ),

                    "system_intervals": (
                        intervals
                    ),
                }
            )

    return events


# ============================================================
# VIDEO INFO
# ============================================================

def read_video_info(
    video_path,
):

    capture = cv2.VideoCapture(
        str(
            video_path
        )
    )

    if not capture.isOpened():

        raise RuntimeError(
            f"เปิดวิดีโอไม่ได้:\n"
            f"{video_path}"
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

    width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    capture.release()

    if (
        fps is None
        or fps <= 0
        or frame_count <= 0
        or width <= 0
        or height <= 0
    ):

        raise RuntimeError(
            "อ่านข้อมูลวิดีโอไม่ได้"
        )

    duration = (
        frame_count
        /
        fps
    )

    return {
        "fps": fps,

        "frame_count": (
            frame_count
        ),

        "width": (
            width
        ),

        "height": (
            height
        ),

        "duration": (
            duration
        ),
    }


# ============================================================
# READ FRAME AT TIME
# ============================================================

def read_frame_at(
    capture,
    fps,
    timestamp,
):

    frame_index = max(
        0,
        int(
            round(
                timestamp
                *
                fps
            )
        ),
    )

    capture.set(
        cv2.CAP_PROP_POS_FRAMES,
        frame_index,
    )

    ok, frame = (
        capture.read()
    )

    if not ok:
        return None

    return frame


# ============================================================
# FIND BEST SYSTEM FRAME
# ============================================================

def best_system_timestamp(
    event,
):
    """
    ถ้า DETECTED:

    เลือกจุดกลางของ system interval
    ที่ยาวที่สุด

    เพื่อเอาภาพที่เห็น detection ชัดที่สุด
    """

    intervals = (
        event[
            "system_intervals"
        ]
    )

    if (
        not event[
            "detected"
        ]
        or
        not intervals
    ):
        return None

    longest = max(
        intervals,
        key=lambda interval: (
            interval[1]
            -
            interval[0]
        ),
    )

    return (
        longest[0]
        +
        longest[1]
    ) / 2.0


# ============================================================
# DRAW TEXT BOX
# ============================================================

def draw_text_box(
    image,
    lines,
    top=15,
):

    result = image.copy()

    font = (
        cv2.FONT_HERSHEY_SIMPLEX
    )

    font_scale = 0.58

    thickness = 1

    line_height = 25

    margin = 10

    text_widths = []

    for line in lines:

        (
            size,
            _
        ) = cv2.getTextSize(
            line,
            font,
            font_scale,
            thickness,
        )

        text_widths.append(
            size[0]
        )

    box_width = min(
        result.shape[1]
        -
        20,

        max(
            text_widths
            or [100]
        )
        +
        margin
        *
        2,
    )

    box_height = (
        line_height
        *
        len(
            lines
        )
        +
        margin
    )

    overlay = (
        result.copy()
    )

    cv2.rectangle(
        overlay,

        (
            10,
            top,
        ),

        (
            10
            +
            box_width,

            top
            +
            box_height,
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

        result,
        0.35,

        0,

        result,
    )

    y = (
        top
        +
        22
    )

    for line in lines:

        cv2.putText(
            result,

            line,

            (
                18,
                y,
            ),

            font,

            font_scale,

            (
                255,
                255,
                255,
            ),

            thickness,

            cv2.LINE_AA,
        )

        y += (
            line_height
        )

    return result


# ============================================================
# CREATE PANEL
# ============================================================

def make_panel(
    frame,
    title,
    subtitle,
    width=640,
    height=360,
):

    panel = cv2.resize(
        frame,
        (
            width,
            height,
        ),
    )

    panel = draw_text_box(
        panel,
        [
            title,
            subtitle,
        ],
        top=10,
    )

    return panel


def save_image_unicode(
    output_path,
    image,
):
    """
    บันทึกภาพให้รองรับ path ภาษาไทยบน Windows

    cv2.imwrite() บางเครื่องมีปัญหากับ Unicode path
    จึงใช้ cv2.imencode() ก่อน แล้วเขียน bytes ลงไฟล์เอง
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    extension = (
        output_path.suffix.lower()
        or ".jpg"
    )

    success, encoded = (
        cv2.imencode(
            extension,
            image,
        )
    )

    if not success:

        raise RuntimeError(
            "OpenCV encode image failed:\n"
            f"{output_path}"
        )

    try:

        encoded.tofile(
            str(
                output_path
            )
        )

    except Exception as exc:

        raise RuntimeError(
            "บันทึกภาพไม่ได้:\n"
            f"{output_path}\n\n"
            f"{exc}"
        )

# ============================================================
# EXPORT SIDE-BY-SIDE IMAGE
# ============================================================

def export_comparison_image(
    capture,
    fps,
    event,
    output_path,
):

    # --------------------------------------------------------
    # Human key frame
    #
    # ใช้กลางช่วง Human Event
    # --------------------------------------------------------

    human_time = (
        event[
            "human_start_sec"
        ]
        +
        event[
            "human_end_sec"
        ]
    ) / 2.0

    human_frame = (
        read_frame_at(
            capture,
            fps,
            human_time,
        )
    )

    if human_frame is None:

        raise RuntimeError(
            "อ่าน Human key frame ไม่ได้ "
            f"ที่ {human_time:.3f}s"
        )

    # --------------------------------------------------------
    # System key frame
    # --------------------------------------------------------

    system_time = (
        best_system_timestamp(
            event
        )
    )

    if system_time is not None:

        system_frame = (
            read_frame_at(
                capture,
                fps,
                system_time,
            )
        )

    else:

        system_frame = (
            human_frame.copy()
        )

    if system_frame is None:

        system_frame = (
            human_frame.copy()
        )

    posture = (
        event[
            "posture"
        ]
    )

    # --------------------------------------------------------
    # LEFT = Human
    # --------------------------------------------------------

    left = make_panel(
        human_frame,

        f"HUMAN: {posture}",

        (
            "Event midpoint: "
            f"{format_time(human_time)}"
        ),
    )

    # --------------------------------------------------------
    # RIGHT = PostGuard
    # --------------------------------------------------------

    if event[
        "detected"
    ]:

        right = make_panel(
            system_frame,

            f"POSTGUARD: {posture}",

            (
                "Detected at: "
                f"{format_time(system_time)} "
                "| MATCH"
            ),
        )

    else:

        right = make_panel(
            system_frame,

            "POSTGUARD: NOT DETECTED",

            (
                "Human event: "
                f"{format_time(human_time)} "
                "| MISSED"
            ),
        )

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    comparison = cv2.hconcat(
        [
            left,
            right,
        ]
    )

    footer_height = 50

    canvas = cv2.copyMakeBorder(
        comparison,

        0,
        footer_height,

        0,
        0,

        cv2.BORDER_CONSTANT,

        value=(
            25,
            25,
            25,
        ),
    )

    detail = (
        "Human: "
        f"{format_time(event['human_start_sec'])}"
        " - "
        f"{format_time(event['human_end_sec'])}"
    )

    if (
        event[
            "detected"
        ]
        and
        event[
            "system_intervals"
        ]
    ):

        system_text = "; ".join(
            (
                f"{format_time(start)}"
                "-"
                f"{format_time(end)}"
            )
            for (
                start,
                end,
            )
            in event[
                "system_intervals"
            ]
        )

        detail += (
            " | System: "
            +
            system_text
        )

    else:

        detail += (
            " | System: none"
        )

    cv2.putText(
        canvas,

        detail[:180],

        (
            12,
            comparison.shape[0]
            +
            31,
        ),

        cv2.FONT_HERSHEY_SIMPLEX,

        0.52,

        (
            255,
            255,
            255,
        ),

        1,

        cv2.LINE_AA,
    )

    save_image_unicode(
        output_path,
        canvas,
    )


# ============================================================
# CHECK SYSTEM ACTIVE AT TIME
# ============================================================

def system_active_at(
    timestamp,
    intervals,
):

    return any(
        (
            start
            <=
            timestamp
            <=
            end
        )
        for (
            start,
            end,
        )
        in intervals
    )


# ============================================================
# EXPORT MINI EVENT CLIP
# ============================================================

def export_event_clip(
    video_path,
    info,
    event,
    output_path,
):
    """
    สร้าง mini clip หลักฐาน

    ใช้ temporary ASCII path ก่อน
    เพื่อหลีกเลี่ยงปัญหา cv2.VideoWriter()
    กับ path ภาษาไทยบน Windows

    หลังเขียนเสร็จจึง move ไปยัง output path จริง
    """

    video_path = Path(
        video_path
    )

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fps = (
        info[
            "fps"
        ]
    )

    duration = (
        info[
            "duration"
        ]
    )

    clip_start = max(
        0.0,
        event[
            "human_start_sec"
        ]
        -
        CLIP_PADDING_SECONDS,
    )

    clip_end = min(
        duration,
        event[
            "human_end_sec"
        ]
        +
        CLIP_PADDING_SECONDS,
    )

    start_frame = max(
        0,
        int(
            math.floor(
                clip_start
                *
                fps
            )
        ),
    )

    end_frame = min(
        info[
            "frame_count"
        ]
        -
        1,
        int(
            math.ceil(
                clip_end
                *
                fps
            )
        ),
    )

    capture = cv2.VideoCapture(
        str(
            video_path
        )
    )

    if not capture.isOpened():

        raise RuntimeError(
            "เปิดวิดีโอสำหรับสร้าง clip ไม่ได้:\n"
            f"{video_path}"
        )

    capture.set(
        cv2.CAP_PROP_POS_FRAMES,
        start_frame,
    )

    # ========================================================
    # TEMP ASCII FILE
    #
    # VideoWriter ของ OpenCV บน Windows
    # อาจเขียน path ภาษาไทยไม่ได้
    # ========================================================

    temp_dir = Path(
        tempfile.gettempdir()
    )

    temp_file = (
        temp_dir
        /
        (
            "postguard_evidence_"
            f"{os.getpid()}_"
            f"{event['event_number']}.mp4"
        )
    )

    # ลบของเก่าถ้ามี
    try:

        if temp_file.exists():
            temp_file.unlink()

    except Exception:
        pass

    writer = cv2.VideoWriter(
        str(
            temp_file
        ),
        cv2.VideoWriter_fourcc(
            *"mp4v"
        ),
        fps,
        (
            info[
                "width"
            ],
            info[
                "height"
            ],
        ),
    )

    if not writer.isOpened():

        capture.release()

        raise RuntimeError(
            "สร้าง VideoWriter ไม่สำเร็จ:\n"
            f"{temp_file}"
        )

    posture = (
        event[
            "posture"
        ]
    )

    frame_index = (
        start_frame
    )

    try:

        while (
            frame_index
            <=
            end_frame
        ):

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
            # HUMAN ACTIVE?
            # =================================================

            human_active = (
                event[
                    "human_start_sec"
                ]
                <=
                timestamp
                <=
                event[
                    "human_end_sec"
                ]
            )

            # =================================================
            # SYSTEM SAME LABEL ACTIVE?
            # =================================================

            system_active = (
                system_active_at(
                    timestamp,
                    event[
                        "system_intervals"
                    ],
                )
            )

            result_text = (
                "DETECTED"
                if event[
                    "detected"
                ]
                else
                "MISSED"
            )

            lines = [
                (
                    f"Posture: "
                    f"{posture}"
                ),

                (
                    f"Time: "
                    f"{format_time(timestamp)}"
                ),

                (
                    "Human Event: "
                    +
                    (
                        "YES"
                        if human_active
                        else
                        "NO"
                    )
                ),

                (
                    "PostGuard Same Label: "
                    +
                    (
                        "YES"
                        if system_active
                        else
                        "NO"
                    )
                ),

                (
                    f"Result: "
                    f"{result_text}"
                ),
            ]

            frame = (
                draw_text_box(
                    frame,
                    lines,
                    top=15,
                )
            )

            writer.write(
                frame
            )

            frame_index += 1

    finally:

        capture.release()

        writer.release()

    # ========================================================
    # VERIFY TEMP VIDEO
    # ========================================================

    if (
        not temp_file.exists()
        or
        temp_file.stat().st_size
        ==
        0
    ):

        raise RuntimeError(
            "สร้างไฟล์วิดีโอชั่วคราวไม่สำเร็จ:\n"
            f"{temp_file}"
        )

    # ========================================================
    # MOVE TO REAL UNICODE PATH
    # ========================================================

    try:

        if output_path.exists():
            output_path.unlink()

        shutil.move(
            str(
                temp_file
            ),
            str(
                output_path
            ),
        )

    except Exception as exc:

        raise RuntimeError(
            "ย้าย Evidence Clip "
            "ไปยัง Output Folder ไม่สำเร็จ:\n"
            f"{output_path}\n\n"
            f"{exc}"
        )


# ============================================================
# EXPORT SUMMARY CSV
# ============================================================

def export_summary_csv(
    path,
    events,
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
        "evidence_image",
        "evidence_clip",
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

        for event in events:

            writer.writerow(
                {
                    "posture": (
                        event[
                            "posture"
                        ]
                    ),

                    "human_event": (
                        event[
                            "event_number"
                        ]
                    ),

                    "human_start_sec": (
                        event[
                            "human_start_sec"
                        ]
                    ),

                    "human_end_sec": (
                        event[
                            "human_end_sec"
                        ]
                    ),

                    "human_duration_sec": (
                        event[
                            "human_duration_sec"
                        ]
                    ),

                    "detected": (
                        event[
                            "detected"
                        ]
                    ),

                    "system_overlap_sec": (
                        event[
                            "system_overlap_sec"
                        ]
                    ),

                    "system_intervals": (
                        "; ".join(
                            (
                                f"{start:.3f}"
                                "-"
                                f"{end:.3f}"
                            )
                            for (
                                start,
                                end,
                            )
                            in event[
                                "system_intervals"
                            ]
                        )
                    ),

                    "evidence_image": (
                        event[
                            "evidence_image"
                        ]
                    ),

                    "evidence_clip": (
                        event[
                            "evidence_clip"
                        ]
                    ),
                }
            )


# ============================================================
# CREATE HTML REPORT
# ============================================================

def create_html_report(
    output_path,
    video_name,
    events,
):

    grouped = {}

    for event in events:

        posture = (
            event[
                "posture"
            ]
        )

        grouped.setdefault(
            posture,
            [],
        ).append(
            event
        )

    total = len(
        events
    )

    detected = sum(
        1
        for event in events
        if event[
            "detected"
        ]
    )

    missed = (
        total
        -
        detected
    )

    rate = (
        detected
        /
        total
        *
        100.0
        if total
        else 0.0
    )

    parts = [
        "<!DOCTYPE html>",

        "<html lang='th'>",

        "<head>",

        "<meta charset='utf-8'>",

        (
            "<meta name='viewport' "
            "content='width=device-width, initial-scale=1'>"
        ),

        "<title>PostGuard Evidence Report</title>",

        """
<style>

body {
    font-family: Arial, sans-serif;
    margin: 30px;
    background: #f4f5f7;
    color: #222;
}

h1, h2, h3 {
    margin-bottom: 8px;
}

.summary {
    background: white;
    padding: 18px;
    border-radius: 10px;
    margin-bottom: 25px;
}

.event {
    background: white;
    padding: 16px;
    margin: 15px 0;
    border-radius: 10px;
    border-left: 6px solid #999;
}

.detected {
    border-left-color: #2e8b57;
}

.missed {
    border-left-color: #c0392b;
}

.status-detected {
    color: #2e8b57;
    font-weight: bold;
}

.status-missed {
    color: #c0392b;
    font-weight: bold;
}

img {
    max-width: 100%;
    margin-top: 10px;
    border-radius: 6px;
}

table {
    border-collapse: collapse;
    width: 100%;
    background: white;
}

th,
td {
    border: 1px solid #ddd;
    padding: 9px;
}

th {
    background: #edf1f5;
}

a {
    color: #1f5aa6;
}

</style>
""",

        "</head>",

        "<body>",

        "<h1>PostGuard Detection Evidence Report</h1>",

        "<div class='summary'>",

        (
            "<b>Video:</b> "
            +
            html.escape(
                video_name
            )
            +
            "<br>"
        ),

        (
            f"<b>Human Events:</b> "
            f"{total}<br>"
        ),

        (
            f"<b>Detected:</b> "
            f"{detected}<br>"
        ),

        (
            f"<b>Missed:</b> "
            f"{missed}<br>"
        ),

        (
            f"<b>Event Detection Rate:</b> "
            f"{rate:.2f}%"
        ),

        "</div>",

        "<h2>Summary by Posture</h2>",

        "<table>",

        (
            "<tr>"
            "<th>Posture</th>"
            "<th>Human Events</th>"
            "<th>Detected</th>"
            "<th>Missed</th>"
            "<th>Detection Rate</th>"
            "</tr>"
        ),
    ]

    # ========================================================
    # SUMMARY TABLE
    # ========================================================

    for (
        posture,
        posture_events,
    ) in grouped.items():

        event_count = len(
            posture_events
        )

        posture_detected = sum(
            1
            for event
            in posture_events
            if event[
                "detected"
            ]
        )

        posture_missed = (
            event_count
            -
            posture_detected
        )

        posture_rate = (
            posture_detected
            /
            event_count
            *
            100.0
            if event_count
            else 0.0
        )

        parts.append(
            "<tr>"
            f"<td>{html.escape(posture)}</td>"
            f"<td>{event_count}</td>"
            f"<td>{posture_detected}</td>"
            f"<td>{posture_missed}</td>"
            f"<td>{posture_rate:.2f}%</td>"
            "</tr>"
        )

    parts.append(
        "</table>"
    )

    # ========================================================
    # EVENT DETAILS
    # ========================================================

    for (
        posture,
        posture_events,
    ) in grouped.items():

        parts.append(
            f"<h2>"
            f"{html.escape(posture)}"
            f"</h2>"
        )

        for event in posture_events:

            if event[
                "detected"
            ]:

                css_class = (
                    "detected"
                )

                status_class = (
                    "status-detected"
                )

                status = (
                    "DETECTED"
                )

            else:

                css_class = (
                    "missed"
                )

                status_class = (
                    "status-missed"
                )

                status = (
                    "MISSED"
                )

            parts.append(
                f"<div class='event {css_class}'>"
            )

            parts.append(
                (
                    f"<h3>"
                    f"Event #{event['event_number']} "
                    f"<span class='{status_class}'>"
                    f"{status}"
                    f"</span>"
                    f"</h3>"
                )
            )

            parts.append(
                (
                    "<p>"
                    "Human: "
                    f"{format_time(event['human_start_sec'])}"
                    " - "
                    f"{format_time(event['human_end_sec'])}"
                    "</p>"
                )
            )

            if event[
                "system_intervals"
            ]:

                system_text = ", ".join(
                    (
                        f"{format_time(start)}"
                        "-"
                        f"{format_time(end)}"
                    )
                    for (
                        start,
                        end,
                    )
                    in event[
                        "system_intervals"
                    ]
                )

                parts.append(
                    (
                        "<p>"
                        "System overlap: "
                        f"{html.escape(system_text)}"
                        "</p>"
                    )
                )

            else:

                parts.append(
                    "<p>System overlap: none</p>"
                )

            image_path = (
                event[
                    "evidence_image"
                ]
                .replace(
                    "\\",
                    "/",
                )
            )

            clip_path = (
                event[
                    "evidence_clip"
                ]
                .replace(
                    "\\",
                    "/",
                )
            )

            parts.append(
                (
                    f"<img "
                    f"src='{html.escape(image_path)}' "
                    f"alt='Evidence'>"
                )
            )

            parts.append(
                (
                    "<p>"
                    f"<a href='{html.escape(clip_path)}'>"
                    "Open Evidence Clip"
                    "</a>"
                    "</p>"
                )
            )

            parts.append(
                "</div>"
            )

    parts.extend(
        [
            "</body>",
            "</html>",
        ]
    )

    output_path.write_text(
        "\n".join(
            parts
        ),
        encoding="utf-8",
    )


# ============================================================
# EXPORT ALL
# ============================================================

def export_all_evidence(
    video_path,
    event_details_path,
    output_dir,
    status_callback=None,
):

    video_path = Path(
        video_path
    )

    event_details_path = Path(
        event_details_path
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Output folders
    # --------------------------------------------------------

    image_dir = (
        output_dir
        /
        "keyframes"
    )

    clip_dir = (
        output_dir
        /
        "event_clips"
    )

    image_dir.mkdir(
        exist_ok=True
    )

    clip_dir.mkdir(
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    info = (
        read_video_info(
            video_path
        )
    )

    events = (
        load_event_details(
            event_details_path
        )
    )

    if not events:

        raise RuntimeError(
            "ไม่พบ Event ใน event_details.csv"
        )

    capture = cv2.VideoCapture(
        str(
            video_path
        )
    )

    if not capture.isOpened():

        raise RuntimeError(
            "เปิดวิดีโอไม่ได้"
        )

    try:

        for (
            index,
            event,
        ) in enumerate(
            events,
            start=1,
        ):

            posture_name = safe_name(
                event[
                    "posture"
                ]
            )

            if event[
                "detected"
            ]:

                result_name = (
                    "DETECTED"
                )

            else:

                result_name = (
                    "MISSED"
                )

            base_name = (
                f"{posture_name}"
                f"_event_"
                f"{event['event_number']:03d}"
                f"_"
                f"{result_name}"
            )

            image_name = (
                base_name
                +
                ".jpg"
            )

            clip_name = (
                base_name
                +
                ".mp4"
            )

            image_path = (
                image_dir
                /
                image_name
            )

            clip_path = (
                clip_dir
                /
                clip_name
            )

            # =================================================
            # IMAGE
            # =================================================

            export_comparison_image(
                capture,
                info[
                    "fps"
                ],
                event,
                image_path,
            )

            # =================================================
            # MINI CLIP
            # =================================================

            export_event_clip(
                video_path,
                info,
                event,
                clip_path,
            )

            event[
                "evidence_image"
            ] = str(
                Path(
                    "keyframes"
                )
                /
                image_name
            )

            event[
                "evidence_clip"
            ] = str(
                Path(
                    "event_clips"
                )
                /
                clip_name
            )

            if status_callback:

                status_callback(
                    (
                        f"Exporting "
                        f"{index}/"
                        f"{len(events)} | "
                        f"{event['posture']} | "
                        f"{result_name}"
                    )
                )

    finally:

        capture.release()

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary_path = (
        output_dir
        /
        "evidence_summary.csv"
    )

    export_summary_csv(
        summary_path,
        events,
    )

    # --------------------------------------------------------
    # HTML Report
    # --------------------------------------------------------

    html_path = (
        output_dir
        /
        "evidence_report.html"
    )

    create_html_report(
        html_path,
        video_path.name,
        events,
    )

    detected_count = sum(
        1
        for event in events
        if event[
            "detected"
        ]
    )

    return {
        "events": len(
            events
        ),

        "detected": (
            detected_count
        ),

        "missed": (
            len(events)
            -
            detected_count
        ),

        "summary": str(
            summary_path
        ),

        "html_report": str(
            html_path
        ),

        "output_dir": str(
            output_dir
        ),
    }


# ============================================================
# GUI
# ============================================================

class EvidenceExporterApp:

    def __init__(
        self,
        root,
    ):

        self.root = root

        self.root.title(
            APP_TITLE
        )

        self.root.geometry(
            "900x430"
        )

        self.video_var = (
            tk.StringVar()
        )

        self.details_var = (
            tk.StringVar()
        )

        self.output_var = (
            tk.StringVar()
        )

        self.status_var = (
            tk.StringVar(
                value="Ready"
            )
        )

        self._build_ui()


    def _build_ui(
        self,
    ):

        frame = ttk.Frame(
            self.root,
            padding=18,
        )

        frame.pack(
            fill="both",
            expand=True,
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        ttk.Label(
            frame,

            text=(
                "PostGuard Detection Evidence Exporter"
            ),

            font=(
                "TkDefaultFont",
                14,
                "bold",
            ),
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 16),
        )


        # ----------------------------------------------------
        # VIDEO
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="Original Video",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=5,
        )


        ttk.Entry(
            frame,
            textvariable=(
                self.video_var
            ),
            width=75,
        ).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=6,
        )


        ttk.Button(
            frame,
            text="Browse",
            command=(
                self.choose_video
            ),
        ).grid(
            row=1,
            column=2,
        )


        # ----------------------------------------------------
        # EVENT DETAILS
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="event_details.csv",
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=5,
        )


        ttk.Entry(
            frame,
            textvariable=(
                self.details_var
            ),
            width=75,
        ).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=6,
        )


        ttk.Button(
            frame,
            text="Browse",
            command=(
                self.choose_event_details
            ),
        ).grid(
            row=2,
            column=2,
        )


        # ----------------------------------------------------
        # OUTPUT
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="Output Folder",
        ).grid(
            row=3,
            column=0,
            sticky="w",
            pady=5,
        )


        ttk.Entry(
            frame,
            textvariable=(
                self.output_var
            ),
            width=75,
        ).grid(
            row=3,
            column=1,
            sticky="ew",
            padx=6,
        )


        ttk.Button(
            frame,
            text="Browse",
            command=(
                self.choose_output
            ),
        ).grid(
            row=3,
            column=2,
        )


        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description = (
            "ใช้ผล Validation เดิมได้เลย ไม่ต้องตรวจจับใหม่ "
            "และไม่ต้องทำ Human Ground Truth ใหม่\n\n"
            "โปรแกรมจะอ่าน Human Event และช่วงที่ PostGuard "
            "ตรวจเจอจาก event_details.csv แล้วดึงภาพและคลิป "
            "จากวิดีโอต้นฉบับให้อัตโนมัติ"
        )


        ttk.Label(
            frame,
            text=(
                description
            ),
            wraplength=820,
        ).grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(18, 14),
        )


        # ----------------------------------------------------
        # EXPORT
        # ----------------------------------------------------

        ttk.Button(
            frame,

            text=(
                "EXPORT IMAGE + EVENT CLIP + HTML REPORT"
            ),

            command=(
                self.run_export
            ),
        ).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=8,
        )


        ttk.Label(
            frame,
            textvariable=(
                self.status_var
            ),
            wraplength=820,
        ).grid(
            row=6,
            column=0,
            columnspan=3,
            sticky="w",
            pady=8,
        )


        frame.columnconfigure(
            1,
            weight=1,
        )


    # ========================================================
    # FILE PICKERS
    # ========================================================

    def choose_video(
        self,
    ):

        path = (
            filedialog.askopenfilename(
                title=(
                    "Choose Original Video"
                ),
                filetypes=[
                    (
                        "Video files",
                        "*.mp4 *.avi *.mov *.mkv",
                    ),
                    (
                        "All files",
                        "*.*",
                    ),
                ],
            )
        )

        if path:

            self.video_var.set(
                path
            )


    def choose_event_details(
        self,
    ):

        path = (
            filedialog.askopenfilename(
                title=(
                    "Choose event_details.csv"
                ),
                filetypes=[
                    (
                        "CSV files",
                        "*.csv",
                    ),
                    (
                        "All files",
                        "*.*",
                    ),
                ],
            )
        )

        if path:

            self.details_var.set(
                path
            )


    def choose_output(
        self,
    ):

        path = (
            filedialog.askdirectory(
                title=(
                    "Choose Output Folder"
                )
            )
        )

        if path:

            self.output_var.set(
                path
            )


    # ========================================================
    # STATUS
    # ========================================================

    def update_status(
        self,
        text,
    ):

        self.status_var.set(
            text
        )

        self.root.update_idletasks()


    # ========================================================
    # RUN
    # ========================================================

    def run_export(
        self,
    ):

        video_path = (
            self.video_var.get()
            .strip()
        )

        details_path = (
            self.details_var.get()
            .strip()
        )

        output_dir = (
            self.output_var.get()
            .strip()
        )


        if (
            not video_path
            or
            not details_path
            or
            not output_dir
        ):

            messagebox.showwarning(
                "Missing Input",

                (
                    "เลือกให้ครบ:\n\n"
                    "1. Original Video\n"
                    "2. event_details.csv\n"
                    "3. Output Folder"
                ),
            )

            return


        try:

            report = (
                export_all_evidence(
                    video_path,
                    details_path,
                    output_dir,
                    status_callback=(
                        self.update_status
                    ),
                )
            )


            self.status_var.set(
                (
                    f"Finished | "
                    f"Events="
                    f"{report['events']} | "
                    f"Detected="
                    f"{report['detected']} | "
                    f"Missed="
                    f"{report['missed']}"
                )
            )


            messagebox.showinfo(
                "Evidence Export Complete",

                (
                    "สร้างหลักฐานเรียบร้อย\n\n"

                    f"Human Events: "
                    f"{report['events']}\n"

                    f"Detected: "
                    f"{report['detected']}\n"

                    f"Missed: "
                    f"{report['missed']}\n\n"

                    "HTML Report:\n"
                    f"{report['html_report']}"
                ),
            )


            # เปิด HTML อัตโนมัติบน Windows
            try:

                os.startfile(
                    report[
                        "html_report"
                    ]
                )

            except Exception:

                pass


        except Exception as exc:

            self.status_var.set(
                "Export Failed"
            )

            messagebox.showerror(
                "Export Failed",
                str(
                    exc
                ),
            )


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    EvidenceExporterApp(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()