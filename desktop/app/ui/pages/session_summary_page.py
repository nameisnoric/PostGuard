
"""PostGuard Session Summary with database save status and retry."""

import requests

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QMessageBox,
)

from app.services.api_client import APIClient
from app.services.alert_history_service import (
    duration_text,
    event_type_label,
    local_datetime,
    summarize_alerts,
)
from app.services.session_summary_service import (
    save_session_summary,
)
from app.ui.pages.alert_history_dialog import AlertHistoryDialog


class SessionSummaryPage(QWidget):
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setProperty("page", True)

        self.current_session_id = None
        self.current_summary = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        self.title_label = QLabel("Session Summary")
        self.title_label.setProperty("role", "title")
        self.description_label = QLabel(
            "Completed monitoring session report"
        )
        self.description_label.setProperty("role", "muted")

        # Session information
        info_group = QGroupBox("Session Information")
        info_layout = QVBoxLayout(info_group)

        self.session_label = QLabel("Session ID: --")
        self.database_label = QLabel("Session Status: --")
        self.camera_label = QLabel("Camera: --")
        self.baseline_label = QLabel("Baseline ID: --")
        self.start_label = QLabel("Started: --")
        self.end_label = QLabel("Ended: --")
        self.duration_label = QLabel("Duration: --")
        self.paused_duration_label = QLabel("Paused Duration: --")
        self.pause_count_label = QLabel("Pause Count: --")

        for widget in (
            self.session_label,
            self.database_label,
            self.camera_label,
            self.baseline_label,
            self.start_label,
            self.end_label,
            self.duration_label,
            self.paused_duration_label,
            self.pause_count_label,
        ):
            info_layout.addWidget(widget)

        # Detection summary
        detection_group = QGroupBox("Detection Summary")
        detection_layout = QVBoxLayout(detection_group)

        self.count_label = QLabel("Detection Cycles: --")
        self.pose_label = QLabel("Pose Detected: --")
        self.face_label = QLabel("Face Detected: --")
        self.shoulder_label = QLabel("Average Shoulder: --")
        self.neck_label = QLabel("Average Neck: --")
        self.baseline_shoulder_label = QLabel(
            "Baseline Shoulder: --"
        )
        self.baseline_neck_label = QLabel(
            "Baseline Neck: --"
        )

        for widget in (
            self.count_label,
            self.pose_label,
            self.face_label,
            self.shoulder_label,
            self.neck_label,
            self.baseline_shoulder_label,
            self.baseline_neck_label,
        ):
            detection_layout.addWidget(widget)

        report_group = QGroupBox("Stored Report Metrics")
        report_layout = QVBoxLayout(report_group)
        self.average_risk_label = QLabel("Average Risk Score: N/A")
        self.maximum_risk_label = QLabel("Maximum Risk Score: N/A")
        self.blink_rate_label = QLabel("Blink Rate: N/A")
        self.report_alert_count_label = QLabel("Stored Alert Count: --")
        self.frequent_event_label = QLabel("Most Frequent Alert: N/A")
        self.risk_breakdown_label = QLabel("Risk Breakdown: --")
        self.risk_breakdown_label.setWordWrap(True)
        for widget in (
            self.average_risk_label,
            self.maximum_risk_label,
            self.blink_rate_label,
            self.report_alert_count_label,
            self.frequent_event_label,
            self.risk_breakdown_label,
        ):
            report_layout.addWidget(widget)

        # Database save status
        self.save_group = QGroupBox("Summary Save Problem")
        save_layout = QVBoxLayout(self.save_group)

        self.save_status_label = QLabel("No report save status is available.")
        self.save_status_label.setWordWrap(True)

        self.retry_button = QPushButton(
            "Retry Save Summary"
        )
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(
            self.retry_save
        )

        save_layout.addWidget(self.save_status_label)
        save_layout.addWidget(self.retry_button)

        # Alert overview
        alert_group = QGroupBox(
            "Alert Events (Experimental)"
        )
        alert_layout = QVBoxLayout(alert_group)

        self.alert_total_label = QLabel("Total Alerts: --")
        self.alert_closed_label = QLabel("Closed Alerts: --")
        self.alert_active_label = QLabel("Active Alerts: --")
        self.alert_duration_label = QLabel(
            "Closed Alert Duration: --"
        )
        self.alert_error_label = QLabel("")
        self.alert_error_label.setWordWrap(True)

        for widget in (
            self.alert_total_label,
            self.alert_closed_label,
            self.alert_active_label,
            self.alert_duration_label,
            self.alert_error_label,
        ):
            alert_layout.addWidget(widget)

        alert_buttons = QHBoxLayout()

        self.refresh_alerts_button = QPushButton(
            "Refresh Alert Summary"
        )
        self.refresh_alerts_button.clicked.connect(
            self.refresh_alerts
        )

        self.view_alerts_button = QPushButton(
            "View Alert History"
        )
        self.view_alerts_button.clicked.connect(
            self.open_alert_history
        )

        alert_buttons.addWidget(
            self.refresh_alerts_button
        )
        alert_buttons.addWidget(
            self.view_alerts_button
        )

        alert_layout.addLayout(alert_buttons)

        self.note_label = QLabel(
            "Risk score and blink rate remain N/A until their complete calculations "
            "are connected. Alert duration is the time an alert record remained open."
        )
        self.note_label.setWordWrap(True)
        self.note_label.setProperty("role", "muted")

        self.back_button = QPushButton(
            "Back to Dashboard"
        )
        self.back_button.clicked.connect(
            self.go_back
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(info_group)
        layout.addWidget(detection_group)
        layout.addWidget(report_group)
        layout.addWidget(self.save_group)
        layout.addWidget(alert_group)
        layout.addWidget(self.note_label)
        layout.addStretch()
        layout.addWidget(self.back_button)

    @staticmethod
    def format_angle(value):
        if value is None:
            return "N/A"
        return f"{float(value):+.2f}\N{DEGREE SIGN}"

    def set_saved_report(self, session: dict, saved: dict) -> None:
        """Display database measurements without recalculating detection."""
        report = {
            **saved,
            "database_status": session.get("status", "N/A"),
            "camera_name": session.get("camera_name") or f"ID {session.get('camera_id', 'N/A')}",
            "baseline_id": session.get("baseline_id", "N/A"),
            "started_at": session.get("started_at", "N/A"),
            "ended_at": session.get("ended_at", "N/A"),
            "duration_seconds": session.get("total_duration"),
            "paused_duration": session.get("paused_duration"),
            "pause_count": session.get("pause_count", 0),
            "summary_save_status": "LOADED",
        }
        self.set_summary(report)
        self.title_label.setText("Saved Session Report")
        self.back_button.setText("Close Report")

    def set_summary(self, summary: dict) -> None:
        self.current_summary = summary.copy()
        self.current_session_id = summary.get("session_id")
        saved_metrics = summary.get("saved_summary")
        report_metrics = saved_metrics if isinstance(saved_metrics, dict) else summary

        self.session_label.setText(
            f"Session ID: {self.current_session_id}"
        )
        self.database_label.setText(
            "Session Status: "
            + str(summary.get("database_status", "--"))
        )
        self.camera_label.setText(
            "Camera: "
            + str(summary.get("camera_name", "--"))
        )
        self.baseline_label.setText(
            "Baseline ID: "
            + str(summary.get("baseline_id", "--"))
        )
        self.start_label.setText(
            "Started: "
            + local_datetime(summary.get("started_at"))
        )
        self.end_label.setText(
            "Ended: "
            + local_datetime(summary.get("ended_at"))
        )

        seconds = summary.get("duration_seconds")
        self.duration_label.setText(f"Total Duration: {duration_text(seconds)}")
        self.paused_duration_label.setText(
            f"Paused Duration: {duration_text(summary.get('paused_duration'))}"
        )
        self.pause_count_label.setText(
            f"Pause Count: {summary.get('pause_count', 0)}"
        )

        for label, title, key in (
            (self.count_label, "Detection Cycles", "detection_count"),
            (self.pose_label, "Pose Detected", "pose_detected_count"),
            (self.face_label, "Face Detected", "face_detected_count"),
        ):
            value = summary.get(key)
            label.setText(f"{title}: {value if value is not None else 'N/A'}")
        self.shoulder_label.setText(
            "Average Shoulder: "
            + self.format_angle(
                summary.get("average_shoulder")
            )
        )
        self.neck_label.setText(
            "Average Neck: "
            + self.format_angle(
                summary.get("average_neck")
            )
        )
        self.baseline_shoulder_label.setText(
            "Baseline Shoulder: "
            + self.format_angle(
                summary.get("baseline_shoulder")
            )
        )
        self.baseline_neck_label.setText(
            "Baseline Neck: "
            + self.format_angle(
                summary.get("baseline_neck")
            )
        )

        self.average_risk_label.setText(
            "Average Risk Score: "
            + self._number_or_na(report_metrics.get("average_risk_score"))
        )
        self.maximum_risk_label.setText(
            "Maximum Risk Score: "
            + self._number_or_na(report_metrics.get("maximum_risk_score"))
        )
        self.blink_rate_label.setText(
            "Blink Rate: " + self._number_or_na(report_metrics.get("blink_rate"))
        )
        alert_count = report_metrics.get("total_alert_count")
        self.report_alert_count_label.setText(
            f"Stored Alert Count: {alert_count if alert_count is not None else 'N/A'}"
        )
        frequent = report_metrics.get("most_frequent_alert_event")
        self.frequent_event_label.setText(
            f"Most Frequent Alert: {event_type_label(frequent)}"
        )
        self.risk_breakdown_label.setText(
            "Risk Breakdown: " + self._risk_breakdown(report_metrics)
        )

        self.update_save_status()
        self.refresh_alerts()

    @staticmethod
    def _number_or_na(value):
        if value is None:
            return "N/A"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _risk_breakdown(summary):
        parts = []
        for level in ("low", "medium", "high"):
            count = summary.get(f"{level}_risk_alert_count")
            seconds = summary.get(f"{level}_risk_duration")
            if count is None and seconds is None:
                parts.append(f"{level.title()} N/A")
            else:
                count_text = count if count is not None else "N/A"
                parts.append(
                    f"{level.title()} {count_text} alert(s), "
                    f"{duration_text(seconds)} open time"
                )
        return " | ".join(parts)

    def update_save_status(self):
        summary = self.current_summary or {}
        status = summary.get("summary_save_status")
        error = summary.get("summary_save_error")

        if status == "LOADED":
            self.save_status_label.setText("Loaded saved report from database.")
            self.retry_button.setEnabled(False)
            self.save_group.hide()
        elif status == "SAVED":
            self.save_status_label.setText("Session report saved successfully.")
            self.retry_button.setEnabled(False)
            self.save_group.hide()
        elif status == "ALREADY_EXISTS":
            self.save_status_label.setText("A saved report already exists for this session.")
            self.retry_button.setEnabled(False)
            self.save_group.hide()
        else:
            self.save_status_label.setText(
                "The session report has not been saved.\n" + str(error or "Unknown error")
            )
            self.retry_button.setEnabled(self.current_session_id is not None)
            self.save_group.show()
    def retry_save(self):
        if not self.current_summary:
            return

        self.retry_button.setEnabled(False)

        try:
            result = save_session_summary(
                self.current_summary
            )

            self.current_summary["summary_save_status"] = (
                result["status"]
            )
            self.current_summary["saved_summary"] = (
                result["summary"]
            )
            self.current_summary["summary_save_error"] = None

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            self.current_summary["summary_save_status"] = (
                "FAILED"
            )
            self.current_summary["summary_save_error"] = (
                str(error)
            )

        self.update_save_status()

    def refresh_alerts(self):
        for label in (
            self.alert_total_label,
            self.alert_closed_label,
            self.alert_active_label,
            self.alert_duration_label,
        ):
            label.setText("--")

        self.alert_error_label.setText("")

        session_id = self.current_session_id

        if type(session_id) is not int or session_id <= 0:
            return

        try:
            response = APIClient.get_session_alerts(
                session_id
            )

            if not response.ok:
                raise RuntimeError(
                    f"Alert API HTTP {response.status_code}"
                )

            stats = summarize_alerts(
                response.json()
            )

            self.alert_total_label.setText(
                f"Total Alerts: {stats['total_alerts']}"
            )
            self.alert_closed_label.setText(
                f"Closed Alerts: {stats['closed_alerts']}"
            )
            self.alert_active_label.setText(
                f"Active Alerts: {stats['active_alerts']}"
            )
            self.alert_duration_label.setText(
                "Closed Alert Duration: "
                f"{stats['closed_alert_seconds']} seconds"
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
        ) as error:
            self.alert_error_label.setText(
                f"Alert data unavailable: {error}"
            )

    def open_alert_history(self):
        dialog = AlertHistoryDialog(
            self,
            session_id=self.current_session_id,
        )
        dialog.exec()

    def go_back(self):
        status = (self.current_summary or {}).get("summary_save_status")
        if status not in ("SAVED", "ALREADY_EXISTS", "LOADED"):
            answer = QMessageBox.question(
                self,
                "Unsaved Report",
                "This session report has not been saved successfully. "
                "If you leave now, you may not be able to retry with the same data.\n\n"
                "Leave this report?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.back_requested.emit()
