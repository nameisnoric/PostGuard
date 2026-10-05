from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel
)

class DashboardPage(QWidget):

    def __init__(self, user_data: dict):
        super().__init__()

        self.user_data = user_data

        layout = QVBoxLayout(self)

        username = self.user_data.get(
            "username",
            "User"
        )

        title_label = QLabel("Dashboard")

        welcome_label = QLabel(
            f"Welcome back, {username}"
        )

        description_label = QLabel(
            "PostGuard is ready to monitor your posture."
        )

        layout.addWidget(title_label)
        layout.addWidget(welcome_label)
        layout.addWidget(description_label)
        layout.addStretch()