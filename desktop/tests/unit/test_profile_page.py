import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

from app.ui.pages.profile_page import ProfilePage, ProfileSaveConfirmationDialog


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
        self.assertEqual(self.page.display_name_input.text(), "jlee")
        self.assertEqual(self.page.avatar_label.text(), "JL")

    def test_save_updates_session_state_and_emits_profile(self):
        updated = Mock()
        self.page.profile_updated.connect(updated)
        self.page.first_name_input.setText("Jane")
        self.page.last_name_input.setText("Doe")
        self.page.display_name_input.setText("Jane D")

        self.page.save_changes()

        updated.assert_called_once_with({
            "full_name": "Jane Doe",
            "display_name": "Jane D",
            "avatar_path": None,
        })
        self.assertIn("app session", self.page.status_label.text())

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
        with patch.object(
            ProfileSaveConfirmationDialog,
            "exec",
            return_value=QDialog.DialogCode.Accepted,
        ):
            self.page.save_button.click()
        self.assertEqual(self.page.user_data["full_name"], "Jane Lee")

    def test_required_fields_are_validated(self):
        self.page.first_name_input.clear()
        self.page.save_changes()
        self.assertIn("required", self.page.status_label.text())

    def test_selected_photo_is_uploaded_through_authenticated_api(self):
        self.page.selected_photo_path = "selected.jpg"
        reply = Mock(ok=True, json=lambda: {"avatar_path": "users/1/private.webp"})
        with patch("app.ui.pages.profile_page.APIClient.upload_avatar", return_value=reply) as upload:
            self.page.save_changes()
        upload.assert_called_once_with("selected.jpg")
        self.assertEqual(self.page.user_data["avatar_path"], "users/1/private.webp")
        self.assertIn("privately", self.page.status_label.text())

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


if __name__ == "__main__":
    unittest.main()
