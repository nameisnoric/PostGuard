import os
import unittest


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)


from PySide6.QtWidgets import (
    QApplication,
)

from app.ui.session_risk_trend_chart import (
    SessionRiskTrendChart,
)


class SessionRiskTrendChartTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or
            QApplication([])
        )

    def setUp(
        self,
    ):
        self.chart = (
            SessionRiskTrendChart()
        )

        self.addCleanup(
            self.chart.deleteLater
        )

    def test_empty_series(
        self,
    ):
        self.chart.set_series(
            []
        )

        self.assertEqual(
            self.chart.series,
            [],
        )

    def test_valid_series_is_preserved(
        self,
    ):
        self.chart.set_series(
            [
                {
                    "session_id": 38,
                    "score": 21.25,
                    "risk_score_method": "METHOD",
                },
                {
                    "session_id": 39,
                    "score": 18.50,
                    "risk_score_method": "METHOD",
                },
            ]
        )

        self.assertEqual(
            len(
                self.chart.series
            ),
            2,
        )

        self.assertEqual(
            self.chart.series[
                0
            ][
                "session_id"
            ],
            38,
        )

        self.assertEqual(
            self.chart.series[
                1
            ][
                "score"
            ],
            18.50,
        )

    def test_invalid_points_are_skipped(
        self,
    ):
        self.chart.set_series(
            [
                {
                    "session_id": 38,
                    "score": 21.25,
                },
                {
                    "session_id": 39,
                    "score": None,
                },
                {
                    "session_id": -1,
                    "score": 20.0,
                },
                {
                    "session_id": 40,
                    "score": 101.0,
                },
            ]
        )

        self.assertEqual(
            len(
                self.chart.series
            ),
            1,
        )

        self.assertEqual(
            self.chart.series[
                0
            ][
                "session_id"
            ],
            38,
        )

    def test_clear(
        self,
    ):
        self.chart.set_series(
            [
                {
                    "session_id": 38,
                    "score": 21.25,
                }
            ]
        )

        self.chart.clear()

        self.assertEqual(
            self.chart.series,
            [],
        )


if __name__ == "__main__":
    unittest.main()