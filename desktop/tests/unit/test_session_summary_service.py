import unittest
from unittest.mock import Mock, patch

import requests

from app.services.session_summary_service import (
    APIClient, load_session_summary, save_session_summary,
)


def response(status, data):
    return Mock(status_code=status, ok=status < 400, json=lambda: data, text="test response")


class SummaryServiceTests(unittest.TestCase):
    def setUp(self):
        self.summary = dict(session_id=7, database_status="COMPLETED", detection_count=10, pose_detected_count=8, face_detected_count=6, average_shoulder=-1.5, average_neck=None)

    def test_save_measured_values_and_null_risk(self):
        with patch.object(APIClient, "post", return_value=response(201, {"session_id": 7})) as post:
            self.assertEqual(save_session_summary(self.summary)["status"], "SAVED")
            payload = post.call_args.args[1]
            self.assertEqual(payload["detection_count"], 10)
            self.assertEqual(payload["average_shoulder"], -1.5)
            self.assertIsNone(payload["average_risk_score"])
            self.assertIsNone(payload["rula_final_score"])
            self.assertIsNone(payload["average_neck"])

    def test_save_measured_prototype_risk_and_blink_rate(self):
        summary = {
            **self.summary,
            "average_risk_score": 1.25,
            "maximum_risk_score": 3.0,
            "blink_rate": 14.0,
            "rula_final_score": 5,
            "rula_action_level": 3,
        }
        with patch.object(
            APIClient,
            "post",
            return_value=response(201, {"session_id": 7}),
        ) as post:
            save_session_summary(summary)

        payload = post.call_args.args[1]
        self.assertEqual(payload["average_risk_score"], 1.25)
        self.assertEqual(payload["maximum_risk_score"], 3.0)
        self.assertEqual(payload["blink_rate"], 14.0)
        self.assertEqual(payload["rula_final_score"], 5)
        self.assertEqual(payload["rula_action_level"], 3)

    def test_retry_after_lost_response_reads_existing_report(self):
        saved = {"session_id": 7, "detection_count": 10}
        with patch.object(APIClient, "post", side_effect=[requests.Timeout(), response(409, {})]), patch.object(APIClient, "get", return_value=response(200, saved)):
            with self.assertRaises(requests.Timeout):
                save_session_summary(self.summary)
            result = save_session_summary(self.summary)
            self.assertEqual(result, {"status": "ALREADY_EXISTS", "summary": saved})

    def test_reject_unfinished_or_invalid_data(self):
        for change in (
            {"database_status": "RUNNING"},
            {"face_detected_count": 11},
            {"average_neck": float("nan")},
            {"detection_count": True},
            {"average_risk_score": -0.1},
            {"maximum_risk_score": 3.1},
            {"average_risk_score": 2.0, "maximum_risk_score": 1.0},
            {"blink_rate": -1.0},
            {"rula_final_score": 0, "rula_action_level": 1},
            {"rula_final_score": 5, "rula_action_level": 2},
            {"rula_final_score": 5, "rula_action_level": None},
        ):
            with self.subTest(change=change), patch.object(APIClient, "post") as post:
                with self.assertRaises(ValueError):
                    save_session_summary({**self.summary, **change})
                post.assert_not_called()

    def test_load_missing_failed_or_wrong_report(self):
        for status, data in ((200, {"session_id": 8}), (200, []), (500, {})):
            with self.subTest(status=status, data=data), patch.object(APIClient, "get", return_value=response(status, data)):
                with self.assertRaises((ValueError, RuntimeError)):
                    load_session_summary(7)
        with patch.object(APIClient, "get", return_value=response(404, {})):
            self.assertIsNone(load_session_summary(7))

    def test_bad_save_response_is_not_success(self):
        with patch.object(APIClient, "post", return_value=response(201, [])):
            with self.assertRaises(ValueError):
                save_session_summary(self.summary)


if __name__ == "__main__":
    unittest.main()
