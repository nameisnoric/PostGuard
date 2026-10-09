import requests

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QMessageBox,
)

from app.core.token_store import TokenStore

from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.camera_setup_page import CameraSetupPage
from app.ui.pages.camera_preview_page import CameraPreviewPage
from app.ui.pages.baseline_page import BaselinePage
from app.ui.pages.monitoring_page import MonitoringPage
from app.ui.pages.session_summary_page import SessionSummaryPage

from app.services.api_client import APIClient

class MainWindow(QMainWindow):

    def __init__(self, user_data: dict):
        super().__init__()

        self.user_data = user_data

        self.setWindowTitle("PostGuard")
        self.resize(1200, 750)

        # ========================================
        # 1. Central Widget
        # ========================================

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(
            central_widget
        )

        # ========================================
        # 2. Sidebar
        # ========================================

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

        # ========================================
        # 3. Create Pages
        # ========================================

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

        # NEW: Session Summary
        self.session_summary_page = (
            SessionSummaryPage()
        )

        self.history_placeholder = QLabel(
            "History Page"
        )

        # ========================================
        # 4. Register Pages
        # ========================================

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

        # NEW: Register Session Summary
        self.pages.addWidget(
            self.session_summary_page
        )

        self.pages.addWidget(
            self.history_placeholder
        )

        # ========================================
        # 5. Main Layout
        # ========================================

        main_layout.addWidget(
            sidebar
        )

        main_layout.addWidget(
            self.pages
        )

        # ========================================
        # 6. Sidebar Events
        # ========================================

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

        # ========================================
        # 7. Camera Page Events
        # ========================================

        # Camera Setup -> Camera Preview
        self.camera_setup_page.camera_selected.connect(
            self.show_camera_preview
        )

        # Camera Preview -> Camera Setup
        self.camera_preview_page.back_requested.connect(
            self.show_camera_setup
        )

        # Camera Preview -> Personal Baseline
        self.camera_preview_page.continue_requested.connect(
            self.handle_preview_continue
        )

        # Personal Baseline -> Camera Preview
        self.baseline_page.back_requested.connect(
            self.show_camera_preview
        )

        # ========================================
        # 8. Monitoring Events
        # ========================================

        # Personal Baseline -> Monitoring
        self.baseline_page.monitoring_requested.connect(
            self.show_monitoring_page
        )

        # Monitoring -> Session Summary
        self.monitoring_page.stop_requested.connect(
            self.show_session_summary
        )

        # Session Summary -> Dashboard
        self.session_summary_page.back_requested.connect(
            self.show_dashboard
        )

        # ========================================
        # 9. Default Page
        # ========================================

        self.pages.setCurrentWidget(
            self.dashboard_page
        )

    # ============================================
    # Dashboard
    # ============================================

    def show_dashboard(self):

        self.camera_preview_page.stop_preview()

        self.pages.setCurrentWidget(
            self.dashboard_page
        )

    # ============================================
    # Monitor Menu
    # ============================================

    def show_monitor(self):

        self.camera_preview_page.stop_preview()

        self.pages.setCurrentWidget(
            self.camera_setup_page
        )

    # ============================================
    # History
    # ============================================

    def show_history(self):

        self.camera_preview_page.stop_preview()

        self.pages.setCurrentWidget(
            self.history_placeholder
        )

    # ============================================
    # Logout
    # ============================================

    def logout(self):

        # Stop Camera Preview
        self.camera_preview_page.stop_preview()

        # Stop Monitoring
        self.monitoring_page.stop_monitoring()

        # Clear Authentication Token
        TokenStore.clear_token()

        self.hide()

        from app.ui.login_window import LoginWindow

        self.login_window = LoginWindow()
        self.login_window.show()

        self.close()

    # ============================================
    # Camera Preview
    # ============================================

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

    # ============================================
    # Camera Setup
    # ============================================

    def show_camera_setup(self):

        self.camera_preview_page.stop_preview()

        self.pages.setCurrentWidget(
            self.camera_setup_page
        )

    # ============================================
    # Camera Registration
    # ============================================

    def handle_preview_continue(
        self,
        camera: dict
    ) -> None:

        try:

            # 1. Get Camera Device Index
            device_index = camera.get(
                "device_index"
            )

            if device_index is None:
                raise ValueError(
                    "Camera device index is missing."
                )

            # Temporary Device Identifier
            device_id = (
                f"opencv-index:{device_index}"
            )

            # 2. Load Registered Cameras
            response = APIClient.get_cameras()

            if not response.ok:
                raise RuntimeError(
                    f"Cannot load cameras: "
                    f"HTTP {response.status_code}"
                )

            saved_cameras = response.json()

            if not isinstance(saved_cameras, list):
                raise ValueError(
                    "Invalid camera list from server."
                )

            # 3. Find Existing Camera
            registered_camera = next(
                (
                    item
                    for item in saved_cameras
                    if item.get("device_id") == device_id
                ),
                None
            )

            # 4. Register New Camera
            if registered_camera is None:

                print(
                    "REGISTERING CAMERA:",
                    device_id
                )

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

            # 5. Get Camera ID from Database
            camera_id = registered_camera.get(
                "camera_id"
            )

            if (
                not isinstance(camera_id, int)
                or isinstance(camera_id, bool)
                or camera_id <= 0
            ):
                raise ValueError(
                    "Invalid camera_id from server."
                )

            # 6. Prepare Camera Data
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

            # Reopen Preview for Retry
            self.camera_preview_page.start_preview(
                camera
            )

            return

        # 7. Send Camera Data to Baseline
        self.baseline_page.set_camera(
            camera_data
        )

        # 8. Open Personal Baseline Page
        self.pages.setCurrentWidget(
            self.baseline_page
        )

    # ============================================
    # Real-time Monitoring
    # ============================================

    def show_monitoring_page(
        self,
        camera: dict,
        baseline_id: int
    ) -> None:

        # Switch to Monitoring Page
        self.pages.setCurrentWidget(
            self.monitoring_page
        )

        # Start Monitoring with Camera
        # and Saved Personal Baseline
        started = self.monitoring_page.start_monitoring(
            camera,
            baseline_id
        )

        # If Monitoring Cannot Start
        if not started:

            self.pages.setCurrentWidget(
                self.camera_setup_page
            )

    # ============================================
    # Session Summary
    # ============================================

    def show_session_summary(
        self,
        summary: dict
    ) -> None:

        # Display Session Information
        self.session_summary_page.set_summary(
            summary
        )

        # Switch Monitoring -> Session Summary
        self.pages.setCurrentWidget(
            self.session_summary_page
        )
