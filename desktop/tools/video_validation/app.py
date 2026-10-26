
from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from collections import defaultdict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2

# ------------------------------------------------------------
# Resolve Desktop package so the existing PostGuard service
# can be imported when this script is launched directly.
# ------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DESKTOP_DIR = SCRIPT_DIR.parents[1]

if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

from app.services.detection_service import DetectionService


APP_TITLE = "PostGuard Offline Video Validation"

POSTURE_TYPES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
    "neck_extension",
)

# Initial values based on the prototype neutral limits discussed
# for PostGuard. These are editable test criteria, not clinical
# thresholds or a claim that the backend Assessment was invoked.
DEFAULT_THRESHOLDS = {
    "shoulder_tilt": 3.0,
    "neck_lateral_tilt": 10.0,
    "neck_flexion": 10.0,
    "neck_extension": 10.0,
}


def finite_number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def feature_value(result, name):
    features = result.get("features", {})
    feature = features.get(name, {})
    if not isinstance(feature, dict) or not feature.get("valid", False):
        return None
    return finite_number(feature.get("value"))


def posture_values(result):
    """Read the actual feature values returned by DetectionService."""
    shoulder = feature_value(result, "shoulder_tilt")
    lateral = feature_value(result, "neck_lateral_tilt")
    flexion = feature_value(result, "neck_flexion")

    # DetectionService currently also exposes these top-level values.
    # Prefer the feature contract; use the top-level value if needed.
    if shoulder is None:
        shoulder = finite_number(result.get("shoulder_tilt"))

    if lateral is None:
        raw = result.get("neck_lateral_tilt")
        if isinstance(raw, dict):
            lateral = finite_number(raw.get("neck_tilt"))

    if flexion is None:
        flexion = finite_number(result.get("neck_flexion"))

    return {
        "shoulder_tilt": shoulder,
        "neck_lateral_tilt": lateral,
        "neck_flexion": flexion,
        "neck_extension": (
            -flexion if flexion is not None else None
        ),
    }


def classify_postures(values, thresholds):
    """
    Apply editable evaluation criteria to PostGuard's measured angles.

    Positive neck_flexion means looking down according to the
    convention established for the PostGuard prototype.
    """
    found = []

    for name in POSTURE_TYPES:
        value = values.get(name)
        threshold = thresholds[name]

        if value is not None and abs(value) >= threshold:
            found.append(name)

    return found


def draw_landmarks(frame, result):
    """Draw selected landmarks returned by PostGuard DetectionService."""
    image = frame.copy()
    pose = result.get("pose_points") or {}
    face = result.get("face_points") or {}

    # Selected pose landmarks available in the current Desktop branch.
    pose_edges = [
        ("left_ear", "left_shoulder"),
        ("right_ear", "right_shoulder"),
        ("left_shoulder", "right_shoulder"),
        ("nose", "left_shoulder"),
        ("nose", "right_shoulder"),
    ]

    for first, second in pose_edges:
        a = pose.get(first)
        b = pose.get(second)
        if not a or not b:
            continue
        try:
            cv2.line(
                image,
                (int(a["x"]), int(a["y"])),
                (int(b["x"]), int(b["y"])),
                (0, 220, 255),
                2,
                cv2.LINE_AA,
            )
        except (KeyError, TypeError, ValueError):
            pass

    for name, point in pose.items():
        try:
            x, y = int(point["x"]), int(point["y"])
            cv2.circle(image, (x, y), 5, (0, 220, 255), -1)
            cv2.putText(
                image, name, (x + 5, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (0, 220, 255), 1, cv2.LINE_AA,
            )
        except (KeyError, TypeError, ValueError):
            pass

    # Draw the selected face points and useful eye/face connections.
    face_edges = [
        ("right_eye_outer", "right_eye_inner"),
        ("left_eye_outer", "left_eye_inner"),
        ("nose_tip", "chin"),
        ("right_face", "left_face"),
    ]

    for first, second in face_edges:
        a = face.get(first)
        b = face.get(second)
        if not a or not b:
            continue
        try:
            cv2.line(
                image,
                (int(a["x"]), int(a["y"])),
                (int(b["x"]), int(b["y"])),
                (255, 160, 0),
                1,
                cv2.LINE_AA,
            )
        except (KeyError, TypeError, ValueError):
            pass

    for name, point in face.items():
        try:
            x, y = int(point["x"]), int(point["y"])
            cv2.circle(image, (x, y), 3, (255, 160, 0), -1)
        except (KeyError, TypeError, ValueError):
            pass

    return image


def add_overlay_text(frame, timestamp, result, values, detected, eval_status):
    image = frame.copy()
    lines = [
        f"Time: {timestamp:.3f}s | Status: {eval_status}",
        "Detected: " + (", ".join(detected) if detected else "None"),
        "Shoulder: " + format_angle(values.get("shoulder_tilt")),
        "Neck lateral: " + format_angle(values.get("neck_lateral_tilt")),
        "Neck flexion: " + format_angle(values.get("neck_flexion")),
    ]

    y = 26
    for line in lines:
        cv2.putText(
            image, line, (12, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.58,
            (255, 255, 255), 3, cv2.LINE_AA,
        )
        cv2.putText(
            image, line, (12, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.58,
            (20, 20, 20), 1, cv2.LINE_AA,
        )
        y += 25

    return image


def format_angle(value):
    return "N/A" if value is None else f"{value:.2f} deg"


def load_annotations(path):
    annotations = []
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"type", "start", "end"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Annotation CSV must contain: type,start,end")

        for line_number, row in enumerate(reader, start=2):
            kind = (row.get("type") or "").strip().lower()
            start = finite_number(row.get("start"))
            end = finite_number(row.get("end"))

            if kind not in POSTURE_TYPES:
                raise ValueError(
                    f"CSV line {line_number}: unsupported type {kind!r}. "
                    f"Supported types: {', '.join(POSTURE_TYPES)}"
                )
            if start is None or end is None or start < 0 or end < start:
                raise ValueError(
                    f"CSV line {line_number}: invalid start/end time"
                )

            annotations.append({
                "type": kind,
                "start": start,
                "end": end,
            })

    return annotations


def save_annotations(path, annotations):
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["type", "start", "end"]
        )
        writer.writeheader()
        for item in annotations:
            writer.writerow({
                "type": item["type"],
                "start": f"{item['start']:.3f}",
                "end": f"{item['end']:.3f}",
            })


def annotation_is_active(annotations, kind, timestamp):
    return any(
        item["type"] == kind
        and item["start"] <= timestamp <= item["end"]
        for item in annotations
    )


def safe_divide(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def calculate_metrics(rows, annotations):
    """
    Frame-level classification.

    Human-positive frames that cannot be evaluated by the detector
    count as FN. Human-negative frames with unavailable measurements
    are excluded from confusion-matrix counts and reported separately.
    """
    summaries = {}

    for kind in POSTURE_TYPES:
        tp = fp = fn = tn = unevaluable = 0

        for row in rows:
            timestamp = row["timestamp_sec"]
            human_positive = annotation_is_active(
                annotations, kind, timestamp
            )
            system_positive = kind in row["detected_postures"]
            feature_valid = row["feature_valid"].get(kind, False)

            if not feature_valid:
                unevaluable += 1
                if human_positive:
                    fn += 1
                continue

            if human_positive and system_positive:
                tp += 1
            elif not human_positive and system_positive:
                fp += 1
            elif human_positive and not system_positive:
                fn += 1
            else:
                tn += 1

        precision = safe_divide(tp, tp + fp)
        recall = safe_divide(tp, tp + fn)
        f1 = safe_divide(2 * precision * recall, precision + recall)
        accuracy = safe_divide(tp + tn, tp + fp + fn + tn)

        summaries[kind] = {
            "type": kind,
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "TN": tn,
            "unevaluable_frames": unevaluable,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "accuracy": accuracy,
        }

    return summaries


def export_frame_csv(path, rows):
    columns = [
        "video_id", "frame_index", "timestamp_sec",
        "pose_detected", "face_detected", "context_valid",
        "assessment_status",
        "shoulder_tilt_deg", "neck_lateral_tilt_deg",
        "neck_flexion_deg", "neck_extension_deg",
        "detected_postures",
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                key: row.get(key, "")
                for key in columns
            })


def export_summary_csv(path, summaries):
    columns = [
        "type", "TP", "FP", "FN", "TN",
        "unevaluable_frames", "precision", "recall",
        "f1_score", "accuracy",
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for kind in POSTURE_TYPES:
            item = summaries[kind].copy()
            for metric in ("precision", "recall", "f1_score", "accuracy"):
                item[metric] = f"{item[metric]:.4f}"
            writer.writerow({key: item.get(key, "") for key in columns})


def export_timeline(path, rows, annotations):
    """
    Create a PNG timeline. Matplotlib is required for this export.
    Blue bars = human annotations; red bars = system detections.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        len(POSTURE_TYPES) + 1, 1,
        figsize=(14, 10), sharex=True,
        gridspec_kw={"height_ratios": [2] + [1] * len(POSTURE_TYPES)},
    )

    times = [r["timestamp_sec"] for r in rows]
    axes[0].plot(
        times,
        [r["shoulder_tilt_deg"] for r in rows],
        label="Shoulder tilt",
    )
    axes[0].plot(
        times,
        [r["neck_lateral_tilt_deg"] for r in rows],
        label="Neck lateral tilt",
    )
    axes[0].plot(
        times,
        [r["neck_flexion_deg"] for r in rows],
        label="Neck flexion",
    )
    axes[0].set_ylabel("Angle (deg)")
    axes[0].legend(loc="upper right")
    axes[0].grid(True, alpha=0.3)

    for index, kind in enumerate(POSTURE_TYPES, start=1):
        axis = axes[index]
        axis.set_yticks([0, 1])
        axis.set_yticklabels(["System", "Human"])
        axis.set_ylabel(kind, fontsize=8)
        axis.grid(True, axis="x", alpha=0.3)

        for annotation in annotations:
            if annotation["type"] == kind:
                axis.barh(
                    1,
                    annotation["end"] - annotation["start"],
                    left=annotation["start"],
                    height=0.35,
                    color="royalblue",
                )

        # Merge consecutive positive frames into visual intervals.
        active_start = None
        previous_time = None
        for row in rows:
            active = kind in row["detected_postures"]
            t = row["timestamp_sec"]
            if active and active_start is None:
                active_start = t
            if not active and active_start is not None:
                axis.barh(
                    0, max(0.001, previous_time - active_start),
                    left=active_start, height=0.35, color="crimson",
                )
                active_start = None
            previous_time = t

        if active_start is not None and previous_time is not None:
            axis.barh(
                0, max(0.001, previous_time - active_start),
                left=active_start, height=0.35, color="crimson",
            )

    axes[-1].set_xlabel("Video time (seconds)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run_evaluation(video_path, output_dir, annotations, thresholds, status_callback):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = finite_number(capture.get(cv2.CAP_PROP_FPS)) or 0.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if fps <= 0 or frame_count <= 0:
        capture.release()
        raise RuntimeError("Video FPS/frame count is unavailable or invalid")

    video_id = Path(video_path).stem
    output_video = output_dir / f"{video_id}_landmarks.mp4"
    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    if not writer.isOpened():
        capture.release()
        raise RuntimeError("Cannot create annotated MP4 output")

    detector = None
    rows = []

    try:
        detector = DetectionService()

        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            # Use source-video timestamps, not wall-clock processing time.
            timestamp = frame_index / fps

            result = detector.process_frame(frame)
            values = posture_values(result)
            context = result.get("context") or {}
            context_valid = bool(
                context.get("allow_posture_evaluation", False)
            )

            feature_valid = {
                "shoulder_tilt": (
                    context_valid and values["shoulder_tilt"] is not None
                ),
                "neck_lateral_tilt": (
                    context_valid and values["neck_lateral_tilt"] is not None
                ),
                "neck_flexion": (
                    context_valid and values["neck_flexion"] is not None
                ),
                "neck_extension": (
                    context_valid and values["neck_extension"] is not None
                ),
            }

            detected = (
                classify_postures(values, thresholds)
                if context_valid else []
            )
            eval_status = (
                "COMPLETE" if all(feature_valid.values())
                else "PARTIAL" if any(feature_valid.values())
                else "NOT_EVALUATED"
            )

            row = {
                "video_id": video_id,
                "frame_index": frame_index,
                "timestamp_sec": timestamp,
                "pose_detected": bool(result.get("pose_detected")),
                "face_detected": bool(result.get("face_detected")),
                "context_valid": context_valid,
                "assessment_status": eval_status,
                "shoulder_tilt_deg": values["shoulder_tilt"],
                "neck_lateral_tilt_deg": values["neck_lateral_tilt"],
                "neck_flexion_deg": values["neck_flexion"],
                "neck_extension_deg": values["neck_extension"],
                "detected_postures": detected,
                "feature_valid": feature_valid,
            }
            rows.append(row)

            image = draw_landmarks(frame, result)
            image = add_overlay_text(
                image, timestamp, result, values, detected, eval_status
            )
            writer.write(image)

            frame_index += 1
            if frame_index % max(1, int(fps)) == 0:
                status_callback(
                    f"Processing {frame_index}/{frame_count} frames "
                    f"({100 * frame_index / frame_count:.1f}%)"
                )

    finally:
        capture.release()
        writer.release()
        if detector is not None:
            detector.close()

    summaries = calculate_metrics(rows, annotations)

    # Convert the list to a readable field for CSV/JSON.
    export_rows = []
    for row in rows:
        item = dict(row)
        item["detected_postures"] = "|".join(row["detected_postures"])
        export_rows.append(item)

    export_frame_csv(output_dir / f"{video_id}_frame_results.csv", export_rows)
    export_summary_csv(output_dir / f"{video_id}_summary.csv", summaries)

    with open(
        output_dir / f"{video_id}_summary.json",
        "w", encoding="utf-8",
    ) as handle:
        json.dump(
            {
                "video": str(video_path),
                "fps": fps,
                "frames_processed": len(rows),
                "thresholds_deg": thresholds,
                "metrics": summaries,
                "note": (
                    "DetectionService is the existing PostGuard detector. "
                    "Labels are generated using the editable thresholds "
                    "recorded in this report."
                ),
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    export_timeline(
        output_dir / f"{video_id}_timeline.png",
        rows,
        annotations,
    )

    return {
        "frames": len(rows),
        "fps": fps,
        "video": str(output_video),
        "output_dir": str(output_dir),
        "summaries": summaries,
    }


class ValidationApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1050x760")

        self.video_path = None
        self.capture = None
        self.current_frame = None
        self.current_time = 0.0
        self.duration = 0.0
        self.annotations = []
        self.playing = False

        self.video_var = tk.StringVar(value="No video selected")
        self.status_var = tk.StringVar(value="Select a video to begin")
        self.type_var = tk.StringVar(value="neck_flexion")
        self.start_var = tk.StringVar(value="0.000")
        self.end_var = tk.StringVar(value="0.000")

        self.threshold_vars = {
            name: tk.StringVar(value=str(value))
            for name, value in DEFAULT_THRESHOLDS.items()
        }

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Button(top, text="Browse Video", command=self.open_video).pack(
            side="left"
        )
        ttk.Button(top, text="Import Annotation CSV", command=self.import_csv).pack(
            side="left", padx=6
        )
        ttk.Button(top, text="Export Annotation CSV", command=self.export_csv).pack(
            side="left"
        )

        ttk.Label(
            self.root, textvariable=self.video_var, padding=(10, 0)
        ).pack(anchor="w")

        self.preview = tk.Label(
            self.root, text="Video preview", background="#222222",
            foreground="white", width=100, height=24,
        )
        self.preview.pack(fill="both", expand=True, padx=10, pady=8)

        seek = ttk.Frame(self.root, padding=(10, 0))
        seek.pack(fill="x")
        ttk.Button(seek, text="|<", command=self.first_frame).pack(side="left")
        ttk.Button(seek, text="Previous frame", command=self.previous_frame).pack(
            side="left", padx=3
        )
        ttk.Button(seek, text="Play / Pause", command=self.toggle_play).pack(
            side="left", padx=3
        )
        ttk.Button(seek, text="Next frame", command=self.next_frame).pack(
            side="left", padx=3
        )
        ttk.Label(seek, text="Time (sec):").pack(side="left", padx=(12, 3))
        self.time_label = ttk.Label(seek, text="0.000")
        self.time_label.pack(side="left")

        annotation_frame = ttk.LabelFrame(
            self.root, text="Human Ground Truth", padding=8
        )
        annotation_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(annotation_frame, text="Posture").grid(row=0, column=0)
        ttk.Combobox(
            annotation_frame, textvariable=self.type_var,
            values=POSTURE_TYPES, state="readonly", width=24,
        ).grid(row=0, column=1, padx=4)

        ttk.Label(annotation_frame, text="Start (s)").grid(row=0, column=2)
        ttk.Entry(
            annotation_frame, textvariable=self.start_var, width=12
        ).grid(row=0, column=3, padx=4)

        ttk.Button(
            annotation_frame, text="Set start = current time",
            command=lambda: self.start_var.set(f"{self.current_time:.3f}"),
        ).grid(row=0, column=4, padx=3)

        ttk.Label(annotation_frame, text="End (s)").grid(row=1, column=2)
        ttk.Entry(
            annotation_frame, textvariable=self.end_var, width=12
        ).grid(row=1, column=3, padx=4)

        ttk.Button(
            annotation_frame, text="Set end = current time",
            command=lambda: self.end_var.set(f"{self.current_time:.3f}"),
        ).grid(row=1, column=4, padx=3)

        ttk.Button(
            annotation_frame, text="Add annotation",
            command=self.add_annotation,
        ).grid(row=0, column=5, rowspan=2, padx=8)

        self.annotation_list = tk.Listbox(annotation_frame, height=4)
        self.annotation_list.grid(
            row=2, column=0, columnspan=5, sticky="ew", pady=6
        )
        ttk.Button(
            annotation_frame, text="Remove selected",
            command=self.remove_annotation,
        ).grid(row=2, column=5, padx=8)

        threshold_frame = ttk.LabelFrame(
            self.root, text="Evaluation thresholds (degrees)", padding=8
        )
        threshold_frame.pack(fill="x", padx=10, pady=5)

        for index, name in enumerate(POSTURE_TYPES):
            ttk.Label(threshold_frame, text=name).grid(
                row=0, column=index * 2, sticky="w"
            )
            ttk.Entry(
                threshold_frame,
                textvariable=self.threshold_vars[name],
                width=7,
            ).grid(row=0, column=index * 2 + 1, padx=(3, 12))

        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(fill="x")
        ttk.Button(
            bottom, text="Run Evaluation",
            command=self.run,
        ).pack(side="left")

        ttk.Label(
            bottom, textvariable=self.status_var
        ).pack(side="left", padx=12)

    def open_video(self):
        path = filedialog.askopenfilename(
            title="Choose video",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        self._release_capture()
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            messagebox.showerror("Video error", "Cannot open this video.")
            return

        fps = finite_number(capture.get(cv2.CAP_PROP_FPS)) or 0
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or count <= 0:
            capture.release()
            messagebox.showerror("Video error", "Invalid FPS or frame count.")
            return

        self.video_path = path
        self.capture = capture
        self.fps = fps
        self.frame_count = count
        self.duration = count / fps
        self.current_time = 0.0
        self.annotations.clear()
        self._refresh_annotations()
        self.video_var.set(
            f"{Path(path).name} | {fps:.3f} FPS | {count} frames "
            f"| {self.duration:.2f} seconds"
        )
        self.show_frame(0)

    def _read_frame(self, index):
        if self.capture is None:
            return None
        index = max(0, min(self.frame_count - 1, index))
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.capture.read()
        if not ok:
            return None
        self.current_time = index / self.fps
        self.time_label.configure(text=f"{self.current_time:.3f}")
        return frame

    def show_frame(self, index):
        frame = self._read_frame(index)
        if frame is None:
            return
        self.current_frame = frame

        # Preview shows the actual frame. Landmark overlay is created
        # during evaluation so preview seeking stays responsive.
        try:
            from PIL import Image, ImageTk
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(image)
            image.thumbnail((1000, 420))
            photo = ImageTk.PhotoImage(image)
            self.preview.configure(image=photo, text="")
            self.preview.image = photo
        except ImportError:
            self.preview.configure(
                image="", text="Install Pillow to display video preview"
            )

    def first_frame(self):
        self.show_frame(0)

    def previous_frame(self):
        index = round(self.current_time * self.fps) - 1
        self.show_frame(index)

    def next_frame(self):
        index = round(self.current_time * self.fps) + 1
        self.show_frame(index)

    def toggle_play(self):
        if self.capture is None:
            return
        self.playing = not self.playing
        if self.playing:
            self._play_tick()

    def _play_tick(self):
        if not self.playing:
            return
        index = round(self.current_time * self.fps) + 1
        if index >= self.frame_count:
            self.playing = False
            return
        self.show_frame(index)
        self.root.after(max(1, int(1000 / self.fps)), self._play_tick)

    def add_annotation(self):
        kind = self.type_var.get()
        start = finite_number(self.start_var.get())
        end = finite_number(self.end_var.get())

        if start is None or end is None or start < 0 or end < start:
            messagebox.showerror(
                "Invalid interval", "Check start and end times."
            )
            return
        if self.video_path and end > self.duration:
            messagebox.showerror(
                "Invalid interval", "End time exceeds video duration."
            )
            return

        self.annotations.append({
            "type": kind, "start": start, "end": end
        })
        self.annotations.sort(key=lambda x: (x["start"], x["type"]))
        self._refresh_annotations()

    def remove_annotation(self):
        selection = self.annotation_list.curselection()
        if not selection:
            return
        del self.annotations[selection[0]]
        self._refresh_annotations()

    def _refresh_annotations(self):
        self.annotation_list.delete(0, tk.END)
        for item in self.annotations:
            self.annotation_list.insert(
                tk.END,
                f"{item['type']}: {item['start']:.3f}s - "
                f"{item['end']:.3f}s",
            )

    def import_csv(self):
        path = filedialog.askopenfilename(
            title="Import annotations",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            loaded = load_annotations(path)
            if self.video_path:
                for item in loaded:
                    if item["end"] > self.duration:
                        raise ValueError(
                            f"Annotation ends after video duration: {item}"
                        )
            self.annotations = loaded
            self._refresh_annotations()
            self.status_var.set(f"Loaded {len(loaded)} annotations")
        except Exception as exc:
            messagebox.showerror("CSV error", str(exc))

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="Export annotations",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            save_annotations(path, self.annotations)
            self.status_var.set(f"Saved annotations: {path}")
        except Exception as exc:
            messagebox.showerror("CSV error", str(exc))

    def run(self):
        if not self.video_path:
            messagebox.showwarning("Missing video", "Choose a video first.")
            return

        try:
            thresholds = {
                name: finite_number(variable.get())
                for name, variable in self.threshold_vars.items()
            }
            if any(
                value is None or value <= 0
                for value in thresholds.values()
            ):
                raise ValueError("Thresholds must be positive finite numbers.")

            output_dir = filedialog.askdirectory(
                title="Choose output folder"
            )
            if not output_dir:
                return

            self.playing = False
            self.status_var.set("Processing video...")
            self.root.update_idletasks()

            report = run_evaluation(
                self.video_path,
                output_dir,
                self.annotations,
                thresholds,
                lambda message: self.status_var.set(message),
            )

            self.status_var.set(
                f"Finished: {report['frames']} frames | {report['output_dir']}"
            )

            metric_lines = []
            for kind, item in report["summaries"].items():
                metric_lines.append(
                    f"{kind}: Precision={item['precision']:.3f}, "
                    f"Recall={item['recall']:.3f}, "
                    f"F1={item['f1_score']:.3f}, "
                    f"TP={item['TP']} FP={item['FP']} "
                    f"FN={item['FN']} TN={item['TN']}"
                )

            messagebox.showinfo(
                "Evaluation complete",
                "Output folder:\n"
                f"{report['output_dir']}\n\n"
                + "\n".join(metric_lines),
            )

        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("Evaluation failed", str(exc))
            self.status_var.set("Evaluation failed")

    def _release_capture(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def close(self):
        self.playing = False
        self._release_capture()
        self.root.destroy()


def main():
    root = tk.Tk()
    ValidationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
