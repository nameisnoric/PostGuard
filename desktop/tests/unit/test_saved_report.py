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
        self.session = dict(
            session_id=7,
            status="COMPLETED",
            camera_id=1,
            baseline_id=2,
            total_duration=120,
            paused_duration=20,
            pause_count=1,
            started_at="2026-10-15T04:48:28Z",
            ended_at="2026-10-15T04:50:28Z",
        )
        self.saved = dict(
            session_id=7,
            detection_count=12,
            pose_detected_count=10,
            face_detected_count=9,
            average_shoulder=-1.5,
            average_neck=None,
            average_risk_score=None,
            maximum_risk_score=None,
            risk_score_method="RULA_ADAPTED_FRONT_V1",
            blink_rate=None,
            total_alert_count=2,
            most_frequent_alert_event="NECK_LATERAL_TILT",
            low_risk_alert_count=0,
            medium_risk_alert_count=2,
            high_risk_alert_count=0,
            low_risk_duration=0,
            medium_risk_duration=30,
            high_risk_duration=0,
        )

    def test_saved_report_uses_persisted_values_and_disables_save(self):
        with patch.object(APIClient, "get_session_alerts", return_value=Mock(ok=True, json=lambda: [])), patch.object(APIClient, "post") as post:
            page = SessionSummaryPage()
            page.set_saved_report(self.session, self.saved)
            self.assertEqual(page.count_label.text(), "รอบการตรวจจับ: 12")
            self.assertIn("-1.50", page.shoulder_label.text())
            self.assertEqual(page.neck_label.text(), "ความเอียงคอเฉลี่ย: N/A")
            self.assertEqual(page.duration_label.text(), "ระยะเวลารวม: 00:02:00")
            self.assertEqual(page.paused_duration_label.text(), "เวลาหยุดชั่วคราว: 00:00:20")
            self.assertIn("Neck Lateral Tilt", page.frequent_event_label.text())
            self.assertEqual(
                page.average_risk_label.text(),
                "คะแนนความเสี่ยงเฉลี่ย: N/A (RULA-adapted Front Camera)",
            )
            self.assertFalse(page.retry_button.isEnabled())
            self.assertIn("โหลดรายงาน", page.save_status_label.text())
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

    def test_history_filters_and_marks_report_availability(self):
        interrupted = dict(
            session_id=8,
            status="INTERRUPTED",
            camera_id=2,
            baseline_id=3,
            total_duration=None,
        )
        sessions_response = Mock(ok=True, json=lambda: [self.session, interrupted])
        reports_response = Mock(ok=True, json=lambda: [self.saved])
        with patch.object(
            APIClient,
            "get_sessions",
            return_value=sessions_response,
        ), patch.object(
            APIClient,
            "get_session_summaries",
            return_value=reports_response,
        ):
            page = HistoryPage()
            page.load_sessions()

        self.assertEqual(page.total_value.text(), "2")
        self.assertEqual(page.reports_value.text(), "1")
        self.assertEqual(page.table.item(0, 5).text(), "Saved")
        page.status_filter.setCurrentIndex(page.status_filter.findData("INTERRUPTED"))
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 0).text(), "#8")
        page.deleteLater()


if __name__ == "__main__":
    unittest.main()
