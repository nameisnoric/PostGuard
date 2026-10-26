import os
import unittest
import requests

from unittest.mock import (
    Mock,
    patch,
)

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

from PySide6.QtWidgets import (
    QApplication,
)

from app.services.api_client import (
    APIClient,
)
from app.ui.pages.history_page import (
    HistoryPage,
)
from app.ui.pages.session_summary_page import (
    SessionSummaryPage,
)


class SavedReportTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or
            QApplication([])
        )

    def setUp(
        self,
    ):
        self.session = {
            "session_id": 7,
            "status": "COMPLETED",
            "camera_id": 1,
            "baseline_id": 2,
            "total_duration": 120,
            "paused_duration": 20,
            "pause_count": 1,
            "started_at": (
                "2026-10-15T04:48:28Z"
            ),
            "ended_at": (
                "2026-10-15T04:50:28Z"
            ),
        }

        self.saved = {
            "session_id": 7,

            "detection_count": 12,
            "pose_detected_count": 10,
            "face_detected_count": 9,

            "average_shoulder": -1.5,
            "average_neck": None,

            "average_risk_score": 21.25,
            "minimum_risk_score": 0.0,
            "maximum_risk_score": 83.0,

            "risk_score_method": (
                "POSTGUARD_MODIFIED_RULA_FRONT_VIEW_V1"
            ),

            "blink_rate": None,

            "total_alert_count": 2,

            "most_frequent_alert_event": (
                "NECK_LATERAL_TILT"
            ),

            "low_risk_alert_count": 0,
            "medium_risk_alert_count": 2,
            "high_risk_alert_count": 0,

            "low_risk_duration": 0,
            "medium_risk_duration": 30,
            "high_risk_duration": 0,
        }

    # ========================================================
    # SESSION SUMMARY
    # ========================================================

    def test_saved_report_uses_persisted_values_and_disables_save(
        self,
    ):
        with (
            patch.object(
                APIClient,
                "get_session_risk_events",
                return_value=Mock(
                    ok=True,
                    json=lambda: [],
                ),
            ),
            patch.object(
                APIClient,
                "get_session_alert_notifications",
                return_value=Mock(
                    ok=True,
                    json=lambda: [],
                ),
            ),
            patch(
                (
                    "app.ui.pages."
                    "session_summary_page."
                    "load_session_risk_score_buckets"
                ),
                return_value=[],
            ),
            patch.object(
                APIClient,
                "post",
            ) as post,
        ):
            page = (
                SessionSummaryPage()
            )

            page.set_saved_report(
                self.session,
                self.saved,
            )

            self.assertEqual(
                page.count_label.text(),
                "รอบการตรวจจับ: 12",
            )

            self.assertIn(
                "-1.50",
                page.shoulder_label.text(),
            )

            self.assertEqual(
                page.neck_label.text(),
                "ความเอียงคอเฉลี่ย: N/A",
            )

            self.assertEqual(
                page.duration_label.text(),
                "ระยะเวลารวม: 00:02:00",
            )

            self.assertEqual(
                page.paused_duration_label.text(),
                "เวลาหยุดชั่วคราว: 00:00:20",
            )

            self.assertEqual(
                page.average_risk_label.text(),
                "คะแนนความเสี่ยงเฉลี่ย: 21.25",
            )

            self.assertEqual(
                page.minimum_risk_label.text(),
                "คะแนนความเสี่ยงต่ำสุด: 0.00",
            )

            self.assertEqual(
                page.maximum_risk_label.text(),
                "คะแนนความเสี่ยงสูงสุด: 83.00",
            )

            self.assertFalse(
                page.retry_button.isEnabled()
            )

            self.assertIn(
                "โหลดรายงาน",
                page.save_status_label.text(),
            )

            post.assert_not_called()

            page.deleteLater()

    # ========================================================
    # HISTORY LOAD
    # ========================================================

    def test_history_loads_risk_scores_into_table(
        self,
    ):
        sessions_response = Mock(
            ok=True,
            json=lambda: [
                self.session
            ],
        )

        reports_response = Mock(
            ok=True,
            json=lambda: [
                self.saved
            ],
        )

        with (
            patch.object(
                APIClient,
                "get_sessions",
                return_value=(
                    sessions_response
                ),
            ),
            patch.object(
                APIClient,
                "get_session_summaries",
                return_value=(
                    reports_response
                ),
            ),
        ):
            page = HistoryPage()

            page.load_sessions()

        self.assertEqual(
            page.total_value.text(),
            "1",
        )

        self.assertEqual(
            page.reports_value.text(),
            "1",
        )

        self.assertEqual(
            page.table.item(
                0,
                4,
            ).text(),
            "21.25",
        )

        self.assertEqual(
            page.table.item(
                0,
                5,
            ).text(),
            "83.00",
        )

        self.assertEqual(
            page.table.item(
                0,
                6,
            ).text(),
            "Saved",
        )

        page.deleteLater()

    # ========================================================
    # DETAILS
    # ========================================================

    def test_history_selection_shows_risk_details(
        self,
    ):
        with (
            patch.object(
                APIClient,
                "get_sessions",
                return_value=Mock(
                    ok=True,
                    json=lambda: [
                        self.session
                    ],
                ),
            ),
            patch.object(
                APIClient,
                "get_session_summaries",
                return_value=Mock(
                    ok=True,
                    json=lambda: [
                        self.saved
                    ],
                ),
            ),
        ):
            page = HistoryPage()

            page.load_sessions()

        page.table.selectRow(
            0
        )

        self.assertEqual(
            page.detail_values[
                "avg_risk"
            ].text(),
            "21.25",
        )

        self.assertEqual(
            page.detail_values[
                "min_risk"
            ].text(),
            "0.00",
        )

        self.assertEqual(
            page.detail_values[
                "max_risk"
            ].text(),
            "83.00",
        )

        self.assertEqual(
            page.detail_values[
                "alerts"
            ].text(),
            "2",
        )

        self.assertTrue(
            page.report_button.isEnabled()
        )

        page.deleteLater()

    # ========================================================
    # OPEN SAVED REPORT
    # ========================================================

    def test_history_opens_shared_saved_report_dialog(
        self,
    ):
        with (
            patch.object(
                APIClient,
                "get_sessions",
                return_value=Mock(
                    ok=True,
                    json=lambda: [
                        self.session
                    ],
                ),
            ),
            patch.object(
                APIClient,
                "get_session_summaries",
                return_value=Mock(
                    ok=True,
                    json=lambda: [
                        self.saved
                    ],
                ),
            ),
        ):
            page = HistoryPage()

            page.load_sessions()

        page.table.selectRow(
            0
        )

        with (
            patch(
                (
                    "app.ui.pages.history_page."
                    "load_session_summary"
                ),
                return_value=self.saved,
            ) as load,
            patch(
                (
                    "app.ui.pages.history_page."
                    "SavedSessionReportDialog"
                )
            ) as dialog_class,
        ):
            page.open_saved_report()

            load.assert_called_once_with(
                7
            )

            dialog_class.assert_called_once_with(
                session=self.session,
                saved_summary=self.saved,
                parent=page,
            )

            dialog_class.return_value.exec.assert_called_once()

        page.deleteLater()

    # ========================================================
    # MISSING REPORT
    # ========================================================

    def test_missing_report_is_handled(
        self,
    ):
        with (
            patch.object(
                APIClient,
                "get_sessions",
                return_value=Mock(
                    ok=True,
                    json=lambda: [
                        self.session
                    ],
                ),
            ),
            patch.object(
                APIClient,
                "get_session_summaries",
                return_value=Mock(
                    ok=True,
                    json=lambda: [
                        self.saved
                    ],
                ),
            ),
        ):
            page = HistoryPage()

            page.load_sessions()

        page.table.selectRow(
            0
        )

        with (
            patch(
                (
                    "app.ui.pages.history_page."
                    "load_session_summary"
                ),
                return_value=None,
            ),
            patch(
                (
                    "app.ui.pages.history_page."
                    "QMessageBox.information"
                )
            ) as notice,
        ):
            page.open_saved_report()

            notice.assert_called_once()

        page.deleteLater()

    # ========================================================
    # REPORT INDEX FAILURE
    # ========================================================

    def test_summary_index_failure_keeps_session_history(
        self,
    ):
        with (
            patch.object(
                APIClient,
                "get_sessions",
                return_value=Mock(
                    ok=True,
                    json=lambda: [
                        self.session
                    ],
                ),
            ),
            patch.object(
                APIClient,
                "get_session_summaries",
                side_effect=(
                    requests.Timeout()
                ),
            ),
        ):
            page = HistoryPage()

            page.load_sessions()

        self.assertEqual(
            page.table.rowCount(),
            1,
        )

        self.assertEqual(
            page.table.item(
                0,
                4,
            ).text(),
            "N/A",
        )

        self.assertEqual(
            page.reports_value.text(),
            "N/A",
        )

        page.deleteLater()


if __name__ == "__main__":
    unittest.main()