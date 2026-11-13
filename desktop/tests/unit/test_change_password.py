import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.services.api_client import APIClient
from app.ui.dialogs.change_password_dialog import ChangePasswordDialog


def response(data=None, status=200):
    return Mock(ok=status < 400, status_code=status, json=lambda: data or {})


class ChangePasswordDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = ChangePasswordDialog()
        self.addCleanup(self.dialog.deleteLater)

    def fill(self, current="OldPass123!", new="NewPass456!", confirm="NewPass456!"):
        self.dialog.current_password_input.setText(current)
        self.dialog.new_password_input.setText(new)
        self.dialog.confirm_password_input.setText(confirm)

    def test_weak_password_lists_specific_missing_rules(self):
        self.fill(new="weak", confirm="weak")
        with patch.object(APIClient, "change_password") as change:
            self.dialog.submit()
        change.assert_not_called()
        message = self.dialog.status_label.text()
        self.assertIn("พิมพ์ใหญ่", message)
        self.assertIn("ตัวเลข", message)
        self.assertIn("อักขระพิเศษ", message)

    def test_success_uses_authenticated_password_endpoint(self):
        self.fill()
        with patch(
            "app.ui.dialogs.change_password_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "app.ui.dialogs.change_password_dialog.QMessageBox.information"
        ), patch.object(
            APIClient, "change_password", return_value=response({"message": "changed"})
        ) as change:
            self.dialog.submit()
        change.assert_called_once_with("OldPass123!", "NewPass456!")
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)

    def test_backend_error_is_translated(self):
        self.fill()
        with patch(
            "app.ui.dialogs.change_password_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch.object(
            APIClient,
            "change_password",
            return_value=response({"detail": "Current password is incorrect."}, 400),
        ):
            self.dialog.submit()
        self.assertEqual(self.dialog.status_label.text(), "รหัสผ่านปัจจุบันไม่ถูกต้อง")


if __name__ == "__main__":
    unittest.main()
