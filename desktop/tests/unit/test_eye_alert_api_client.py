import unittest
from unittest.mock import patch

from app.services.api_client import APIClient


class EyeAlertAPIClientTests(unittest.TestCase):
    def test_runtime_notification_id_is_sent_to_backend(self):
        with patch.object(APIClient, "post") as post:
            APIClient.create_eye_alert_notification(
                session_id=51,
                runtime_notification_id="eye-runtime-1",
                alert_type="FIRST",
                blink_rate=4.0,
                window_blink_count=4,
                reason="LOW_BLINK_CONFIRMED",
            )

        post.assert_called_once_with(
            "/sessions/51/eye-alert-notifications",
            {
                "runtime_notification_id": "eye-runtime-1",
                "alert_type": "FIRST",
                "blink_rate": 4.0,
                "window_blink_count": 4,
                "decision": "ALERT",
                "reason": "LOW_BLINK_CONFIRMED",
            },
        )


if __name__ == "__main__":
    unittest.main()
