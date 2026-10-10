"""Session Summary with read-only Alert Events overview."""

import requests
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox, QHBoxLayout,
)

from app.services.api_client import APIClient
from app.services.alert_history_service import summarize_alerts
from app.ui.pages.alert_history_dialog import AlertHistoryDialog


class SessionSummaryPage(QWidget):
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.current_session_id = None
        layout = QVBoxLayout(self)
        self.title_label = QLabel("Session Summary")
        self.description_label = QLabel("Summary of the completed monitoring session.")

        info_group = QGroupBox("Session Information")
        info_layout = QVBoxLayout(info_group)
        self.session_label = QLabel("Session ID: --")
        self.database_label = QLabel("Database Status: --")
        self.camera_label = QLabel("Camera: --")
        self.baseline_label = QLabel("Baseline ID: --")
        self.start_label = QLabel("Started: --")
        self.end_label = QLabel("Ended: --")
        self.duration_label = QLabel("Duration: --")
        for label in (
            self.session_label, self.database_label, self.camera_label,
            self.baseline_label, self.start_label, self.end_label,
            self.duration_label,
        ):
            info_layout.addWidget(label)

        result_group = QGroupBox("Detection Summary")
        result_layout = QVBoxLayout(result_group)
        self.count_label = QLabel("Detection Cycles: --")
        self.pose_label = QLabel("Pose Detected: --")
        self.face_label = QLabel("Face Detected: --")
        self.shoulder_label = QLabel("Average Shoulder Tilt: --")
        self.neck_label = QLabel("Average Neck Lateral Tilt: --")
        self.baseline_shoulder_label = QLabel("Baseline Shoulder Tilt: --")
        self.baseline_neck_label = QLabel("Baseline Neck Lateral Tilt: --")
        for label in (
            self.count_label, self.pose_label, self.face_label,
            self.shoulder_label, self.neck_label,
            self.baseline_shoulder_label, self.baseline_neck_label,
        ):
            result_layout.addWidget(label)

        alert_group = QGroupBox("Alert Events (Experimental)")
        alert_layout = QVBoxLayout(alert_group)
        self.alert_total_label = QLabel("Total Alerts: --")
        self.alert_closed_label = QLabel("Closed Alerts: --")
        self.alert_active_label = QLabel("Active Alerts: --")
        self.alert_duration_label = QLabel("Total Closed Alert Duration: --")
        self.alert_error_label = QLabel("")
        self.alert_error_label.setWordWrap(True)
        for label in (
            self.alert_total_label, self.alert_closed_label,
            self.alert_active_label, self.alert_duration_label,
            self.alert_error_label,
        ):
            alert_layout.addWidget(label)

        buttons = QHBoxLayout()
        self.refresh_alerts_button = QPushButton("Refresh Alert Summary")
        self.refresh_alerts_button.clicked.connect(self.refresh_alerts)
        buttons.addWidget(self.refresh_alerts_button)
        self.view_alerts_button = QPushButton("View Alert History")
        self.view_alerts_button.clicked.connect(self.open_alert_history)
        buttons.addWidget(self.view_alerts_button)
        alert_layout.addLayout(buttons)

        self.note_label = QLabel(
            "Session lifecycle is stored in the database. Detection averages shown "
            "here are local-only and are not persisted in Session Summary. "
            "Alert Duration is the time AFTER an alert was created, not full "
            "posture exposure. API risk level MEDIUM is provisional. "
            "Full PostGuard Risk Score and blink rate are not available yet."
        )
        self.note_label.setWordWrap(True)
        self.back_button = QPushButton("Back to Dashboard")
        self.back_button.clicked.connect(lambda: self.back_requested.emit())

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(info_group)
        layout.addWidget(result_group)
        layout.addWidget(alert_group)
        layout.addWidget(self.note_label)
        layout.addStretch()
        layout.addWidget(self.back_button)

    @staticmethod
    def format_angle(value):
        return "--" if value is None else f"{value:+.2f}°"

    def set_summary(self, summary: dict) -> None:
        self.current_session_id = summary.get("session_id")
        self.session_label.setText(f"Session ID: {summary.get('session_id', '--')}")
        self.database_label.setText(
            "Database Status: " + str(summary.get("database_status", "--"))
        )
        self.camera_label.setText(f"Camera: {summary.get('camera_name', '--')}")
        self.baseline_label.setText(f"Baseline ID: {summary.get('baseline_id', '--')}")
        self.start_label.setText(f"Started: {summary.get('started_at', '--')}")
        self.end_label.setText(f"Ended: {summary.get('ended_at', '--')}")
        seconds = summary.get("duration_seconds") or 0
        minutes, remaining = divmod(int(seconds), 60)
        self.duration_label.setText(f"Duration: {minutes:02d}:{remaining:02d}")
        self.count_label.setText(
            "Detection Cycles: " + str(summary.get("detection_count", 0))
        )
        self.pose_label.setText(
            "Pose Detected: " + str(summary.get("pose_detected_count", 0))
        )
        self.face_label.setText(
            "Face Detected: " + str(summary.get("face_detected_count", 0))
        )
        self.shoulder_label.setText(
            "Average Shoulder Tilt: " + self.format_angle(summary.get("average_shoulder"))
        )
        self.neck_label.setText(
            "Average Neck Lateral Tilt: " + self.format_angle(summary.get("average_neck"))
        )
        self.baseline_shoulder_label.setText(
            "Baseline Shoulder Tilt: " + self.format_angle(summary.get("baseline_shoulder"))
        )
        self.baseline_neck_label.setText(
            "Baseline Neck Lateral Tilt: " + self.format_angle(summary.get("baseline_neck"))
        )
        self.refresh_alerts()

    def refresh_alerts(self):
        self.alert_total_label.setText("Total Alerts: --")
        self.alert_closed_label.setText("Closed Alerts: --")
        self.alert_active_label.setText("Active Alerts: --")
        self.alert_duration_label.setText("Total Closed Alert Duration: --")
        self.alert_error_label.setText("")
        session_id = self.current_session_id
        if type(session_id) is not int or session_id <= 0:
            self.alert_error_label.setText("No valid session ID available.")
            return
        try:
            response = APIClient.get_session_alerts(session_id)
            if not response.ok:
                raise RuntimeError(f"GET alerts returned HTTP {response.status_code}")
            stats = summarize_alerts(response.json())
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            self.alert_error_label.setText(
                f"Alert data unavailable (not zero): {exc}"
            )
            return
        self.alert_total_label.setText(f"Total Alerts: {stats['total_alerts']}")
        self.alert_closed_label.setText(f"Closed Alerts: {stats['closed_alerts']}")
        self.alert_active_label.setText(f"Active Alerts: {stats['active_alerts']}")
        self.alert_duration_label.setText(
            f"Total Closed Alert Duration: {stats['closed_alert_seconds']} seconds"
        )

    def open_alert_history(self):
        dialog = AlertHistoryDialog(self, session_id=self.current_session_id)
        dialog.exec()
