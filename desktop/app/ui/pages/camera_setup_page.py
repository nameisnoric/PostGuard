from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QMessageBox
)
from PySide6.QtCore import Signal

import requests

from app.services.api_client import APIClient
from app.services.camera_service import CameraService

class CameraSetupPage(QWidget):
    camera_selected = Signal(dict)

    def __init__(self):
        super().__init__()

        # เก็บข้อมูล camera ที่ได้จาก Backend
        self.saved_cameras = []
        self.detected_cameras = []
        
        # -------------------------
        # Layout
        # -------------------------

        layout = QVBoxLayout(self)

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "Camera Setup"
        )

        self.description_label = QLabel(
            "Select a camera for PostGuard monitoring."
        )

        # -------------------------
        # Camera List
        # -------------------------

        self.camera_list = QListWidget()

        # -------------------------
        # Buttons
        # -------------------------

        self.refresh_button = QPushButton(
            "Refresh Cameras"
        )

        self.continue_button = QPushButton(
            "Continue"
        )
        
        self.scan_button = QPushButton(
            "Scan Webcam"
        )

        # ยังไม่ให้กด Continue
        # จนกว่าจะเลือก camera
        self.continue_button.setEnabled(False)

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
            self.camera_list
        )

        layout.addWidget(
            self.scan_button
        )
        
        layout.addWidget(
            self.refresh_button
        )

        layout.addWidget(
            self.continue_button
        )

        # -------------------------
        # Events
        # -------------------------

        self.refresh_button.clicked.connect(
            self.load_cameras
        )

        self.camera_list.itemSelectionChanged.connect(
            self.handle_selection
        )

        self.continue_button.clicked.connect(
            self.handle_continue
        )
        
        self.scan_button.clicked.connect(
            self.scan_webcams
        )

        # # โหลด camera ครั้งแรก
        # self.load_cameras()

    def load_cameras(self):
        try:
            response = APIClient.get_cameras()

        except requests.RequestException:
            QMessageBox.critical(
                self,
                "PostGuard",
                "Cannot connect to the PostGuard server."
            )
            return

        print(
            "CAMERAS STATUS:",
            response.status_code
        )

        print(
            "CAMERAS RESPONSE:",
            response.text
        )

        if not response.ok:
            QMessageBox.warning(
                self,
                "PostGuard",
                "Unable to load cameras."
            )
            return

        self.saved_cameras = response.json()

        self.camera_list.clear()

        if not self.saved_cameras:
            self.camera_list.addItem(
                "No cameras found."
            )

            self.continue_button.setEnabled(
                False
            )

            return

        for camera in self.saved_cameras:
            camera_name = camera.get(
                "camera_name",
                "Unknown Camera"
            )

            width = camera.get(
                "resolution_width"
            )

            height = camera.get(
                "resolution_height"
            )

            if width and height:
                display_text = (
                    f"{camera_name} "
                    f"({width}x{height})"
                )

            else:
                display_text = camera_name

            self.camera_list.addItem(
                display_text
            )
            
            self.camera_list.setCurrentRow(0)
            self.continue_button.setEnabled(True)

    def handle_selection(self):

        selected_row = self.camera_list.currentRow()

        print(
            "SELECTED ROW:",
            selected_row
        )

        if self.current_source == "detected":
            camera_count = len(
                self.detected_cameras
            )

        elif self.current_source == "saved":
            camera_count = len(
                self.saved_cameras
            )

        else:
            camera_count = 0

        print(
            "CURRENT SOURCE:",
            self.current_source
        )

        print(
            "CAMERA COUNT:",
            camera_count
        )

        if 0 <= selected_row < camera_count:
            self.continue_button.setEnabled(True)

        else:
            self.continue_button.setEnabled(False)

    def handle_continue(self):

        selected_row = self.camera_list.currentRow()

        print(
            "CONTINUE SELECTED ROW:",
            selected_row
        )

        print(
            "CURRENT SOURCE:",
            self.current_source
        )

    # --------------------------------
    # ยังไม่ได้เลือก Camera
    # --------------------------------

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "PostGuard",
                "Please select a camera."
            )
            return

    # --------------------------------
    # Physical Webcam จาก OpenCV
    # --------------------------------

        if self.current_source == "detected":

            if selected_row >= len(
                self.detected_cameras
            ):
                return

            selected_camera = (
                self.detected_cameras[
                    selected_row
                ]
            )

            print(
                "SELECTED WEBCAM:",
                selected_camera
            )

            self.camera_selected.emit(
                selected_camera
            )
    # --------------------------------
    # Camera ที่บันทึกใน Database
    # --------------------------------

        elif self.current_source == "saved":

            if selected_row >= len(
                self.saved_cameras
            ):
                return

            selected_camera = (
                self.saved_cameras[
                    selected_row
                ]
            )

            print(
                "SELECTED SAVED CAMERA:",
                selected_camera
            )

            camera_name = selected_camera.get(
                "camera_name",
                "Unknown Camera"
            )

            QMessageBox.information(
                self,
                "PostGuard",
                (
                    "Saved camera selected.\n\n"
                    f"Camera: {camera_name}"
                )
            )

    # --------------------------------
    # ไม่มี Source
    # --------------------------------

        else:

            QMessageBox.warning(
                self,
                "PostGuard",
                "Please scan or load cameras first."
            )
        
    def scan_webcams(self):

        self.scan_button.setEnabled(False)

        self.scan_button.setText(
            "Scanning..."
        )

        try:
            cameras = CameraService.scan_cameras()

        finally:
            self.scan_button.setEnabled(True)

            self.scan_button.setText(
                "Scan Webcams"
            )

        self.detected_cameras = cameras
        self.current_source = "detected"

        self.camera_list.clear()

        if not cameras:
            self.camera_list.addItem(
                "No webcam detected."
            )

            self.continue_button.setEnabled(
                False
            )

            return

        for camera in self.detected_cameras:

            camera_name = camera.get(
                "camera_name",
                "Unknown Camera"
            )

            width = camera.get(
                "resolution_width"
            )

            height = camera.get(
                "resolution_height"
            )

            device_index = camera.get(
                "device_index"
            )

            display_text = (
                f"{camera_name} "
                f"[Device {device_index}] "
                f"({width}x{height})"
            )

            self.camera_list.addItem(
                display_text
            )
            self.camera_list.setCurrentRow(0)
            self.continue_button.setEnabled(True)