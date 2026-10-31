from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
    QFrame,
    QHBoxLayout,
)

import requests

from app.core.token_store import TokenStore
from app.services.api_client import APIClient
from app.ui.windows.main_window import MainWindow
from app.ui.theme import APP_QSS, set_centered_window


class LoginWindow(QWidget):

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("PostGuard - เข้าสู่ระบบ")
        set_centered_window(self, 900, 580, 720, 500)
        self.setObjectName("authWindow")
        self.setStyleSheet(APP_QSS)

        self.title_label = QLabel("PostGuard")
        self.title_label.setProperty("role", "title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("เข้าสู่ระบบเพื่อเริ่มตรวจติดตามท่าทาง")
        subtitle.setProperty("role", "muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("อีเมล KU")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("รหัสผ่าน")
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.login_button = QPushButton("เข้าสู่ระบบ")
        self.login_button.setProperty("variant", "primary")
        self.register_button = QPushButton("สร้างบัญชี")
        self.forgot_password_button = QPushButton("ลืมรหัสผ่าน?")
        self.forgot_password_button.clicked.connect(self.open_password_reset)
        self.login_button.clicked.connect(
            self.handle_login
        )
        self.register_button.clicked.connect(
            self.open_register
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.addStretch()
        card = QFrame()
        card.setProperty("card", True)
        card.setMaximumWidth(460)
        card.setMinimumWidth(400)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(42, 40, 42, 40)
        layout.setSpacing(14)
        layout.addWidget(self.title_label)
        layout.addWidget(subtitle)
        layout.addSpacing(12)
        layout.addWidget(QLabel("อีเมล KU"))
        layout.addWidget(self.email_input)
        layout.addWidget(QLabel("รหัสผ่าน"))
        layout.addWidget(self.password_input)
        layout.addWidget(self.forgot_password_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.login_button)
        layout.addWidget(self.register_button)
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

    def handle_login(self) -> None:
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            self.show_error(
                "Please enter your email and password."
            )
            return

        try:
            response = APIClient.login(
                email,
                password
            )

        except requests.RequestException:
            self.show_error(
                "Cannot connect to the PostGuard server."
            )
            return

        if response.status_code != 200:
            self.show_error(
                "Invalid email or password."
            )
            return

        login_data = response.json()

        access_token = login_data.get(
            "access_token"
        )
        refresh_token = login_data.get("refresh_token")

        if not access_token or not refresh_token:
            self.show_error(
                "Authentication tokens were not returned by the server."
            )
            return

        TokenStore.set_session(
            access_token,
            refresh_token,
            int(login_data.get("expires_in", 30 * 60)),
        )

        try:
            me_response = APIClient.get_current_user()

        except requests.RequestException:
            TokenStore.clear_token()

            self.show_error(
                "Unable to load user information."
            )
            return

        if me_response.status_code != 200:
            TokenStore.clear_token()

            self.show_error(
                "Unable to verify the current user."
            )
            return

        user_data = me_response.json()

        if user_data.get("account_status") == "PENDING_DELETION":
            from app.ui.windows.account_recovery_window import AccountRecoveryWindow

            self.recovery_window = AccountRecoveryWindow(user_data)
            self.recovery_window.show()
            self.close()
            return

        self.main_window = MainWindow(
            user_data
        )

        self.main_window.show()
        self.close()
        self.main_window.check_previous_sessions()
        self.main_window.dashboard_page.refresh()

    def open_password_reset(self):
        from app.ui.dialogs.password_reset_dialog import PasswordResetDialog

        dialog = PasswordResetDialog(self, email=self.email_input.text().strip())
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.email_input.setText(dialog.email)
            self.password_input.clear()
            self.password_input.setFocus()

    def open_register(self):
        from app.ui.windows.register_window import RegisterWindow
        self.register_window = RegisterWindow()

        self.register_window.show()

        self.close()
    
    def show_error(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "PostGuard",
            message
        )
