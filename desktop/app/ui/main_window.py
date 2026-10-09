from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QMessageBox
)

from app.core.token_store import TokenStore
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.camera_setup_page import CameraSetupPage
from app.ui.pages.camera_preview_page import CameraPreviewPage
from app.ui.pages.baseline_page import BaselinePage
from app.ui.pages.monitoring_page import MonitoringPage
from app.services.api_client import APIClient

import requests

class MainWindow(QMainWindow):

    def __init__(self, user_data: dict):
        super().__init__()

        self.user_data = user_data

        self.setWindowTitle("PostGuard")
        self.resize(1200, 750)

        # -------------------------
        # Central Widget
        # -------------------------

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(
            central_widget
        )

        # -------------------------
        # Sidebar
        # -------------------------

        sidebar = QWidget()

        sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(
            sidebar
        )

        app_title = QLabel("PostGuard")

        self.dashboard_button = QPushButton(
            "Dashboard"
        )

        self.monitor_button = QPushButton(
            "Monitor"
        )

        self.history_button = QPushButton(
            "History"
        )

        self.logout_button = QPushButton(
            "Logout"
        )

        sidebar_layout.addWidget(
            app_title
        )

        sidebar_layout.addWidget(
            self.dashboard_button
        )

        sidebar_layout.addWidget(
            self.monitor_button
        )

        sidebar_layout.addWidget(
            self.history_button
        )

        sidebar_layout.addStretch()

        sidebar_layout.addWidget(
            self.logout_button
        )

        # -------------------------
        # Pages
        # -------------------------

        self.pages = QStackedWidget()

        self.dashboard_page = DashboardPage(
            self.user_data
        )

        self.camera_setup_page = (
            CameraSetupPage()
        )
        
        self.camera_preview_page = (
            CameraPreviewPage()
        )
        
        self.baseline_page = (
            BaselinePage()
        )
        
        self.monitoring_page = (
            MonitoringPage()
        )

        self.history_placeholder = QLabel(
            "History Page"
        )

        self.pages.addWidget(
            self.dashboard_page
        )

        self.pages.addWidget(
            self.camera_setup_page
        )
        
        self.pages.addWidget(
            self.camera_preview_page
        )
        
        self.pages.addWidget(
            self.baseline_page
        )
        
        self.pages.addWidget(
            self.monitoring_page
        )

        self.pages.addWidget(
            self.history_placeholder
        )

        # -------------------------
        # Main Layout
        # -------------------------

        main_layout.addWidget(
            sidebar
        )

        main_layout.addWidget(
            self.pages
        )

        # -------------------------
        # Button Events
        # -------------------------

        self.dashboard_button.clicked.connect(
            self.show_dashboard
        )

        self.monitor_button.clicked.connect(
            self.show_monitor
        )

        self.history_button.clicked.connect(
            self.show_history
        )

        self.logout_button.clicked.connect(
            self.logout
        )
        
        # -------------------------
        # Camera Page Events
        # ใส่ 3 ตัวตรงนี้
        # -------------------------

        self.camera_setup_page.camera_selected.connect(
            self.show_camera_preview
        )

        self.camera_preview_page.back_requested.connect(
            self.show_camera_setup
        )

        self.camera_preview_page.continue_requested.connect(
            self.handle_preview_continue
        )
        
        self.baseline_page.back_requested.connect(
            self.show_camera_preview
        )
        
        self.baseline_page.monitoring_requested.connect(
            self.show_monitoring_page
        )
        
        self.monitoring_page.stop_requested.connect(
            self.show_dashboard
        )

        # เปิด Dashboard เป็นหน้าแรก
        self.pages.setCurrentWidget(
            self.dashboard_page
        )

    def show_dashboard(self):
        self.camera_preview_page.stop_preview()
        
        self.pages.setCurrentWidget(
            self.dashboard_page
        )

    def show_monitor(self):
        self.camera_preview_page.stop_preview()
        
        self.pages.setCurrentWidget(
            self.camera_setup_page
        )

    def show_history(self):
        self.camera_preview_page.stop_preview()
        
        self.pages.setCurrentWidget(
            self.history_placeholder
        )

    def logout(self):
        self.camera_preview_page.stop_preview()
        self.monitoring_page.stop_monitoring()
        
        TokenStore.clear_token()
        self.hide()
        
        from app.ui.login_window import LoginWindow
        
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()
        
    def show_camera_preview(
        self,
        camera: dict
    ):
        self.camera_preview_page.start_preview(
            camera
        )

        self.pages.setCurrentWidget(
            self.camera_preview_page
        )


    def show_camera_setup(self):

        self.camera_preview_page.stop_preview()

        self.pages.setCurrentWidget(
            self.camera_setup_page
        )

    def handle_preview_continue(
        self,
        camera: dict
    ) -> None:

        try:
            # 1. รับข้อมูลกล้องจาก OpenCV
            device_index = camera.get("device_index")

            if device_index is None:
                raise ValueError(
                    "Camera device index is missing."
                )

            # รหัสชั่วคราวสำหรับการพัฒนา
            device_id = f"opencv-index:{device_index}"

            # 2. ตรวจสอบกล้องที่เคยบันทึกไว้
            response = APIClient.get_cameras()

            if not response.ok:
                raise RuntimeError(
                    f"Cannot load cameras: HTTP "
                    f"{response.status_code}"
                )

            saved_cameras = response.json()

            if not isinstance(saved_cameras, list):
                raise ValueError(
                    "Invalid camera list from server."
                )

            # 3. ค้นหากล้องที่มี device_id ตรงกัน
            registered_camera = next(
                (
                    item
                    for item in saved_cameras
                    if item.get("device_id") == device_id
                ),
                None
            )

            # 4. ถ้าไม่พบ ให้ลงทะเบียนกล้องใหม่
            if registered_camera is None:

                print("REGISTERING CAMERA:", device_id)

                response = APIClient.create_camera(
                    device_id=device_id,
                    camera_name=camera.get(
                        "camera_name",
                        f"Camera {device_index}"
                    ),
                    resolution_width=camera[
                        "resolution_width"
                    ],
                    resolution_height=camera[
                        "resolution_height"
                    ]
                )

                if not response.ok:
                    raise RuntimeError(
                        f"Camera registration failed: "
                        f"HTTP {response.status_code}"
                    )

                registered_camera = response.json()

                print("NEW CAMERA REGISTERED")

            else:
                print("USING EXISTING CAMERA")

            # 5. รับ camera_id จาก PostgreSQL
            camera_id = registered_camera.get(
                "camera_id"
            )

            if not isinstance(camera_id, int):
                raise ValueError(
                    "Invalid camera_id from server."
                )

            # 6. รวมข้อมูลกล้องกับ camera_id
            camera_data = camera.copy()

            camera_data["camera_id"] = camera_id
            camera_data["device_id"] = device_id

            print("CAMERA ID:", camera_id)
            print("BASELINE CAMERA:", camera_data)

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
            TypeError
        ) as error:

            QMessageBox.warning(
                self,
                "Camera Registration Error",
                str(error)
            )

            # เปิด Preview อีกครั้งเพื่อให้ลองใหม่ได้
            self.camera_preview_page.start_preview(
                camera
            )

            return

        # 7. ส่งข้อมูลกล้องให้ BaselinePage
        self.baseline_page.set_camera(
            camera_data
        )

        # 8. เปิดหน้า Personal Baseline
        self.pages.setCurrentWidget(
            self.baseline_page
        )

        
    def show_monitoring_page(
        self,
        camera: dict,
        baseline_id: int
    ) -> None:

        # เปลี่ยนจากหน้า Baseline ไป Monitoring
        self.pages.setCurrentWidget(
            self.monitoring_page
        )

        # เปิดกล้องพร้อมข้อมูล Baseline ID
        started = self.monitoring_page.start_monitoring(
            camera,
            baseline_id
        )

        # ถ้าเปิดกล้องไม่สำเร็จ
        # ให้กลับไปเลือกกล้องใหม่
        if not started:
            self.pages.setCurrentWidget(
                self.camera_setup_page
            )
