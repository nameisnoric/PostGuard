import math
import unittest
from unittest.mock import MagicMock, patch

from app.services.detection_service import (
    DETECTION_CONTRACT_VERSION,
    EXPERIMENTAL_STATUS,
    VALIDATED_STATUS,
    DetectionService,
    _invalid_feature,
    _is_finite_number,
    _valid_feature,
)


class FakeFrame:
    def __init__(self):
        self.size = 100
        self.shape = (480, 640, 3)


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
    return {
        "x": x,
        "y": y,
        "visibility": visibility,
        "presence": presence,
        "world_x": world_x,
        "world_y": world_y,
        "world_z": world_z,
    }


def make_valid_pose():
    return {
        "left_shoulder": make_pose_point(
            x=0.40,
            y=0.50,
            world_x=-0.2,
        ),
        "right_shoulder": make_pose_point(
            x=0.60,
            y=0.50,
            world_x=0.2,
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
    x_norm=None,
    y_norm=None,
    z=0.0,
):
    return {
        "x": x,
        "y": y,
        "x_norm": (
            x / 640.0
            if x_norm is None
            else x_norm
        ),
        "y_norm": (
            y / 480.0
            if y_norm is None
            else y_norm
        ),
        "z": z,
    }


def make_valid_face_points():
    return {
        "left_eye_outer": make_face_point(
            x=400,
            y=200,
        ),
        "left_eye_inner": make_face_point(
            x=370,
            y=200,
        ),
        "right_eye_inner": make_face_point(
            x=270,
            y=200,
        ),
        "right_eye_outer": make_face_point(
            x=240,
            y=200,
        ),
    }


class DetectionFeatureContractTests(
    unittest.TestCase
):
    def test_finite_number_accepts_normal_number(self):
        self.assertTrue(
            _is_finite_number(1.25)
        )

    def test_finite_number_rejects_bool(self):
        self.assertFalse(
            _is_finite_number(True)
        )

    def test_finite_number_rejects_nan(self):
        self.assertFalse(
            _is_finite_number(
                float("nan")
            )
        )

    def test_finite_number_rejects_infinity(self):
        self.assertFalse(
            _is_finite_number(
                float("inf")
            )
        )

    def test_valid_feature_contract(self):
        result = _valid_feature(
            12.5,
            "deg",
        )

        self.assertEqual(
            result["valid"],
            True,
        )
        self.assertEqual(
            result["value"],
            12.5,
        )
        self.assertEqual(
            result["unit"],
            "deg",
        )
        self.assertEqual(
            result["reason"],
            "OK",
        )
        self.assertEqual(
            result["status"],
            VALIDATED_STATUS,
        )

    def test_invalid_feature_has_no_value(self):
        result = _invalid_feature(
            unit="deg",
            reason="TEST_FAILURE",
        )

        self.assertFalse(
            result["valid"]
        )
        self.assertIsNone(
            result["value"]
        )
        self.assertEqual(
            result["reason"],
            "TEST_FAILURE",
        )


class DetectionFeatureIsolationTests(
    unittest.TestCase
):
    def test_missing_face_does_not_invalidate_shoulder(self):
        pose = make_valid_pose()

        with patch(
            "app.services.detection_service."
            "calculate_shoulder_tilt",
            return_value=2.5,
        ):
            value, feature = (
                DetectionService
                ._detect_shoulder_tilt(
                    pose
                )
            )

        self.assertEqual(
            value,
            2.5,
        )
        self.assertTrue(
            feature["valid"]
        )

    def test_missing_ear_invalidates_neck_lateral_only(self):
        pose = make_valid_pose()

        del pose["left_ear"]

        (
            value,
            measurement,
            feature,
        ) = (
            DetectionService
            ._detect_neck_lateral_tilt(
                pose
            )
        )

        self.assertIsNone(
            value
        )
        self.assertIsNone(
            measurement
        )
        self.assertFalse(
            feature["valid"]
        )

    def test_invalid_shoulder_measurement_is_not_safe_zero(self):
        pose = make_valid_pose()

        with patch(
            "app.services.detection_service."
            "calculate_shoulder_tilt",
            return_value=float("nan"),
        ):
            value, feature = (
                DetectionService
                ._detect_shoulder_tilt(
                    pose
                )
            )

        self.assertIsNone(
            value
        )
        self.assertFalse(
            feature["valid"]
        )
        self.assertEqual(
            feature["reason"],
            "SHOULDER_TILT_MEASUREMENT_INVALID",
        )

    def test_neck_lateral_missing_measurement_value_has_reason(self):
        pose = make_valid_pose()

        with patch(
            "app.services.detection_service."
            "calculate_neck_lateral_tilt",
            return_value={},
        ):
            (
                value,
                measurement,
                feature,
            ) = (
                DetectionService
                ._detect_neck_lateral_tilt(
                    pose
                )
            )

        self.assertIsNone(
            value
        )
        self.assertEqual(
            measurement,
            {},
        )
        self.assertFalse(
            feature["valid"]
        )
        self.assertEqual(
            feature["reason"],
            "NECK_LATERAL_VALUE_MISSING",
        )

    def test_neck_lateral_nonfinite_value_has_reason(self):
        pose = make_valid_pose()

        with patch(
            "app.services.detection_service."
            "calculate_neck_lateral_tilt",
            return_value={
                "neck_tilt": float("inf"),
            },
        ):
            (
                value,
                _measurement,
                feature,
            ) = (
                DetectionService
                ._detect_neck_lateral_tilt(
                    pose
                )
            )

        self.assertIsNone(
            value
        )
        self.assertFalse(
            feature["valid"]
        )
        self.assertEqual(
            feature["reason"],
            "NECK_LATERAL_VALUE_INVALID",
        )


class NeckFlexionContractTests(
    unittest.TestCase
):
    def test_missing_face_is_experimental_invalid(self):
        value, feature = (
            DetectionService
            ._detect_neck_flexion(
                None,
                False,
            )
        )

        self.assertIsNone(
            value
        )
        self.assertFalse(
            feature["valid"]
        )
        self.assertEqual(
            feature["status"],
            EXPERIMENTAL_STATUS,
        )

    def test_orientation_missing_is_invalid(self):
        with patch(
            "app.services.detection_service."
            "extract_face_orientation",
            return_value=None,
        ):
            value, feature = (
                DetectionService
                ._detect_neck_flexion(
                    object(),
                    True,
                )
            )

        self.assertIsNone(
            value
        )
        self.assertFalse(
            feature["valid"]
        )
        self.assertEqual(
            feature["reason"],
            "FACE_ORIENTATION_NOT_AVAILABLE",
        )

    def test_pitch_nan_is_invalid(self):
        with patch(
            "app.services.detection_service."
            "extract_face_orientation",
            return_value={
                "pitch": float("nan"),
            },
        ):
            value, feature = (
                DetectionService
                ._detect_neck_flexion(
                    object(),
                    True,
                )
            )

        self.assertIsNone(
            value
        )
        self.assertFalse(
            feature["valid"]
        )
        self.assertEqual(
            feature["reason"],
            "FACE_ORIENTATION_PITCH_INVALID",
        )

    def test_valid_pitch_remains_experimental(self):
        with patch(
            "app.services.detection_service."
            "extract_face_orientation",
            return_value={
                "pitch": 12.0,
                "singular": False,
                "rotation_det": 1.0,
                "scale": 1.0,
            },
        ):
            value, feature = (
                DetectionService
                ._detect_neck_flexion(
                    object(),
                    True,
                )
            )

        self.assertEqual(
            value,
            12.0,
        )
        self.assertTrue(
            feature["valid"]
        )
        self.assertEqual(
            feature["status"],
            EXPERIMENTAL_STATUS,
        )


class EyeDistanceContractTests(
    unittest.TestCase
):
    def test_missing_face_points_invalidates_eye_distance(self):
        (
            value,
            measurement,
            feature,
        ) = (
            DetectionService
            ._detect_eye_distance(
                None
            )
        )

        self.assertIsNone(
            value
        )
        self.assertIsNone(
            measurement
        )
        self.assertFalse(
            feature["valid"]
        )

    def test_valid_eye_distance(self):
        face_points = (
            make_valid_face_points()
        )

        with patch(
            "app.services.detection_service."
            "calculate_eye_distance",
            return_value={
                "eye_distance_px": 100.0,
            },
        ):
            (
                value,
                measurement,
                feature,
            ) = (
                DetectionService
                ._detect_eye_distance(
                    face_points
                )
            )

        self.assertEqual(
            value,
            100.0,
        )
        self.assertEqual(
            measurement[
                "eye_distance_px"
            ],
            100.0,
        )
        self.assertTrue(
            feature["valid"]
        )

    def test_eye_distance_nan_is_invalid(self):
        face_points = (
            make_valid_face_points()
        )

        with patch(
            "app.services.detection_service."
            "calculate_eye_distance",
            return_value={
                "eye_distance_px": float("nan"),
            },
        ):
            (
                value,
                _measurement,
                feature,
            ) = (
                DetectionService
                ._detect_eye_distance(
                    face_points
                )
            )

        self.assertIsNone(
            value
        )
        self.assertFalse(
            feature["valid"]
        )
        self.assertEqual(
            feature["reason"],
            "EYE_DISTANCE_VALUE_INVALID",
        )


class DetectionProcessContractTests(
    unittest.TestCase
):
    def _make_service_without_models(self):
        service = (
            DetectionService.__new__(
                DetectionService
            )
        )

        service.pose_detector = (
            MagicMock()
        )

        service.face_detector = (
            MagicMock()
        )

        service.context_filter = (
            MagicMock()
        )

        return service

    def test_process_frame_preserves_context_transition(
        self,
    ):
        service = (
            self._make_service_without_models()
        )

        pose = make_valid_pose()

        service.pose_detector.detect.return_value = (
            pose
        )

        service.face_detector.detect.return_value = (
            None
        )

        service.context_filter.update.return_value = {
            "state": "TRANSITION",
            "allow_posture_evaluation": False,
            "reason": "stabilizing",
            "stable_seconds": 0.1,
        }

        frame = FakeFrame()

        with patch(
            "app.services.detection_service."
            "calculate_shoulder_tilt",
            return_value=2.0,
        ), patch(
            "app.services.detection_service."
            "calculate_neck_lateral_tilt",
            return_value={
                "neck_tilt": 1.0,
            },
        ):
            result = (
                service.process_frame(
                    frame
                )
            )

        self.assertEqual(
            result["contract_version"],
            DETECTION_CONTRACT_VERSION,
        )

        self.assertEqual(
            result["context"]["state"],
            "TRANSITION",
        )

        self.assertFalse(
            result["context"][
                "allow_posture_evaluation"
            ]
        )

        # Context transition must NOT erase an otherwise
        # measurable posture feature.
        self.assertTrue(
            result["features"][
                "shoulder_tilt"
            ]["valid"]
        )

        # Assessment, not DetectionService, is responsible
        # for rejecting posture evaluation on this frame.

    def test_eye_distance_is_not_gated_by_posture_context(
        self,
    ):
        service = (
            self._make_service_without_models()
        )

        service.pose_detector.detect.return_value = (
            None
        )

        fake_face_result = MagicMock()

        fake_face_result.face_landmarks = [
            object()
        ]

        service.face_detector.detect.return_value = (
            fake_face_result
        )

        service.context_filter.update.return_value = {
            "state": "UNKNOWN",
            "allow_posture_evaluation": False,
            "reason": "pose_not_detected",
            "stable_seconds": 0.0,
        }

        face_points = (
            make_valid_face_points()
        )

        frame = FakeFrame()

        with patch(
            "app.services.detection_service."
            "extract_face_points",
            return_value=face_points,
        ), patch(
            "app.services.detection_service."
            "calculate_eye_distance",
            return_value={
                "eye_distance_px": 100.0,
            },
        ), patch(
            "app.services.detection_service."
            "extract_face_orientation",
            return_value={
                "pitch": 0.0,
                "singular": False,
                "rotation_det": 1.0,
                "scale": 1.0,
            },
        ):
            result = (
                service.process_frame(
                    frame
                )
            )

        self.assertEqual(
            result["context"]["state"],
            "UNKNOWN",
        )

        self.assertFalse(
            result["context"][
                "allow_posture_evaluation"
            ]
        )

        self.assertTrue(
            result["features"][
                "eye_distance"
            ]["valid"]
        )

        self.assertEqual(
            result["features"][
                "eye_distance"
            ]["value"],
            100.0,
        )

    def test_reset_runtime_resets_context_filter(
        self,
    ):
        service = (
            self._make_service_without_models()
        )

        service.reset_runtime()

        service.context_filter.reset.assert_called_once_with()

    def test_close_releases_both_detectors(
        self,
    ):
        service = (
            self._make_service_without_models()
        )

        service.close()

        service.context_filter.reset.assert_called_once_with()
        service.pose_detector.close.assert_called_once_with()
        service.face_detector.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()