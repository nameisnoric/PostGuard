import unittest

from app.vision.risk_evaluation.rula import (
    RulaInputError,
    camera_rula_partial,
    neck_score,
)


class RulaNeckTests(unittest.TestCase):
    def test_neck_boundaries_and_side_bending(self):
        self.assertEqual(neck_score(0), 1)
        self.assertEqual(neck_score(10), 1)
        self.assertEqual(neck_score(10.1), 2)
        self.assertEqual(neck_score(20.1), 3)
        self.assertEqual(neck_score(-0.1), 4)
        self.assertEqual(neck_score(15, side_bent=True), 3)
        self.assertEqual(neck_score(-1, side_bent=True), 5)

    def test_camera_contract_returns_neck_lower_bound_only(self):
        assessment = {
            "features": {
                "neck_flexion": {"evaluated": True, "current": 15.0},
                "neck_lateral_tilt": {
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

        result = camera_rula_partial(assessment, temporal)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["body_region"], "NECK")
        self.assertEqual(result["neck_score_lower_bound"], 3)
        self.assertTrue(result["static_over_60_seconds"])
        self.assertIsNone(result["full_rula_score"])
        self.assertIn("neck_twist", result["missing"])

    def test_missing_camera_evidence_is_not_evaluated(self):
        result = camera_rula_partial({"features": {}}, {"features": {}})
        self.assertEqual(result["status"], "NOT_EVALUATED")
        self.assertIsNone(result["neck_score_lower_bound"])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(RulaInputError):
            neck_score(float("nan"))
        with self.assertRaises(RulaInputError):
            neck_score(0, side_bent=1)


if __name__ == "__main__":
    unittest.main()
