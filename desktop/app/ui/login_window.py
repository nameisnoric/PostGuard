from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox
)

import requests

from app.core.token_store import TokenStore
from app.services.api_client import APIClient
from app.ui.main_window import MainWindow


class LoginWindow(QWidget):

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("PostGuard - Login")
        self.resize(400, 400)

        self.title_label = QLabel("PostGuard")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("KU Email")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.login_button = QPushButton("Login")
        self.register_button = QPushButton("Create Account")
        self.login_button.clicked.connect(
            self.handle_login
        )
        self.register_button.clicked.connect(
            self.open_register
        )

        layout = QVBoxLayout()

        layout.addWidget(self.title_label)
        layout.addWidget(self.email_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)
        layout.addWidget(self.register_button)

        self.setLayout(layout)

    def handle_login(self) -> None:
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            self.show_error(
                "Please enter your email and password."
            )
            return

        try:
            response = APIClient.login(
                email,
                password
            )

        except requests.RequestException:
            self.show_error(
                "Cannot connect to the PostGuard server."
            )
            return

        print("LOGIN STATUS:", response.status_code)
        print("LOGIN RESPONSE:", response.text)

        if response.status_code != 200:
            self.show_error(
                "Invalid email or password."
            )
            return

        login_data = response.json()

        access_token = login_data.get(
            "access_token"
        )

        if not access_token:
            self.show_error(
                "Access token was not returned by the server."
            )
            return

        TokenStore.set_token(access_token)

        try:
            me_response = APIClient.get_current_user()

        except requests.RequestException:
            TokenStore.clear_token()

            self.show_error(
                "Unable to load user information."
            )
            return

        print("ME STATUS:", me_response.status_code)
        print("ME RESPONSE:", me_response.text)

        if me_response.status_code != 200:
            TokenStore.clear_token()

            self.show_error(
                "Unable to verify the current user."
            )
            return

        user_data = me_response.json()

        self.main_window = MainWindow(
            user_data
        )

        self.main_window.show()
        self.close()

    def open_register(self):
        from app.ui.register_window import RegisterWindow
        self.register_window = RegisterWindow()

        self.register_window.show()

        self.close()
    
    def show_error(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "PostGuard",
            message
        )