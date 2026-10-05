from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget
)

from app.core.token_store import TokenStore
from app.ui.pages.dashboard_page import DashboardPage


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

        self.monitor_placeholder = QLabel(
            "Monitoring Page"
        )

        self.history_placeholder = QLabel(
            "History Page"
        )

        self.pages.addWidget(
            self.dashboard_page
        )

        self.pages.addWidget(
            self.monitor_placeholder
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

        # เปิด Dashboard เป็นหน้าแรก
        self.pages.setCurrentWidget(
            self.dashboard_page
        )

    def show_dashboard(self):
        self.pages.setCurrentWidget(
            self.dashboard_page
        )

    def show_monitor(self):
        self.pages.setCurrentWidget(
            self.monitor_placeholder
        )

    def show_history(self):
        self.pages.setCurrentWidget(
            self.history_placeholder
        )

    def logout(self):
        TokenStore.clear_token()
        self.hide()
        
        from app.ui.login_window import LoginWindow
        
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()