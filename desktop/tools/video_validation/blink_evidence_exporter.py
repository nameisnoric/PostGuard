from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2


APP_TITLE = "PostGuard Blink Evidence Exporter"


# ============================================================
# SETTINGS
# ============================================================

# ภาพก่อน/หลัง blink ห่างจากจุดกลางกี่วินาที
FRAME_OFFSET_SECONDS = 0.15

# mini clip ก่อนและหลัง blink
CLIP_PADDING_SECONDS = 0.75


# ============================================================
# HELPERS
# ============================================================

def finite_number(value):
    try:
        value = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(value):
        return None

    return value


def format_time(seconds):
    seconds = max(
        0.0,
        float(seconds),
    )

    minute = int(
        seconds // 60
    )

    remain = (
        seconds
        -
        minute * 60
    )

    return (
        f"{minute:02d}:"
        f"{remain:06.3f}"
    )


def save_image_unicode(
    path,
    image,
):
    """
    รองรับ path ภาษาไทยบน Windows
    """

    path = Path(
        path
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    extension = (
        path.suffix.lower()
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
            "Cannot encode image"
        )

    encoded.tofile(
        str(
            path
        )
    )


# ============================================================
# LOAD REPORT
# ============================================================

def load_blink_report(
    report_path,
):
    """
    รองรับ report เวอร์ชัน Clip 2 เดิม:

    "blink": {
        "human_blinks": 74,
        "system_blinks": 77,
        "matched": 46,
        "missed": 28,
        "matches": [...]
    }

    และรองรับ v4:
        blink.summary
        blink.details
    """

    with open(
        report_path,
        "r",
        encoding="utf-8",
    ) as handle:

        report = json.load(
            handle
        )

    blink = report.get(
        "blink",
        {}
    )

    events = []

    # ========================================================
    # V4 FORMAT
    # ========================================================

    if (
        isinstance(
            blink,
            dict,
        )
        and
        "details"
        in blink
    ):

        details = (
            blink.get(
                "details",
                [],
            )
        )

        for row in details:

            result = (
                row.get(
                    "result"
                )
                or ""
            ).upper()

            if result not in (
                "MATCH",
                "MISSED",
                "SYSTEM_ONLY",
            ):
                continue

            events.append(
                {
                    "result": result,

                    "human_event": (
                        row.get(
                            "human_event"
                        )
                    ),

                    "human_time": (
                        finite_number(
                            row.get(
                                "human_time_sec"
                            )
                        )
                    ),

                    "system_time": (
                        finite_number(
                            row.get(
                                "system_time_sec"
                            )
                        )
                    ),

                    "error": (
                        finite_number(
                            row.get(
                                "time_error_sec"
                            )
                        )
                    ),
                }
            )

        return (
            report,
            events,
        )

    # ========================================================
    # OLD CLIP 2 FORMAT
    # ========================================================

    matches = (
        blink.get(
            "matches",
            []
        )
    )

    human_count = int(
        blink.get(
            "human_blinks",
            0,
        )
    )

    system_count = int(
        blink.get(
            "system_blinks",
            0,
        )
    )

    matched_human_times = set()

    matched_system_times = set()


    for index, match in enumerate(
        matches,
        start=1,
    ):

        human_time = finite_number(
            match.get(
                "human_time"
            )
        )

        system_time = finite_number(
            match.get(
                "system_time"
            )
        )

        if (
            human_time is None
            or
            system_time is None
        ):
            continue

        matched_human_times.add(
            human_time
        )

        matched_system_times.add(
            system_time
        )

        events.append(
            {
                "result": (
                    "MATCH"
                ),

                "human_event": (
                    index
                ),

                "human_time": (
                    human_time
                ),

                "system_time": (
                    system_time
                ),

                "error": abs(
                    system_time
                    -
                    human_time
                ),
            }
        )

    # NOTE:
    # report เก่ามีเฉพาะ match list
    # แต่ไม่ได้เก็บ timestamp ของ human missed / system only
    #
    # ดังนั้นสามารถสร้างภาพ MATCH ได้ครบ
    # แต่ MISSED / SYSTEM_ONLY ต้องใช้ blink_details.csv จาก v4

    return (
        report,
        events,
    )


# ============================================================
# VIDEO
# ============================================================

def get_video_info(
    path,
):
    capture = cv2.VideoCapture(
        str(
            path
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

    count = int(
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
        or count <= 0
    ):
        raise RuntimeError(
            "Invalid video"
        )

    return {
        "fps": fps,
        "frame_count": count,
        "width": width,
        "height": height,
        "duration": (
            count
            /
            fps
        ),
    }


def read_frame_at(
    capture,
    fps,
    timestamp,
):
    timestamp = max(
        0.0,
        timestamp,
    )

    frame_index = int(
        round(
            timestamp
            *
            fps
        )
    )

    capture.set(
        cv2.CAP_PROP_POS_FRAMES,
        frame_index,
    )

    ok, frame = capture.read()

    if not ok:
        return None

    return frame


# ============================================================
# DRAWING
# ============================================================

def draw_header(
    image,
    title,
    subtitle,
):
    image = image.copy()

    overlay = image.copy()

    cv2.rectangle(
        overlay,
        (0, 0),
        (
            image.shape[1],
            80,
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
        image,
        0.35,
        0,
        image,
    )

    cv2.putText(
        image,
        title,
        (
            15,
            30,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (
            255,
            255,
            255,
        ),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        image,
        subtitle,
        (
            15,
            62,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (
            230,
            230,
            230,
        ),
        1,
        cv2.LINE_AA,
    )

    return image


def create_panel(
    frame,
    title,
    timestamp,
    width=480,
    height=360,
):
    frame = cv2.resize(
        frame,
        (
            width,
            height,
        ),
    )

    return draw_header(
        frame,
        title,
        format_time(
            timestamp
        ),
    )


# ============================================================
# MATCH IMAGE
# ============================================================

def create_match_image(
    capture,
    fps,
    event,
    output_path,
):
    """
    สร้างภาพ 3 ช่อง:

    BEFORE
    HUMAN BLINK
    SYSTEM BLINK

    ทำให้เห็นว่า Human และ System เจอเหตุการณ์เดียวกัน
    """

    human_time = (
        event[
            "human_time"
        ]
    )

    system_time = (
        event[
            "system_time"
        ]
    )

    before_time = max(
        0.0,
        human_time
        -
        FRAME_OFFSET_SECONDS,
    )

    before_frame = (
        read_frame_at(
            capture,
            fps,
            before_time,
        )
    )

    human_frame = (
        read_frame_at(
            capture,
            fps,
            human_time,
        )
    )

    system_frame = (
        read_frame_at(
            capture,
            fps,
            system_time,
        )
    )

    if (
        before_frame is None
        or
        human_frame is None
        or
        system_frame is None
    ):
        raise RuntimeError(
            "Cannot read blink frames"
        )

    before_panel = (
        create_panel(
            before_frame,
            "BEFORE BLINK",
            before_time,
        )
    )

    human_panel = (
        create_panel(
            human_frame,
            "HUMAN BLINK",
            human_time,
        )
    )

    system_panel = (
        create_panel(
            system_frame,
            "POSTGUARD BLINK",
            system_time,
        )
    )

    combined = cv2.hconcat(
        [
            before_panel,
            human_panel,
            system_panel,
        ]
    )

    footer_height = 90

    canvas = cv2.copyMakeBorder(
        combined,
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

    line1 = (
        f"Human: "
        f"{format_time(human_time)}"
        f"   |   "
        f"PostGuard: "
        f"{format_time(system_time)}"
    )

    line2 = (
        f"Difference: "
        f"{event['error']:.3f} sec"
        f"   |   "
        f"Result: MATCH"
    )

    cv2.putText(
        canvas,
        line1,
        (
            20,
            combined.shape[0]
            +
            35,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (
            255,
            255,
            255,
        ),
        1,
        cv2.LINE_AA,
    )

    cv2.putText(
        canvas,
        line2,
        (
            20,
            combined.shape[0]
            +
            68,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
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
# MISSED IMAGE
# ============================================================

def create_missed_image(
    capture,
    fps,
    event,
    output_path,
):
    human_time = (
        event[
            "human_time"
        ]
    )

    before_time = max(
        0,
        human_time
        -
        FRAME_OFFSET_SECONDS,
    )

    after_time = (
        human_time
        +
        FRAME_OFFSET_SECONDS
    )

    before = read_frame_at(
        capture,
        fps,
        before_time,
    )

    blink = read_frame_at(
        capture,
        fps,
        human_time,
    )

    after = read_frame_at(
        capture,
        fps,
        after_time,
    )

    if (
        before is None
        or
        blink is None
        or
        after is None
    ):
        raise RuntimeError(
            "Cannot read frames"
        )

    panels = [
        create_panel(
            before,
            "BEFORE",
            before_time,
        ),

        create_panel(
            blink,
            "HUMAN BLINK",
            human_time,
        ),

        create_panel(
            after,
            "AFTER",
            after_time,
        ),
    ]

    combined = cv2.hconcat(
        panels
    )

    canvas = cv2.copyMakeBorder(
        combined,
        0,
        90,
        0,
        0,
        cv2.BORDER_CONSTANT,
        value=(
            25,
            25,
            25,
        ),
    )

    cv2.putText(
        canvas,
        (
            f"Human Blink: "
            f"{format_time(human_time)}"
        ),
        (
            20,
            combined.shape[0]
            +
            35,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (
            255,
            255,
            255,
        ),
        1,
        cv2.LINE_AA,
    )

    cv2.putText(
        canvas,
        (
            "PostGuard Blink: NONE   |   "
            "Result: MISSED"
        ),
        (
            20,
            combined.shape[0]
            +
            68,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
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
# SYSTEM ONLY IMAGE
# ============================================================

def create_system_only_image(
    capture,
    fps,
    event,
    output_path,
):
    system_time = (
        event[
            "system_time"
        ]
    )

    before_time = max(
        0,
        system_time
        -
        FRAME_OFFSET_SECONDS,
    )

    after_time = (
        system_time
        +
        FRAME_OFFSET_SECONDS
    )

    before = read_frame_at(
        capture,
        fps,
        before_time,
    )

    blink = read_frame_at(
        capture,
        fps,
        system_time,
    )

    after = read_frame_at(
        capture,
        fps,
        after_time,
    )

    if (
        before is None
        or
        blink is None
        or
        after is None
    ):
        raise RuntimeError(
            "Cannot read frames"
        )

    combined = cv2.hconcat(
        [
            create_panel(
                before,
                "BEFORE",
                before_time,
            ),

            create_panel(
                blink,
                "POSTGUARD BLINK",
                system_time,
            ),

            create_panel(
                after,
                "AFTER",
                after_time,
            ),
        ]
    )

    canvas = cv2.copyMakeBorder(
        combined,
        0,
        90,
        0,
        0,
        cv2.BORDER_CONSTANT,
        value=(
            25,
            25,
            25,
        ),
    )

    cv2.putText(
        canvas,
        (
            "Human Blink: NONE"
        ),
        (
            20,
            combined.shape[0]
            +
            35,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (
            255,
            255,
            255,
        ),
        1,
        cv2.LINE_AA,
    )

    cv2.putText(
        canvas,
        (
            f"PostGuard: "
            f"{format_time(system_time)}"
            f"   |   "
            f"Result: SYSTEM ONLY"
        ),
        (
            20,
            combined.shape[0]
            +
            68,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
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
# HTML REPORT
# ============================================================

def create_html_report(
    path,
    video_name,
    event_records,
):
    html_parts = [
        """
<!DOCTYPE html>
<html lang="th">

<head>
<meta charset="utf-8">

<title>PostGuard Blink Evidence</title>

<style>

body {
    font-family: Arial, sans-serif;
    margin: 30px;
    background: #f4f5f7;
}

h1 {
    margin-bottom: 5px;
}

.event {
    background: white;
    padding: 18px;
    margin: 20px 0;
    border-radius: 10px;
}

.match {
    border-left: 7px solid #2e8b57;
}

.missed {
    border-left: 7px solid #c0392b;
}

.system-only {
    border-left: 7px solid #d68910;
}

img {
    width: 100%;
    max-width: 1500px;
    border-radius: 8px;
    margin-top: 10px;
}

.MATCH {
    color: #2e8b57;
}

.MISSED {
    color: #c0392b;
}

.SYSTEM_ONLY {
    color: #d68910;
}

</style>

</head>

<body>
"""
    ]

    html_parts.append(
        "<h1>"
        "PostGuard Blink Detection Evidence"
        "</h1>"
    )

    html_parts.append(
        f"<p>Video: "
        f"{video_name}</p>"
    )

    for index, event in enumerate(
        event_records,
        start=1,
    ):
        result = (
            event[
                "result"
            ]
        )

        if result == "MATCH":
            css = "match"

        elif result == "MISSED":
            css = "missed"

        else:
            css = "system-only"

        html_parts.append(
            (
                f"<div class='event {css}'>"
                f"<h2>"
                f"Blink Event #{index} "
                f"<span class='{result}'>"
                f"{result}"
                f"</span>"
                f"</h2>"
            )
        )

        if (
            event.get(
                "human_time"
            )
            is not None
        ):
            html_parts.append(
                (
                    f"<p>Human: "
                    f"{format_time(event['human_time'])}"
                    f"</p>"
                )
            )

        if (
            event.get(
                "system_time"
            )
            is not None
        ):
            html_parts.append(
                (
                    f"<p>System: "
                    f"{format_time(event['system_time'])}"
                    f"</p>"
                )
            )

        if (
            event.get(
                "error"
            )
            is not None
        ):
            html_parts.append(
                (
                    f"<p>Difference: "
                    f"{event['error']:.3f} sec"
                    f"</p>"
                )
            )

        html_parts.append(
            (
                f"<img "
                f"src='{event['image_name']}'>"
            )
        )

        html_parts.append(
            "</div>"
        )

    html_parts.extend(
        [
            "</body>",
            "</html>",
        ]
    )

    Path(
        path
    ).write_text(
        "\n".join(
            html_parts
        ),
        encoding="utf-8",
    )


# ============================================================
# EXPORT
# ============================================================

def export_blink_evidence(
    video_path,
    report_path,
    output_dir,
    status_callback=None,
):
    video_path = Path(
        video_path
    )

    report_path = Path(
        report_path
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    image_dir = (
        output_dir
        /
        "blink_keyframes"
    )

    image_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    info = get_video_info(
        video_path
    )

    report, events = (
        load_blink_report(
            report_path
        )
    )

    if not events:
        raise RuntimeError(
            "No Blink event data found"
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

    records = []

    try:
        for index, event in enumerate(
            events,
            start=1,
        ):

            result = (
                event[
                    "result"
                ]
            )

            image_name = (
                f"blink_"
                f"{index:03d}_"
                f"{result}.jpg"
            )

            image_path = (
                image_dir
                /
                image_name
            )

            if result == "MATCH":

                create_match_image(
                    capture,
                    info[
                        "fps"
                    ],
                    event,
                    image_path,
                )

            elif result == "MISSED":

                create_missed_image(
                    capture,
                    info[
                        "fps"
                    ],
                    event,
                    image_path,
                )

            elif result == "SYSTEM_ONLY":

                create_system_only_image(
                    capture,
                    info[
                        "fps"
                    ],
                    event,
                    image_path,
                )

            record = dict(
                event
            )

            record[
                "image_name"
            ] = (
                "blink_keyframes/"
                +
                image_name
            )

            records.append(
                record
            )

            if status_callback:

                status_callback(
                    (
                        f"Export "
                        f"{index}/"
                        f"{len(events)} "
                        f"{result}"
                    )
                )

    finally:

        capture.release()

    html_path = (
        output_dir
        /
        "blink_evidence_report.html"
    )

    create_html_report(
        html_path,
        video_path.name,
        records,
    )

    return {
        "count": len(
            records
        ),
        "output": str(
            output_dir
        ),
        "html": str(
            html_path
        ),
    }


# ============================================================
# GUI
# ============================================================

class App:

    def __init__(
        self,
        root,
    ):
        self.root = root

        self.root.title(
            APP_TITLE
        )

        self.root.geometry(
            "900x400"
        )

        self.video_var = (
            tk.StringVar()
        )

        self.report_var = (
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

        self.build_ui()


    def build_ui(
        self,
    ):
        frame = ttk.Frame(
            self.root,
            padding=20,
        )

        frame.pack(
            fill="both",
            expand=True,
        )

        ttk.Label(
            frame,
            text=(
                "PostGuard Blink Evidence Exporter"
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
            pady=(0, 20),
        )

        # VIDEO

        ttk.Label(
            frame,
            text="Original Video",
        ).grid(
            row=1,
            column=0,
            sticky="w",
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
            padx=5,
            sticky="ew",
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

        # REPORT

        ttk.Label(
            frame,
            text=(
                "Validation Report JSON"
            ),
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=8,
        )

        ttk.Entry(
            frame,
            textvariable=(
                self.report_var
            ),
            width=75,
        ).grid(
            row=2,
            column=1,
            padx=5,
            sticky="ew",
        )

        ttk.Button(
            frame,
            text="Browse",
            command=(
                self.choose_report
            ),
        ).grid(
            row=2,
            column=2,
        )

        # OUTPUT

        ttk.Label(
            frame,
            text=(
                "Output Folder"
            ),
        ).grid(
            row=3,
            column=0,
            sticky="w",
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
            padx=5,
            sticky="ew",
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

        ttk.Label(
            frame,
            text=(
                "สร้างภาพเปรียบเทียบ Blink "
                "จากผล Validation เดิม "
                "ไม่ต้องทำ Human Ground Truth ใหม่"
            ),
        ).grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="w",
            pady=20,
        )

        ttk.Button(
            frame,
            text=(
                "EXPORT BLINK COMPARISON IMAGES"
            ),
            command=(
                self.run
            ),
        ).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="ew",
        )

        ttk.Label(
            frame,
            textvariable=(
                self.status_var
            ),
        ).grid(
            row=6,
            column=0,
            columnspan=3,
            sticky="w",
            pady=10,
        )

        frame.columnconfigure(
            1,
            weight=1,
        )


    def choose_video(
        self,
    ):
        path = filedialog.askopenfilename(
            filetypes=[
                (
                    "Video",
                    "*.mp4 *.avi *.mov *.mkv",
                ),
            ]
        )

        if path:
            self.video_var.set(
                path
            )


    def choose_report(
        self,
    ):
        path = filedialog.askopenfilename(
            filetypes=[
                (
                    "JSON",
                    "*.json",
                ),
            ]
        )

        if path:
            self.report_var.set(
                path
            )


    def choose_output(
        self,
    ):
        path = filedialog.askdirectory()

        if path:
            self.output_var.set(
                path
            )


    def update_status(
        self,
        text,
    ):
        self.status_var.set(
            text
        )

        self.root.update_idletasks()


    def run(
        self,
    ):
        video = (
            self.video_var.get()
            .strip()
        )

        report = (
            self.report_var.get()
            .strip()
        )

        output = (
            self.output_var.get()
            .strip()
        )

        if (
            not video
            or
            not report
            or
            not output
        ):
            messagebox.showwarning(
                "Missing",
                (
                    "เลือก Video, "
                    "Validation Report "
                    "และ Output Folder ให้ครบ"
                ),
            )

            return

        try:

            result = (
                export_blink_evidence(
                    video,
                    report,
                    output,
                    self.update_status,
                )
            )

            self.status_var.set(
                "Finished"
            )

            messagebox.showinfo(
                "Complete",
                (
                    f"สร้างภาพ "
                    f"{result['count']} "
                    f"เหตุการณ์\n\n"
                    f"{result['html']}"
                ),
            )

            try:
                os.startfile(
                    result[
                        "html"
                    ]
                )

            except Exception:
                pass

        except Exception as exc:

            messagebox.showerror(
                "Error",
                str(
                    exc
                ),
            )


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    App(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()