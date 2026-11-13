"""Authenticated password-change dialog."""

import requests
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.services.api_client import APIClient
from app.ui.theme import APP_QSS
from app.ui.utils.auth_validation import (
    password_validation_errors,
    password_feedback,
    response_error_message,
    validation_message,
)
from app.ui.utils.password_visibility import attach_password_visibility


class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostGuard - เปลี่ยนรหัสผ่าน")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel("เปลี่ยนรหัสผ่าน")
        title.setProperty("role", "heading")
        note = QLabel(
            "รหัสผ่านใหม่ต้องมีอย่างน้อย 8 ตัวอักษร พร้อมตัวพิมพ์ใหญ่ "
            "ตัวพิมพ์เล็ก ตัวเลข และอักขระพิเศษ"
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(note)

        self.current_password_input = self._password_field("รหัสผ่านปัจจุบัน")
        self.new_password_input = self._password_field("รหัสผ่านใหม่")
        self.confirm_password_input = self._password_field("ยืนยันรหัสผ่านใหม่")
        for label, field in (
            ("รหัสผ่านปัจจุบัน", self.current_password_input),
            ("รหัสผ่านใหม่", self.new_password_input),
            ("ยืนยันรหัสผ่านใหม่", self.confirm_password_input),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(field)
            if field is self.new_password_input:
                self.password_feedback_label = QLabel(password_feedback(""))
                self.password_feedback_label.setProperty("role", "muted")
                self.password_feedback_label.setWordWrap(True)
                layout.addWidget(self.password_feedback_label)
        self.new_password_input.textChanged.connect(
            lambda value: self.password_feedback_label.setText(password_feedback(value))
        )

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.cancel_button = QPushButton("ยกเลิก")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("เปลี่ยนรหัสผ่าน")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self.submit)
        actions.addStretch()
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)

    @staticmethod
    def _password_field(placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        attach_password_visibility(field)
        return field

    def _clear_passwords(self) -> None:
        self.current_password_input.clear()
        self.new_password_input.clear()
        self.confirm_password_input.clear()

    def submit(self) -> None:
        current_password = self.current_password_input.text()
        new_password = self.new_password_input.text()
        confirmation = self.confirm_password_input.text()

        missing = []
        if not current_password:
            missing.append("กรุณากรอกรหัสผ่านปัจจุบัน")
        if not new_password:
            missing.append("กรุณากรอกรหัสผ่านใหม่")
        if not confirmation:
            missing.append("กรุณากรอกยืนยันรหัสผ่านใหม่")
        if missing:
            self.status_label.setText(validation_message("กรอกข้อมูลไม่ครบ:", missing))
            return

        password_errors = password_validation_errors(new_password)
        if password_errors:
            self.status_label.setText(
                validation_message("รหัสผ่านใหม่ไม่ผ่านเงื่อนไข:", password_errors)
            )
            self.new_password_input.setFocus()
            return
        if new_password != confirmation:
            self.status_label.setText("รหัสผ่านใหม่และการยืนยันรหัสผ่านไม่ตรงกัน")
            self.confirm_password_input.clear()
            self.confirm_password_input.setFocus()
            return
        if current_password == new_password:
            self.status_label.setText("รหัสผ่านใหม่ต้องไม่เหมือนรหัสผ่านปัจจุบัน")
            return

        answer = QMessageBox.question(
            self,
            "ยืนยันการเปลี่ยนรหัสผ่าน",
            "ต้องการเปลี่ยนรหัสผ่านและออกจากระบบทุกอุปกรณ์หรือไม่?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.save_button.setEnabled(False)
        self.status_label.setText("กำลังเปลี่ยนรหัสผ่าน...")
        try:
            response = APIClient.change_password(current_password, new_password)
        except requests.RequestException:
            self.status_label.setText("ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ PostGuard ได้")
            return
        finally:
            self.save_button.setEnabled(True)

        if not response.ok:
            self.status_label.setText(response_error_message(
                response,
                "ไม่สามารถเปลี่ยนรหัสผ่านได้",
            ))
            return

        self._clear_passwords()
        QMessageBox.information(
            self,
            "เปลี่ยนรหัสผ่านสำเร็จ",
            "เปลี่ยนรหัสผ่านแล้ว กรุณาเข้าสู่ระบบอีกครั้งด้วยรหัสผ่านใหม่",
        )
        self.accept()
