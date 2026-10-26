import unittest
from unittest.mock import Mock, patch

import numpy as np

from app.services.detection_service import DetectionService


def feature(value, unit, *, valid=True):
    return {
        "valid": valid,
        "value": value if valid else None,
        "unit": unit,
        "reason": "OK" if valid else "NOT_AVAILABLE",
        "status": "validated_prototype",
    }


class DetectionBaselineContractTests(unittest.TestCase):
    def service_with_result(self, result):
        service = DetectionService.__new__(DetectionService)
        service.pipeline = Mock(process_frame=Mock(return_value=result))
        service.blink_statistics = Mock(
            update=Mock(return_value={"blink_rate": None})
        )
        service.temporal_tracker = Mock(
            update=Mock(return_value={"status": "COMPLETE"})
        )
        service.risk_event_tracker = Mock(
            update=Mock(return_value={"event_action": "NONE"})
        )
        service.alert_policy = Mock(
            update=Mock(return_value={"should_notify": False})
        )
        service.session_context = None
        service.measurement_thresholds = {}
        return service

    def test_detection_result_exposes_four_validated_baseline_features(self):
        detection = {
            "contract_version": "1.0",
            "timestamp": 100.0,
            "pose_detected": True,
            "face_detected": True,
            "context": {
                "state": "VALID",
                "reason": "OK",
                "allow_posture_evaluation": True,
            },
            "features": {
                "shoulder_tilt": feature(-1.25, "deg"),
                "neck_lateral_tilt": feature(2.5, "deg"),
                "neck_flexion": feature(3.75, "deg"),
                "eye_distance": feature(70.0, "px"),
            },
            "eye": {
                "state": {"calibrated": True, "eye_state": "OPEN"},
                "measurement": {"mean_eye_openness": 0.3},
                "blink": {"blink_event": False},
            },
            "landmarks": {"pose": {"left_shoulder": {}}, "face": {}},
        }
        service = self.service_with_result(detection)

        with (
            patch(
                "app.services.detection_service.assess_current_posture",
                return_value={"status": "COMPLETE"},
            ),
            patch(
                "app.services.detection_service.evaluate_risk",
                return_value={
                    "status": "EVALUATED",
                    "risk_level": "NONE",
                    "prototype_score": 0.0,
                },
            ),
        ):
            result = service.process_frame(
                np.zeros((360, 640, 3), dtype=np.uint8)
            )

        self.assertEqual(result["contract_version"], "1.0")
        self.assertTrue(result["context"]["allow_posture_evaluation"])
        self.assertEqual(result["shoulder_tilt"], -1.25)
        self.assertEqual(result["neck_lateral_tilt"], {"neck_tilt": 2.5})
        self.assertEqual(result["neck_flexion"], 3.75)
        self.assertEqual(result["eye_distance"], 70.0)
        self.assertIs(result["detection"], detection)

    def test_missing_measurement_is_explicitly_invalid(self):
        detection = {
            "contract_version": "1.0",
            "timestamp": 100.0,
            "pose_detected": False,
            "face_detected": False,
            "context": {
                "state": "INVALID",
                "reason": "POSE_OR_FACE_MISSING",
                "allow_posture_evaluation": False,
            },
            "features": {
                name: feature(None, unit, valid=False)
                for name, unit in (
                    ("shoulder_tilt", "deg"),
                    ("neck_lateral_tilt", "deg"),
                    ("neck_flexion", "deg"),
                    ("eye_distance", "px"),
                )
            },
            "eye": {"state": None, "measurement": None, "blink": {}},
            "landmarks": {"pose": None, "face": None},
        }
        service = self.service_with_result(detection)

        with (
            patch(
                "app.services.detection_service.assess_current_posture",
                return_value={"status": "NOT_EVALUATED"},
            ),
            patch(
                "app.services.detection_service.evaluate_risk",
                return_value={
                    "status": "NOT_EVALUATED",
                    "risk_level": None,
                    "prototype_score": None,
                },
            ),
        ):
            result = service.process_frame(
                np.zeros((360, 640, 3), dtype=np.uint8)
            )

        self.assertEqual(result["context"]["state"], "INVALID")
        self.assertTrue(all(
            not item["valid"] for item in result["features"].values()
        ))
        self.assertIsNone(result["shoulder_tilt"])
        self.assertIsNone(result["neck_lateral_tilt"])


if __name__ == "__main__":
    unittest.main()
