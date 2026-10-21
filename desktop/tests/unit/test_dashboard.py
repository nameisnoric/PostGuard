import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.services.api_client import APIClient
from app.ui.pages.dashboard_page import (
    DashboardPage,
    active_seconds,
    summary_insights,
)


def payload(sessions, summaries=None, report_error=""):
    return {
        "sessions": sessions,
        "summaries": summaries,
        "report_error": report_error,
    }


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = DashboardPage({"username": "Test User"})
        self.addCleanup(self.page.deleteLater)

    def test_totals_exclude_pauses_and_incomplete_sessions(self):
        sessions = [
            dict(session_id=3, status="RUNNING", total_duration=999, paused_duration=0),
            dict(session_id=2, status="INTERRUPTED", total_duration=None, paused_duration=None),
            dict(session_id=1, status="COMPLETED", total_duration=3600, paused_duration=600),
        ]
        self.page._loaded(payload(sessions, []), "")

        self.assertEqual(self.page.completed_value.text(), "1")
        self.assertEqual(self.page.time_value.text(), "00:50:00")
        self.assertEqual(self.page.interrupted_value.text(), "1")
        self.assertEqual(self.page.alerts_value.text(), "0")
        self.assertEqual(self.page.recent_table.item(0, 3).text(), "N/A")

    def test_report_metrics_and_recent_rows_use_saved_values(self):
        sessions = [dict(
            session_id=7,
            status="COMPLETED",
            total_duration=120,
            paused_duration=20,
            started_at="2026-10-22T12:00:00Z",
        )]
        summaries = [dict(
            session_id=7,
            average_risk_score=1.5,
            maximum_risk_score=3.0,
            rula_neck_score=5,
            blink_rate=14.0,
            total_alert_count=4,
        )]

        self.page._loaded(payload(sessions, summaries), "")

        self.assertEqual(self.page.risk_value.text(), "1.5 / 3")
        self.assertEqual(self.page.blink_value.text(), "14.0 / min")
        self.assertEqual(self.page.rula_value.text(), "≥5 / 6")
        self.assertEqual(self.page.alerts_value.text(), "4")
        self.assertEqual(self.page.recent_table.item(0, 4).text(), "1.5/3")
        self.assertEqual(self.page.recent_table.item(0, 5).text(), "≥5/6")
        self.assertEqual(self.page.recent_table.item(0, 6).text(), "4")

    def test_insights_ignore_missing_and_invalid_measurements(self):
        result = summary_insights([
            dict(average_risk_score=1.0, maximum_risk_score=2.0, rula_neck_score=4, blink_rate=10.0, total_alert_count=2),
            dict(average_risk_score=3.0, maximum_risk_score=3.0, rula_neck_score=6, blink_rate=20.0, total_alert_count=1),
            dict(average_risk_score=4.0, maximum_risk_score=-1.0, rula_neck_score=7, blink_rate=-2.0, total_alert_count=-1),
        ])

        self.assertEqual(result["average_risk"], 2.0)
        self.assertEqual(result["maximum_risk"], 3.0)
        self.assertEqual(result["maximum_rula_neck"], 6)
        self.assertEqual(result["average_blink_rate"], 15.0)
        self.assertEqual(result["total_alert_count"], 3)

    def test_missing_duration_is_not_zero(self):
        self.page._loaded(
            payload([dict(status="COMPLETED", total_duration=100)], []), ""
        )
        self.assertEqual(self.page.time_value.text(), "N/A")
        self.assertIn("ไม่มีข้อมูลระยะเวลา", self.page.data_status.text())
        self.assertIsNone(active_seconds(dict(
            status="COMPLETED", total_duration=20, paused_duration=30
        )))

    def test_empty_error_and_partial_report_states(self):
        self.page._loaded(payload([], []), "")
        self.assertEqual(self.page.completed_value.text(), "0")
        self.assertEqual(self.page.time_value.text(), "00:00:00")
        self.assertEqual(self.page.alerts_value.text(), "0")

        self.page._loaded(payload([], None, "unavailable"), "")
        self.assertEqual(self.page.alerts_value.text(), "N/A")
        self.assertIn("Report metrics", self.page.data_status.text())

        self.page._loaded(None, "Offline; retry")
        self.assertEqual(self.page.completed_value.text(), "--")
        self.assertEqual(self.page.alerts_value.text(), "--")
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
        with (
            patch.object(
                APIClient,
                "get_sessions",
                return_value=Mock(ok=True, json=lambda: []),
            ) as get_sessions,
            patch.object(
                APIClient,
                "get_session_summaries",
                return_value=Mock(ok=True, json=lambda: []),
            ) as get_summaries,
        ):
            self.page.refresh()
            self.page.refresh()
            for _ in range(40):
                if self.page._loader is None:
                    break
                QTest.qWait(25)

        self.assertIsNone(self.page._loader)
        get_sessions.assert_called_once()
        get_summaries.assert_called_once()
        self.assertTrue(self.page.refresh_button.isEnabled())
        self.assertEqual(self.page.completed_value.text(), "0")

    def test_recent_table_limited_to_five(self):
        sessions = [
            dict(
                session_id=index,
                status="COMPLETED",
                total_duration=10,
                paused_duration=0,
            )
            for index in range(8)
        ]
        self.page._loaded(payload(sessions, []), "")
        self.assertEqual(self.page.recent_table.rowCount(), 5)
        self.assertEqual(self.page.completed_value.text(), "8")


if __name__ == "__main__":
    unittest.main()
