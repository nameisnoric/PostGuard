import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import requests
from PySide6.QtWidgets import QApplication, QDialog
from app.services.api_client import APIClient
from app.core.token_store import TokenStore
from app.ui.password_reset_dialog import PasswordResetDialog


def response(data, status=200):
    return Mock(status_code=status, json=lambda: data)


class PasswordResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = PasswordResetDialog(email="test@ku.th")
        self.addCleanup(self.dialog.deleteLater)

    def request(self):
        with patch.object(APIClient, "request_password_reset", return_value=response({"message": "sent"})):
            self.dialog.request_code()

    def verify(self):
        self.request()
        self.dialog.otp_input.setText("123456")
        with patch.object(APIClient, "verify_reset_otp", return_value=response({"reset_token": "reset-only-token"})):
            self.dialog.verify_code()

    def test_complete_flow_keeps_reset_token_out_of_login_store(self):
        TokenStore.clear_token()
        self.verify()
        self.assertEqual(self.dialog.pages.currentIndex(), 2)
        self.assertIsNone(TokenStore.get_token())
        self.dialog.password_input.setText("NewPass123!")
        self.dialog.confirm_input.setText("NewPass123!")
        with patch.object(APIClient, "reset_password", return_value=response({"message": "changed"})) as reset, patch("PySide6.QtWidgets.QMessageBox.information"):
            self.dialog.save_password()
        reset.assert_called_once_with("reset-only-token", "NewPass123!")
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNone(self.dialog._reset_token)
        self.assertEqual(self.dialog.password_input.text(), "")

    def test_invalid_email_and_otp_do_not_send_requests(self):
        self.dialog.email_input.setText("invalid@example.com")
        with patch.object(APIClient, "request_password_reset") as send:
            self.dialog.request_code()
            send.assert_not_called()
        self.dialog.email_input.setText("test@ku.th")
        self.request()
        self.dialog.otp_input.setText("12abcd")
        with patch.object(APIClient, "verify_reset_otp") as verify:
            self.dialog.verify_code()
            verify.assert_not_called()

    def test_bad_or_expired_otp_stays_on_verification(self):
        self.request()
        self.dialog.otp_input.setText("123456")
        with patch.object(APIClient, "verify_reset_otp", return_value=response({}, 400)):
            self.dialog.verify_code()
        self.assertEqual(self.dialog.pages.currentIndex(), 1)
        self.assertIsNone(self.dialog._reset_token)

    def test_password_validation(self):
        self.verify()
        for password, confirmation in (("weak", "weak"), ("NewPass123!", "different")):
            self.dialog.password_input.setText(password)
            self.dialog.confirm_input.setText(confirmation)
            with patch.object(APIClient, "reset_password") as reset:
                self.dialog.save_password()
                reset.assert_not_called()

    def test_expired_reset_token_requires_new_code(self):
        self.verify()
        self.dialog.password_input.setText("NewPass123!")
        self.dialog.confirm_input.setText("NewPass123!")
        with patch.object(APIClient, "reset_password", return_value=response({}, 401)):
            self.dialog.save_password()
        self.assertIsNone(self.dialog._reset_token)
        self.assertEqual(self.dialog.pages.currentIndex(), 1)
        self.assertEqual(self.dialog.password_input.text(), "")

    def test_network_error_allows_retry_and_does_not_claim_success(self):
        with patch.object(APIClient, "request_password_reset", side_effect=requests.Timeout()):
            self.dialog.request_code()
        self.assertTrue(self.dialog.pages.isEnabled())
        self.assertEqual(self.dialog.pages.currentIndex(), 0)
        self.assertIn("Cannot confirm", self.dialog.status_label.text())

    def test_malformed_verification_response_and_resend(self):
        self.request()
        self.dialog.otp_input.setText("123456")
        with patch.object(APIClient, "verify_reset_otp", return_value=response([])):
            self.dialog.verify_code()
        self.assertIsNone(self.dialog._reset_token)
        self.request()
        self.assertEqual(self.dialog.otp_input.text(), "")

    def test_cancel_and_change_email_clear_credentials(self):
        self.verify()
        self.dialog.change_email()
        self.assertIsNone(self.dialog._reset_token)
        self.assertEqual(self.dialog.pages.currentIndex(), 0)
        self.verify()
        self.dialog.reject()
        self.assertIsNone(self.dialog._reset_token)

    def test_api_paths_and_payloads(self):
        with patch.object(APIClient, "post") as post:
            APIClient.request_password_reset("test@ku.th")
            post.assert_called_with("/auth/forgot-password", {"email": "test@ku.th"})
            APIClient.verify_reset_otp("test@ku.th", "123456")
            post.assert_called_with("/auth/verify-reset-otp", {"email": "test@ku.th", "otp": "123456"})
            APIClient.reset_password("token", "NewPass123!")
            post.assert_called_with("/auth/reset_password", {"reset_token": "token", "new_password": "NewPass123!"})


if __name__ == "__main__":
    unittest.main()
