import unittest

from app.services.session_risk_score_collector import (
    SessionRiskScoreCollector,
    SessionRiskScoreCollectorError,
)


def pipeline_result(
    *,
    timestamp: float,
    rula: int | None,
    risk_score: float | None,
    status: str = "COMPLETE",
):
    return {
        "timestamp_monotonic": (
            timestamp
        ),

        "posture_score": {
            "status": status,

            "modified_rula_score": (
                rula
            ),

            "postguard_risk_score": (
                risk_score
            ),
        },
    }


class SessionRiskScoreCollectorTests(
    unittest.TestCase
):

    def test_empty_session_has_no_score(
        self,
    ):
        collector = (
            SessionRiskScoreCollector()
        )

        result = (
            collector.get_summary()
        )

        self.assertEqual(
            result["status"],
            "NO_VALID_SCORES",
        )

        self.assertIsNone(
            result[
                "average_risk_score"
            ]
        )

        self.assertIsNone(
            result[
                "minimum_risk_score"
            ]
        )

        self.assertIsNone(
            result[
                "maximum_risk_score"
            ]
        )

        self.assertEqual(
            result["buckets"],
            [],
        )

    def test_one_score_sets_avg_min_max(
        self,
    ):
        collector = (
            SessionRiskScoreCollector()
        )

        accepted = (
            collector.add_pipeline_result(
                pipeline_result(
                    timestamp=100.0,
                    rula=5,
                    risk_score=67,
                )
            )
        )

        self.assertTrue(
            accepted
        )

        result = (
            collector.get_summary()
        )

        self.assertEqual(
            result["status"],
            "AVAILABLE",
        )

        self.assertEqual(
            result[
                "average_risk_score"
            ],
            67.0,
        )

        self.assertEqual(
            result[
                "minimum_risk_score"
            ],
            67.0,
        )

        self.assertEqual(
            result[
                "maximum_risk_score"
            ],
            67.0,
        )

    def test_average_min_max_from_all_valid_samples(
        self,
    ):
        collector = (
            SessionRiskScoreCollector(
                bucket_seconds=10.0
            )
        )

        collector.start_session(
            now=100.0
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=100.0,
                rula=1,
                risk_score=0,
            )
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=103.0,
                rula=3,
                risk_score=33,
            )
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=106.0,
                rula=5,
                risk_score=67,
            )
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=109.0,
                rula=7,
                risk_score=100,
            )
        )

        result = (
            collector.get_summary()
        )

        self.assertAlmostEqual(
            result[
                "average_risk_score"
            ],
            50.0,
        )

        self.assertEqual(
            result[
                "minimum_risk_score"
            ],
            0.0,
        )

        self.assertEqual(
            result[
                "maximum_risk_score"
            ],
            100.0,
        )

    def test_partial_score_is_skipped_not_zero(
        self,
    ):
        collector = (
            SessionRiskScoreCollector()
        )

        collector.start_session(
            now=100.0
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=100.0,
                rula=5,
                risk_score=67,
            )
        )

        accepted = (
            collector.add_pipeline_result(
                pipeline_result(
                    timestamp=101.0,
                    rula=None,
                    risk_score=None,
                    status="PARTIAL",
                )
            )
        )

        self.assertFalse(
            accepted
        )

        result = (
            collector.get_summary()
        )

        self.assertEqual(
            result[
                "average_risk_score"
            ],
            67.0,
        )

        self.assertEqual(
            result[
                "accepted_score_samples"
            ],
            1,
        )

        self.assertEqual(
            result[
                "skipped_score_samples"
            ],
            1,
        )

    def test_ten_second_buckets(
        self,
    ):
        collector = (
            SessionRiskScoreCollector(
                bucket_seconds=10.0
            )
        )

        collector.start_session(
            now=100.0
        )

        # bucket 0: [0, 10)
        collector.add_pipeline_result(
            pipeline_result(
                timestamp=100.0,
                rula=2,
                risk_score=17,
            )
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=109.999,
                rula=4,
                risk_score=50,
            )
        )

        # bucket 1: [10, 20)
        collector.add_pipeline_result(
            pipeline_result(
                timestamp=110.0,
                rula=5,
                risk_score=67,
            )
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=119.0,
                rula=7,
                risk_score=100,
            )
        )

        result = (
            collector.get_summary()
        )

        buckets = (
            result[
                "buckets"
            ]
        )

        self.assertEqual(
            len(
                buckets
            ),
            2,
        )

        first = buckets[0]

        self.assertEqual(
            first[
                "bucket_index"
            ],
            0,
        )

        self.assertEqual(
            first[
                "start_second"
            ],
            0.0,
        )

        self.assertEqual(
            first[
                "end_second"
            ],
            10.0,
        )

        self.assertEqual(
            first[
                "sample_count"
            ],
            2,
        )

        self.assertAlmostEqual(
            first[
                "average_risk_score"
            ],
            33.5,
        )

        self.assertEqual(
            first[
                "minimum_risk_score"
            ],
            17.0,
        )

        self.assertEqual(
            first[
                "maximum_risk_score"
            ],
            50.0,
        )

        second = buckets[1]

        self.assertEqual(
            second[
                "bucket_index"
            ],
            1,
        )

        self.assertAlmostEqual(
            second[
                "average_risk_score"
            ],
            83.5,
        )

    def test_rula_distribution_is_preserved(
        self,
    ):
        collector = (
            SessionRiskScoreCollector()
        )

        collector.start_session(
            now=100.0
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=100.0,
                rula=5,
                risk_score=67,
            )
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=101.0,
                rula=5,
                risk_score=67,
            )
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=102.0,
                rula=3,
                risk_score=33,
            )
        )

        result = (
            collector.get_summary()
        )

        distribution = (
            result[
                "modified_rula_distribution"
            ]
        )

        self.assertEqual(
            distribution["5"],
            2,
        )

        self.assertEqual(
            distribution["3"],
            1,
        )

        self.assertEqual(
            distribution["1"],
            0,
        )

    def test_reset_clears_previous_session(
        self,
    ):
        collector = (
            SessionRiskScoreCollector()
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=100.0,
                rula=7,
                risk_score=100,
            )
        )

        self.assertEqual(
            collector.get_sample_count(),
            1,
        )

        collector.reset(
            session_started_at_monotonic=200.0
        )

        self.assertEqual(
            collector.get_sample_count(),
            0,
        )

        result = (
            collector.get_summary()
        )

        self.assertEqual(
            result["status"],
            "NO_VALID_SCORES",
        )

    def test_pause_style_pipeline_reset_does_not_require_collector_reset(
        self,
    ):
        """
        Collector itself is session-level.

        A caller may reset the risk pipeline during Pause/Resume,
        but must keep this collector instance alive.
        """

        collector = (
            SessionRiskScoreCollector()
        )

        collector.start_session(
            now=100.0
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=100.0,
                rula=2,
                risk_score=17,
            )
        )

        # Simulate time after Pause/Resume.
        collector.add_pipeline_result(
            pipeline_result(
                timestamp=130.0,
                rula=6,
                risk_score=83,
            )
        )

        result = (
            collector.get_summary()
        )

        self.assertEqual(
            result[
                "accepted_score_samples"
            ],
            2,
        )

        self.assertEqual(
            result[
                "minimum_risk_score"
            ],
            17.0,
        )

        self.assertEqual(
            result[
                "maximum_risk_score"
            ],
            83.0,
        )

    def test_timestamp_cannot_move_backwards(
        self,
    ):
        collector = (
            SessionRiskScoreCollector()
        )

        collector.add_pipeline_result(
            pipeline_result(
                timestamp=100.0,
                rula=3,
                risk_score=33,
            )
        )

        with self.assertRaises(
            SessionRiskScoreCollectorError
        ):
            collector.add_pipeline_result(
                pipeline_result(
                    timestamp=99.0,
                    rula=3,
                    risk_score=33,
                )
            )

    def test_invalid_score_is_not_accepted(
        self,
    ):
        collector = (
            SessionRiskScoreCollector()
        )

        accepted = (
            collector.add_pipeline_result(
                pipeline_result(
                    timestamp=100.0,
                    rula=8,
                    risk_score=150,
                )
            )
        )

        self.assertFalse(
            accepted
        )

        result = (
            collector.get_summary()
        )

        self.assertEqual(
            result[
                "accepted_score_samples"
            ],
            0,
        )


if __name__ == "__main__":

    unittest.main()