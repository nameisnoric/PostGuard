"""Desktop orchestration tests; camera/detection and API responses are simulated."""

import os
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSizePolicy
from PySide6.QtGui import QCloseEvent
from PySide6.QtTest import QTest
from app.core.token_store import TokenStore
from app.services.api_client import APIClient
from app.ui.main_window import MainWindow


def response(data, status=200):
    return Mock(ok=status < 400, status_code=status, json=lambda: data, text="test")


class DesktopWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(redirect_stdout(StringIO()))
        for method in ("information", "warning", "critical"):
            self.stack.enter_context(patch("PySide6.QtWidgets.QMessageBox." + method))
        self.camera = dict(camera_id=1, device_index=0, camera_name="Test", resolution_width=640, resolution_height=360)
        self.baseline = dict(baseline_id=2, camera_id=1, shoulder_angle=1.0, lateral_tilt_baseline=2.0)
        self.camera_reference = {
            "status": "VALID",
            "frame_width": 640,
            "frame_height": 360,
            "card_width_px": 300,
            "card_height_px": 189,
            "scale_x": 3.50,
            "scale_y": 3.50,
            "scale_avg": 3.50,
            "card_roll_deg": 0.5,
            "horizontal_perspective": 0.02,
            "vertical_perspective": 0.03,
            "captured_at": "2026-10-15T12:00:00+00:00",
        }
        self.result = dict(pose_points={}, face_detected=True, shoulder_tilt=1.0, neck_lateral_tilt={"neck_tilt": 2.0})
        self.capture = Mock()
        self.capture.isOpened.return_value = True
        self.capture.read.return_value = (True, np.zeros((360, 640, 3), dtype=np.uint8))
        self.stack.enter_context(patch("cv2.VideoCapture", return_value=self.capture))
        for module in ("baseline_page", "camera_preview_page", "monitoring_page"):
            detector = self.stack.enter_context(patch(f"app.ui.pages.{module}.DetectionService"))
            detector.return_value.process_frame.return_value = self.result
        self.stack.enter_context(patch.object(APIClient, "get_cameras", return_value=response([])))
        self.stack.enter_context(patch.object(APIClient, "get_sessions", return_value=response([])))
        self.stack.enter_context(patch.object(APIClient, "create_camera", return_value=response(self.camera, 201)))
        self.create_baseline = self.stack.enter_context(
            patch.object(
                APIClient,
                "create_personal_baseline",
                return_value=response(self.baseline, 201),
            )
        )
        self.stack.enter_context(patch.object(APIClient, "get", return_value=response(self.baseline)))
        self.stack.enter_context(patch.object(APIClient, "get_session_alerts", return_value=response([])))
        self.user_settings = {
            "notifications_enabled": True,
            "sound_enabled": True,
            "sound_volume": 70,
            "reminder_interval_minutes": 5,
        }
        self.stack.enter_context(patch.object(
            APIClient, "get_settings", return_value=response(self.user_settings)
        ))
        self.update_profile = self.stack.enter_context(patch.object(
            APIClient,
            "update_profile",
            return_value=response({
                "username": "newname",
                "full_name": "New Name",
                "avatar_path": None,
            }),
        ))
        self.start = self.stack.enter_context(patch.object(APIClient, "start_session", return_value=response({"session_id": 3, "status": "RUNNING"}, 201)))
        self.end = self.stack.enter_context(patch.object(APIClient, "end_session", return_value=response({"session_id": 3, "status": "COMPLETED", "total_duration": 100})))
        self.save = self.stack.enter_context(patch.object(APIClient, "post", return_value=response({"session_id": 3}, 201)))
        self.window = MainWindow({"username": "test"})
        self.stack.enter_context(patch.object(self.window.dashboard_page, "refresh"))
        self.window.show()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.end.return_value = response({"session_id": 3, "status": "COMPLETED"})
        self.window.monitoring_page.stop_monitoring()
        self.window.baseline_page.stop_camera_preview()
        self.window.camera_preview_page.stop_preview()
        self.window.camera_calibration_page.stop_camera()
        self.window._exit_ready = True
        self.window.close()
        self.window.deleteLater()

    def start_monitoring(self):
        self.window.show_monitoring_page(self.camera, 2)
        self.assertEqual(self.window.monitoring_page.session_id, 3)

    def test_saved_camera_selection_opens_preview(self):
        setup = self.window.camera_setup_page
        setup.saved_cameras = [self.camera]
        setup.current_source = "saved"
        setup.camera_list.clear()
        setup.camera_list.addItem("Test (640x360)")
        setup.camera_list.setCurrentRow(0)

        setup.handle_continue()

        self.assertIs(
            self.window.pages.currentWidget(),
            self.window.camera_preview_page,
        )
        self.assertEqual(
            self.window.camera_preview_page.selected_camera,
            self.camera,
        )

    def test_camera_previews_are_bounded_and_alerts_live_in_history(self):
        preview = self.window.camera_preview_page.preview_label
        baseline = self.window.baseline_page.preview_label
        monitor = self.window.monitoring_page.preview_label
        calibration = self.window.camera_calibration_page.preview_label

        self.assertEqual(
            preview.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Ignored,
        )
        self.assertEqual(preview.maximumWidth(), 960)
        self.assertEqual(baseline.maximumWidth(), 720)
        self.assertEqual(calibration.maximumWidth(), 820)
        self.assertEqual(monitor.size().width(), 720)
        self.assertEqual(monitor.size().height(), 405)
        preview_item = self.window.camera_preview_page.layout().itemAt(6)
        preview_label_item = preview_item.layout().itemAt(1)
        self.assertEqual(
            preview_label_item.alignment(),
            Qt.AlignmentFlag.AlignCenter,
        )
        self.assertEqual(
            self.window.history_page.alert_history_button.text(),
            "All Alert Events",
        )
        self.assertFalse(hasattr(self.window, "alert_history_button"))

    def test_main_window_uses_centered_resizable_desktop_size(self):
        self.assertEqual(self.window.width(), 1280)
        self.assertEqual(self.window.height(), 800)
        self.assertEqual(self.window.minimumWidth(), 980)
        self.assertEqual(self.window.minimumHeight(), 680)
        self.assertGreater(self.window.maximumWidth(), self.window.width())
        self.assertGreater(self.window.maximumHeight(), self.window.height())

    def test_profile_menu_opens_profile_and_updates_account_initials(self):
        self.window.profile_action.trigger()
        self.assertIs(self.window.pages.currentWidget(), self.window.profile_page)
        self.window.profile_page.first_name_input.setText("New")
        self.window.profile_page.last_name_input.setText("Name")
        self.window.profile_page.username_input.setText("newname")
        self.window.profile_page.save_changes()
        self.assertEqual(self.window.user_data["full_name"], "New Name")
        self.assertEqual(self.window.user_data["username"], "newname")
        self.assertEqual(self.window.account_button.text(), "NN")

    def test_settings_menu_loads_persisted_alert_preferences(self):
        self.window.settings_action.trigger()
        self.assertIs(self.window.pages.currentWidget(), self.window.settings_page)
        self.assertEqual(self.window.settings_page.volume_slider.value(), 70)
        self.assertEqual(
            self.window.monitoring_page.sound_player.settings,
            self.user_settings,
        )

    def test_account_deletion_logs_out_after_backend_confirmation(self):
        TokenStore.set_token("test-token")
        deletion = response({
            "account_status": "PENDING_DELETION",
            "deletion_scheduled_for": "2026-10-29T12:00:00+00:00",
        })
        with patch.object(
            APIClient, "request_account_deletion", return_value=deletion
        ) as request_deletion, patch("app.ui.login_window.LoginWindow") as login:
            self.window.delete_account()

        request_deletion.assert_called_once_with()
        self.assertIsNone(TokenStore.get_token())
        login.return_value.show.assert_called_once_with()

    def test_preview_calibrate_save_monitor_pause_stop_summary(self):
        self.window.show_monitor()
        self.window.show_camera_preview(self.camera)
        self.window.camera_preview_page.handle_continue()
        camera_preparation = self.window.camera_calibration_page
        self.assertIs(self.window.pages.currentWidget(), camera_preparation)
        self.assertFalse(camera_preparation.continue_button.isEnabled())
        camera_preparation.calibration_reference = self.camera_reference.copy()
        camera_preparation.continue_button.setEnabled(True)
        camera_preparation.handle_continue()
        baseline = self.window.baseline_page
        self.assertIs(self.window.pages.currentWidget(), baseline)
        self.assertEqual(
            baseline.selected_camera["camera_calibration"]["scale_avg"], 3.50
        )
        baseline.start_calibration()
        for _ in range(30):
            baseline.collect_calibration_sample(self.result)
        self.assertEqual(baseline.baseline_result["sample_count"], 30)
        self.assertTrue(baseline.calibration_dialog.isVisible())
        baseline.calibration_dialog.accept()
        self.assertFalse(baseline.monitor_button.isEnabled())
        self.assertTrue(baseline.save_button.isEnabled())
        baseline.save_baseline()
        self.assertEqual(baseline.saved_baseline_id, 2)
        self.assertTrue(baseline.monitor_button.isEnabled())
        self.assertTrue(baseline.saved_dialog.isVisible())
        baseline.saved_dialog.accept()
        baseline.handle_start_monitoring()
        monitor = self.window.monitoring_page
        self.assertIs(self.window.pages.currentWidget(), monitor)
        for _ in range(10):
            monitor.update_frame()
        self.assertEqual(monitor.detection_count, 2)
        with patch.object(APIClient, "pause_session", return_value=response({"session_id": 3, "status": "PAUSED", "pause_count": 1})):
            monitor.handle_pause_resume()
        self.assertTrue(monitor.is_paused)
        self.assertFalse(monitor.timer.isActive())
        with patch.object(APIClient, "resume_session", return_value=response({"session_id": 3, "status": "RUNNING", "paused_duration": 5})):
            monitor.handle_pause_resume()
        self.assertFalse(monitor.is_paused)
        self.assertTrue(monitor.timer.isActive())
        self.start.assert_called_once()
        monitor.handle_stop()
        summary_page = self.window.session_summary_page
        self.assertIs(self.window.pages.currentWidget(), summary_page)
        self.assertEqual(summary_page.current_summary["summary_save_status"], "SAVED")
        self.assertEqual(summary_page.current_summary["detection_count"], 2)
        self.assertTrue(summary_page.save_group.isHidden())
        self.assertEqual(monitor.stop_button.text(), "Stop Monitoring")
        self.assertEqual(self.save.call_args.args[1]["average_neck"], 2.0)
        baseline_payload = self.create_baseline.call_args.kwargs["measurements"]
        self.assertEqual(baseline_payload["camera_scale_avg"], 3.50)
        self.assertEqual(
            baseline_payload["camera_calibrated_at"],
            "2026-10-15T12:00:00+00:00",
        )
        self.assertIsNone(monitor.capture)
        self.assertFalse(monitor.timer.isActive())

    def test_camera_preparation_completion_notifies_only_once(self):
        page = self.window.camera_calibration_page
        with patch(
            "app.ui.pages.camera_calibration_page.QMessageBox.information"
        ) as information:
            page._complete_preparation(self.camera_reference)
            page._complete_preparation(self.camera_reference)

        self.assertTrue(page.continue_button.isEnabled())
        self.assertEqual(page.calibration_reference, self.camera_reference)
        information.assert_called_once()

    def test_experimental_threshold_requires_explicit_enable(self):
        monitor = self.window.monitoring_page
        self.assertEqual(monitor.neck_threshold_spin.locale().zeroDigit(), "0")
        self.assertFalse(monitor.threshold_enabled.isChecked())
        self.assertFalse(monitor.neck_threshold_spin.isEnabled())
        self.assertEqual(monitor.neck_threshold_spin.value(), 0.0)

        monitor.threshold_enabled.setChecked(True)
        self.assertTrue(monitor.neck_threshold_spin.isEnabled())
        self.assertEqual(monitor.neck_threshold_spin.value(), 10.0)
        monitor.neck_threshold_spin.setValue(12.5)
        self.assertEqual(monitor.neck_threshold_spin.value(), 12.5)

        monitor.threshold_enabled.setChecked(False)
        self.assertFalse(monitor.neck_threshold_spin.isEnabled())
        self.assertEqual(monitor.neck_threshold_spin.value(), 0.0)
        monitor.threshold_enabled.setChecked(True)
        self.assertEqual(monitor.neck_threshold_spin.value(), 12.5)

    def test_failed_end_preserves_samples_for_retry(self):
        self.start_monitoring()
        monitor = self.window.monitoring_page
        monitor.record_detection_sample(self.result)
        self.end.return_value = response({}, 503)
        monitor.handle_stop()
        self.assertEqual(monitor.session_id, 3)
        self.assertEqual(monitor.detection_count, 1)
        self.save.assert_not_called()
        self.end.return_value = response({"session_id": 3, "status": "COMPLETED"})
        monitor.handle_stop()
        self.assertEqual(self.window.session_summary_page.current_summary["detection_count"], 1)

    def test_summary_retry_after_api_failure(self):
        self.start_monitoring()
        self.window.monitoring_page.record_detection_sample(self.result)
        self.save.return_value = response({}, 503)
        self.window.monitoring_page.handle_stop()
        summary = self.window.session_summary_page
        self.assertEqual(summary.current_summary["summary_save_status"], "FAILED")
        self.assertTrue(summary.retry_button.isEnabled())
        self.assertFalse(summary.save_group.isHidden())
        self.save.return_value = response({"session_id": 3}, 201)
        summary.retry_save()
        self.assertEqual(summary.current_summary["summary_save_status"], "SAVED")

    def test_navigation_keeps_timer_and_returns_to_same_session(self):
        self.start_monitoring()
        monitor = self.window.monitoring_page
        self.window.show_dashboard()
        self.assertFalse(monitor.isVisible())
        for _ in range(20):
            if monitor.detection_count:
                break
            QTest.qWait(50)
        self.assertGreater(monitor.detection_count, 0)
        with patch.object(APIClient, "get", return_value=response([])):
            self.window.show_history()
        self.assertTrue(monitor.timer.isActive())
        self.assertEqual(monitor.session_id, 3)
        self.end.assert_not_called()
        self.assertIn("Running", self.window.monitoring_status_label.text())
        self.window.show_monitor()
        self.assertIs(self.window.pages.currentWidget(), monitor)
        self.start.assert_called_once()

    def test_global_pause_resume_stop_while_on_history(self):
        self.start_monitoring()
        monitor = self.window.monitoring_page
        monitor.record_detection_sample(self.result)
        with patch.object(APIClient, "get", return_value=response([])):
            self.window.show_history()
        with patch.object(APIClient, "pause_session", return_value=response({"session_id": 3, "status": "PAUSED", "pause_count": 1})):
            self.window.global_pause_button.click()
        self.assertFalse(monitor.timer.isActive())
        self.assertIn("Paused", self.window.monitoring_status_label.text())
        self.assertEqual(self.window.global_pause_button.text(), "Resume Monitoring")
        self.window.show_monitor()
        self.assertTrue(monitor.is_paused)
        self.window.show_dashboard()
        with patch.object(APIClient, "resume_session", return_value=response({"session_id": 3, "status": "RUNNING", "paused_duration": 5})):
            self.window.global_pause_button.click()
        self.assertTrue(monitor.timer.isActive())
        self.window.global_stop_button.click()
        self.assertIs(self.window.pages.currentWidget(), self.window.session_summary_page)
        self.assertEqual(self.window.session_summary_page.current_summary["detection_count"], 1)
        self.assertFalse(self.window.global_pause_button.isEnabled())
        self.assertFalse(self.window.global_stop_button.isEnabled())
        self.assertFalse(monitor.pause_button.isEnabled())

    def test_close_saves_before_clearing_credentials(self):
        self.start_monitoring()
        TokenStore.set_token("test-token")
        self.window.monitoring_page.record_detection_sample(self.result)
        self.window.show_dashboard()
        def save_with_token(*args):
            self.assertEqual(TokenStore.get_token(), "test-token")
            return response({"session_id": 3}, 201)
        self.save.side_effect = save_with_token
        event = QCloseEvent()
        self.window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.save.assert_called_once()
        self.assertIsNone(TokenStore.get_token())
        self.assertIsNone(self.window.monitoring_page.capture)

    def test_close_failure_preserves_token_and_statistics(self):
        self.start_monitoring()
        TokenStore.set_token("test-token")
        self.window.monitoring_page.record_detection_sample(self.result)
        self.end.return_value = response({}, 503)
        event = QCloseEvent()
        self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertEqual(TokenStore.get_token(), "test-token")
        self.assertEqual(self.window.monitoring_page.detection_count, 1)
        self.save.assert_not_called()

    def test_close_save_failure_blocks_new_session_until_retry(self):
        self.start_monitoring()
        TokenStore.set_token("test-token")
        self.save.return_value = response({}, 503)
        event = QCloseEvent()
        self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertEqual(TokenStore.get_token(), "test-token")
        self.window.show_dashboard()
        self.window.show_monitor()
        self.assertIs(self.window.pages.currentWidget(), self.window.session_summary_page)
        self.start.assert_called_once()
        self.save.return_value = response({"session_id": 3}, 201)
        self.window.session_summary_page.retry_save()
        self.window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.end.assert_called_once()

    def test_logout_saves_and_opens_login(self):
        self.start_monitoring()
        TokenStore.set_token("test-token")
        with patch("app.ui.login_window.LoginWindow") as login:
            self.window.logout()
            login.return_value.show.assert_called_once()
        self.save.assert_called_once()
        self.assertIsNone(TokenStore.get_token())

    def test_logout_failure_keeps_current_window(self):
        self.start_monitoring()
        TokenStore.set_token("test-token")
        self.save.return_value = response({}, 503)
        with patch("app.ui.login_window.LoginWindow") as login:
            self.window.logout()
            login.assert_not_called()
        self.assertEqual(TokenStore.get_token(), "test-token")
        self.assertTrue(self.window.isVisible())

    def test_stop_from_paused_saves_same_session(self):
        self.start_monitoring()
        with patch.object(APIClient, "pause_session", return_value=response({"session_id": 3, "status": "PAUSED", "pause_count": 1})):
            self.window.global_pause_button.click()
        self.window.show_dashboard()
        self.window.global_stop_button.click()
        self.end.assert_called_once_with(3)
        self.save.assert_called_once()

    def test_camera_failure_keeps_statistics_until_end_retry(self):
        self.start_monitoring()
        monitor = self.window.monitoring_page
        monitor.record_detection_sample(self.result)
        self.capture.read.return_value = (False, None)
        self.end.return_value = response({}, 503)
        self.window.show_dashboard()
        monitor.update_frame()
        self.assertFalse(monitor.timer.isActive())
        self.assertEqual(monitor.detection_count, 1)
        self.assertIsNone(monitor.capture)
        self.assertFalse(self.window.global_pause_button.isEnabled())
        self.assertTrue(self.window.global_stop_button.isEnabled())
        self.end.return_value = response({"session_id": 3, "status": "COMPLETED"})
        self.window.global_stop_button.click()
        self.assertEqual(self.window.session_summary_page.current_summary["detection_count"], 1)


if __name__ == "__main__":
    unittest.main()
