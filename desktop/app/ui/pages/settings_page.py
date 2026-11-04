"""Persisted notification and local alert-sound settings."""

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from app.services.alert_sound import AlertSoundPlayer, DEFAULT_SETTINGS
from app.services.api_client import APIClient
from app.ui.dialogs.account_deletion_dialog import AccountDeletionConfirmationDialog
from app.ui.theme import polish


class SettingsPage(QWidget):
    settings_updated = Signal(dict)
    privacy_consent_changed = Signal(bool)
    account_deletion_requested = Signal()

    def __init__(self, sound_player: AlertSoundPlayer):
        super().__init__()
        self.sound_player = sound_player
        self.current_settings = DEFAULT_SETTINGS.copy()
        self.has_privacy_consent = None
        self.setProperty("page", True)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page_layout.addWidget(scroll)

        content = QWidget()
        content.setProperty("page", True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(48, 28, 48, 40)
        layout.setSpacing(16)
        scroll.setWidget(content)

        title = QLabel("การตั้งค่า")
        title.setProperty("role", "title")
        subtitle = QLabel("จัดการการแจ้งเตือนท่าทางและเสียงแจ้งเตือน")
        subtitle.setProperty("role", "muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        row = QHBoxLayout()
        row.addStretch()
        card = QFrame()
        card.setProperty("card", True)
        card.setMaximumWidth(900)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 26, 28, 26)
        card_layout.setSpacing(18)

        heading = QLabel("การตั้งค่าการแจ้งเตือน")
        heading.setProperty("role", "heading")
        card_layout.addWidget(heading)

        self.notifications_enabled = QCheckBox("เปิดป๊อปอัปแจ้งเตือนท่าทาง")
        self.notifications_enabled.toggled.connect(self._sync_enabled_state)
        self.sound_enabled = QCheckBox("เล่นเสียงเมื่อมีการแจ้งเตือนท่าทาง")
        self.sound_enabled.toggled.connect(self._sync_enabled_state)
        card_layout.addWidget(self.notifications_enabled)
        card_layout.addWidget(self.sound_enabled)

        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("ระดับเสียงแจ้งเตือน"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setSingleStep(5)
        self.volume_slider.valueChanged.connect(self._show_volume)
        self.volume_label = QLabel("70%")
        self.volume_label.setMinimumWidth(44)
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_label)
        card_layout.addLayout(volume_row)

        reminder_row = QHBoxLayout()
        reminder_row.addWidget(QLabel("เล่นเสียงซ้ำขณะที่การแจ้งเตือนยังทำงาน"))
        self.reminder_interval = QComboBox()
        for minutes in (1, 5, 10, 15, 30, 60):
            self.reminder_interval.addItem(
                f"ทุก {minutes} นาที",
                minutes,
            )
        reminder_row.addWidget(self.reminder_interval)
        card_layout.addLayout(reminder_row)

        note = QLabel(
            "ป๊อปอัปจะแสดงเมื่อพบเหตุการณ์ท่าทางใหม่ ส่วนเสียงจะเล่นตามระดับเสียง "
            "และช่วงเวลาแจ้งเตือนซ้ำที่กำหนด เหตุการณ์ยังคงถูกบันทึกไว้ในประวัติ"
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        card_layout.addWidget(note)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        card_layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.test_sound_button = QPushButton("ทดสอบเสียง")
        self.test_sound_button.clicked.connect(self.test_sound)
        self.save_button = QPushButton("บันทึกการเปลี่ยนแปลง")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self.save_settings)
        actions.addWidget(self.test_sound_button)
        actions.addStretch()
        actions.addWidget(self.save_button)
        card_layout.addLayout(actions)

        row.addWidget(card, 1)
        row.addStretch()
        layout.addLayout(row)

        privacy_row = QHBoxLayout()
        privacy_row.addStretch()
        privacy_card = QFrame()
        privacy_card.setProperty("card", True)
        privacy_card.setMaximumWidth(900)
        privacy_layout = QVBoxLayout(privacy_card)
        privacy_layout.setContentsMargins(28, 26, 28, 26)
        privacy_layout.setSpacing(12)

        privacy_heading = QLabel("ความเป็นส่วนตัวและข้อมูลกล้อง")
        privacy_heading.setProperty("role", "heading")
        privacy_note = QLabel(
            "ตรวจสอบวิธีประมวลผลภาพจากกล้อง สถานะการยินยอม "
            "หรือถอนความยินยอมสำหรับการตรวจจับในอนาคต"
        )
        privacy_note.setProperty("role", "muted")
        privacy_note.setWordWrap(True)
        self.privacy_status_label = QLabel('สถานะความยินยอม: ยังไม่ได้โหลด')
        self.privacy_status_label.setWordWrap(True)

        privacy_actions = QHBoxLayout()
        self.review_privacy_button = QPushButton("อ่านประกาศความเป็นส่วนตัว")
        self.review_privacy_button.clicked.connect(self.review_privacy_notice)
        self.consent_action_button = QPushButton("ให้ความยินยอม")
        self.consent_action_button.clicked.connect(self.handle_privacy_consent_action)
        privacy_actions.addWidget(self.review_privacy_button)
        privacy_actions.addStretch()
        privacy_actions.addWidget(self.consent_action_button)

        privacy_layout.addWidget(privacy_heading)
        privacy_layout.addWidget(privacy_note)
        privacy_layout.addWidget(self.privacy_status_label)
        privacy_layout.addLayout(privacy_actions)
        privacy_row.addWidget(privacy_card, 1)
        privacy_row.addStretch()
        layout.addLayout(privacy_row)

        account_row = QHBoxLayout()
        account_row.addStretch()
        self.danger_card = QFrame()
        self.danger_card.setProperty("card", True)
        self.danger_card.setProperty("variant", "dangerZone")
        self.danger_card.setMaximumWidth(900)
        danger_layout = QVBoxLayout(self.danger_card)
        danger_layout.setContentsMargins(28, 22, 28, 22)
        danger_layout.setSpacing(10)
        danger_title = QLabel("ลบบัญชี")
        danger_title.setProperty("role", "heading")
        danger_message = QLabel(
            "ปิดใช้งานบัญชีทันทีและลบข้อมูลถาวรหลังระยะเวลากู้คืน 14 วัน "
            "คุณสามารถเข้าสู่ระบบเพื่อกู้คืนบัญชีได้ก่อนครบกำหนด"
        )
        danger_message.setProperty("role", "muted")
        danger_message.setWordWrap(True)
        self.account_status_label = QLabel("")
        self.account_status_label.setProperty("role", "muted")
        self.account_status_label.setWordWrap(True)
        self.delete_account_button = QPushButton("ลบบัญชี")
        self.delete_account_button.setProperty("variant", "danger")
        self.delete_account_button.clicked.connect(self.confirm_account_deletion)
        danger_actions = QHBoxLayout()
        danger_actions.addWidget(self.delete_account_button)
        danger_actions.addStretch()
        danger_layout.addWidget(danger_title)
        danger_layout.addWidget(danger_message)
        danger_layout.addWidget(self.account_status_label)
        danger_layout.addLayout(danger_actions)
        account_row.addWidget(self.danger_card, 1)
        account_row.addStretch()
        layout.addLayout(account_row)
        layout.addStretch()
        self._populate(DEFAULT_SETTINGS)
        self._set_privacy_consent_action(None)

    def confirm_account_deletion(self) -> None:
        dialog = AccountDeletionConfirmationDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.account_deletion_requested.emit()

    def load_settings(self) -> None:
        self.status_label.setText('กำลังโหลดการตั้งค่า...')
        try:
            response = APIClient.get_settings()
        except requests.RequestException:
            self.status_label.setText("ไม่สามารถโหลดการตั้งค่าได้ โปรดตรวจสอบการเชื่อมต่อ")
            return
        if not response.ok:
            self.status_label.setText(
                self._response_error(response, "ไม่สามารถโหลดการตั้งค่าได้")
            )
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            self.status_label.setText("ข้อมูลการตั้งค่าที่ได้รับไม่ถูกต้อง")
            return
        if not self._valid_payload(payload):
            self.status_label.setText("ข้อมูลการตั้งค่าที่ได้รับไม่ถูกต้อง")
            return
        self.current_settings = self._settings_only(payload)
        self._populate(self.current_settings)
        self.status_label.clear()
        self.settings_updated.emit(self.current_settings.copy())

    def save_settings(self) -> None:
        settings = self.form_settings()
        self.save_button.setEnabled(False)
        self.status_label.setText('กำลังบันทึกการตั้งค่า...')
        try:
            response = APIClient.update_settings(settings)
        except (requests.RequestException, ValueError):
            self.status_label.setText("ไม่สามารถบันทึกการตั้งค่าได้ โปรดตรวจสอบการเชื่อมต่อ")
            return
        finally:
            self.save_button.setEnabled(True)
        if not response.ok:
            self.status_label.setText(
                self._response_error(response, "ไม่สามารถบันทึกการตั้งค่าได้")
            )
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            self.status_label.setText("ข้อมูลตอบกลับจากการอัปเดตการตั้งค่าไม่ถูกต้อง")
            return
        if not self._valid_payload(payload):
            self.status_label.setText("ข้อมูลตอบกลับจากการอัปเดตการตั้งค่าไม่ถูกต้อง")
            return
        self.current_settings = self._settings_only(payload)
        self._populate(self.current_settings)
        self.settings_updated.emit(self.current_settings.copy())
        self.status_label.setText('บันทึกการตั้งค่าแล้ว')

    def form_settings(self) -> dict:
        return {
            "notifications_enabled": self.notifications_enabled.isChecked(),
            "sound_enabled": self.sound_enabled.isChecked(),
            "sound_volume": self.volume_slider.value(),
            "reminder_interval_minutes": int(self.reminder_interval.currentData()),
        }

    def test_sound(self) -> None:
        if not self.notifications_enabled.isChecked() or not self.sound_enabled.isChecked():
            self.status_label.setText("โปรดเปิดการแจ้งเตือนและเสียงเพื่อทดสอบการแจ้งเตือน")
            return
        if self.volume_slider.value() == 0:
            self.status_label.setText("โปรดเพิ่มระดับเสียงแจ้งเตือนเพื่อทดสอบเสียง")
            return
        self.sound_player.play_preview(self.volume_slider.value())
        self.status_label.setText('กำลังเล่นเสียงแจ้งเตือน')

    def load_privacy_consent(self) -> None:
        self.privacy_status_label.setText('สถานะความยินยอม: กำลังโหลด...')
        try:
            response = APIClient.get_privacy_consent()
        except requests.RequestException:
            self.privacy_status_label.setText(
                "สถานะการยินยอม: ไม่สามารถโหลดได้ โปรดตรวจสอบการเชื่อมต่อ"
            )
            self._set_privacy_consent_action(None)
            return
        if not response.ok:
            self.privacy_status_label.setText("สถานะการยินยอม: ไม่สามารถโหลดได้")
            self._set_privacy_consent_action(None)
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            payload = None
        if not isinstance(payload, dict) or type(
            payload.get("has_current_consent")
        ) is not bool:
            self.privacy_status_label.setText("สถานะการยินยอม: ข้อมูลตอบกลับไม่ถูกต้อง")
            self._set_privacy_consent_action(None)
            return

        accepted = payload["has_current_consent"]
        self._set_privacy_consent_action(accepted)
        if accepted:
            accepted_at = payload.get("accepted_at") or "recorded"
            self.privacy_status_label.setText(
                f"สถานะการยินยอม: ยินยอมแล้ว · {accepted_at}"
            )
        elif payload.get("withdrawn_at"):
            self.privacy_status_label.setText(
                f"สถานะการยินยอม: ถอนความยินยอมแล้ว · {payload['withdrawn_at']}"
            )
        else:
            self.privacy_status_label.setText('สถานะความยินยอม: ยังไม่ยอมรับ')

    def review_privacy_notice(self) -> None:
        from app.ui.dialogs.privacy_notice_dialog import PrivacyNoticeDialog

        PrivacyNoticeDialog(self, require_acceptance=False).exec()

    def handle_privacy_consent_action(self) -> None:
        if self.has_privacy_consent is True:
            self.withdraw_privacy_consent()
        elif self.has_privacy_consent is False:
            self.give_privacy_consent()

    def give_privacy_consent(self) -> None:
        from app.ui.dialogs.privacy_notice_dialog import PrivacyNoticeDialog

        dialog = PrivacyNoticeDialog(self, require_acceptance=True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._set_privacy_consent_action(True)
        self.privacy_status_label.setText('Consent status: Accepted')
        self.privacy_consent_changed.emit(True)

    def withdraw_privacy_consent(self) -> None:
        answer = QMessageBox.question(
            self,
            'ถอนความยินยอมการใช้กล้อง',
            "ต้องการถอนความยินยอมสำหรับการตรวจจับด้วยกล้องในอนาคตหรือไม่? ประวัติที่มีอยู่ "
            "จะยังคงสามารถดูได้",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.consent_action_button.setEnabled(False)
        try:
            response = APIClient.withdraw_privacy_consent()
        except requests.RequestException:
            self.privacy_status_label.setText(
                "ไม่สามารถถอนความยินยอมได้ โปรดตรวจสอบการเชื่อมต่อ"
            )
            self.consent_action_button.setEnabled(True)
            return
        if not response.ok:
            self.privacy_status_label.setText(
                self._response_error(response, "ไม่สามารถถอนความยินยอมได้")
            )
            self.consent_action_button.setEnabled(True)
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            payload = None
        if not isinstance(payload, dict) or payload.get("has_current_consent") is not False:
            self.privacy_status_label.setText("ไม่สามารถยืนยันการถอนความยินยอมได้")
            self.consent_action_button.setEnabled(True)
            return
        self.privacy_status_label.setText('สถานะความยินยอม: ถอนแล้ว')
        self._set_privacy_consent_action(False)
        self.privacy_consent_changed.emit(False)

    def _set_privacy_consent_action(self, accepted: bool | None) -> None:
        self.has_privacy_consent = accepted
        self.consent_action_button.setEnabled(accepted is not None)
        if accepted is True:
            self.consent_action_button.setText("ถอนความยินยอม")
            self.consent_action_button.setProperty("variant", "danger")
        else:
            self.consent_action_button.setText("ให้ความยินยอม")
            self.consent_action_button.setProperty("variant", "primary")
        polish(self.consent_action_button)

    def _populate(self, settings: dict) -> None:
        self.notifications_enabled.setChecked(settings["notifications_enabled"])
        self.sound_enabled.setChecked(settings["sound_enabled"])
        self.volume_slider.setValue(settings["sound_volume"])
        index = self.reminder_interval.findData(settings["reminder_interval_minutes"])
        self.reminder_interval.setCurrentIndex(max(0, index))
        self._sync_enabled_state()

    def _sync_enabled_state(self, *_args) -> None:
        notifications = self.notifications_enabled.isChecked()
        sound = notifications and self.sound_enabled.isChecked()
        self.sound_enabled.setEnabled(notifications)
        self.volume_slider.setEnabled(sound)
        self.reminder_interval.setEnabled(sound)
        self.test_sound_button.setEnabled(sound)

    def _show_volume(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")

    @staticmethod
    def _settings_only(payload: dict) -> dict:
        return {key: payload[key] for key in DEFAULT_SETTINGS}

    @staticmethod
    def _valid_payload(payload) -> bool:
        return (
            isinstance(payload, dict)
            and type(payload.get("notifications_enabled")) is bool
            and type(payload.get("sound_enabled")) is bool
            and type(payload.get("sound_volume")) is int
            and 0 <= payload["sound_volume"] <= 100
            and type(payload.get("reminder_interval_minutes")) is int
            and payload["reminder_interval_minutes"] in (1, 5, 10, 15, 30, 60)
        )

    @staticmethod
    def _response_error(response, fallback: str) -> str:
        if getattr(response, "status_code", None) == 404:
            return "ไม่สามารถใช้งาน API การตั้งค่าได้ โปรดรีสตาร์ต PostGuard backend"
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError, TypeError):
            detail = None
        return str(detail) if detail else fallback
