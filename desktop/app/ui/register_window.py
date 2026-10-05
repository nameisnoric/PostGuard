from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox
)

import requests

from app.services.api_client import APIClient


class RegisterWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "PostGuard - Register"
        )

        self.resize(
            400,
            500
        )

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "Create PostGuard Account"
        )

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

        # -------------------------
        # Buttons
        # -------------------------

        self.register_button = QPushButton(
            "Send OTP"
        )

        self.back_button = QPushButton(
            "Back to Login"
        )

        # -------------------------
        # Layout
        # -------------------------

        layout = QVBoxLayout(self)

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.full_name_input
        )

        layout.addWidget(
            self.username_input
        )

        layout.addWidget(
            self.email_input
        )

        layout.addWidget(
            self.password_input
        )

        layout.addWidget(
            self.register_button
        )

        layout.addWidget(
            self.back_button
        )

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

        # -------------------------
        # Basic validation
        # -------------------------

        if (
            not full_name
            or not username
            or not email
            or not password
        ):
            self.show_error(
                "Please fill in all fields."
            )
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

        print(
            "REGISTER OTP STATUS:",
            response.status_code
        )

        print(
            "REGISTER OTP RESPONSE:",
            response.text
        )

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

        QMessageBox.information(
            self,
            "PostGuard",
            "OTP has been sent to your email."
        )
        
        from app.ui.otp_window import OTPWindow

        self.otp_window = OTPWindow(email)

        self.otp_window.show()

        self.close()

    def back_to_login(self):
        from app.ui.login_window import (
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