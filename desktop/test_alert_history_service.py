import unittest
from app.services.alert_history_service import summarize_alerts, validate_session_id


class AlertHistoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.alerts = [
            {"event_id": 11, "event_type": "NECK_LATERAL_TILT", "duration": 4, "ended_at": "2026-10-10T16:12:09+07:00"},
            {"event_id": 12, "event_type": "NECK_LATERAL_TILT", "duration": 26, "ended_at": "2026-10-10T16:13:35+07:00"},
        ]

    def test_user_example(self):
        result = summarize_alerts(self.alerts)
        self.assertEqual(result["total_alerts"], 2)
        self.assertEqual(result["closed_alerts"], 2)
        self.assertEqual(result["closed_alert_seconds"], 30)

    def test_empty(self):
        self.assertEqual(summarize_alerts([])["total_alerts"], 0)

    def test_active_not_counted_as_closed_duration(self):
        alert = dict(self.alerts[0], ended_at=None, duration=0)
        result = summarize_alerts([alert])
        self.assertEqual(result["active_alerts"], 1)
        self.assertEqual(result["closed_alert_seconds"], 0)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            summarize_alerts([self.alerts[0], self.alerts[0]])

    def test_invalid_duration_rejected(self):
        with self.assertRaises(ValueError):
            summarize_alerts([dict(self.alerts[0], duration=-1)])

    def test_invalid_session_id_rejected(self):
        for invalid in (0, -1, True, "10"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_session_id(invalid)


if __name__ == "__main__":
    unittest.main()
