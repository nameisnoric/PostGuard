"""Dashboard backed by saved sessions and their persisted reports."""

import math
from datetime import datetime

import requests
from PySide6.QtCore import (
    QObject, QPointF, QRectF, QRunnable, QThreadPool, Qt, Signal, Slot,
)
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.services.api_client import APIClient
from app.ui.utils.risk_display import format_rula_percent, rula_score_to_percent


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
    return value if value is not None and 1 <= value <= 7 else None


def _adapted_risk_label(score):
    if score <= 2:
        return "ต่ำ"
    if score <= 4:
        return "ปานกลาง"
    if score <= 6:
        return "สูง"
    return "สูงมาก"


def _nonnegative_number(value):
    value = _finite_number(value)
    return value if value is not None and value >= 0 else None


def rula_trend_points(sessions, summaries, limit=12):
    """Build oldest-to-newest RULA points from persisted session reports."""
    if not isinstance(sessions, list) or not isinstance(summaries, list):
        return []
    reports = {
        row.get("session_id"): row
        for row in summaries
        if isinstance(row, dict)
        and type(row.get("session_id")) is int
        and row.get("risk_score_method") == "RULA_ADAPTED_FRONT_V1"
    }
    points = []
    for position, session in enumerate(sessions):
        if not isinstance(session, dict):
            continue
        session_id = session.get("session_id")
        report = reports.get(session_id)
        if report is None:
            continue
        average = _risk_number(report.get("average_risk_score"))
        maximum = _risk_number(report.get("maximum_risk_score"))
        if average is None and maximum is None:
            continue
        started_at = session.get("started_at")
        try:
            parsed = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            sort_key = (1, parsed.timestamp())
            date_label = parsed.astimezone().strftime("%d %b")
        except (ValueError, TypeError, AttributeError, OSError):
            sort_key = (0, session_id if type(session_id) is int else -position)
            date_label = ""
        points.append({
            "session_id": session_id,
            "average": rula_score_to_percent(average),
            "maximum": rula_score_to_percent(maximum),
            "date_label": date_label,
            "sort_key": sort_key,
        })
    points.sort(key=lambda row: row["sort_key"])
    return points[-max(1, int(limit)):]


class RulaTrendChart(QWidget):
    """Dependency-free chart for persisted RULA-adapted session scores."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.setMinimumHeight(300)
        self.setAccessibleName("RULA score trend")
        self.setAccessibleDescription(
            "Average and maximum RULA-adapted risk percentages ordered by monitoring session."
        )

    def set_points(self, points):
        self.points = list(points or [])
        self.update()

    @staticmethod
    def _score_y(score, plot):
        return plot.bottom() - (float(score) / 100.0) * plot.height()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        plot = QRectF(52, 30, max(1, self.width() - 76), max(1, self.height() - 78))

        bands = (
            (0, 100 / 6, QColor(220, 252, 231, 150)),
            (100 / 6, 50, QColor(254, 249, 195, 135)),
            (50, 500 / 6, QColor(255, 237, 213, 140)),
            (500 / 6, 100, QColor(254, 226, 226, 150)),
        )
        for low, high, color in bands:
            top = self._score_y(high, plot)
            bottom = self._score_y(low, plot)
            painter.fillRect(QRectF(plot.left(), top, plot.width(), bottom - top), color)

        painter.setPen(QPen(QColor("#d8e1ee"), 1))
        for score in range(0, 101, 20):
            y = self._score_y(score, plot)
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QPen(QColor("#52627a"), 1))
            painter.drawText(QRectF(4, y - 9, 42, 18), Qt.AlignmentFlag.AlignRight, f"{score}%")
            painter.setPen(QPen(QColor("#d8e1ee"), 1))

        if not self.points:
            painter.setPen(QColor("#60708a"))
            painter.drawText(
                plot,
                Qt.AlignmentFlag.AlignCenter,
                "No saved RULA-adapted risk percentages yet",
            )
            return

        count = len(self.points)
        x_positions = [
            plot.center().x()
            if count == 1
            else plot.left() + index * plot.width() / (count - 1)
            for index in range(count)
        ]

        def draw_series(field, color, width):
            samples = [
                QPointF(x, self._score_y(row[field], plot))
                for x, row in zip(x_positions, self.points)
                if row.get(field) is not None
            ]
            painter.setPen(QPen(QColor(color), width))
            if len(samples) > 1:
                painter.drawPolyline(QPolygonF(samples))
            painter.setBrush(QColor(color))
            for sample in samples:
                painter.drawEllipse(sample, 4.0, 4.0)
            painter.setBrush(Qt.BrushStyle.NoBrush)

        draw_series("maximum", "#ef4444", 2)
        draw_series("average", "#2563eb", 3)

        painter.setPen(QColor("#52627a"))
        label_step = max(1, math.ceil(count / 6))
        for index, (x, row) in enumerate(zip(x_positions, self.points)):
            if index % label_step and index != count - 1:
                continue
            label = f"#{row.get('session_id', '--')}"
            if row.get("date_label"):
                label += f"\n{row['date_label']}"
            painter.drawText(
                QRectF(x - 38, plot.bottom() + 7, 76, 36),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )

        painter.setPen(QPen(QColor("#2563eb"), 3))
        painter.drawLine(QPointF(plot.left(), 12), QPointF(plot.left() + 22, 12))
        painter.setPen(QColor("#26364d"))
        painter.drawText(QPointF(plot.left() + 28, 17), "Average")
        painter.setPen(QPen(QColor("#ef4444"), 2))
        painter.drawLine(QPointF(plot.left() + 100, 12), QPointF(plot.left() + 122, 12))
        painter.setPen(QColor("#26364d"))
        painter.drawText(QPointF(plot.left() + 128, 17), "Maximum")


def summary_insights(summaries):
    """Aggregate only persisted measurements; missing values remain unavailable."""
    if summaries is None:
        return None

    average_risks = [
        value
        for summary in summaries
        if summary.get("risk_score_method") == "RULA_ADAPTED_FRONT_V1"
        and (value := _risk_number(summary.get("average_risk_score"))) is not None
    ]
    maximum_risks = [
        value
        for summary in summaries
        if summary.get("risk_score_method") == "RULA_ADAPTED_FRONT_V1"
        and (value := _risk_number(summary.get("maximum_risk_score"))) is not None
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
        layout.addWidget(self._build_rula_trend_card())
        layout.addStretch()

    def _build_usage_card(self):
        card, layout = self._card()
        layout.addWidget(self._label("Recent Sessions", "heading"))
        layout.addWidget(self._label(
            "Session ล่าสุดพร้อม RULA-adapted Risk Score และ Alert ที่บันทึกจริง",
            "muted",
        ))
        self.recent_table = QTableWidget(0, 6)
        self.recent_table.setHorizontalHeaderLabels(
            ("Session", "Started", "Status", "Active Time", "Risk Score", "Alerts")
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
        risk_layout.addWidget(self._label("RULA-adapted Risk Score", "heading"))
        self.risk_value = self._label("N/A", "metric")
        self.risk_note = self._label(
            "เปอร์เซ็นต์ 0–100% สำหรับกล้องด้านหน้า", "muted"
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

    def _build_rula_trend_card(self):
        card, layout = self._card()
        layout.addWidget(self._label("RULA Score Trend", "heading"))
        self.risk_trend_note = self._label(
            "Average and maximum RULA-adapted risk percentage by completed session.",
            "muted",
        )
        layout.addWidget(self.risk_trend_note)
        self.risk_trend_chart = RulaTrendChart()
        layout.addWidget(self.risk_trend_chart)
        return card

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
        self.risk_trend_chart.set_points([])
        self.risk_trend_note.setText(
            "Saved report metrics are temporarily unavailable."
            if unavailable
            else "No saved RULA-adapted scores yet."
        )
        self.risk_note.setText("ยังไม่มี RULA-adapted Risk Score ใน Report")
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
            self.risk_note.setText("ยังไม่มี RULA-adapted Risk Score ใน Report")
        else:
            self.risk_value.setText(format_rula_percent(average_risk, 1))
            maximum_text = (
                f" | สูงสุด {format_rula_percent(maximum_risk, 1)} ({_adapted_risk_label(maximum_risk)})"
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
        trend = rula_trend_points(sessions, summaries or [])
        self.risk_trend_chart.set_points(trend)
        if summaries is None:
            self.risk_trend_note.setText(
                "Saved report metrics are temporarily unavailable."
            )
        elif trend:
            self.risk_trend_note.setText(
                f"Oldest to newest across {len(trend)} session(s). "
                "Blue = average, red = maximum; lower percentages indicate lower risk."
            )
        else:
            self.risk_trend_note.setText(
                "No completed session has a saved RULA-adapted score yet."
            )

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
            method = report.get("risk_score_method") if report else None
            raw_risk = report.get("average_risk_score") if report else None
            risk = (
                _risk_number(raw_risk)
                if method == "RULA_ADAPTED_FRONT_V1"
                else _finite_number(raw_risk)
            )
            risk_text = (
                format_rula_percent(risk, 1)
                if method == "RULA_ADAPTED_FRONT_V1"
                else f"{risk:.1f}/3" if risk is not None else "N/A"
            )
            alerts = report.get("total_alert_count") if report else None
            values = (
                session.get("session_id", "N/A"), started,
                session.get("status", "N/A"),
                duration_text(active_seconds(session)),
                risk_text,
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
