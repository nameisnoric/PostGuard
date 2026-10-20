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

from app.services.api_client import APIClient
from app.ui.theme import APP_QSS, set_centered_window


class RegisterWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "PostGuard - Register"
        )

        set_centered_window(self, 900, 680, 720, 600)
        self.setObjectName("authWindow")
        self.setStyleSheet(APP_QSS)

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "Create PostGuard Account"
        )
        self.title_label.setProperty("role", "title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Create an account with your KU email")
        subtitle.setProperty("role", "muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # -------------------------
        # Full Name
        # -------------------------

        self.full_name_input = QLineEdit()

        self.full_name_input.setPlaceholderText(
            "Full Name"
        )

        # -------------------------
        # Username
        # -------------------------

        self.username_input = QLineEdit()

        self.username_input.setPlaceholderText(
            "Username"
        )

        # -------------------------
        # Email
        # -------------------------

        self.email_input = QLineEdit()

        self.email_input.setPlaceholderText(
            "KU Email"
        )

        # -------------------------
        # Password
        # -------------------------

        self.password_input = QLineEdit()

        self.password_input.setPlaceholderText(
            "Password"
        )

        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText(
            "Confirm Password"
        )
        self.confirm_password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        # -------------------------
        # Buttons
        # -------------------------

        self.register_button = QPushButton(
            "Send OTP"
        )
        self.register_button.setProperty("variant", "primary")

        self.back_button = QPushButton(
            "Back to Login"
        )

        # -------------------------
        # Layout
        # -------------------------

        outer = QHBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.addStretch()
        card = QFrame()
        card.setProperty("card", True)
        card.setMaximumWidth(500)
        card.setMinimumWidth(420)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(42, 36, 42, 36)
        layout.setSpacing(11)
        layout.addWidget(self.title_label)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        for label, field in (
            ("Full name", self.full_name_input),
            ("Username", self.username_input),
            ("KU Email", self.email_input),
            ("Password", self.password_input),
            ("Confirm password", self.confirm_password_input),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(field)
        layout.addSpacing(6)
        layout.addWidget(self.register_button)
        layout.addWidget(self.back_button)
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

        # -------------------------
        # Events
        # -------------------------

        self.register_button.clicked.connect(
            self.handle_register
        )

        self.back_button.clicked.connect(
            self.back_to_login
        )

    def handle_register(self):
        full_name = (
            self.full_name_input
            .text()
            .strip()
        )

        username = (
            self.username_input
            .text()
            .strip()
        )

        email = (
            self.email_input
            .text()
            .strip()
        )

        password = (
            self.password_input
            .text()
        )

        confirm_password = (
            self.confirm_password_input
            .text()
        )

        # -------------------------
        # Basic validation
        # -------------------------

        if (
            not full_name
            or not username
            or not email
            or not password
            or not confirm_password
        ):
            self.show_error(
                "Please fill in all fields."
            )
            return

        if password != confirm_password:
            self.show_error(
                "Password and confirmation do not match."
            )
            self.confirm_password_input.clear()
            self.confirm_password_input.setFocus()
            return

        try:
            response = (
                APIClient.request_register_otp(
                    email=email,
                    username=username,
                    password=password,
                    full_name=full_name
                )
            )

        except requests.RequestException:
            self.show_error(
                "Cannot connect to the PostGuard server."
            )
            return

        if response.status_code != 200:
            try:
                error_data = response.json()

                message = error_data.get(
                    "detail",
                    "Unable to send OTP."
                )

            except ValueError:
                message = "Unable to send OTP."

            self.show_error(
                str(message)
            )

            return

        from app.ui.windows.otp_window import OTPWindow

        self.otp_window = OTPWindow(email)

        self.otp_window.show()

        self.close()

    def back_to_login(self):
        from app.ui.windows.login_window import (
            LoginWindow
        )

        self.login_window = LoginWindow()

        self.login_window.show()

        self.close()

    def show_error(
        self,
        message: str
    ):
        QMessageBox.warning(
            self,
            "PostGuard",
            message
        )
