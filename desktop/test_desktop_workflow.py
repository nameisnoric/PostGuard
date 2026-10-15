"""Desktop orchestration tests; camera/detection and API responses are simulated."""

import os
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication
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
        self.result = dict(pose_points={}, face_detected=True, shoulder_tilt=1.0, neck_lateral_tilt={"neck_tilt": 2.0})
        self.capture = Mock()
        self.capture.isOpened.return_value = True
        self.capture.read.return_value = (True, np.zeros((360, 640, 3), dtype=np.uint8))
        self.stack.enter_context(patch("cv2.VideoCapture", return_value=self.capture))
        for module in ("baseline_page", "camera_preview_page", "monitoring_page"):
            detector = self.stack.enter_context(patch(f"app.ui.pages.{module}.DetectionService"))
            detector.return_value.process_frame.return_value = self.result
        self.stack.enter_context(patch.object(APIClient, "get_cameras", return_value=response([])))
        self.stack.enter_context(patch.object(APIClient, "create_camera", return_value=response(self.camera, 201)))
        self.stack.enter_context(patch.object(APIClient, "create_personal_baseline", return_value=response(self.baseline, 201)))
        self.stack.enter_context(patch.object(APIClient, "get", return_value=response(self.baseline)))
        self.stack.enter_context(patch.object(APIClient, "get_session_alerts", return_value=response([])))
        self.start = self.stack.enter_context(patch.object(APIClient, "start_session", return_value=response({"session_id": 3, "status": "RUNNING"}, 201)))
        self.end = self.stack.enter_context(patch.object(APIClient, "end_session", return_value=response({"session_id": 3, "status": "COMPLETED", "total_duration": 100})))
        self.save = self.stack.enter_context(patch.object(APIClient, "post", return_value=response({"session_id": 3}, 201)))
        self.window = MainWindow({"username": "test"})
        self.window.show()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.end.return_value = response({"session_id": 3, "status": "COMPLETED"})
        self.window.monitoring_page.stop_monitoring()
        self.window.baseline_page.stop_camera_preview()
        self.window.camera_preview_page.stop_preview()
        self.window._exit_ready = True
        self.window.close()
        self.window.deleteLater()

    def start_monitoring(self):
        self.window.show_monitoring_page(self.camera, 2)
        self.assertEqual(self.window.monitoring_page.session_id, 3)

    def test_preview_calibrate_save_monitor_pause_stop_summary(self):
        self.window.show_monitor()
        self.window.show_camera_preview(self.camera)
        self.window.camera_preview_page.handle_continue()
        baseline = self.window.baseline_page
        self.assertIs(self.window.pages.currentWidget(), baseline)
        baseline.start_calibration()
        for _ in range(30):
            baseline.collect_calibration_sample(self.result)
        self.assertEqual(baseline.baseline_result["sample_count"], 30)
        baseline.save_baseline()
        self.assertEqual(baseline.saved_baseline_id, 2)
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
        self.assertEqual(self.save.call_args.args[1]["average_neck"], 2.0)
        self.assertIsNone(monitor.capture)
        self.assertFalse(monitor.timer.isActive())

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
        self.save.return_value = response({"session_id": 3}, 201)
        summary.retry_save()
        self.assertEqual(summary.current_summary["summary_save_status"], "SAVED")

    def test_navigation_keeps_timer_and_returns_to_same_session(self):
        self.start_monitoring()
        monitor = self.window.monitoring_page
        self.window.show_dashboard()
        self.assertFalse(monitor.isVisible())
        QTest.qWait(200)
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
