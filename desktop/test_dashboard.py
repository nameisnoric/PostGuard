import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.ui.pages.dashboard_page import DashboardPage, active_seconds
from app.services.api_client import APIClient


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = DashboardPage({"username": "Test User"})
        self.addCleanup(self.page.deleteLater)

    def test_totals_exclude_pauses_and_incomplete_sessions(self):
        self.page._loaded([
            dict(session_id=3, status="RUNNING", total_duration=999, paused_duration=0),
            dict(session_id=2, status="INTERRUPTED", total_duration=None, paused_duration=None),
            dict(session_id=1, status="COMPLETED", total_duration=3600, paused_duration=600),
        ], "")
        self.assertEqual(self.page.completed_value.text(), "1")
        self.assertEqual(self.page.time_value.text(), "00:50:00")
        self.assertEqual(self.page.interrupted_value.text(), "1")
        self.assertEqual(self.page.recent_table.item(0, 3).text(), "N/A")

    def test_missing_duration_is_not_zero(self):
        self.page._loaded([dict(status="COMPLETED", total_duration=100)], "")
        self.assertEqual(self.page.time_value.text(), "N/A")
        self.assertIn("excluded", self.page.data_status.text())
        self.assertIsNone(active_seconds(dict(status="COMPLETED", total_duration=20, paused_duration=30)))

    def test_empty_and_error_states(self):
        self.page._loaded([], "")
        self.assertEqual(self.page.completed_value.text(), "0")
        self.assertEqual(self.page.time_value.text(), "00:00:00")
        self.page._loaded(None, "Offline; retry")
        self.assertEqual(self.page.completed_value.text(), "--")
        self.assertEqual(self.page.recent_table.rowCount(), 0)
        self.assertEqual(self.page.data_status.text(), "Offline; retry")

    def test_live_state_and_actions(self):
        monitor, history = Mock(), Mock()
        self.page.monitor_requested.connect(monitor)
        self.page.history_requested.connect(history)
        self.page.set_monitoring_state(9, paused=True)
        self.assertIn("Paused", self.page.live_label.text())
        self.assertEqual(self.page.monitor_button.text(), "Return to Monitoring")
        self.page.monitor_button.click()
        self.page.history_button.click()
        monitor.assert_called_once()
        history.assert_called_once()
        self.page.set_monitoring_state(9, stopping=True)
        self.assertFalse(self.page.monitor_button.isEnabled())

    def test_async_refresh_and_prevent_duplicate_request(self):
        with patch.object(APIClient, "get_sessions", return_value=Mock(ok=True, json=lambda: [])) as get:
            self.page.refresh()
            self.page.refresh()
            for _ in range(40):
                if self.page._loader is None:
                    break
                QTest.qWait(25)
            self.assertIsNone(self.page._loader)
            get.assert_called_once()
            self.assertTrue(self.page.refresh_button.isEnabled())
            self.assertEqual(self.page.completed_value.text(), "0")

    def test_recent_table_limited_to_five(self):
        self.page._loaded([dict(session_id=i, status="COMPLETED", total_duration=10, paused_duration=0) for i in range(8)], "")
        self.assertEqual(self.page.recent_table.rowCount(), 5)
        self.assertEqual(self.page.completed_value.text(), "8")


if __name__ == "__main__":
    unittest.main()
