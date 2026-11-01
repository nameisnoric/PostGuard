import unittest

from app.vision.mediapipe_detection.eye.blink_statistics import (
    BlinkStatistics,
)


class BlinkStatisticsTests(unittest.TestCase):

    def setUp(self):
        self.stats = BlinkStatistics(
            window_seconds=60.0
        )
        self.stats.start(
            timestamp=0.0
        )

    def test_window_not_ready_before_60_seconds(self):
        result = self.stats.update(
            blink_event=True,
            timestamp=10.0,
        )

        self.assertFalse(
            result["window_ready"]
        )

        self.assertIsNone(
            result["blink_rate"]
        )

        self.assertEqual(
            result["blink_count_total"],
            1,
        )

    def test_blink_rate_available_after_60_seconds(self):
        for timestamp in (
            10.0,
            20.0,
            30.0,
            40.0,
            50.0,
            60.0,
        ):
            result = self.stats.update(
                blink_event=True,
                timestamp=timestamp,
            )

        self.assertTrue(
            result["window_ready"]
        )

        self.assertEqual(
            result["blink_count_60s"],
            6,
        )

        self.assertEqual(
            result["blink_rate"],
            6.0,
        )

    def test_expired_blinks_leave_sliding_window(self):
        self.stats.update(
            blink_event=True,
            timestamp=1.0,
        )

        self.stats.update(
            blink_event=True,
            timestamp=30.0,
        )

        result = self.stats.update(
            blink_event=False,
            timestamp=62.0,
        )

        self.assertTrue(
            result["window_ready"]
        )

        self.assertEqual(
            result["blink_count_60s"],
            1,
        )

        self.assertEqual(
            result["blink_rate"],
            1.0,
        )

    def test_reset_clears_statistics(self):
        self.stats.update(
            blink_event=True,
            timestamp=10.0,
        )

        self.stats.reset()

        self.assertEqual(
            self.stats.blink_count_total,
            0,
        )

        self.assertEqual(
            len(self.stats.blink_timestamps),
            0,
        )

        self.assertIsNone(
            self.stats.last_blink_time
        )

    def test_timestamp_before_start_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            self.stats.update(
                blink_event=False,
                timestamp=-1.0,
            )


if __name__ == "__main__":
    unittest.main()