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

        # =========================================================
        # Email
        # =========================================================

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("อีเมล KU")

        # =========================================================
        # Password
        # =========================================================

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("รหัสผ่าน")
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        # ปุ่มดู / ซ่อนรหัสผ่าน
        self.password_toggle_button = QPushButton("ดู")
        self.password_toggle_button.setCheckable(True)
        self.password_toggle_button.setFixedWidth(54)
        self.password_toggle_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.password_toggle_button.clicked.connect(
            self.toggle_password_visibility
        )

        password_row = QHBoxLayout()
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.setSpacing(8)

        password_row.addWidget(
            self.password_input,
            stretch=1
        )
        password_row.addWidget(
            self.password_toggle_button
        )

        # =========================================================
        # Buttons
        # =========================================================

        self.login_button = QPushButton("เข้าสู่ระบบ")
        self.login_button.setProperty(
            "variant",
            "primary"
        )

        self.register_button = QPushButton(
            "สร้างบัญชี"
        )

        self.forgot_password_button = QPushButton(
            "ลืมรหัสผ่าน?"
        )

        self.forgot_password_button.clicked.connect(
            self.open_password_reset
        )

        self.login_button.clicked.connect(
            self.handle_login
        )

        self.register_button.clicked.connect(
            self.open_register
        )

        # กด Enter เพื่อ Login ได้
        self.password_input.returnPressed.connect(
            self.handle_login
        )

        # =========================================================
        # Layout
        # =========================================================

        outer = QHBoxLayout(self)
        outer.setContentsMargins(
            32,
            32,
            32,
            32
        )

        outer.addStretch()

        card = QFrame()
        card.setProperty("card", True)
        card.setMaximumWidth(460)
        card.setMinimumWidth(400)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            42,
            40,
            42,
            40
        )
        layout.setSpacing(14)

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            subtitle
        )

        layout.addSpacing(12)

        layout.addWidget(
            QLabel("อีเมล KU")
        )

        layout.addWidget(
            self.email_input
        )

        layout.addWidget(
            QLabel("รหัสผ่าน")
        )

        layout.addLayout(
            password_row
        )

        layout.addWidget(
            self.forgot_password_button,
            alignment=Qt.AlignmentFlag.AlignRight
        )

        layout.addWidget(
            self.login_button
        )

        layout.addWidget(
            self.register_button
        )

        outer.addWidget(
            card,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        outer.addStretch()

    # =============================================================
    # Password visibility
    # =============================================================

    def toggle_password_visibility(
        self,
        checked: bool
    ) -> None:

        if checked:
            self.password_input.setEchoMode(
                QLineEdit.EchoMode.Normal
            )

            self.password_toggle_button.setText(
                "ซ่อน"
            )

        else:
            self.password_input.setEchoMode(
                QLineEdit.EchoMode.Password
            )

            self.password_toggle_button.setText(
                "ดู"
            )

        # ไม่ให้ focus หลุดจากช่องรหัสผ่าน
        self.password_input.setFocus()

    # =============================================================
    # Login
    # =============================================================

    def handle_login(self) -> None:

        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:

            self.show_error(
                "กรุณากรอกอีเมลและรหัสผ่าน"
            )

            return

        try:

            response = APIClient.login(
                email,
                password
            )

        except requests.RequestException:

            self.show_error(
                "ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ PostGuard ได้"
            )

            return

        if response.status_code != 200:

            self.show_error(
                "อีเมลหรือรหัสผ่านไม่ถูกต้อง"
            )

            return

        login_data = response.json()

        access_token = login_data.get(
            "access_token"
        )

        if not access_token:

            self.show_error(
                "เซิร์ฟเวอร์ไม่ได้ส่ง Access Token กลับมา"
            )

            return

        TokenStore.set_token(
            access_token
        )

        try:

            me_response = APIClient.get_current_user()

        except requests.RequestException:

            TokenStore.clear_token()

            self.show_error(
                "ไม่สามารถโหลดข้อมูลผู้ใช้ได้"
            )

            return

        if me_response.status_code != 200:

            TokenStore.clear_token()

            self.show_error(
                "ไม่สามารถยืนยันข้อมูลผู้ใช้ได้"
            )

            return

        user_data = me_response.json()

        if (
            user_data.get("account_status")
            == "PENDING_DELETION"
        ):

            from app.ui.windows.account_recovery_window import (
                AccountRecoveryWindow,
            )

            self.recovery_window = (
                AccountRecoveryWindow(
                    user_data
                )
            )

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

    # =============================================================
    # Password reset
    # =============================================================

    def open_password_reset(self):

        from app.ui.dialogs.password_reset_dialog import (
            PasswordResetDialog,
        )

        dialog = PasswordResetDialog(
            self,
            email=self.email_input.text().strip(),
        )

        if (
            dialog.exec()
            == dialog.DialogCode.Accepted
        ):

            self.email_input.setText(
                dialog.email
            )

            self.password_input.clear()

            # ทุกครั้งหลัง reset password
            # กลับไปซ่อนรหัส
            self.password_toggle_button.setChecked(
                False
            )

            self.password_input.setEchoMode(
                QLineEdit.EchoMode.Password
            )

            self.password_toggle_button.setText(
                "ดู"
            )

            self.password_input.setFocus()

    # =============================================================
    # Register
    # =============================================================

    def open_register(self):

        from app.ui.windows.register_window import (
            RegisterWindow,
        )

        self.register_window = (
            RegisterWindow()
        )

        self.register_window.show()

        self.close()

    # =============================================================
    # Error dialog
    # =============================================================

    def show_error(
        self,
        message: str
    ) -> None:

        QMessageBox.warning(
            self,
            "PostGuard",
            message
        )