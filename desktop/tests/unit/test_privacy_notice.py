import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

from app.services.api_client import APIClient
from app.ui.privacy_notice_dialog import (
    PRIVACY_NOTICE_VERSION,
    PrivacyNoticeDialog,
)


def response(data, status=200):
    return Mock(ok=status < 400, status_code=status, json=lambda: data)


class PrivacyNoticeDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = PrivacyNoticeDialog(require_acceptance=True)
        self.addCleanup(self.dialog.deleteLater)

    def test_accept_button_requires_explicit_checkbox(self):
        self.assertFalse(self.dialog.accept_button.isEnabled())
        self.dialog.accept_checkbox.setChecked(True)
        self.assertTrue(self.dialog.accept_button.isEnabled())

    def test_acceptance_is_saved_before_dialog_completes(self):
        self.dialog.accept_checkbox.setChecked(True)
        payload = {
            "notice_version": PRIVACY_NOTICE_VERSION,
            "accepted_version": PRIVACY_NOTICE_VERSION,
            "accepted_at": "2026-10-20T00:00:00+00:00",
            "withdrawn_at": None,
            "has_current_consent": True,
        }
        with patch.object(
            APIClient,
            "accept_privacy_consent",
            return_value=response(payload),
        ) as accept:
            self.dialog.accept_consent()

        accept.assert_called_once_with(PRIVACY_NOTICE_VERSION)
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)


if __name__ == "__main__":
    unittest.main()
