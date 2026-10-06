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
    ):
        print(
            "READY FOR PERSONAL BASELINE:",
            camera
        )

        QMessageBox.information(
            self,
            "PostGuard",
            "Camera check completed. Personal Baseline is next."
        )