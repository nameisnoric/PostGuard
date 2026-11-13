"""Privacy Notice shown before PostGuard accesses the camera."""

from pathlib import Path

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
_CHECKBOX_ICON_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "icons"
)
PRIVACY_NOTICE_HTML = """
<h2>1. การใช้กล้องและข้อมูลท่าทาง</h2>
<p>PostGuard ใช้กล้องที่คุณเลือกเพื่อตรวจวัดท่าทางระหว่างการตรวจจับ
(Monitoring) โดยภาพจากกล้องจะถูกประมวลผลภายในอุปกรณ์ของคุณเท่านั้น
(Local Processing)</p>

<h2>2. ข้อมูลที่ระบบไม่จัดเก็บ</h2>
<p>PostGuard <b>ไม่บันทึกและไม่อัปโหลดภาพหรือวิดีโอจากกล้อง</b>
เมื่อประมวลผลเสร็จแล้ว ภาพต้นฉบับแต่ละเฟรมจะถูกทิ้งทันที</p>

<h2>3. ข้อมูลที่ระบบจัดเก็บ</h2>
<p>ระบบจัดเก็บเฉพาะข้อมูลที่จำเป็นต่อการทำงานและการแสดงประวัติ ได้แก่</p>
<ul>
  <li>ข้อมูลบัญชีผู้ใช้และการตั้งค่าของระบบ</li>
  <li>การตั้งค่ากล้องและค่า Personal Baseline ในรูปแบบตัวเลข</li>
  <li>เวลา ระยะเวลา และสถานะของ Monitoring Session</li>
  <li>ค่าท่าทางและคะแนนความเสี่ยงที่ระบบคำนวณได้</li>
  <li>เหตุการณ์แจ้งเตือน (Alert Events)</li>
  <li>รายงานและสรุปผลของแต่ละ Session</li>
</ul>
<p>ข้อมูลเหล่านี้จะผูกกับบัญชี PostGuard ที่คุณเข้าสู่ระบบอยู่
เพื่อให้คุณสามารถดูประวัติและรายงานของตนเองได้</p>

<h2>4. ทางเลือกและสิทธิของคุณ</h2>
<p>คุณสามารถเลือก <b>“ไว้ภายหลัง”</b> ได้ โดยยังใช้งานส่วนบัญชีของระบบได้
แต่จะยังไม่สามารถเริ่มการตรวจจับด้วยกล้องจนกว่าจะให้ความยินยอม</p>
<p>ภายหลังคุณสามารถเข้าไปที่หน้าการตั้งค่าเพื่ออ่านประกาศฉบับนี้อีกครั้ง
ตรวจสอบสถานะ ให้ความยินยอม หรือถอนความยินยอมได้</p>
<p>การถอนความยินยอมจะป้องกันการตรวจจับด้วยกล้องในอนาคต
แต่จะไม่ลบประวัติเดิมโดยอัตโนมัติ หากต้องการลบบัญชีและข้อมูลที่เกี่ยวข้อง
คุณสามารถส่งคำขอลบบัญชีแยกต่างหากได้จากหน้าการตั้งค่า</p>
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

        eyebrow = QLabel(f"ประกาศความเป็นส่วนตัว · เวอร์ชัน {PRIVACY_NOTICE_VERSION}")
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
            self.accept_checkbox.setObjectName(
                "privacyConsentCheckbox"
            )
            unchecked_icon = (
                _CHECKBOX_ICON_DIRECTORY
                / "checkbox-unchecked.svg"
            ).as_posix()
            checked_icon = (
                _CHECKBOX_ICON_DIRECTORY
                / "checkbox-checked.svg"
            ).as_posix()
            self.accept_checkbox.setStyleSheet(
                f"""
                QCheckBox {{
                    color: #0f172a;
                    background: transparent;
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    image: url(\"{unchecked_icon}\");
                }}
                QCheckBox::indicator:checked {{
                    image: url(\"{checked_icon}\");
                }}
                QCheckBox:disabled {{
                    color: #64748b;
                }}
                """
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
            self.status_label.setText(str(detail or "ไม่สามารถบันทึกการยินยอมด้านความเป็นส่วนตัวได้"))
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
