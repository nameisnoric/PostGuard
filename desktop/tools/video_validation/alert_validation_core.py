"""Ground Truth I/O, production alert replay, and alert matching metrics."""
from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Callable

import cv2

from app.services.camera_setup import mirror_camera_frame
from app.services.detection_service import DetectionService, DEFAULT_ALERT_POLICY
from app.services.wellness_alert_policy import WellnessAlertPolicy
from app.vision.alert_policy import AlertPolicy
from app.vision.mediapipe_detection.eye.blink_detector import BlinkDetector
from app.vision.mediapipe_detection.eye.blink_statistics import BlinkStatistics
from app.vision.mediapipe_detection.eye.eye_measurement import calculate_eye_openness
from app.vision.mediapipe_detection.eye.eye_state import EyeStateDetector
from app.vision.mediapipe_detection.posture.screen_distance_policy import ScreenDistancePolicy
from app.vision.risk_evaluation import evaluate_risk
from app.vision.risk_event import RiskEventTracker
from app.vision.temporal_tracking.temporal_posture_tracker import (
    TemporalPostureTracker,
)


EVENT_TYPES = ("POSTURE_RISK", "LOW_BLINK_RATE", "SCREEN_DISTANCE")
ALERT_TYPES = ("FIRST", "REPEAT", "ESCALATION", "RESOLVED")
GROUND_TRUTH_COLUMNS = ("event_type", "alert_type", "timestamp_sec", "note")


def finite_number(value, *, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def validate_marker(marker: dict, *, line: int | None = None) -> dict:
    prefix = f"line {line}: " if line is not None else ""
    event_type = str(marker.get("event_type") or "").strip().upper()
    alert_type = str(marker.get("alert_type") or "").strip().upper()
    if event_type not in EVENT_TYPES:
        raise ValueError(f"{prefix}unknown event_type {event_type!r}")
    if alert_type not in ALERT_TYPES:
        raise ValueError(f"{prefix}unknown alert_type {alert_type!r}")
    timestamp = finite_number(marker.get("timestamp_sec"), name=f"{prefix}timestamp")
    if timestamp < 0:
        raise ValueError(f"{prefix}timestamp must be >= 0")
    return {
        "event_type": event_type,
        "alert_type": alert_type,
        "timestamp_sec": timestamp,
        "note": str(marker.get("note") or "").strip(),
    }


def save_alert_ground_truth(path: str | Path, markers: list[dict]) -> None:
    normalized = [validate_marker(marker) for marker in markers]
    normalized.sort(key=lambda item: (item["timestamp_sec"], item["event_type"]))
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=GROUND_TRUTH_COLUMNS)
        writer.writeheader()
        for marker in normalized:
            writer.writerow({**marker, "timestamp_sec": f"{marker['timestamp_sec']:.6f}"})


def load_alert_ground_truth(path: str | Path) -> list[dict]:
    markers = []
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = set(GROUND_TRUTH_COLUMNS[:3])
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                "Alert Ground Truth CSV must contain "
                "event_type,alert_type,timestamp_sec"
            )
        for line, row in enumerate(reader, start=2):
            markers.append(validate_marker(row, line=line))
    return sorted(markers, key=lambda item: (item["timestamp_sec"], item["event_type"]))


def _append_unique(records, event_type, alert_type, timestamp, **extra):
    if event_type not in EVENT_TYPES or alert_type not in ALERT_TYPES:
        return
    if records and (
        records[-1]["event_type"] == event_type
        and records[-1]["alert_type"] == alert_type
        and abs(records[-1]["timestamp_sec"] - timestamp) < 1e-6
    ):
        return
    records.append({
        "event_type": event_type,
        "alert_type": alert_type,
        "timestamp_sec": float(timestamp),
        **extra,
    })


def collect_system_alerts(
    video_path: str | Path,
    *,
    baseline_eye_distance: float | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> tuple[list[dict], dict]:
    """Replay video through the production decision chain using video time."""
    video_path = Path(video_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Cannot open video")
    fps = finite_number(capture.get(cv2.CAP_PROP_FPS), name="video FPS")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or frame_count <= 0:
        capture.release()
        raise RuntimeError("Video FPS or frame count is invalid")
    if baseline_eye_distance is not None:
        baseline_eye_distance = finite_number(
            baseline_eye_distance, name="baseline_eye_distance"
        )
        if baseline_eye_distance <= 0:
            raise ValueError("baseline_eye_distance must be > 0")

    detector = DetectionService()
    temporal = TemporalPostureTracker()
    risk_tracker = RiskEventTracker()
    alert_policy = AlertPolicy(DEFAULT_ALERT_POLICY)
    eye_state_detector = EyeStateDetector()
    eye_state_detector.start_calibration(timestamp=0.0)
    blink_detector = BlinkDetector()
    blink_statistics = BlinkStatistics()
    blink_statistics.start(timestamp=0.0)
    screen_policy = ScreenDistancePolicy()
    wellness_policy = WellnessAlertPolicy()
    records = []
    frame_index = 0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = frame_index / fps
            pipeline = detector.process_frame(mirror_camera_frame(frame))

            assessment = pipeline.get("assessment") or {}
            temporal_result = temporal.update(assessment, now=timestamp)
            risk = evaluate_risk(assessment, temporal_result)
            risk_event = risk_tracker.update(risk, now=timestamp)
            posture_alert = alert_policy.update(risk_event, now=timestamp)
            if posture_alert.get("should_notify") is True:
                _append_unique(
                    records, "POSTURE_RISK",
                    str(posture_alert.get("alert_type") or "").upper(), timestamp,
                    risk_level=risk_event.get("current_risk_level"),
                )
            if risk_event.get("event_action") == "RESOLVED":
                _append_unique(records, "POSTURE_RISK", "RESOLVED", timestamp)

            face_points = pipeline.get("face_points") or {}
            eye_measurement = calculate_eye_openness(face_points)
            eye_state = eye_state_detector.update(eye_measurement, timestamp=timestamp)
            blink = blink_detector.update(
                eye_state, eye_measurement=eye_measurement, timestamp=timestamp
            )
            observation_valid = (
                eye_measurement is not None
                and eye_state.get("calibrated") is True
                and eye_state.get("eye_state") in {"OPEN", "CLOSED"}
            )
            blink_stats = blink_statistics.update(
                blink_event=blink.get("blink_event") is True,
                timestamp=timestamp,
                observation_valid=observation_valid,
            )
            screen_result = None
            if baseline_eye_distance is not None:
                screen_result = screen_policy.update(
                    pipeline.get("eye_distance"), baseline_eye_distance, now=timestamp
                )
            wellness = wellness_policy.update(screen_result, blink_stats, now=timestamp)
            for notification in wellness.get("notifications", []):
                if isinstance(notification, dict):
                    _append_unique(
                        records,
                        str(notification.get("event_type") or "").upper(),
                        str(notification.get("alert_type") or "").upper(),
                        timestamp,
                        value=notification.get("value"),
                    )
            for event in wellness.get("events", []):
                if isinstance(event, dict) and event.get("action") == "RESOLVED":
                    _append_unique(
                        records, str(event.get("event_type") or "").upper(),
                        "RESOLVED", timestamp,
                    )

            frame_index += 1
            if status_callback and frame_index % max(1, int(fps)) == 0:
                status_callback(
                    f"Processing {frame_index:,}/{frame_count:,} "
                    f"({frame_index / frame_count * 100:.1f}%)"
                )
    finally:
        capture.release()
        detector.close()

    return records, {
        "video": str(video_path),
        "fps": fps,
        "frames": frame_index,
        "duration_seconds": frame_index / fps,
        "baseline_eye_distance": baseline_eye_distance,
        "pipeline": [
            "horizontal_mirror", "DetectionService", "TemporalPostureTracker",
            "RULA-adapted Risk Evaluation", "RiskEventTracker", "AlertPolicy",
            "BlinkStatistics", "WellnessAlertPolicy",
        ],
    }


def match_alerts(expected, actual, *, tolerance_seconds):
    tolerance = finite_number(tolerance_seconds, name="tolerance_seconds")
    if tolerance < 0:
        raise ValueError("tolerance_seconds must be >= 0")
    candidates = []
    for expected_index, expected_item in enumerate(expected):
        for actual_index, actual_item in enumerate(actual):
            if (
                expected_item["event_type"] == actual_item["event_type"]
                and expected_item["alert_type"] == actual_item["alert_type"]
            ):
                latency = actual_item["timestamp_sec"] - expected_item["timestamp_sec"]
                if abs(latency) <= tolerance:
                    candidates.append((abs(latency), expected_index, actual_index, latency))
    candidates.sort()
    used_expected, used_actual, details = set(), set(), []
    for _, expected_index, actual_index, latency in candidates:
        if expected_index in used_expected or actual_index in used_actual:
            continue
        used_expected.add(expected_index)
        used_actual.add(actual_index)
        details.append({
            "status": "MATCHED",
            "event_type": expected[expected_index]["event_type"],
            "alert_type": expected[expected_index]["alert_type"],
            "expected_at": expected[expected_index]["timestamp_sec"],
            "actual_at": actual[actual_index]["timestamp_sec"],
            "latency_seconds": latency,
        })
    for index, item in enumerate(expected):
        if index not in used_expected:
            details.append({
                "status": "MISSED", "event_type": item["event_type"],
                "alert_type": item["alert_type"],
                "expected_at": item["timestamp_sec"], "actual_at": None,
                "latency_seconds": None,
            })
    for index, item in enumerate(actual):
        if index not in used_actual:
            details.append({
                "status": "SYSTEM_ONLY", "event_type": item["event_type"],
                "alert_type": item["alert_type"], "expected_at": None,
                "actual_at": item["timestamp_sec"], "latency_seconds": None,
            })
    details.sort(key=lambda item: (
        item["expected_at"] if item["expected_at"] is not None else item["actual_at"],
        item["event_type"], item["alert_type"],
    ))
    return details


def _metric(details, duration_seconds):
    matched = sum(item["status"] == "MATCHED" for item in details)
    missed = sum(item["status"] == "MISSED" for item in details)
    system_only = sum(item["status"] == "SYSTEM_ONLY" for item in details)
    if not details:
        precision = recall = f1 = None
    else:
        precision = matched / (matched + system_only) if matched + system_only else 0.0
        recall = matched / (matched + missed) if matched + missed else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    latencies = [item["latency_seconds"] for item in details if item["latency_seconds"] is not None]
    return {
        "matched": matched, "missed": missed, "system_only": system_only,
        "precision": precision, "recall": recall, "f1_score": f1,
        "mean_latency_seconds": statistics.mean(latencies) if latencies else None,
        "false_alerts_per_hour": (
            system_only * 3600.0 / duration_seconds if duration_seconds > 0 else 0.0
        ),
    }


def calculate_summary(details, duration_seconds):
    summary = _metric(details, duration_seconds)
    summary["by_event_type"] = {
        event_type: _metric(
            [item for item in details if item["event_type"] == event_type], duration_seconds
        ) for event_type in EVENT_TYPES
    }
    summary["by_alert_type"] = {
        alert_type: _metric(
            [item for item in details if item["alert_type"] == alert_type], duration_seconds
        ) for alert_type in ALERT_TYPES
    }
    return summary


def export_validation_report(
    output_dir, ground_truth, system_alerts, metadata, *, tolerance_seconds
):
    details = match_alerts(
        ground_truth, system_alerts, tolerance_seconds=tolerance_seconds
    )
    summary = calculate_summary(details, metadata.get("duration_seconds", 0.0))
    report = {
        "validation_version": "2.0-manual-alert-ground-truth",
        "metadata": metadata,
        "tolerance_seconds": float(tolerance_seconds),
        "ground_truth": ground_truth,
        "system_alerts": system_alerts,
        "summary": summary,
        "details": details,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = Path(metadata.get("video") or "video").stem
    report_path = output / f"{stem}_alert_validation_report.json"
    details_path = output / f"{stem}_alert_validation_details.csv"
    system_path = output / f"{stem}_system_alerts.csv"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(details_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "status", "event_type", "alert_type", "expected_at",
            "actual_at", "latency_seconds",
        ))
        writer.writeheader()
        writer.writerows(details)
    with open(system_path, "w", newline="", encoding="utf-8-sig") as handle:
        columns = ("event_type", "alert_type", "timestamp_sec", "risk_level", "value")
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(system_alerts)
    return {
        **report,
        "report_path": str(report_path),
        "details_path": str(details_path),
        "system_alerts_path": str(system_path),
    }
