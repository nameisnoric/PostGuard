
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
    QSizePolicy,
    QMessageBox
)

from app.services.camera_setup import adjust_camera_frame
from app.services.detection_service import DetectionService
from app.ui.utils.preview_sizing import fit_preview_label


class CameraPreviewPage(QWidget):

    # ส่ง Signal กลับไป Camera Setup
    back_requested = Signal(dict)

    # ส่งข้อมูลกล้องไป Personal Baseline
    continue_requested = Signal(dict)

    def __init__(self):
        super().__init__()

        # -------------------------
        # Camera State
        # -------------------------

        self.capture = None
        self.selected_camera = None
        self.last_pose_points = None

        # -------------------------
        # Detection State
        # -------------------------

        self.detector = None
        self.frame_count = 0

        self.detection_status_label = QLabel(
            'ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ'
        )
        
        self.shoulder_tilt_label = QLabel(
            'ความเอียงไหล่: --'
        )
        
        self.neck_tilt_label = QLabel(
            'ความเอียงคอด้านข้าง: --'
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
        self.setProperty("page", True)
        layout.setContentsMargins(72, 28, 72, 36)
        layout.setSpacing(10)

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "ตรวจสอบกล้องของคุณ"
        )
        self.title_label.setProperty("role", "title")

        self.description_label = QLabel(
            "ขั้นตอน 3 จาก 4  ·  ตรวจสอบภาพหลังแก้การเอียงของกล้อง"
        )
        self.description_label.setProperty("role", "muted")

        # -------------------------
        # Camera Information
        # -------------------------

        self.camera_info_label = QLabel(
            "ยังไม่ได้เลือกกล้อง"
        )
        self.camera_info_label.setProperty("role", "muted")

        # -------------------------
        # Preview
        # -------------------------

        self.preview_label = QLabel(
            "ภาพตัวอย่างจากกล้องจะแสดงที่นี่"
        )

        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_label.setMinimumSize(
            640,
            360
        )
        self.preview_label.setMaximumSize(960, 540)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )

        self.preview_label.setProperty("preview", True)

        # -------------------------
        # Buttons
        # -------------------------

        button_layout = QHBoxLayout()

        self.back_button = QPushButton(
            "ย้อนกลับ"
        )

        self.continue_button = QPushButton(
            "ไปยังค่าท่าทางอ้างอิงส่วนบุคคล"
        )
        self.continue_button.setProperty("variant", "primary")

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
            self.shoulder_tilt_label
        )
        
        layout.addWidget(
            self.neck_tilt_label
        )
        
        preview_row = QHBoxLayout()
        preview_row.addStretch(1)
        preview_row.addWidget(self.preview_label)
        preview_row.addStretch(1)
        layout.addLayout(preview_row, 1)

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

        calibration = camera.get("camera_calibration")
        if not isinstance(calibration, dict):
            calibration = {}

        self.camera_info_label.setText(
            (
                f"อุปกรณ์: {device_index} | "
                f"ความละเอียด: {width}x{height} | "
                f"แก้การเอียง: "
                f"{calibration.get('card_roll_deg', 0):+.2f}°"
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
                'ไม่พบหมายเลขอุปกรณ์กล้อง'
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
                'ไม่สามารถเปิดกล้องที่เลือกได้'
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
                'ข้อผิดพลาดของระบบตรวจจับ',
                str(error)
            )

            return

        self.frame_count = 0

        self.detection_status_label.setText(
            'ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ'
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
                'ข้อผิดพลาดของกล้อง',
                'ไม่สามารถอ่านภาพจากกล้องได้'
            )

            return

        frame = adjust_camera_frame(
            frame,
            self.selected_camera.get("camera_calibration"),
        )

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
                
                shoulder_tilt = result["shoulder_tilt"]

                if shoulder_tilt is not None:   
                    self.shoulder_tilt_label.setText(
                        f"ความเอียงไหล่: {shoulder_tilt:+.2f}°"
                    )
                else:
                    self.shoulder_tilt_label.setText(
                        'ความเอียงไหล่: --'
                    )

                neck_result = result["neck_lateral_tilt"]

                if neck_result is not None:

                    neck_angle = neck_result["neck_tilt"]

                    self.neck_tilt_label.setText(
                    f"ความเอียงคอด้านข้าง: {neck_angle:+.2f}°"
                    )
    
                else:
                    self.neck_tilt_label.setText(
                    'ความเอียงคอด้านข้าง: --'
                )

                pose_detected = (
                    result["pose_points"] is not None
                )
                
                self.last_pose_points = result["pose_points"]

                face_detected = (
                    result["face_detected"]
                )

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
                    f"ท่าทาง: {pose_status} | "
                    f"ใบหน้า: {face_status}"
                )

            except Exception as error:

                self.stop_preview()

                QMessageBox.warning(
                    self,
                    'ข้อผิดพลาดของระบบตรวจจับ',
                    str(error)
                )

                return

        # -------------------------
        # Draw Pose Landmarks
        # -------------------------

        self.draw_pose_landmarks(
        frame,
        self.last_pose_points
        )
        
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

        fit_preview_label(
            self.preview_label,
            width,
            height,
            960,
            540,
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
            "ภาพตัวอย่างจากกล้องจะแสดงที่นี่"
        )
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setMaximumSize(960, 540)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )

        # -------------------------
        # Reset Detection Status
        # -------------------------

        self.frame_count = 0

        self.last_pose_points = None
        
        self.detection_status_label.setText(
            'ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ'
        )
        
        self.shoulder_tilt_label.setText(
            'ความเอียงไหล่: --'
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

        camera = self.selected_camera.copy() if self.selected_camera else {}
        self.back_requested.emit(camera)

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
    
    
    # =========================================================
    # Draw Pose Landmarks
    # =========================================================

    def draw_pose_landmarks(self, frame, points) -> None:

        if not points:
            return

        # เส้นเชื่อมจุดสำคัญ
        connections = [
            ("left_ear", "right_ear"),
            ("left_shoulder", "right_shoulder")
        ]

        # วาดเส้นเชื่อม
        for start_name, end_name in connections:

            start = points.get(start_name)
            end = points.get(end_name)

            if start is None or end is None:
                continue

            start_xy = (
                int(start["x"]),
                int(start["y"])
            )

            end_xy = (
                int(end["x"]),
                int(end["y"])
            )

            cv2.line(
                frame,
                start_xy,
                end_xy,
                (0, 255, 0),
                2
            )

        # วาดจุด Landmark
        for name, point in points.items():

            if point is None:
                continue

            x = int(point["x"])
            y = int(point["y"])

            cv2.circle(
                frame,
                (x, y),
                5,
                (0, 0, 255),
                -1
            )

