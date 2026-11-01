import unittest

from app.services.wellness_alert_policy import (
    WellnessAlertConfig,
    WellnessAlertPolicy,
)


class WellnessAlertPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = WellnessAlertPolicy(WellnessAlertConfig(
            low_blink_rate_per_minute=8.0,
            recovery_blink_rate_per_minute=10.0,
            blink_confirmation_seconds=2.0,
            repeat_cooldown_seconds=30.0,
        ))

    @staticmethod
    def screen(state="NORMAL", evaluated=True):
        return {"state": state, "evaluated": evaluated, "ratio": 1.3}

    @staticmethod
    def blink(rate=15.0, ready=True):
        return {"window_ready": ready, "blink_rate": rate}

    def test_screen_distance_first_repeat_and_resolution(self):
        first = self.policy.update(
            self.screen("TOO_CLOSE"), self.blink(), now=0.0
        )
        self.assertEqual(first["notification"]["event_type"], "SCREEN_DISTANCE")
        self.assertEqual(first["notification"]["alert_type"], "FIRST")

        quiet = self.policy.update(
            self.screen("TOO_CLOSE"), self.blink(), now=20.0
        )
        self.assertIsNone(quiet["notification"])

        repeat = self.policy.update(
            self.screen("TOO_CLOSE"), self.blink(), now=30.0
        )
        self.assertEqual(repeat["notification"]["alert_type"], "REPEAT")

        resolved = self.policy.update(self.screen(), self.blink(), now=31.0)
        screen_event = resolved["events"][0]
        self.assertEqual(screen_event["action"], "RESOLVED")
        self.assertFalse(screen_event["active"])

    def test_blink_waits_for_complete_window(self):
        waiting = self.policy.update(
            self.screen(), self.blink(rate=None, ready=False), now=0.0
        )
        self.assertIsNone(waiting["notification"])
        low = self.policy.update(
            self.screen(), self.blink(rate=5.0, ready=True), now=60.0
        )
        self.assertIsNone(low["notification"])
        self.assertEqual(low["events"][1]["action"], "PENDING")
        confirmed = self.policy.update(
            self.screen(), self.blink(rate=5.0, ready=True), now=62.0
        )
        self.assertEqual(
            confirmed["notification"]["event_type"], "LOW_BLINK_RATE"
        )
        self.assertEqual(confirmed["notification"]["alert_type"], "FIRST")

    def test_low_blink_uses_hysteresis_and_repeat_cooldown(self):
        self.policy.update(self.screen(), self.blink(rate=5.0), now=0.0)
        first = self.policy.update(self.screen(), self.blink(rate=5.0), now=2.0)
        self.assertEqual(first["notification"]["alert_type"], "FIRST")

        still_active = self.policy.update(
            self.screen(), self.blink(rate=9.0), now=3.0
        )
        self.assertTrue(still_active["events"][1]["active"])
        repeat = self.policy.update(
            self.screen(), self.blink(rate=9.0), now=32.0
        )
        self.assertEqual(repeat["notification"]["alert_type"], "REPEAT")

        recovered = self.policy.update(
            self.screen(), self.blink(rate=10.0), now=33.0
        )
        self.assertEqual(recovered["events"][1]["action"], "RESOLVED")

    def test_data_gap_preserves_active_episode_without_notification(self):
        self.policy.update(self.screen("TOO_CLOSE"), self.blink(), now=0.0)
        gap = self.policy.update(
            self.screen("NOT_EVALUATED", evaluated=False),
            self.blink(rate=None, ready=False),
            now=40.0,
        )
        self.assertTrue(gap["events"][0]["active"])
        self.assertEqual(gap["events"][0]["action"], "DATA_GAP")
        self.assertIsNone(gap["notification"])

    def test_simultaneous_screen_and_eye_alerts_are_not_dropped(self):
        self.policy.update(
            self.screen("NORMAL"), self.blink(rate=5.0), now=0.0
        )
        result = self.policy.update(
            self.screen("TOO_CLOSE"), self.blink(rate=5.0), now=2.0
        )
        self.assertEqual(
            [item["event_type"] for item in result["notifications"]],
            ["SCREEN_DISTANCE", "LOW_BLINK_RATE"],
        )


if __name__ == "__main__":
    unittest.main()
