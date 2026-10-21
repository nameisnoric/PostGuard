import unittest

from app.vision.risk_evaluation.rula import (
    RulaInputError,
    action_level,
    assess_full_rula,
    camera_rula_partial,
    force_load_score,
    lower_arm_score,
    muscle_use_score,
    neck_score,
    table_a_score,
    table_b_score,
    table_c_score,
    trunk_score,
    upper_arm_score,
    wrist_score,
    wrist_twist_score,
)


class RulaTests(unittest.TestCase):
    def test_body_part_boundaries(self):
        self.assertEqual(upper_arm_score(0), 1)
        self.assertEqual(upper_arm_score(20), 1)
        self.assertEqual(upper_arm_score(20.1), 2)
        self.assertEqual(upper_arm_score(45.1), 3)
        self.assertEqual(upper_arm_score(90.1), 4)
        self.assertEqual(lower_arm_score(60), 1)
        self.assertEqual(lower_arm_score(100), 1)
        self.assertEqual(lower_arm_score(101), 2)
        self.assertEqual(wrist_score(0), 1)
        self.assertEqual(wrist_score(15), 2)
        self.assertEqual(wrist_score(15.1), 3)
        self.assertEqual(wrist_twist_score(False), 1)
        self.assertEqual(wrist_twist_score(True), 2)

    def test_neck_and_trunk_boundaries(self):
        self.assertEqual(neck_score(0), 1)
        self.assertEqual(neck_score(10), 1)
        self.assertEqual(neck_score(10.1), 2)
        self.assertEqual(neck_score(20.1), 3)
        self.assertEqual(neck_score(-0.1), 4)
        self.assertEqual(neck_score(15, side_bent=True), 3)
        self.assertEqual(trunk_score(0), 1)
        self.assertEqual(trunk_score(20), 2)
        self.assertEqual(trunk_score(60), 3)
        self.assertEqual(trunk_score(60.1), 4)

    def test_muscle_and_force_rules(self):
        self.assertEqual(muscle_use_score(static_seconds=60), 0)
        self.assertEqual(muscle_use_score(static_seconds=60.1), 1)
        self.assertEqual(muscle_use_score(repetitions_per_minute=4), 1)
        self.assertEqual(force_load_score(1.9), 0)
        self.assertEqual(force_load_score(2), 1)
        self.assertEqual(force_load_score(2, static_or_repeated=True), 2)
        self.assertEqual(force_load_score(10.1), 3)
        self.assertEqual(force_load_score(0, shock=True), 3)

    def test_official_tables_and_action_levels(self):
        self.assertEqual(table_a_score(1, 1, 1, 1), 1)
        self.assertEqual(table_a_score(6, 3, 4, 2), 9)
        self.assertEqual(table_b_score(1, 1, 1), 1)
        self.assertEqual(table_b_score(6, 6, 2), 9)
        self.assertEqual(table_c_score(1, 1), 1)
        self.assertEqual(table_c_score(13, 13), 7)
        self.assertEqual(action_level(2), (1, "ACCEPTABLE"))
        self.assertEqual(action_level(4)[0], 2)
        self.assertEqual(action_level(6)[0], 3)
        self.assertEqual(action_level(7)[0], 4)

    def test_full_rula_low_and_high_examples(self):
        low = assess_full_rula({
            "upper_arm": 1, "lower_arm": 1, "wrist": 1, "wrist_twist": 1,
            "neck": 1, "trunk": 1, "legs": 1,
            "muscle_use_a": 0, "force_load_a": 0,
            "muscle_use_b": 0, "force_load_b": 0,
        })
        high = assess_full_rula({
            "upper_arm": 6, "lower_arm": 3, "wrist": 4, "wrist_twist": 2,
            "neck": 6, "trunk": 6, "legs": 2,
            "muscle_use_a": 1, "force_load_a": 3,
            "muscle_use_b": 1, "force_load_b": 3,
        })

        self.assertEqual(low["final_score"], 1)
        self.assertEqual(low["action_level"], 1)
        self.assertEqual(high["final_score"], 7)
        self.assertEqual(high["action_level"], 4)

    def test_partial_never_invents_full_score(self):
        result = assess_full_rula({"neck": 2})
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["final_score"])
        self.assertIn("upper_arm", result["missing"])

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
        self.assertEqual(result["neck_score_lower_bound"], 3)
        self.assertEqual(result["muscle_use_score"], 1)
        self.assertIsNone(result["final_score"])
        self.assertIn("neck_twist", result["missing"])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(RulaInputError):
            neck_score(float("nan"))
        with self.assertRaises(RulaInputError):
            table_a_score(0, 1, 1, 1)
        with self.assertRaises(RulaInputError):
            force_load_score(-1)


if __name__ == "__main__":
    unittest.main()
