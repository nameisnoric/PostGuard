
import cv2

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal
)

from PySide6.QtGui import (
    QImage,
    QPixmap
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox
)

from app.services.detection_service import DetectionService


class CameraPreviewPage(QWidget):

    # ส่ง Signal กลับไป Camera Setup
    back_requested = Signal()

    # ส่งข้อมูลกล้องไป Personal Baseline
    continue_requested = Signal(dict)

    def __init__(self):
        super().__init__()

        # -------------------------
        # Camera State
        # -------------------------

        self.capture = None
        self.selected_camera = None

        # -------------------------
        # Detection State
        # -------------------------

        self.detector = None
        self.frame_count = 0

        self.detection_status_label = QLabel(
            "Pose: Waiting | Face: Waiting"
        )

        # -------------------------
        # Timer
        # -------------------------

        self.timer = QTimer(self)

        self.timer.setInterval(30)

        self.timer.timeout.connect(
            self.update_frame
        )

        # -------------------------
        # Main Layout
        # -------------------------

        layout = QVBoxLayout(self)

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "Camera Preview"
        )

        self.description_label = QLabel(
            "Check that your camera is positioned correctly."
        )

        # -------------------------
        # Camera Information
        # -------------------------

        self.camera_info_label = QLabel(
            "No camera selected."
        )

        # -------------------------
        # Preview
        # -------------------------

        self.preview_label = QLabel(
            "Camera preview will appear here."
        )

        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_label.setMinimumSize(
            640,
            480
        )

        self.preview_label.setStyleSheet(
            """
            QLabel {
                background-color: #111111;
                border: 1px solid #444444;
                border-radius: 8px;
            }
            """
        )

        # -------------------------
        # Buttons
        # -------------------------

        button_layout = QHBoxLayout()

        self.back_button = QPushButton(
            "Back"
        )

        self.continue_button = QPushButton(
            "Continue to Personal Baseline"
        )

        self.continue_button.setEnabled(
            False
        )

        button_layout.addWidget(
            self.back_button
        )

        button_layout.addWidget(
            self.continue_button
        )

        # -------------------------
        # Add Widgets
        # -------------------------

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.description_label
        )

        layout.addWidget(
            self.camera_info_label
        )

        layout.addWidget(
            self.detection_status_label
        )

        layout.addWidget(
            self.preview_label,
            1
        )

        layout.addLayout(
            button_layout
        )

        # -------------------------
        # Events
        # -------------------------

        self.back_button.clicked.connect(
            self.handle_back
        )

        self.continue_button.clicked.connect(
            self.handle_continue
        )

    # =========================================================
    # Start Preview
    # =========================================================

    def start_preview(
        self,
        camera: dict
    ) -> None:

        # ปิดกล้องและ Detector เดิมก่อน
        self.stop_preview()

        self.selected_camera = camera

        device_index = camera.get(
            "device_index"
        )

        width = camera.get(
            "resolution_width"
        )

        height = camera.get(
            "resolution_height"
        )

        self.camera_info_label.setText(
            (
                f"Device: {device_index} | "
                f"Resolution: {width}x{height}"
            )
        )

        print(
            "STARTING CAMERA PREVIEW:",
            camera
        )

        # -------------------------
        # Validate Camera
        # -------------------------

        if device_index is None:
            QMessageBox.warning(
                self,
                "PostGuard",
                "No camera device index was provided."
            )
            return

        # -------------------------
        # Open Camera
        # -------------------------

        self.capture = cv2.VideoCapture(
            int(device_index)
        )

        if not self.capture.isOpened():

            self.stop_preview()

            QMessageBox.critical(
                self,
                "PostGuard",
                "Unable to open the selected camera."
            )

            return

        # -------------------------
        # Initialize Detection
        # -------------------------

        try:
            self.detector = DetectionService()

        except Exception as error:

            self.stop_preview()

            QMessageBox.critical(
                self,
                "Detection Error",
                str(error)
            )

            return

        self.frame_count = 0

        self.detection_status_label.setText(
            "Pose: Waiting | Face: Waiting"
        )

        # -------------------------
        # Start Timer
        # -------------------------

        self.timer.start()

        self.continue_button.setEnabled(
            True
        )

        print(
            "CAMERA AND DETECTION STARTED"
        )

    # =========================================================
    # Update Camera Frame
    # =========================================================

    def update_frame(self) -> None:

        if self.capture is None:
            return

        if not self.capture.isOpened():
            return

        success, frame = self.capture.read()

        if not success or frame is None:

            print(
                "CAMERA ERROR: Cannot read frame"
            )

            self.stop_preview()

            QMessageBox.warning(
                self,
                "Camera Error",
                "Unable to read a frame from the camera."
            )

            return

        # -------------------------
        # Count Frames
        # -------------------------

        self.frame_count += 1

        # -------------------------
        # Detection Every 5 Frames
        # -------------------------

        if (
            self.detector is not None
            and self.frame_count % 5 == 0
        ):

            try:

                result = self.detector.process_frame(
                    frame
                )

                pose_detected = (
                    result["pose_points"] is not None
                )

                face_detected = (
                    result["face_detected"]
                )

                pose_status = (
                    "Detected"
                    if pose_detected
                    else "Not Found"
                )

                face_status = (
                    "Detected"
                    if face_detected
                    else "Not Found"
                )

                self.detection_status_label.setText(
                    f"Pose: {pose_status} | "
                    f"Face: {face_status}"
                )

            except Exception as error:

                self.stop_preview()

                QMessageBox.warning(
                    self,
                    "Detection Error",
                    str(error)
                )

                return

        # -------------------------
        # Convert BGR to RGB
        # -------------------------

        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        height, width, channels = (
            frame_rgb.shape
        )

        bytes_per_line = (
            channels * width
        )

        # -------------------------
        # Convert to Qt Image
        # -------------------------

        image = QImage(
            frame_rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888
        )

        pixmap = QPixmap.fromImage(
            image
        )

        # -------------------------
        # Resize Preview
        # -------------------------

        pixmap = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.preview_label.setPixmap(
            pixmap
        )

    # =========================================================
    # Stop Preview
    # =========================================================

    def stop_preview(self) -> None:

        # -------------------------
        # Stop Timer
        # -------------------------

        if self.timer.isActive():
            self.timer.stop()

        # -------------------------
        # Close Detection
        # -------------------------

        if self.detector is not None:

            try:
                self.detector.close()

            finally:
                self.detector = None

        # -------------------------
        # Release Camera
        # -------------------------

        if self.capture is not None:

            if self.capture.isOpened():
                self.capture.release()

            self.capture = None

        # -------------------------
        # Reset Preview
        # -------------------------

        self.preview_label.clear()

        self.preview_label.setText(
            "Camera preview will appear here."
        )

        # -------------------------
        # Reset Detection Status
        # -------------------------

        self.frame_count = 0

        self.detection_status_label.setText(
            "Pose: Waiting | Face: Waiting"
        )

        # -------------------------
        # Disable Continue
        # -------------------------

        self.continue_button.setEnabled(
            False
        )

        print(
            "CAMERA PREVIEW STOPPED"
        )

    # =========================================================
    # Back
    # =========================================================

    def handle_back(self) -> None:

        self.stop_preview()

        self.back_requested.emit()

    # =========================================================
    # Continue
    # =========================================================

    def handle_continue(self) -> None:

        if self.selected_camera is None:
            return

        camera = self.selected_camera

        # ปิดกล้องก่อนส่งต่อไป Baseline
        self.stop_preview()

        self.continue_requested.emit(
            camera
        )
