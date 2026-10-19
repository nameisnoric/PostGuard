"""Email delivery helpers must send OTPs only to the requested account."""

import unittest
from unittest.mock import patch

from app.services.email_service import (
    RESEND_FROM_EMAIL,
    send_password_reset_otp,
    send_registration_otp,
)


class EmailServiceTests(unittest.TestCase):
    def test_password_reset_uses_requested_recipient(self):
        with patch("app.services.email_service.resend.Emails.send") as send:
            send_password_reset_otp("student@ku.th", "123456")

        params = send.call_args.args[0]
        self.assertEqual(params["from"], RESEND_FROM_EMAIL)
        self.assertEqual(params["to"], ["student@ku.th"])
        self.assertIn("123456", params["html"])
        self.assertNotIn("123456", params["subject"])

    def test_registration_uses_requested_recipient(self):
        with patch("app.services.email_service.resend.Emails.send") as send:
            send_registration_otp("new.student@ku.th", "654321")

        params = send.call_args.args[0]
        self.assertEqual(params["from"], RESEND_FROM_EMAIL)
        self.assertEqual(params["to"], ["new.student@ku.th"])
        self.assertIn("654321", params["html"])
        self.assertNotIn("654321", params["subject"])


if __name__ == "__main__":
    unittest.main()
