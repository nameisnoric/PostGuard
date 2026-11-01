"""Desktop adapter for the shared camera detection and session pipeline."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from app.vision.mediapipe_detection.detection_pipeline import DetectionPipeline
from app.vision.mediapipe_detection.eye.blink_statistics import BlinkStatistics
from app.vision.alert_policy import AlertPolicy, AlertPolicyConfig
from app.vision.posture_assessment.current_posture_assessment import (
    assess_current_posture,
)
from app.vision.risk_event import RiskEventTracker
from app.vision.risk_evaluation import evaluate_risk
from app.vision.session_monitoring.measurement_change_gate import (
    evaluate_measurement_change,
    load_measurement_change_thresholds,
)
from app.vision.session_monitoring.session_monitor import (
    build_session_monitoring_snapshot,
)
from app.vision.temporal_tracking.temporal_posture_tracker import (
    TemporalPostureTracker,
)
from app.vision.mediapipe_detection.posture.screen_distance_policy import (
    ScreenDistancePolicy,
)
from app.services.wellness_alert_policy import WellnessAlertPolicy


DEFAULT_ALERT_POLICY = AlertPolicyConfig(
    moderate_first_alert_delay_seconds=0.0,
    high_first_alert_delay_seconds=0.0,
    moderate_repeat_cooldown_seconds=600.0,
    high_repeat_cooldown_seconds=300.0,
    escalation_bypasses_cooldown=True,
    notify_on_resolution=False,
)


def _feature_value(result: Mapping[str, Any], name: str) -> float | None:
    """Read a finite numeric value from Detection Contract v1."""
    feature = result.get("features", {}).get(name)
    if not isinstance(feature, Mapping) or feature.get("valid") is not True:
        return None

    value = feature.get("value")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        return None
    return float(value)


class DetectionService:
    """Run shared detection while preserving the current desktop page keys."""

    def __init__(self):
        self.pipeline = DetectionPipeline()
        self.pipeline.start_eye_calibration()

        self.pose_detector = self.pipeline.pose_detector
        self.face_detector = self.pipeline.face_detector

        self.blink_statistics = BlinkStatistics()
        self.blink_statistics.start()
        self.temporal_tracker = TemporalPostureTracker()
        self.risk_event_tracker = RiskEventTracker()
        self.alert_policy = AlertPolicy(DEFAULT_ALERT_POLICY)
        self.screen_distance_policy = ScreenDistancePolicy()
        self.wellness_alert_policy = WellnessAlertPolicy()

        threshold_path = (
            Path(__file__).resolve().parents[1]
            / "vision"
            / "session_monitoring"
            / "measurement_change_thresholds.json"
        )
        self.measurement_thresholds = load_measurement_change_thresholds(
            threshold_path
        )
        self.session_context: tuple[Mapping[str, Any], Mapping[str, Any]] | None = None

    def configure_session(
        self,
        session: Mapping[str, Any],
        baseline: Mapping[str, Any],
    ) -> None:
        """Attach a running session and baseline for per-frame comparison."""
        if not isinstance(session, Mapping) or not isinstance(baseline, Mapping):
            raise TypeError("session and baseline must be mappings")
        self.session_context = (dict(session), dict(baseline))
        self.temporal_tracker.reset()

    def reset_runtime(self) -> None:
        """Reset eye, posture-context, and temporal state for a new session."""
        self.pipeline.reset_runtime()
        self.pipeline.start_eye_calibration()
        self.blink_statistics.start()
        self.temporal_tracker.reset()
        # A resumed session must not reuse a runtime event id that was already
        # persisted before the pause.
        self.risk_event_tracker.reset(preserve_sequence=True)
        self.alert_policy.reset()
        self.screen_distance_policy.reset()
        self.wellness_alert_policy.reset()

    def process_frame(self, frame):
        if frame is None or frame.size == 0:
            raise ValueError("Invalid camera frame")

        detection = self.pipeline.process_frame(frame)
        timestamp = detection.get("timestamp")
        eye = detection.get("eye") if isinstance(detection.get("eye"), Mapping) else {}
        blink = eye.get("blink") if isinstance(eye.get("blink"), Mapping) else {}
        eye_state = eye.get("state") if isinstance(eye.get("state"), Mapping) else {}
        eye_observation_valid = (
            eye.get("measurement_valid") is True
            and eye_state.get("calibrated") is True
            and eye_state.get("eye_state") in {"OPEN", "CLOSED"}
        )
        blink_statistics = self.blink_statistics.update(
            blink_event=blink.get("blink_event") is True,
            timestamp=timestamp,
            observation_valid=eye_observation_valid,
        )

        assessment = assess_current_posture(detection)
        temporal = self.temporal_tracker.update(assessment, now=timestamp)
        risk = evaluate_risk(assessment, temporal)
        risk_event = self.risk_event_tracker.update(risk, now=timestamp)
        alert_policy = self.alert_policy.update(risk_event, now=timestamp)

        monitoring_snapshot = None
        measurement_change = None
        if self.session_context is not None:
            session, baseline = self.session_context
            monitoring_snapshot = build_session_monitoring_snapshot(
                session=session,
                baseline=baseline,
                detection_result=detection,
            )
            measurement_change = evaluate_measurement_change(
                monitoring_snapshot=monitoring_snapshot,
                threshold_config=self.measurement_thresholds,
            )

        landmarks = detection.get("landmarks")
        if not isinstance(landmarks, Mapping):
            landmarks = {}
        pose_points = landmarks.get("pose")
        face_points = landmarks.get("face")

        shoulder_tilt = _feature_value(detection, "shoulder_tilt")
        neck_lateral = _feature_value(detection, "neck_lateral_tilt")
        neck_flexion = _feature_value(detection, "neck_flexion")
        eye_distance = _feature_value(detection, "eye_distance")

        screen_distance = None
        if self.session_context is not None:
            _, baseline = self.session_context
            baseline_eye_distance = baseline.get("ipd_baseline")
            if baseline_eye_distance is None:
                baseline_eye_distance = baseline.get("screen_distance_baseline")
            screen_distance = self.screen_distance_policy.update(
                eye_distance,
                baseline_eye_distance,
                now=timestamp,
            )
        wellness_policy = getattr(self, "wellness_alert_policy", None)
        if wellness_policy is None:
            # Compatibility for lightweight adapters/tests that construct the
            # service without invoking the hardware-heavy initializer.
            wellness_policy = WellnessAlertPolicy()
            self.wellness_alert_policy = wellness_policy
        wellness_alert = wellness_policy.update(
            screen_distance,
            blink_statistics,
            now=timestamp,
        )

        result = dict(detection)
        result.update({
            "detection": detection,
            "assessment": assessment,
            "temporal": temporal,
            "risk": risk,
            "risk_event": risk_event,
            "alert_policy": alert_policy,
            "monitoring_snapshot": monitoring_snapshot,
            "measurement_change": measurement_change,
            "blink_statistics": blink_statistics,
            "pose_points": pose_points,
            "face_points": face_points,
            "face_result": None,
            "shoulder_tilt": shoulder_tilt,
            "neck_lateral_tilt": (
                {"neck_tilt": neck_lateral}
                if neck_lateral is not None
                else None
            ),
            "neck_flexion": neck_flexion,
            "eye_distance": eye_distance,
            "screen_distance": screen_distance,
            "wellness_alert": wellness_alert,
            "eye_openness": eye.get("measurement"),
            "eye_state": eye.get("state"),
        })
        return result

    def process_data_gap(
        self,
        reason: str,
        *,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        """Advance lifecycle state without interpreting missing data as safe."""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("data-gap reason is required")
        if timestamp is None:
            import time
            timestamp = time.monotonic()

        normalized_reason = reason.strip().upper()
        # Uninterrupted posture and blink exposure cannot be proven while the
        # camera is unavailable. RiskEventTracker still preserves the active
        # risk episode below and records the DATA_GAP transition.
        self.temporal_tracker.reset()
        screen_distance = None
        if self.session_context is not None:
            _, baseline = self.session_context
            baseline_eye_distance = baseline.get("ipd_baseline")
            if baseline_eye_distance is None:
                baseline_eye_distance = baseline.get("screen_distance_baseline")
            screen_distance = self.screen_distance_policy.update(
                None,
                baseline_eye_distance,
                now=timestamp,
            )
        wellness_alert = self.wellness_alert_policy.update(
            screen_distance,
            {"window_ready": False, "blink_rate": None},
            now=timestamp,
        )
        risk = {
            "risk_contract_version": "1.2",
            "status": "NOT_EVALUATED",
            "reason": normalized_reason,
            "risk_level_available": False,
            "risk_level": None,
            "risk_event": None,
            "alert": None,
        }
        risk_event = self.risk_event_tracker.update(risk, now=timestamp)
        alert_policy = self.alert_policy.update(risk_event, now=timestamp)
        return {
            "assessment": {
                "status": "NOT_EVALUATED",
                "reason": normalized_reason,
                "factors": [],
            },
            "temporal": {
                "status": "DATA_GAP",
                "reason": normalized_reason,
                "active_factors": [],
            },
            "risk": risk,
            "risk_event": risk_event,
            "alert_policy": alert_policy,
            "screen_distance": screen_distance,
            "wellness_alert": wellness_alert,
            "data_gap_reason": normalized_reason,
        }

    def resume_after_data_gap(self, *, timestamp: float | None = None) -> None:
        """Restart measurement windows that require continuous camera data."""
        self.blink_statistics.start(timestamp=timestamp)

    def close(self):
        self.pipeline.close()
