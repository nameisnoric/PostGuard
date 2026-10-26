"""Select a physical camera before camera preparation and corrected preview."""

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

        title = QLabel("ตั้งค่ากล้อง")
        title.setProperty("role", "title")
        description = QLabel(
            "ขั้นตอน 1 จาก 4  ·  สแกนอุปกรณ์และเลือกกล้องที่ต้องการใช้"
        )
        description.setProperty("role", "muted")
        layout.addWidget(title)
        layout.addWidget(description)

        card = QFrame()
        card.setProperty("card", True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(12)

        heading = QLabel("กล้องที่เชื่อมต่อกับอุปกรณ์นี้")
        heading.setProperty("role", "heading")
        self.status_label = QLabel(
            "เลือกสแกนกล้องเพื่อค้นหาเว็บแคมที่พร้อมใช้งาน"
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
        self.scan_button = QPushButton("สแกนกล้อง")
        self.continue_button = QPushButton("เตรียมและปรับแนวกล้อง")
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
        self.scan_button.setText("กำลังสแกน...")
        self.continue_button.setEnabled(False)
        self.camera_list.clear()
        self.camera_list.setEnabled(False)
        self.status_label.setText("กำลังตรวจสอบกล้องที่เชื่อมต่อกับอุปกรณ์นี้...")
        QApplication.processEvents()

        try:
            cameras = CameraService.scan_cameras()
        except (OSError, RuntimeError, ValueError) as error:
            self.detected_cameras = []
            self.status_label.setText('สแกนกล้องไม่สำเร็จ โปรดตรวจสอบสิทธิ์การใช้กล้อง')
            QMessageBox.warning(self, 'การสแกนกล้อง', str(error))
            return
        finally:
            self.scan_button.setEnabled(True)
            self.scan_button.setText("สแกนอีกครั้ง")

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
                f"{name}  ·  อุปกรณ์ {device_index}  ·  {width}×{height}"
            )

        count = len(cameras)
        self.status_label.setText(
            f"พบกล้องที่พร้อมใช้งาน {count} ตัว เลือกกล้องเพื่อเริ่มปรับแนวภาพ"
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
                'การตั้งค่ากล้อง',
                'โปรดสแกนและเลือกกล้องที่พร้อมใช้งานก่อน',
            )
            return
        self.camera_selected.emit(self.detected_cameras[row].copy())
