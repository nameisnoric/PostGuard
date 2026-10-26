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
# PATHS
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

# Current file:
# C:\project\PostGuard\desktop\tools\video_validation\
#     postguard_validation_studio_v2.py
#
# Therefore:
# SCRIPT_DIR.parents[1]
# = C:\project\PostGuard\desktop

DESKTOP_DIR = SCRIPT_DIR.parents[1]

PROJECT_ROOT = DESKTOP_DIR.parent

BACKEND_DIR = PROJECT_ROOT / "backend"


# ============================================================
# IMPORTANT:
#
# Python automatically adds the script folder to sys.path.
#
# In this project the folder:
#
# desktop\tools\video_validation
#
# contains app.py.
#
# That file can shadow the real package:
#
# desktop\app
#
# Remove the validation folder from import search path so
# `import app...` always resolves to desktop/app.
# ============================================================

script_dir_string = str(SCRIPT_DIR)

while script_dir_string in sys.path:
    sys.path.remove(script_dir_string)


# Add real PostGuard packages first.
for path in (
    DESKTOP_DIR,
    BACKEND_DIR,
):
    value = str(path)

    while value in sys.path:
        sys.path.remove(value)

    sys.path.insert(
        0,
        value,
    )

# ============================================================
# REAL POSTGUARD MODULES
# ============================================================
from app.services.detection_service import DetectionService
from app.vision.mediapipe_detection.eye.eye_measurement import calculate_eye_openness
from app.vision.mediapipe_detection.eye.eye_state import (
    EyeStateDetector,
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
)
from camera_card.posture_assessment.current_posture_assessment import (
    assess_current_posture,
    get_default_assessment_rules,
)

APP_TITLE = "PostGuard Validation Studio v2"

POSTURE_LABELS = (
    "NEUTRAL",
    "LEFT_SHOULDER_HIGH",
    "RIGHT_SHOULDER_HIGH",
    "TILT_LEFT",
    "TILT_RIGHT",
    "FLEXION",
    "EXTENSION",
)
SPECIAL_LABELS = ("IGNORE", "BLINK")
ALL_ANNOTATION_TYPES = POSTURE_LABELS + SPECIAL_LABELS

DEFAULT_BLINK_MATCH_TOLERANCE_SECONDS = 0.25
DEFAULT_MAX_BLINK_CLOSED_SECONDS = 1.0


def finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_divide(a, b):
    return a / b if b else 0.0


def load_annotations(path):
    annotations = []
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"type", "start", "end"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Annotation CSV must contain: type,start,end")

        for line_number, row in enumerate(reader, start=2):
            kind = (row.get("type") or "").strip().upper()
            start = finite_number(row.get("start"))
            end = finite_number(row.get("end"))

            if kind not in ALL_ANNOTATION_TYPES:
                raise ValueError(
                    f"CSV line {line_number}: unsupported type {kind!r}. "
                    f"Supported: {', '.join(ALL_ANNOTATION_TYPES)}"
                )
            if start is None or end is None or start < 0 or end < start:
                raise ValueError(f"CSV line {line_number}: invalid start/end")
            if kind == "BLINK":
                end = start

            annotations.append({"type": kind, "start": start, "end": end})

    return sorted(annotations, key=lambda x: (x["start"], x["type"]))


def save_annotations(path, annotations):
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["type", "start", "end"])
        writer.writeheader()
        for item in annotations:
            writer.writerow({
                "type": item["type"],
                "start": f"{item['start']:.3f}",
                "end": f"{item['end']:.3f}",
            })


def interval_active(annotations, kind, timestamp):
    return any(
        item["type"] == kind and item["start"] <= timestamp <= item["end"]
        for item in annotations
    )


def ignored_at(annotations, timestamp):
    return interval_active(annotations, "IGNORE", timestamp)


def human_blink_times(annotations):
    return [a["start"] for a in annotations if a["type"] == "BLINK"]


# ============================================================
# PRODUCTION POSTURE ADAPTER
# No duplicated posture thresholds here.
# ============================================================
def assessment_labels(assessment):
    if not isinstance(assessment, dict):
        return set()

    features = assessment.get("features") or {}
    labels = set()

    shoulder = (features.get("shoulder_tilt") or {}).get("status")
    lateral = (features.get("neck_lateral_tilt") or {}).get("status")
    sagittal = (features.get("neck_flexion") or {}).get("status")

    if shoulder == "LEFT_SHOULDER_HIGH":
        labels.add("LEFT_SHOULDER_HIGH")
    elif shoulder == "RIGHT_SHOULDER_HIGH":
        labels.add("RIGHT_SHOULDER_HIGH")

    if lateral == "TILT_LEFT":
        labels.add("TILT_LEFT")
    elif lateral == "TILT_RIGHT":
        labels.add("TILT_RIGHT")

    if sagittal == "FLEXION":
        labels.add("FLEXION")
    elif sagittal == "EXTENSION":
        labels.add("EXTENSION")

    if assessment.get("status") == "COMPLETE" and not labels:
        labels.add("NEUTRAL")

    return labels


def label_is_evaluable(assessment, label):
    if not isinstance(assessment, dict):
        return False

    if label == "NEUTRAL":
        return assessment.get("status") == "COMPLETE"

    source = {
        "LEFT_SHOULDER_HIGH": "shoulder_tilt",
        "RIGHT_SHOULDER_HIGH": "shoulder_tilt",
        "TILT_LEFT": "neck_lateral_tilt",
        "TILT_RIGHT": "neck_lateral_tilt",
        "FLEXION": "neck_flexion",
        "EXTENSION": "neck_flexion",
    }[label]

    feature = ((assessment.get("features") or {}).get(source) or {})
    return bool(feature.get("evaluated", False))


def assessment_values(assessment):
    features = (assessment or {}).get("features") or {}

    def value(name):
        return finite_number((features.get(name) or {}).get("current"))

    return {
        "shoulder_tilt_deg": value("shoulder_tilt"),
        "neck_lateral_tilt_deg": value("neck_lateral_tilt"),
        "neck_flexion_deg": value("neck_flexion"),
    }


# ============================================================
# BLINK EVENT ADAPTER
# OPEN/CLOSED/UNKNOWN is from PostGuard EyeStateDetector.
# This class only turns CLOSED -> OPEN into validation events.
# ============================================================
class BlinkEventTracker:
    def __init__(self, max_closed_seconds=DEFAULT_MAX_BLINK_CLOSED_SECONDS):
        self.max_closed_seconds = float(max_closed_seconds)
        self.previous_state = EYE_UNKNOWN
        self.closed_started_at = None
        self.events = []

    def update(self, state, timestamp):
        event = None

        if state == EYE_CLOSED and self.previous_state != EYE_CLOSED:
            self.closed_started_at = timestamp

        if (
            state == EYE_OPEN
            and self.previous_state == EYE_CLOSED
            and self.closed_started_at is not None
        ):
            duration = max(0.0, timestamp - self.closed_started_at)
            if duration <= self.max_closed_seconds:
                event = {
                    "timestamp_sec": float(timestamp),
                    "closed_started_sec": float(self.closed_started_at),
                    "closed_duration_sec": float(duration),
                }
                self.events.append(event)
            self.closed_started_at = None

        if state == EYE_UNKNOWN:
            self.closed_started_at = None

        self.previous_state = state
        return event


def match_blink_events(human_times, system_events, tolerance_seconds):
    system_times = [e["timestamp_sec"] for e in system_events]
    available = set(range(len(system_times)))
    matches = []
    missed = []

    for human_time in sorted(human_times):
        candidates = [
            i for i in available
            if abs(system_times[i] - human_time) <= tolerance_seconds
        ]
        if not candidates:
            missed.append(human_time)
            continue

        best = min(candidates, key=lambda i: abs(system_times[i] - human_time))
        available.remove(best)
        matches.append({
            "human_time_sec": human_time,
            "system_time_sec": system_times[best],
            "absolute_error_sec": abs(system_times[best] - human_time),
        })

    false_events = [system_times[i] for i in sorted(available)]
    precision = safe_divide(len(matches), len(matches) + len(false_events))
    recall = safe_divide(len(matches), len(matches) + len(missed))
    f1 = safe_divide(2 * precision * recall, precision + recall)

    return {
        "human_event_count": len(human_times),
        "system_event_count": len(system_events),
        "matched": len(matches),
        "missed": len(missed),
        "false_events": len(false_events),
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "tolerance_seconds": tolerance_seconds,
        "matches": matches,
        "missed_human_times_sec": missed,
        "false_system_times_sec": false_events,
    }


# ============================================================
# METRICS
# ============================================================
def calculate_posture_metrics(rows, annotations):
    summaries = {}

    for label in POSTURE_LABELS:
        tp = fp = fn = tn = unevaluable = ignored = 0

        for row in rows:
            timestamp = row["timestamp_sec"]

            if ignored_at(annotations, timestamp):
                ignored += 1
                continue

            human_positive = interval_active(annotations, label, timestamp)
            system_positive = label in row["system_labels"]
            evaluable = row["label_evaluable"].get(label, False)

            if not evaluable:
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
        coverage = safe_divide(
            tp + fp + fn + tn,
            tp + fp + fn + tn + unevaluable,
        )

        summaries[label] = {
            "type": label,
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "TN": tn,
            "ignored_frames": ignored,
            "unevaluable_frames": unevaluable,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "accuracy": accuracy,
            "coverage": coverage,
        }

    return summaries


# ============================================================
# EXPORT
# ============================================================
def export_frame_csv(path, rows):
    columns = [
        "video_id", "frame_index", "timestamp_sec",
        "pose_detected", "face_detected", "context_valid",
        "assessment_status",
        "shoulder_tilt_deg", "neck_lateral_tilt_deg", "neck_flexion_deg",
        "system_labels",
        "eye_calibrated", "right_eye_openness", "left_eye_openness",
        "eye_state", "blink_event",
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            item = {key: row.get(key, "") for key in columns}
            item["system_labels"] = "|".join(row["system_labels"])
            writer.writerow(item)


def export_posture_summary_csv(path, summaries):
    columns = [
        "type", "TP", "FP", "FN", "TN",
        "ignored_frames", "unevaluable_frames",
        "precision", "recall", "f1_score", "accuracy", "coverage",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for label in POSTURE_LABELS:
            item = summaries[label].copy()
            for metric in ("precision", "recall", "f1_score", "accuracy", "coverage"):
                item[metric] = f"{item[metric]:.6f}"
            writer.writerow({key: item.get(key, "") for key in columns})


def export_blink_csv(path, system_events, human_times, blink_metrics):
    columns = [
        "source", "timestamp_sec", "matched",
        "matched_other_time_sec", "absolute_error_sec",
    ]
    matched_h = {m["human_time_sec"]: m for m in blink_metrics["matches"]}
    matched_s = {m["system_time_sec"]: m for m in blink_metrics["matches"]}

    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()

        for timestamp in human_times:
            match = matched_h.get(timestamp)
            writer.writerow({
                "source": "HUMAN",
                "timestamp_sec": f"{timestamp:.6f}",
                "matched": bool(match),
                "matched_other_time_sec": f"{match['system_time_sec']:.6f}" if match else "",
                "absolute_error_sec": f"{match['absolute_error_sec']:.6f}" if match else "",
            })

        for event in system_events:
            timestamp = event["timestamp_sec"]
            match = matched_s.get(timestamp)
            writer.writerow({
                "source": "SYSTEM",
                "timestamp_sec": f"{timestamp:.6f}",
                "matched": bool(match),
                "matched_other_time_sec": f"{match['human_time_sec']:.6f}" if match else "",
                "absolute_error_sec": f"{match['absolute_error_sec']:.6f}" if match else "",
            })


def export_timeline(path, rows, annotations, system_blinks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    count = len(POSTURE_LABELS) + 2
    fig, axes = plt.subplots(
        count, 1,
        figsize=(15, 2 + count * 1.15),
        sharex=True,
        gridspec_kw={"height_ratios": [2] + [1] * len(POSTURE_LABELS) + [1]},
    )

    times = [r["timestamp_sec"] for r in rows]
    axes[0].plot(times, [r["shoulder_tilt_deg"] for r in rows], label="Shoulder tilt")
    axes[0].plot(times, [r["neck_lateral_tilt_deg"] for r in rows], label="Neck lateral")
    axes[0].plot(times, [r["neck_flexion_deg"] for r in rows], label="Neck flexion")
    axes[0].set_ylabel("Angle (deg)")
    axes[0].legend(loc="upper right")
    axes[0].grid(True, alpha=0.3)

    for idx, label in enumerate(POSTURE_LABELS, start=1):
        axis = axes[idx]
        axis.set_yticks([0, 1])
        axis.set_yticklabels(["System", "Human"])
        axis.set_ylabel(label, fontsize=8)
        axis.grid(True, axis="x", alpha=0.25)

        for ann in annotations:
            if ann["type"] == label:
                axis.barh(1, max(0.001, ann["end"] - ann["start"]), left=ann["start"], height=0.35)

        active_start = None
        previous = None
        for row in rows:
            active = label in row["system_labels"]
            t = row["timestamp_sec"]
            if active and active_start is None:
                active_start = t
            if not active and active_start is not None:
                axis.barh(0, max(0.001, previous - active_start), left=active_start, height=0.35)
                active_start = None
            previous = t
        if active_start is not None and previous is not None:
            axis.barh(0, max(0.001, previous - active_start), left=active_start, height=0.35)

    blink_axis = axes[-1]
    blink_axis.set_yticks([0, 1])
    blink_axis.set_yticklabels(["System", "Human"])
    blink_axis.set_ylabel("BLINK", fontsize=8)
    for t in human_blink_times(annotations):
        blink_axis.vlines(t, 0.75, 1.25)
    for event in system_blinks:
        blink_axis.vlines(event["timestamp_sec"], -0.25, 0.25)

    for ann in annotations:
        if ann["type"] == "IGNORE":
            for axis in axes:
                axis.axvspan(ann["start"], ann["end"], alpha=0.08)

    axes[-1].set_xlabel("Video time (seconds)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


# ============================================================
# OVERLAY
# ============================================================
def draw_landmarks(frame, result):
    image = frame.copy()
    pose = result.get("pose_points") or {}
    face = result.get("face_points") or {}

    for a_name, b_name in [
        ("left_ear", "left_shoulder"),
        ("right_ear", "right_shoulder"),
        ("left_shoulder", "right_shoulder"),
    ]:
        a, b = pose.get(a_name), pose.get(b_name)
        if not a or not b:
            continue
        try:
            cv2.line(image, (int(a["x"]), int(a["y"])), (int(b["x"]), int(b["y"])), (0, 220, 255), 2)
        except (KeyError, TypeError, ValueError):
            pass

    for point in pose.values():
        try:
            cv2.circle(image, (int(point["x"]), int(point["y"])), 4, (0, 220, 255), -1)
        except (KeyError, TypeError, ValueError):
            pass

    for point in face.values():
        try:
            cv2.circle(image, (int(point["x"]), int(point["y"])), 2, (255, 160, 0), -1)
        except (KeyError, TypeError, ValueError):
            pass

    return image


def overlay_text(frame, timestamp, assessment, labels, eye_state, blink_count):
    image = frame.copy()
    values = assessment_values(assessment)
    lines = [
        f"Time: {timestamp:.3f}s",
        f"Assessment: {assessment.get('status', 'UNKNOWN')}",
        "Posture: " + (", ".join(sorted(labels)) if labels else "N/A"),
        f"Shoulder: {values['shoulder_tilt_deg']}",
        f"Neck lateral: {values['neck_lateral_tilt_deg']}",
        f"Neck flexion: {values['neck_flexion_deg']}",
        f"Eye: {eye_state} | Blink events: {blink_count}",
    ]
    y = 26
    for line in lines:
        cv2.putText(image, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(image, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 1, cv2.LINE_AA)
        y += 24
    return image


# ============================================================
# EVALUATION
# ============================================================
def run_evaluation(video_path, output_dir, annotations, status_callback, blink_tolerance_seconds):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = finite_number(cap.get(cv2.CAP_PROP_FPS)) or 0.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or frame_count <= 0:
        cap.release()
        raise RuntimeError("Invalid FPS/frame count")

    video_id = Path(video_path).stem
    output_video = output_dir / f"{video_id}_validated_overlay_v2.mp4"
    writer = cv2.VideoWriter(str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Cannot create output video")

    detector = DetectionService()
    eye_detector = EyeStateDetector()
    eye_detector.start_calibration(timestamp=0.0)
    blink_tracker = BlinkEventTracker()
    rows = []

    try:
        frame_index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            timestamp = frame_index / fps
            detection = detector.process_frame(frame)
            assessment = assess_current_posture(detection)
            labels = assessment_labels(assessment)
            values = assessment_values(assessment)

            face_points = detection.get("face_points") or {}
            eye_measurement = calculate_eye_openness(face_points)
            eye_result = eye_detector.update(eye_measurement, timestamp=timestamp)
            eye_state = eye_result.get("eye_state", EYE_UNKNOWN)
            blink_event = blink_tracker.update(eye_state, timestamp)

            right_open = finite_number(eye_measurement.get("right_eye_openness")) if isinstance(eye_measurement, dict) else None
            left_open = finite_number(eye_measurement.get("left_eye_openness")) if isinstance(eye_measurement, dict) else None
            context = detection.get("context") or {}

            rows.append({
                "video_id": video_id,
                "frame_index": frame_index,
                "timestamp_sec": timestamp,
                "pose_detected": bool(detection.get("pose_detected")),
                "face_detected": bool(detection.get("face_detected")),
                "context_valid": bool(context.get("allow_posture_evaluation", False)),
                "assessment_status": assessment.get("status"),
                "shoulder_tilt_deg": values["shoulder_tilt_deg"],
                "neck_lateral_tilt_deg": values["neck_lateral_tilt_deg"],
                "neck_flexion_deg": values["neck_flexion_deg"],
                "system_labels": sorted(labels),
                "label_evaluable": {label: label_is_evaluable(assessment, label) for label in POSTURE_LABELS},
                "eye_calibrated": bool(eye_result.get("calibrated")),
                "right_eye_openness": right_open,
                "left_eye_openness": left_open,
                "eye_state": eye_state,
                "blink_event": blink_event is not None,
            })

            image = draw_landmarks(frame, detection)
            image = overlay_text(image, timestamp, assessment, labels, eye_state, len(blink_tracker.events))
            writer.write(image)

            frame_index += 1
            if frame_index % max(1, int(fps)) == 0:
                status_callback(f"Processing {frame_index}/{frame_count} ({100 * frame_index / frame_count:.1f}%)")

    finally:
        cap.release()
        writer.release()
        detector.close()

    posture_metrics = calculate_posture_metrics(rows, annotations)
    human_blinks = human_blink_times(annotations)
    blink_metrics = match_blink_events(human_blinks, blink_tracker.events, blink_tolerance_seconds)

    export_frame_csv(output_dir / f"{video_id}_frame_results_v2.csv", rows)
    export_posture_summary_csv(output_dir / f"{video_id}_posture_metrics_v2.csv", posture_metrics)
    export_blink_csv(output_dir / f"{video_id}_blink_events_v2.csv", blink_tracker.events, human_blinks, blink_metrics)
    export_timeline(output_dir / f"{video_id}_timeline_v2.png", rows, annotations, blink_tracker.events)
    save_annotations(output_dir / f"{video_id}_ground_truth_v2.csv", annotations)

    report = {
        "validation_version": "2.0",
        "video": str(video_path),
        "fps": fps,
        "frames_processed": len(rows),
        "production_sources": {
            "detection": "app.services.detection_service.DetectionService",
            "posture_assessment": "camera_card.posture_assessment.current_posture_assessment.assess_current_posture",
            "eye_measurement": "app.vision.mediapipe_detection.eye.eye_measurement.calculate_eye_openness",
            "eye_state": "app.vision.mediapipe_detection.eye.eye_state.EyeStateDetector",
        },
        "assessment_rules": get_default_assessment_rules(),
        "posture_metrics": posture_metrics,
        "blink_metrics": blink_metrics,
        "blink_note": (
            "OPEN/CLOSED/UNKNOWN comes from PostGuard EyeStateDetector. "
            "Blink event counting is derived in this validation tool from CLOSED->OPEN transitions "
            "because the current GitHub DetectionService does not expose a production BlinkCounter."
        ),
    }

    report_path = output_dir / f"{video_id}_validation_report_v2.json"
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    return {
        "frames": len(rows),
        "output_dir": str(output_dir),
        "posture_metrics": posture_metrics,
        "blink_metrics": blink_metrics,
        "report_json": str(report_path),
    }


# ============================================================
# GUI
# ============================================================
class ValidationApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1250x900")

        self.video_path = None
        self.capture = None
        self.current_time = 0.0
        self.duration = 0.0
        self.fps = 0.0
        self.frame_count = 0
        self.annotations = []
        self.playing = False
        self.play_speed = 1.0

        self.video_var = tk.StringVar(value="No video selected")
        self.status_var = tk.StringVar(value="Select a video to begin")
        self.start_var = tk.StringVar(value="0.000")
        self.end_var = tk.StringVar(value="0.000")
        self.blink_tolerance_var = tk.StringVar(value=str(DEFAULT_BLINK_MATCH_TOLERANCE_SECONDS))
        self.label_vars = {label: tk.BooleanVar(value=False) for label in POSTURE_LABELS}
        self.ignore_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Button(top, text="Browse Video", command=self.open_video).pack(side="left")
        ttk.Button(top, text="Import Ground Truth CSV", command=self.import_csv).pack(side="left", padx=6)
        ttk.Button(top, text="Export Ground Truth CSV", command=self.export_csv).pack(side="left")
        ttk.Label(self.root, textvariable=self.video_var, padding=(10, 0)).pack(anchor="w")

        self.preview = tk.Label(self.root, text="Video preview", background="#222", foreground="white", width=100, height=24)
        self.preview.pack(fill="both", expand=True, padx=10, pady=8)

        seek = ttk.Frame(self.root, padding=(10, 0))
        seek.pack(fill="x")
        ttk.Button(seek, text="|<", command=lambda: self.show_frame(0)).pack(side="left")
        ttk.Button(seek, text="Previous frame", command=self.previous_frame).pack(side="left", padx=3)
        ttk.Button(seek, text="Play / Pause", command=self.toggle_play).pack(side="left", padx=3)
        ttk.Button(seek, text="Next frame", command=self.next_frame).pack(side="left", padx=3)
        ttk.Label(seek, text="Speed:").pack(side="left", padx=(12, 3))
        self.speed_combo = ttk.Combobox(seek, values=("0.25x", "0.5x", "1.0x", "2.0x"), state="readonly", width=7)
        self.speed_combo.set("1.0x")
        self.speed_combo.pack(side="left")
        self.speed_combo.bind("<<ComboboxSelected>>", self.speed_changed)
        ttk.Label(seek, text="Time:").pack(side="left", padx=(12, 3))
        self.time_label = ttk.Label(seek, text="0.000 s")
        self.time_label.pack(side="left")

        gt = ttk.LabelFrame(self.root, text="Human Ground Truth (do this before viewing PostGuard results)", padding=8)
        gt.pack(fill="x", padx=10, pady=5)

        for index, label in enumerate(POSTURE_LABELS):
            ttk.Checkbutton(gt, text=label, variable=self.label_vars[label]).grid(row=index // 4, column=index % 4, sticky="w", padx=4, pady=2)

        ttk.Checkbutton(gt, text="IGNORE / TRANSITION", variable=self.ignore_var).grid(row=2, column=0, columnspan=2, sticky="w")

        ttk.Label(gt, text="Start (sec)").grid(row=3, column=0, sticky="e")
        ttk.Entry(gt, textvariable=self.start_var, width=12).grid(row=3, column=1)
        ttk.Button(gt, text="Set Start = current", command=lambda: self.start_var.set(f"{self.current_time:.3f}")).grid(row=3, column=2)
        ttk.Label(gt, text="End (sec)").grid(row=3, column=3, sticky="e")
        ttk.Entry(gt, textvariable=self.end_var, width=12).grid(row=3, column=4)
        ttk.Button(gt, text="Set End = current", command=lambda: self.end_var.set(f"{self.current_time:.3f}")).grid(row=3, column=5)

        ttk.Button(gt, text="Add Posture Segment", command=self.add_posture_segment).grid(row=4, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Button(gt, text="BLINK NOW", command=self.add_blink).grid(row=4, column=2, sticky="ew", padx=5)
        ttk.Label(gt, text="Blink tolerance (sec)").grid(row=4, column=3, sticky="e")
        ttk.Entry(gt, textvariable=self.blink_tolerance_var, width=8).grid(row=4, column=4)

        self.annotation_list = tk.Listbox(gt, height=7)
        self.annotation_list.grid(row=5, column=0, columnspan=5, sticky="ew", pady=6)
        ttk.Button(gt, text="Remove selected", command=self.remove_annotation).grid(row=5, column=5, padx=8)

        rules = get_default_assessment_rules()
        f = rules["features"]
        rules_text = (
            f"Rules {rules.get('version')} | "
            f"Shoulder LEFT < {f['shoulder_tilt']['left_high_threshold_deg']}°, RIGHT > {f['shoulder_tilt']['right_high_threshold_deg']}° | "
            f"Neck LEFT > {f['neck_lateral_tilt']['left_tilt_threshold_deg']}°, RIGHT < {f['neck_lateral_tilt']['right_tilt_threshold_deg']}° | "
            f"Flexion > {f['neck_flexion']['flexion_threshold_deg']}°, Extension < {f['neck_flexion']['extension_threshold_deg']}°"
        )
        rf = ttk.LabelFrame(self.root, text="Production Assessment Rules (read-only)", padding=8)
        rf.pack(fill="x", padx=10, pady=5)
        ttk.Label(rf, text=rules_text, wraplength=1180).pack(anchor="w")
        ttk.Label(rf, text="Eye = calculate_eye_openness + EyeStateDetector; blink event = CLOSED→OPEN validation adapter", wraplength=1180).pack(anchor="w")

        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Run Production Validation", command=self.run).pack(side="left")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left", padx=12)

    def open_video(self):
        path = filedialog.askopenfilename(title="Choose video", filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")])
        if not path:
            return
        self._release_capture()
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            messagebox.showerror("Video error", "Cannot open video")
            return
        fps = finite_number(capture.get(cv2.CAP_PROP_FPS)) or 0.0
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or count <= 0:
            capture.release()
            messagebox.showerror("Video error", "Invalid FPS/frame count")
            return
        self.video_path = path
        self.capture = capture
        self.fps = fps
        self.frame_count = count
        self.duration = count / fps
        self.current_time = 0.0
        self.annotations.clear()
        self.refresh_annotations()
        self.video_var.set(f"{Path(path).name} | {fps:.3f} FPS | {count} frames | {self.duration:.2f} sec")
        self.show_frame(0)

    def show_frame(self, index):
        if self.capture is None:
            return
        index = max(0, min(self.frame_count - 1, index))
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.capture.read()
        if not ok:
            return
        self.current_time = index / self.fps
        self.time_label.configure(text=f"{self.current_time:.3f} s")
        try:
            from PIL import Image, ImageTk
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            image.thumbnail((1180, 430))
            photo = ImageTk.PhotoImage(image)
            self.preview.configure(image=photo, text="")
            self.preview.image = photo
        except ImportError:
            self.preview.configure(image="", text="Install Pillow to display video preview")

    def previous_frame(self):
        self.show_frame(round(self.current_time * self.fps) - 1)

    def next_frame(self):
        self.show_frame(round(self.current_time * self.fps) + 1)

    def toggle_play(self):
        if self.capture is None:
            return
        self.playing = not self.playing
        if self.playing:
            self.play_tick()

    def speed_changed(self, _event=None):
        speed = finite_number(self.speed_combo.get().replace("x", ""))
        if speed and speed > 0:
            self.play_speed = speed

    def play_tick(self):
        if not self.playing:
            return
        index = round(self.current_time * self.fps) + 1
        if index >= self.frame_count:
            self.playing = False
            return
        self.show_frame(index)
        self.root.after(max(1, int(1000 / (self.fps * self.play_speed))), self.play_tick)

    def add_posture_segment(self):
        start = finite_number(self.start_var.get())
        end = finite_number(self.end_var.get())
        if start is None or end is None or start < 0 or end < start:
            messagebox.showerror("Invalid interval", "Check start/end")
            return
        if self.video_path and end > self.duration:
            messagebox.showerror("Invalid interval", "End exceeds video duration")
            return

        if self.ignore_var.get():
            selected = ["IGNORE"]
        else:
            selected = [label for label, var in self.label_vars.items() if var.get()]

        if not selected:
            messagebox.showwarning("No label", "Select posture or IGNORE")
            return
        if "NEUTRAL" in selected and len(selected) > 1:
            messagebox.showerror("Invalid labels", "NEUTRAL cannot coexist with another posture label")
            return

        for kind in selected:
            self.annotations.append({"type": kind, "start": start, "end": end})
        self.annotations.sort(key=lambda x: (x["start"], x["type"]))
        self.refresh_annotations()

    def add_blink(self):
        if not self.video_path:
            return
        self.annotations.append({"type": "BLINK", "start": self.current_time, "end": self.current_time})
        self.annotations.sort(key=lambda x: (x["start"], x["type"]))
        self.refresh_annotations()

    def remove_annotation(self):
        selection = self.annotation_list.curselection()
        if selection:
            del self.annotations[selection[0]]
            self.refresh_annotations()

    def refresh_annotations(self):
        self.annotation_list.delete(0, tk.END)
        for item in self.annotations:
            if item["type"] == "BLINK":
                text = f"BLINK @ {item['start']:.3f}s"
            else:
                text = f"{item['type']}: {item['start']:.3f}s - {item['end']:.3f}s"
            self.annotation_list.insert(tk.END, text)

    def import_csv(self):
        path = filedialog.askopenfilename(title="Import Ground Truth", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            loaded = load_annotations(path)
            if self.video_path:
                for item in loaded:
                    if item["end"] > self.duration:
                        raise ValueError(f"Annotation exceeds video: {item}")
            self.annotations = loaded
            self.refresh_annotations()
            self.status_var.set(f"Loaded {len(loaded)} annotations")
        except Exception as exc:
            messagebox.showerror("CSV error", str(exc))

    def export_csv(self):
        path = filedialog.asksaveasfilename(title="Export Ground Truth", defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            save_annotations(path, self.annotations)
            self.status_var.set(f"Saved: {path}")
        except Exception as exc:
            messagebox.showerror("CSV error", str(exc))

    def run(self):
        if not self.video_path:
            messagebox.showwarning("Missing video", "Choose video first")
            return
        tolerance = finite_number(self.blink_tolerance_var.get())
        if tolerance is None or tolerance <= 0:
            messagebox.showerror("Blink tolerance", "Enter a positive number")
            return
        output_dir = filedialog.askdirectory(title="Choose output folder")
        if not output_dir:
            return
        try:
            self.playing = False
            self.status_var.set("Running production validation...")
            self.root.update_idletasks()
            report = run_evaluation(self.video_path, output_dir, self.annotations, self.update_status, tolerance)

            lines = []
            for label in POSTURE_LABELS:
                m = report["posture_metrics"][label]
                lines.append(
                    f"{label}: P={m['precision']:.3f} R={m['recall']:.3f} "
                    f"F1={m['f1_score']:.3f} Acc={m['accuracy']:.3f} Cov={m['coverage']:.3f}"
                )
            b = report["blink_metrics"]
            lines.append(
                f"BLINK: Human={b['human_event_count']} System={b['system_event_count']} "
                f"Matched={b['matched']} Missed={b['missed']} False={b['false_events']} "
                f"P={b['precision']:.3f} R={b['recall']:.3f} F1={b['f1_score']:.3f}"
            )
            self.status_var.set(f"Finished: {report['frames']} frames")
            messagebox.showinfo("Validation complete", "\n".join(lines))
        except Exception as exc:
            traceback.print_exc()
            self.status_var.set("Validation failed")
            messagebox.showerror("Validation failed", str(exc))

    def update_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()

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
