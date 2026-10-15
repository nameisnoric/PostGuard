"""Restricted desktop screen for accounts in the 14-day deletion period."""

from datetime import datetime, timezone

import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.token_store import TokenStore
from app.services.api_client import APIClient
from app.ui.theme import APP_QSS, set_centered_window


class AccountRecoveryWindow(QWidget):
    def __init__(self, user_data: dict):
        super().__init__()
        self.user_data = user_data
        self._leaving = False
        self.setWindowTitle("PostGuard - Account Recovery")
        self.setObjectName("authWindow")
        self.setStyleSheet(APP_QSS)
        set_centered_window(self, 900, 580, 720, 500)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.addStretch()
        card = QFrame()
        card.setProperty("card", True)
        card.setMaximumWidth(560)
        card.setMinimumWidth(460)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(42, 40, 42, 40)
        layout.setSpacing(16)

        title = QLabel("Account scheduled for deletion")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message = QLabel(
            "This account is disabled. Recover it before the deadline to restore "
            "access to PostGuard and keep its saved data."
        )
        message.setProperty("role", "muted")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.deadline_label = QLabel(self._deadline_text())
        self.deadline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.deadline_label.setWordWrap(True)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.recover_button = QPushButton("Recover Account")
        self.recover_button.setProperty("variant", "primary")
        self.recover_button.clicked.connect(self.recover_account)
        self.logout_button = QPushButton("Back to Login")
        self.logout_button.clicked.connect(self.back_to_login)

        layout.addWidget(title)
        layout.addWidget(message)
        layout.addWidget(self.deadline_label)
        layout.addWidget(self.status_label)
        layout.addSpacing(6)
        layout.addWidget(self.recover_button)
        layout.addWidget(self.logout_button)
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

        if self._deadline_has_passed():
            self.recover_button.setEnabled(False)
            self.status_label.setText(
                "The 14-day recovery period has ended. Permanent deletion is pending."
            )

    def _deadline(self) -> datetime | None:
        value = self.user_data.get("deletion_scheduled_for")
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _deadline_text(self) -> str:
        deadline = self._deadline()
        if deadline is None:
            return "Deletion deadline is unavailable."
        return "Deletion deadline: " + deadline.astimezone().strftime("%d %b %Y, %H:%M %Z")

    def _deadline_has_passed(self) -> bool:
        deadline = self._deadline()
        return deadline is not None and deadline <= datetime.now(timezone.utc)

    def recover_account(self) -> None:
        self.recover_button.setEnabled(False)
        self.status_label.setText("Recovering account...")
        try:
            response = APIClient.cancel_account_deletion()
        except requests.RequestException:
            self.recover_button.setEnabled(True)
            self.status_label.setText("Cannot recover the account. Check your connection.")
            return
        if not response.ok:
            try:
                detail = response.json().get("detail", "Account recovery failed.")
            except (ValueError, AttributeError):
                detail = "Account recovery failed."
            self.recover_button.setEnabled(response.status_code != 410)
            self.status_label.setText(str(detail))
            return
        try:
            recovered_user = response.json()
        except (ValueError, AttributeError):
            self.recover_button.setEnabled(True)
            self.status_label.setText("Account recovery returned an invalid response.")
            return
        if recovered_user.get("account_status") != "ACTIVE":
            self.recover_button.setEnabled(True)
            self.status_label.setText("Account recovery could not be confirmed.")
            return

        QMessageBox.information(self, "Account recovered", "Your PostGuard account is active again.")
        from app.ui.main_window import MainWindow

        self._leaving = True
        self.main_window = MainWindow(recovered_user)
        self.main_window.show()
        self.close()
        self.main_window.check_previous_sessions()
        self.main_window.dashboard_page.refresh()

    def back_to_login(self) -> None:
        TokenStore.clear_token()
        from app.ui.login_window import LoginWindow

        self._leaving = True
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

    def closeEvent(self, event) -> None:
        if not self._leaving:
            TokenStore.clear_token()
        event.accept()
