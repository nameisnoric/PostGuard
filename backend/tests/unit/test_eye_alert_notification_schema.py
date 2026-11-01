import unittest
from pydantic import ValidationError
from app.schemas.eye_alert_notification import EyeAlertNotificationCreate


class EyeAlertNotificationSchemaTests(unittest.TestCase):
    def test_first(self):
        value = EyeAlertNotificationCreate(
            alert_type="FIRST",
            blink_rate=4.0,
            window_blink_count=4,
            reason="LOW_BLINK_CONFIRMED",
        )
        self.assertEqual(value.alert_type, "FIRST")

    def test_repeat(self):
        value = EyeAlertNotificationCreate(
            alert_type="REPEAT",
            blink_rate=5.2,
            window_blink_count=5,
        )
        self.assertEqual(value.alert_type, "REPEAT")

    def test_negative_rate_rejected(self):
        with self.assertRaises(ValidationError):
            EyeAlertNotificationCreate(
                alert_type="FIRST",
                blink_rate=-1.0,
                window_blink_count=0,
            )

    def test_negative_count_rejected(self):
        with self.assertRaises(ValidationError):
            EyeAlertNotificationCreate(
                alert_type="FIRST",
                blink_rate=0.0,
                window_blink_count=-1,
            )

    def test_escalation_rejected(self):
        with self.assertRaises(ValidationError):
            EyeAlertNotificationCreate(
                alert_type="ESCALATION",
                blink_rate=4.0,
                window_blink_count=4,
            )


if __name__ == "__main__":
    unittest.main()
