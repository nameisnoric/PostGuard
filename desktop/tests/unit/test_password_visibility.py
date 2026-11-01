import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit

from app.ui.dialogs.change_password_dialog import ChangePasswordDialog
from app.ui.dialogs.password_reset_dialog import PasswordResetDialog
from app.ui.utils.password_visibility import attach_password_visibility
from app.ui.windows.login_window import LoginWindow
from app.ui.windows.register_window import RegisterWindow


class PasswordVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_action_toggles_field_and_accessible_label(self):
        field = QLineEdit()
        self.addCleanup(field.deleteLater)
        action = attach_password_visibility(field)

        self.assertEqual(field.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(action.text(), "แสดงรหัสผ่าน")

        action.trigger()
        self.assertEqual(field.echoMode(), QLineEdit.EchoMode.Normal)
        self.assertEqual(action.text(), "ซ่อนรหัสผ่าน")

        action.trigger()
        self.assertEqual(field.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(action.text(), "แสดงรหัสผ่าน")

    def test_every_password_entry_has_visibility_action(self):
        widgets = [
            LoginWindow(),
            RegisterWindow(),
            PasswordResetDialog(email="student@ku.th"),
            ChangePasswordDialog(),
        ]
        for widget in widgets:
            self.addCleanup(widget.deleteLater)

        fields = [
            widgets[0].password_input,
            widgets[1].password_input,
            widgets[1].confirm_password_input,
            widgets[2].password_input,
            widgets[2].confirm_input,
            widgets[3].current_password_input,
            widgets[3].new_password_input,
            widgets[3].confirm_password_input,
        ]
        for field in fields:
            with self.subTest(placeholder=field.placeholderText()):
                self.assertEqual(field.echoMode(), QLineEdit.EchoMode.Password)
                self.assertIsNotNone(field.password_visibility_action)
                self.assertTrue(field.password_visibility_action.isCheckable())


if __name__ == "__main__":
    unittest.main()
