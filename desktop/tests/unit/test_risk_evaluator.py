import unittest

from app.vision.risk_evaluation import evaluate_risk


FEATURES = ("shoulder_tilt", "neck_lateral_tilt", "neck_flexion")


def assessment(active=None):
    active = active or {}
    return {
        "contract_version": "1.1",
        "status": "COMPLETE",
        "features": {
            name: {
                "evaluated": True,
                "is_posture_factor": name in active,
                "status": active.get(name, "NEUTRAL"),
            }
            for name in FEATURES
        },
    }


def temporal(active=None):
    active = active or {}
    return {
        "contract_version": "1.0",
        "status": "COMPLETE",
        "features": {
            name: {
                "evaluable": True,
                "active": name in active,
                "factor": active.get(name, (None, 0.0))[0],
                "continuous_seconds": active.get(name, (None, 0.0))[1],
            }
            for name in FEATURES
        },
    }


class RiskEvaluatorTests(unittest.TestCase):
    def test_neutral_posture_is_none(self):
        result = evaluate_risk(assessment(), temporal())

        self.assertEqual(result["status"], "EVALUATED")
        self.assertEqual(result["risk_level"], "NONE")
        self.assertEqual(result["prototype_score"], 0.0)
        self.assertIsNone(result["risk_score"])
        self.assertEqual(result["rula"]["status"], "NOT_EVALUATED")
        self.assertIsNone(result["rula"]["full_rula_score"])

    def test_single_active_group_progresses_with_duration(self):
        factors = {"neck_lateral_tilt": "NECK_LATERAL_RIGHT"}

        low = evaluate_risk(
            assessment(factors),
            temporal({"neck_lateral_tilt": ("NECK_LATERAL_RIGHT", 15.0)}),
        )
        moderate = evaluate_risk(
            assessment(factors),
            temporal({"neck_lateral_tilt": ("NECK_LATERAL_RIGHT", 60.0)}),
        )

        self.assertEqual(low["risk_level"], "LOW")
        self.assertEqual(low["prototype_score"], 1.0)
        self.assertEqual(moderate["risk_level"], "MODERATE")
        self.assertEqual(moderate["prototype_score"], 2.0)

    def test_two_groups_with_static_evidence_are_high(self):
        factors = {
            "shoulder_tilt": "SHOULDER_LEFT_HIGHER",
            "neck_flexion": "NECK_FLEXED",
        }
        durations = {
            "shoulder_tilt": ("SHOULDER_LEFT_HIGHER", 61.0),
            "neck_flexion": ("NECK_FLEXED", 10.0),
        }

        result = evaluate_risk(assessment(factors), temporal(durations))

        self.assertEqual(result["risk_level"], "HIGH")
        self.assertEqual(result["prototype_score"], 3.0)
        self.assertEqual(
            result["risk_level_mapping"]["active_group_count"], 2
        )

    def test_factor_mismatch_makes_result_partial(self):
        result = evaluate_risk(
            assessment({"neck_lateral_tilt": "NECK_LATERAL_LEFT"}),
            temporal({"neck_lateral_tilt": ("NECK_LATERAL_RIGHT", 60.0)}),
        )

        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["risk_level"])
        self.assertEqual(
            result["feature_results"]["neck_lateral_tilt"]["consistency"]["status"],
            "FACTOR_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
