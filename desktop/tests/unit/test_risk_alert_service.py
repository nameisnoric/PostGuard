import unittest
from unittest.mock import Mock

from app.services.risk_alert_service import RiskAlertService


def response(data, status=200):
    result = Mock()
    result.status_code = status
    result.ok = 200 <= status < 300
    result.json.return_value = data
    result.text = str(data)
    return result


def risk(level="MODERATE", seconds=60.0, active=True):
    return {
        "status": "EVALUATED",
        "risk_level": level,
        "feature_results": {
            "neck_lateral_tilt": {
                "active": active,
                "factor": "NECK_LATERAL_RIGHT" if active else None,
                "continuous_seconds": seconds,
            },
        },
    }


class RiskAlertServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.create_alert_event.return_value = response(
            {"event_id": 7, "event_type": "NECK_LATERAL_TILT"}, 201
        )
        self.client.end_alert_event.return_value = response(
            {"event_id": 7, "ended_at": "2026-10-22T00:00:00Z"}
        )
        self.service = RiskAlertService(client=self.client, clock=lambda: 100.0)

    def test_creates_one_alert_for_sustained_feature(self):
        first = self.service.update(3, risk())
        second = self.service.update(3, risk(seconds=65.0))

        self.assertEqual(len(first["created"]), 1)
        self.assertEqual(first["created"][0]["risk_level"], "MEDIUM")
        self.assertEqual(second["created"], [])
        self.client.create_alert_event.assert_called_once_with(
            3, "NECK_LATERAL_TILT", "MEDIUM"
        )

    def test_does_not_create_before_duration_threshold(self):
        result = self.service.update(3, risk(level="LOW", seconds=59.9))

        self.assertEqual(result["created"], [])
        self.client.create_alert_event.assert_not_called()

    def test_closes_alert_when_posture_clears(self):
        self.service.update(3, risk())

        result = self.service.update(3, risk(level="NONE", active=False))

        self.assertEqual(result["ended"], ["NECK_LATERAL_TILT"])
        self.assertFalse(self.service.has_active_alerts)
        self.client.end_alert_event.assert_called_once_with(7)

    def test_high_level_is_preserved_for_backend(self):
        self.service.update(3, risk(level="HIGH", seconds=70.0))

        self.client.create_alert_event.assert_called_once_with(
            3, "NECK_LATERAL_TILT", "HIGH"
        )


if __name__ == "__main__":
    unittest.main()
