import unittest

from app.services.posture_duration_tracker import (
    PostureDurationTracker,
    classify_neck_side_bending,
)
from app.services.risk_engine import assess_posture


class TestPostureDurationTracker(unittest.TestCase):
    def test_continuous_one_side(self):
        tracker = PostureDurationTracker()
        self.assertEqual(tracker.update(1, now=100), 0)
        self.assertEqual(tracker.update(1, now=130), 30)
        self.assertEqual(tracker.update(1, now=160), 60)

    def test_neutral_resets(self):
        tracker = PostureDurationTracker()
        tracker.update(1, now=100)
        self.assertEqual(tracker.update(0, now=120), 0)
        self.assertEqual(tracker.update(1, now=130), 0)

    def test_switching_side_resets(self):
        tracker = PostureDurationTracker()
        tracker.update(1, now=100)
        self.assertEqual(tracker.update(-1, now=120), 0)
        self.assertEqual(tracker.update(-1, now=125), 5)

    def test_missing_detection_resets(self):
        tracker = PostureDurationTracker()
        tracker.update(-1, now=100)
        self.assertIsNone(tracker.update(None, now=110))
        self.assertEqual(tracker.update(-1, now=120), 0)

    def test_disabled_threshold(self):
        self.assertIsNone(classify_neck_side_bending(9, 1, 0))
        self.assertIsNone(classify_neck_side_bending(None, 1, 5))

    def test_classification_relative_to_baseline(self):
        self.assertEqual(classify_neck_side_bending(7, 1, 5), 1)
        self.assertEqual(classify_neck_side_bending(-5, 1, 5), -1)
        self.assertEqual(classify_neck_side_bending(4, 1, 5), 0)

    def test_duration_score_at_60(self):
        self.assertEqual(
            assess_posture(neck_side_bending=True, sustained_seconds=59)["factors"]["muscle_use_duration"],
            0,
        )
        self.assertEqual(
            assess_posture(neck_side_bending=True, sustained_seconds=60)["factors"]["muscle_use_duration"],
            1,
        )

    def test_incomplete_assessment_has_no_raw_score(self):
        result = assess_posture(neck_side_bending=True, sustained_seconds=65)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["raw_score"])


if __name__ == "__main__":
    unittest.main()
