from __future__ import annotations

import copy
import unittest

from camera_card.risk_evaluation import (
    evaluate_risk,
)


def assessment_feature(
    factor=None,
    *,
    valid=True,
):
    if not valid:
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


def temporal_feature(
    factor=None,
    *,
    state=None,
    seconds=0.0,
):
    if state is None:
        state = (
            "ACTIVE"
            if factor is not None
            else "NEUTRAL"
        )

    if state == "NOT_EVALUATED":
        return {
            "state": "NOT_EVALUATED",
            "factor": None,
            "continuous_seconds": None,
        }

    return {
        "state": state,
        "factor": factor,
        "continuous_seconds": seconds,
    }


def make_assessment(
    shoulder=None,
    lateral=None,
    flexion=None,
    *,
    shoulder_valid=True,
    lateral_valid=True,
    flexion_valid=True,
):
    return {
        "assessment_contract_version": "1.1",

        "features": {
            "shoulder_tilt":
                assessment_feature(
                    shoulder,
                    valid=shoulder_valid,
                ),

            "neck_lateral_tilt":
                assessment_feature(
                    lateral,
                    valid=lateral_valid,
                ),

            "neck_flexion":
                assessment_feature(
                    flexion,
                    valid=flexion_valid,
                ),
        },
    }


def make_temporal(
    shoulder=None,
    lateral=None,
    flexion=None,
    *,
    shoulder_state=None,
    lateral_state=None,
    flexion_state=None,
    shoulder_seconds=0.0,
    lateral_seconds=0.0,
    flexion_seconds=0.0,
):
    return {
        "temporal_contract_version": "1.0",

        "features": {
            "shoulder_tilt":
                temporal_feature(
                    shoulder,
                    state=shoulder_state,
                    seconds=shoulder_seconds,
                ),

            "neck_lateral_tilt":
                temporal_feature(
                    lateral,
                    state=lateral_state,
                    seconds=lateral_seconds,
                ),

            "neck_flexion":
                temporal_feature(
                    flexion,
                    state=flexion_state,
                    seconds=flexion_seconds,
                ),
        },
    }


class TestRiskEvaluatorContractV11(
    unittest.TestCase
):

    # ========================================================
    # CONTRACT UPGRADE
    # ========================================================

    def test_contract_upgraded_to_v12_without_breaking_v11_evidence(
        self,
    ):
        result = evaluate_risk(
            make_assessment(),
            make_temporal(),
        )

        self.assertEqual(
            result["risk_contract_version"],
            "1.2",
        )

    # ========================================================
    # COMPLETE / NEUTRAL
    # ========================================================

    def test_all_neutral_ready(self):
        result = evaluate_risk(
            make_assessment(),
            make_temporal(),
        )

        self.assertEqual(
            result["status"],
            "EVALUATED",
        )

        self.assertTrue(
            result["risk_level_available"]
        )

        self.assertEqual(
            result["risk_level"],
            "NONE",
        )

    # ========================================================
    # MATCHING ACTIVE FACTOR
    # ========================================================

    def test_matching_active_factor_ready(self):
        result = evaluate_risk(
            make_assessment(
                lateral="TILT_LEFT"
            ),
            make_temporal(
                lateral="TILT_LEFT",
                lateral_seconds=12.0,
            ),
        )

        feature = result[
            "feature_results"
        ]["neck_lateral_tilt"]

        self.assertEqual(
            feature[
                "consistency"
            ]["status"],
            "READY",
        )

        self.assertEqual(
            feature[
                "continuous_seconds"
            ],
            12.0,
        )

    # ========================================================
    # FACTOR MISMATCH
    # ========================================================

    def test_opposite_factor_is_mismatch(self):
        result = evaluate_risk(
            make_assessment(
                lateral="TILT_LEFT"
            ),
            make_temporal(
                lateral="TILT_RIGHT",
                lateral_seconds=30.0,
            ),
        )

        feature = result[
            "feature_results"
        ]["neck_lateral_tilt"]

        self.assertEqual(
            feature[
                "consistency"
            ]["status"],
            "FACTOR_MISMATCH",
        )

        self.assertIsNone(
            feature[
                "continuous_seconds"
            ]
        )

        self.assertEqual(
            result["status"],
            "PARTIAL",
        )

        self.assertFalse(
            result[
                "risk_level_available"
            ]
        )

    # ========================================================
    # NEUTRAL ASSESSMENT / ACTIVE TEMPORAL
    # ========================================================

    def test_neutral_assessment_active_temporal_mismatch(self):
        result = evaluate_risk(
            make_assessment(),
            make_temporal(
                lateral="TILT_LEFT",
                lateral_seconds=20.0,
            ),
        )

        feature = result[
            "feature_results"
        ]["neck_lateral_tilt"]

        self.assertEqual(
            feature[
                "consistency"
            ]["status"],
            "FACTOR_MISMATCH",
        )

    # ========================================================
    # ACTIVE ASSESSMENT / NEUTRAL TEMPORAL
    # ========================================================

    def test_active_assessment_neutral_temporal_mismatch(self):
        result = evaluate_risk(
            make_assessment(
                flexion="FLEXION"
            ),
            make_temporal(
                flexion=None,
                flexion_state="NEUTRAL",
            ),
        )

        feature = result[
            "feature_results"
        ]["neck_flexion"]

        self.assertEqual(
            feature[
                "consistency"
            ]["status"],
            "FACTOR_MISMATCH",
        )

    # ========================================================
    # TEMPORAL NOT EVALUATED
    # ========================================================

    def test_temporal_not_evaluated_unavailable(self):
        result = evaluate_risk(
            make_assessment(
                lateral="TILT_LEFT"
            ),
            make_temporal(
                lateral_state="NOT_EVALUATED",
            ),
        )

        feature = result[
            "feature_results"
        ]["neck_lateral_tilt"]

        self.assertEqual(
            feature[
                "consistency"
            ]["status"],
            "TEMPORAL_UNAVAILABLE",
        )

        self.assertIsNone(
            feature[
                "continuous_seconds"
            ]
        )

    # ========================================================
    # ASSESSMENT NOT EVALUATED
    # ========================================================

    def test_assessment_not_evaluated(self):
        result = evaluate_risk(
            make_assessment(
                lateral_valid=False
            ),
            make_temporal(
                lateral_state="NOT_EVALUATED"
            ),
        )

        feature = result[
            "feature_results"
        ]["neck_lateral_tilt"]

        self.assertEqual(
            feature[
                "consistency"
            ]["status"],
            "ASSESSMENT_NOT_EVALUATED",
        )

        self.assertEqual(
            result["status"],
            "PARTIAL",
        )

    # ========================================================
    # ALL INVALID
    # ========================================================

    def test_all_assessment_invalid_not_evaluated(self):
        result = evaluate_risk(
            make_assessment(
                shoulder_valid=False,
                lateral_valid=False,
                flexion_valid=False,
            ),
            make_temporal(
                shoulder_state="NOT_EVALUATED",
                lateral_state="NOT_EVALUATED",
                flexion_state="NOT_EVALUATED",
            ),
        )

        self.assertEqual(
            result["status"],
            "NOT_EVALUATED",
        )

        self.assertFalse(
            result[
                "risk_level_available"
            ]
        )

        self.assertIsNone(
            result["risk_level"]
        )

    # ========================================================
    # PARTIAL MUST NOT BECOME NONE
    # ========================================================

    def test_partial_neutral_is_not_none_risk(self):
        result = evaluate_risk(
            make_assessment(
                lateral_valid=False,
                flexion_valid=False,
            ),
            make_temporal(
                lateral_state="NOT_EVALUATED",
                flexion_state="NOT_EVALUATED",
            ),
        )

        self.assertEqual(
            result["status"],
            "PARTIAL",
        )

        self.assertIsNone(
            result["risk_level"]
        )

        self.assertFalse(
            result[
                "risk_level_available"
            ]
        )

    # ========================================================
    # LATERAL GROUP - SHOULDER
    # ========================================================

    def test_lateral_group_contains_shoulder(self):
        result = evaluate_risk(
            make_assessment(
                shoulder="LEFT_SHOULDER_HIGH"
            ),
            make_temporal(
                shoulder="LEFT_SHOULDER_HIGH",
                shoulder_seconds=10.0,
            ),
        )

        group = result[
            "evidence_groups"
        ]["LATERAL_ASYMMETRY"]

        self.assertTrue(
            group["active"]
        )

        self.assertIn(
            "shoulder_tilt",
            group["active_features"],
        )

    # ========================================================
    # LATERAL GROUP - NECK
    # ========================================================

    def test_lateral_group_contains_neck_lateral(self):
        result = evaluate_risk(
            make_assessment(
                lateral="TILT_LEFT"
            ),
            make_temporal(
                lateral="TILT_LEFT",
                lateral_seconds=10.0,
            ),
        )

        group = result[
            "evidence_groups"
        ]["LATERAL_ASYMMETRY"]

        self.assertIn(
            "neck_lateral_tilt",
            group["active_features"],
        )

    # ========================================================
    # SAGITTAL GROUP
    # ========================================================

    def test_sagittal_group_contains_flexion(self):
        result = evaluate_risk(
            make_assessment(
                flexion="FLEXION"
            ),
            make_temporal(
                flexion="FLEXION",
                flexion_seconds=10.0,
            ),
        )

        group = result[
            "evidence_groups"
        ]["NECK_SAGITTAL"]

        self.assertTrue(
            group["active"]
        )

        self.assertIn(
            "neck_flexion",
            group["active_features"],
        )

    # ========================================================
    # COUPLED FEATURES STAY ONE GROUP
    # ========================================================

    def test_coupled_features_remain_same_group(self):
        result = evaluate_risk(
            make_assessment(
                shoulder="RIGHT_SHOULDER_HIGH",
                lateral="TILT_LEFT",
            ),
            make_temporal(
                shoulder="RIGHT_SHOULDER_HIGH",
                lateral="TILT_LEFT",
                shoulder_seconds=20.0,
                lateral_seconds=20.0,
            ),
        )

        group = result[
            "evidence_groups"
        ]["LATERAL_ASYMMETRY"]

        self.assertEqual(
            len(
                group["active_features"]
            ),
            2,
        )

        self.assertFalse(
            result[
                "interaction_policy"
            ][
                "automatic_score_addition"
            ]
        )

        self.assertEqual(
            result[
                "risk_level_mapping"
            ][
                "active_group_count"
            ],
            1,
        )

    # ========================================================
    # DURATION BELOW 60
    # ========================================================

    def test_duration_below_60_not_static(self):
        result = evaluate_risk(
            make_assessment(
                flexion="FLEXION"
            ),
            make_temporal(
                flexion="FLEXION",
                flexion_seconds=59.9,
            ),
        )

        evidence = result[
            "evidence"
        ]["temporal"]

        self.assertEqual(
            evidence,
            [],
        )

        self.assertEqual(
            result["risk_level"],
            "LOW",
        )

    # ========================================================
    # EXACT 60
    # ========================================================

    def test_duration_60_creates_temporal_evidence(self):
        result = evaluate_risk(
            make_assessment(
                flexion="FLEXION"
            ),
            make_temporal(
                flexion="FLEXION",
                flexion_seconds=60.0,
            ),
        )

        evidence = result[
            "evidence"
        ]["temporal"]

        self.assertEqual(
            len(evidence),
            1,
        )

        self.assertEqual(
            evidence[0]["type"],
            "STATIC_DURATION",
        )

        self.assertEqual(
            evidence[0]["source"],
            "POSTGUARD_TEMPORAL_PROTOTYPE",
        )

        self.assertEqual(
            result["risk_level"],
            "MODERATE",
        )

    # ========================================================
    # MISMATCH DURATION CANNOT COUNT
    # ========================================================

    def test_mismatch_duration_cannot_create_static_evidence(self):
        result = evaluate_risk(
            make_assessment(
                flexion="FLEXION"
            ),
            make_temporal(
                flexion="EXTENSION",
                flexion_seconds=120.0,
            ),
        )

        evidence = result[
            "evidence"
        ]["temporal"]

        self.assertEqual(
            evidence,
            [],
        )

        self.assertIsNone(
            result["risk_level"]
        )

    # ========================================================
    # FULL RULA STILL UNSUPPORTED
    # ========================================================

    def test_no_full_rula_score(self):
        result = evaluate_risk(
            make_assessment(
                flexion="FLEXION"
            ),
            make_temporal(
                flexion="FLEXION",
                flexion_seconds=120.0,
            ),
        )

        self.assertFalse(
            result["full_rula"]["supported"]
        )

        self.assertIsNone(
            result["full_rula"]["score"]
        )

        self.assertIsNone(
            result["full_rula"]["action_level"]
        )

    # ========================================================
    # V1.2 MAPPING ENABLED
    # ========================================================

    def test_v12_risk_level_mapping_enabled(self):
        result = evaluate_risk(
            make_assessment(
                flexion="FLEXION"
            ),
            make_temporal(
                flexion="FLEXION",
                flexion_seconds=120.0,
            ),
        )

        self.assertTrue(
            result[
                "risk_level_mapping_enabled"
            ]
        )

        self.assertTrue(
            result[
                "risk_level_available"
            ]
        )

        self.assertEqual(
            result["risk_level"],
            "MODERATE",
        )

    # ========================================================
    # NO RISK EVENT / ALERT YET
    # ========================================================

    def test_no_risk_event_or_alert(self):
        result = evaluate_risk(
            make_assessment(),
            make_temporal(),
        )

        self.assertIsNone(
            result["risk_event"]
        )

        self.assertIsNone(
            result["alert"]
        )

    # ========================================================
    # INPUT IMMUTABILITY
    # ========================================================

    def test_inputs_not_modified(self):
        assessment = make_assessment(
            lateral="TILT_LEFT"
        )

        temporal = make_temporal(
            lateral="TILT_LEFT",
            lateral_seconds=15.0,
        )

        assessment_before = (
            copy.deepcopy(
                assessment
            )
        )

        temporal_before = (
            copy.deepcopy(
                temporal
            )
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


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )