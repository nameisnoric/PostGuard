import unittest

from app.services.session_risk_insight_service import (
    SESSION_RISK_INSIGHT_CONTRACT_VERSION,
    TREND_IMPROVING,
    TREND_NO_COMPARISON,
    TREND_NO_DATA,
    TREND_STABLE,
    TREND_WORSENING,
    build_session_risk_insight,
    build_session_risk_trend_series,
    classify_risk_trend,
)


METHOD = (
    "POSTGUARD_MODIFIED_RULA_FRONT_VIEW_V1"
)


class SessionRiskInsightTests(
    unittest.TestCase
):
    def test_contract_version(
        self,
    ):
        self.assertEqual(
            SESSION_RISK_INSIGHT_CONTRACT_VERSION,
            "1.1",
        )

    def test_improving(
        self,
    ):
        self.assertEqual(
            classify_risk_trend(
                20.0,
                30.0,
            ),
            TREND_IMPROVING,
        )

    def test_worsening(
        self,
    ):
        self.assertEqual(
            classify_risk_trend(
                40.0,
                30.0,
            ),
            TREND_WORSENING,
        )

    def test_stable_inside_deadband(
        self,
    ):
        self.assertEqual(
            classify_risk_trend(
                32.0,
                30.0,
            ),
            TREND_STABLE,
        )

    def test_exact_negative_boundary_is_improving(
        self,
    ):
        self.assertEqual(
            classify_risk_trend(
                25.0,
                30.0,
            ),
            TREND_IMPROVING,
        )

    def test_exact_positive_boundary_is_worsening(
        self,
    ):
        self.assertEqual(
            classify_risk_trend(
                35.0,
                30.0,
            ),
            TREND_WORSENING,
        )

    def test_no_data(
        self,
    ):
        insight = (
            build_session_risk_insight(
                [],
                [],
            )
        )

        self.assertEqual(
            insight[
                "trend"
            ],
            TREND_NO_DATA,
        )

        self.assertIsNone(
            insight[
                "overall_session_risk_score"
            ]
        )

    def test_first_scored_session_has_no_comparison(
        self,
    ):
        sessions = [
            {
                "session_id": 38,
                "status": "COMPLETED",
            }
        ]

        summaries = [
            {
                "session_id": 38,
                "average_risk_score": 21.25,
                "risk_score_method": METHOD,
            }
        ]

        insight = (
            build_session_risk_insight(
                sessions,
                summaries,
            )
        )

        self.assertEqual(
            insight[
                "trend"
            ],
            TREND_NO_COMPARISON,
        )

        self.assertEqual(
            insight[
                "overall_session_risk_score"
            ],
            21.25,
        )

    def test_latest_vs_previous_same_method(
        self,
    ):
        sessions = [
            {
                "session_id": 40,
                "status": "COMPLETED",
            },
            {
                "session_id": 39,
                "status": "COMPLETED",
            },
        ]

        summaries = [
            {
                "session_id": 40,
                "average_risk_score": 20.0,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 39,
                "average_risk_score": 30.0,
                "risk_score_method": METHOD,
            },
        ]

        insight = (
            build_session_risk_insight(
                sessions,
                summaries,
            )
        )

        self.assertEqual(
            insight[
                "session_id"
            ],
            40,
        )

        self.assertEqual(
            insight[
                "previous_session_id"
            ],
            39,
        )

        self.assertEqual(
            insight[
                "score_delta"
            ],
            -10.0,
        )

        self.assertEqual(
            insight[
                "trend"
            ],
            TREND_IMPROVING,
        )

    def test_different_score_method_is_not_compared(
        self,
    ):
        sessions = [
            {
                "session_id": 40,
                "status": "COMPLETED",
            },
            {
                "session_id": 39,
                "status": "COMPLETED",
            },
        ]

        summaries = [
            {
                "session_id": 40,
                "average_risk_score": 20.0,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 39,
                "average_risk_score": 80.0,
                "risk_score_method": "OLD_METHOD",
            },
        ]

        insight = (
            build_session_risk_insight(
                sessions,
                summaries,
            )
        )

        self.assertEqual(
            insight[
                "trend"
            ],
            TREND_NO_COMPARISON,
        )

    def test_trend_series_is_oldest_to_newest(
        self,
    ):
        sessions = [
            {
                "session_id": 40,
                "status": "COMPLETED",
            },
            {
                "session_id": 39,
                "status": "COMPLETED",
            },
            {
                "session_id": 38,
                "status": "COMPLETED",
            },
        ]

        summaries = [
            {
                "session_id": 40,
                "average_risk_score": 20.0,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 39,
                "average_risk_score": 25.0,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 38,
                "average_risk_score": 30.0,
                "risk_score_method": METHOD,
            },
        ]

        series = (
            build_session_risk_trend_series(
                sessions,
                summaries,
            )
        )

        self.assertEqual(
            [
                point[
                    "session_id"
                ]
                for point
                in series
            ],
            [
                38,
                39,
                40,
            ],
        )

        self.assertEqual(
            [
                point[
                    "score"
                ]
                for point
                in series
            ],
            [
                30.0,
                25.0,
                20.0,
            ],
        )

    def test_trend_series_skips_missing_score(
        self,
    ):
        sessions = [
            {
                "session_id": 40,
                "status": "COMPLETED",
            },
            {
                "session_id": 39,
                "status": "COMPLETED",
            },
            {
                "session_id": 38,
                "status": "COMPLETED",
            },
        ]

        summaries = [
            {
                "session_id": 40,
                "average_risk_score": 20.0,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 39,
                "average_risk_score": None,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 38,
                "average_risk_score": 30.0,
                "risk_score_method": METHOD,
            },
        ]

        series = (
            build_session_risk_trend_series(
                sessions,
                summaries,
            )
        )

        self.assertEqual(
            len(
                series
            ),
            2,
        )

        self.assertEqual(
            series[
                0
            ][
                "session_id"
            ],
            38,
        )

        self.assertEqual(
            series[
                1
            ][
                "session_id"
            ],
            40,
        )

    def test_trend_series_excludes_other_methods(
        self,
    ):
        sessions = [
            {
                "session_id": 40,
                "status": "COMPLETED",
            },
            {
                "session_id": 39,
                "status": "COMPLETED",
            },
            {
                "session_id": 38,
                "status": "COMPLETED",
            },
        ]

        summaries = [
            {
                "session_id": 40,
                "average_risk_score": 20.0,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 39,
                "average_risk_score": 80.0,
                "risk_score_method": "OLD_METHOD",
            },
            {
                "session_id": 38,
                "average_risk_score": 30.0,
                "risk_score_method": METHOD,
            },
        ]

        series = (
            build_session_risk_trend_series(
                sessions,
                summaries,
            )
        )

        self.assertEqual(
            [
                point[
                    "session_id"
                ]
                for point
                in series
            ],
            [
                38,
                40,
            ],
        )

    def test_trend_series_limits_latest_ten(
        self,
    ):
        sessions = [
            {
                "session_id": session_id,
                "status": "COMPLETED",
            }
            for session_id
            in range(
                20,
                5,
                -1,
            )
        ]

        summaries = [
            {
                "session_id": session_id,
                "average_risk_score": float(
                    session_id
                ),
                "risk_score_method": METHOD,
            }
            for session_id
            in range(
                20,
                5,
                -1,
            )
        ]

        series = (
            build_session_risk_trend_series(
                sessions,
                summaries,
                max_points=10,
            )
        )

        self.assertEqual(
            len(
                series
            ),
            10,
        )

        self.assertEqual(
            series[
                -1
            ][
                "session_id"
            ],
            20,
        )


if __name__ == "__main__":
    unittest.main()