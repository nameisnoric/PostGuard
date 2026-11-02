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
PRIVACY_NOTICE_HTML = f"""
<p><b>โปรดอ่านข้อมูลต่อไปนี้ก่อนอนุญาตให้ PostGuard เปิดกล้อง</b></p>

<h2>1. การใช้กล้องและข้อมูลท่าทาง</h2>
<p>PostGuard ใช้กล้องที่คุณเลือกเพื่อวัดท่าทาง การกะพริบตา
และการเปลี่ยนแปลงของระยะใบหน้าในระหว่าง Monitoring Session
ภาพจากกล้องจะถูก <b>ประมวลผลภายในคอมพิวเตอร์ของคุณเท่านั้น</b>
(Local Processing)</p>

<h2>2. ข้อมูลที่ระบบไม่จัดเก็บ</h2>
<p>PostGuard <b>ไม่บันทึกและไม่อัปโหลดภาพหรือวิดีโอจากกล้อง</b>
เมื่อระบบประมวลผลภาพแต่ละเฟรมเสร็จแล้ว ภาพต้นฉบับ (Raw Frame)
จะถูกทิ้งทันที</p>

<h2>3. ข้อมูลที่ระบบจัดเก็บ</h2>
<p>ระบบบันทึกเฉพาะข้อมูลที่จำเป็นต่อการทำงานและการแสดงประวัติ ได้แก่</p>
<ul>
  <li>ข้อมูลบัญชีผู้ใช้และการตั้งค่าของระบบ</li>
  <li>การตั้งค่ากล้องและ Personal Baseline ในรูปแบบตัวเลข</li>
  <li>เวลา ระยะเวลา และสถานะของ Monitoring Session</li>
  <li>ค่าท่าทาง อัตราการกะพริบตา และคะแนนความเสี่ยงที่คำนวณได้</li>
  <li>เหตุการณ์แจ้งเตือน (Alert Events)</li>
  <li>Session Summary และรายงานย้อนหลัง</li>
</ul>
<p>ข้อมูลเหล่านี้จะเชื่อมกับบัญชี PostGuard ที่คุณกำลังเข้าสู่ระบบ
เพื่อให้ผู้ใช้อื่นไม่สามารถเปิดดูประวัติของคุณได้</p>

<h2>4. ทางเลือกและสิทธิของคุณ</h2>
<p>หากเลือก <b>“ยังไม่ยินยอม”</b> คุณยังสามารถเข้าสู่ระบบ จัดการบัญชี
และดูประวัติเดิมได้ แต่ระบบจะไม่เปิดกล้องและจะไม่เข้าสู่ขั้นตอน Camera Setup
หรือเริ่ม Monitoring Session ใหม่</p>
<p>คุณสามารถเปิดหน้า Settings เพื่อดำเนินการต่อไปนี้ได้ทุกเมื่อ:</p>
<ul>
  <li>อ่านประกาศความเป็นส่วนตัวอีกครั้ง</li>
  <li>ตรวจสอบสถานะหรือให้ความยินยอม</li>
  <li>ถอนความยินยอมสำหรับการใช้กล้องในอนาคต</li>
  <li>ส่งคำขอลบบัญชีและข้อมูลที่เกี่ยวข้อง</li>
</ul>
<p>การถอนความยินยอมจะป้องกันการเริ่ม Monitoring Session ใหม่
แต่จะไม่ลบ History และ Report เดิมโดยอัตโนมัติ
หากต้องการลบข้อมูลบัญชี ต้องใช้เมนู “ลบบัญชี” แยกต่างหาก</p>
<p><b>คุณไม่สามารถถอนความยินยอมขณะที่ Session อยู่ในสถานะ RUNNING หรือ PAUSED</b>
กรุณา Stop Monitoring ให้ Session สิ้นสุดก่อน แล้วจึงถอนความยินยอมจาก Settings</p>

<h2>5. การบันทึกการให้ความยินยอม</h2>
<p>เมื่อคุณทำเครื่องหมายในช่องยืนยันและกด “ให้ความยินยอมและดำเนินการต่อ”
ระบบจะบันทึกหมายเลขฉบับของประกาศ ฉบับที่คุณยอมรับ วันและเวลาที่ยอมรับ
วันและเวลาที่ถอนความยินยอม (ถ้ามี) และสถานะความยินยอมปัจจุบัน</p>
<p>ประกาศความเป็นส่วนตัวฉบับปัจจุบัน: <b>{PRIVACY_NOTICE_VERSION}</b></p>
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

        eyebrow = QLabel(f"ประกาศความเป็นส่วนตัว · ฉบับ {PRIVACY_NOTICE_VERSION}")
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
                "ฉันได้อ่านและยินยอมให้ PostGuard ประมวลผลภาพจากกล้องบนอุปกรณ์นี้ "
                "\nและบันทึกเฉพาะข้อมูลที่ระบุข้างต้น"
            )
            layout.addWidget(self.accept_checkbox)
            layout.addWidget(self.status_label)
            self.cancel_button = QPushButton("ยังไม่ยินยอม")
            self.accept_button = QPushButton("ให้ความยินยอมและดำเนินการต่อ")
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
            self.status_label.setText(
                str(detail or "ไม่สามารถบันทึกความยินยอมได้ กรุณาลองอีกครั้ง")
            )
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
