import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.session_summary_page import SessionSummaryPage
from app.services.api_client import APIClient


class SavedReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.session = dict(session_id=7, status="COMPLETED", camera_id=1, baseline_id=2, total_duration=120)
        self.saved = dict(session_id=7, detection_count=12, pose_detected_count=10, face_detected_count=9, average_shoulder=-1.5, average_neck=None)

    def test_saved_report_uses_persisted_values_and_disables_save(self):
        with patch.object(APIClient, "get_session_alerts", return_value=Mock(ok=True, json=lambda: [])), patch.object(APIClient, "post") as post:
            page = SessionSummaryPage()
            page.set_saved_report(self.session, self.saved)
            self.assertEqual(page.count_label.text(), "Detection Cycles: 12")
            self.assertIn("-1.50", page.shoulder_label.text())
            self.assertEqual(page.neck_label.text(), "Average Neck: N/A")
            self.assertFalse(page.retry_button.isEnabled())
            self.assertIn("Loaded", page.save_status_label.text())
            post.assert_not_called()
            page.deleteLater()

    def test_history_load_select_and_open(self):
        with patch.object(APIClient, "get", return_value=Mock(ok=True, json=lambda: [self.session])):
            page = HistoryPage()
            page.load_sessions()
        page.table.selectRow(0)
        self.assertTrue(page.report_button.isEnabled())
        with patch("app.ui.pages.history_page.load_session_summary", return_value=self.saved) as load, patch.object(APIClient, "get_session_alerts", return_value=Mock(ok=True, json=lambda: [])), patch("app.ui.pages.history_page.QDialog.exec", return_value=0):
            page.open_saved_report()
            load.assert_called_once_with(7)
        report_dialogs = page.findChildren(QDialog)
        self.assertTrue(report_dialogs)
        self.assertIn("QDialog", report_dialogs[-1].styleSheet())
        self.assertTrue(page.report_button.isEnabled())
        page.deleteLater()

    def test_missing_report_and_refresh_failure(self):
        page = HistoryPage()
        with patch.object(APIClient, "get", return_value=Mock(ok=True, json=lambda: [self.session])):
            page.load_sessions()
        page.table.selectRow(0)
        with patch("app.ui.pages.history_page.load_session_summary", return_value=None), patch("app.ui.pages.history_page.QMessageBox.information") as notice:
            page.open_saved_report()
            notice.assert_called_once()
        with patch.object(APIClient, "get", return_value=Mock(ok=False, status_code=503, text="Unavailable")), patch("app.ui.pages.history_page.QMessageBox.warning"):
            page.load_sessions()
        self.assertEqual(page.table.rowCount(), 0)
        self.assertFalse(page.report_button.isEnabled())
        page.deleteLater()


if __name__ == "__main__":
    unittest.main()
