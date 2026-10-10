"""Read-only Alert Events viewer. No database changes or writes."""

import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.services.api_client import APIClient
from app.services.alert_history_service import (
    local_datetime, summarize_alerts, validate_session_id,
)


class AlertHistoryDialog(QDialog):
    def __init__(self, parent=None, session_id=None):
        super().__init__(parent)
        self.setWindowTitle("PostGuard - Alert Events History")
        self.resize(940, 550)
        self.initial_session_id = session_id
        self.setLayout(QVBoxLayout())

        self.description = QLabel(
            "Experimental posture alerts. The duration column is alert-open time, "
            "NOT the full time spent in a posture. MEDIUM is a provisional API label."
        )
        self.description.setWordWrap(True)
        self.layout().addWidget(self.description)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Session:"))
        self.session_selector = QComboBox()
        controls.addWidget(self.session_selector, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_selected_alerts)
        controls.addWidget(self.refresh_button)
        self.layout().addLayout(controls)

        self.stats_label = QLabel("Select a session to load alerts.")
        self.layout().addWidget(self.stats_label)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Event ID", "Event Type", "API Risk Level", "Started (local)",
            "Ended (local)", "Alert Duration (s)", "Status",
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.layout().addWidget(self.table)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        self.layout().addWidget(close_button)

        self.load_sessions()

    @staticmethod
    def _message(response):
        try:
            data = response.json()
            if isinstance(data, dict):
                return str(data.get("detail", response.text))
        except ValueError:
            pass
        return response.text

    def load_sessions(self):
        try:
            response = APIClient.get_sessions()
            if not response.ok:
                raise RuntimeError(
                    f"GET /sessions HTTP {response.status_code}: {self._message(response)}"
                )
            sessions = response.json()
            if not isinstance(sessions, list):
                raise ValueError("Invalid sessions response")

            self.session_selector.blockSignals(True)
            self.session_selector.clear()
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                session_id = session.get("session_id")
                if type(session_id) is not int or session_id <= 0:
                    continue
                status = session.get("status", "--")
                started = local_datetime(session.get("started_at"))
                self.session_selector.addItem(
                    f"#{session_id} | {started} | {status}", session_id
                )
            if self.initial_session_id is not None:
                index = self.session_selector.findData(self.initial_session_id)
                if index >= 0:
                    self.session_selector.setCurrentIndex(index)
            self.session_selector.blockSignals(False)
            self.session_selector.currentIndexChanged.connect(self.load_selected_alerts)
            self.load_selected_alerts()
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            self.stats_label.setText("Could not load sessions.")
            QMessageBox.warning(self, "Alert History", str(exc))

    def load_selected_alerts(self, *_):
        session_id = self.session_selector.currentData()
        if session_id is None:
            self.table.setRowCount(0)
            self.stats_label.setText("No sessions available.")
            return
        try:
            validate_session_id(session_id)
            response = APIClient.get_session_alerts(session_id)
            if not response.ok:
                raise RuntimeError(
                    f"GET /sessions/{session_id}/alerts HTTP "
                    f"{response.status_code}: {self._message(response)}"
                )
            alerts = response.json()
            stats = summarize_alerts(alerts)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            self.table.setRowCount(0)
            self.stats_label.setText("Alert data unavailable (not zero).")
            QMessageBox.warning(self, "Alert History", str(exc))
            return

        self.stats_label.setText(
            f"Total: {stats['total_alerts']} | Closed: {stats['closed_alerts']} | "
            f"Active: {stats['active_alerts']} | "
            f"Sum of closed alert-open durations: {stats['closed_alert_seconds']} s"
        )
        self.table.setRowCount(len(alerts))
        for row, alert in enumerate(alerts):
            ended = alert.get("ended_at")
            values = [
                alert.get("event_id", "--"),
                alert.get("event_type", "--"),
                alert.get("risk_level", "--"),
                local_datetime(alert.get("started_at")),
                local_datetime(ended),
                alert.get("duration", "--") if ended else "--",
                "CLOSED" if ended else "ACTIVE",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()


def add_alert_history_button(sidebar_layout, main_window):
    """Optional, non-invasive integration with an existing MainWindow sidebar."""
    button = QPushButton("Alert Events")
    sidebar_layout.addWidget(button)
    button.clicked.connect(lambda: AlertHistoryDialog(main_window).exec())
    main_window.alert_history_button = button
    return button
