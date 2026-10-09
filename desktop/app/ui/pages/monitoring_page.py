import cv2

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QGroupBox
)

from app.services.detection_service import DetectionService

class MonitoringPage(QWidget):

    stop_requested = Signal()

    def __init__(self):
        super().__init__()

        self.selected_camera = None
        self.baseline_id = None
        self.capture = None
        self.detector = None
        self.frame_count = 0

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_frame)

        layout = QVBoxLayout(self)

        self.title_label = QLabel("Real-time Monitoring")

        self.description_label = QLabel(
            "Live posture detection (risk assessment not enabled yet)."
        )

        info_group = QGroupBox("Monitoring Information")
        info_layout = QVBoxLayout(info_group)

        self.camera_label = QLabel("Camera: -")
        self.baseline_label = QLabel("Baseline ID: -")
        self.status_label = QLabel("Status: Not started")

        info_layout.addWidget(self.camera_label)
        info_layout.addWidget(self.baseline_label)
        info_layout.addWidget(self.status_label)

        self.preview_label = QLabel("Monitoring preview will appear here.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setStyleSheet(
            """
            QLabel {
                background-color: #111111;
                border: 1px solid #444444;
                border-radius: 8px;
            }
            """
        )

        detection_group = QGroupBox("Live Detection")
        detection_layout = QVBoxLayout(detection_group)

        self.detection_label = QLabel(
            "Pose: Waiting | Face: Waiting"
        )
        self.shoulder_label = QLabel("Shoulder Tilt: --")
        self.neck_label = QLabel("Neck Lateral Tilt: --")

        detection_layout.addWidget(self.detection_label)
        detection_layout.addWidget(self.shoulder_label)
        detection_layout.addWidget(self.neck_label)

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
        layout.addLayout(button_layout)

    def start_monitoring(
        self,
        camera: dict,
        baseline_id: int
    ) -> bool:

        self.stop_monitoring()

        self.selected_camera = camera.copy()
        self.baseline_id = baseline_id

        device_index = camera.get("device_index")

        if device_index is None:
            QMessageBox.warning(
                self,
                "Monitoring",
                "Camera device index is missing."
            )
            return False

        if not isinstance(baseline_id, int) or baseline_id <= 0:
            QMessageBox.warning(
                self,
                "Monitoring",
                "A saved Baseline ID is required."
            )
            return False

        self.camera_label.setText(
            f"Camera: {camera.get('camera_name', 'Unknown Camera')}"
        )

        self.baseline_label.setText(
            f"Baseline ID: {baseline_id}"
        )

        try:
            self.capture = cv2.VideoCapture(
                int(device_index)
            )

            if not self.capture.isOpened():
                raise RuntimeError("Unable to open camera.")

            self.detector = DetectionService()

        except Exception as error:
            self.stop_monitoring()

            QMessageBox.warning(
                self,
                "Monitoring Error",
                str(error)
            )
            return False

        self.frame_count = 0
        self.status_label.setText("Status: Monitoring")
        self.stop_button.setEnabled(True)

        self.timer.start()

        print(
            "MONITORING STARTED:",
            self.selected_camera,
            "BASELINE ID:",
            self.baseline_id
        )

        return True

    def update_frame(self) -> None:

        if self.capture is None:
            return

        success, frame = self.capture.read()

        if not success or frame is None:
            self.stop_monitoring()

            QMessageBox.warning(
                self,
                "Camera Error",
                "Unable to read camera frame."
            )
            return

        self.frame_count += 1

        if (
            self.detector is not None
            and self.frame_count % 5 == 0
        ):
            try:
                result = self.detector.process_frame(frame)

                pose_detected = result["pose_points"] is not None
                face_detected = result["face_detected"]

                pose_text = (
                    "Detected" if pose_detected else "Not Found"
                )
                face_text = (
                    "Detected" if face_detected else "Not Found"
                )

                self.detection_label.setText(
                    f"Pose: {pose_text} | Face: {face_text}"
                )

                shoulder = result["shoulder_tilt"]

                if shoulder is not None:
                    self.shoulder_label.setText(
                        f"Shoulder Tilt: {shoulder:+.2f}°"
                    )
                else:
                    self.shoulder_label.setText(
                        "Shoulder Tilt: --"
                    )

                neck_result = result["neck_lateral_tilt"]

                if neck_result is not None:
                    neck = neck_result["neck_tilt"]
                    self.neck_label.setText(
                        f"Neck Lateral Tilt: {neck:+.2f}°"
                    )
                else:
                    self.neck_label.setText(
                        "Neck Lateral Tilt: --"
                    )

            except Exception as error:
                self.stop_monitoring()

                QMessageBox.warning(
                    self,
                    "Detection Error",
                    str(error)
                )
                return

        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        height, width, channels = frame_rgb.shape

        image = QImage(
            frame_rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888
        ).copy()

        pixmap = QPixmap.fromImage(image)

        pixmap = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.preview_label.setPixmap(pixmap)

    def stop_monitoring(self) -> None:

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

        self.detection_label.setText(
            "Pose: Waiting | Face: Waiting"
        )
        self.shoulder_label.setText("Shoulder Tilt: --")
        self.neck_label.setText("Neck Lateral Tilt: --")

        self.preview_label.clear()
        self.preview_label.setText(
            "Monitoring preview will appear here."
        )

        self.status_label.setText("Status: Stopped")
        self.stop_button.setEnabled(False)

    def handle_stop(self) -> None:

        self.stop_monitoring()
        self.stop_requested.emit()

    def hideEvent(self, event) -> None:

        self.stop_monitoring()
        super().hideEvent(event)
