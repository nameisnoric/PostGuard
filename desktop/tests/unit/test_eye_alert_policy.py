import unittest

from app.services.eye_alert_policy import (
    ALERT_FIRST,
    ALERT_REPEAT,
    STATE_DATA_GAP,
    STATE_LOW_BLINK,
    STATE_NORMAL,
    STATE_NOT_EVALUATED,
    STATE_PENDING_LOW_BLINK,
    STATE_WARMUP,
    EyeAlertPolicy,
    EyeAlertPolicyConfig,
)


def make_blink_result(
    *,
    calibrated=True,
    eye_state="OPEN",
    blink_event=False,
):
    return {
        "calibrated": calibrated,
        "eye_state": eye_state,
        "blink_event": blink_event,
    }


class EyeAlertPolicyTests(
    unittest.TestCase
):

    def setUp(self):
        # ใช้ค่าที่สั้นลงเพื่อให้ Unit Test
        # ไม่ต้องจำลองเวลานาน 10 นาทีจริง
        self.config = EyeAlertPolicyConfig(
            window_seconds=10.0,
            minimum_valid_seconds=5.0,
            low_blink_rate_per_minute=8.0,
            recovery_blink_rate_per_minute=10.0,
            confirmation_seconds=2.0,
            repeat_cooldown_seconds=5.0,
            maximum_sample_gap_seconds=2.0,
        )

        self.policy = EyeAlertPolicy(
            self.config
        )

    # ========================================================
    # HELPERS
    # ========================================================

    def feed_valid_samples(
        self,
        *,
        start: float,
        end: float,
        step: float = 1.0,
        blink_times: set[float] | None = None,
    ):
        """
        Feed calibrated OPEN samples.

        blink_times:
            timestamps ที่ต้องการให้ blink_event=True
        """

        blink_times = blink_times or set()

        t = float(start)

        result = None

        while t <= end:

            result = self.policy.update(
                make_blink_result(
                    calibrated=True,
                    eye_state="OPEN",
                    blink_event=(
                        t in blink_times
                    ),
                ),
                now=t,
            )

            t += step

        return result

    # ========================================================
    # INITIAL / CALIBRATION
    # ========================================================

    def test_calibration_not_ready_is_not_evaluated(
        self,
    ):
        result = self.policy.update(
            make_blink_result(
                calibrated=False,
            ),
            now=1.0,
        )

        self.assertEqual(
            result["state"],
            STATE_NOT_EVALUATED,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["reason"],
            "BLINK_CALIBRATION_NOT_READY",
        )

    # ========================================================
    # WARMUP
    # ========================================================

    def test_warmup_before_minimum_observation_time(
        self,
    ):
        result = self.feed_valid_samples(
            start=0.0,
            end=4.0,
        )

        self.assertEqual(
            result["state"],
            STATE_WARMUP,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertLess(
            result["valid_observation_seconds"],
            self.config.minimum_valid_seconds,
        )

    # ========================================================
    # NORMAL
    # ========================================================

    def test_normal_blink_rate_does_not_notify(
        self,
    ):
        # 5 blinks in 5 seconds
        # rate สูงกว่า threshold แน่นอน
        result = self.feed_valid_samples(
            start=0.0,
            end=5.0,
            blink_times={
                1.0,
                2.0,
                3.0,
                4.0,
                5.0,
            },
        )

        self.assertEqual(
            result["state"],
            STATE_NORMAL,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertIsNone(
            result["alert_type"]
        )

    # ========================================================
    # LOW BLINK PENDING
    # ========================================================

    def test_low_blink_enters_pending_before_first_alert(
        self,
    ):
        result = self.feed_valid_samples(
            start=0.0,
            end=5.0,
        )

        self.assertEqual(
            result["state"],
            STATE_PENDING_LOW_BLINK,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["reason"],
            "LOW_BLINK_CONFIRMATION_STARTED",
        )

    # ========================================================
    # FIRST ALERT
    # ========================================================

    def test_low_blink_after_confirmation_generates_first_alert(
        self,
    ):
        # Build enough window first.
        self.feed_valid_samples(
            start=0.0,
            end=5.0,
        )

        # Pending started at 5.0
        result = self.policy.update(
            make_blink_result(),
            now=7.0,
        )

        self.assertEqual(
            result["state"],
            STATE_LOW_BLINK,
        )

        self.assertTrue(
            result["should_notify"]
        )

        self.assertEqual(
            result["alert_type"],
            ALERT_FIRST,
        )

        self.assertEqual(
            result["reason"],
            "LOW_BLINK_CONFIRMED",
        )

        self.assertTrue(
            result["low_blink_active"]
        )

        self.assertEqual(
            result["alert_count"],
            1,
        )

    # ========================================================
    # REPEAT COOLDOWN
    # ========================================================

    def test_repeat_does_not_fire_before_cooldown(
        self,
    ):
        # Build valid window.
        self.feed_valid_samples(
            start=0.0,
            end=5.0,
        )

        # Pending starts at 5.0.
        # Keep samples continuous until FIRST at 7.0.
        self.policy.update(
            make_blink_result(),
            now=6.0,
        )

        first = self.policy.update(
            make_blink_result(),
            now=7.0,
        )

        self.assertTrue(
            first["should_notify"]
        )

        self.assertEqual(
            first["alert_type"],
            ALERT_FIRST,
        )

        # Runtime continues receiving samples.
        self.policy.update(
            make_blink_result(),
            now=8.0,
        )

        self.policy.update(
            make_blink_result(),
            now=9.0,
        )

        result = self.policy.update(
            make_blink_result(),
            now=10.0,
        )

        self.assertEqual(
            result["state"],
            STATE_LOW_BLINK,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["reason"],
            "LOW_BLINK_REPEAT_COOLDOWN",
        )

        self.assertEqual(
            result["alert_count"],
            1,
        )

    def test_repeat_fires_once_when_cooldown_expires(
        self,
    ):
        self.feed_valid_samples(
            start=0.0,
            end=5.0,
        )

        self.policy.update(
            make_blink_result(),
            now=6.0,
        )

        first = self.policy.update(
            make_blink_result(),
            now=7.0,
        )

        self.assertTrue(
            first["should_notify"]
        )

        self.assertEqual(
            first["alert_type"],
            ALERT_FIRST,
        )

        # Keep eye observations continuous.
        self.policy.update(
            make_blink_result(),
            now=8.0,
        )

        self.policy.update(
            make_blink_result(),
            now=9.0,
        )

        self.policy.update(
            make_blink_result(),
            now=10.0,
        )

        self.policy.update(
            make_blink_result(),
            now=11.0,
        )

        # Cooldown = 5 sec.
        # FIRST at 7.0 -> REPEAT due at 12.0.
        repeat = self.policy.update(
            make_blink_result(),
            now=12.0,
        )

        self.assertTrue(
            repeat["should_notify"]
        )

        self.assertEqual(
            repeat["alert_type"],
            ALERT_REPEAT,
        )

        self.assertEqual(
            repeat["reason"],
            "LOW_BLINK_REPEAT_READY",
        )

        self.assertEqual(
            repeat["alert_count"],
            2,
        )

        # Immediately after REPEAT:
        # must NOT notify again.
        after_repeat = self.policy.update(
            make_blink_result(),
            now=12.1,
        )

        self.assertFalse(
            after_repeat["should_notify"]
        )

        self.assertEqual(
            after_repeat["reason"],
            "LOW_BLINK_REPEAT_COOLDOWN",
        )

        self.assertEqual(
            after_repeat["alert_count"],
            2,
        )

    # ========================================================
    # RECOVERY
    # ========================================================

    def test_low_blink_recovers_when_rate_reaches_recovery_threshold(
        self,
    ):
        # Trigger FIRST low-blink alert.
        self.feed_valid_samples(
            start=0.0,
            end=5.0,
        )

        self.policy.update(
            make_blink_result(),
            now=6.0,
        )

        first = self.policy.update(
            make_blink_result(),
            now=7.0,
        )

        self.assertTrue(
            first["should_notify"]
        )

        self.assertTrue(
            first["low_blink_active"]
        )

        # First blink:
        # 1 blink / 7.5 sec ≈ 8/min
        # Still below recovery threshold 10/min.
        still_low = self.policy.update(
            make_blink_result(
                blink_event=True
            ),
            now=7.5,
        )

        self.assertEqual(
            still_low["state"],
            STATE_LOW_BLINK,
        )

        self.assertTrue(
            still_low["low_blink_active"]
        )

        # Second blink:
        # recent rate rises above recovery threshold.
        recovered = self.policy.update(
            make_blink_result(
                blink_event=True
            ),
            now=8.0,
        )

        self.assertEqual(
            recovered["state"],
            STATE_NORMAL,
        )

        self.assertFalse(
            recovered["should_notify"]
        )

        self.assertFalse(
            recovered["low_blink_active"]
        )

        self.assertEqual(
            recovered["reason"],
            "BLINK_RATE_RECOVERED",
        )

        # Following sample remains NORMAL.
        after_recovery = self.policy.update(
            make_blink_result(),
            now=8.5,
        )

        self.assertEqual(
            after_recovery["state"],
            STATE_NORMAL,
        )

        self.assertEqual(
            after_recovery["reason"],
            "BLINK_RATE_NORMAL",
        )
    # ========================================================
    # DATA GAP
    # ========================================================

    def test_data_gap_clears_window_and_pending_confirmation(
        self,
    ):
        result = self.feed_valid_samples(
            start=0.0,
            end=5.0,
        )

        self.assertEqual(
            result["state"],
            STATE_PENDING_LOW_BLINK,
        )

        gap_result = (
            self.policy.process_data_gap(
                now=6.0,
                reason="TEST_GAP",
            )
        )

        self.assertEqual(
            gap_result["state"],
            STATE_DATA_GAP,
        )

        self.assertFalse(
            gap_result["should_notify"]
        )

        self.assertEqual(
            gap_result["window_blink_count"],
            0,
        )

        self.assertEqual(
            gap_result["valid_observation_seconds"],
            0.0,
        )

        # หลัง gap ต้องเริ่มสะสมใหม่
        after_gap = self.policy.update(
            make_blink_result(),
            now=7.0,
        )

        self.assertEqual(
            after_gap["state"],
            STATE_WARMUP,
        )

        self.assertFalse(
            after_gap["should_notify"]
        )

    # ========================================================
    # AUTOMATIC SAMPLE GAP
    # ========================================================

    def test_large_sample_gap_restarts_observation_window(
        self,
    ):
        self.feed_valid_samples(
            start=0.0,
            end=5.0,
        )

        # gap = 3 sec > maximum_sample_gap_seconds=2
        result = self.policy.update(
            make_blink_result(),
            now=8.0,
        )

        self.assertEqual(
            result["state"],
            STATE_WARMUP,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["valid_observation_seconds"],
            0.0,
        )

    # ========================================================
    # UNKNOWN EYE STATE
    # ========================================================

    def test_short_unknown_does_not_generate_alert(
        self,
    ):
        self.policy.update(
            make_blink_result(),
            now=0.0,
        )

        result = self.policy.update(
            make_blink_result(
                eye_state="UNKNOWN"
            ),
            now=1.0,
        )

        self.assertEqual(
            result["state"],
            STATE_NOT_EVALUATED,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["reason"],
            "EYE_STATE_UNKNOWN",
        )

    def test_long_unknown_gap_becomes_data_gap(
        self,
    ):
        self.policy.update(
            make_blink_result(),
            now=0.0,
        )

        result = self.policy.update(
            make_blink_result(
                eye_state="UNKNOWN"
            ),
            now=3.0,
        )

        self.assertEqual(
            result["state"],
            STATE_DATA_GAP,
        )

        self.assertFalse(
            result["should_notify"]
        )

    # ========================================================
    # RESET
    # ========================================================

    def test_reset_clears_runtime_state(
        self,
    ):
        self.feed_valid_samples(
            start=0.0,
            end=5.0,
        )

        first = self.policy.update(
            make_blink_result(),
            now=7.0,
        )

        self.assertTrue(
            first["should_notify"]
        )

        self.policy.reset()

        result = self.policy.update(
            make_blink_result(),
            now=100.0,
        )

        self.assertEqual(
            result["state"],
            STATE_WARMUP,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["alert_count"],
            0,
        )


if __name__ == "__main__":
    unittest.main()