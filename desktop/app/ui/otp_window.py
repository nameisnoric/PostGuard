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


class OTPWindow(QWidget):

    def __init__(self, email: str):
        super().__init__()

        self.email = email

        self.setWindowTitle(
            "PostGuard - Verify OTP"
        )

        self.resize(
            400,
            300
        )

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "Verify Your Email"
        )

        # แสดงว่า OTP ถูกส่งไปที่ email ไหน
        self.email_label = QLabel(
            f"OTP was sent to:\n{self.email}"
        )

        # -------------------------
        # OTP Input
        # -------------------------

        self.otp_input = QLineEdit()

        self.otp_input.setPlaceholderText(
            "Enter OTP"
        )

        self.otp_input.setMaxLength(6)

        # -------------------------
        # Buttons
        # -------------------------

        self.verify_button = QPushButton(
            "Verify OTP"
        )

        self.back_button = QPushButton(
            "Back"
        )

        # -------------------------
        # Layout
        # -------------------------

        layout = QVBoxLayout(self)

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.email_label
        )

        layout.addWidget(
            self.otp_input
        )

        layout.addWidget(
            self.verify_button
        )

        layout.addWidget(
            self.back_button
        )

        # -------------------------
        # Events
        # -------------------------

        self.verify_button.clicked.connect(
            self.handle_verify
        )

        self.back_button.clicked.connect(
            self.back_to_register
        )

    def handle_verify(self):
        otp = (
            self.otp_input
            .text()
            .strip()
        )

        # -------------------------
        # Basic validation
        # -------------------------

        if not otp:
            self.show_error(
                "Please enter the OTP."
            )
            return

        if len(otp) != 6:
            self.show_error(
                "OTP must contain 6 digits."
            )
            return

        if not otp.isdigit():
            self.show_error(
                "OTP must contain numbers only."
            )
            return

        # -------------------------
        # Verify OTP with Backend
        # -------------------------

        try:
            response = (
                APIClient.verify_register_otp(
                    email=self.email,
                    otp=otp
                )
            )

        except requests.RequestException:
            self.show_error(
                "Cannot connect to the PostGuard server."
            )
            return

        print(
            "VERIFY OTP STATUS:",
            response.status_code
        )

        print(
            "VERIFY OTP RESPONSE:",
            response.text
        )

        # -------------------------
        # OTP incorrect / expired
        # -------------------------

        if response.status_code not in (200,201):
            try:
                error_data = response.json()

                message = error_data.get(
                    "detail",
                    "OTP verification failed."
                )

            except ValueError:
                message = (
                    "OTP verification failed."
                )

            self.show_error(
                str(message)
            )

            return

        # -------------------------
        # Registration Successful
        # -------------------------

        QMessageBox.information(
            self,
            "PostGuard",
            "Registration successful. You can now log in."
        )

        self.open_login()

    def open_login(self):
        from app.ui.login_window import (
            LoginWindow
        )

        self.login_window = LoginWindow()

        self.login_window.show()

        self.close()

    def back_to_register(self):
        from app.ui.register_window import (
            RegisterWindow
        )

        self.register_window = (
            RegisterWindow()
        )

        self.register_window.show()

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