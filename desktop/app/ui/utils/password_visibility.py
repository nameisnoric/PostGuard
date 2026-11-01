"""Shared show/hide control for password fields."""

from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QLineEdit


_ICON_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "icons"
)


def attach_password_visibility(
    field: QLineEdit,
) -> QAction:
    """
    Add a trailing show/hide action to a password field.

    The password remains hidden by default.
    Clicking the eye icon toggles between:
    - Password
    - Normal

    This function only changes presentation.
    It does not modify authentication or password values.
    """

    field.setEchoMode(
        QLineEdit.EchoMode.Password
    )

    action = field.addAction(
        QIcon(
            str(
                _ICON_DIRECTORY
                / "eye.svg"
            )
        ),
        QLineEdit.ActionPosition.TrailingPosition,
    )

    action.setCheckable(
        True
    )

    action.setText(
        "แสดงรหัสผ่าน"
    )

    action.setToolTip(
        "แสดงรหัสผ่าน"
    )

    def toggle_visibility(
        visible: bool,
    ) -> None:

        field.setEchoMode(
            QLineEdit.EchoMode.Normal
            if visible
            else
            QLineEdit.EchoMode.Password
        )

        label = (
            "ซ่อนรหัสผ่าน"
            if visible
            else
            "แสดงรหัสผ่าน"
        )

        icon_name = (
            "eye-off.svg"
            if visible
            else
            "eye.svg"
        )

        action.setText(
            label
        )

        action.setToolTip(
            label
        )

        action.setIcon(
            QIcon(
                str(
                    _ICON_DIRECTORY
                    / icon_name
                )
            )
        )

    action.toggled.connect(
        toggle_visibility
    )

    # Keep a reference for testing/UI automation.
    field.password_visibility_action = (
        action
    )

    return action