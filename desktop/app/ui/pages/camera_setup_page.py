"""Select a physical camera before preview and camera preparation."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.camera_service import CameraService


class CameraSetupPage(QWidget):
    camera_selected = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setProperty("page", True)
        self.detected_cameras = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(140, 36, 140, 48)
        layout.setSpacing(12)

        title = QLabel("Set up your camera")
        title.setProperty("role", "title")
        description = QLabel(
            "Step 1 of 4  ·  Scan this device and select the camera you want to use."
        )
        description.setProperty("role", "muted")
        layout.addWidget(title)
        layout.addWidget(description)

        card = QFrame()
        card.setProperty("card", True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(12)

        heading = QLabel("Cameras connected to this device")
        heading.setProperty("role", "heading")
        self.status_label = QLabel(
            "Select Scan Cameras to look for an available webcam."
        )
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        card_layout.addWidget(heading)
        card_layout.addWidget(self.status_label)

        self.camera_list = QListWidget()
        self.camera_list.setMinimumHeight(220)
        self.camera_list.setEnabled(False)
        card_layout.addWidget(self.camera_list)

        actions = QHBoxLayout()
        self.scan_button = QPushButton("Scan Cameras")
        self.continue_button = QPushButton("Check Camera")
        self.continue_button.setProperty("variant", "primary")
        self.continue_button.setEnabled(False)
        actions.addWidget(self.scan_button)
        actions.addStretch()
        actions.addWidget(self.continue_button)
        card_layout.addLayout(actions)
        layout.addWidget(card)

        privacy = QLabel(
            "Camera access stays on this device. Scanning checks which camera can "
            "provide a frame; it does not save or upload an image."
        )
        privacy.setProperty("role", "muted")
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        layout.addStretch()

        self.scan_button.clicked.connect(self.scan_webcams)
        self.camera_list.itemSelectionChanged.connect(self.handle_selection)
        self.camera_list.itemDoubleClicked.connect(self.handle_continue)
        self.continue_button.clicked.connect(self.handle_continue)

    def scan_webcams(self):
        self.scan_button.setEnabled(False)
        self.scan_button.setText("Scanning...")
        self.continue_button.setEnabled(False)
        self.camera_list.clear()
        self.camera_list.setEnabled(False)
        self.status_label.setText("Checking cameras connected to this device...")
        QApplication.processEvents()

        try:
            cameras = CameraService.scan_cameras()
        except (OSError, RuntimeError, ValueError) as error:
            self.detected_cameras = []
            self.status_label.setText("Camera scan failed. Check camera permission.")
            QMessageBox.warning(self, "Camera Scan", str(error))
            return
        finally:
            self.scan_button.setEnabled(True)
            self.scan_button.setText("Scan Again")

        self.detected_cameras = cameras
        if not cameras:
            self.status_label.setText(
                "No available camera was found. Check Windows camera permission "
                "and make sure another application is not using the camera."
            )
            return

        for camera in cameras:
            name = camera.get("camera_name", "Unknown Camera")
            device_index = camera.get("device_index", "--")
            width = camera.get("resolution_width", "--")
            height = camera.get("resolution_height", "--")
            self.camera_list.addItem(
                f"{name}  ·  Device {device_index}  ·  {width}×{height}"
            )

        count = len(cameras)
        noun = "camera" if count == 1 else "cameras"
        self.status_label.setText(
            f"Found {count} available {noun}. Select one to check its preview."
        )
        self.camera_list.setEnabled(True)
        self.camera_list.setCurrentRow(0)

    def handle_selection(self):
        row = self.camera_list.currentRow()
        self.continue_button.setEnabled(0 <= row < len(self.detected_cameras))

    def handle_continue(self, *_args):
        row = self.camera_list.currentRow()
        if not 0 <= row < len(self.detected_cameras):
            QMessageBox.warning(
                self,
                "Camera Setup",
                "Scan and select an available camera first.",
            )
            return
        self.camera_selected.emit(self.detected_cameras[row].copy())
