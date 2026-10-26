import math
import unittest

from app.ui.utils.risk_display import format_rula_percent, rula_score_to_percent


class RiskDisplayTests(unittest.TestCase):
    def test_rula_range_maps_linearly_to_percentage(self):
        self.assertEqual(rula_score_to_percent(1), 0.0)
        self.assertEqual(rula_score_to_percent(4), 50.0)
        self.assertEqual(rula_score_to_percent(7), 100.0)
        self.assertEqual(format_rula_percent(2, 1), "16.7%")

    def test_invalid_scores_remain_unavailable(self):
        for value in (None, True, 0, 8, math.nan, "4"):
            with self.subTest(value=value):
                self.assertIsNone(rula_score_to_percent(value))
                self.assertEqual(format_rula_percent(value), "N/A")


if __name__ == "__main__":
    unittest.main()
