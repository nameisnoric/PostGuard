from __future__ import annotations

import copy
import unittest

from camera_card.risk_evaluation import (
    RiskEvaluationError,
    evaluate_risk,
)


def make_assessment(
    *,
    shoulder_factor=None,
    neck_lateral_factor=None,
    neck_flexion_factor=None,
    shoulder_evaluable=True,
    neck_lateral_evaluable=True,
    neck_flexion_evaluable=True,
):
    def feature(factor, evaluable):
        if not evaluable:
            return {
                "valid": False,
                "status": "NOT_EVALUATED",
                "factor": None,
            }

        return {
            "valid": True,
            "status": "EVALUATED",
            "factor": factor,
        }

    return {
        "assessment_contract_version": "1.1",
        "status": "COMPLETE",
        "features": {
            "shoulder_tilt": feature(
                shoulder_factor,
                shoulder_evaluable,
            ),
            "neck_lateral_tilt": feature(
                neck_lateral_factor,
                neck_lateral_evaluable,
            ),
            "neck_flexion": feature(
                neck_flexion_factor,
                neck_flexion_evaluable,
            ),
        },
        "risk": None,
        "alert": None,
    }


def make_temporal(
    *,
    shoulder_factor=None,
    shoulder_seconds=0.0,
    neck_lateral_factor=None,
    neck_lateral_seconds=0.0,
    neck_flexion_factor=None,
    neck_flexion_seconds=0.0,
    shoulder_evaluable=True,
    neck_lateral_evaluable=True,
    neck_flexion_evaluable=True,
):
    def feature(
        factor,
        seconds,
        evaluable,
    ):
        if not evaluable:
            return {
                "state": "NOT_EVALUATED",
                "factor": None,
                "continuous_seconds": None,
            }

        if factor is None:
            return {
                "state": "NEUTRAL",
                "factor": None,
                "continuous_seconds": 0.0,
            }

        return {
            "state": "ACTIVE",
            "factor": factor,
            "continuous_seconds": seconds,
        }

    return {
        "temporal_contract_version": "1.0",
        "status": "COMPLETE",
        "features": {
            "shoulder_tilt": feature(
                shoulder_factor,
                shoulder_seconds,
                shoulder_evaluable,
            ),
            "neck_lateral_tilt": feature(
                neck_lateral_factor,
                neck_lateral_seconds,
                neck_lateral_evaluable,
            ),
            "neck_flexion": feature(
                neck_flexion_factor,
                neck_flexion_seconds,
                neck_flexion_evaluable,
            ),
        },
        "risk": None,
        "alert": None,
    }


class TestRiskEvaluator(unittest.TestCase):

    def test_contract_version(self):

        assessment = make_assessment()
        temporal = make_temporal()

        result = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            result["risk_contract_version"],
            "1.2",
        )

    def test_neutral_is_evaluated(self):
        result = evaluate_risk(
            make_assessment(),
            make_temporal(),
        )

        self.assertEqual(
            result["status"],
            "EVALUATED",
        )

        self.assertEqual(
            result["evidence"]["rula_derived"],
            [],
        )

        self.assertEqual(
            result["evidence"]["postguard_specific"],
            [],
        )

    def test_neck_left_creates_rula_side_bending_evidence(self):
        assessment = make_assessment(
            neck_lateral_factor="TILT_LEFT",
        )

        temporal = make_temporal(
            neck_lateral_factor="TILT_LEFT",
            neck_lateral_seconds=10.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        evidence = result["evidence"]["rula_derived"]

        self.assertTrue(
            any(
                item["type"] == "NECK_SIDE_BENDING"
                for item in evidence
            )
        )

    def test_neck_right_creates_rula_side_bending_evidence(self):
        assessment = make_assessment(
            neck_lateral_factor="TILT_RIGHT",
        )

        temporal = make_temporal(
            neck_lateral_factor="TILT_RIGHT",
            neck_lateral_seconds=10.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        evidence = result["evidence"]["rula_derived"]

        self.assertTrue(
            any(
                item["type"] == "NECK_SIDE_BENDING"
                for item in evidence
            )
        )

    def test_flexion_creates_rula_neck_evidence(self):
        assessment = make_assessment(
            neck_flexion_factor="FLEXION",
        )

        temporal = make_temporal(
            neck_flexion_factor="FLEXION",
            neck_flexion_seconds=20.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        evidence = result["evidence"]["rula_derived"]

        self.assertTrue(
            any(
                item["type"] == "NECK_FLEXION_EXTENSION"
                for item in evidence
            )
        )

    def test_extension_creates_rula_neck_evidence(self):
        assessment = make_assessment(
            neck_flexion_factor="EXTENSION",
        )

        temporal = make_temporal(
            neck_flexion_factor="EXTENSION",
            neck_flexion_seconds=20.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        evidence = result["evidence"]["rula_derived"]

        self.assertTrue(
            any(
                item["type"] == "NECK_FLEXION_EXTENSION"
                for item in evidence
            )
        )

    def test_shoulder_asymmetry_is_postguard_specific(self):
        assessment = make_assessment(
            shoulder_factor="LEFT_SHOULDER_HIGH",
        )

        temporal = make_temporal(
            shoulder_factor="LEFT_SHOULDER_HIGH",
            shoulder_seconds=15.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        evidence = result[
            "evidence"
        ]["postguard_specific"]

        self.assertTrue(
            any(
                item["type"] == "SHOULDER_ASYMMETRY"
                for item in evidence
            )
        )

        shoulder_item = next(
            item
            for item in evidence
            if item["type"] == "SHOULDER_ASYMMETRY"
        )

        self.assertFalse(
            shoulder_item["rula_equivalent"]
        )

    def test_under_60_seconds_no_static_duration(self):
        assessment = make_assessment(
            neck_flexion_factor="FLEXION",
        )

        temporal = make_temporal(
            neck_flexion_factor="FLEXION",
            neck_flexion_seconds=59.9,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        evidence = result["evidence"]["rula_derived"]

        self.assertFalse(
            any(
                item["type"] == "STATIC_DURATION"
                for item in evidence
            )
        )

    def test_exact_60_seconds_static_duration(self):
        assessment = make_assessment(
            neck_flexion_factor="FLEXION",
        )

        temporal = make_temporal(
            neck_flexion_factor="FLEXION",
            neck_flexion_seconds=60.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        evidence = result["evidence"]["temporal"]

        self.assertTrue(
            any(
                item["type"] == "STATIC_DURATION"
                for item in evidence
            )
        )

    def test_over_60_seconds_static_duration(self):
        assessment = make_assessment(
            neck_lateral_factor="TILT_LEFT",
        )

        temporal = make_temporal(
            neck_lateral_factor="TILT_LEFT",
            neck_lateral_seconds=75.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        static_items = [
            item
            for item in result[
                "evidence"
            ]["temporal"]
            if item["type"] == "STATIC_DURATION"
        ]

        self.assertEqual(
            len(static_items),
            1,
        )

        self.assertEqual(
            static_items[0]["feature"],
            "neck_lateral_tilt",
        )

    def test_duration_kept_separate_per_feature(self):
        assessment = make_assessment(
            shoulder_factor="LEFT_SHOULDER_HIGH",
            neck_lateral_factor="TILT_LEFT",
            neck_flexion_factor="FLEXION",
        )

        temporal = make_temporal(
            shoulder_factor="LEFT_SHOULDER_HIGH",
            shoulder_seconds=12.0,
            neck_lateral_factor="TILT_LEFT",
            neck_lateral_seconds=34.0,
            neck_flexion_factor="FLEXION",
            neck_flexion_seconds=56.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        features = result["feature_results"]

        self.assertEqual(
            features["shoulder_tilt"][
                "continuous_seconds"
            ],
            12.0,
        )

        self.assertEqual(
            features["neck_lateral_tilt"][
                "continuous_seconds"
            ],
            34.0,
        )

        self.assertEqual(
            features["neck_flexion"][
                "continuous_seconds"
            ],
            56.0,
        )

    def test_multiple_factors_are_preserved(self):
        assessment = make_assessment(
            shoulder_factor="RIGHT_SHOULDER_HIGH",
            neck_lateral_factor="TILT_LEFT",
            neck_flexion_factor="FLEXION",
        )

        temporal = make_temporal(
            shoulder_factor="RIGHT_SHOULDER_HIGH",
            shoulder_seconds=10.0,
            neck_lateral_factor="TILT_LEFT",
            neck_lateral_seconds=10.0,
            neck_flexion_factor="FLEXION",
            neck_flexion_seconds=10.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            result["feature_results"][
                "shoulder_tilt"
            ]["factor"],
            "RIGHT_SHOULDER_HIGH",
        )

        self.assertEqual(
            result["feature_results"][
                "neck_lateral_tilt"
            ]["factor"],
            "TILT_LEFT",
        )

        self.assertEqual(
            result["feature_results"][
                "neck_flexion"
            ]["factor"],
            "FLEXION",
        )

    def test_geometric_coupling_does_not_auto_sum_score(self):
        assessment = make_assessment(
            shoulder_factor="RIGHT_SHOULDER_HIGH",
            neck_lateral_factor="TILT_LEFT",
        )

        temporal = make_temporal(
            shoulder_factor="RIGHT_SHOULDER_HIGH",
            shoulder_seconds=20.0,
            neck_lateral_factor="TILT_LEFT",
            neck_lateral_seconds=20.0,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertFalse(
            result["interaction_policy"][
                "automatic_score_addition"
            ]
        )

        self.assertIsNone(
            result["risk_score"]
        )

    def test_partial_when_one_feature_not_evaluated(self):
        assessment = make_assessment(
            neck_flexion_evaluable=False,
        )

        temporal = make_temporal(
            neck_flexion_evaluable=False,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            result["status"],
            "PARTIAL",
        )

    def test_not_evaluated_when_all_features_invalid(self):
        assessment = make_assessment(
            shoulder_evaluable=False,
            neck_lateral_evaluable=False,
            neck_flexion_evaluable=False,
        )

        temporal = make_temporal(
            shoulder_evaluable=False,
            neck_lateral_evaluable=False,
            neck_flexion_evaluable=False,
        )

        result = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            result["status"],
            "NOT_EVALUATED",
        )

    def test_invalid_assessment_contract_rejected(self):
        assessment = make_assessment()
        assessment[
            "assessment_contract_version"
        ] = "999"

        with self.assertRaises(
            RiskEvaluationError
        ):
            evaluate_risk(
                assessment,
                make_temporal(),
            )

    def test_invalid_temporal_contract_rejected(self):
        temporal = make_temporal()
        temporal[
            "temporal_contract_version"
        ] = "999"

        with self.assertRaises(
            RiskEvaluationError
        ):
            evaluate_risk(
                make_assessment(),
                temporal,
            )

    def test_inputs_are_not_modified(self):
        assessment = make_assessment(
            neck_lateral_factor="TILT_LEFT",
        )

        temporal = make_temporal(
            neck_lateral_factor="TILT_LEFT",
            neck_lateral_seconds=12.0,
        )

        assessment_before = copy.deepcopy(
            assessment
        )

        temporal_before = copy.deepcopy(
            temporal
        )

        evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            assessment,
            assessment_before,
        )

        self.assertEqual(
            temporal,
            temporal_before,
        )

    def test_full_rula_not_claimed(self):
        result = evaluate_risk(
            make_assessment(
                neck_flexion_factor="FLEXION",
            ),
            make_temporal(
                neck_flexion_factor="FLEXION",
                neck_flexion_seconds=80.0,
            ),
        )

        self.assertFalse(
            result["full_rula"]["supported"]
        )

        self.assertIsNone(
            result["full_rula"]["score"]
        )

    def test_risk_level_generated_in_v12(self):

        result = evaluate_risk(
            make_assessment(
                neck_flexion_factor="FLEXION",
            ),
            make_temporal(
                neck_flexion_factor="FLEXION",
                neck_flexion_seconds=120.0,
            ),
        )

        # v1.2 still does not create numeric risk score.
        self.assertIsNone(
            result["risk_score"]
        )

        # One active group + static duration >= 60 sec.
        self.assertEqual(
            result["risk_level"],
            "MODERATE",
        )

    def test_no_risk_event_or_alert(self):
        result = evaluate_risk(
            make_assessment(
                neck_lateral_factor="TILT_LEFT",
            ),
            make_temporal(
                neck_lateral_factor="TILT_LEFT",
                neck_lateral_seconds=120.0,
            ),
        )

        self.assertIsNone(
            result["risk_event"]
        )

        self.assertIsNone(
            result["alert"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)