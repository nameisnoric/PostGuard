import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.api_client import APIClient
from app.ui.windows.otp_window import OTPWindow
from app.ui.windows.register_window import RegisterWindow


def response(data, status=200):
    return Mock(status_code=status, json=lambda: data)


class RegistrationUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = RegisterWindow()
        self.addCleanup(self.window.deleteLater)
        self.window.full_name_input.setText("PostGuard Student")
        self.window.username_input.setText("postguard.student")
        self.window.email_input.setText("student@ku.th")
        self.window.password_input.setText("StrongPass123!")

    def test_confirm_password_is_present_and_masked(self):
        self.assertEqual(
            self.window.confirm_password_input.placeholderText(),
            "ยืนยันรหัสผ่าน",
        )
        self.assertEqual(
            self.window.confirm_password_input.echoMode(),
            self.window.password_input.echoMode(),
        )

    def test_mismatched_confirmation_does_not_request_otp(self):
        self.window.confirm_password_input.setText("DifferentPass123!")

        with (
            patch.object(APIClient, "request_register_otp") as request_otp,
            patch.object(self.window, "show_error") as show_error,
        ):
            self.window.handle_register()

        request_otp.assert_not_called()
        show_error.assert_called_once_with(
            "Password and confirmation do not match."
        )
        self.assertEqual(self.window.confirm_password_input.text(), "")

    def test_matching_confirmation_requests_otp_without_duplicate_password(self):
        self.window.confirm_password_input.setText("StrongPass123!")
        otp_window = Mock()

        with (
            patch.object(
                APIClient,
                "request_register_otp",
                return_value=response({"message": "sent"}),
            ) as request_otp,
            patch("app.ui.windows.otp_window.OTPWindow", return_value=otp_window),
        ):
            self.window.handle_register()

        request_otp.assert_called_once_with(
            email="student@ku.th",
            username="postguard.student",
            password="StrongPass123!",
            full_name="PostGuard Student",
        )
        otp_window.show.assert_called_once_with()

    def test_otp_window_uses_shared_theme_and_primary_action(self):
        otp_window = OTPWindow("student@ku.th")
        self.addCleanup(otp_window.deleteLater)

        self.assertEqual(otp_window.objectName(), "authWindow")
        self.assertTrue(otp_window.card.property("card"))
        self.assertEqual(otp_window.verify_button.property("variant"), "primary")
        self.assertEqual(otp_window.email_label.text(), "student@ku.th")


if __name__ == "__main__":
    unittest.main()
