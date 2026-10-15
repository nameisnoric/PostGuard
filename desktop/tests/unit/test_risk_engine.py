import unittest
from app.services.risk_engine import assess_posture, neck_score, duration_score, risk_level


class RiskEngineTests(unittest.TestCase):
    def test_neck_boundaries(self):
        self.assertEqual(neck_score(0), 1)
        self.assertEqual(neck_score(10), 1)
        self.assertEqual(neck_score(10.01), 2)
        self.assertEqual(neck_score(20), 2)
        self.assertEqual(neck_score(20.01), 3)
        self.assertEqual(neck_score(extension=True), 4)

    def test_duration_boundary(self):
        self.assertEqual(duration_score(59.9), 0)
        self.assertEqual(duration_score(60), 1)

    def test_complete_highest_score(self):
        result = assess_posture(
            neck_extension=True,
            neck_side_bending=True,
            neck_rotation=True,
            trunk_level=3,
            sustained_seconds=60,
        )
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["raw_score"], 10)
        self.assertEqual(result["risk_level"], "ACTION_REQUIRED")

    def test_partial_does_not_invent_missing_factors(self):
        result = assess_posture(neck_side_bending=True)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["raw_score"])
        self.assertIsNone(result["risk_level"])
        self.assertEqual(len(result["missing_factors"]), 4)

    def test_risk_bands(self):
        self.assertEqual(risk_level(2), "ACCEPTABLE")
        self.assertEqual(risk_level(3), "IMPROVEMENT_MAY_BE_NEEDED")
        self.assertEqual(risk_level(5), "IMPROVE_SOON")
        self.assertEqual(risk_level(7), "ACTION_REQUIRED")
        self.assertEqual(risk_level(10), "ACTION_REQUIRED")

    def test_invalid_values(self):
        with self.assertRaises(ValueError):
            neck_score(-3)
        with self.assertRaises(ValueError):
            assess_posture(neck_side_bending=3)
        with self.assertRaises(ValueError):
            assess_posture(trunk_level=4)
        with self.assertRaises(ValueError):
            assess_posture(sustained_seconds=-1)


if __name__ == "__main__":
    unittest.main()
