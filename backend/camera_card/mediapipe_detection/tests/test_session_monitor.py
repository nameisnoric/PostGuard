import math
import unittest

from camera_card.session_monitoring.session_monitor import (
    build_session_monitoring_snapshot,
)


class TestSessionMonitor(unittest.TestCase):

    def setUp(self):

        self.session = {
            "session_id": 18,
            "user_id": 1,
            "baseline_id": 16,
            "camera_id": 1,
            "status": "RUNNING",
        }

        self.baseline = {
            "baseline_id": 16,
            "user_id": 1,
            "camera_id": 1,

            "shoulder_angle": (
                -1.0953881214607577
            ),

            "lateral_tilt_baseline": (
                -1.6575091171294787
            ),

            "neck_flexion_baseline": (
                -1.990968161957748
            ),

            "eye_distance_baseline_px": (
                115.50432892320529
            ),
        }

        self.detection = {
            "contract_version": "1.0",

            "timestamp": 100.0,

            "context": {
                "state": "VALID",
                "allow_posture_evaluation": True,
                "reason": "stable_upper_body",
            },

            "features": {
                "shoulder_tilt": {
                    "valid": True,
                    "value": 3.2,
                    "unit": "deg",
                    "reason": "OK",
                    "status": (
                        "validated_prototype"
                    ),
                },

                "neck_lateral_tilt": {
                    "valid": True,
                    "value": -2.1,
                    "unit": "deg",
                    "reason": "OK",
                    "status": (
                        "validated_prototype"
                    ),
                },

                "neck_flexion": {
                    "valid": True,
                    "value": 12.0,
                    "unit": "deg",
                    "reason": "OK",
                    "status": (
                        "validated_prototype"
                    ),
                },

                "eye_distance": {
                    "valid": True,
                    "value": 123.8,
                    "unit": "px",
                    "reason": "OK",
                    "status": (
                        "validated_prototype"
                    ),
                },
            },
        }

    # ========================================================
    # Normal Snapshot
    # ========================================================

    def test_builds_all_four_feature_deltas(self):

        result = (
            build_session_monitoring_snapshot(
                session=self.session,
                baseline=self.baseline,
                detection_result=self.detection,
            )
        )

        features = result[
            "features"
        ]

        self.assertAlmostEqual(
            features[
                "shoulder_tilt"
            ][
                "delta"
            ],
            (
                3.2
                -
                self.baseline[
                    "shoulder_angle"
                ]
            ),
        )

        self.assertAlmostEqual(
            features[
                "neck_lateral_tilt"
            ][
                "delta"
            ],
            (
                -2.1
                -
                self.baseline[
                    "lateral_tilt_baseline"
                ]
            ),
        )

        self.assertAlmostEqual(
            features[
                "neck_flexion"
            ][
                "delta"
            ],
            (
                12.0
                -
                self.baseline[
                    "neck_flexion_baseline"
                ]
            ),
        )

        self.assertAlmostEqual(
            features[
                "eye_distance"
            ][
                "delta"
            ],
            (
                123.8
                -
                self.baseline[
                    "eye_distance_baseline_px"
                ]
            ),
        )

    # ========================================================
    # Measurement Validity
    # ========================================================

    def test_valid_context_and_features_are_measurement_valid(
        self
    ):

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                self.detection,
            )
        )

        for row in (
            result[
                "features"
            ].values()
        ):
            self.assertTrue(
                row[
                    "measurement_valid"
                ]
            )

            self.assertTrue(
                row[
                    "baseline_comparison_eligible"
                ]
            )

    # ========================================================
    # No Risk Yet
    # ========================================================

    def test_risk_is_not_implemented(self):

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                self.detection,
            )
        )

        self.assertEqual(
            result[
                "measurement_change_gate_status"
            ],
            "NOT_IMPLEMENTED",
        )

        self.assertEqual(
            result[
                "posture_assessment_status"
            ],
            "NOT_IMPLEMENTED",
        )

        self.assertEqual(
            result[
                "risk_score_status"
            ],
            "NOT_IMPLEMENTED",
        )

        self.assertEqual(
            result[
                "alert_status"
            ],
            "NOT_IMPLEMENTED",
        )

    # ========================================================
    # Context Transition
    # ========================================================

    def test_transition_context_is_observation_only(
        self
    ):

        detection = {
            **self.detection,

            "context": {
                "state": "TRANSITION",
                "allow_posture_evaluation": False,
                "reason": "posture_transition",
            },
        }

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                detection,
            )
        )

        row = result[
            "features"
        ][
            "neck_flexion"
        ]

        # Current/Delta can still exist.
        self.assertAlmostEqual(
            row[
                "current"
            ],
            12.0,
        )

        self.assertIsNotNone(
            row[
                "delta"
            ]
        )

        # But downstream use is blocked.
        self.assertFalse(
            row[
                "measurement_valid"
            ]
        )

        self.assertFalse(
            row[
                "baseline_comparison_eligible"
            ]
        )

        self.assertEqual(
            row[
                "status"
            ],
            "OBSERVATION_ONLY",
        )

    # ========================================================
    # Missing Context
    # ========================================================

    def test_missing_context_is_not_valid(
        self
    ):

        detection = dict(
            self.detection
        )

        detection.pop(
            "context"
        )

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                detection,
            )
        )

        self.assertEqual(
            result[
                "context"
            ][
                "state"
            ],
            "UNKNOWN",
        )

        self.assertFalse(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "measurement_valid"
            ]
        )

    # ========================================================
    # Missing Baseline
    # ========================================================

    def test_missing_baseline_does_not_invalidate_current_measurement(
        self
    ):

        baseline = dict(
            self.baseline
        )

        baseline[
            "eye_distance_baseline_px"
        ] = None

        result = (
            build_session_monitoring_snapshot(
                self.session,
                baseline,
                self.detection,
            )
        )

        row = result[
            "features"
        ][
            "eye_distance"
        ]

        # Current measurement itself is still valid.
        self.assertTrue(
            row[
                "measurement_valid"
            ]
        )

        # But comparison cannot be performed.
        self.assertFalse(
            row[
                "baseline_comparison_eligible"
            ]
        )

        self.assertIsNone(
            row[
                "delta"
            ]
        )

        self.assertEqual(
            row[
                "status"
            ],
            "NOT_EVALUATED",
        )

    # ========================================================
    # Invalid Detection Feature
    # ========================================================

    def test_invalid_feature_is_not_zero(
        self
    ):

        detection = {
            **self.detection,

            "features": {
                **self.detection[
                    "features"
                ],

                "shoulder_tilt": {
                    "valid": False,
                    "value": None,
                    "unit": "deg",
                    "reason": (
                        "LOW_QUALITY_SHOULDER"
                    ),
                    "status": (
                        "validated_prototype"
                    ),
                },
            },
        }

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                detection,
            )
        )

        row = result[
            "features"
        ][
            "shoulder_tilt"
        ]

        self.assertIsNone(
            row[
                "current"
            ]
        )

        self.assertIsNone(
            row[
                "delta"
            ]
        )

        self.assertFalse(
            row[
                "measurement_valid"
            ]
        )

    # ========================================================
    # NaN / Infinity
    # ========================================================

    def test_nan_is_rejected(self):

        detection = {
            **self.detection,

            "features": {
                **self.detection[
                    "features"
                ],

                "neck_flexion": {
                    "valid": True,
                    "value": math.nan,
                    "unit": "deg",
                    "reason": "OK",
                    "status": (
                        "validated_prototype"
                    ),
                },
            },
        }

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                detection,
            )
        )

        row = result[
            "features"
        ][
            "neck_flexion"
        ]

        self.assertIsNone(
            row[
                "current"
            ]
        )

        self.assertIsNone(
            row[
                "delta"
            ]
        )

    def test_infinity_is_rejected(self):

        detection = {
            **self.detection,

            "features": {
                **self.detection[
                    "features"
                ],

                "neck_flexion": {
                    "valid": True,
                    "value": math.inf,
                    "unit": "deg",
                    "reason": "OK",
                    "status": (
                        "validated_prototype"
                    ),
                },
            },
        }

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                detection,
            )
        )

        self.assertIsNone(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "current"
            ]
        )

    # ========================================================
    # Bool Must Not Become Number
    # ========================================================

    def test_bool_is_not_accepted_as_numeric_measurement(
        self
    ):

        detection = {
            **self.detection,

            "features": {
                **self.detection[
                    "features"
                ],

                "neck_flexion": {
                    "valid": True,
                    "value": True,
                    "unit": "deg",
                    "reason": "OK",
                    "status": (
                        "validated_prototype"
                    ),
                },
            },
        }

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                detection,
            )
        )

        self.assertIsNone(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "current"
            ]
        )

    # ========================================================
    # Wrong Baseline
    # ========================================================

    def test_baseline_id_must_match_session(
        self
    ):

        baseline = {
            **self.baseline,
            "baseline_id": 999,
        }

        with self.assertRaisesRegex(
            ValueError,
            "does not match",
        ):
            build_session_monitoring_snapshot(
                self.session,
                baseline,
                self.detection,
            )

    # ========================================================
    # Wrong Camera
    # ========================================================

    def test_camera_id_must_match(
        self
    ):

        baseline = {
            **self.baseline,
            "camera_id": 2,
        }

        with self.assertRaisesRegex(
            ValueError,
            "different cameras",
        ):
            build_session_monitoring_snapshot(
                self.session,
                baseline,
                self.detection,
            )

    # ========================================================
    # Wrong User
    # ========================================================

    def test_user_id_must_match(
        self
    ):

        baseline = {
            **self.baseline,
            "user_id": 2,
        }

        with self.assertRaisesRegex(
            ValueError,
            "different users",
        ):
            build_session_monitoring_snapshot(
                self.session,
                baseline,
                self.detection,
            )

    # ========================================================
    # Session Status
    # ========================================================

    def test_session_must_be_running(
        self
    ):

        session = {
            **self.session,
            "status": "PAUSED",
        }

        with self.assertRaisesRegex(
            ValueError,
            "RUNNING",
        ):
            build_session_monitoring_snapshot(
                session,
                self.baseline,
                self.detection,
            )

    # ========================================================
    # Detection Contract
    # ========================================================

    def test_detection_contract_must_be_1_0(
        self
    ):

        detection = {
            **self.detection,
            "contract_version": "2.0",
        }

        with self.assertRaisesRegex(
            ValueError,
            "contract_version",
        ):
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                detection,
            )

    # ========================================================
    # Candidate Feature
    # ========================================================

    def test_candidate_feature_not_approved_for_core(
        self
    ):

        detection = {
            **self.detection,

            "features": {
                **self.detection[
                    "features"
                ],

                "neck_flexion": {
                    "valid": True,
                    "value": 12.0,
                    "unit": "deg",
                    "reason": "OK",
                    "status": (
                        "candidate_prototype"
                    ),
                },
            },
        }

        result = (
            build_session_monitoring_snapshot(
                self.session,
                self.baseline,
                detection,
            )
        )

        row = result[
            "features"
        ][
            "neck_flexion"
        ]

        self.assertFalse(
            row[
                "measurement_valid"
            ]
        )

        self.assertFalse(
            row[
                "baseline_comparison_eligible"
            ]
        )

        self.assertEqual(
            row[
                "quality_status"
            ],
            "NOT_APPROVED",
        )


if __name__ == "__main__":
    unittest.main()