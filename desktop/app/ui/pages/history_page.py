
from datetime import datetime

import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QGroupBox,
    QMessageBox,
)

from app.services.api_client import APIClient


class HistoryPage(QWidget):

    COLUMNS = [
        "Session ID",
        "Started At",
        "Duration",
        "Status",
        "Camera ID",
        "Baseline ID",
    ]

    def __init__(self):
        super().__init__()

        self.sessions = []

        layout = QVBoxLayout(self)

        # Page header
        header_layout = QHBoxLayout()

        self.title_label = QLabel(
            "Monitoring History"
        )

        self.refresh_button = QPushButton(
            "Refresh"
        )

        self.refresh_button.clicked.connect(
            self.load_sessions
        )

        header_layout.addWidget(
            self.title_label
        )

        header_layout.addStretch()

        header_layout.addWidget(
            self.refresh_button
        )

        self.description_label = QLabel(
            "Monitoring sessions saved in PostgreSQL."
        )

        self.status_label = QLabel(
            "Click Refresh to load sessions."
        )

        # History table
        self.table = QTableWidget()

        self.table.setColumnCount(
            len(self.COLUMNS)
        )

        self.table.setHorizontalHeaderLabels(
            self.COLUMNS
        )

        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.table.setAlternatingRowColors(True)

        self.table.verticalHeader().setVisible(False)

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.table.itemSelectionChanged.connect(
            self.show_selected_session
        )

        # Session details
        details_group = QGroupBox(
            "Session Details"
        )

        details_layout = QVBoxLayout(
            details_group
        )

        self.details_label = QLabel(
            "Select a session to view its details."
        )

        self.details_label.setWordWrap(True)

        details_layout.addWidget(
            self.details_label
        )

        # Main layout
        layout.addLayout(header_layout)
        layout.addWidget(self.description_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.table, 1)
        layout.addWidget(details_group)

    @staticmethod
    def format_datetime(value):
        if not value:
            return "--"

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if parsed.tzinfo is not None:
                parsed = parsed.astimezone()

            return parsed.strftime(
                "%d/%m/%Y %H:%M:%S"
            )

        except (ValueError, TypeError, AttributeError):
            return str(value)

    @staticmethod
    def format_duration(seconds):
        if seconds is None:
            return "--"

        try:
            total = max(0, int(seconds))
        except (ValueError, TypeError):
            return "--"

        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    @staticmethod
    def make_item(value):
        item = QTableWidgetItem(
            str(value)
        )

        item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        return item

    def load_sessions(self):
        self.refresh_button.setEnabled(False)

        try:
            response = APIClient.get(
                "/sessions"
            )

            if not response.ok:
                raise RuntimeError(
                    "Cannot load sessions: "
                    f"HTTP {response.status_code}\n"
                    f"{response.text[:300]}"
                )

            sessions = response.json()

            if not isinstance(sessions, list):
                raise ValueError(
                    "Invalid sessions response."
                )

            if not all(
                isinstance(session, dict)
                for session in sessions
            ):
                raise ValueError(
                    "Invalid session record."
                )

            # Backend already returns newest first.
            self.sessions = sessions

            self.table.setRowCount(0)

            self.details_label.setText(
                "Select a session to view its details."
            )

            self.table.setRowCount(
                len(sessions)
            )

            for row, session in enumerate(sessions):

                values = [
                    session.get("session_id", "--"),
                    self.format_datetime(
                        session.get("started_at")
                    ),
                    self.format_duration(
                        session.get("total_duration")
                    ),
                    session.get("status", "--"),
                    session.get("camera_id", "--"),
                    session.get("baseline_id", "--"),
                ]

                for column, value in enumerate(values):
                    self.table.setItem(
                        row,
                        column,
                        self.make_item(value),
                    )

            if sessions:
                self.status_label.setText(
                    f"Found {len(sessions)} session(s)."
                )
            else:
                self.status_label.setText(
                    "No monitoring history found."
                )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
        ) as error:

            self.status_label.setText(
                "Failed to load session history."
            )

            QMessageBox.warning(
                self,
                "History Error",
                str(error),
            )

        finally:
            self.refresh_button.setEnabled(True)

    def show_selected_session(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.sessions):
            return

        session = self.sessions[row]

        details = [
            f"Session ID: {session.get('session_id', '--')}",
            f"Status: {session.get('status', '--')}",
            f"Camera ID: {session.get('camera_id', '--')}",
            f"Baseline ID: {session.get('baseline_id', '--')}",
            "Started: "
            + self.format_datetime(
                session.get("started_at")
            ),
            "Ended: "
            + self.format_datetime(
                session.get("ended_at")
            ),
            "Total Duration: "
            + self.format_duration(
                session.get("total_duration")
            ),
            "Paused Duration: "
            + self.format_duration(
                session.get("paused_duration")
            ),
            f"Pause Count: {session.get('pause_count', 0)}",
        ]

        self.details_label.setText(
            "\n".join(details)
        )
