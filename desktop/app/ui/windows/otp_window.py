import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.api_client import APIClient
from app.ui.theme import APP_QSS, set_centered_window


class OTPWindow(QWidget):
    def __init__(self, email: str):
        super().__init__()

        self.email = email
        self.setWindowTitle("PostGuard - ยืนยันอีเมล")
        set_centered_window(self, 760, 520, 640, 460)
        self.setObjectName("authWindow")
        self.setStyleSheet(APP_QSS)

        eyebrow = QLabel("การยืนยันอีเมล")
        eyebrow.setProperty("role", "eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("ยืนยันอีเมลของคุณ")
        self.title_label.setProperty("role", "title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel(
            "กรอกรหัสยืนยัน 6 หลักที่ส่งไปยัง"
        )
        description.setProperty("role", "muted")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.email_label = QLabel(self.email)
        self.email_label.setProperty("role", "heading")
        self.email_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.email_label.setWordWrap(True)

        self.otp_input = QLineEdit()
        self.otp_input.setPlaceholderText("รหัสยืนยัน 6 หลัก")
        self.otp_input.setMaxLength(6)
        self.otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.otp_input.setClearButtonEnabled(True)

        helper = QLabel(
            "รหัสมีอายุ 5 นาที หากไม่พบโปรดตรวจสอบโฟลเดอร์สแปม"
        )
        helper.setProperty("role", "muted")
        helper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        helper.setWordWrap(True)

        self.verify_button = QPushButton("ยืนยันอีเมล")
        self.verify_button.setProperty("variant", "primary")
        self.back_button = QPushButton("กลับไปหน้าสมัครสมาชิก")

        self.card = QFrame()
        self.card.setProperty("card", True)
        self.card.setMaximumWidth(500)
        self.card.setMinimumWidth(420)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(42, 38, 42, 38)
        card_layout.setSpacing(13)
        card_layout.addWidget(eyebrow)
        card_layout.addWidget(self.title_label)
        card_layout.addWidget(description)
        card_layout.addWidget(self.email_label)
        card_layout.addSpacing(8)
        card_layout.addWidget(QLabel("รหัสยืนยัน"))
        card_layout.addWidget(self.otp_input)
        card_layout.addWidget(helper)
        card_layout.addSpacing(6)
        card_layout.addWidget(self.verify_button)
        card_layout.addWidget(self.back_button)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.addStretch()
        outer.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

        self.verify_button.clicked.connect(self.handle_verify)
        self.back_button.clicked.connect(self.back_to_register)
        self.otp_input.returnPressed.connect(self.handle_verify)
        self.otp_input.setFocus()

    def handle_verify(self):
        otp = self.otp_input.text().strip()

        if not otp:
            self.show_error("Please enter the OTP.")
            return

        if len(otp) != 6:
            self.show_error("OTP must contain 6 digits.")
            return

        if not otp.isdigit():
            self.show_error("OTP must contain numbers only.")
            return

        self.verify_button.setEnabled(False)

        try:
            response = APIClient.verify_register_otp(
                email=self.email,
                otp=otp,
            )
        except requests.RequestException:
            self.verify_button.setEnabled(True)
            self.show_error("Cannot connect to the PostGuard server.")
            return

        if response.status_code not in (200, 201):
            self.verify_button.setEnabled(True)
            try:
                error_data = response.json()
                message = error_data.get(
                    "detail",
                    "OTP verification failed.",
                )
            except (AttributeError, ValueError):
                message = "OTP verification failed."

            self.show_error(str(message))
            self.otp_input.selectAll()
            self.otp_input.setFocus()
            return

        QMessageBox.information(
            self,
            'สมัครสมาชิกสำเร็จ',
            'ยืนยันอีเมลแล้ว คุณสามารถเข้าสู่ระบบได้',
        )
        self.open_login()

    def open_login(self):
        from app.ui.windows.login_window import LoginWindow

        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

    def back_to_register(self):
        from app.ui.windows.register_window import RegisterWindow

        self.register_window = RegisterWindow()
        self.register_window.email_input.setText(self.email)
        self.register_window.show()
        self.close()

    def show_error(self, message: str):
        QMessageBox.warning(
            self,
            "PostGuard",
            message,
        )
