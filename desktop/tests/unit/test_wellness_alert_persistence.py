import unittest
from unittest.mock import Mock

import requests

from app.services.wellness_alert_persistence import WellnessAlertPersistence


def response(data=None, status=200):
    return Mock(
        ok=status < 400,
        status_code=status,
        json=lambda: data,
        text="test",
    )


class WellnessAlertPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.client = Mock()
        self.persistence = WellnessAlertPersistence(
            client=self.client,
            clock=lambda: self.now,
        )

    @staticmethod
    def policy(active, action="STARTED"):
        return {
            "events": [{
                "event_type": "SCREEN_DISTANCE",
                "active": active,
                "action": action,
            }],
        }

    def test_episode_is_created_once_and_closed_on_resolution(self):
        self.client.create_alert_event.return_value = response({"event_id": 7}, 201)
        self.client.end_alert_event.return_value = response({"event_id": 7})

        self.persistence.update(3, self.policy(True))
        self.persistence.update(3, self.policy(True, "UPDATED"))
        self.persistence.update(3, self.policy(False, "RESOLVED"))

        self.client.create_alert_event.assert_called_once_with(
            3, "SCREEN_DISTANCE", "MEDIUM"
        )
        self.client.end_alert_event.assert_called_once_with(7)
        self.assertEqual(self.persistence.event_ids, {})

    def test_create_timeout_recovers_existing_active_episode(self):
        self.client.create_alert_event.side_effect = requests.ConnectionError("timeout")
        self.client.get_session_alerts.return_value = response([{
            "event_id": 8,
            "event_type": "SCREEN_DISTANCE",
            "ended_at": None,
        }])

        self.persistence.update(3, self.policy(True))

        self.assertEqual(self.persistence.event_ids["SCREEN_DISTANCE"], 8)
        self.assertIsNone(self.persistence.last_error)

    def test_failed_create_retries_after_cooldown(self):
        self.client.create_alert_event.side_effect = [
            requests.ConnectionError("offline"),
            response({"event_id": 9}, 201),
        ]
        self.client.get_session_alerts.side_effect = requests.ConnectionError("offline")

        self.persistence.update(3, self.policy(True))
        self.assertIsNotNone(self.persistence.last_error)
        self.now = 4.9
        self.persistence.update(3, self.policy(True, "UPDATED"))
        self.assertEqual(self.client.create_alert_event.call_count, 1)
        self.now = 5.0
        self.persistence.update(3, self.policy(True, "UPDATED"))

        self.assertEqual(self.persistence.event_ids["SCREEN_DISTANCE"], 9)
        self.assertIsNone(self.persistence.last_error)

    def test_eye_first_notification_is_saved_once_with_stable_retry_id(self):
        self.client.create_alert_event.return_value = response({"event_id": 10}, 201)
        self.client.create_eye_alert_notification.side_effect = [
            requests.ConnectionError("offline"),
            response({"eye_notification_id": 4}, 201),
        ]
        policy = self.policy(True)
        policy["notification"] = {
            "event_type": "LOW_BLINK_RATE",
            "alert_type": "FIRST",
            "value": 5.0,
            "window_blink_count": 5,
        }
        policy["events"][0]["event_type"] = "LOW_BLINK_RATE"

        self.persistence.update(3, policy)
        first_id = self.client.create_eye_alert_notification.call_args.args[1]
        self.assertEqual(len(self.persistence.pending_eye_notifications), 1)
        self.now = 5.0
        self.persistence.update(3, {"events": []})

        second_id = self.client.create_eye_alert_notification.call_args.args[1]
        self.assertEqual(first_id, second_id)
        self.assertEqual(self.persistence.pending_eye_notifications, [])

    def test_flush_forces_queued_eye_notification_retry(self):
        self.client.create_alert_event.return_value = response({"event_id": 10}, 201)
        self.client.create_eye_alert_notification.side_effect = [
            requests.ConnectionError("offline"),
            response({"eye_notification_id": 4}, 201),
        ]
        policy = self.policy(True)
        policy["events"][0]["event_type"] = "LOW_BLINK_RATE"
        policy["notification"] = {
            "event_type": "LOW_BLINK_RATE", "alert_type": "FIRST",
            "value": 5.0, "window_blink_count": 5,
        }
        self.persistence.update(3, policy)

        self.assertTrue(self.persistence.flush(3))
        self.assertEqual(self.persistence.pending_eye_notifications, [])

    def test_disabled_notifications_keep_episode_without_saving_reminder(self):
        self.client.create_alert_event.return_value = response({"event_id": 10}, 201)
        policy = self.policy(True)
        policy["events"][0]["event_type"] = "LOW_BLINK_RATE"
        policy["notification"] = {
            "event_type": "LOW_BLINK_RATE", "alert_type": "FIRST",
            "value": 5.0, "window_blink_count": 5,
        }

        self.persistence.update(3, policy, persist_notifications=False)

        self.client.create_alert_event.assert_called_once()
        self.client.create_eye_alert_notification.assert_not_called()
        self.assertEqual(self.persistence.pending_eye_notifications, [])

    def test_screen_distance_first_notification_is_persisted(self):
        self.client.create_alert_event.return_value = response({"event_id": 11}, 201)
        self.client.create_screen_distance_notification.return_value = response(
            {"screen_notification_id": 2}, 201
        )
        policy = self.policy(True)
        policy["notification"] = {
            "event_type": "SCREEN_DISTANCE", "alert_type": "FIRST",
            "value": 1.42,
        }

        self.persistence.update(3, policy)

        args = self.client.create_screen_distance_notification.call_args.args
        self.assertEqual(args[0], 3)
        self.assertEqual(args[2:], ("FIRST", 1.42, "SCREEN_DISTANCE_CONFIRMED"))
        self.assertEqual(self.persistence.pending_screen_notifications, [])


if __name__ == "__main__":
    unittest.main()
