"""Tests for asynchronous, idempotent risk persistence."""

import unittest
from unittest.mock import patch

import requests

from app.services.risk_persistence_service import RiskPersistenceService


class Response:
    ok = True
    status_code = 200
    text = ""

    @staticmethod
    def json():
        return {}


def pipeline_result(action="STARTED", notify=True):
    return {
        "assessment": {"factors": [{"factor": "neck_lateral_tilt"}]},
        "risk": {"evidence_groups": {"NECK": {"active": True}}},
        "risk_event": {
            "event_action": action,
            "current_risk_level": "MODERATE",
            "event_active": action != "RESOLVED",
            "event": None if action == "RESOLVED" else {
                "runtime_event_id": "risk-event-000001",
                "current_risk_level": "MODERATE",
            },
            "resolved_event": {
                "runtime_event_id": "risk-event-000001",
                "current_risk_level": "MODERATE",
            } if action == "RESOLVED" else None,
            "reason": "RISK_EVENT_RESOLVED" if action == "RESOLVED" else "ACTIVE",
        },
        "alert_policy": {
            "should_notify": notify,
            "alert_type": "FIRST",
            "current_risk_level": "MODERATE",
            "decision": "ALERT",
            "reason": "FIRST_NOTIFICATION",
        },
    }


class RiskPersistenceServiceTests(unittest.TestCase):
    def test_start_and_notification_are_serialized(self):
        calls = []
        service = RiskPersistenceService(max_attempts=1)
        with patch(
            "app.services.risk_persistence_service.APIClient.create_risk_event",
            side_effect=lambda *args: calls.append(("event", args)) or Response(),
        ), patch(
            "app.services.risk_persistence_service.APIClient.create_alert_notification",
            side_effect=lambda *args: calls.append(("notification", args)) or Response(),
        ):
            self.assertTrue(service.process_pipeline_result(4, pipeline_result()))
            self.assertTrue(service.flush())
        service.shutdown()
        self.assertEqual([call[0] for call in calls], ["event", "notification"])
        self.assertTrue(calls[1][1][2].startswith("notification-"))

    def test_updates_are_throttled(self):
        now = [10.0]
        service = RiskPersistenceService(clock=lambda: now[0], max_attempts=1)
        with patch(
            "app.services.risk_persistence_service.APIClient.update_risk_event",
            return_value=Response(),
        ) as update:
            self.assertTrue(service.process_pipeline_result(4, pipeline_result("UPDATED", False)))
            self.assertFalse(service.process_pipeline_result(4, pipeline_result("UPDATED", False)))
            now[0] += 5.0
            self.assertTrue(service.process_pipeline_result(4, pipeline_result("UPDATED", False)))
            self.assertTrue(service.flush())
        service.shutdown()
        self.assertEqual(update.call_count, 2)

    def test_retry_reuses_one_notification_key(self):
        keys = []
        attempts = [0]

        def notify(*args):
            keys.append(args[2])
            attempts[0] += 1
            if attempts[0] == 1:
                raise requests.ConnectionError("temporary")
            return Response()

        service = RiskPersistenceService(max_attempts=2)
        with patch(
            "app.services.risk_persistence_service.APIClient.create_risk_event",
            return_value=Response(),
        ), patch(
            "app.services.risk_persistence_service.APIClient.create_alert_notification",
            side_effect=notify,
        ):
            service.process_pipeline_result(4, pipeline_result())
            self.assertTrue(service.flush())
        service.shutdown()
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys[0], keys[1])


if __name__ == "__main__":
    unittest.main()
