import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.api_client import APIClient
from app.ui.dialogs.alert_history_dialog import AlertHistoryDialog


def response(data, status=200):
    return Mock(
        ok=status < 400,
        status_code=status,
        json=lambda: data,
        text="test",
    )


class AlertHistoryDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_dialog(self, alerts):
        sessions = [
            {"session_id": 11, "status": "COMPLETED", "started_at": "2026-10-15T04:41:46Z"},
            {"session_id": 12, "status": "COMPLETED", "started_at": "2026-10-15T04:48:28Z"},
        ]
        with patch.object(APIClient, "get_sessions", return_value=response(sessions)), patch.object(
            APIClient, "get_session_alerts", return_value=response(alerts)
        ):
            dialog = AlertHistoryDialog(session_id=12)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_selected_session_and_empty_state_are_visible(self):
        dialog = self.make_dialog([])
        self.assertEqual(dialog.session_selector.currentData(), 12)
        self.assertTrue(dialog.empty_label.isVisibleTo(dialog))
        self.assertTrue(dialog.table.isHidden())
        self.assertIn("Total: 0", dialog.stats_label.text())

    def test_alert_rows_are_rendered(self):
        alerts = [{
            "event_id": 4,
            "event_type": "NECK_LATERAL_TILT",
            "risk_level": "MEDIUM",
            "started_at": "2026-10-15T04:50:00Z",
            "ended_at": "2026-10-15T04:51:00Z",
            "duration": 60,
            "incomplete": False,
        }]
        dialog = self.make_dialog(alerts)
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertFalse(dialog.table.isHidden())
        self.assertEqual(dialog.table.item(0, 1).text(), "Neck Lateral Tilt")
        self.assertEqual(dialog.table.item(0, 5).text(), "00:01:00")


if __name__ == "__main__":
    unittest.main()
