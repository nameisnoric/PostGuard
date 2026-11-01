import unittest

from app.services.camera_loss_tracker import CameraLossTracker


class CameraLossTrackerTests(unittest.TestCase):
    def test_one_gap_counts_once_and_accumulates_duration(self):
        tracker = CameraLossTracker()
        self.assertTrue(tracker.begin(10.0))
        self.assertFalse(tracker.begin(11.0))
        self.assertEqual(tracker.loss_count, 1)
        self.assertEqual(tracker.duration(13.5), 3.5)
        self.assertEqual(tracker.recover(14.0), 4.0)
        self.assertEqual(tracker.duration(), 4.0)
        self.assertFalse(tracker.active)

    def test_separate_gaps_accumulate(self):
        tracker = CameraLossTracker()
        tracker.begin(1.0)
        tracker.recover(3.0)
        tracker.begin(10.0)
        tracker.recover(13.5)
        self.assertEqual(tracker.loss_count, 2)
        self.assertEqual(tracker.duration(), 5.5)

    def test_pause_closes_duration_and_continue_does_not_add_loss(self):
        tracker = CameraLossTracker()
        tracker.begin(10.0)
        self.assertEqual(tracker.recover(12.0), 2.0)
        self.assertTrue(tracker.continue_after_pause(100.0))
        self.assertEqual(tracker.loss_count, 1)
        self.assertEqual(tracker.duration(103.0), 5.0)


if __name__ == "__main__":
    unittest.main()
