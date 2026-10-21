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
        early = statistics.update(blink_event=True, timestamp=20.0)
        ready = statistics.update(blink_event=False, timestamp=70.0)

        self.assertIsNone(early["blink_rate"])
        self.assertTrue(ready["window_ready"])
        self.assertEqual(ready["blink_rate"], 1.0)

    def test_risk_mapper_does_not_publish_incomplete_risk(self):
        result = map_prototype_risk_level(
            evaluation_status="PARTIAL",
            evidence_groups={},
        )
        self.assertFalse(result["available"])
        self.assertIsNone(result["level"])


if __name__ == "__main__":
    unittest.main()
