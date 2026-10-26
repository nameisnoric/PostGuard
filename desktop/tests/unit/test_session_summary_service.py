import unittest
from unittest.mock import (
    Mock,
    patch,
)

import requests

from app.services.session_summary_service import (
    APIClient,
    RISK_SCORE_METHOD,
    build_summary_payload,
    load_session_summary,
    save_session_summary,
)


def response(
    status,
    data,
):
    return Mock(
        status_code=status,
        ok=status < 400,
        json=lambda: data,
        text="test response",
    )


class SummaryServiceTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.summary = {
            "session_id": 7,
            "database_status": "COMPLETED",

            "detection_count": 10,
            "pose_detected_count": 8,
            "face_detected_count": 6,

            "average_shoulder": -1.5,
            "average_neck": None,

            "average_risk_score": None,
            "minimum_risk_score": None,
            "maximum_risk_score": None,

            "risk_score_buckets": [],
        }

    # ========================================================
    # LEGACY / NO SCORE SESSION
    # ========================================================

    def test_save_measured_values_and_null_risk(
        self,
    ):
        with patch.object(
            APIClient,
            "post",
            return_value=response(
                201,
                {
                    "session_id": 7,
                },
            ),
        ) as post:
            result = save_session_summary(
                self.summary
            )

            self.assertEqual(
                result["status"],
                "SAVED",
            )

            payload = (
                post.call_args.args[1]
            )

            self.assertEqual(
                payload[
                    "detection_count"
                ],
                10,
            )

            self.assertEqual(
                payload[
                    "average_shoulder"
                ],
                -1.5,
            )

            self.assertIsNone(
                payload[
                    "average_risk_score"
                ]
            )

            self.assertIsNone(
                payload[
                    "minimum_risk_score"
                ]
            )

            self.assertIsNone(
                payload[
                    "maximum_risk_score"
                ]
            )

            self.assertIsNone(
                payload[
                    "risk_score_method"
                ]
            )

            self.assertEqual(
                payload[
                    "risk_score_buckets"
                ],
                [],
            )

    # ========================================================
    # SCORE SESSION
    # ========================================================

    def test_build_payload_with_risk_scores_and_buckets(
        self,
    ):
        summary = {
            **self.summary,

            "average_risk_score": 50.0,
            "minimum_risk_score": 17.0,
            "maximum_risk_score": 83.0,

            "risk_score_buckets": [
                {
                    "bucket_index": 0,

                    "start_second": 0.0,
                    "end_second": 10.0,

                    "sample_count": 20,

                    "average_risk_score": 33.5,
                    "minimum_risk_score": 17.0,
                    "maximum_risk_score": 50.0,

                    "minimum_modified_rula_score": 2,
                    "maximum_modified_rula_score": 4,
                },
                {
                    "bucket_index": 1,

                    "start_second": 10.0,
                    "end_second": 20.0,

                    "sample_count": 18,

                    "average_risk_score": 75.0,
                    "minimum_risk_score": 67.0,
                    "maximum_risk_score": 83.0,

                    "minimum_modified_rula_score": 5,
                    "maximum_modified_rula_score": 6,
                },
            ],
        }

        payload = build_summary_payload(
            summary
        )

        self.assertEqual(
            payload[
                "average_risk_score"
            ],
            50.0,
        )

        self.assertEqual(
            payload[
                "minimum_risk_score"
            ],
            17.0,
        )

        self.assertEqual(
            payload[
                "maximum_risk_score"
            ],
            83.0,
        )

        self.assertEqual(
            payload[
                "risk_score_method"
            ],
            RISK_SCORE_METHOD,
        )

        self.assertEqual(
            len(
                payload[
                    "risk_score_buckets"
                ]
            ),
            2,
        )

        self.assertEqual(
            payload[
                "risk_score_buckets"
            ][0][
                "bucket_index"
            ],
            0,
        )

        self.assertEqual(
            payload[
                "risk_score_buckets"
            ][1][
                "maximum_risk_score"
            ],
            83.0,
        )

    # ========================================================
    # SAVE SCORE
    # ========================================================

    def test_save_risk_score_payload(
        self,
    ):
        summary = {
            **self.summary,

            "average_risk_score": 50.0,
            "minimum_risk_score": 17.0,
            "maximum_risk_score": 83.0,

            "risk_score_buckets": [
                {
                    "bucket_index": 0,
                    "start_second": 0.0,
                    "end_second": 10.0,
                    "sample_count": 10,

                    "average_risk_score": 50.0,
                    "minimum_risk_score": 17.0,
                    "maximum_risk_score": 83.0,

                    "minimum_modified_rula_score": 2,
                    "maximum_modified_rula_score": 6,
                }
            ],
        }

        with patch.object(
            APIClient,
            "post",
            return_value=response(
                201,
                {
                    "session_id": 7,
                },
            ),
        ) as post:
            result = save_session_summary(
                summary
            )

            self.assertEqual(
                result[
                    "status"
                ],
                "SAVED",
            )

            payload = (
                post.call_args.args[1]
            )

            self.assertEqual(
                payload[
                    "average_risk_score"
                ],
                50.0,
            )

            self.assertEqual(
                payload[
                    "risk_score_method"
                ],
                RISK_SCORE_METHOD,
            )

            self.assertEqual(
                len(
                    payload[
                        "risk_score_buckets"
                    ]
                ),
                1,
            )

    # ========================================================
    # RETRY
    # ========================================================

    def test_retry_after_lost_response_reads_existing_report(
        self,
    ):
        saved = {
            "session_id": 7,
            "detection_count": 10,
        }

        with (
            patch.object(
                APIClient,
                "post",
                side_effect=[
                    requests.Timeout(),
                    response(
                        409,
                        {},
                    ),
                ],
            ),
            patch.object(
                APIClient,
                "get",
                return_value=response(
                    200,
                    saved,
                ),
            ),
        ):
            with self.assertRaises(
                requests.Timeout
            ):
                save_session_summary(
                    self.summary
                )

            result = (
                save_session_summary(
                    self.summary
                )
            )

            self.assertEqual(
                result,
                {
                    "status": (
                        "ALREADY_EXISTS"
                    ),
                    "summary": saved,
                },
            )

    # ========================================================
    # INVALID SUMMARY
    # ========================================================

    def test_reject_unfinished_or_invalid_data(
        self,
    ):
        changes = (
            {
                "database_status": (
                    "RUNNING"
                ),
            },
            {
                "face_detected_count": 11,
            },
            {
                "average_neck": (
                    float("nan")
                ),
            },
            {
                "detection_count": True,
            },
        )

        for change in changes:
            with (
                self.subTest(
                    change=change
                ),
                patch.object(
                    APIClient,
                    "post",
                ) as post,
            ):
                with self.assertRaises(
                    ValueError
                ):
                    save_session_summary(
                        {
                            **self.summary,
                            **change,
                        }
                    )

                post.assert_not_called()

    # ========================================================
    # INVALID SCORE
    # ========================================================

    def test_reject_invalid_session_risk_scores(
        self,
    ):
        invalid = (
            {
                "average_risk_score": 50.0,
                "minimum_risk_score": None,
                "maximum_risk_score": 83.0,
            },
            {
                "average_risk_score": 40.0,
                "minimum_risk_score": 60.0,
                "maximum_risk_score": 80.0,
            },
            {
                "average_risk_score": 50.0,
                "minimum_risk_score": 17.0,
                "maximum_risk_score": 101.0,
            },
        )

        for change in invalid:
            with self.subTest(
                change=change
            ):
                with self.assertRaises(
                    ValueError
                ):
                    build_summary_payload(
                        {
                            **self.summary,
                            **change,
                        }
                    )

    # ========================================================
    # INVALID BUCKET
    # ========================================================

    def test_reject_invalid_risk_score_bucket(
        self,
    ):
        base = {
            **self.summary,

            "average_risk_score": 50.0,
            "minimum_risk_score": 17.0,
            "maximum_risk_score": 83.0,
        }

        invalid_buckets = (
            {
                "bucket_index": 0,
                "start_second": 10.0,
                "end_second": 5.0,
                "sample_count": 10,

                "average_risk_score": 50.0,
                "minimum_risk_score": 17.0,
                "maximum_risk_score": 83.0,

                "minimum_modified_rula_score": 2,
                "maximum_modified_rula_score": 6,
            },

            {
                "bucket_index": 0,
                "start_second": 0.0,
                "end_second": 10.0,
                "sample_count": 0,

                "average_risk_score": 50.0,
                "minimum_risk_score": 17.0,
                "maximum_risk_score": 83.0,

                "minimum_modified_rula_score": 2,
                "maximum_modified_rula_score": 6,
            },

            {
                "bucket_index": 0,
                "start_second": 0.0,
                "end_second": 10.0,
                "sample_count": 10,

                "average_risk_score": 50.0,
                "minimum_risk_score": 17.0,
                "maximum_risk_score": 83.0,

                "minimum_modified_rula_score": 0,
                "maximum_modified_rula_score": 6,
            },
        )

        for bucket in invalid_buckets:
            with self.subTest(
                bucket=bucket
            ):
                with self.assertRaises(
                    ValueError
                ):
                    build_summary_payload(
                        {
                            **base,
                            "risk_score_buckets": [
                                bucket
                            ],
                        }
                    )

    # ========================================================
    # LOAD
    # ========================================================

    def test_load_missing_failed_or_wrong_report(
        self,
    ):
        for status, data in (
            (
                200,
                {
                    "session_id": 8,
                },
            ),
            (
                200,
                [],
            ),
            (
                500,
                {},
            ),
        ):
            with (
                self.subTest(
                    status=status,
                    data=data,
                ),
                patch.object(
                    APIClient,
                    "get",
                    return_value=response(
                        status,
                        data,
                    ),
                ),
            ):
                with self.assertRaises(
                    (
                        ValueError,
                        RuntimeError,
                    )
                ):
                    load_session_summary(
                        7
                    )

        with patch.object(
            APIClient,
            "get",
            return_value=response(
                404,
                {},
            ),
        ):
            self.assertIsNone(
                load_session_summary(
                    7
                )
            )

    def test_bad_save_response_is_not_success(
        self,
    ):
        with patch.object(
            APIClient,
            "post",
            return_value=response(
                201,
                [],
            ),
        ):
            with self.assertRaises(
                ValueError
            ):
                save_session_summary(
                    self.summary
                )


if __name__ == "__main__":
    unittest.main()