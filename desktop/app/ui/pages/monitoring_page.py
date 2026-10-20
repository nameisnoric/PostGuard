"""PostGuard Monitoring UI: Session API + experimental partial risk tracking."""

import math
import statistics
import time
from datetime import datetime

import cv2
import requests

from PySide6.QtCore import QLocale, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.detection_service import DetectionService
from app.services.api_client import APIClient
from app.services.risk_engine import assess_posture
from app.services.experimental_alert_service import ExperimentalAlertService
from app.services.alert_sound import AlertSoundPlayer
from app.services.posture_duration_tracker import (
    PostureDurationTracker,
    classify_neck_side_bending,
)
from app.services.session_summary_service import save_session_summary
from app.ui.utils.preview_sizing import fit_preview_label


class MonitoringPage(QWidget):
    stop_requested = Signal(dict)
    state_changed = Signal()

    def __init__(self):
        super().__init__()
        self.is_stopping = False
        self.selected_camera = None
        self.baseline_id = None
        self.baseline_data = None
        self.capture = None
        self.detector = None
        self.frame_count = 0
        self.session_id = None
        self.is_paused = False
        self.session_started_at = None
        self.session_started_monotonic = None
        self.detection_count = 0
        self.pose_detected_count = 0
        self.face_detected_count = 0
        self.shoulder_samples = []
        self.neck_samples = []
        self.posture_tracker = PostureDurationTracker()
        self.alert_service = ExperimentalAlertService()
        self.sound_player = AlertSoundPlayer()
        self._alert_force_close = False

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_frame)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the monitoring widgets and arrange the page."""
        self.setProperty("page", True)
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page_layout.addWidget(scroll)

        content = QWidget()
        content.setProperty("page", True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)
        scroll.setWidget(content)

        self.title_label = QLabel("การตรวจจับแบบเรียลไทม์")
        self.title_label.setProperty("role", "title")
        self.description_label = QLabel(
            "กล้องจะตรวจจับต่อเนื่องขณะเปิดหน้าแดชบอร์ดหรือประวัติ"
        )
        self.description_label.setProperty("role", "muted")

        info_group = self._create_information_group()
        self._setup_preview()
        detection_group = self._create_detection_group()
        risk_group = self._create_risk_group()
        button_layout = self._create_button_layout()

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        columns = QHBoxLayout()
        columns.setSpacing(16)

        camera_panel = QFrame()
        camera_panel.setProperty("card", True)
        camera_layout = QVBoxLayout(camera_panel)
        camera_layout.setContentsMargins(14, 14, 14, 14)
        camera_layout.setSpacing(10)
        camera_layout.addWidget(info_group)
        camera_layout.addWidget(
            self.preview_label,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )
        camera_layout.addLayout(button_layout)

        metrics_panel = QFrame()
        metrics_panel.setProperty("card", True)
        metrics_layout = QVBoxLayout(metrics_panel)
        metrics_layout.setContentsMargins(14, 14, 14, 14)
        metrics_layout.setSpacing(10)
        metrics_layout.addWidget(detection_group)
        metrics_layout.addWidget(risk_group)
        metrics_layout.addStretch()

        columns.addWidget(camera_panel, 3)
        columns.addWidget(metrics_panel, 2)
        layout.addLayout(columns, 1)

    def _create_information_group(self) -> QGroupBox:
        info_group = QGroupBox("ข้อมูลการตรวจจับ")
        info_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        info_layout = QVBoxLayout(info_group)
        self.camera_label = QLabel('กล้อง: -')
        self.baseline_label = QLabel('Baseline ID: -')
        self.session_label = QLabel('Session ID: -')
        self.baseline_shoulder_label = QLabel('ค่าอ้างอิงความเอียงไหล่: -')
        self.baseline_neck_label = QLabel('ค่าอ้างอิงความเอียงคอด้านข้าง: -')
        self.status_label = QLabel('สถานะ: ยังไม่เริ่ม')
        for label in (
            self.camera_label, self.baseline_label, self.session_label,
            self.baseline_shoulder_label, self.baseline_neck_label,
            self.status_label,
        ):
            info_layout.addWidget(label)

        return info_group

    def _setup_preview(self) -> None:
        self.preview_label = QLabel("ภาพการตรวจจับจะแสดงที่นี่")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(720, 405)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.preview_label.setProperty("preview", True)

    def _create_detection_group(self) -> QGroupBox:
        detection_group = QGroupBox("ผลตรวจจับปัจจุบัน")
        detection_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        detection_layout = QVBoxLayout(detection_group)
        self.detection_label = QLabel('ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ')
        self.shoulder_label = QLabel('ความเอียงไหล่: --')
        self.neck_label = QLabel('ความเอียงคอด้านข้าง: --')
        self.shoulder_difference_label = QLabel('ผลต่างความเอียงไหล่: --')
        self.neck_difference_label = QLabel('ผลต่างความเอียงคอ: --')
        for label in (
            self.detection_label, self.shoulder_label, self.neck_label,
            self.shoulder_difference_label, self.neck_difference_label,
        ):
            detection_layout.addWidget(label)

        return detection_group

    def _create_risk_group(self) -> QGroupBox:
        # This is a test control, NOT a validated clinical cutoff.
        risk_group = QGroupBox("การประเมินความเสี่ยงบางส่วน (ทดลอง)")
        risk_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        risk_layout = QVBoxLayout(risk_group)
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel('เกณฑ์ทดลองการเอียงคอด้านข้าง:'))
        self._last_neck_threshold = 10.0
        self.threshold_enabled = QCheckBox("เปิดใช้งาน")
        self.threshold_enabled.setToolTip(
            'เปิดใช้เกณฑ์ทดลองการเอียงคอด้านข้าง'
        )
        self.threshold_enabled.toggled.connect(self.set_threshold_enabled)
        threshold_layout.addWidget(self.threshold_enabled)
        self.neck_threshold_spin = QDoubleSpinBox()
        # Keep numeric controls readable regardless of the Windows regional locale.
        self.neck_threshold_spin.setLocale(QLocale.c())
        self.neck_threshold_spin.setRange(0.0, 45.0)
        self.neck_threshold_spin.setDecimals(1)
        self.neck_threshold_spin.setSingleStep(0.5)
        self.neck_threshold_spin.setSuffix("°")
        self.neck_threshold_spin.setSpecialValueText("Disabled (0°)")
        self.neck_threshold_spin.setValue(0.0)
        self.neck_threshold_spin.setMinimumWidth(120)
        self.neck_threshold_spin.setKeyboardTracking(False)
        self.neck_threshold_spin.setEnabled(False)
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

        return risk_group

    def set_threshold_enabled(self, enabled: bool) -> None:
        """Make the experimental cutoff an explicit opt-in control."""
        if not enabled and self.neck_threshold_spin.value() > 0:
            self._last_neck_threshold = self.neck_threshold_spin.value()
        self.neck_threshold_spin.blockSignals(True)
        self.neck_threshold_spin.setEnabled(enabled)
        self.neck_threshold_spin.setValue(
            self._last_neck_threshold if enabled else 0.0
        )
        self.neck_threshold_spin.blockSignals(False)
        self.reset_risk_tracking()

    def _create_button_layout(self) -> QHBoxLayout:
        button_layout = QHBoxLayout()

        self.pause_button = QPushButton("หยุดชั่วคราว")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.handle_pause_resume)

        self.stop_button = QPushButton("หยุดการตรวจจับ")
        self.stop_button.setProperty("variant", "danger")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.handle_stop)

        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.pause_button)
        button_layout.setStretch(0, 1)
        button_layout.setStretch(1, 1)

        return button_layout

    @staticmethod
    def _response_error(response):

        try:
            payload = response.json()
            detail = (
                payload.get("detail", response.text)
                if isinstance(payload, dict)
                else response.text
            )
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
        self.baseline_shoulder_label.setText(f"ค่าอ้างอิงความเอียงไหล่: {shoulder:+.2f}°")
        self.baseline_neck_label.setText(f"ค่าอ้างอิงความเอียงคอด้านข้าง: {neck:+.2f}°")
        self.baseline_data = baseline

        return baseline

    def start_monitoring(self, camera: dict, baseline_id: int) -> bool:
        if not self.stop_monitoring():
            QMessageBox.warning(
                self, 'ข้อผิดพลาดของเซสชัน',
                "The previous database session could not be ended. "
                "Check your connection and retry.",
            )
            return False

        self.selected_camera = camera.copy()
        self.baseline_id = baseline_id
        device_index = camera.get("device_index")
        camera_id = camera.get("camera_id")
        if device_index is None:
            QMessageBox.warning(self, "การตรวจจับ", 'ไม่พบหมายเลขอุปกรณ์กล้อง')
            return False
        if type(baseline_id) is not int or baseline_id <= 0:
            QMessageBox.warning(self, "การตรวจจับ", 'ต้องมี Baseline ID ที่บันทึกแล้ว')
            return False

        try:
            if type(camera_id) is not int or camera_id <= 0:
                raise ValueError('Camera ID ไม่ถูกต้อง')
            self.load_personal_baseline(baseline_id, camera_id)
        except (requests.RequestException, RuntimeError, ValueError, TypeError) as error:
            QMessageBox.warning(self, 'ข้อผิดพลาดของค่าอ้างอิง', str(error))
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
            QMessageBox.warning(self, 'ข้อผิดพลาดในการตรวจจับ', str(error))
            return False
        self.frame_count = 0
        self.session_started_at = session.get("started_at") or (
            datetime.now().astimezone().isoformat(timespec="seconds")
        )
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
        self.status_label.setText('สถานะ: กำลังตรวจจับ (RUNNING)')
        self.is_paused = False
        self.pause_button.setText("หยุดชั่วคราว")
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.timer.start()
        self.state_changed.emit()
        print("MONITORING STARTED: SESSION ID", self.session_id)
        return True

    def reset_risk_tracking(self, *_args) -> None:
        """Changing threshold resets duration and closes any active alert."""
        if self.session_id is not None and self.alert_service.active_event_id is not None:
            self._alert_force_close = not self.alert_service.close_if_active()
            if self._alert_force_close:
                self.alert_label.setText("Experimental Alert: End pending (API unavailable)")
            else:
                self.alert_label.setText("Experimental Alert: Cleared")

        self.posture_tracker.reset()
        self.side_bending_label.setText("Neck Side-bending: N/A")
        self.duration_label.setText("Continuous Side-bending: N/A")
        self.partial_factors_label.setText("Side-bending Score: N/A | Duration Score: N/A")
        self.risk_label.setText("Risk Score: N/A (PARTIAL - missing factors)")
        if self.session_id is None:
            self.alert_label.setText("Experimental Alert: Waiting")
        if self.alert_service.active_event_id is None:
            self.sound_player.notify(False)

    def apply_notification_settings(self, settings: dict) -> None:
        self.sound_player.apply_settings(settings)

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
        self.sound_player.notify(
            self.alert_service.active_event_id is not None,
            new_alert=action == "created",
        )

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
            self.shoulder_difference_label.setText('ผลต่างความเอียงไหล่: --')
        if (
            type(current_neck) in (int, float)
            and type(baseline_neck) in (int, float)
            and math.isfinite(current_neck)
            and math.isfinite(baseline_neck)
        ):
            difference = current_neck - baseline_neck
            self.neck_difference_label.setText(f"Neck Difference: {difference:+.2f}°")
        else:
            self.neck_difference_label.setText('ผลต่างความเอียงคอ: --')

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
        if self.capture is None or self.is_paused or self.is_stopping:
            return

        success, frame = self.capture.read()
        if not success or frame is None:
            self._finish_after_capture_error()
            QMessageBox.warning(self, 'ข้อผิดพลาดของกล้อง', "Unable to read camera frame.")
            return

        self.frame_count += 1
        if self.detector is not None and self.frame_count % 5 == 0:
            try:
                result = self.detector.process_frame(frame)
                self.record_detection_sample(result)
                self.update_baseline_comparison(result)
                self.update_partial_risk(result)
                self._update_detection_labels(result)
            except Exception as error:
                self._finish_after_capture_error()
                QMessageBox.warning(self, 'ข้อผิดพลาดของระบบตรวจจับ', str(error))
                return
        self._update_preview(frame)

    def _update_detection_labels(self, result: dict) -> None:
        pose_text = "ตรวจพบ" if result["pose_points"] is not None else "ไม่พบ"
        face_text = "ตรวจพบ" if result["face_detected"] else "ไม่พบ"
        self.detection_label.setText(f"ท่าทาง: {pose_text} | ใบหน้า: {face_text}")
        shoulder = result["shoulder_tilt"]
        self.shoulder_label.setText(
            f"ความเอียงไหล่: {shoulder:+.2f}°" if shoulder is not None else 'ความเอียงไหล่: --'
        )
        neck_result = result["neck_lateral_tilt"]
        neck = neck_result.get("neck_tilt") if isinstance(neck_result, dict) else None
        self.neck_label.setText(
            f"ความเอียงคอด้านข้าง: {neck:+.2f}°" if neck is not None else 'ความเอียงคอด้านข้าง: --'
        )

    def _update_preview(self, frame) -> None:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = frame_rgb.shape
        fit_preview_label(
            self.preview_label,
            width,
            height,
            720,
            480,
        )
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

    def _finish_after_capture_error(self) -> None:
        self._close_capture_resources()
        self.pause_button.setEnabled(False)
        self.status_label.setText('สถานะ: หยุดตรวจจับ กำลังจบเซสชัน')
        self.handle_stop()

    def _close_capture_resources(self) -> None:
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

    def _release_local_resources(self) -> None:
        self._close_capture_resources()
        self.frame_count = 0
        self.detection_label.setText('ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ')
        self.shoulder_label.setText('ความเอียงไหล่: --')
        self.neck_label.setText('ความเอียงคอด้านข้าง: --')
        self.shoulder_difference_label.setText('ผลต่างความเอียงไหล่: --')
        self.neck_difference_label.setText('ผลต่างความเอียงคอ: --')
        self.preview_label.clear()
        self.preview_label.setText("ภาพการตรวจจับจะแสดงที่นี่")
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("หยุดชั่วคราว")
        self.is_paused = False
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
                    self, 'ยังไม่สามารถจบเซสชัน',
                    f"Session {self.session_id} may still be RUNNING on the server.\n"
                    f"{error}\nReconnect and retry before starting another session.",
                )

        self._release_local_resources()
        if ended:
            self.status_label.setText('สถานะ: หยุดแล้ว')
            self.session_label.setText('Session ID: -')
        else:
            self.status_label.setText('สถานะ: รอยืนยันการจบเซสชันจากฐานข้อมูล')
            self.session_label.setText(f"Session ID: {self.session_id} (pending)")

        self.state_changed.emit()
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
            "average_shoulder": (
                statistics.mean(self.shoulder_samples) if self.shoulder_samples else None
            ),
            "average_neck": (
                statistics.mean(self.neck_samples) if self.neck_samples else None
            ),
            "baseline_shoulder": baseline.get("shoulder_angle"),
            "baseline_neck": baseline.get("lateral_tilt_baseline"),
        }

    def _change_remote_session_status(
        self,
        action: str,
        expected_status: str,
    ) -> dict:
        """
        Change session state and verify Backend result.
        Recover if a request succeeded but its response was lost.
        """
        session_id = self.session_id

        if type(session_id) is not int or session_id <= 0:
            raise ValueError("No valid active session")

        if action == "pause":
            request_function = APIClient.pause_session
        elif action == "resume":
            request_function = APIClient.resume_session
        else:
            raise ValueError("Unsupported session action")

        response = None

        try:
            response = request_function(session_id)
        except requests.RequestException:
            # The server may have committed the change.
            # Check its authoritative state before reporting failure.
            pass

        if response is not None and response.ok:
            data = response.json()
        else:
            check = APIClient.get_session(session_id)

            if not check.ok:
                if response is not None:
                    raise RuntimeError(
                        self._response_error(response)
                    )
                raise RuntimeError(
                    "Session state could not be confirmed"
                )

            data = check.json()

            if data.get("status") != expected_status:
                if response is not None:
                    raise RuntimeError(
                        self._response_error(response)
                    )
                raise RuntimeError(
                    "Backend did not confirm "
                    + expected_status
                )

        if not isinstance(data, dict):
            raise ValueError("Invalid session response")

        if data.get("session_id") != session_id:
            raise ValueError("Session ID mismatch")

        if data.get("status") != expected_status:
            raise RuntimeError(
                f"Expected {expected_status}, "
                f"received {data.get('status')}"
            )

        return data

    def handle_pause_resume(self) -> None:
        """Pause or resume without creating a new session."""

        if self.session_id is None or self.is_stopping or self.capture is None:
            return

        self.pause_button.setEnabled(False)

        if self.is_paused:
            self._resume_monitoring()
        else:
            self._pause_monitoring()

        if self.session_id is not None:
            self.pause_button.setEnabled(True)
        self.state_changed.emit()

    def _pause_monitoring(self) -> None:

        try:
            remote = self._change_remote_session_status(
                action="pause",
                expected_status="PAUSED",
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            QMessageBox.warning(
                self,
                'หยุดชั่วคราวไม่สำเร็จ',
                "ไม่สามารถยืนยันสถานะ PAUSED ได้\n"
                f"{error}\n"
                "กรุณาตรวจสอบการเชื่อมต่อ",
            )
            return

        # Backend confirmed PAUSED.
        self.timer.stop()
        self.is_paused = True

        # Backend closes active alerts when pausing.
        # Clear stale local alert state.
        self.alert_service.reset()
        self._alert_force_close = False

        # A continuous posture episode must not span a pause.

        self.posture_tracker.reset()

        self.preview_label.clear()
        self.preview_label.setText('หยุดการตรวจจับชั่วคราว')

        self.side_bending_label.setText("การเอียงคอด้านข้าง: หยุดชั่วคราว")
        self.duration_label.setText("ระยะเวลาการเอียงต่อเนื่อง: หยุดชั่วคราว")
        self.alert_label.setText("การแจ้งเตือนทดลอง: หยุดชั่วคราว")

        self.status_label.setText(
            "สถานะ: หยุดชั่วคราว "
            f"(จำนวนครั้ง: {remote['pause_count']})"
        )
        self.pause_button.setText("ตรวจจับต่อ")

    def _resume_monitoring(self) -> None:

        try:
            remote = self._change_remote_session_status(
                action="resume",
                expected_status="RUNNING",
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            QMessageBox.warning(
                self,
                'ตรวจจับต่อไม่สำเร็จ',
                "ไม่สามารถยืนยันสถานะ RUNNING ได้\n"
                f"{error}\n"
                "กรุณาตรวจสอบการเชื่อมต่อ",
            )
            return

        # Resume only after Backend confirms RUNNING.
        self.is_paused = False

        self.posture_tracker.reset()
        self.alert_service.reset()
        self._alert_force_close = False

        self.preview_label.setText('กำลังตรวจจับต่อ...')
        self.alert_label.setText("การแจ้งเตือนทดลอง: กำลังรอ")
        self.side_bending_label.setText("การเอียงคอด้านข้าง: กำลังรอ")
        self.duration_label.setText("ระยะเวลาการเอียงต่อเนื่อง: กำลังรอ")

        self.status_label.setText(
            "สถานะ: กำลังตรวจจับ (RUNNING) "
            f"| เวลาหยุดรวม: "
            f"{remote['paused_duration']} วินาที"
        )
        self.pause_button.setText("หยุดชั่วคราว")

        self.timer.start()

    def handle_stop(self) -> None:
        if self.is_stopping:
            return
        self.is_stopping = True
        self.state_changed.emit()
        try:
            self._finish_session()
        finally:
            self.is_stopping = False
            self.state_changed.emit()

    def _finish_session(self) -> None:
        if (
            self.session_started_monotonic is None
            or self.session_id is None
        ):
            return

        # 1. Snapshot detection statistics before resetting
        summary = self.build_session_summary()

        # 2. End the remote session

        try:
            remote = self._end_remote_session()

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
        ) as error:
            QMessageBox.warning(
                self,
                'ไม่สามารถจบเซสชัน',
                "Backend ยังไม่ยืนยันว่า Session สิ้นสุด\n"
                f"{error}\n"
                "กรุณาตรวจสอบ Backend แล้วกด Stop อีกครั้ง",
            )
            return

        # 3. Use authoritative session data from Backend
        summary["database_status"] = remote["status"]
        summary["session_id"] = remote["session_id"]
        summary["started_at"] = (
            remote.get("started_at")
            or summary["started_at"]
        )
        summary["ended_at"] = (
            remote.get("ended_at")
            or summary["ended_at"]
        )
        summary["duration_seconds"] = (
            remote.get("total_duration")
            if remote.get("total_duration") is not None
            else summary["duration_seconds"]
        )

        # 4. Release camera and local resources
        self.stop_monitoring()

        # 5. Save the measured summary to Backend
        summary["summary_save_status"] = "FAILED"
        summary["summary_save_error"] = None

        try:
            result = save_session_summary(summary)

            summary["summary_save_status"] = result["status"]
            summary["saved_summary"] = result["summary"]

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            summary["summary_save_error"] = str(error)

            QMessageBox.warning(
                self,
                'เกิดข้อผิดพลาดในการบันทึกสรุป',
                "Session สิ้นสุดแล้ว แต่ยังบันทึก Summary "
                "ไม่สำเร็จ\n\n"
                f"{error}\n\n"
                "สามารถกด Retry ที่หน้า Summary ได้",
            )

        # 6. Show summary page
        self.stop_requested.emit(summary)

    # Page visibility does not own session lifetime. MainWindow explicitly ends
    # and saves the session on Stop, logout or application close.
