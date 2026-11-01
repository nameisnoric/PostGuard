import unittest
from pathlib import Path

from app.vision.mediapipe_detection.eye.blink_statistics import BlinkStatistics
from app.vision.posture_assessment.current_posture_assessment import (
    assess_current_posture,
)
from app.vision.risk_evaluation import map_prototype_risk_level
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


def valid_feature(value, unit="deg"):
    return {
        "valid": True,
        "value": value,
        "unit": unit,
        "reason": "OK",
        "status": "validated_prototype",
    }


def detection_result():
    return {
        "contract_version": "1.0",
        "timestamp": 100.0,
        "context": {
            "state": "VALID",
            "allow_posture_evaluation": True,
            "reason": "OK",
            "stable_seconds": 2.0,
        },
        "features": {
            "shoulder_tilt": valid_feature(5.0),
            "neck_lateral_tilt": valid_feature(8.0),
            "neck_flexion": valid_feature(12.0),
            "eye_distance": valid_feature(72.0, "px"),
        },
    }


class CameraSessionIntegrationTests(unittest.TestCase):
    def test_current_posture_feeds_temporal_tracker(self):
        assessment = assess_current_posture(detection_result())
        tracker = TemporalPostureTracker()
        first = tracker.update(assessment, now=100.0)
        second = tracker.update(assessment, now=103.5)

        self.assertEqual(assessment["status"], "COMPLETE")
        self.assertGreater(assessment["factor_count"], 0)
        self.assertEqual(first["contract_version"], "1.0")
        self.assertGreaterEqual(
            second["features"]["neck_flexion"]["continuous_seconds"],
            3.5,
        )

    def test_session_snapshot_feeds_measurement_change_gate(self):
        session = {
            "session_id": 9,
            "baseline_id": 4,
            "camera_id": 2,
            "user_id": 7,
            "status": "RUNNING",
        }
        baseline = {
            "baseline_id": 4,
            "camera_id": 2,
            "user_id": 7,
            "shoulder_angle": 0.0,
            "lateral_tilt_baseline": 0.0,
            "neck_flexion_baseline": 0.0,
            "eye_distance_baseline_px": 70.0,
        }
        snapshot = build_session_monitoring_snapshot(
            session,
            baseline,
            detection_result(),
        )
        config_path = (
            Path(__file__).resolve().parents[2]
            / "app"
            / "vision"
            / "session_monitoring"
            / "measurement_change_thresholds.json"
        )
        gate = evaluate_measurement_change(
            snapshot,
            load_measurement_change_thresholds(config_path),
        )

        self.assertEqual(snapshot["session"]["session_id"], 9)
        self.assertEqual(gate["features"]["shoulder_tilt"]["status"], "CHANGED")
        self.assertEqual(gate["features"]["neck_lateral_tilt"]["status"], "CHANGED")

    def test_blink_statistics_waits_for_full_window(self):
        statistics = BlinkStatistics(window_seconds=60.0)
        statistics.start(timestamp=10.0)
        early = None
        for second in range(11, 71):
            early = statistics.update(
                blink_event=second == 20,
                timestamp=float(second),
                observation_valid=True,
            )
        ready = early

        self.assertTrue(ready["window_ready"])
        self.assertEqual(ready["blink_rate"], 1.0)

    def test_blink_statistics_requires_valid_eye_observation(self):
        statistics = BlinkStatistics(window_seconds=60.0, min_valid_seconds=45.0)
        statistics.start(timestamp=0.0)
        result = None
        for second in range(1, 61):
            result = statistics.update(
                timestamp=float(second),
                observation_valid=second <= 30,
            )
        self.assertFalse(result["window_ready"])
        self.assertIsNone(result["blink_rate"])

    def test_blink_statistics_restarts_after_long_eye_gap(self):
        statistics = BlinkStatistics(window_seconds=60.0, min_valid_seconds=45.0)
        statistics.start(timestamp=0.0)
        for second in range(1, 11):
            statistics.update(timestamp=float(second), observation_valid=True)
        statistics.update(timestamp=13.1, observation_valid=False)
        resumed = statistics.update(timestamp=14.0, observation_valid=True)
        self.assertFalse(resumed["window_ready"])
        self.assertEqual(resumed["valid_observation_seconds"], 0.0)

    def test_risk_mapper_does_not_publish_incomplete_risk(self):
        result = map_prototype_risk_level(
            evaluation_status="PARTIAL",
            evidence_groups={},
        )
        self.assertFalse(result["available"])
        self.assertIsNone(result["level"])


if __name__ == "__main__":
    unittest.main()
