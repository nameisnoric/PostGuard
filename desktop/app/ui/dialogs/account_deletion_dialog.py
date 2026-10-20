"""Confirmation dialog for the account deletion and recovery flow."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class AccountDeletionConfirmationDialog(QDialog):
    """Explain the recovery period before an account deletion request."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostGuard - Delete Account")
        self.setModal(True)
        self.setFixedWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(16)

        heading = QLabel("ยืนยันคำขอลบบัญชี?")
        heading.setProperty("role", "title")
        message = QLabel(
            "บัญชีจะถูกปิดใช้งานทันทีและกำหนดให้ลบถาวรภายใน 14 วัน "
            "ระหว่างนี้สามารถเข้าสู่ระบบอีกครั้งเพื่อกู้คืนบัญชีได้ "
            "เมื่อครบกำหนด บัญชี ประวัติการตรวจจับ และรูป Profile "
            "ส่วนตัวจะถูกลบถาวร"
        )
        message.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("เก็บบัญชีไว้")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("Delete Account")
        confirm.setProperty("variant", "danger")
        confirm.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)

        layout.addWidget(heading)
        layout.addWidget(message)
        layout.addLayout(buttons)
