"""PostGuard Monitoring UI: Session API + experimental partial risk tracking."""

import math
import statistics
import time
from datetime import datetime

import cv2
import requests

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QGroupBox, QDoubleSpinBox, QApplication,
)

from app.services.detection_service import DetectionService
from app.services.api_client import APIClient
from app.services.risk_engine import assess_posture
from app.services.experimental_alert_service import ExperimentalAlertService
from app.services.posture_duration_tracker import (
    PostureDurationTracker,
    classify_neck_side_bending,
)


class MonitoringPage(QWidget):
    stop_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        self.selected_camera = None
        self.baseline_id = None
        self.baseline_data = None
        self.capture = None
        self.detector = None
        self.frame_count = 0
        self.session_id = None
        self.session_started_at = None
        self.session_started_monotonic = None
        self.detection_count = 0
        self.pose_detected_count = 0
        self.face_detected_count = 0
        self.shoulder_samples = []
        self.neck_samples = []
        self.posture_tracker = PostureDurationTracker()
        self.alert_service = ExperimentalAlertService()
        self._alert_force_close = False

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_frame)

        layout = QVBoxLayout(self)
        self.title_label = QLabel("Real-time Monitoring")
        self.description_label = QLabel(
            "Live posture detection (complete risk assessment not enabled yet)."
        )

        info_group = QGroupBox("Monitoring Information")
        info_layout = QVBoxLayout(info_group)
        self.camera_label = QLabel("Camera: -")
        self.baseline_label = QLabel("Baseline ID: -")
        self.session_label = QLabel("Session ID: -")
        self.baseline_shoulder_label = QLabel("Baseline Shoulder Tilt: -")
        self.baseline_neck_label = QLabel("Baseline Neck Lateral Tilt: -")
        self.status_label = QLabel("Status: Not started")
        for label in (
            self.camera_label, self.baseline_label, self.session_label,
            self.baseline_shoulder_label, self.baseline_neck_label,
            self.status_label,
        ):
            info_layout.addWidget(label)

        self.preview_label = QLabel("Monitoring preview will appear here.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setStyleSheet(
            "QLabel { background-color: #111111; border: 1px solid #444444; "
            "border-radius: 8px; }"
        )

        detection_group = QGroupBox("Live Detection")
        detection_layout = QVBoxLayout(detection_group)
        self.detection_label = QLabel("Pose: Waiting | Face: Waiting")
        self.shoulder_label = QLabel("Shoulder Tilt: --")
        self.neck_label = QLabel("Neck Lateral Tilt: --")
        self.shoulder_difference_label = QLabel("Shoulder Difference: --")
        self.neck_difference_label = QLabel("Neck Difference: --")
        for label in (
            self.detection_label, self.shoulder_label, self.neck_label,
            self.shoulder_difference_label, self.neck_difference_label,
        ):
            detection_layout.addWidget(label)

        # This is a test control, NOT a validated clinical cutoff.
        risk_group = QGroupBox("Partial Risk Assessment (Experimental)")
        risk_layout = QVBoxLayout(risk_group)
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Neck side-bending test threshold:"))
        self.neck_threshold_spin = QDoubleSpinBox()
        self.neck_threshold_spin.setRange(0.0, 45.0)
        self.neck_threshold_spin.setDecimals(1)
        self.neck_threshold_spin.setSingleStep(0.5)
        self.neck_threshold_spin.setSuffix("°")
        self.neck_threshold_spin.setSpecialValueText("Disabled (0°)")
        self.neck_threshold_spin.setValue(0.0)
        self.neck_threshold_spin.setToolTip(
            "For experimentation only. 0 disables classification; "
            "no validated side-bending cutoff has been selected."
        )
        self.neck_threshold_spin.valueChanged.connect(self.reset_risk_tracking)
        threshold_layout.addWidget(self.neck_threshold_spin)
        threshold_layout.addStretch()
        risk_layout.addLayout(threshold_layout)
        self.side_bending_label = QLabel("Neck Side-bending: N/A")
        self.duration_label = QLabel("Continuous Side-bending: N/A")
        self.partial_factors_label = QLabel("Side-bending Score: N/A | Duration Score: N/A")
        self.risk_label = QLabel("Risk Score: N/A (PARTIAL - missing factors)")
        self.alert_label = QLabel("Experimental Alert: Waiting")
        self.alert_label.setWordWrap(True)
        self.risk_note_label = QLabel(
            "Experimental neck alert after 60 s of continuous bending. "
            "Backend MEDIUM is a provisional API label, NOT a calculated "
            "Risk Score. Full Risk Score remains unavailable."
        )
        self.risk_note_label.setWordWrap(True)
        for label in (
            self.side_bending_label, self.duration_label,
            self.partial_factors_label, self.risk_label,
            self.alert_label, self.risk_note_label,
        ):
            risk_layout.addWidget(label)

        button_layout = QHBoxLayout()
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.handle_stop)
        button_layout.addStretch()
        button_layout.addWidget(self.stop_button)

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(info_group)
        layout.addWidget(self.preview_label, 1)
        layout.addWidget(detection_group)
        layout.addWidget(risk_group)
        layout.addLayout(button_layout)

    @staticmethod
    def _response_error(response):
        try:
            payload = response.json()
            detail = payload.get("detail", response.text) if isinstance(payload, dict) else response.text
        except ValueError:
            detail = response.text
        return f"HTTP {response.status_code}: {detail}"

    def _end_remote_session(self) -> dict | None:
        if self.session_id is None:
            return None
        try:
            response = APIClient.end_session(self.session_id)
        except requests.RequestException as error:
            try:
                check = APIClient.get_session(self.session_id)
                if check.ok and check.json().get("status") == "COMPLETED":
                    response = check
                else:
                    raise error
            except (requests.RequestException, ValueError, AttributeError):
                raise error
        if not response.ok:
            if response.status_code == 409:
                check = APIClient.get_session(self.session_id)
                if check.ok and check.json().get("status") == "COMPLETED":
                    response = check
                else:
                    raise RuntimeError(self._response_error(response))
            else:
                raise RuntimeError(self._response_error(response))
        data = response.json()
        if not isinstance(data, dict) or data.get("status") != "COMPLETED":
            raise ValueError("Backend did not confirm COMPLETED session status.")
        if data.get("session_id") != self.session_id:
            raise ValueError("Backend returned an unexpected session_id.")
        self.session_id = None
        return data

    def load_personal_baseline(self, baseline_id: int, camera_id: int) -> dict:
        response = APIClient.get(f"/personal-baselines/{baseline_id}")
        if not response.ok:
            raise RuntimeError("Cannot load baseline: " + self._response_error(response))
        baseline = response.json()
        if not isinstance(baseline, dict):
            raise ValueError("Invalid baseline response.")
        if baseline.get("baseline_id") != baseline_id:
            raise ValueError("Baseline ID does not match.")
        if baseline.get("camera_id") != camera_id:
            raise ValueError("Baseline belongs to another camera.")
        shoulder = baseline.get("shoulder_angle")
        neck = baseline.get("lateral_tilt_baseline")
        for name, value in (("Shoulder", shoulder), ("Neck", neck)):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"Invalid {name} baseline value.")
        self.baseline_shoulder_label.setText(f"Baseline Shoulder Tilt: {shoulder:+.2f}°")
        self.baseline_neck_label.setText(f"Baseline Neck Lateral Tilt: {neck:+.2f}°")
        self.baseline_data = baseline
        return baseline

    def start_monitoring(self, camera: dict, baseline_id: int) -> bool:
        if not self.stop_monitoring():
            QMessageBox.warning(
                self, "Session Error",
                "The previous database session could not be ended. "
                "Check your connection and retry.",
            )
            return False
        self.selected_camera = camera.copy()
        self.baseline_id = baseline_id
        device_index = camera.get("device_index")
        camera_id = camera.get("camera_id")
        if device_index is None:
            QMessageBox.warning(self, "Monitoring", "Camera device index is missing.")
            return False
        if type(baseline_id) is not int or baseline_id <= 0:
            QMessageBox.warning(self, "Monitoring", "A saved Baseline ID is required.")
            return False
        try:
            if type(camera_id) is not int or camera_id <= 0:
                raise ValueError("Invalid Camera ID.")
            self.load_personal_baseline(baseline_id, camera_id)
        except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
            QMessageBox.warning(self, "Baseline Error", str(error))
            return False
        self.camera_label.setText("Camera: " + camera.get("camera_name", "Unknown Camera"))
        self.baseline_label.setText(f"Baseline ID: {baseline_id}")
        try:
            self.capture = cv2.VideoCapture(int(device_index))
            if not self.capture.isOpened():
                raise RuntimeError("Unable to open camera.")
            self.detector = DetectionService()
            response = APIClient.start_session(camera_id, baseline_id)
            if not response.ok:
                raise RuntimeError("Cannot start session: " + self._response_error(response))
            session = response.json()
            session_id = session.get("session_id") if isinstance(session, dict) else None
            if type(session_id) is not int or session_id <= 0:
                raise ValueError("Backend returned an invalid session_id.")
            if session.get("status") != "RUNNING":
                raise ValueError("Backend did not confirm RUNNING status.")
            self.session_id = session_id
        except (requests.RequestException, RuntimeError, ValueError, TypeError, OSError) as error:
            self.stop_monitoring()
            QMessageBox.warning(self, "Monitoring Error", str(error))
            return False
        self.frame_count = 0
        self.session_started_at = session.get("started_at") or datetime.now().astimezone().isoformat(timespec="seconds")
        self.session_started_monotonic = time.monotonic()
        self.detection_count = 0
        self.pose_detected_count = 0
        self.face_detected_count = 0
        self.shoulder_samples.clear()
        self.neck_samples.clear()
        self.alert_service.reset()
        self._alert_force_close = False
        self.reset_risk_tracking()
        self.session_label.setText(f"Session ID: {self.session_id}")
        self.status_label.setText("Status: Monitoring (RUNNING)")
        self.stop_button.setEnabled(True)
        self.timer.start()
        print("MONITORING STARTED: SESSION ID", self.session_id)
        return True

    def reset_risk_tracking(self, *_args) -> None:
        """Changing threshold resets duration and closes any active alert."""
        if self.session_id is not None and self.alert_service.active_event_id is not None:
            self._alert_force_close = not self.alert_service.close_if_active()
            if self._alert_force_close:
                self.alert_label.setText(
                    "Experimental Alert: End pending (API unavailable)"
                )
            else:
                self.alert_label.setText("Experimental Alert: Cleared")
        self.posture_tracker.reset()
        self.side_bending_label.setText("Neck Side-bending: N/A")
        self.duration_label.setText("Continuous Side-bending: N/A")
        self.partial_factors_label.setText("Side-bending Score: N/A | Duration Score: N/A")
        self.risk_label.setText("Risk Score: N/A (PARTIAL - missing factors)")
        if self.session_id is None:
            self.alert_label.setText("Experimental Alert: Waiting")

    def update_partial_risk(self, result: dict) -> None:
        """Use existing neck_tilt only. Never change teammate's detector math."""
        neck_result = result.get("neck_lateral_tilt")
        neck_angle = neck_result.get("neck_tilt") if isinstance(neck_result, dict) else None
        baseline = self.baseline_data or {}
        baseline_neck = baseline.get("lateral_tilt_baseline")
        threshold = self.neck_threshold_spin.value()
        direction = classify_neck_side_bending(neck_angle, baseline_neck, threshold)
        seconds = self.posture_tracker.update(direction)

        if direction is None:
            self.side_bending_label.setText("Neck Side-bending: N/A (threshold off or pose missing)")
            self.duration_label.setText("Continuous Side-bending: N/A")
            side_bending = None
        elif direction == 0:
            self.side_bending_label.setText("Neck Side-bending: No (experimental)")
            self.duration_label.setText("Continuous Side-bending: 0.0 s")
            side_bending = False
        else:
            side_name = "+ direction" if direction > 0 else "- direction"
            self.side_bending_label.setText(f"Neck Side-bending: Yes ({side_name}, experimental)")
            self.duration_label.setText(f"Continuous Side-bending: {seconds:.1f} s")
            side_bending = True

        assessment = assess_posture(
            neck_side_bending=side_bending,
            sustained_seconds=seconds,
        )
        factors = assessment["factors"]
        side_score = factors["neck_side_bending"]
        duration_score = factors["muscle_use_duration"]
        side_text = str(side_score) if side_score is not None else "N/A"
        duration_text = str(duration_score) if duration_score is not None else "N/A"
        self.partial_factors_label.setText(
            f"Side-bending Score: {side_text} | Duration Score: {duration_text}"
        )
        # Neck flexion, rotation and trunk are unavailable: never show full risk.
        self.risk_label.setText("Risk Score: N/A (PARTIAL - missing factors)")
        # Retry closing an old event before applying a new threshold.
        if self._alert_force_close:
            if self.alert_service.close_if_active():
                self._alert_force_close = False
                self.alert_label.setText("Experimental Alert: Cleared")
            else:
                self.alert_label.setText(
                    "Experimental Alert: End pending - "
                    + str(self.alert_service.last_error)
                )
                return

        if self.session_id is None:
            return
        action = self.alert_service.update(self.session_id, direction, seconds)
        if action == "created":
            self.alert_label.setText(
                "Experimental Alert: Neck side-bending held >= 60 s. "
                "Please adjust your posture. Event saved to PostgreSQL."
            )
            QApplication.beep()
        elif action == "ended":
            self.alert_label.setText("Experimental Alert: Cleared (event ended)")
        elif self.alert_service.last_error:
            self.alert_label.setText(
                "Experimental Alert: API error (will retry): "
                + self.alert_service.last_error
            )
        elif direction == 0:
            self.alert_label.setText("Experimental Alert: No sustained bending")
        elif direction is None:
            self.alert_label.setText("Experimental Alert: Detection unavailable / disabled")
        elif self.alert_service.active_event_id is None:
            self.alert_label.setText("Experimental Alert: Monitoring continuous bending")

    def update_baseline_comparison(self, result: dict) -> None:
        if self.baseline_data is None:
            return
        current_shoulder = result.get("shoulder_tilt")
        neck_result = result.get("neck_lateral_tilt")
        current_neck = neck_result.get("neck_tilt") if isinstance(neck_result, dict) else None
        baseline_shoulder = self.baseline_data.get("shoulder_angle")
        baseline_neck = self.baseline_data.get("lateral_tilt_baseline")
        if (
            type(current_shoulder) in (int, float)
            and type(baseline_shoulder) in (int, float)
            and math.isfinite(current_shoulder)
            and math.isfinite(baseline_shoulder)
        ):
            difference = current_shoulder - baseline_shoulder
            self.shoulder_difference_label.setText(f"Shoulder Difference: {difference:+.2f}°")
        else:
            self.shoulder_difference_label.setText("Shoulder Difference: --")
        if (
            type(current_neck) in (int, float)
            and type(baseline_neck) in (int, float)
            and math.isfinite(current_neck)
            and math.isfinite(baseline_neck)
        ):
            difference = current_neck - baseline_neck
            self.neck_difference_label.setText(f"Neck Difference: {difference:+.2f}°")
        else:
            self.neck_difference_label.setText("Neck Difference: --")

    def record_detection_sample(self, result: dict) -> None:
        self.detection_count += 1
        if result.get("pose_points") is not None:
            self.pose_detected_count += 1
        if result.get("face_detected"):
            self.face_detected_count += 1
        shoulder = result.get("shoulder_tilt")
        if type(shoulder) in (int, float) and math.isfinite(shoulder):
            self.shoulder_samples.append(float(shoulder))
        neck_result = result.get("neck_lateral_tilt")
        neck = neck_result.get("neck_tilt") if isinstance(neck_result, dict) else None
        if type(neck) in (int, float) and math.isfinite(neck):
            self.neck_samples.append(float(neck))

    def update_frame(self) -> None:
        if self.capture is None:
            return
        success, frame = self.capture.read()
        if not success or frame is None:
            self.stop_monitoring()
            QMessageBox.warning(self, "Camera Error", "Unable to read camera frame.")
            return
        self.frame_count += 1
        if self.detector is not None and self.frame_count % 5 == 0:
            try:
                result = self.detector.process_frame(frame)
                self.record_detection_sample(result)
                self.update_baseline_comparison(result)
                self.update_partial_risk(result)
                pose_text = "Detected" if result["pose_points"] is not None else "Not Found"
                face_text = "Detected" if result["face_detected"] else "Not Found"
                self.detection_label.setText(f"Pose: {pose_text} | Face: {face_text}")
                shoulder = result["shoulder_tilt"]
                self.shoulder_label.setText(
                    f"Shoulder Tilt: {shoulder:+.2f}°" if shoulder is not None else "Shoulder Tilt: --"
                )
                neck_result = result["neck_lateral_tilt"]
                neck = neck_result.get("neck_tilt") if isinstance(neck_result, dict) else None
                self.neck_label.setText(
                    f"Neck Lateral Tilt: {neck:+.2f}°" if neck is not None else "Neck Lateral Tilt: --"
                )
            except Exception as error:
                self.stop_monitoring()
                QMessageBox.warning(self, "Detection Error", str(error))
                return
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = frame_rgb.shape
        image = QImage(
            frame_rgb.data, width, height, channels * width,
            QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(pixmap)

    def _release_local_resources(self) -> None:
        self.timer.stop()
        if self.detector is not None:
            try:
                self.detector.close()
            except Exception as error:
                print("DETECTION CLOSE ERROR:", error)
            finally:
                self.detector = None
        if self.capture is not None:
            try:
                self.capture.release()
            finally:
                self.capture = None
        self.frame_count = 0
        self.detection_label.setText("Pose: Waiting | Face: Waiting")
        self.shoulder_label.setText("Shoulder Tilt: --")
        self.neck_label.setText("Neck Lateral Tilt: --")
        self.shoulder_difference_label.setText("Shoulder Difference: --")
        self.neck_difference_label.setText("Neck Difference: --")
        self.preview_label.clear()
        self.preview_label.setText("Monitoring preview will appear here.")
        self.stop_button.setEnabled(False)
        self.session_started_at = None
        self.session_started_monotonic = None
        self.baseline_data = None
        self.baseline_shoulder_label.setText("Baseline Shoulder Tilt: --")
        self.baseline_neck_label.setText("Baseline Neck Lateral Tilt: --")
        self.detection_count = 0
        self.pose_detected_count = 0
        self.face_detected_count = 0
        self.shoulder_samples.clear()
        self.neck_samples.clear()
        self.posture_tracker.reset()
        self.side_bending_label.setText("Neck Side-bending: N/A")
        self.duration_label.setText("Continuous Side-bending: N/A")
        self.partial_factors_label.setText("Side-bending Score: N/A | Duration Score: N/A")
        self.risk_label.setText("Risk Score: N/A (PARTIAL - missing factors)")
        # Successful session end automatically closes backend alert events.
        # Preserve IDs when session end fails, for a later retry.
        if self.session_id is None:
            self.alert_service.reset()
            self._alert_force_close = False
            self.alert_label.setText("Experimental Alert: Waiting")

    def stop_monitoring(self) -> bool:
        ended = True
        if self.session_id is not None:
            try:
                self._end_remote_session()
            except (requests.RequestException, RuntimeError, ValueError) as error:
                ended = False
                print("SESSION END ERROR:", error)
                QMessageBox.warning(
                    self, "Session Not Ended",
                    f"Session {self.session_id} may still be RUNNING on the server.\n"
                    f"{error}\nReconnect and retry before starting another session.",
                )
        self._release_local_resources()
        if ended:
            self.status_label.setText("Status: Stopped")
            self.session_label.setText("Session ID: -")
        else:
            self.status_label.setText("Status: Database session end pending")
            self.session_label.setText(f"Session ID: {self.session_id} (pending)")
        return ended

    def build_session_summary(self) -> dict:
        if self.session_started_monotonic is None:
            raise RuntimeError("No active monitoring session.")
        duration = max(0.0, time.monotonic() - self.session_started_monotonic)
        baseline = self.baseline_data or {}
        camera = self.selected_camera or {}
        return {
            "session_id": self.session_id,
            "database_status": "RUNNING",
            "camera_name": camera.get("camera_name", "Unknown Camera"),
            "camera_id": camera.get("camera_id"),
            "baseline_id": self.baseline_id,
            "started_at": self.session_started_at,
            "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "duration_seconds": duration,
            "detection_count": self.detection_count,
            "pose_detected_count": self.pose_detected_count,
            "face_detected_count": self.face_detected_count,
            "average_shoulder": statistics.mean(self.shoulder_samples) if self.shoulder_samples else None,
            "average_neck": statistics.mean(self.neck_samples) if self.neck_samples else None,
            "baseline_shoulder": baseline.get("shoulder_angle"),
            "baseline_neck": baseline.get("lateral_tilt_baseline"),
        }

    def handle_stop(self) -> None:
        if self.session_started_monotonic is None or self.session_id is None:
            return
        summary = self.build_session_summary()
        try:
            remote = self._end_remote_session()
        except (requests.RequestException, RuntimeError, ValueError) as error:
            QMessageBox.warning(
                self, "Cannot End Session",
                "The database session was not confirmed as completed.\n"
                f"{error}\nMonitoring remains active. Check the Backend and press Stop again.",
            )
            return
        summary["database_status"] = remote["status"]
        summary["session_id"] = remote["session_id"]
        summary["started_at"] = remote.get("started_at") or summary["started_at"]
        summary["ended_at"] = remote.get("ended_at") or summary["ended_at"]
        summary["duration_seconds"] = remote.get("total_duration", summary["duration_seconds"])
        self.stop_monitoring()
        self.stop_requested.emit(summary)

    def hideEvent(self, event) -> None:
        self.stop_monitoring()
        super().hideEvent(event)
