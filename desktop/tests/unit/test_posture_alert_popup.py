import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.pages.monitoring_page import MonitoringPage


class PostureAlertPopupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = MonitoringPage()
        self.addCleanup(self.page.deleteLater)

    def test_created_alert_shows_one_non_blocking_popup(self):
        self.page.session_id = 12
        self.page.baseline_data = {"lateral_tilt_baseline": 0.0}
        self.page.posture_tracker.update = Mock(return_value=60.0)
        self.page.alert_service.update = Mock(return_value="created")
        self.page.alert_service.active_event_id = 44
        self.page.apply_notification_settings({"notifications_enabled": True})

        with patch(
            "app.ui.pages.monitoring_page.classify_neck_side_bending",
            return_value=1,
        ):
            self.page.update_partial_risk(
                {"neck_lateral_tilt": {"neck_tilt": 15.0}}
            )

        self.assertIsNotNone(self.page.alert_popup)
        self.assertTrue(self.page.alert_popup.isVisible())
        self.assertFalse(self.page.alert_popup.isModal())
        self.assertIn("60.0", self.page.alert_popup.duration_label.text())
        self.page.alert_popup.close()

    def test_disabled_notifications_do_not_show_popup(self):
        self.page.apply_notification_settings({"notifications_enabled": False})

        shown = self.page.show_posture_alert(direction=-1, seconds=60.0)

        self.assertFalse(shown)
        self.assertIsNone(self.page.alert_popup)

    def test_disabling_notifications_closes_visible_popup(self):
        self.page.apply_notification_settings({"notifications_enabled": True})
        self.assertTrue(self.page.show_posture_alert(direction=1, seconds=60.0))
        popup = self.page.alert_popup

        self.page.apply_notification_settings({"notifications_enabled": False})

        self.assertIsNone(self.page.alert_popup)
        self.assertFalse(popup.isVisible())


if __name__ == "__main__":
    unittest.main()
