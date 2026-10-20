"""Profile UI with authenticated private avatar storage."""

from pathlib import Path

import requests

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.services.api_client import APIClient


class ProfileSaveConfirmationDialog(QDialog):
    """Confirm profile changes before any upload or session update occurs."""

    def __init__(self, changes: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle('PostGuard - ยืนยันการแก้ไขโปรไฟล์')
        self.setModal(True)
        self.setFixedWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(16)

        heading = QLabel("ยืนยันการบันทึกโปรไฟล์?")
        heading.setProperty("role", "title")
        message = QLabel(
            "Please review the changes below. Your photo stays private and is "
            "available only through your signed-in account."
        )
        message.setProperty("role", "muted")
        message.setWordWrap(True)

        summary = QFrame()
        summary.setProperty("card", True)
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(8)
        for change in changes:
            item = QLabel(f"•  {change}")
            item.setWordWrap(True)
            summary_layout.addWidget(item)

        buttons = QHBoxLayout()
        buttons.addStretch()
        keep_editing = QPushButton("แก้ไขต่อ")
        keep_editing.clicked.connect(self.reject)
        confirm = QPushButton("บันทึกการเปลี่ยนแปลง")
        confirm.setProperty("variant", "primary")
        confirm.clicked.connect(self.accept)
        confirm.setDefault(True)
        buttons.addWidget(keep_editing)
        buttons.addWidget(confirm)

        layout.addWidget(heading)
        layout.addWidget(message)
        layout.addWidget(summary)
        layout.addLayout(buttons)


class ProfilePage(QWidget):
    profile_updated = Signal(dict)

    def __init__(self, user_data: dict):
        super().__init__()
        self.setProperty("page", True)
        self.user_data = user_data.copy()
        self.selected_photo_path = None

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page_layout.addWidget(scroll)

        content = QWidget()
        content.setProperty("page", True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(48, 28, 48, 40)
        layout.setSpacing(16)
        scroll.setWidget(content)

        title = QLabel("Profile")
        title.setProperty("role", "title")
        subtitle = QLabel("จัดการรูปโปรไฟล์และข้อมูลส่วนตัวของคุณ")
        subtitle.setProperty("role", "muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card_row = QHBoxLayout()
        card_row.addStretch()
        card = QFrame()
        card.setProperty("card", True)
        card.setMaximumWidth(1048)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(18)

        photo_title = QLabel("รูปโปรไฟล์")
        photo_title.setProperty("role", "heading")
        card_layout.addWidget(photo_title)

        photo_row = QHBoxLayout()
        photo_row.setSpacing(16)
        self.avatar_label = QLabel()
        self.avatar_label.setObjectName("profileAvatar")
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setFixedSize(96, 96)
        photo_row.addWidget(self.avatar_label)

        photo_actions = QVBoxLayout()
        photo_buttons = QHBoxLayout()
        self.change_photo_button = QPushButton("เปลี่ยนรูป")
        self.change_photo_button.clicked.connect(self.choose_photo)
        self.remove_photo_button = QPushButton("ลบรูป")
        self.remove_photo_button.clicked.connect(self.remove_photo)
        photo_buttons.addWidget(self.change_photo_button)
        photo_buttons.addWidget(self.remove_photo_button)
        photo_note = QLabel('รองรับ JPG หรือ PNG ขนาดไม่เกิน 5 MB แนะนำ 400 x 400 พิกเซล')
        photo_note.setProperty("role", "muted")
        photo_actions.addStretch()
        photo_actions.addLayout(photo_buttons)
        photo_actions.addWidget(photo_note)
        photo_actions.addStretch()
        photo_row.addLayout(photo_actions)
        photo_row.addStretch()
        card_layout.addLayout(photo_row)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("divider")
        card_layout.addWidget(divider)

        personal_title = QLabel("ข้อมูลส่วนตัว")
        personal_title.setProperty("role", "heading")
        card_layout.addWidget(personal_title)

        fields = QGridLayout()
        fields.setHorizontalSpacing(16)
        fields.setVerticalSpacing(8)
        self.first_name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.username_input = QLineEdit()
        fields.addWidget(QLabel("ชื่อ"), 0, 0)
        fields.addWidget(QLabel("นามสกุล"), 0, 1)
        fields.addWidget(self.first_name_input, 1, 0)
        fields.addWidget(self.last_name_input, 1, 1)
        fields.addWidget(QLabel("ชื่อผู้ใช้"), 2, 0, 1, 2)
        fields.addWidget(self.username_input, 3, 0, 1, 2)
        fields.setColumnStretch(0, 1)
        fields.setColumnStretch(1, 1)
        card_layout.addLayout(fields)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        card_layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.save_button = QPushButton("บันทึกการเปลี่ยนแปลง")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self.request_save_changes)
        actions.addWidget(self.save_button)
        actions.addStretch()
        card_layout.addLayout(actions)

        card_row.addWidget(card, 1)
        card_row.addStretch()
        layout.addLayout(card_row)

        layout.addStretch()

        self.reset_form()

    @staticmethod
    def _split_name(full_name: str) -> tuple[str, str]:
        parts = str(full_name or "").strip().split(maxsplit=1)
        return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")

    def _initials(self) -> str:
        name = self.user_data.get("full_name") or self.user_data.get("username") or "U"
        words = str(name).split()
        return "".join(word[0].upper() for word in words[:2]) or "U"

    def _set_avatar_pixmap(self, source: QPixmap | None) -> None:
        if source is None or source.isNull():
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setText(self._initials())
            return
        size = self.avatar_label.size()
        scaled = source.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - size.width()) // 2)
        y = max(0, (scaled.height() - size.height()) // 2)
        cropped = scaled.copy(x, y, size.width(), size.height())
        circle = QPixmap(size)
        circle.fill(Qt.GlobalColor.transparent)
        painter = QPainter(circle)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addEllipse(0, 0, size.width(), size.height())
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.avatar_label.setText("")
        self.avatar_label.setPixmap(circle)

    def load_private_avatar(self) -> None:
        try:
            response = APIClient.get_avatar()
        except requests.RequestException:
            self._set_avatar_pixmap(None)
            self.status_label.setText('ไม่สามารถโหลดรูปโปรไฟล์ได้')
            return
        if response.status_code == 404:
            self._set_avatar_pixmap(None)
            return
        if not response.ok:
            self._set_avatar_pixmap(None)
            self.status_label.setText('ไม่สามารถโหลดรูปโปรไฟล์ได้')
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(response.content):
            self._set_avatar_pixmap(None)
            self.status_label.setText('ข้อมูลรูปโปรไฟล์ไม่ถูกต้อง')
            return
        self._set_avatar_pixmap(pixmap)

    def choose_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose profile photo",
            "",
            "Images (*.jpg *.jpeg *.png)",
        )
        if not path:
            return
        file_path = Path(path)

        if file_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            self.status_label.setText('โปรดเลือกรูป JPG หรือ PNG')
            return
        try:
            if file_path.stat().st_size > 5 * 1024 * 1024:
                self.status_label.setText('รูปที่เลือกมีขนาดเกิน 5 MB')
                return

        except OSError:
            self.status_label.setText('ไม่สามารถเปิดรูปที่เลือกได้')
            return
        preview = QPixmap(path)

        if preview.isNull():
            self.status_label.setText('ไฟล์ที่เลือกไม่ใช่รูปภาพที่อ่านได้')
            return
        self.selected_photo_path = path
        self._set_avatar_pixmap(preview)
        self.remove_photo_button.setEnabled(True)
        self.status_label.setText('เลือกรูปแล้ว กดบันทึกการเปลี่ยนแปลงเพื่ออัปโหลดแบบส่วนตัว')

    def remove_photo(self) -> None:
        """Remove the signed-in user's stored avatar and restore initials."""
        has_stored_avatar = bool(self.user_data.get("avatar_path"))
        if has_stored_avatar:
            self.remove_photo_button.setEnabled(False)
            self.status_label.setText('กำลังลบรูปโปรไฟล์ส่วนตัว...')
            QApplication.processEvents()
            try:
                response = APIClient.delete_avatar()
            except requests.RequestException:
                self.remove_photo_button.setEnabled(True)
                self.status_label.setText(
                    "Cannot remove the profile photo. Check your connection."
                )
                return
            if not response.ok and response.status_code != 404:
                self.remove_photo_button.setEnabled(True)
                self.status_label.setText("Profile photo could not be removed.")
                return

        self.selected_photo_path = None
        self.user_data["avatar_path"] = None
        self._set_avatar_pixmap(None)
        self.remove_photo_button.setEnabled(False)
        self.status_label.setText('ลบรูปโปรไฟล์แล้ว')
        self.profile_updated.emit({"avatar_path": None})

    def reset_form(self) -> None:
        first, last = self._split_name(self.user_data.get("full_name"))
        self.first_name_input.setText(first)
        self.last_name_input.setText(last)
        self.username_input.setText(self.user_data.get("username") or "")
        self.selected_photo_path = None
        self.status_label.clear()
        if self.user_data.get("avatar_path"):
            self.load_private_avatar()
        else:
            self._set_avatar_pixmap(None)
        self.remove_photo_button.setEnabled(bool(self.user_data.get("avatar_path")))

    def request_save_changes(self) -> None:
        """Validate and ask for confirmation before applying profile changes."""
        first = self.first_name_input.text().strip()
        last = self.last_name_input.text().strip()
        username = self.username_input.text().strip()
        if not first or not username:
            self.status_label.setText('ต้องกรอกชื่อและชื่อผู้ใช้')
            return

        full_name = " ".join(part for part in (first, last) if part)
        changes = []
        if full_name != str(self.user_data.get("full_name") or ""):
            changes.append("Your first and last name will be saved to your account.")
        if username != str(self.user_data.get("username") or ""):
            changes.append("Your username will be saved to your account.")
        if self.selected_photo_path:
            changes.append("Your new profile photo will be uploaded to private storage.")

        if not changes:
            self.status_label.setText('ไม่มีการเปลี่ยนแปลงโปรไฟล์ให้บันทึก')
            return

        dialog = ProfileSaveConfirmationDialog(changes, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.save_changes()

    def save_changes(self) -> None:
        first = self.first_name_input.text().strip()
        last = self.last_name_input.text().strip()
        username = self.username_input.text().strip()
        if not first or not username:
            self.status_label.setText('ต้องกรอกชื่อและชื่อผู้ใช้')
            return

        full_name = " ".join(part for part in (first, last) if part)
        profile_changed = (
            username != str(self.user_data.get("username") or "")
            or full_name != str(self.user_data.get("full_name") or "")
        )
        if not profile_changed and not self.selected_photo_path:
            self.status_label.setText('ไม่มีการเปลี่ยนแปลงโปรไฟล์ให้บันทึก')
            return

        avatar_path = self.user_data.get("avatar_path")
        profile_saved = False
        photo_uploaded = False
        self.save_button.setEnabled(False)
        QApplication.processEvents()
        try:
            if profile_changed:
                self.status_label.setText('กำลังบันทึกข้อมูลโปรไฟล์...')
                QApplication.processEvents()
                try:
                    response = APIClient.update_profile(username, full_name)
                except requests.RequestException:
                    self.status_label.setText(
                        "Cannot save profile information. Check your connection."
                    )
                    return
                if not response.ok:
                    self.status_label.setText(self._response_detail(
                        response, "Profile information could not be saved."
                    ))
                    return
                try:
                    payload = response.json()
                except (ValueError, AttributeError):
                    self.status_label.setText("Profile update returned an invalid response.")
                    return
                saved_username = payload.get("username")
                saved_full_name = payload.get("full_name")
                if not isinstance(saved_username, str) or not isinstance(saved_full_name, str):
                    self.status_label.setText("Profile update returned an invalid response.")
                    return
                username = saved_username
                full_name = saved_full_name
                avatar_path = payload.get("avatar_path", avatar_path)
                self.user_data.update({
                    "username": username,
                    "full_name": full_name,
                    "avatar_path": avatar_path,
                })
                profile_saved = True

            if self.selected_photo_path:
                self.status_label.setText('กำลังอัปโหลดรูปโปรไฟล์แบบส่วนตัว...')
                QApplication.processEvents()
                try:
                    response = APIClient.upload_avatar(self.selected_photo_path)
                except (OSError, ValueError, requests.RequestException):
                    if profile_saved:
                        self.profile_updated.emit(self._current_profile_update())
                        self.status_label.setText(
                            "Profile information was saved, but the photo could not be uploaded."
                        )
                    else:
                        self.status_label.setText(
                            "Cannot upload the profile photo. Check your connection."
                        )
                    return
                if not response.ok:
                    detail = self._response_detail(response, "Avatar upload failed.")
                    if profile_saved:
                        self.profile_updated.emit(self._current_profile_update())
                        self.status_label.setText(
                            "Profile information was saved, but the photo could not be uploaded. "
                            + detail
                        )
                    else:
                        self.status_label.setText(detail)
                    return
                try:
                    payload = response.json()
                except (ValueError, AttributeError):
                    self._show_photo_failure(
                        "Avatar upload returned an invalid response.", profile_saved
                    )
                    return
                avatar_path = payload.get("avatar_path")
                if not isinstance(avatar_path, str) or not avatar_path:
                    self._show_photo_failure(
                        "Avatar upload returned an invalid response.", profile_saved
                    )
                    return
                photo_uploaded = True
        finally:
            self.save_button.setEnabled(True)

        updated = {
            "username": username,
            "full_name": full_name,
            "avatar_path": avatar_path,
        }
        self.user_data.update(updated)
        self.selected_photo_path = None
        if profile_saved and photo_uploaded:
            self.status_label.setText('บันทึกข้อมูลและรูปโปรไฟล์แล้ว')
        elif photo_uploaded:
            self.status_label.setText('บันทึกรูปโปรไฟล์แบบส่วนตัวแล้ว')
        else:
            self.status_label.setText('บันทึกข้อมูลโปรไฟล์แล้ว')
        self.profile_updated.emit(updated)

    def _current_profile_update(self) -> dict:
        return {
            "username": self.user_data.get("username"),
            "full_name": self.user_data.get("full_name"),
            "avatar_path": self.user_data.get("avatar_path"),
        }

    def _show_photo_failure(self, detail: str, profile_saved: bool) -> None:
        if profile_saved:
            self.profile_updated.emit(self._current_profile_update())
            self.status_label.setText(
                "Profile information was saved, but the photo upload failed. " + detail
            )
        else:
            self.status_label.setText(detail)

    @staticmethod
    def _response_detail(response, fallback: str) -> str:
        try:
            detail = response.json().get("detail", fallback)
        except (ValueError, AttributeError):
            detail = fallback
        return str(detail)
