import unittest

from app.services.personal_baseline_service import (
    BASELINE_COLLECTING,
    BASELINE_FAILED,
    BASELINE_NEED_CONFIRMATION,
    BASELINE_SUCCESS,
    PersonalBaselineCollector,
    PersonalBaselineConfig,
)


def detection_result(**feature_values):
    values = {
        "shoulder_tilt": -1.0,
        "neck_lateral_tilt": 2.0,
        "neck_flexion": 3.0,
        "eye_distance": 70.0,
        **feature_values,
    }
    return {
        "contract_version": "1.0",
        "timestamp": 1.0,
        "context": {
            "state": "VALID",
            "reason": "OK",
            "allow_posture_evaluation": True,
        },
        "features": {
            name: {
                "valid": value is not None,
                "value": value,
                "unit": "px" if name == "eye_distance" else "deg",
                "reason": "OK" if value is not None else "NOT_AVAILABLE",
                "status": "validated_prototype",
            }
            for name, value in values.items()
        },
    }


class PersonalBaselineCollectorTests(unittest.TestCase):
    def collector(self):
        now = [0.0]

        def clock():
            now[0] += 0.5
            return now[0]

        return PersonalBaselineCollector(
            PersonalBaselineConfig(
                target_samples=2,
                min_calibration_seconds=1.0,
                max_calibration_seconds=5.0,
            ),
            monotonic_fn=clock,
        )

    def test_valid_candidate_requires_explicit_confirmation(self):
        collector = self.collector()
        self.assertEqual(
            collector.add_detection_result(detection_result())["status"],
            BASELINE_COLLECTING,
        )
        candidate = collector.add_detection_result(detection_result())
        self.assertEqual(candidate["status"], BASELINE_NEED_CONFIRMATION)
        self.assertFalse(candidate["ready_for_session"])
        with self.assertRaises(RuntimeError):
            collector.get_usable_baseline()

        confirmed = collector.confirm()
        self.assertEqual(confirmed["status"], BASELINE_SUCCESS)
        self.assertTrue(collector.is_ready_for_session())
        self.assertEqual(collector.get_usable_baseline()["eye_distance"], 70.0)

    def test_missing_feature_is_rejected(self):
        collector = self.collector()
        status = collector.add_detection_result(
            detection_result(neck_flexion=None)
        )
        self.assertEqual(status["status"], BASELINE_COLLECTING)
        self.assertEqual(status["sample_count"], 0)
        self.assertEqual(status["rejected_frames"], 1)

    def test_user_rejection_never_becomes_session_ready(self):
        collector = self.collector()
        collector.add_detection_result(detection_result())
        collector.add_detection_result(detection_result())
        rejected = collector.reject()
        self.assertEqual(rejected["status"], BASELINE_FAILED)
        self.assertFalse(collector.is_ready_for_session())


if __name__ == "__main__":
    unittest.main()
