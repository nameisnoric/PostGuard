"""Restricted account recovery window tests."""

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.token_store import TokenStore
from app.services.api_client import APIClient
from app.ui.account_recovery_window import AccountRecoveryWindow


def response(data, status=200):
    return Mock(ok=status < 400, status_code=status, json=lambda: data)


class AccountRecoveryWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.pending = {
            "id": 1,
            "account_status": "PENDING_DELETION",
            "deletion_scheduled_for": (
                datetime.now(timezone.utc) + timedelta(days=14)
            ).isoformat(),
        }
        self.window = AccountRecoveryWindow(self.pending)
        self.addCleanup(self.window.deleteLater)

    def test_recover_reactivates_account_and_opens_main_window(self):
        active = {
            "id": 1,
            "username": "test",
            "account_status": "ACTIVE",
            "deletion_scheduled_for": None,
        }
        with patch.object(
            APIClient, "cancel_account_deletion", return_value=response(active)
        ) as recover, patch(
            "app.ui.main_window.MainWindow"
        ) as main_window, patch("PySide6.QtWidgets.QMessageBox.information"):
            self.window.recover_account()

        recover.assert_called_once_with()
        main_window.assert_called_once_with(active)
        main_window.return_value.show.assert_called_once_with()

    def test_expired_recovery_period_disables_recovery(self):
        expired = dict(self.pending)
        expired["deletion_scheduled_for"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        window = AccountRecoveryWindow(expired)
        self.addCleanup(window.deleteLater)

        self.assertFalse(window.recover_button.isEnabled())
        self.assertIn("ended", window.status_label.text())

    def test_back_to_login_clears_token(self):
        TokenStore.set_token("token")
        with patch("app.ui.login_window.LoginWindow") as login:
            self.window.back_to_login()
        self.assertIsNone(TokenStore.get_token())
        login.return_value.show.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
