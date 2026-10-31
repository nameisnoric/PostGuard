import math
import unittest

from app.vision.mediapipe_detection.posture.screen_distance_policy import (
    ScreenDistancePolicy,
    ScreenDistancePolicyConfig,
    STATE_NORMAL,
    STATE_TOO_CLOSE,
    STATE_PENDING,
    STATE_NOT_EVALUATED,
    calculate_screen_distance_ratio,
)


class TestScreenDistanceRatio(unittest.TestCase):

    def test_baseline_ratio_is_one(self):
        self.assertAlmostEqual(
            calculate_screen_distance_ratio(
                100.0,
                100.0,
            ),
            1.0,
        )

    def test_closer_ratio_is_above_one(self):
        self.assertAlmostEqual(
            calculate_screen_distance_ratio(
                125.0,
                100.0,
            ),
            1.25,
        )

    def test_invalid_current_returns_none(self):
        for value in (
            None,
            0,
            -1,
            float("nan"),
            float("inf"),
            True,
        ):
            with self.subTest(value=value):
                self.assertIsNone(
                    calculate_screen_distance_ratio(
                        value,
                        100.0,
                    )
                )

    def test_invalid_baseline_returns_none(self):
        for value in (
            None,
            0,
            -1,
            float("nan"),
            float("inf"),
            True,
        ):
            with self.subTest(value=value):
                self.assertIsNone(
                    calculate_screen_distance_ratio(
                        100.0,
                        value,
                    )
                )


class TestScreenDistancePolicy(unittest.TestCase):

    def make_policy(self):
        return ScreenDistancePolicy(
            ScreenDistancePolicyConfig(
                enter_ratio=1.25,
                exit_ratio=1.15,
                confirmation_seconds=3.0,
            )
        )

    def test_normal_below_enter_threshold(self):
        policy = self.make_policy()

        result = policy.update(
            current_eye_distance_px=110.0,
            baseline_eye_distance_px=100.0,
            now=0.0,
        )

        self.assertTrue(
            result["evaluated"]
        )

        self.assertEqual(
            result["state"],
            STATE_NORMAL,
        )

        self.assertEqual(
            result["stable_state"],
            STATE_NORMAL,
        )

    def test_enter_threshold_starts_pending(self):
        policy = self.make_policy()

        result = policy.update(
            125.0,
            100.0,
            0.0,
        )

        self.assertEqual(
            result["state"],
            STATE_PENDING,
        )

        self.assertEqual(
            result["stable_state"],
            STATE_NORMAL,
        )

        self.assertAlmostEqual(
            result["candidate_seconds"],
            0.0,
        )

    def test_sustained_ratio_becomes_too_close(self):
        policy = self.make_policy()

        policy.update(
            130.0,
            100.0,
            0.0,
        )

        middle = policy.update(
            130.0,
            100.0,
            2.0,
        )

        self.assertEqual(
            middle["state"],
            STATE_PENDING,
        )

        result = policy.update(
            130.0,
            100.0,
            3.0,
        )

        self.assertEqual(
            result["state"],
            STATE_TOO_CLOSE,
        )

        self.assertEqual(
            result["stable_state"],
            STATE_TOO_CLOSE,
        )

    def test_short_spike_does_not_become_too_close(self):
        policy = self.make_policy()

        policy.update(
            130.0,
            100.0,
            0.0,
        )

        result = policy.update(
            110.0,
            100.0,
            1.0,
        )

        self.assertEqual(
            result["state"],
            STATE_NORMAL,
        )

        self.assertEqual(
            policy.state,
            STATE_NORMAL,
        )

    def test_interrupted_candidate_restarts_timer(self):
        policy = self.make_policy()

        policy.update(
            130.0,
            100.0,
            0.0,
        )

        policy.update(
            110.0,
            100.0,
            2.0,
        )

        result = policy.update(
            130.0,
            100.0,
            3.0,
        )

        self.assertEqual(
            result["state"],
            STATE_PENDING,
        )

        self.assertAlmostEqual(
            result["candidate_seconds"],
            0.0,
        )

    def test_hysteresis_keeps_too_close_above_exit_ratio(self):
        policy = self.make_policy()

        policy.update(
            130.0,
            100.0,
            0.0,
        )

        policy.update(
            130.0,
            100.0,
            3.0,
        )

        result = policy.update(
            120.0,
            100.0,
            4.0,
        )

        self.assertEqual(
            result["state"],
            STATE_TOO_CLOSE,
        )

    def test_hysteresis_recovers_at_exit_ratio(self):
        policy = self.make_policy()

        policy.update(
            130.0,
            100.0,
            0.0,
        )

        policy.update(
            130.0,
            100.0,
            3.0,
        )

        result = policy.update(
            115.0,
            100.0,
            4.0,
        )

        self.assertEqual(
            result["state"],
            STATE_NORMAL,
        )

        self.assertEqual(
            result["reason"],
            "RECOVERED_BELOW_EXIT_RATIO",
        )

    def test_missing_measurement_is_not_evaluated_not_normal(self):
        policy = self.make_policy()

        result = policy.update(
            None,
            100.0,
            0.0,
        )

        self.assertFalse(
            result["evaluated"]
        )

        self.assertEqual(
            result["state"],
            STATE_NOT_EVALUATED,
        )

    def test_missing_baseline_is_not_evaluated(self):
        policy = self.make_policy()

        result = policy.update(
            130.0,
            None,
            0.0,
        )

        self.assertEqual(
            result["state"],
            STATE_NOT_EVALUATED,
        )

        self.assertEqual(
            result["reason"],
            "BASELINE_EYE_DISTANCE_INVALID",
        )

    def test_data_gap_does_not_fake_recovery(self):
        policy = self.make_policy()

        policy.update(
            130.0,
            100.0,
            0.0,
        )

        policy.update(
            130.0,
            100.0,
            3.0,
        )

        gap = policy.update(
            None,
            100.0,
            4.0,
        )

        self.assertEqual(
            gap["state"],
            STATE_NOT_EVALUATED,
        )

        self.assertEqual(
            gap["stable_state"],
            STATE_TOO_CLOSE,
        )

        after_gap = policy.update(
            120.0,
            100.0,
            5.0,
        )

        self.assertEqual(
            after_gap["state"],
            STATE_TOO_CLOSE,
        )

    def test_gap_breaks_pending_confirmation(self):
        policy = self.make_policy()

        policy.update(
            130.0,
            100.0,
            0.0,
        )

        gap = policy.update(
            None,
            100.0,
            2.0,
        )

        self.assertEqual(
            gap["state"],
            STATE_NOT_EVALUATED,
        )

        result = policy.update(
            130.0,
            100.0,
            3.0,
        )

        self.assertEqual(
            result["state"],
            STATE_PENDING,
        )

        self.assertAlmostEqual(
            result["candidate_seconds"],
            0.0,
        )

    def test_reset_clears_runtime_state(self):
        policy = self.make_policy()

        policy.update(
            130.0,
            100.0,
            0.0,
        )

        policy.update(
            130.0,
            100.0,
            3.0,
        )

        self.assertEqual(
            policy.state,
            STATE_TOO_CLOSE,
        )

        policy.reset()

        self.assertEqual(
            policy.state,
            STATE_NORMAL,
        )

    def test_timestamp_cannot_move_backwards(self):
        policy = self.make_policy()

        policy.update(
            100.0,
            100.0,
            10.0,
        )

        with self.assertRaises(
            ValueError
        ):
            policy.update(
                100.0,
                100.0,
                9.0,
            )

    def test_contract_marks_threshold_as_candidate(self):
        policy = self.make_policy()

        result = policy.update(
            100.0,
            100.0,
            0.0,
        )

        self.assertEqual(
            result["threshold_status"],
            "candidate_policy",
        )

        self.assertEqual(
            result["enter_ratio"],
            1.25,
        )

        self.assertEqual(
            result["exit_ratio"],
            1.15,
        )

        self.assertEqual(
            result["confirmation_seconds"],
            3.0,
        )


class TestScreenDistancePolicyConfig(unittest.TestCase):

    def test_exit_must_be_lower_than_enter(self):
        with self.assertRaises(
            ValueError
        ):
            ScreenDistancePolicy(
                ScreenDistancePolicyConfig(
                    enter_ratio=1.25,
                    exit_ratio=1.25,
                    confirmation_seconds=3.0,
                )
            )

    def test_enter_must_be_above_one(self):
        with self.assertRaises(
            ValueError
        ):
            ScreenDistancePolicy(
                ScreenDistancePolicyConfig(
                    enter_ratio=1.0,
                    exit_ratio=0.9,
                    confirmation_seconds=3.0,
                )
            )

    def test_confirmation_cannot_be_negative(self):
        with self.assertRaises(
            ValueError
        ):
            ScreenDistancePolicy(
                ScreenDistancePolicyConfig(
                    enter_ratio=1.25,
                    exit_ratio=1.15,
                    confirmation_seconds=-1.0,
                )
            )


if __name__ == "__main__":
    unittest.main()