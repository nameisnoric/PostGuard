import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from app.services.detection_service import DetectionService


class DetectionBaselineContractTests(unittest.TestCase):
    def test_detection_result_exposes_four_validated_baseline_features(self):
        service = DetectionService.__new__(DetectionService)
        service.pose_detector = Mock()
        service.face_detector = Mock()
        pose_points = {
            "left_shoulder": object(),
            "right_shoulder": object(),
            "left_ear": object(),
            "right_ear": object(),
        }
        service.pose_detector.detect.return_value = pose_points
        service.face_detector.detect.return_value = SimpleNamespace(
            face_landmarks=[object()]
        )

        with (
            patch(
                "app.services.detection_service.calculate_shoulder_tilt",
                return_value=-1.25,
            ),
            patch(
                "app.services.detection_service.calculate_neck_lateral_tilt",
                return_value={"neck_tilt": 2.5},
            ),
            patch(
                "app.services.detection_service.extract_face_points",
                return_value={"eyes": "available"},
            ),
            patch(
                "app.services.detection_service.extract_face_orientation",
                return_value={"pitch": 3.75},
            ),
            patch(
                "app.services.detection_service.calculate_eye_distance",
                return_value={"eye_distance_px": 70.0},
            ),
        ):
            result = service.process_frame(
                np.zeros((360, 640, 3), dtype=np.uint8)
            )

        self.assertEqual(result["contract_version"], "1.0")
        self.assertTrue(result["context"]["allow_posture_evaluation"])
        expected = {
            "shoulder_tilt": (-1.25, "deg"),
            "neck_lateral_tilt": (2.5, "deg"),
            "neck_flexion": (3.75, "deg"),
            "eye_distance": (70.0, "px"),
        }
        for name, (value, unit) in expected.items():
            feature = result["features"][name]
            self.assertTrue(feature["valid"])
            self.assertEqual(feature["value"], value)
            self.assertEqual(feature["unit"], unit)
            self.assertEqual(feature["status"], "validated_prototype")

    def test_missing_measurement_is_explicitly_invalid(self):
        service = DetectionService.__new__(DetectionService)
        service.pose_detector = Mock(detect=Mock(return_value=None))
        service.face_detector = Mock(
            detect=Mock(return_value=SimpleNamespace(face_landmarks=[]))
        )
        with (
            patch(
                "app.services.detection_service.extract_face_points",
                return_value=None,
            ),
            patch(
                "app.services.detection_service.extract_face_orientation",
                return_value=None,
            ),
            patch(
                "app.services.detection_service.calculate_eye_distance",
                return_value=None,
            ),
        ):
            result = service.process_frame(
                np.zeros((360, 640, 3), dtype=np.uint8)
            )

        self.assertEqual(result["context"]["state"], "INVALID")
        self.assertTrue(all(
            not feature["valid"]
            for feature in result["features"].values()
        ))


if __name__ == "__main__":
    unittest.main()
