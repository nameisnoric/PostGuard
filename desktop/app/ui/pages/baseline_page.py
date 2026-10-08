
from PySide6.QtCore import Signal

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QMessageBox
)


class BaselinePage(QWidget):

    # ส่งข้อมูลกล้องกลับไป MainWindow
    back_requested = Signal(dict)

    def __init__(self):
        super().__init__()

        self.selected_camera = None

        # -------------------------
        # Main Layout
        # -------------------------

        layout = QVBoxLayout(self)

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "Personal Baseline"
        )

        self.description_label = QLabel(
            "Prepare your sitting posture "
            "before starting calibration."
        )

        # -------------------------
        # Camera Information
        # -------------------------

        camera_group = QGroupBox(
            "Selected Camera"
        )

        camera_layout = QVBoxLayout(
            camera_group
        )

        self.camera_name_label = QLabel(
            "Camera: Not selected"
        )

        self.device_label = QLabel(
            "Device: -"
        )
        
        self.camera_id_label = QLabel(
            "Camera ID: -"
        )

        self.resolution_label = QLabel(
            "Resolution: -"
        )

        camera_layout.addWidget(
            self.camera_name_label
        )

        camera_layout.addWidget(
            self.device_label
        )
        
        camera_layout.addWidget(
            self.camera_id_label
        )

        camera_layout.addWidget(
            self.resolution_label
        )

        # -------------------------
        # Calibration Information
        # -------------------------

        calibration_group = QGroupBox(
            "Calibration"
        )

        calibration_layout = QVBoxLayout(
            calibration_group
        )

        self.instruction_label = QLabel(
            "1. Sit in your normal working position.\n"
            "2. Keep your head and shoulders relaxed.\n"
            "3. Face the camera directly.\n"
            "4. Keep your posture steady during calibration."
        )

        self.status_label = QLabel(
            "Status: Waiting for detection module"
        )

        calibration_layout.addWidget(
            self.instruction_label
        )

        calibration_layout.addWidget(
            self.status_label
        )

        # -------------------------
        # Buttons
        # -------------------------

        button_layout = QHBoxLayout()

        self.back_button = QPushButton(
            "Back to Camera Preview"
        )

        self.calibrate_button = QPushButton(
            "Start Calibration"
        )

        # ยังไม่เปิดจนกว่าจะเชื่อม Detection
        self.calibrate_button.setEnabled(False)

        button_layout.addWidget(
            self.back_button
        )

        button_layout.addWidget(
            self.calibrate_button
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
            camera_group
        )

        layout.addWidget(
            calibration_group
        )

        layout.addStretch()

        layout.addLayout(
            button_layout
        )

        # -------------------------
        # Events
        # -------------------------

        self.back_button.clicked.connect(
            self.handle_back
        )

    # =========================================================
    # Receive Camera
    # =========================================================

    def set_camera(
        self,
        camera: dict
    ) -> None:

        self.selected_camera = camera.copy()
        
        camera_id = camera.get("camera_id")

        self.camera_id_label.setText(
            f"Camera ID: {camera_id}"
        )

        camera_name = camera.get(
            "camera_name",
            "Unknown Camera"
        )

        device_index = camera.get(
            "device_index"
        )

        width = camera.get(
            "resolution_width"
        )

        height = camera.get(
            "resolution_height"
        )

        self.camera_name_label.setText(
            f"Camera: {camera_name}"
        )

        self.device_label.setText(
            f"Device: {device_index}"
        )

        self.resolution_label.setText(
            f"Resolution: {width}x{height}"
        )

        self.status_label.setText(
            "Status: Ready for detection integration"
        )

        print(
            "BASELINE CAMERA:",
            self.selected_camera
        )

    # =========================================================
    # Back to Preview
    # =========================================================

    def handle_back(self) -> None:

        if self.selected_camera is None:
            QMessageBox.warning(
                self,
                "PostGuard",
                "No camera selected."
            )
            return

        self.back_requested.emit(
            self.selected_camera
        )
