"""Dashboard backed by saved sessions and their persisted reports."""

import math
from datetime import datetime

import requests
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.services.api_client import APIClient


class _LoadSignals(QObject):
    finished = Signal(object, str)


def _response_list(response, label):
    if not response.ok:
        raise ValueError(f"{label} returned HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError(f"Invalid {label.lower()} response")
    return data


class _DashboardLoader(QRunnable):
    """Load required sessions and optional reports away from the UI thread."""

    def __init__(self):
        super().__init__()
        self.signals = _LoadSignals()

    def run(self):
        try:
            sessions = _response_list(APIClient.get_sessions(), "Sessions")
        except (requests.RequestException, ValueError, TypeError):
            self.signals.finished.emit(
                None, "Cannot load saved activity. Use Refresh to retry."
            )
            return

        report_error = ""
        try:
            summaries = _response_list(
                APIClient.get_session_summaries(), "Summaries"
            )
        except (requests.RequestException, ValueError, TypeError):
            summaries = None
            report_error = "Saved report metrics are temporarily unavailable."

        self.signals.finished.emit(
            {
                "sessions": sessions,
                "summaries": summaries,
                "report_error": report_error,
            },
            "",
        )


def active_seconds(session):
    """Return known active seconds for a completed session."""
    if session.get("status") != "COMPLETED":
        return None
    total = session.get("total_duration")
    paused = session.get("paused_duration")
    if any(
        type(value) not in (int, float) or not math.isfinite(value)
        for value in (total, paused)
    ):
        return None
    return int(total - paused) if 0 <= paused <= total else None


def duration_text(seconds):
    if seconds is None:
        return "N/A"
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _finite_number(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        return None
    return float(value)


def _risk_number(value):
    value = _finite_number(value)
    return value if value is not None and 0 <= value <= 3 else None


def _nonnegative_number(value):
    value = _finite_number(value)
    return value if value is not None and value >= 0 else None


def summary_insights(summaries):
    """Aggregate only persisted measurements; missing values remain unavailable."""
    if summaries is None:
        return None

    average_risks = [
        value
        for summary in summaries
        if (value := _risk_number(summary.get("average_risk_score"))) is not None
    ]
    maximum_risks = [
        value
        for summary in summaries
        if (value := _risk_number(summary.get("maximum_risk_score"))) is not None
    ]
    blink_rates = [
        value
        for summary in summaries
        if (value := _nonnegative_number(summary.get("blink_rate"))) is not None
    ]
    alert_counts = [
        value
        for summary in summaries
        if (
            (value := summary.get("total_alert_count")) is not None
            and type(value) is int
            and value >= 0
        )
    ]
    return {
        "report_count": len(summaries),
        "average_risk": (
            sum(average_risks) / len(average_risks) if average_risks else None
        ),
        "maximum_risk": max(maximum_risks) if maximum_risks else None,
        "risk_report_count": len(average_risks),
        "average_blink_rate": (
            sum(blink_rates) / len(blink_rates) if blink_rates else None
        ),
        "blink_report_count": len(blink_rates),
        "total_alert_count": sum(alert_counts),
    }


class DashboardPage(QWidget):
    monitor_requested = Signal()
    history_requested = Signal()

    def __init__(self, user_data: dict):
        super().__init__()
        self._loader = None
        self.setProperty("page", True)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page_layout.addWidget(scroll)

        content = QWidget()
        content.setProperty("page", True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(16)
        scroll.setWidget(content)

        welcome, welcome_layout = self._card("welcome")
        welcome_row = QHBoxLayout()
        welcome_copy = QVBoxLayout()
        name = user_data.get("full_name") or user_data.get("username") or "User"
        welcome_copy.addWidget(self._label(f"Welcome back, {name}", "title"))
        welcome_copy.addWidget(self._label(
            "ตรวจสอบ Session ที่บันทึกไว้ หรือทำ Session ปัจจุบันต่อ", "muted"
        ))
        welcome_row.addLayout(welcome_copy, 1)
        welcome_row.addWidget(
            self._label("POSTGUARD DESKTOP", "eyebrow"),
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        welcome_layout.addLayout(welcome_row)
        layout.addWidget(welcome)

        self.live_label = self._label("พร้อมเมื่อคุณพร้อม", "heading")
        self.live_note = self._label(
            "เลือกกล้อง ตรวจสอบ Camera Preview และบันทึก Personal Baseline",
            "muted",
        )
        layout.addWidget(self.live_label)
        layout.addWidget(self.live_note)

        actions = QHBoxLayout()
        self.monitor_button = QPushButton("Start Monitoring")
        self.monitor_button.setProperty("variant", "primary")
        self.monitor_button.clicked.connect(self.monitor_requested.emit)
        self.history_button = QPushButton("View History")
        self.history_button.clicked.connect(self.history_requested.emit)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.monitor_button)
        actions.addWidget(self.history_button)
        actions.addStretch()
        actions.addWidget(self.refresh_button)
        layout.addLayout(actions)

        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(12)
        self.completed_value = self._metric(
            summary_grid, 0, "Completed Sessions", "Session ที่เสร็จสมบูรณ์"
        )
        self.time_value = self._metric(
            summary_grid, 1, "Active Time", "ไม่รวมเวลาที่ Pause"
        )
        self.alerts_value = self._metric(
            summary_grid, 2, "Alert Events", "จาก Report ที่บันทึกแล้ว"
        )
        self.interrupted_value = self._metric(
            summary_grid, 3, "Interrupted Sessions", "ไม่นำมารวมใน Active Time"
        )
        layout.addLayout(summary_grid)

        self.data_status = self._label(
            "กด Refresh เพื่อโหลดข้อมูล Session และ Report", "muted"
        )
        layout.addWidget(self.data_status)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(self._build_usage_card(), 3)
        columns.addLayout(self._build_insights_column(), 2)
        layout.addLayout(columns)
        layout.addStretch()

    def _build_usage_card(self):
        card, layout = self._card()
        layout.addWidget(self._label("Recent Sessions", "heading"))
        layout.addWidget(self._label(
            "Session ล่าสุดพร้อมผล Prototype Risk และ Alert ที่บันทึกจริง",
            "muted",
        ))
        self.recent_table = QTableWidget(0, 6)
        self.recent_table.setHorizontalHeaderLabels(
            ("Session", "Started", "Status", "Active Time", "Risk", "Alerts")
        )
        self.recent_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.recent_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setMinimumHeight(300)
        self.recent_table.cellDoubleClicked.connect(
            lambda *_: self.history_requested.emit()
        )
        layout.addWidget(self.recent_table)
        self.empty_label = self._label("ยังไม่ได้โหลดข้อมูล", "muted")
        layout.addWidget(self.empty_label)
        return card

    def _build_insights_column(self):
        column = QVBoxLayout()

        risk, risk_layout = self._card()
        risk_layout.addWidget(self._label("Prototype Risk", "heading"))
        self.risk_value = self._label("N/A", "metric")
        self.risk_note = self._label(
            "รอข้อมูลจาก Session Report (คะแนนต้นแบบ 0–3)", "muted"
        )
        risk_layout.addWidget(self.risk_value)
        risk_layout.addWidget(self.risk_note)
        column.addWidget(risk)

        blink, blink_layout = self._card()
        blink_layout.addWidget(self._label("Blink Rate", "heading"))
        self.blink_value = self._label("N/A", "metric")
        self.blink_note = self._label(
            "รอข้อมูลจากช่วงตรวจจับดวงตาครบ 60 วินาที", "muted"
        )
        blink_layout.addWidget(self.blink_value)
        blink_layout.addWidget(self.blink_note)
        column.addWidget(blink)
        column.addStretch()
        return column

    @staticmethod
    def _label(text, role):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setProperty("role", role)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _card(variant=None):
        card = QFrame()
        card.setProperty("card", True)
        if variant:
            card.setProperty("variant", variant)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        return card, layout

    def _metric(self, grid, column, title, note):
        card, layout = self._card()
        layout.addWidget(self._label(title, "muted"))
        value = self._label("--", "metric")
        layout.addWidget(value)
        layout.addWidget(self._label(note, "muted"))
        grid.addWidget(card, 0, column)
        grid.setColumnStretch(column, 1)
        return value

    def set_monitoring_state(
        self, session_id, paused=False, stopping=False, camera_ready=True
    ):
        if stopping:
            title = "กำลังบันทึก Session..."
            note = "โปรดรอขณะระบบจบ Session และบันทึก Report"
        elif session_id is not None:
            state = "Paused" if paused else "Running"
            title = f"Session {session_id} — {state}"
            note = (
                "การตรวจจับหยุดชั่วคราว กลับไปที่ Monitoring เมื่อต้องการทำต่อ"
                if paused
                else "กล้องยังตรวจจับต่อเนื่องเมื่อเปิด Dashboard หรือ History"
            )
            if not camera_ready:
                title = f"Session {session_id} — Action Required"
                note = "กล้องหยุดทำงาน โปรดกลับไปที่ Monitoring และจบ Session"
        else:
            title = "พร้อมเมื่อคุณพร้อม"
            note = "เลือกกล้อง ตรวจสอบ Camera Preview และบันทึก Personal Baseline"
        self.live_label.setText(title)
        self.live_note.setText(note)
        self.monitor_button.setText(
            "Return to Monitoring" if session_id is not None else "Start Monitoring"
        )
        self.monitor_button.setEnabled(not stopping)

    def refresh(self):
        if self._loader is not None:
            return
        self.refresh_button.setEnabled(False)
        self.data_status.setText("กำลังโหลดข้อมูล Session และ Report...")
        self._loader = _DashboardLoader()
        self._loader.signals.finished.connect(self._loaded)
        QThreadPool.globalInstance().start(self._loader)

    def _reset_report_metrics(self, unavailable=False):
        self.alerts_value.setText("N/A" if unavailable else "0")
        self.risk_value.setText("N/A")
        self.blink_value.setText("N/A")
        self.risk_note.setText("ยังไม่มี Prototype Risk ที่บันทึกใน Report")
        self.blink_note.setText("ยังไม่มี Blink Rate ที่บันทึกใน Report")

    def _update_report_metrics(self, summaries):
        insights = summary_insights(summaries)
        if insights is None:
            self._reset_report_metrics(unavailable=True)
            return

        self.alerts_value.setText(str(insights["total_alert_count"]))
        average_risk = insights["average_risk"]
        maximum_risk = insights["maximum_risk"]
        if average_risk is None:
            self.risk_value.setText("N/A")
            self.risk_note.setText("ยังไม่มี Prototype Risk ที่บันทึกใน Report")
        else:
            self.risk_value.setText(f"{average_risk:.1f} / 3")
            maximum_text = (
                f" | สูงสุด {maximum_risk:.1f}/3"
                if maximum_risk is not None else ""
            )
            self.risk_note.setText(
                f"ค่าเฉลี่ยจาก {insights['risk_report_count']} Report{maximum_text}"
            )

        average_blink = insights["average_blink_rate"]
        if average_blink is None:
            self.blink_value.setText("N/A")
            self.blink_note.setText("ยังไม่มี Blink Rate ที่บันทึกใน Report")
        else:
            self.blink_value.setText(f"{average_blink:.1f} / min")
            self.blink_note.setText(
                f"ค่าเฉลี่ยจาก {insights['blink_report_count']} Report"
            )

    @Slot(object, str)
    def _loaded(self, payload, error):
        self._loader = None
        self.refresh_button.setEnabled(True)
        self.recent_table.setRowCount(0)
        if error:
            for label in (
                self.completed_value, self.time_value,
                self.alerts_value, self.interrupted_value,
            ):
                label.setText("--")
            self._reset_report_metrics(unavailable=True)
            self.alerts_value.setText("--")
            self.empty_label.setText("ไม่สามารถโหลดข้อมูล Session ได้")
            self.empty_label.show()
            self.data_status.setText(error)
            return

        sessions = payload["sessions"]
        summaries = payload["summaries"]
        summary_by_session = {
            summary.get("session_id"): summary
            for summary in summaries or []
            if type(summary.get("session_id")) is int
        }

        completed = [
            session for session in sessions
            if session.get("status") == "COMPLETED"
        ]
        known = [
            value for value in (active_seconds(session) for session in completed)
            if value is not None
        ]
        self.completed_value.setText(str(len(completed)))
        self.interrupted_value.setText(str(sum(
            session.get("status") == "INTERRUPTED" for session in sessions
        )))
        self.time_value.setText(
            duration_text(sum(known)) if known or not completed else "N/A"
        )
        self._update_report_metrics(summaries)

        missing_duration = len(completed) - len(known)
        note = (
            f"อัปเดตเมื่อ {datetime.now().strftime('%H:%M:%S')}"
            f" | {len(sessions)} Session | {len(summaries or [])} Report"
        )
        if missing_duration:
            note += f" | {missing_duration} Session ไม่มีข้อมูลระยะเวลา"
        if payload.get("report_error"):
            note += " | ไม่สามารถโหลด Report metrics ได้"
        self.data_status.setText(note)

        recent = sessions[:5]
        self.recent_table.setRowCount(len(recent))
        for row, session in enumerate(recent):
            started = session.get("started_at")
            try:
                parsed = datetime.fromisoformat(started.replace("Z", "+00:00"))
                started = (
                    parsed.astimezone() if parsed.tzinfo else parsed
                ).strftime("%d %b %Y %H:%M")
            except (ValueError, TypeError, AttributeError):
                started = "N/A"

            report = summary_by_session.get(session.get("session_id"))
            risk = _risk_number(report.get("average_risk_score")) if report else None
            alerts = report.get("total_alert_count") if report else None
            values = (
                session.get("session_id", "N/A"), started,
                session.get("status", "N/A"),
                duration_text(active_seconds(session)),
                f"{risk:.1f}/3" if risk is not None else "N/A",
                alerts if type(alerts) is int and alerts >= 0 else "N/A",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.recent_table.setItem(row, column, item)

        self.empty_label.setText(
            "ยังไม่มี Session เริ่มการตรวจจับครั้งแรกได้จากด้านบน"
        )
        self.empty_label.setVisible(not sessions)
