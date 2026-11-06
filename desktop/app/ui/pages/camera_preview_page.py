import cv2

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QMessageBox,
)

from app.services.detection_service import DetectionService
from app.ui.utils.preview_sizing import fit_preview_label


class CameraPreviewPage(QWidget):
    back_requested = Signal()
    continue_requested = Signal(dict)

    def __init__(self):
        super().__init__()

        self.capture = None
        self.selected_camera = None
        self.last_pose_points = None
        self.detector = None
        self.frame_count = 0

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_frame)

        layout = QVBoxLayout(self)
        self.setProperty("page", True)
        layout.setContentsMargins(72, 28, 72, 36)
        layout.setSpacing(12)

        self.title_label = QLabel("ตรวจสอบกล้องของคุณ")
        self.title_label.setStyleSheet(
            "font-size: 30px;"
            "font-weight: 800;"
            "color: #0f172a;"
        )

        self.description_label = QLabel(
            "ขั้นตอน 2 จาก 4  ·  ตรวจว่ากล้องเปิดได้และเห็นคุณชัดเจน"
        )
        self.description_label.setStyleSheet(
            "font-size: 13px;"
            "color: #64748b;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)

        body = QHBoxLayout()
        body.setSpacing(18)

        # Equal left/right side widths keep the actual camera preview
        # horizontally centered while status remains on the right.
        left_balance = QWidget()
        left_balance.setFixedWidth(260)

        preview_card = QFrame()
        preview_card.setStyleSheet(
            "QFrame {"
            "background: #ffffff;"
            "border: 1px solid #dbe4ef;"
            "border-radius: 16px;"
            "}"
        )

        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(6)

        preview_title = QLabel("ภาพจากกล้อง")
        preview_title.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 800;"
            "color: #0f172a;"
            "border: none;"
        )

        preview_help = QLabel(
            "ให้ใบหน้าและหัวไหล่อยู่ในภาพ และตรวจว่าภาพไม่มืดหรือเบลอ"
        )
        preview_help.setStyleSheet(
            "font-size: 12px;"
            "color: #64748b;"
            "border: none;"
        )

        self.preview_label = QLabel(
            "ภาพตัวอย่างจากกล้องจะแสดงที่นี่"
        )
        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.preview_label.setMinimumSize(960, 540)
        self.preview_label.setMaximumSize(960, 540)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )
        self.preview_label.setProperty("preview", True)

        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(preview_help)
        preview_layout.addWidget(
            self.preview_label,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )

        status_card = QFrame()
        status_card.setFixedWidth(260)
        status_card.setStyleSheet(
            "QFrame {"
            "background: #ffffff;"
            "border: 2px solid #2563eb;"
            "border-radius: 16px;"
            "}"
        )

        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 18, 18, 18)
        status_layout.setSpacing(12)

        status_title = QLabel("สถานะกล้อง")
        status_title.setStyleSheet(
            "font-size: 21px;"
            "font-weight: 800;"
            "color: #0f172a;"
            "border: none;"
        )

        self.camera_info_label = QLabel("ยังไม่ได้เลือกกล้อง")
        self.camera_info_label.setWordWrap(True)
        self.camera_info_label.setStyleSheet(
            "font-size: 12px;"
            "color: #475569;"
            "border: none;"
        )

        self.detection_status_label = QLabel(
            "ร่างกาย: กำลังรอ\nใบหน้า: กำลังรอ"
        )
        self.detection_status_label.setWordWrap(True)
        self.detection_status_label.setStyleSheet(
            "font-size: 16px;"
            "font-weight: 800;"
            "color: #15803d;"
            "border: none;"
        )

        self.shoulder_tilt_label = QLabel("")
        self.neck_tilt_label = QLabel("")
        self.shoulder_tilt_label.hide()
        self.neck_tilt_label.hide()

        ready_box = QLabel(
            "✓ พร้อมใช้งาน\nกล้องทำงานปกติและตรวจพบคุณแล้ว"
        )
        ready_box.setWordWrap(True)
        ready_box.setStyleSheet(
            "QLabel {"
            "background: #eefbf1;"
            "border: 1px solid #bbf7d0;"
            "border-radius: 10px;"
            "padding: 10px;"
            "font-size: 13px;"
            "font-weight: 700;"
            "color: #166534;"
            "}"
        )

        status_layout.addWidget(status_title)
        status_layout.addWidget(self.camera_info_label)
        status_layout.addWidget(self.detection_status_label)
        status_layout.addStretch(1)
        status_layout.addWidget(ready_box)

        body.addWidget(left_balance)

        body.addWidget(
            preview_card,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

        body.addWidget(status_card)

        layout.addLayout(body, 1)

        buttons = QHBoxLayout()

        self.back_button = QPushButton("ย้อนกลับ")
        self.continue_button = QPushButton(
            "ไปยังการเตรียมกล้อง"
        )
        self.continue_button.setProperty(
            "variant",
            "primary",
        )
        self.continue_button.setEnabled(False)

        buttons.addWidget(self.back_button)
        buttons.addWidget(self.continue_button)

        layout.addLayout(buttons)

        self.back_button.clicked.connect(self.handle_back)
        self.continue_button.clicked.connect(
            self.handle_continue
        )

    def _center_preview_now(
        self,
    ) -> None:
        """
        Keep preview_label horizontally centered relative to the
        whole CameraPreviewPage.

        This runs after Qt layout/resizing so status cards cannot
        push the live camera preview away from page center.
        """

        if not hasattr(
            self,
            "preview_label",
        ):
            return

        current_center = (
            self.preview_label.mapTo(
                self,
                self.preview_label.rect().center(),
            ).x()
        )

        target_center = (
            self.rect().center().x()
        )

        delta_x = (
            target_center
            - current_center
        )

        if abs(delta_x) <= 2:
            return

        self.preview_label.move(
            self.preview_label.x() + delta_x,
            self.preview_label.y(),
        )


    def resizeEvent(
        self,
        event,
    ) -> None:

        super().resizeEvent(
            event
        )

        QTimer.singleShot(
            0,
            self._center_preview_now,
        )


    def start_preview(self, camera: dict) -> None:
        self.stop_preview()
        self.selected_camera = camera

        device_index = camera.get("device_index")
        width = camera.get("resolution_width")
        height = camera.get("resolution_height")

        self.camera_info_label.setText(
            f"อุปกรณ์: {device_index}\n"
            f"ความละเอียด: {width}x{height}"
        )

        if device_index is None:
            QMessageBox.warning(
                self,
                "PostGuard",
                "ไม่พบหมายเลขอุปกรณ์กล้อง",
            )
            return

        if (
            type(width) is not int
            or type(height) is not int
            or width <= 0
            or height <= 0
        ):
            QMessageBox.warning(
                self,
                "PostGuard",
                "กล้องที่เลือกไม่มีข้อมูลความละเอียดที่ถูกต้อง",
            )
            return

        self.capture = cv2.VideoCapture(
            int(device_index),
            cv2.CAP_DSHOW,
        )

        if not self.capture.isOpened():
            self.capture.release()
            self.capture = cv2.VideoCapture(
                int(device_index),
                cv2.CAP_ANY,
            )

        if not self.capture.isOpened():
            self.stop_preview()
            QMessageBox.critical(
                self,
                "PostGuard",
                "ไม่สามารถเปิดกล้องที่เลือกได้",
            )
            return

        self.capture.set(
            cv2.CAP_PROP_FOURCC,
            cv2.VideoWriter_fourcc(*"MJPG"),
        )
        self.capture.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            width,
        )
        self.capture.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            height,
        )
        self.capture.set(
            cv2.CAP_PROP_FPS,
            30,
        )

        try:
            self.detector = DetectionService()

        except Exception as error:
            self.stop_preview()
            QMessageBox.critical(
                self,
                "ข้อผิดพลาดของระบบตรวจจับ",
                str(error),
            )
            return

        self.frame_count = 0
        self.detection_status_label.setText(
            "ร่างกาย: กำลังรอ\nใบหน้า: กำลังรอ"
        )

        self.timer.start()
        self.continue_button.setEnabled(True)

    def update_frame(self) -> None:
        if self.capture is None:
            return

        if not self.capture.isOpened():
            return

        success, frame = self.capture.read()

        if not success or frame is None:
            self.stop_preview()
            QMessageBox.warning(
                self,
                "ข้อผิดพลาดของกล้อง",
                "ไม่สามารถอ่านภาพจากกล้องได้",
            )
            return

        self.frame_count += 1

        if (
            self.detector is not None
            and self.frame_count % 5 == 0
        ):
            try:
                result = self.detector.process_frame(frame)

                shoulder_tilt = result["shoulder_tilt"]

                if shoulder_tilt is not None:
                    self.shoulder_tilt_label.setText(
                        f"ความเอียงไหล่: {shoulder_tilt:+.2f}°"
                    )
                else:
                    self.shoulder_tilt_label.setText(
                        "ความเอียงไหล่: --"
                    )

                neck_result = result["neck_lateral_tilt"]

                if neck_result is not None:
                    neck_angle = neck_result["neck_tilt"]
                    self.neck_tilt_label.setText(
                        f"ความเอียงคอด้านข้าง: {neck_angle:+.2f}°"
                    )
                else:
                    self.neck_tilt_label.setText(
                        "ความเอียงคอด้านข้าง: --"
                    )

                pose_detected = (
                    result["pose_points"] is not None
                )
                self.last_pose_points = result["pose_points"]

                face_detected = result["face_detected"]

                pose_status = (
                    "ตรวจพบ"
                    if pose_detected
                    else "ไม่พบ"
                )

                face_status = (
                    "ตรวจพบ"
                    if face_detected
                    else "ไม่พบ"
                )

                self.detection_status_label.setText(
                    f"ร่างกาย: {pose_status}\n"
                    f"ใบหน้า: {face_status}"
                )

            except Exception as error:
                self.stop_preview()
                QMessageBox.warning(
                    self,
                    "ข้อผิดพลาดของระบบตรวจจับ",
                    str(error),
                )
                return

        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
        )

        height, width, channels = frame_rgb.shape

        fit_preview_label(
            self.preview_label,
            width,
            height,
            960,
            540,
        )

        bytes_per_line = channels * width

        image = QImage(
            frame_rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )

        pixmap = QPixmap.fromImage(image)

        pixmap = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.preview_label.setPixmap(pixmap)

    def stop_preview(self) -> None:
        if self.timer.isActive():
            self.timer.stop()

        if self.detector is not None:
            try:
                self.detector.close()
            finally:
                self.detector = None

        if self.capture is not None:
            if self.capture.isOpened():
                self.capture.release()

            self.capture = None

        self.preview_label.clear()
        self.preview_label.setText(
            "ภาพตัวอย่างจากกล้องจะแสดงที่นี่"
        )
        self.preview_label.setMinimumSize(960, 540)
        self.preview_label.setMaximumSize(960, 540)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )

        self.frame_count = 0
        self.last_pose_points = None

        self.detection_status_label.setText(
            "ร่างกาย: กำลังรอ\nใบหน้า: กำลังรอ"
        )

        self.shoulder_tilt_label.setText(
            "ความเอียงไหล่: --"
        )
        self.neck_tilt_label.setText(
            "ความเอียงคอด้านข้าง: --"
        )

        self.continue_button.setEnabled(False)

    def handle_back(self) -> None:
        self.stop_preview()
        self.back_requested.emit()

    def handle_continue(self) -> None:
        if self.selected_camera is None:
            return

        camera = self.selected_camera
        self.stop_preview()
        self.continue_requested.emit(camera)

    def draw_pose_landmarks(
        self,
        frame,
        points,
    ) -> None:
        return
