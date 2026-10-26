import unittest

from app.services.session_comparison_service import (
    SESSION_COMPARISON_CONTRACT_VERSION,
    STATUS_AVAILABLE,
    STATUS_METHOD_MISMATCH,
    STATUS_SAME_SESSION,
    build_comparison_candidates,
    compare_sessions,
)


METHOD = (
    "POSTGUARD_MODIFIED_RULA_FRONT_VIEW_V1"
)


class SessionComparisonServiceTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.sessions = [
            {
                "session_id": 40,
                "status": "COMPLETED",
                "total_duration": 120,
                "paused_duration": 20,
            },
            {
                "session_id": 39,
                "status": "COMPLETED",
                "total_duration": 100,
                "paused_duration": 10,
            },
        ]

        self.summaries = [
            {
                "session_id": 40,
                "average_risk_score": 20.0,
                "minimum_risk_score": 0.0,
                "maximum_risk_score": 50.0,
                "total_alert_count": 1,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 39,
                "average_risk_score": 30.0,
                "minimum_risk_score": 0.0,
                "maximum_risk_score": 83.0,
                "total_alert_count": 3,
                "risk_score_method": METHOD,
            },
        ]

    def test_contract_version(
        self,
    ):
        self.assertEqual(
            SESSION_COMPARISON_CONTRACT_VERSION,
            "1.1",
        )

    def test_candidates(
        self,
    ):
        candidates = (
            build_comparison_candidates(
                self.sessions,
                self.summaries,
            )
        )

        self.assertEqual(
            len(
                candidates
            ),
            2,
        )

        self.assertEqual(
            candidates[
                0
            ][
                "session_id"
            ],
            40,
        )

    def test_compare_improving(
        self,
    ):
        result = (
            compare_sessions(
                self.sessions,
                self.summaries,
                39,
                40,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            STATUS_AVAILABLE,
        )

        self.assertEqual(
            result[
                "trend_text"
            ],
            "ดีขึ้น",
        )

        self.assertEqual(
            result[
                "deltas"
            ][
                "average_risk_score"
            ],
            -10.0,
        )

        self.assertEqual(
            result[
                "deltas"
            ][
                "maximum_risk_score"
            ],
            -33.0,
        )

        self.assertEqual(
            result[
                "deltas"
            ][
                "total_alert_count"
            ],
            -2.0,
        )

        self.assertEqual(
            result[
                "session_a"
            ][
                "active_seconds"
            ],
            90,
        )

        self.assertEqual(
            result[
                "session_b"
            ][
                "active_seconds"
            ],
            100,
        )

    def test_alert_rate_is_normalized_by_active_time(
        self,
    ):
        result = compare_sessions(
            self.sessions,
            self.summaries,
            39,
            40,
        )

        rate_a = (
            result[
                "session_a"
            ][
                "alert_rate_per_minute"
            ]
        )

        rate_b = (
            result[
                "session_b"
            ][
                "alert_rate_per_minute"
            ]
        )

        # Session 39:
        # 3 alerts / 90 seconds = 2.0 per minute
        self.assertAlmostEqual(
            rate_a,
            2.0,
            places=6,
        )

        # Session 40:
        # 1 alert / 100 seconds = 0.6 per minute
        self.assertAlmostEqual(
            rate_b,
            0.6,
            places=6,
        )

        self.assertAlmostEqual(
            result[
                "deltas"
            ][
                "alert_rate_per_minute"
            ],
            -1.4,
            places=6,
        )

    def test_stable_human_explanation(
        self,
    ):
        summaries = [
            {
                **self.summaries[
                    0
                ],
                "average_risk_score": 29.0,
            },
            self.summaries[
                1
            ],
        ]

        result = compare_sessions(
            self.sessions,
            summaries,
            39,
            40,
        )

        self.assertEqual(
            result[
                "trend_text"
            ],
            "ใกล้เคียงเดิม",
        )

        self.assertIn(
            "ยังไม่มากพอ",
            result[
                "explanation"
            ],
        )

    def test_same_session_rejected(
        self,
    ):
        result = compare_sessions(
            self.sessions,
            self.summaries,
            40,
            40,
        )

        self.assertEqual(
            result[
                "status"
            ],
            STATUS_SAME_SESSION,
        )

    def test_method_mismatch_not_compared(
        self,
    ):
        summaries = [
            self.summaries[
                0
            ],
            {
                **self.summaries[
                    1
                ],
                "risk_score_method": (
                    "OLD_METHOD"
                ),
            },
        ]

        result = compare_sessions(
            self.sessions,
            summaries,
            39,
            40,
        )

        self.assertEqual(
            result[
                "status"
            ],
            STATUS_METHOD_MISMATCH,
        )

        self.assertNotIn(
            "trend",
            result,
        )

    def test_missing_score_not_candidate(
        self,
    ):
        summaries = [
            self.summaries[
                0
            ],
            {
                **self.summaries[
                    1
                ],
                "average_risk_score": None,
            },
        ]

        candidates = (
            build_comparison_candidates(
                self.sessions,
                summaries,
            )
        )

        self.assertEqual(
            len(
                candidates
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()