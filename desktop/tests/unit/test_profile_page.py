import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

from app.services.api_client import APIClient
from app.ui.pages.profile_page import (
    AccountDeletionConfirmationDialog,
    ProfilePage,
    ProfileSaveConfirmationDialog,
)


class ProfilePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = ProfilePage({
            "username": "jlee",
            "full_name": "Jordan Lee",
        })
        self.addCleanup(self.page.deleteLater)

    def test_existing_user_data_populates_figma_fields(self):
        self.assertEqual(self.page.first_name_input.text(), "Jordan")
        self.assertEqual(self.page.last_name_input.text(), "Lee")
        self.assertEqual(self.page.username_input.text(), "jlee")
        self.assertEqual(self.page.avatar_label.text(), "JL")

    def test_delete_account_is_a_separate_visible_action_card(self):
        self.assertEqual(self.page.danger_card.property("variant"), "dangerZone")
        self.assertEqual(self.page.delete_account_button.text(), "Delete Account")
        self.assertEqual(self.page.delete_account_button.property("variant"), "danger")

    def test_save_persists_profile_and_emits_backend_values(self):
        updated = Mock()
        self.page.profile_updated.connect(updated)
        self.page.first_name_input.setText("Jane")
        self.page.last_name_input.setText("Doe")
        self.page.username_input.setText("janed")
        reply = Mock(ok=True, json=lambda: {
            "username": "janed",
            "full_name": "Jane Doe",
            "avatar_path": None,
        })

        with patch(
            "app.ui.pages.profile_page.APIClient.update_profile",
            return_value=reply,
        ) as update_profile:
            self.page.save_changes()

        update_profile.assert_called_once_with("janed", "Jane Doe")
        updated.assert_called_once_with({
            "username": "janed",
            "full_name": "Jane Doe",
            "avatar_path": None,
        })
        self.assertEqual(self.page.status_label.text(), "บันทึกข้อมูลโปรไฟล์แล้ว")

    def test_keep_editing_does_not_apply_changes(self):
        self.page.first_name_input.setText("Temporary")
        with patch.object(
            ProfileSaveConfirmationDialog,
            "exec",
            return_value=QDialog.DialogCode.Rejected,
        ):
            self.page.save_button.click()
        self.assertEqual(self.page.user_data["full_name"], "Jordan Lee")
        self.assertEqual(self.page.first_name_input.text(), "Temporary")

    def test_confirming_from_save_button_applies_changes(self):
        self.page.first_name_input.setText("Jane")
        reply = Mock(ok=True, json=lambda: {
            "username": "jlee",
            "full_name": "Jane Lee",
            "avatar_path": None,
        })
        with patch.object(
            ProfileSaveConfirmationDialog,
            "exec",
            return_value=QDialog.DialogCode.Accepted,
        ), patch(
            "app.ui.pages.profile_page.APIClient.update_profile",
            return_value=reply,
        ):
            self.page.save_button.click()
        self.assertEqual(self.page.user_data["full_name"], "Jane Lee")

    def test_duplicate_username_error_does_not_change_profile(self):
        self.page.username_input.setText("already-used")
        reply = Mock(
            ok=False,
            status_code=409,
            json=lambda: {"detail": "Username is already in use."},
        )

        with patch(
            "app.ui.pages.profile_page.APIClient.update_profile",
            return_value=reply,
        ):
            self.page.save_changes()

        self.assertEqual(self.page.user_data["username"], "jlee")
        self.assertEqual(self.page.status_label.text(), "Username is already in use.")

    def test_api_client_sends_profile_update_to_authenticated_endpoint(self):
        with patch.object(APIClient, "patch") as send:
            APIClient.update_profile("janed", "Jane Doe")

        send.assert_called_once_with(
            "/users/me",
            {"username": "janed", "full_name": "Jane Doe"},
        )

    def test_required_fields_are_validated(self):
        self.page.first_name_input.clear()
        self.page.save_changes()
        self.assertIn("ต้องกรอก", self.page.status_label.text())

    def test_selected_photo_is_uploaded_through_authenticated_api(self):
        self.page.selected_photo_path = "selected.jpg"
        reply = Mock(ok=True, json=lambda: {"avatar_path": "users/1/private.webp"})
        with patch("app.ui.pages.profile_page.APIClient.upload_avatar", return_value=reply) as upload:
            self.page.save_changes()
        upload.assert_called_once_with("selected.jpg")
        self.assertEqual(self.page.user_data["avatar_path"], "users/1/private.webp")
        self.assertIn("แบบส่วนตัว", self.page.status_label.text())

    def test_stored_photo_can_be_removed_through_authenticated_api(self):
        self.page.user_data["avatar_path"] = "users/1/private.webp"
        self.page.remove_photo_button.setEnabled(True)
        updated = Mock()
        self.page.profile_updated.connect(updated)
        reply = Mock(ok=True, status_code=204)

        with patch("app.ui.pages.profile_page.APIClient.delete_avatar", return_value=reply) as remove:
            self.page.remove_photo()

        remove.assert_called_once_with()
        self.assertIsNone(self.page.user_data["avatar_path"])
        self.assertEqual(self.page.avatar_label.text(), "JL")
        updated.assert_called_once_with({"avatar_path": None})

    def test_account_deletion_requires_confirmation_before_signal(self):
        requested = Mock()
        self.page.account_deletion_requested.connect(requested)
        with patch.object(
            AccountDeletionConfirmationDialog,
            "exec",
            side_effect=(QDialog.DialogCode.Rejected, QDialog.DialogCode.Accepted),
        ):
            self.page.delete_account_button.click()
            requested.assert_not_called()
            self.page.delete_account_button.click()
            requested.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
