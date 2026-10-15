"""Three-step password reset. Reset credentials stay in this dialog only."""

import re

import requests
from PySide6.QtWidgets import (
    QDialog, QFrame, QLabel, QLineEdit, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from app.services.api_client import APIClient
from app.ui.theme import APP_QSS


class PasswordResetDialog(QDialog):
    def __init__(self, parent=None, email=""):
        super().__init__(parent)
        self.setWindowTitle("PostGuard - Reset Password")
        self.resize(520, 510)
        self.setStyleSheet(APP_QSS)
        self.email = ""
        self._reset_token = None
        self._busy = False
        self.pages = QStackedWidget()
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.back_button = QPushButton("Back to Login")
        self.back_button.clicked.connect(self.reject)

        self.email_input = QLineEdit(email)
        self.email_input.setPlaceholderText("KU Email (@ku.th)")
        self.send_button = QPushButton("Send Reset OTP")
        self.send_button.setProperty("variant", "primary")
        self.send_button.clicked.connect(self.request_code)
        self._add_page("Forgot Password", [self.email_input, self.send_button])

        self.otp_note = QLabel("")
        self.otp_note.setWordWrap(True)
        self.otp_input = QLineEdit()
        self.otp_input.setPlaceholderText("6-digit OTP")
        self.otp_input.setMaxLength(6)
        self.verify_button = QPushButton("Verify OTP")
        self.verify_button.setProperty("variant", "primary")
        self.verify_button.clicked.connect(self.verify_code)
        self.resend_button = QPushButton("Send New OTP")
        self.resend_button.clicked.connect(self.request_code)
        self.change_email_button = QPushButton("Change Email")
        self.change_email_button.clicked.connect(self.change_email)
        self._add_page("Verify Reset OTP", [self.otp_note, self.otp_input, self.verify_button, self.resend_button, self.change_email_button])

        rules = QLabel("Use at least 8 characters, including uppercase and lowercase letters, a number and a special character.")
        rules.setWordWrap(True)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("New password")
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Confirm new password")
        for field in (self.password_input, self.confirm_input):
            field.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_button = QPushButton("Save New Password")
        self.reset_button.setProperty("variant", "primary")
        self.reset_button.clicked.connect(self.save_password)
        self._add_page("Set New Password", [rules, self.password_input, self.confirm_input, self.reset_button])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)
        layout.addWidget(self.pages)
        layout.addWidget(self.status_label)
        layout.addWidget(self.back_button)

    def _add_page(self, title, widgets):
        page = QFrame()
        page.setProperty("card", True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(13)
        title_label = QLabel(title)
        title_label.setProperty("role", "title")
        layout.addWidget(title_label)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch()
        self.pages.addWidget(page)

    def _set_busy(self, busy):
        self._busy = busy
        self.pages.setEnabled(not busy)
        self.back_button.setEnabled(not busy)

    def _clear_credentials(self):
        self._reset_token = None
        self.otp_input.clear()
        self.password_input.clear()
        self.confirm_input.clear()

    def done(self, result):
        self._clear_credentials()
        super().done(result)

    def change_email(self):
        self._clear_credentials()
        self.email = ""
        self.status_label.clear()
        self.pages.setCurrentIndex(0)

    @staticmethod
    def _json_object(response):
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid response")
        return data

    def request_code(self):
        if self._busy:
            return
        email = self.email_input.text().strip()
        if not re.fullmatch(r"[^\s@]+@ku\.th", email, re.IGNORECASE):
            self.status_label.setText("Please enter a valid @ku.th email address.")
            return
        self._set_busy(True)
        self.status_label.setText("Requesting reset code...")
        try:
            response = APIClient.request_password_reset(email)
            if response.status_code != 200:
                self.status_label.setText("Cannot request a code. Check your email address and try again.")
                return
            self._json_object(response)
            self._clear_credentials()
            self.email = email
            self.otp_note.setText(f"If this account exists, a code will be sent to {email}.\nThe code expires after 5 minutes. Use the latest code.")
            self.pages.setCurrentIndex(1)
            self.status_label.setText("Enter the code from your email.")
        except requests.RequestException:
            self.status_label.setText("Cannot confirm that the code was sent. Check your connection and try again.")
        except ValueError:
            self.status_label.setText("The server returned an invalid response. Please try again.")
        finally:
            self._set_busy(False)

    def verify_code(self):
        if self._busy or self.pages.currentIndex() != 1:
            return
        otp = self.otp_input.text().strip()
        if not re.fullmatch(r"[0-9]{6}", otp):
            self.status_label.setText("OTP must contain exactly 6 digits.")
            return
        self._set_busy(True)
        try:
            response = APIClient.verify_reset_otp(self.email, otp)
            if response.status_code != 200:
                self.status_label.setText("Unable to verify OTP. The code may be incorrect, expired or used. You can request a new code.")
                return
            token = self._json_object(response).get("reset_token")
            if not isinstance(token, str) or not token.strip():
                raise ValueError("Missing reset token")
            self._reset_token = token
            self.otp_input.clear()
            self.pages.setCurrentIndex(2)
            self.status_label.setText("OTP verified. Set your new password within 10 minutes.")
        except requests.RequestException:
            self.status_label.setText("Cannot confirm verification. Check your connection; request a new OTP if this code was already used.")
        except ValueError:
            self.status_label.setText("Invalid verification response. Please request a new OTP.")
        finally:
            self._set_busy(False)

    def save_password(self):
        if self._busy or self.pages.currentIndex() != 2 or not self._reset_token:
            return
        password = self.password_input.text()
        if password != self.confirm_input.text():
            self.status_label.setText("Passwords do not match.")
            return
        if len(password) < 8 or any(not re.search(pattern, password) for pattern in (r"[A-Z]", r"[a-z]", r"\d", r"[^A-Za-z0-9]")):
            self.status_label.setText("Please follow all password requirements above.")
            return
        self._set_busy(True)
        try:
            response = APIClient.reset_password(self._reset_token, password)
            if response.status_code == 401:
                self._clear_credentials()
                self.pages.setCurrentIndex(1)
                self.status_label.setText("Reset authorization expired or was already used. Try logging in if you previously submitted this password, or request a new OTP.")
                return
            if response.status_code != 200:
                self.status_label.setText("Password reset was not confirmed. Check the requirements and try again.")
                return
            self._json_object(response)
            self._clear_credentials()
            QMessageBox.information(self, "Password Updated", "Your password has been updated. Log in with your new password.")
            self.accept()
        except requests.RequestException:
            self.status_label.setText("The result could not be confirmed. Try logging in with the new password before requesting another reset.")
        except ValueError:
            self.status_label.setText("Invalid response. Try logging in with the new password to check whether it was saved.")
        finally:
            self._set_busy(False)
