from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox
)

from services.api_client import APIClient

import httpx

class LoginWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.api_client = APIClient()

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
        self.login_button.clicked.connect(self.handle_login)

        layout = QVBoxLayout()

        layout.addWidget(self.title_label)
        layout.addWidget(self.email_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)

        self.setLayout(layout)

    def handle_login(self) -> None:
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password :
            QMessageBox.warning(
                self,
                "Login",
                "Please enter your email and password"
            )
            return

        try :
            access_token = self.api_client.login(
                email,
                password
            )

            QMessageBox.information(
                self,
                "Login",
                "Login Success"
            )

            print("Access token recieve : ", bool(access_token))

        except httpx.HTTPStatusError:
            QMessageBox.warning(
                self,
                "Login",
                "Invalid email or password"
            )

        except httpx.RequestError:
            QMessageBox.critical(
                self,
                "Connect Error",
                "Cannot connect to PostGaurd"
            )