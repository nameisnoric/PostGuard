import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

import requests
from PySide6.QtWidgets import QApplication, QMessageBox
try:
    from . import test_desktop_workflow as fixtures
except ImportError:
    import test_desktop_workflow as fixtures
from app.services.api_client import APIClient
from app.services.session_recovery_service import find_unclosed_sessions, interrupt_previous_session
from app.services.alert_history_service import summarize_alerts
from app.ui.login_window import LoginWindow

response = fixtures.response


class SessionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    setUp = fixtures.DesktopWorkflowTests.setUp
    cleanup_window = fixtures.DesktopWorkflowTests.cleanup_window
    start_monitoring = fixtures.DesktopWorkflowTests.start_monitoring

    def test_cancel_blocks_monitor_without_ending_remote_session(self):
        with patch.object(APIClient, "get_sessions", return_value=response([{"session_id": 9, "status": "RUNNING"}])), patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.No), patch.object(APIClient, "interrupt_session") as interrupt:
            self.window.show_monitor()
            interrupt.assert_not_called()
        self.assertIs(self.window.pages.currentWidget(), self.window.dashboard_page)
        self.start.assert_not_called()

    def test_confirm_recovers_then_opens_camera_setup(self):
        with patch.object(APIClient, "get_sessions", return_value=response([{"session_id": 9, "status": "PAUSED"}])), patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), patch.object(APIClient, "interrupt_session", return_value=response({"session_id": 9, "status": "INTERRUPTED"})) as interrupt:
            self.window.show_monitor()
            interrupt.assert_called_once_with(9)
        self.assertIs(self.window.pages.currentWidget(), self.window.camera_setup_page)
        self.save.assert_not_called()

    def test_network_failure_blocks_start_until_check_succeeds(self):
        with patch.object(APIClient, "get_sessions", side_effect=requests.Timeout()):
            self.window.show_monitoring_page(self.camera, 2)
        self.start.assert_not_called()
        self.start_monitoring()

    def test_active_local_session_is_not_recovered(self):
        self.start_monitoring()
        with patch.object(APIClient, "get_sessions") as get:
            self.window.show_dashboard()
            self.window.show_monitor()
            get.assert_not_called()

    def test_lost_interrupt_response_reconciles_with_get(self):
        with patch.object(APIClient, "interrupt_session", side_effect=requests.Timeout()), patch.object(APIClient, "get_session", return_value=response({"session_id": 9, "status": "INTERRUPTED"})):
            interrupt_previous_session(9)
        with patch.object(APIClient, "interrupt_session", return_value=response({"session_id": 8, "status": "INTERRUPTED"})):
            with self.assertRaises(ValueError):
                interrupt_previous_session(9)

    def test_malformed_list_is_not_treated_as_no_active_session(self):
        for data in ({}, [{"session_id": True, "status": "RUNNING"}], [{"session_id": 9, "status": "UNKNOWN"}]):
            with self.subTest(data=data), patch.object(APIClient, "get_sessions", return_value=response(data)):
                with self.assertRaises(ValueError):
                    find_unclosed_sessions()

    def test_incomplete_alert_not_counted_as_active_or_closed(self):
        stats = summarize_alerts([{"event_id": 1, "event_type": "NECK_LATERAL_TILT", "ended_at": None, "duration": None, "incomplete": True}])
        self.assertEqual(stats["incomplete_alerts"], 1)
        self.assertEqual(stats["active_alerts"], 0)
        self.assertEqual(stats["closed_alerts"], 0)

    def test_login_checks_previous_sessions_without_logging_token(self):
        login = LoginWindow()
        login.email_input.setText("test@ku.th")
        login.password_input.setText("secret-password")
        login_response = response({"access_token": "secret-token"})
        login_response.text = "secret-token"
        output = StringIO()
        with patch.object(APIClient, "login", return_value=login_response), patch.object(APIClient, "get_current_user", return_value=response({"id": 1})), patch("app.ui.login_window.MainWindow") as window, redirect_stdout(output):
            login.handle_login()
            window.return_value.check_previous_sessions.assert_called_once()
        self.assertNotIn("secret-token", output.getvalue())
        self.assertNotIn("secret-password", output.getvalue())
        login.deleteLater()

    def test_pending_deletion_login_opens_only_account_recovery(self):
        login = LoginWindow()
        login.email_input.setText("test@ku.th")
        login.password_input.setText("secret-password")
        pending_user = {
            "id": 1,
            "account_status": "PENDING_DELETION",
            "deletion_scheduled_for": "2026-10-29T12:00:00+00:00",
        }
        with patch.object(
            APIClient, "login", return_value=response({"access_token": "token"})
        ), patch.object(
            APIClient, "get_current_user", return_value=response(pending_user)
        ), patch(
            "app.ui.account_recovery_window.AccountRecoveryWindow"
        ) as recovery, patch("app.ui.login_window.MainWindow") as main_window:
            login.handle_login()

        recovery.assert_called_once_with(pending_user)
        recovery.return_value.show.assert_called_once_with()
        main_window.assert_not_called()
        login.deleteLater()


if __name__ == "__main__":
    unittest.main()
