
"""PostGuard Session Summary with database save status and retry."""

import requests

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QLayout,
    QScrollArea,
    QSizePolicy,
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
from app.ui.dialogs.alert_history_dialog import AlertHistoryDialog


class SessionSummaryPage(QWidget):
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setProperty("page", True)

        self.current_session_id = None
        self.current_summary = None

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content.setProperty("page", True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 18, 24, 20)
        layout.setSpacing(12)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        scroll_area.setWidget(content)
        page_layout.addWidget(scroll_area)

        self.title_label = QLabel("Session Summary")
        self.title_label.setProperty("role", "title")
        self.description_label = QLabel(
            "รายงานเซสชันการตรวจจับที่เสร็จสิ้น"
        )
        self.description_label.setProperty("role", "muted")

        # Session information
        info_group = QGroupBox("Session Information")
        info_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        info_layout = QVBoxLayout(info_group)

        self.session_label = QLabel('Session ID: --')
        self.database_label = QLabel('สถานะเซสชัน: --')
        self.camera_label = QLabel('กล้อง: --')
        self.baseline_label = QLabel("Baseline ID: --")
        self.start_label = QLabel('เริ่มเมื่อ: --')
        self.end_label = QLabel('สิ้นสุดเมื่อ: --')
        self.duration_label = QLabel('ระยะเวลา: --')
        self.paused_duration_label = QLabel('เวลาหยุดชั่วคราว: --')
        self.pause_count_label = QLabel('จำนวนครั้งที่หยุด: --')

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
        detection_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        detection_layout = QVBoxLayout(detection_group)

        self.count_label = QLabel('รอบการตรวจจับ: --')
        self.pose_label = QLabel('ตรวจพบท่าทาง: --')
        self.face_label = QLabel('ตรวจพบใบหน้า: --')
        self.shoulder_label = QLabel('ความเอียงไหล่เฉลี่ย: --')
        self.neck_label = QLabel('ความเอียงคอเฉลี่ย: --')
        self.baseline_shoulder_label = QLabel(
            'ค่าอ้างอิงไหล่: --'
        )
        self.baseline_neck_label = QLabel(
            'ค่าอ้างอิงคอ: --'
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

        report_group = QGroupBox("ข้อมูลสรุปในรายงาน")
        report_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        report_layout = QVBoxLayout(report_group)
        self.average_risk_label = QLabel('คะแนนความเสี่ยงเฉลี่ย: N/A')
        self.maximum_risk_label = QLabel('คะแนนความเสี่ยงสูงสุด: N/A')
        self.rula_label = QLabel('Full RULA: N/A')
        self.blink_rate_label = QLabel('อัตราการกะพริบตา: N/A')
        self.report_alert_count_label = QLabel('จำนวนการแจ้งเตือนที่บันทึก: --')
        self.frequent_event_label = QLabel('การแจ้งเตือนที่พบบ่อยที่สุด: N/A')
        self.risk_breakdown_label = QLabel('รายละเอียดความเสี่ยง: --')
        self.risk_breakdown_label.setWordWrap(True)
        for widget in (
            self.average_risk_label,
            self.maximum_risk_label,
            self.rula_label,
            self.blink_rate_label,
            self.report_alert_count_label,
            self.frequent_event_label,
            self.risk_breakdown_label,
        ):
            report_layout.addWidget(widget)

        # Database save status
        self.save_group = QGroupBox("เกิดปัญหาในการบันทึกสรุป")
        self.save_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        save_layout = QVBoxLayout(self.save_group)

        self.save_status_label = QLabel('ไม่มีข้อมูลสถานะการบันทึกรายงาน')
        self.save_status_label.setWordWrap(True)

        self.retry_button = QPushButton(
            "ลองบันทึกสรุปอีกครั้ง"
        )
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(
            self.retry_save
        )

        save_layout.addWidget(self.save_status_label)
        save_layout.addWidget(self.retry_button)

        # Alert overview
        alert_group = QGroupBox(
            "เหตุการณ์แจ้งเตือน (ทดลอง)"
        )
        alert_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        alert_layout = QVBoxLayout(alert_group)

        self.alert_total_label = QLabel('การแจ้งเตือนทั้งหมด: --')
        self.alert_closed_label = QLabel('การแจ้งเตือนที่จบแล้ว: --')
        self.alert_active_label = QLabel('การแจ้งเตือนที่ยังทำงาน: --')
        self.alert_duration_label = QLabel(
            'ระยะเวลาการแจ้งเตือนที่จบแล้ว: --'
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
            "Prototype risk uses a 0-3 engineering scale and is not Full RULA or a "
            "clinical diagnosis. Full RULA is saved only after all manual observations "
            "are completed. Blink rate appears after a complete 60-second window. "
            "Alert duration is the time an alert record remained open."
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
        self.back_button.setText("ปิดรายงาน")

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
        self.duration_label.setText(f"ระยะเวลารวม: {duration_text(seconds)}")
        self.paused_duration_label.setText(
            f"เวลาหยุดชั่วคราว: {duration_text(summary.get('paused_duration'))}"
        )
        self.pause_count_label.setText(
            f"จำนวนครั้งที่หยุด: {summary.get('pause_count', 0)}"
        )

        for label, title, key in (
            (self.count_label, "รอบการตรวจจับ", "detection_count"),
            (self.pose_label, "ตรวจพบท่าทาง", "pose_detected_count"),
            (self.face_label, "ตรวจพบใบหน้า", "face_detected_count"),
        ):
            value = summary.get(key)
            label.setText(f"{title}: {value if value is not None else 'N/A'}")
        self.shoulder_label.setText(
            "ความเอียงไหล่เฉลี่ย: "
            + self.format_angle(
                summary.get("average_shoulder")
            )
        )
        self.neck_label.setText(
            "ความเอียงคอเฉลี่ย: "
            + self.format_angle(
                summary.get("average_neck")
            )
        )
        self.baseline_shoulder_label.setText(
            "ค่าอ้างอิงไหล่: "
            + self.format_angle(
                summary.get("baseline_shoulder")
            )
        )
        self.baseline_neck_label.setText(
            "ค่าอ้างอิงคอ: "
            + self.format_angle(
                summary.get("baseline_neck")
            )
        )

        self.average_risk_label.setText(
            "คะแนนความเสี่ยงเฉลี่ย: "
            + self._number_or_na(report_metrics.get("average_risk_score"))
        )
        self.maximum_risk_label.setText(
            "คะแนนความเสี่ยงสูงสุด: "
            + self._number_or_na(report_metrics.get("maximum_risk_score"))
        )
        rula_score = report_metrics.get("rula_final_score")
        rula_level = report_metrics.get("rula_action_level")
        self.rula_label.setText(
            f"Full RULA: {rula_score}/7 | Action Level {rula_level}"
            if rula_score is not None and rula_level is not None
            else "Full RULA: N/A"
        )
        self.blink_rate_label.setText(
            "อัตราการกะพริบตา: " + self._number_or_na(report_metrics.get("blink_rate"))
        )
        alert_count = report_metrics.get("total_alert_count")
        self.report_alert_count_label.setText(
            f"จำนวนการแจ้งเตือนที่บันทึก: {alert_count if alert_count is not None else 'N/A'}"
        )
        frequent = report_metrics.get("most_frequent_alert_event")
        self.frequent_event_label.setText(
            f"การแจ้งเตือนที่พบบ่อยที่สุด: {event_type_label(frequent)}"
        )
        self.risk_breakdown_label.setText(
            "รายละเอียดความเสี่ยง: " + self._risk_breakdown(report_metrics)
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
            self.save_status_label.setText('โหลดรายงานจากฐานข้อมูลแล้ว')
            self.retry_button.setEnabled(False)
            self.save_group.hide()
        elif status == "SAVED":
            self.save_status_label.setText('บันทึกรายงานเซสชันสำเร็จ')
            self.retry_button.setEnabled(False)
            self.save_group.hide()
        elif status == "ALREADY_EXISTS":
            self.save_status_label.setText('เซสชันนี้มีรายงานที่บันทึกไว้แล้ว')
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
                f"การแจ้งเตือนทั้งหมด: {stats['total_alerts']}"
            )
            self.alert_closed_label.setText(
                f"การแจ้งเตือนที่จบแล้ว: {stats['closed_alerts']}"
            )
            self.alert_active_label.setText(
                f"การแจ้งเตือนที่ยังทำงาน: {stats['active_alerts']}"
            )
            self.alert_duration_label.setText(
                "ระยะเวลาการแจ้งเตือนที่จบแล้ว: "
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
                'รายงานยังไม่ถูกบันทึก',
                "This session report has not been saved successfully. "
                "If you leave now, you may not be able to retry with the same data.\n\n"
                "Leave this report?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.back_requested.emit()
