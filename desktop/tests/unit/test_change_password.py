import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.services.api_client import APIClient
from app.ui.dialogs.change_password_dialog import ChangePasswordDialog


def response(data=None, status=200):
    return Mock(
        ok=status < 400,
        status_code=status,
        json=lambda: data or {},
    )


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

    def test_fields_are_masked_and_validation_stays_local(self):
        for field in (
            self.dialog.current_password_input,
            self.dialog.new_password_input,
            self.dialog.confirm_password_input,
        ):
            self.assertEqual(field.echoMode(), field.EchoMode.Password)

        for values in (
            ("", "NewPass456!", "NewPass456!"),
            ("OldPass123!", "NewPass456!", "different"),
            ("OldPass123!", "weak", "weak"),
            ("OldPass123!", "OldPass123!", "OldPass123!"),
        ):
            with self.subTest(values=values), patch.object(
                APIClient, "change_password"
            ) as change:
                self.fill(*values)
                self.dialog.submit()
                change.assert_not_called()

    def test_confirmation_then_success_accepts_dialog(self):
        self.fill()
        with patch(
            "app.ui.dialogs.change_password_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "app.ui.dialogs.change_password_dialog.QMessageBox.information"
        ), patch.object(
            APIClient,
            "change_password",
            return_value=response({"message": "changed"}),
        ) as change:
            self.dialog.submit()

        change.assert_called_once_with("OldPass123!", "NewPass456!")
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.dialog.current_password_input.text(), "")

    def test_backend_error_keeps_dialog_open(self):
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

        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(
            self.dialog.status_label.text(), "Current password is incorrect."
        )

    def test_api_contract(self):
        with patch.object(APIClient, "put") as put:
            APIClient.change_password("old", "new")
        put.assert_called_once_with(
            "/users/me/password",
            {"current_password": "old", "new_password": "new"},
        )


if __name__ == "__main__":
    unittest.main()
