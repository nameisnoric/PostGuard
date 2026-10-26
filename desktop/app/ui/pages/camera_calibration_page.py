"""Reference-card camera preparation before personal baseline capture."""

import cv2
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.camera_setup import CameraCalibrationTracker


class CameraCalibrationPage(QWidget):
    back_requested = Signal(dict)
    continue_requested = Signal(dict, dict)

    def __init__(self):
        super().__init__()
        self.setProperty("page", True)
        self.capture = None
        self.selected_camera = None
        self.calibration_reference = None
        self.completion_notified = False
        self.tracker = CameraCalibrationTracker(stable_frames=10)

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_frame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 24, 48, 32)
        layout.setSpacing(12)

        title = QLabel("เตรียมกล้อง")
        title.setProperty("role", "title")
        subtitle = QLabel(
            "Step 2 of 4  ·  Hold a standard ID-size card inside the guide. "
            "PostGuard uses it only to calculate camera scale and alignment."
        )
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(16)
        preview_card = QFrame()
        preview_card.setProperty("card", True)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 14, 16, 16)
        preview_layout.setSpacing(10)
        self.preview_label = QLabel("ภาพสำหรับเตรียมกล้องจะแสดงที่นี่")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setProperty("preview", True)
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setMaximumSize(820, 461)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        preview_layout.addWidget(self.preview_label, 1)
        body.addWidget(preview_card, 3)

        status_card = QFrame()
        status_card.setProperty("card", True)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(10)
        heading = QLabel("ข้อมูลอ้างอิงกล้อง")
        heading.setProperty("role", "heading")
        status_layout.addWidget(heading)
        self.camera_label = QLabel('กล้อง: --')
        self.camera_label.setProperty("role", "muted")
        self.guidance_label = QLabel("วางบัตรให้อยู่ภายในกรอบ")
        self.guidance_label.setWordWrap(True)
        self.progress_label = QLabel('เฟรมที่นิ่ง: 0 / 10')
        self.progress_label.setProperty("role", "muted")
        status_layout.addWidget(self.camera_label)
        status_layout.addWidget(self.guidance_label)
        status_layout.addWidget(self.progress_label)

        result_grid = QGridLayout()
        result_grid.setHorizontalSpacing(12)
        self.result_values = {}
        for row, (key, label) in enumerate(
            (
                ("resolution", "Reference resolution"),
                ("scale", "Pixel scale"),
                ("roll", "Card roll"),
                ("perspective", "Perspective difference"),
            )
        ):
            name = QLabel(label)
            name.setProperty("role", "muted")
            value = QLabel("--")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.result_values[key] = value
            result_grid.addWidget(name, row, 0)
            result_grid.addWidget(value, row, 1)
        status_layout.addLayout(result_grid)
        privacy = QLabel(
            'ภาพจากกล้องและภาพบัตรจะอยู่บนอุปกรณ์นี้ โดยไม่บันทึกหรืออัปโหลด'
        )
        privacy.setProperty("role", "muted")
        privacy.setWordWrap(True)
        status_layout.addStretch()
        status_layout.addWidget(privacy)
        body.addWidget(status_card, 2)
        layout.addLayout(body, 1)

        actions = QHBoxLayout()
        self.back_button = QPushButton("กลับไปเลือกกล้อง")
        self.retry_button = QPushButton("เริ่มเตรียมกล้องใหม่")
        self.continue_button = QPushButton("ดูภาพหลังปรับแนวกล้อง")
        self.continue_button.setProperty("variant", "primary")
        self.continue_button.setEnabled(False)
        self.back_button.clicked.connect(self.handle_back)
        self.retry_button.clicked.connect(self.restart_preparation)
        self.continue_button.clicked.connect(self.handle_continue)
        actions.addWidget(self.back_button)
        actions.addWidget(self.retry_button)
        actions.addStretch()
        actions.addWidget(self.continue_button)
        layout.addLayout(actions)

    def set_camera(self, camera):
        self.stop_camera()
        self.selected_camera = camera.copy()
        self.tracker.reset()
        self.calibration_reference = None
        self.completion_notified = False
        self.continue_button.setEnabled(False)
        self._clear_result()
        self.camera_label.setText(
            f"กล้อง: {camera.get('camera_name', 'ไม่ทราบ')} | "
            f"{camera.get('resolution_width', '--')}x"
            f"{camera.get('resolution_height', '--')}"
        )
        self._open_camera()

    def _open_camera(self):
        if not self.selected_camera:
            return
        device_index = self.selected_camera.get("device_index")
        if type(device_index) is not int or device_index < 0:
            QMessageBox.warning(
                self, 'การเตรียมกล้อง', 'ต้องเลือกอุปกรณ์กล้องที่ถูกต้อง'
            )
            return
        self.capture = cv2.VideoCapture(device_index)
        if not self.capture.isOpened():
            self.stop_camera()
            QMessageBox.critical(
                self, 'การเตรียมกล้อง', 'ไม่สามารถเปิดกล้องที่เลือกได้'
            )
            return
        width = self.selected_camera.get("resolution_width")
        height = self.selected_camera.get("resolution_height")
        if type(width) is int and type(height) is int:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.guidance_label.setText('วางบัตรขนาดมาตรฐานไว้ภายในกรอบ')
        self.timer.start()

    def restart_preparation(self):
        self.tracker.reset()
        self.calibration_reference = None
        self.completion_notified = False
        self.continue_button.setEnabled(False)
        self._clear_result()
        if self.capture is None:
            self._open_camera()

    def update_frame(self):
        if self.capture is None or not self.capture.isOpened():
            return
        success, frame = self.capture.read()
        if not success or frame is None:
            self.stop_camera()
            self.guidance_label.setText('ไม่สามารถอ่านภาพจากกล้องได้')
            return
        result = self.tracker.process(frame)
        self.guidance_label.setText(result["guidance"])
        self.progress_label.setText(
            f"เฟรมที่นิ่ง: {result['stable_count']} / {result['stable_frames']}"
        )
        if result["reference"] is not None and self.calibration_reference is None:
            self._complete_preparation(result["reference"])
        self._show_frame(result["display_frame"])

    def _complete_preparation(self, reference):
        self.calibration_reference = reference.copy()
        self.continue_button.setEnabled(True)
        self._show_result(self.calibration_reference)
        if self.completion_notified:
            return
        self.completion_notified = True
        QMessageBox.information(
            self,
            'เตรียมกล้องสำเร็จ',
            "Your camera reference is ready.\n\n"
            f"เฟรมที่นิ่ง: {self.tracker.stable_frames}/{self.tracker.stable_frames}\n"
            f"Pixel scale: {reference['scale_avg']:.2f} px/mm\n"
            f"Card roll: {reference['card_roll_deg']:+.2f}°\n\n"
            "You can now review the adjusted camera preview.",
        )

    def _show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(pixmap)

    def _show_result(self, reference):
        self.result_values["resolution"].setText(
            f"{reference['frame_width']}x{reference['frame_height']}"
        )
        self.result_values["scale"].setText(f"{reference['scale_avg']:.2f} px/mm")
        self.result_values["roll"].setText(f"{reference['card_roll_deg']:+.2f}°")
        self.result_values["perspective"].setText(
            f"H {reference['horizontal_perspective']:.1%} | "
            f"V {reference['vertical_perspective']:.1%}"
        )

    def _clear_result(self):
        for value in self.result_values.values():
            value.setText("--")
        self.progress_label.setText('เฟรมที่นิ่ง: 0 / 10')

    def stop_camera(self):
        self.timer.stop()
        if self.capture is not None:
            if self.capture.isOpened():
                self.capture.release()
            self.capture = None
        self.preview_label.clear()
        self.preview_label.setText("ภาพสำหรับเตรียมกล้องจะแสดงที่นี่")

    def handle_back(self):
        camera = self.selected_camera.copy() if self.selected_camera else {}
        self.stop_camera()
        self.back_requested.emit(camera)

    def handle_continue(self):
        if not self.selected_camera or not self.calibration_reference:
            return
        camera = self.selected_camera.copy()
        reference = self.calibration_reference.copy()
        self.stop_camera()
        self.continue_requested.emit(camera, reference)

    def hideEvent(self, event):
        self.stop_camera()
        super().hideEvent(event)
