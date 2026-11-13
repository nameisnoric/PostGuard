import unittest

from app.ui.utils.auth_validation import (
    email_validation_errors,
    password_validation_errors,
    validation_message,
)


class AuthValidationTests(unittest.TestCase):
    def test_ku_email_validation(self):
        self.assertEqual(email_validation_errors("student@ku.th"), [])
        self.assertEqual(email_validation_errors("STUDENT@KU.TH"), [])
        self.assertTrue(email_validation_errors("student@example.com"))
        self.assertTrue(email_validation_errors(""))

    def test_password_reports_every_missing_rule(self):
        errors = password_validation_errors("weak")
        self.assertEqual(len(errors), 4)
        self.assertTrue(any("8" in error for error in errors))
        self.assertTrue(any("พิมพ์ใหญ่" in error for error in errors))
        self.assertTrue(any("ตัวเลข" in error for error in errors))
        self.assertTrue(any("อักขระพิเศษ" in error for error in errors))
        self.assertEqual(password_validation_errors("StrongPass1!"), [])

    def test_validation_message_uses_readable_bullets(self):
        message = validation_message("ข้อมูลไม่ถูกต้อง:", ["ข้อแรก", "ข้อสอง"])
        self.assertIn("• ข้อแรก", message)
        self.assertIn("• ข้อสอง", message)


if __name__ == "__main__":
    unittest.main()
