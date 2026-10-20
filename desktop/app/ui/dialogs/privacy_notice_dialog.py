"""Privacy Notice shown before PostGuard accesses the camera."""

import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from app.services.api_client import APIClient
from app.ui.theme import APP_QSS, set_centered_window


PRIVACY_NOTICE_VERSION = "2026-10-20"
PRIVACY_NOTICE_HTML = """
<h2>Camera and posture data</h2>
<p>PostGuard uses your selected camera to measure posture while monitoring is
active. Camera frames are processed locally on this device.</p>

<h2>What is not stored</h2>
<p>PostGuard does not save or upload camera images or video. Raw frames are
discarded after local processing.</p>

<h2>What is stored</h2>
<p>PostGuard stores only the account, camera configuration, numerical baseline,
session timing, calculated posture measurements, alert events and reports needed
to provide your history. These records are associated with your signed-in
account in the PostGuard database.</p>

<h2>Your choice</h2>
<p>You can decline now and continue using account pages without camera access.
You can review this notice or withdraw consent later in Settings. Withdrawal
blocks future camera monitoring but does not delete existing history. You can
request account deletion from Profile.</p>
"""


class PrivacyNoticeDialog(QDialog):
    def __init__(self, parent=None, require_acceptance: bool = True):
        super().__init__(parent)
        self.require_acceptance = require_acceptance
        self.setWindowTitle("PostGuard - ประกาศความเป็นส่วนตัว")
        self.setObjectName("privacyNoticeDialog")
        self.setStyleSheet(APP_QSS)
        set_centered_window(self, 720, 650, 620, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        eyebrow = QLabel(f"PRIVACY NOTICE · VERSION {PRIVACY_NOTICE_VERSION}")
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("ข้อมูลจากกล้องจะอยู่บนอุปกรณ์นี้")
        title.setProperty("role", "title")
        subtitle = QLabel(
            "ตรวจสอบวิธีที่ PostGuard ประมวลผลภาพจากกล้องและจัดเก็บค่าที่คำนวณได้"
        )
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)

        self.notice = QTextBrowser()
        self.notice.setHtml(PRIVACY_NOTICE_HTML)
        self.notice.setOpenExternalLinks(False)

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.notice, 1)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)

        actions = QHBoxLayout()
        if require_acceptance:
            self.accept_checkbox = QCheckBox(
                "ฉันเข้าใจและยินยอมให้ประมวลผลข้อมูลจากกล้องตามที่ระบุ"
            )
            layout.addWidget(self.accept_checkbox)
            layout.addWidget(self.status_label)
            self.cancel_button = QPushButton("ไว้ภายหลัง")
            self.accept_button = QPushButton("ยอมรับและดำเนินการต่อ")
            self.accept_button.setProperty("variant", "primary")
            self.accept_button.setEnabled(False)
            self.accept_checkbox.toggled.connect(self.accept_button.setEnabled)
            self.cancel_button.clicked.connect(self.reject)
            self.accept_button.clicked.connect(self.accept_consent)
            actions.addWidget(self.cancel_button)
            actions.addStretch()
            actions.addWidget(self.accept_button)
        else:
            self.accept_checkbox = None
            close_button = QPushButton("ปิด")
            close_button.setProperty("variant", "primary")
            close_button.clicked.connect(self.accept)
            actions.addStretch()
            actions.addWidget(close_button)
        layout.addLayout(actions)

    def accept_consent(self) -> None:
        if self.accept_checkbox is None or not self.accept_checkbox.isChecked():
            return
        self.accept_button.setEnabled(False)
        self.status_label.setText('กำลังบันทึกตัวเลือกความเป็นส่วนตัว...')
        try:
            response = APIClient.accept_privacy_consent(PRIVACY_NOTICE_VERSION)
        except requests.RequestException:
            self.status_label.setText(
                'บันทึกตัวเลือกความเป็นส่วนตัวไม่สำเร็จ โปรดตรวจสอบการเชื่อมต่อ'
            )
            self.accept_button.setEnabled(True)
            return
        if not response.ok:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError, TypeError):
                detail = None
            self.status_label.setText(str(detail or "Privacy consent could not be saved."))
            self.accept_button.setEnabled(True)
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            payload = None
        if not isinstance(payload, dict) or not payload.get("has_current_consent"):
            self.status_label.setText('เซิร์ฟเวอร์ไม่ยืนยันการให้ความยินยอม')
            self.accept_button.setEnabled(True)
            return
        self.accept()
