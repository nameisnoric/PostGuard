"""Read-only history for integrated risk events and user notifications."""

import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QListView, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from app.services.api_client import APIClient
from app.services.alert_history_service import (
    duration_text, event_type_label, local_datetime, summarize_alerts,
    validate_session_id,
)
from app.ui.theme import APP_QSS


class AlertHistoryDialog(QDialog):
    def __init__(self, parent=None, session_id=None):
        super().__init__(parent)
        self.setWindowTitle("PostGuard - Alert History")
        self.resize(980, 600)
        self.setMinimumSize(760, 480)
        self.setStyleSheet(APP_QSS)
        self.initial_session_id = session_id
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(24, 22, 24, 22)
        self.layout().setSpacing(14)

        title = QLabel("Alert Events")
        title.setProperty("role", "title")
        self.layout().addWidget(title)
        self.description = QLabel(
            "Risk events show each continuous posture-risk episode. Notifications "
            "show when PostGuard actually alerted the user."
        )
        self.description.setWordWrap(True)
        self.layout().addWidget(self.description)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Session:"))
        self.session_selector = QComboBox()
        selector_view = QListView(self.session_selector)
        selector_view.setUniformItemSizes(True)
        selector_view.setMaximumHeight(260)
        self.session_selector.setView(selector_view)
        self.session_selector.setMaxVisibleItems(8)
        self.session_selector.currentIndexChanged.connect(self.load_selected_alerts)
        controls.addWidget(self.session_selector, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_selected_alerts)
        controls.addWidget(self.refresh_button)
        self.layout().addLayout(controls)

        self.stats_label = QLabel("Select a session to load its risk history.")
        self.stats_label.setWordWrap(True)
        self.layout().addWidget(self.stats_label)
        self.empty_label = QLabel("This session has no saved risk events or alerts.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setProperty("role", "muted")
        self.empty_label.setMinimumHeight(90)
        self.empty_label.hide()
        self.layout().addWidget(self.empty_label)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Record", "Type", "Risk", "Started / emitted", "Ended", "Duration", "Status",
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
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
                self.session_selector.addItem(
                    f"#{session_id} | {local_datetime(session.get('started_at'))} | "
                    f"{session.get('status', '--')}",
                    session_id,
                )
            if self.initial_session_id is not None:
                index = self.session_selector.findData(self.initial_session_id)
                if index >= 0:
                    self.session_selector.setCurrentIndex(index)
            self.session_selector.blockSignals(False)
            self.load_selected_alerts()
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            self.stats_label.setText("Unable to load sessions.")
            QMessageBox.warning(self, "Alert History", str(exc))

    def _integrated_records(self, session_id):
        event_response = APIClient.get_session_risk_events(session_id)
        notification_response = APIClient.get_session_alert_notifications(session_id)
        if not event_response.ok or not notification_response.ok:
            return None
        events = event_response.json()
        notifications = notification_response.json()
        if not isinstance(events, list) or not isinstance(notifications, list):
            return None
        if not events and not notifications:
            return None

        rows = []
        for event in events:
            if not isinstance(event, dict):
                continue
            ended = event.get("ended_at")
            rows.append({
                "sort_at": event.get("started_at"),
                "values": [
                    f"R#{event.get('risk_event_id', '--')}",
                    "Risk event",
                    str(event.get("max_risk_level") or event.get("current_risk_level") or "--").title(),
                    local_datetime(event.get("started_at")),
                    local_datetime(ended),
                    duration_text(event.get("duration_seconds")) if ended else "--",
                    str(event.get("status", "--")),
                ],
            })
        for notification in notifications:
            if not isinstance(notification, dict):
                continue
            rows.append({
                "sort_at": notification.get("emitted_at"),
                "values": [
                    f"N#{notification.get('notification_id', '--')}",
                    f"Alert {str(notification.get('alert_type', '--')).title()}",
                    str(notification.get("risk_level") or "--").title(),
                    local_datetime(notification.get("emitted_at")),
                    "--", "--", "SENT",
                ],
            })
        rows.sort(key=lambda row: str(row.get("sort_at") or ""))
        active = sum(1 for event in events if event.get("status") == "ACTIVE")
        incomplete = sum(1 for event in events if event.get("status") == "INCOMPLETE")
        duration = sum(float(event.get("duration_seconds") or 0) for event in events)
        stats = (
            f"Risk events: {len(events)} | Notifications: {len(notifications)} | "
            f"Active: {active} | Incomplete: {incomplete} | "
            f"Recorded risk time: {duration_text(duration)}"
        )
        return rows, stats

    def _legacy_records(self, session_id):
        response = APIClient.get_session_alerts(session_id)
        if not response.ok:
            raise RuntimeError(
                f"GET /sessions/{session_id}/alerts HTTP "
                f"{response.status_code}: {self._message(response)}"
            )
        alerts = response.json()
        stats = summarize_alerts(alerts)
        rows = []
        for alert in alerts:
            ended = alert.get("ended_at")
            rows.append({"values": [
                alert.get("event_id", "--"),
                event_type_label(alert.get("event_type")),
                str(alert.get("risk_level", "--")).title(),
                local_datetime(alert.get("started_at")),
                local_datetime(ended),
                duration_text(alert.get("duration")) if ended else "--",
                "INCOMPLETE" if alert.get("incomplete") else "CLOSED" if ended else "ACTIVE",
            ]})
        label = (
            f"Legacy alerts / ทั้งหมด: {stats['total_alerts']} | Closed: {stats['closed_alerts']} | "
            f"Active: {stats['active_alerts']} | Incomplete: {stats['incomplete_alerts']} | "
            f"Open time: {duration_text(stats['closed_alert_seconds'])}"
        )
        return rows, label

    def load_selected_alerts(self, *_):
        session_id = self.session_selector.currentData()
        if session_id is None:
            self.table.setRowCount(0)
            self.stats_label.setText("No session is available.")
            self.empty_label.setText("No monitoring sessions have been saved yet.")
            self.empty_label.show()
            self.table.hide()
            return
        try:
            validate_session_id(session_id)
            loaded = self._integrated_records(session_id)
            rows, stats = loaded if loaded is not None else self._legacy_records(session_id)
        except (requests.RequestException, ValueError, RuntimeError, TypeError) as exc:
            self.table.setRowCount(0)
            self.stats_label.setText("Unable to load alert history.")
            self.empty_label.setText("Unable to load records. Select Refresh to try again.")
            self.empty_label.show()
            self.table.hide()
            QMessageBox.warning(self, "Alert History", str(exc))
            return

        self.stats_label.setText(stats)
        self.empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, value in enumerate(row["values"]):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)
        if rows:
            self.table.resizeColumnsToContents()


def add_alert_history_button(sidebar_layout, main_window):
    """Optional integration with an existing MainWindow sidebar."""
    button = QPushButton("Alert Events")
    sidebar_layout.addWidget(button)
    button.clicked.connect(lambda: AlertHistoryDialog(main_window).exec())
    main_window.alert_history_button = button
    return button
