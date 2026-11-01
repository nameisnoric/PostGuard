import unittest

from app.services.camera_loss_tracker import (
    CameraLossTracker,
)


class CameraLossTrackerTests(unittest.TestCase):

    def setUp(self):
        self.tracker = CameraLossTracker()

    def test_begin_counts_one_camera_loss(self):
        started = self.tracker.begin(
            10.0
        )

        self.assertTrue(started)
        self.assertTrue(
            self.tracker.active
        )
        self.assertEqual(
            self.tracker.loss_count,
            1,
        )

    def test_repeated_begin_does_not_double_count(self):
        first = self.tracker.begin(
            10.0
        )

        second = self.tracker.begin(
            11.0
        )

        self.assertTrue(first)
        self.assertFalse(second)

        self.assertEqual(
            self.tracker.loss_count,
            1,
        )

    def test_recover_accumulates_gap_duration(self):
        self.tracker.begin(
            10.0
        )

        duration = self.tracker.recover(
            15.5
        )

        self.assertAlmostEqual(
            duration,
            5.5,
        )

        self.assertAlmostEqual(
            self.tracker.total_duration,
            5.5,
        )

        self.assertFalse(
            self.tracker.active
        )

    def test_multiple_camera_losses_are_accumulated(self):
        self.tracker.begin(
            10.0
        )
        self.tracker.recover(
            15.0
        )

        self.tracker.begin(
            20.0
        )
        self.tracker.recover(
            23.0
        )

        self.assertEqual(
            self.tracker.loss_count,
            2,
        )

        self.assertAlmostEqual(
            self.tracker.total_duration,
            8.0,
        )

    def test_active_gap_is_included_in_duration(self):
        self.tracker.begin(
            10.0
        )

        self.assertAlmostEqual(
            self.tracker.duration(
                14.0
            ),
            4.0,
        )

    def test_reset_clears_session_metrics(self):
        self.tracker.begin(
            10.0
        )
        self.tracker.recover(
            15.0
        )

        self.tracker.reset()

        self.assertEqual(
            self.tracker.loss_count,
            0,
        )

        self.assertEqual(
            self.tracker.total_duration,
            0.0,
        )

        self.assertFalse(
            self.tracker.active
        )


if __name__ == "__main__":
    unittest.main()