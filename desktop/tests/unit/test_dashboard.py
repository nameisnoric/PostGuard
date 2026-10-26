import os
import unittest
from unittest.mock import (
    Mock,
    patch,
)

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

from PySide6.QtTest import (
    QTest,
)
from PySide6.QtWidgets import (
    QApplication,
)

from app.services.api_client import (
    APIClient,
)
from app.ui.pages.dashboard_page import (
    DashboardPage,
    active_seconds,
)


class DashboardTests(
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
        self.page = DashboardPage(
            {
                "username": (
                    "Test User"
                )
            }
        )

        self.addCleanup(
            self.page.deleteLater
        )

    def test_totals_exclude_pauses_and_incomplete_sessions(
        self,
    ):
        self.page._loaded(
            [
                {
                    "session_id": 3,
                    "status": "RUNNING",
                    "total_duration": 999,
                    "paused_duration": 0,
                },
                {
                    "session_id": 2,
                    "status": "INTERRUPTED",
                    "total_duration": None,
                    "paused_duration": None,
                },
                {
                    "session_id": 1,
                    "status": "COMPLETED",
                    "total_duration": 3600,
                    "paused_duration": 600,
                },
            ],
            [],
            "",
        )

        self.assertEqual(
            self.page.completed_value.text(),
            "1",
        )

        self.assertEqual(
            self.page.time_value.text(),
            "00:50:00",
        )

        self.assertEqual(
            self.page.interrupted_value.text(),
            "1",
        )

    def test_missing_duration_is_not_zero(
        self,
    ):
        self.page._loaded(
            [
                {
                    "session_id": 1,
                    "status": "COMPLETED",
                    "total_duration": 100,
                }
            ],
            [],
            "",
        )

        self.assertEqual(
            self.page.time_value.text(),
            "N/A",
        )

        self.assertIn(
            "ไม่รวม",
            self.page.data_status.text(),
        )

        self.assertIsNone(
            active_seconds(
                {
                    "status": "COMPLETED",
                    "total_duration": 20,
                    "paused_duration": 30,
                }
            )
        )

    def test_empty_and_error_states(
        self,
    ):
        self.page._loaded(
            [],
            [],
            "",
        )

        self.assertEqual(
            self.page.completed_value.text(),
            "0",
        )

        self.assertEqual(
            self.page.time_value.text(),
            "00:00:00",
        )

        self.assertEqual(
            self.page.latest_average_value.text(),
            "N/A",
        )

        self.page._loaded(
            None,
            None,
            "Offline; retry",
        )

        self.assertEqual(
            self.page.completed_value.text(),
            "--",
        )

        self.assertEqual(
            self.page.recent_table.rowCount(),
            0,
        )

    def test_live_state_and_actions(
        self,
    ):
        monitor = Mock()
        history = Mock()

        self.page.monitor_requested.connect(
            monitor
        )

        self.page.history_requested.connect(
            history
        )

        self.page.set_monitoring_state(
            9,
            paused=True,
        )

        self.assertIn(
            "หยุดชั่วคราว",
            self.page.live_label.text(),
        )

        self.page.monitor_button.click()
        self.page.history_button.click()

        monitor.assert_called_once()
        history.assert_called_once()

    def test_async_refresh_and_prevent_duplicate_request(
        self,
    ):
        session_response = Mock(
            ok=True,
            status_code=200,
            json=lambda: [],
        )

        summary_response = Mock(
            ok=True,
            status_code=200,
            json=lambda: [],
        )

        with (
            patch.object(
                APIClient,
                "get_sessions",
                return_value=(
                    session_response
                ),
            ) as get_sessions,

            patch.object(
                APIClient,
                "get_session_summaries",
                return_value=(
                    summary_response
                ),
            ) as get_summaries,
        ):
            self.page.refresh()
            self.page.refresh()

            for _ in range(
                40
            ):
                if (
                    self.page._loader
                    is None
                ):
                    break

                QTest.qWait(
                    25
                )

            self.assertIsNone(
                self.page._loader
            )

            get_sessions.assert_called_once()
            get_summaries.assert_called_once()

    def test_recent_table_limited_to_five(
        self,
    ):
        sessions = [
            {
                "session_id": i,
                "status": "COMPLETED",
                "total_duration": 10,
                "paused_duration": 0,
            }
            for i
            in range(
                8
            )
        ]

        self.page._loaded(
            sessions,
            [],
            "",
        )

        self.assertEqual(
            self.page.recent_table.rowCount(),
            5,
        )

    def test_latest_risk_report_is_displayed(
        self,
    ):
        sessions = [
            {
                "session_id": 38,
                "status": "COMPLETED",
                "total_duration": 161,
                "paused_duration": 0,
            }
        ]

        summaries = [
            {
                "session_id": 38,
                "average_risk_score": 21.2541,
                "minimum_risk_score": 0.0,
                "maximum_risk_score": 83.0,
                "total_alert_count": 3,
                "risk_score_method": (
                    "POSTGUARD_MODIFIED_RULA_FRONT_VIEW_V1"
                ),
            }
        ]

        self.page._loaded(
            sessions,
            summaries,
            "",
        )

        self.assertEqual(
            self.page.latest_average_value.text(),
            "21.25",
        )

        self.assertEqual(
            self.page.latest_maximum_value.text(),
            "83.00",
        )

        self.assertEqual(
            self.page.latest_alert_value.text(),
            "3",
        )

        self.assertTrue(
            self.page.latest_report_button.isEnabled()
        )

    def test_recent_table_joins_summary_by_session_id(
        self,
    ):
        self.page._loaded(
            [
                {
                    "session_id": 10,
                    "status": "COMPLETED",
                    "total_duration": 60,
                    "paused_duration": 0,
                },
                {
                    "session_id": 9,
                    "status": "COMPLETED",
                    "total_duration": 60,
                    "paused_duration": 0,
                },
            ],
            [
                {
                    "session_id": 10,
                    "average_risk_score": 33.0,
                    "minimum_risk_score": 0.0,
                    "maximum_risk_score": 67.0,
                    "total_alert_count": 1,
                }
            ],
            "",
        )

        self.assertEqual(
            self.page.recent_table.item(
                0,
                4,
            ).text(),
            "33.00",
        )

        self.assertEqual(
            self.page.recent_table.item(
                1,
                4,
            ).text(),
            "N/A",
        )

    def test_double_click_report_loads_authoritative_summary(
        self,
    ):
        session = {
            "session_id": 38,
            "status": "COMPLETED",
            "total_duration": 161,
            "paused_duration": 0,
        }

        summary = {
            "session_id": 38,
            "average_risk_score": 21.25,
            "minimum_risk_score": 0.0,
            "maximum_risk_score": 83.0,
            "total_alert_count": 3,
        }

        self.page._loaded(
            [
                session
            ],
            [
                summary
            ],
            "",
        )

        with (
            patch(
                (
                    "app.ui.pages.dashboard_page."
                    "load_session_summary"
                ),
                return_value=summary,
            ) as load,

            patch(
                (
                    "app.ui.pages.dashboard_page."
                    "SavedSessionReportDialog"
                )
            ) as dialog_class,
        ):
            dialog = (
                dialog_class.return_value
            )

            self.page.open_recent_report(
                0,
                0,
            )

            load.assert_called_once_with(
                38
            )

            dialog_class.assert_called_once_with(
                session=session,
                saved_summary=summary,
                parent=self.page,
            )

            dialog.exec.assert_called_once()

    def test_latest_report_button_opens_latest_session(
        self,
    ):
        session = {
            "session_id": 38,
            "status": "COMPLETED",
            "total_duration": 161,
            "paused_duration": 0,
        }

        summary = {
            "session_id": 38,
            "average_risk_score": 21.25,
            "minimum_risk_score": 0.0,
            "maximum_risk_score": 83.0,
            "total_alert_count": 3,
        }

        self.page._loaded(
            [
                session
            ],
            [
                summary
            ],
            "",
        )

        with (
            patch(
                (
                    "app.ui.pages.dashboard_page."
                    "load_session_summary"
                ),
                return_value=summary,
            ),

            patch(
                (
                    "app.ui.pages.dashboard_page."
                    "SavedSessionReportDialog"
                )
            ) as dialog_class,
        ):
            self.page.open_latest_report()

            dialog_class.return_value.exec.assert_called_once()

    def test_session_without_summary_does_not_open_report(
        self,
    ):
        self.page._loaded(
            [
                {
                    "session_id": 37,
                    "status": "COMPLETED",
                    "total_duration": 60,
                    "paused_duration": 0,
                }
            ],
            [],
            "",
        )

        with (
            patch(
                (
                    "app.ui.pages.dashboard_page."
                    "load_session_summary"
                )
            ) as load,
            patch(
                (
                    "app.ui.pages.dashboard_page."
                    "QMessageBox.information"
                )
            ) as information,
        ):
            self.page.open_recent_report(
                0,
                0,
            )

            load.assert_not_called()
            information.assert_called_once()

    def test_legacy_loaded_signature_is_still_supported(
        self,
    ):
        self.page._loaded(
            [
                {
                    "session_id": 1,
                    "status": "COMPLETED",
                    "total_duration": 20,
                    "paused_duration": 0,
                }
            ],
            "",
        )

        self.assertEqual(
            self.page.completed_value.text(),
            "1",
        )

    def test_dashboard_builds_risk_trend_history(
        self,
    ):
        method = (
            "POSTGUARD_MODIFIED_RULA_FRONT_VIEW_V1"
        )

        sessions = [
            {
                "session_id": 40,
                "status": "COMPLETED",
                "total_duration": 100,
                "paused_duration": 0,
            },
            {
                "session_id": 39,
                "status": "COMPLETED",
                "total_duration": 100,
                "paused_duration": 0,
            },
            {
                "session_id": 38,
                "status": "COMPLETED",
                "total_duration": 100,
                "paused_duration": 0,
            },
        ]

        summaries = [
            {
                "session_id": 40,
                "average_risk_score": 20.0,
                "minimum_risk_score": 0.0,
                "maximum_risk_score": 50.0,
                "total_alert_count": 1,
                "risk_score_method": method,
            },
            {
                "session_id": 39,
                "average_risk_score": 25.0,
                "minimum_risk_score": 0.0,
                "maximum_risk_score": 67.0,
                "total_alert_count": 2,
                "risk_score_method": method,
            },
            {
                "session_id": 38,
                "average_risk_score": 30.0,
                "minimum_risk_score": 0.0,
                "maximum_risk_score": 83.0,
                "total_alert_count": 3,
                "risk_score_method": method,
            },
        ]

        self.page._loaded(
            sessions,
            summaries,
            "",
        )

        self.assertEqual(
            len(
                self.page.risk_trend_chart.series
            ),
            3,
        )

        self.assertEqual(
            self.page.risk_trend_chart.series[
                0
            ][
                "session_id"
            ],
            38,
        )

        self.assertEqual(
            self.page.risk_trend_chart.series[
                -1
            ][
                "session_id"
            ],
            40,
        )

        self.assertEqual(
            self.page.risk_trend_value.text(),
            "Improving",
        )


if __name__ == "__main__":
    unittest.main()