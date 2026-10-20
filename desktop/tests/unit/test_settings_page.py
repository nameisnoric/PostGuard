import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.services.api_client import APIClient
from app.ui.pages.settings_page import SettingsPage


def response(data, status=200):
    return Mock(ok=status < 400, status_code=status, json=lambda: data)


class SettingsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.sound = Mock()
        self.page = SettingsPage(self.sound)
        self.addCleanup(self.page.deleteLater)
        self.settings = {
            "notifications_enabled": True,
            "sound_enabled": True,
            "sound_volume": 35,
            "reminder_interval_minutes": 10,
        }

    def test_load_populates_controls_and_emits_settings(self):
        updated = Mock()
        self.page.settings_updated.connect(updated)
        with patch.object(APIClient, "get_settings", return_value=response(self.settings)):
            self.page.load_settings()

        self.assertEqual(self.page.volume_slider.value(), 35)
        self.assertEqual(self.page.reminder_interval.currentData(), 10)
        updated.assert_called_once_with(self.settings)

    def test_save_persists_complete_payload(self):
        self.page.notifications_enabled.setChecked(True)
        self.page.sound_enabled.setChecked(False)
        self.page.volume_slider.setValue(25)
        self.page.reminder_interval.setCurrentIndex(
            self.page.reminder_interval.findData(15)
        )
        expected = self.page.form_settings()
        reply = {"user_id": 1, "updated_at": "now", **expected}

        with patch.object(
            APIClient, "update_settings", return_value=response(reply)
        ) as save:
            self.page.save_settings()

        save.assert_called_once_with(expected)
        self.assertEqual(self.page.status_label.text(), "บันทึกการตั้งค่าแล้ว")

    def test_save_explains_when_backend_has_no_settings_api(self):
        with patch.object(
            APIClient,
            "update_settings",
            return_value=response({"detail": "Not Found"}, status=404),
        ):
            self.page.save_settings()

        self.assertTrue(self.page.save_button.isEnabled())
        self.assertEqual(
            self.page.status_label.text(),
            "Settings API is unavailable. Restart the PostGuard backend.",
        )

    def test_test_sound_uses_current_slider_volume(self):
        self.page.notifications_enabled.setChecked(True)
        self.page.sound_enabled.setChecked(True)
        self.page.volume_slider.setValue(55)
        self.page.test_sound()
        self.sound.play_preview.assert_called_once_with(55)

    def test_privacy_status_and_withdrawal(self):
        accepted = {
            "notice_version": "2026-10-20",
            "accepted_version": "2026-10-20",
            "accepted_at": "2026-10-20T00:00:00+00:00",
            "withdrawn_at": None,
            "has_current_consent": True,
        }
        with patch.object(
            APIClient, "get_privacy_consent", return_value=response(accepted)
        ):
            self.page.load_privacy_consent()

        self.assertTrue(self.page.consent_action_button.isEnabled())
        self.assertEqual(self.page.consent_action_button.text(), "ยกเลิก Consent")
        changed = Mock()
        self.page.privacy_consent_changed.connect(changed)
        withdrawn = {**accepted, "has_current_consent": False, "withdrawn_at": "now"}
        with (
            patch(
                "PySide6.QtWidgets.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch.object(
                APIClient,
                "withdraw_privacy_consent",
                return_value=response(withdrawn),
            ) as withdraw,
        ):
            self.page.withdraw_privacy_consent()

        withdraw.assert_called_once_with()
        changed.assert_called_once_with(False)
        self.assertIn("ถอนแล้ว", self.page.privacy_status_label.text())
        self.assertTrue(self.page.consent_action_button.isEnabled())
        self.assertEqual(self.page.consent_action_button.text(), "ให้ Consent")

    def test_missing_privacy_consent_offers_consent_action(self):
        missing = {
            "notice_version": "2026-10-20",
            "accepted_version": None,
            "accepted_at": None,
            "withdrawn_at": None,
            "has_current_consent": False,
        }
        with patch.object(
            APIClient, "get_privacy_consent", return_value=response(missing)
        ):
            self.page.load_privacy_consent()

        self.assertTrue(self.page.consent_action_button.isEnabled())
        self.assertEqual(self.page.consent_action_button.text(), "ให้ Consent")

    def test_consent_action_updates_state_after_acceptance(self):
        self.page._set_privacy_consent_action(False)
        changed = Mock()
        self.page.privacy_consent_changed.connect(changed)
        dialog = Mock()
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        with patch(
            "app.ui.dialogs.privacy_notice_dialog.PrivacyNoticeDialog",
            return_value=dialog,
        ):
            self.page.handle_privacy_consent_action()

        self.assertTrue(self.page.has_privacy_consent)
        self.assertEqual(self.page.consent_action_button.text(), "ยกเลิก Consent")
        changed.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
