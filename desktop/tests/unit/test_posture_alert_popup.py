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
        self.page.alert_service = Mock()
        self.page.alert_service.update.return_value = {
            "created": [{
                "event_type": "NECK_LATERAL_TILT",
                "factor": "NECK_LATERAL_RIGHT",
                "duration_seconds": 60.0,
                "risk_level": "MEDIUM",
                "event_id": 44,
            }],
            "ended": [],
            "errors": [],
        }
        self.page.alert_service.has_active_alerts = True
        self.page.apply_notification_settings({"notifications_enabled": True})

        self.page.update_partial_risk({
            "assessment": {
                "status": "COMPLETE",
                "factors": [{"factor": "NECK_LATERAL_RIGHT"}],
            },
            "temporal": {
                "active_factors": [{
                    "feature": "neck_lateral_tilt",
                    "continuous_seconds": 60.0,
                }],
            },
            "risk": {
                "status": "EVALUATED",
                "risk_level": "MODERATE",
                "prototype_score": 2.0,
            },
            "measurement_change": {"features": {}},
        })

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
