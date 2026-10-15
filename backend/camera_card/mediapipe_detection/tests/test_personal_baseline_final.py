from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


# ==========================================================
# LOAD REAL PERSONAL BASELINE MODULE
# ==========================================================

TEST_FILE = Path(
    __file__
).resolve()

CAMERA_CARD_DIR = (
    TEST_FILE.parents[2]
)

MODULE_PATH = (
    CAMERA_CARD_DIR
    / "baseline"
    / "personal_baseline.py"
)


if not MODULE_PATH.exists():

    raise FileNotFoundError(
        "Cannot find Personal Baseline module.\n"
        f"Expected: {MODULE_PATH}"
    )


spec = (
    importlib.util
    .spec_from_file_location(
        "personal_baseline_under_test",
        MODULE_PATH,
    )
)


if (
    spec is None
    or
    spec.loader is None
):

    raise ImportError(
        f"Cannot load: {MODULE_PATH}"
    )


pb = (
    importlib.util
    .module_from_spec(
        spec
    )
)

sys.modules[
    spec.name
] = pb

spec.loader.exec_module(
    pb
)


# ==========================================================
# FAKE CLOCK
#
# ทำให้ Unit Test ไม่ต้องรอ 15/30 วินาทีจริง
# ==========================================================

class FakeClock:

    def __init__(
        self,
    ):

        self.value = 0.0

    def __call__(
        self,
    ) -> float:

        return self.value

    def advance(
        self,
        seconds: float,
    ) -> None:

        self.value += float(
            seconds
        )


# ==========================================================
# DETECTION RESULT HELPERS
# ==========================================================

def make_feature(
    value,
    unit,
    *,
    valid=True,
    status="validated_prototype",
    reason="OK",
):

    return {
        "valid": valid,
        "value": value,
        "unit": unit,
        "reason": reason,
        "status": status,
    }


def make_detection_result(
    *,
    shoulder=0.5,
    neck_lateral=0.5,
    neck_flexion=0.5,
    eye_distance=110.0,

    context_state="VALID",
    allow_posture=True,

    timestamp=0.0,

    shoulder_unit="deg",
    shoulder_status="validated_prototype",

    contract_version="1.0",
):

    return {
        "contract_version":
            contract_version,

        "timestamp":
            timestamp,

        "context": {
            "state":
                context_state,

            "allow_posture_evaluation":
                allow_posture,

            "reason":
                "OK",
        },

        "features": {
            "shoulder_tilt":
                make_feature(
                    shoulder,
                    shoulder_unit,
                    status=
                        shoulder_status,
                ),

            "neck_lateral_tilt":
                make_feature(
                    neck_lateral,
                    "deg",
                ),

            "neck_flexion":
                make_feature(
                    neck_flexion,
                    "deg",
                ),

            "eye_distance":
                make_feature(
                    eye_distance,
                    "px",
                ),
        },
    }


# ==========================================================
# UNIT TEST
# ==========================================================

class TestPersonalBaselineFinal(
    unittest.TestCase
):

    # ======================================================
    # HELPERS
    # ======================================================

    def make_collector(
        self,
        **overrides,
    ):

        clock = FakeClock()

        config = (
            pb.PersonalBaselineConfig(
                **overrides
            )
        )

        collector = (
            pb.PersonalBaselineCollector(
                config,
                monotonic_fn=clock,
            )
        )

        return (
            collector,
            clock,
        )

    def feed_valid(
        self,
        collector,
        count,
        **kwargs,
    ):

        result = None

        for _ in range(
            count
        ):

            result = (
                collector
                .add_detection_result(
                    make_detection_result(
                        **kwargs
                    )
                )
            )

        return result

    def technical_pass(
        self,
    ):

        collector, clock = (
            self.make_collector()
        )

        # 59 valid samples
        self.feed_valid(
            collector,
            59,
        )

        self.assertEqual(
            collector.get_status()[
                "status"
            ],
            pb.BASELINE_COLLECTING,
        )

        # เวลาไปถึง 15 sec
        clock.advance(
            15.0
        )

        # Sample ที่ 60
        result = (
            collector
            .add_detection_result(
                make_detection_result()
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_NEED_CONFIRMATION,
        )

        return (
            collector,
            clock,
            result,
        )

    # ======================================================
    # 01 DEFAULT DESIGN
    # ======================================================

    def test_01_default_design(
        self,
    ):

        config = (
            pb.PersonalBaselineConfig()
        )

        self.assertEqual(
            config.target_samples,
            60,
        )

        self.assertEqual(
            config.min_calibration_seconds,
            15.0,
        )

        self.assertEqual(
            config.max_calibration_seconds,
            30.0,
        )

        # Design เก่าต้องไม่มีแล้ว
        self.assertFalse(
            hasattr(
                config,
                "shoulder_confirmation_threshold_deg",
            )
        )

        self.assertFalse(
            hasattr(
                config,
                "max_total_frames",
            )
        )

    # ======================================================
    # 02 60 SAMPLES BUT TIME NOT COMPLETE
    # ======================================================

    def test_02_60_samples_before_15_seconds_still_collecting(
        self,
    ):

        collector, clock = (
            self.make_collector()
        )

        result = (
            self.feed_valid(
                collector,
                60,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_COLLECTING,
        )

        self.assertEqual(
            result[
                "sample_count"
            ],
            60,
        )

        self.assertFalse(
            collector.completed
        )

        self.assertFalse(
            collector
            .is_ready_for_session()
        )

    # ======================================================
    # 03 KEEP COLLECTING AFTER 60
    # ======================================================

    def test_03_collects_beyond_60_until_time_condition(
        self,
    ):

        collector, clock = (
            self.make_collector()
        )

        self.feed_valid(
            collector,
            60,
        )

        clock.advance(
            15.0
        )

        result = (
            collector
            .add_detection_result(
                make_detection_result()
            )
        )

        # ต้องเก็บ Sample ที่ 61 ด้วย
        self.assertEqual(
            result[
                "sample_count"
            ],
            61,
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_NEED_CONFIRMATION,
        )

    # ======================================================
    # 04 PASS -> NEED CONFIRMATION
    # ======================================================

    def test_04_pass_goes_to_confirmation_not_success(
        self,
    ):

        (
            collector,
            clock,
            result,
        ) = self.technical_pass()

        self.assertTrue(
            result[
                "validation"
            ][
                "passed"
            ]
        )

        self.assertTrue(
            result[
                "confirmation"
            ][
                "required"
            ]
        )

        self.assertEqual(
            result[
                "confirmation"
            ][
                "status"
            ],
            pb.CONFIRMATION_PENDING,
        )

        self.assertEqual(
            result[
                "confirmation"
            ][
                "reason"
            ],
            pb.CONFIRMATION_REASON_USER_REVIEW,
        )

        self.assertFalse(
            result[
                "ready_for_session"
            ]
        )

        self.assertIsNone(
            result[
                "usable_baseline"
            ]
        )

    # ======================================================
    # 05 BLOCK USABLE BASELINE BEFORE CONFIRM
    # ======================================================

    def test_05_get_usable_baseline_blocked_before_confirm(
        self,
    ):

        (
            collector,
            _,
            _,
        ) = self.technical_pass()

        with self.assertRaises(
            RuntimeError
        ):

            collector.get_usable_baseline()

    # ======================================================
    # 06 CONFIRM
    # ======================================================

    def test_06_confirm_enables_session(
        self,
    ):

        (
            collector,
            _,
            _,
        ) = self.technical_pass()

        result = (
            collector.confirm()
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_SUCCESS,
        )

        self.assertTrue(
            result[
                "ready_for_session"
            ]
        )

        self.assertEqual(
            result[
                "confirmation"
            ][
                "status"
            ],
            pb.CONFIRMATION_CONFIRMED,
        )

        usable = (
            collector
            .get_usable_baseline()
        )

        self.assertEqual(
            set(usable),
            set(
                pb.REQUIRED_FEATURES
            ),
        )

    # ======================================================
    # 07 REJECT
    # ======================================================

    def test_07_reject_keeps_technical_validation_passed(
        self,
    ):

        (
            collector,
            _,
            _,
        ) = self.technical_pass()

        result = (
            collector.reject()
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_FAILED,
        )

        self.assertEqual(
            result[
                "failure_reason"
            ],
            "USER_REJECTED_BASELINE",
        )

        # Technical Validation ยังผ่าน
        self.assertTrue(
            result[
                "validation"
            ][
                "passed"
            ]
        )

        self.assertEqual(
            result[
                "validation"
            ][
                "issues"
            ],
            [],
        )

        self.assertEqual(
            result[
                "confirmation"
            ][
                "status"
            ],
            pb.CONFIRMATION_REJECTED,
        )

        self.assertFalse(
            result[
                "ready_for_session"
            ]
        )

        self.assertIsNone(
            result[
                "usable_baseline"
            ]
        )

        with self.assertRaises(
            RuntimeError
        ):

            collector.get_usable_baseline()

    # ======================================================
    # 08 USE ALL VALID SAMPLES
    # ======================================================

    def test_08_all_valid_samples_are_used_in_statistics(
        self,
    ):

        collector, clock = (
            self.make_collector(

                max_shoulder_sd_deg=
                    100.0,

                max_neck_lateral_sd_deg=
                    100.0,

                max_neck_flexion_sd_deg=
                    100.0,

                max_eye_distance_sd_px=
                    100.0,
            )
        )

        # 60 samples แรก
        self.feed_valid(
            collector,
            60,
            shoulder=0.0,
        )

        clock.advance(
            15.0
        )

        # Sample ที่ 61
        result = (
            collector
            .add_detection_result(
                make_detection_result(
                    shoulder=6.1
                )
            )
        )

        self.assertEqual(
            result[
                "sample_count"
            ],
            61,
        )

        # Mean ต้องรวม Sample ที่ 61
        self.assertAlmostEqual(
            result[
                "statistics"
            ][
                "shoulder_tilt"
            ][
                "mean"
            ],
            6.1 / 61.0,
            places=7,
        )

    # ======================================================
    # 09 LOW VALID RATIO
    # ======================================================

    def test_09_low_valid_ratio_fails(
        self,
    ):

        collector, clock = (
            self.make_collector()
        )

        self.feed_valid(
            collector,
            60,
        )

        # Reject 40 frames
        for _ in range(
            40
        ):

            collector.add_detection_result(
                make_detection_result(
                    context_state=
                        "TRANSITION",

                    allow_posture=
                        False,
                )
            )

        clock.advance(
            15.0
        )

        # Trigger evaluation
        result = (
            collector
            .add_detection_result(
                make_detection_result(
                    context_state=
                        "TRANSITION",

                    allow_posture=
                        False,
                )
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_FAILED,
        )

        self.assertIn(
            "LOW_VALID_RATIO",

            result[
                "validation"
            ][
                "issues"
            ],
        )

        self.assertIsNone(
            result[
                "usable_baseline"
            ]
        )

    # ======================================================
    # 10 STABILITY FAIL
    # ======================================================

    def test_10_unstable_feature_fails(
        self,
    ):

        collector, clock = (
            self.make_collector(

                target_samples=4,

                min_calibration_seconds=
                    1.0,

                max_calibration_seconds=
                    2.0,
            )
        )

        values = (
            -10.0,
            10.0,
            -10.0,
        )

        for value in values:

            collector.add_detection_result(
                make_detection_result(
                    shoulder=value
                )
            )

        clock.advance(
            1.0
        )

        result = (
            collector
            .add_detection_result(
                make_detection_result(
                    shoulder=10.0
                )
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_FAILED,
        )

        self.assertIn(
            "SHOULDER_TILT_UNSTABLE",

            result[
                "validation"
            ][
                "issues"
            ],
        )

    # ======================================================
    # 11 TIMEOUT
    # ======================================================

    def test_11_timeout_before_collection_requirements(
        self,
    ):

        collector, clock = (
            self.make_collector()
        )

        self.feed_valid(
            collector,
            10,
        )

        clock.advance(
            30.0
        )

        result = (
            collector
            .add_detection_result(
                make_detection_result()
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_FAILED,
        )

        self.assertEqual(
            result[
                "failure_reason"
            ],
            "CALIBRATION_TIMEOUT",
        )

        self.assertEqual(
            result[
                "sample_count"
            ],
            10,
        )

        self.assertIsNone(
            result[
                "usable_baseline"
            ]
        )

    # ======================================================
    # 12 BAD DETECTION RESULT CONTRACT
    # ======================================================

    def test_12_malformed_detection_result_rejected_safely(
        self,
    ):

        collector, _ = (
            self.make_collector()
        )

        result = (
            collector
            .add_detection_result(
                []
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_COLLECTING,
        )

        self.assertEqual(
            result[
                "rejection_reasons"
            ][
                "invalid_detection_result_contract"
            ],
            1,
        )

    # ======================================================
    # 13 BAD CONTEXT CONTRACT
    # ======================================================

    def test_13_malformed_context_rejected_safely(
        self,
    ):

        collector, _ = (
            self.make_collector()
        )

        bad = (
            make_detection_result()
        )

        bad[
            "context"
        ] = []

        result = (
            collector
            .add_detection_result(
                bad
            )
        )

        self.assertEqual(
            result[
                "rejection_reasons"
            ][
                "invalid_context_contract"
            ],
            1,
        )

    # ======================================================
    # 14 BAD FEATURES CONTRACT
    # ======================================================

    def test_14_malformed_features_rejected_safely(
        self,
    ):

        collector, _ = (
            self.make_collector()
        )

        bad = (
            make_detection_result()
        )

        bad[
            "features"
        ] = []

        result = (
            collector
            .add_detection_result(
                bad
            )
        )

        self.assertEqual(
            result[
                "rejection_reasons"
            ][
                "invalid_features_contract"
            ],
            1,
        )

    # ======================================================
    # 15 BAD FEATURE OBJECT
    # ======================================================

    def test_15_malformed_feature_object_rejected_safely(
        self,
    ):

        collector, _ = (
            self.make_collector()
        )

        bad = (
            make_detection_result()
        )

        bad[
            "features"
        ][
            "shoulder_tilt"
        ] = []

        result = (
            collector
            .add_detection_result(
                bad
            )
        )

        self.assertEqual(
            result[
                "rejection_reasons"
            ][
                "shoulder_tilt_invalid_contract"
            ],
            1,
        )

    # ======================================================
    # 16 FEATURE CONTRACT
    # ======================================================

    def test_16_feature_contract_checks(
        self,
    ):

        cases = [
            (
                "wrong unit",

                {
                    "shoulder_unit":
                        "px"
                },

                "shoulder_tilt_invalid_unit_px",
            ),

            (
                "wrong status",

                {
                    "shoulder_status":
                        "candidate"
                },

                "shoulder_tilt_not_validated",
            ),
        ]

        for (
            label,
            kwargs,
            reason,
        ) in cases:

            with self.subTest(
                label=label
            ):

                collector, _ = (
                    self.make_collector()
                )

                result = (
                    collector
                    .add_detection_result(
                        make_detection_result(
                            **kwargs
                        )
                    )
                )

                self.assertEqual(
                    result[
                        "rejection_reasons"
                    ][
                        reason
                    ],
                    1,
                )

        # NaN value
        collector, _ = (
            self.make_collector()
        )

        bad = (
            make_detection_result()
        )

        bad[
            "features"
        ][
            "shoulder_tilt"
        ][
            "value"
        ] = float(
            "nan"
        )

        result = (
            collector
            .add_detection_result(
                bad
            )
        )

        self.assertEqual(
            result[
                "rejection_reasons"
            ][
                "shoulder_tilt_invalid_value"
            ],
            1,
        )

    # ======================================================
    # 17 CONTEXT GATE
    # ======================================================

    def test_17_context_state_and_allow_gate(
        self,
    ):

        collector, _ = (
            self.make_collector()
        )

        result = (
            collector
            .add_detection_result(
                make_detection_result(
                    context_state=
                        "TRANSITION"
                )
            )
        )

        self.assertEqual(
            result[
                "sample_count"
            ],
            0,
        )

        collector, _ = (
            self.make_collector()
        )

        result = (
            collector
            .add_detection_result(
                make_detection_result(
                    allow_posture=
                        False
                )
            )
        )

        self.assertEqual(
            result[
                "sample_count"
            ],
            0,
        )

    # ======================================================
    # 18 ELAPSED VS VALID SAMPLE SPAN
    # ======================================================

    def test_18_elapsed_and_valid_sample_span_are_separate(
        self,
    ):

        collector, clock = (
            self.make_collector(

                target_samples=2,

                minimum_valid_ratio=
                    0.50,

                min_calibration_seconds=
                    15.0,

                max_calibration_seconds=
                    30.0,
            )
        )

        # Start calibration ด้วย rejected frame
        collector.add_detection_result(
            make_detection_result(
                context_state=
                    "TRANSITION"
            )
        )

        # 10 sec แรกไม่มี Valid Sample
        clock.advance(
            10.0
        )

        collector.add_detection_result(
            make_detection_result(
                timestamp=
                    999999.0
            )
        )

        # Valid Sample ตัวที่ 2
        # อยู่ห่างจากตัวแรก 5 sec
        clock.advance(
            5.0
        )

        result = (
            collector
            .add_detection_result(
                make_detection_result(
                    timestamp=
                        -999999.0
                )
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            pb.BASELINE_NEED_CONFIRMATION,
        )

        # Total calibration = 15 sec
        self.assertAlmostEqual(
            result[
                "elapsed_seconds"
            ],
            15.0,
            places=6,
        )

        # Valid samples span = 5 sec
        self.assertAlmostEqual(
            result[
                "valid_sample_span_seconds"
            ],
            5.0,
            places=6,
        )

        # Compatibility field
        self.assertAlmostEqual(
            result[
                "duration_seconds"
            ],
            5.0,
            places=6,
        )

    # ======================================================
    # 19 DEEP COPY
    # ======================================================

    def test_19_result_is_deep_copied(
        self,
    ):

        (
            collector,
            _,
            _,
        ) = self.technical_pass()

        collector.confirm()

        original = (
            collector
            .get_usable_baseline()
            [
                "shoulder_tilt"
            ]
        )

        external = (
            collector
            .get_result()
        )

        external[
            "usable_baseline"
        ][
            "shoulder_tilt"
        ] = 999.0

        external[
            "statistics"
        ][
            "shoulder_tilt"
        ][
            "median"
        ] = 888.0

        external[
            "validation"
        ][
            "issues"
        ].append(
            "EXTERNAL_MUTATION"
        )

        fresh = (
            collector
            .get_result()
        )

        self.assertAlmostEqual(
            fresh[
                "usable_baseline"
            ][
                "shoulder_tilt"
            ],
            original,
        )

        self.assertNotEqual(
            fresh[
                "statistics"
            ][
                "shoulder_tilt"
            ][
                "median"
            ],
            888.0,
        )

        self.assertNotIn(
            "EXTERNAL_MUTATION",

            fresh[
                "validation"
            ][
                "issues"
            ],
        )

    # ======================================================
    # 20 CONFIG VALIDATION
    # ======================================================

    def test_20_config_rejects_invalid_values(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            pb.PersonalBaselineConfig(
                target_samples=1
            )

        with self.assertRaises(
            ValueError
        ):

            pb.PersonalBaselineConfig(
                target_samples=True
            )

        with self.assertRaises(
            ValueError
        ):

            pb.PersonalBaselineConfig(
                minimum_valid_ratio=
                    float("nan")
            )

        with self.assertRaises(
            ValueError
        ):

            pb.PersonalBaselineConfig(
                max_calibration_seconds=
                    float("inf")
            )

        with self.assertRaises(
            ValueError
        ):

            pb.PersonalBaselineConfig(
                min_calibration_seconds=
                    15,

                max_calibration_seconds=
                    15,
            )

        with self.assertRaises(
            ValueError
        ):

            pb.PersonalBaselineConfig(
                max_shoulder_sd_deg=
                    -1
            )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    print()

    print(
        "=" * 70
    )

    print(
        "POSTGUARD - FINAL PERSONAL BASELINE UNIT TEST V2"
    )

    print(
        "Testing module:"
    )

    print(
        MODULE_PATH
    )

    print(
        "=" * 70
    )

    print()

    unittest.main(
        verbosity=2
    )