import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from app.services.detection_service import (
    DetectionService,
    EXPERIMENTAL_STATUS,
    VALIDATED_STATUS,
)


def make_pose_point(
    *,
    x=0.5,
    y=0.5,
    visibility=0.99,
    presence=0.99,
    world_x=0.0,
    world_y=0.0,
    world_z=0.0,
):
    """
    Build a pose landmark that satisfies the current
    feature-specific pose validators.
    """

    return {
        "x": x,
        "y": y,
        "visibility": visibility,
        "presence": presence,
        "world_x": world_x,
        "world_y": world_y,
        "world_z": world_z,
    }


def make_valid_pose_points():
    """
    Minimal pose required by the current DetectionService
    posture features and ContextFilter.
    """

    return {
        "left_shoulder": make_pose_point(
            x=0.40,
            y=0.50,
            world_x=-0.20,
        ),
        "right_shoulder": make_pose_point(
            x=0.60,
            y=0.50,
            world_x=0.20,
        ),
        "left_ear": make_pose_point(
            x=0.44,
            y=0.30,
        ),
        "right_ear": make_pose_point(
            x=0.56,
            y=0.30,
        ),
        "nose": make_pose_point(
            x=0.50,
            y=0.32,
        ),
    }


def make_face_point(
    *,
    x,
    y,
    x_norm,
    y_norm,
    z=0.0,
):
    """
    Build a face landmark that satisfies
    validate_face_feature().
    """

    return {
        "x": x,
        "y": y,
        "x_norm": x_norm,
        "y_norm": y_norm,
        "z": z,
    }


def make_valid_face_points():
    """
    Eye-corner landmarks required by calculate_eye_distance().
    """

    return {
        "left_eye_outer": make_face_point(
            x=400,
            y=200,
            x_norm=0.625,
            y_norm=0.4167,
        ),
        "left_eye_inner": make_face_point(
            x=370,
            y=200,
            x_norm=0.5781,
            y_norm=0.4167,
        ),
        "right_eye_inner": make_face_point(
            x=270,
            y=200,
            x_norm=0.4219,
            y_norm=0.4167,
        ),
        "right_eye_outer": make_face_point(
            x=240,
            y=200,
            x_norm=0.375,
            y_norm=0.4167,
        ),
    }


def make_service_without_models():
    """
    Create DetectionService without loading real MediaPipe
    model files.

    Because __init__() is deliberately bypassed, every runtime
    dependency normally created by __init__() must be supplied
    explicitly here.
    """

    service = DetectionService.__new__(
        DetectionService
    )

    service.pose_detector = Mock()
    service.face_detector = Mock()
    service.context_filter = Mock()

    return service


class DetectionBaselineContractTests(
    unittest.TestCase
):
    def test_detection_result_exposes_four_baseline_features(
        self,
    ):
        """
        Detection Contract must expose all four measurements
        currently required by Personal Baseline.

        IMPORTANT:
        neck_flexion is currently EXPERIMENTAL.

        Therefore this test checks feature availability and
        validity without falsely claiming that all four
        measurements have validated_prototype status.
        """

        service = make_service_without_models()

        pose_points = (
            make_valid_pose_points()
        )

        face_points = (
            make_valid_face_points()
        )

        service.pose_detector.detect.return_value = (
            pose_points
        )

        service.face_detector.detect.return_value = (
            SimpleNamespace(
                face_landmarks=[
                    object()
                ]
            )
        )

        service.context_filter.update.return_value = {
            "state": "VALID",
            "reason": "stable_upper_body",
            "allow_posture_evaluation": True,
            "stable_seconds": 1.0,
        }

        with (
            patch(
                "app.services.detection_service."
                "calculate_shoulder_tilt",
                return_value=-1.25,
            ),
            patch(
                "app.services.detection_service."
                "calculate_neck_lateral_tilt",
                return_value={
                    "neck_tilt": 2.5,
                },
            ),
            patch(
                "app.services.detection_service."
                "extract_face_points",
                return_value=face_points,
            ),
            patch(
                "app.services.detection_service."
                "extract_face_orientation",
                return_value={
                    "pitch": 3.75,
                    "singular": False,
                    "rotation_det": 1.0,
                    "scale": 1.0,
                },
            ),
            patch(
                "app.services.detection_service."
                "calculate_eye_distance",
                return_value={
                    "eye_distance_px": 70.0,
                },
            ),
        ):
            result = service.process_frame(
                np.zeros(
                    (360, 640, 3),
                    dtype=np.uint8,
                )
            )

        # --------------------------------------------------
        # Detection Contract
        # --------------------------------------------------

        self.assertEqual(
            result["contract_version"],
            "1.0",
        )

        # --------------------------------------------------
        # Context Contract
        # --------------------------------------------------

        self.assertEqual(
            result["context"]["state"],
            "VALID",
        )

        self.assertTrue(
            result["context"][
                "allow_posture_evaluation"
            ]
        )

        # --------------------------------------------------
        # Valid measurements
        # --------------------------------------------------

        expected = {
            "shoulder_tilt": (
                -1.25,
                "deg",
            ),
            "neck_lateral_tilt": (
                2.5,
                "deg",
            ),
            "neck_flexion": (
                3.75,
                "deg",
            ),
            "eye_distance": (
                70.0,
                "px",
            ),
        }

        for (
            name,
            (value, unit),
        ) in expected.items():

            feature = (
                result["features"][name]
            )

            self.assertTrue(
                feature["valid"],
                msg=(
                    f"{name} should be valid: "
                    f"{feature}"
                ),
            )

            self.assertEqual(
                feature["value"],
                value,
            )

            self.assertEqual(
                feature["unit"],
                unit,
            )

            self.assertEqual(
                feature["reason"],
                "OK",
            )

        # --------------------------------------------------
        # Validation status must remain truthful
        # --------------------------------------------------

        self.assertEqual(
            result["features"][
                "shoulder_tilt"
            ]["status"],
            VALIDATED_STATUS,
        )

        self.assertEqual(
            result["features"][
                "neck_lateral_tilt"
            ]["status"],
            VALIDATED_STATUS,
        )

        self.assertEqual(
            result["features"][
                "eye_distance"
            ]["status"],
            VALIDATED_STATUS,
        )

        self.assertEqual(
            result["features"][
                "neck_flexion"
            ]["status"],
            EXPERIMENTAL_STATUS,
        )

        # --------------------------------------------------
        # Legacy compatibility keys
        # --------------------------------------------------

        self.assertEqual(
            result["shoulder_tilt"],
            -1.25,
        )

        self.assertIsInstance(
            result["neck_lateral_tilt"],
            dict,
        )

        self.assertEqual(
            result["neck_lateral_tilt"][
                "neck_tilt"
            ],
            2.5,
        )

        self.assertEqual(
            result["neck_flexion"],
            3.75,
        )

        self.assertEqual(
            result["eye_distance"],
            70.0,
        )

    def test_missing_measurement_is_explicitly_invalid(
        self,
    ):
        """
        Missing Pose and Face data must never be converted into
        fake safe numeric values.

        ContextFilter contract:
            missing pose -> UNKNOWN

        Feature contract:
            missing measurement -> valid=False
                                  -> value=None
        """

        service = make_service_without_models()

        service.pose_detector.detect.return_value = (
            None
        )

        service.face_detector.detect.return_value = (
            SimpleNamespace(
                face_landmarks=[]
            )
        )

        service.context_filter.update.return_value = {
            "state": "UNKNOWN",
            "reason": "pose_not_detected",
            "allow_posture_evaluation": False,
            "stable_seconds": 0.0,
        }

        with (
            patch(
                "app.services.detection_service."
                "extract_face_points",
                return_value=None,
            ),
            patch(
                "app.services.detection_service."
                "extract_face_orientation",
                return_value=None,
            ),
            patch(
                "app.services.detection_service."
                "calculate_eye_distance",
                return_value=None,
            ),
        ):
            result = service.process_frame(
                np.zeros(
                    (360, 640, 3),
                    dtype=np.uint8,
                )
            )

        # --------------------------------------------------
        # Context must be UNKNOWN, not fake VALID/INVALID.
        # --------------------------------------------------

        self.assertEqual(
            result["context"]["state"],
            "UNKNOWN",
        )

        self.assertFalse(
            result["context"][
                "allow_posture_evaluation"
            ]
        )

        # --------------------------------------------------
        # No feature may invent a safe zero.
        # --------------------------------------------------

        for (
            name,
            feature,
        ) in result["features"].items():

            self.assertFalse(
                feature["valid"],
                msg=(
                    f"{name} unexpectedly valid: "
                    f"{feature}"
                ),
            )

            self.assertIsNone(
                feature["value"],
                msg=(
                    f"{name} invented a value: "
                    f"{feature}"
                ),
            )

            self.assertNotEqual(
                feature["reason"],
                "OK",
            )

        # --------------------------------------------------
        # Legacy compatibility values also remain missing.
        # --------------------------------------------------

        self.assertIsNone(
            result["shoulder_tilt"]
        )

        self.assertIsNone(
            result["neck_lateral_tilt"]
        )

        self.assertIsNone(
            result["neck_flexion"]
        )

        self.assertIsNone(
            result["eye_distance"]
        )


if __name__ == "__main__":
    unittest.main()