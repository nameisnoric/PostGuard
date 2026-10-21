import unittest

from app.vision.risk_evaluation.rula import (
    RulaInputError,
    evaluate_front_camera_risk,
    neck_score,
)


class RulaAdaptedRiskTests(unittest.TestCase):
    def test_neck_boundaries_and_side_bending(self):
        self.assertEqual(neck_score(0), 1)
        self.assertEqual(neck_score(10), 1)
        self.assertEqual(neck_score(10.1), 2)
        self.assertEqual(neck_score(20.1), 3)
        self.assertEqual(neck_score(-0.1), 4)
        self.assertEqual(neck_score(15, side_bent=True), 3)
        self.assertEqual(neck_score(-1, side_bent=True), 5)

    def test_front_camera_score_uses_neck_shoulder_and_duration(self):
        assessment = {
            "features": {
                "neck_flexion": {"evaluated": True, "current": 15.0},
                "neck_lateral_tilt": {
                    "evaluated": True,
                    "is_posture_factor": True,
                },
                "shoulder_tilt": {
                    "evaluated": True,
                    "is_posture_factor": True,
                },
            },
        }
        temporal = {
            "features": {
                "neck_flexion": {
                    "active": True,
                    "continuous_seconds": 61.0,
                },
            },
        }

        result = evaluate_front_camera_risk(assessment, temporal)

        self.assertEqual(result["status"], "EVALUATED")
        self.assertEqual(result["score"], 5)
        self.assertEqual(result["risk_level"], "HIGH")
        self.assertEqual(result["components"]["neck_base"], 2)
        self.assertEqual(result["components"]["neck_side_bending"], 1)
        self.assertEqual(result["components"]["shoulder_asymmetry"], 1)
        self.assertEqual(result["components"]["sustained_posture"], 1)
        self.assertTrue(result["static_over_60_seconds"])

    def test_missing_camera_evidence_is_not_evaluated(self):
        result = evaluate_front_camera_risk({"features": {}}, {"features": {}})
        self.assertEqual(result["status"], "NOT_EVALUATED")
        self.assertIsNone(result["score"])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(RulaInputError):
            neck_score(float("nan"))
        with self.assertRaises(RulaInputError):
            neck_score(0, side_bent=1)


if __name__ == "__main__":
    unittest.main()
