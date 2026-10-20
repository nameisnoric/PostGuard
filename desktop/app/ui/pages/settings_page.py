"""Persisted notification and local alert-sound settings."""

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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


class SettingsPage(QWidget):
    settings_updated = Signal(dict)
    privacy_consent_changed = Signal(bool)

    def __init__(self, sound_player: AlertSoundPlayer):
        super().__init__()
        self.sound_player = sound_player
        self.current_settings = DEFAULT_SETTINGS.copy()
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

        title = QLabel("Settings")
        title.setProperty("role", "title")
        subtitle = QLabel("Manage posture notifications and alert sound preferences.")
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

        heading = QLabel("Alert preferences")
        heading.setProperty("role", "heading")
        card_layout.addWidget(heading)

        self.notifications_enabled = QCheckBox("Enable posture notifications")
        self.notifications_enabled.toggled.connect(self._sync_enabled_state)
        self.sound_enabled = QCheckBox("Play a sound for posture alerts")
        self.sound_enabled.toggled.connect(self._sync_enabled_state)
        card_layout.addWidget(self.notifications_enabled)
        card_layout.addWidget(self.sound_enabled)

        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Alert volume"))
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
        reminder_row.addWidget(QLabel("Repeat sound while the alert remains active"))
        self.reminder_interval = QComboBox()
        for minutes in (1, 5, 10, 15, 30, 60):
            self.reminder_interval.addItem(
                f"Every {minutes} minute" + ("" if minutes == 1 else "s"),
                minutes,
            )
        reminder_row.addWidget(self.reminder_interval)
        card_layout.addLayout(reminder_row)

        note = QLabel(
            "Settings affect local notifications only. Alert events are still stored "
            "in your history when the monitoring rule is triggered."
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        card_layout.addWidget(note)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        card_layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.test_sound_button = QPushButton("Test Sound")
        self.test_sound_button.clicked.connect(self.test_sound)
        self.save_button = QPushButton("Save Changes")
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

        privacy_heading = QLabel("Privacy and camera data")
        privacy_heading.setProperty("role", "heading")
        privacy_note = QLabel(
            "Review how camera frames are processed, check your consent status, "
            "or withdraw consent for future monitoring."
        )
        privacy_note.setProperty("role", "muted")
        privacy_note.setWordWrap(True)
        self.privacy_status_label = QLabel("Consent status: Not loaded")
        self.privacy_status_label.setWordWrap(True)

        privacy_actions = QHBoxLayout()
        self.review_privacy_button = QPushButton("Review Privacy Notice")
        self.review_privacy_button.clicked.connect(self.review_privacy_notice)
        self.withdraw_privacy_button = QPushButton("Withdraw Consent")
        self.withdraw_privacy_button.setProperty("variant", "danger")
        self.withdraw_privacy_button.clicked.connect(self.withdraw_privacy_consent)
        privacy_actions.addWidget(self.review_privacy_button)
        privacy_actions.addStretch()
        privacy_actions.addWidget(self.withdraw_privacy_button)

        privacy_layout.addWidget(privacy_heading)
        privacy_layout.addWidget(privacy_note)
        privacy_layout.addWidget(self.privacy_status_label)
        privacy_layout.addLayout(privacy_actions)
        privacy_row.addWidget(privacy_card, 1)
        privacy_row.addStretch()
        layout.addLayout(privacy_row)
        layout.addStretch()
        self._populate(DEFAULT_SETTINGS)
        self.withdraw_privacy_button.setEnabled(False)

    def load_settings(self) -> None:
        self.status_label.setText("Loading settings...")
        try:
            response = APIClient.get_settings()
        except requests.RequestException:
            self.status_label.setText("Cannot load settings. Check your connection.")
            return
        if not response.ok:
            self.status_label.setText(
                self._response_error(response, "Settings could not be loaded.")
            )
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            self.status_label.setText("Settings response was invalid.")
            return
        if not self._valid_payload(payload):
            self.status_label.setText("Settings response was invalid.")
            return
        self.current_settings = self._settings_only(payload)
        self._populate(self.current_settings)
        self.status_label.clear()
        self.settings_updated.emit(self.current_settings.copy())

    def save_settings(self) -> None:
        settings = self.form_settings()
        self.save_button.setEnabled(False)
        self.status_label.setText("Saving settings...")
        try:
            response = APIClient.update_settings(settings)
        except (requests.RequestException, ValueError):
            self.status_label.setText("Cannot save settings. Check your connection.")
            return
        finally:
            self.save_button.setEnabled(True)
        if not response.ok:
            self.status_label.setText(
                self._response_error(response, "Settings could not be saved.")
            )
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            self.status_label.setText("Settings update returned an invalid response.")
            return
        if not self._valid_payload(payload):
            self.status_label.setText("Settings update returned an invalid response.")
            return
        self.current_settings = self._settings_only(payload)
        self._populate(self.current_settings)
        self.settings_updated.emit(self.current_settings.copy())
        self.status_label.setText("Settings saved.")

    def form_settings(self) -> dict:
        return {
            "notifications_enabled": self.notifications_enabled.isChecked(),
            "sound_enabled": self.sound_enabled.isChecked(),
            "sound_volume": self.volume_slider.value(),
            "reminder_interval_minutes": int(self.reminder_interval.currentData()),
        }

    def test_sound(self) -> None:
        if not self.notifications_enabled.isChecked() or not self.sound_enabled.isChecked():
            self.status_label.setText("Enable notifications and sound to test the alert.")
            return
        if self.volume_slider.value() == 0:
            self.status_label.setText("Increase the alert volume to test the sound.")
            return
        self.sound_player.play_preview(self.volume_slider.value())
        self.status_label.setText("Playing alert sound.")

    def load_privacy_consent(self) -> None:
        self.privacy_status_label.setText("Consent status: Loading...")
        try:
            response = APIClient.get_privacy_consent()
        except requests.RequestException:
            self.privacy_status_label.setText(
                "Consent status: Cannot load. Check your connection."
            )
            self.withdraw_privacy_button.setEnabled(False)
            return
        if not response.ok:
            self.privacy_status_label.setText("Consent status: Could not be loaded.")
            self.withdraw_privacy_button.setEnabled(False)
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            payload = None
        if not isinstance(payload, dict) or type(
            payload.get("has_current_consent")
        ) is not bool:
            self.privacy_status_label.setText("Consent status: Invalid response.")
            self.withdraw_privacy_button.setEnabled(False)
            return

        accepted = payload["has_current_consent"]
        self.withdraw_privacy_button.setEnabled(accepted)
        if accepted:
            accepted_at = payload.get("accepted_at") or "recorded"
            self.privacy_status_label.setText(
                f"Consent status: Accepted · {accepted_at}"
            )
        elif payload.get("withdrawn_at"):
            self.privacy_status_label.setText(
                f"Consent status: Withdrawn · {payload['withdrawn_at']}"
            )
        else:
            self.privacy_status_label.setText("Consent status: Not accepted")

    def review_privacy_notice(self) -> None:
        from app.ui.privacy_notice_dialog import PrivacyNoticeDialog

        PrivacyNoticeDialog(self, require_acceptance=False).exec()

    def withdraw_privacy_consent(self) -> None:
        answer = QMessageBox.question(
            self,
            "Withdraw camera consent",
            "Withdraw consent for future camera monitoring? Existing history "
            "will remain available.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.withdraw_privacy_button.setEnabled(False)
        try:
            response = APIClient.withdraw_privacy_consent()
        except requests.RequestException:
            self.privacy_status_label.setText(
                "Consent could not be withdrawn. Check your connection."
            )
            self.withdraw_privacy_button.setEnabled(True)
            return
        if not response.ok:
            self.privacy_status_label.setText(
                self._response_error(response, "Consent could not be withdrawn.")
            )
            self.withdraw_privacy_button.setEnabled(True)
            return
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            payload = None
        if not isinstance(payload, dict) or payload.get("has_current_consent") is not False:
            self.privacy_status_label.setText("Consent withdrawal was not confirmed.")
            self.withdraw_privacy_button.setEnabled(True)
            return
        self.privacy_status_label.setText("Consent status: Withdrawn")
        self.privacy_consent_changed.emit(False)

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
            return "Settings API is unavailable. Restart the PostGuard backend."
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError, TypeError):
            detail = None
        return str(detail) if detail else fallback
