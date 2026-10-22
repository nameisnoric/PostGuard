import os
import unittest

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

from PySide6.QtWidgets import QApplication

from app.ui.pages.monitoring_page import (
    MonitoringPage,
)


class PostureAlertPopupTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or
            QApplication([])
        )

    def setUp(self):
        self.page = MonitoringPage()

        self.addCleanup(
            self.page.deleteLater
        )

    def test_alert_policy_notification_shows_non_blocking_popup(
        self,
    ):
        self.page.apply_notification_settings({
            "notifications_enabled": True,
            "sound_enabled": False,
        })

        shown = (
            self.page.show_posture_alert(
                risk_level="MODERATE",
                alert_type="FIRST",
                factors=[
                    "RIGHT_SHOULDER_HIGH",
                ],
                duration_seconds=60.0,
            )
        )

        self.assertTrue(
            shown
        )

        self.assertIsNotNone(
            self.page.alert_popup
        )

        self.assertTrue(
            self.page.alert_popup.isVisible()
        )

        self.assertFalse(
            self.page.alert_popup.isModal()
        )

        self.assertIn(
            "60.0",
            self.page.alert_popup
            .duration_label
            .text(),
        )

        self.assertIn(
            "ปานกลาง",
            self.page.alert_popup
            .risk_label
            .text(),
        )

        self.page.alert_popup.close()

    def test_disabled_notifications_do_not_show_popup(
        self,
    ):
        self.page.apply_notification_settings({
            "notifications_enabled": False,
        })

        shown = (
            self.page.show_posture_alert(
                risk_level="MODERATE",
                alert_type="FIRST",
                factors=[
                    "TILT_LEFT",
                ],
                duration_seconds=60.0,
            )
        )

        self.assertFalse(
            shown
        )

        self.assertIsNone(
            self.page.alert_popup
        )

    def test_disabling_notifications_closes_visible_popup(
        self,
    ):
        self.page.apply_notification_settings({
            "notifications_enabled": True,
            "sound_enabled": False,
        })

        self.assertTrue(
            self.page.show_posture_alert(
                risk_level="HIGH",
                alert_type="ESCALATION",
                factors=[
                    "RIGHT_SHOULDER_HIGH",
                    "FLEXION",
                ],
                duration_seconds=75.0,
            )
        )

        popup = (
            self.page.alert_popup
        )

        self.page.apply_notification_settings({
            "notifications_enabled": False,
        })

        self.assertIsNone(
            self.page.alert_popup
        )

        self.assertFalse(
            popup.isVisible()
        )


if __name__ == "__main__":
    unittest.main()