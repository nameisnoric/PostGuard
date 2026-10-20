"""Dashboard with real session totals and explicit unavailable insights."""

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


class _SessionLoader(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = _LoadSignals()

    def run(self):
        try:
            response = APIClient.get_sessions()
            if not response.ok:
                raise ValueError(f"Server returned HTTP {response.status_code}")
            sessions = response.json()
            if not isinstance(sessions, list) or any(
                not isinstance(session, dict) for session in sessions
            ):
                raise ValueError("Invalid session response")
            self.signals.finished.emit(sessions, "")
        except (requests.RequestException, ValueError):
            self.signals.finished.emit(
                None, "Cannot load saved activity. Use Refresh to retry."
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
            "ตรวจสอบเซสชันที่บันทึกไว้ หรือทำเซสชันปัจจุบันต่อ",
            "muted",
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
            "เลือกกล้อง ตรวจสอบภาพตัวอย่าง และบันทึกค่าท่าทางอ้างอิง", "muted"
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
            summary_grid, 0, "เซสชันที่เสร็จสิ้น", "รายงานที่บันทึก"
        )
        self.time_value = self._metric(
            summary_grid, 1, "เวลาตรวจจับจริง", "ไม่รวมเวลาหยุดชั่วคราว"
        )
        self.interrupted_value = self._metric(
            summary_grid, 2, "เซสชันที่ถูกขัดจังหวะ", "ไม่นำมารวมเวลา"
        )
        layout.addLayout(summary_grid)

        self.data_status = self._label(
            "กด Refresh เพื่อโหลดกิจกรรมที่บันทึกไว้", "muted"
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
        layout.addWidget(self._label("ประวัติการใช้งาน", "heading"))
        layout.addWidget(self._label(
            "เซสชันล่าสุด โดยเวลาตรวจจับไม่รวมช่วงที่หยุดชั่วคราว", "muted"
        ))
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(
            ['เซสชัน', 'เริ่มเมื่อ', 'สถานะ', 'เวลาตรวจจับ']
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
        risk_layout.addWidget(self._label("ประวัติคะแนนความเสี่ยง", "heading"))
        risk_layout.addWidget(self._label(
            'N/A\nยังไม่ได้เชื่อมต่อการคำนวณความเสี่ยงแบบเต็ม จึงไม่แสดงคะแนนตัวอย่าง',
            "muted",
        ))
        column.addWidget(risk)
        blink, blink_layout = self._card()
        blink_layout.addWidget(self._label("ประวัติอัตราการกะพริบตา", "heading"))
        blink_layout.addWidget(self._label(
            'N/A\nยังไม่ได้เชื่อมต่อการตรวจการกะพริบตา ส่วนนี้สงวนไว้สำหรับข้อมูลในอนาคต',
            "muted",
        ))
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
            title = "กำลังบันทึกเซสชัน..."
            note = "โปรดรอขณะระบบจบเซสชันและบันทึกรายงาน"
        elif session_id is not None:
            title = f"เซสชัน {session_id} - {'หยุดชั่วคราว' if paused else 'กำลังตรวจจับ'}"
            note = (
                "การตรวจจับหยุดชั่วคราว เริ่มเซสชันนี้ต่อเมื่อพร้อม"
                if paused
                else "กล้องกำลังทำงาน และจะตรวจจับต่อเนื่องเมื่อเปลี่ยนหน้า"
            )
            if not camera_ready:
                title = f"เซสชัน {session_id} - ต้องดำเนินการ"
                note = "การตรวจจับหยุดแล้ว โปรดกลับไปหน้าการตรวจจับและจบเซสชัน"
        else:
            title = "พร้อมเมื่อคุณพร้อม"
            note = "เลือกกล้อง ตรวจสอบภาพตัวอย่าง และบันทึกค่าท่าทางอ้างอิง"
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
        self.data_status.setText('กำลังโหลดกิจกรรมที่บันทึกไว้...')
        self._loader = _SessionLoader()
        self._loader.signals.finished.connect(self._loaded)
        QThreadPool.globalInstance().start(self._loader)

    @Slot(object, str)
    def _loaded(self, sessions, error):
        self._loader = None
        self.refresh_button.setEnabled(True)
        self.recent_table.setRowCount(0)
        if error:
            for label in (
                self.completed_value, self.time_value, self.interrupted_value
            ):
                label.setText("--")
            self.empty_label.setText('ไม่สามารถเรียกข้อมูลเซสชันได้')
            self.empty_label.show()
            self.data_status.setText(error)
            return

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
        missing = len(completed) - len(known)
        note = f"อัปเดตเมื่อ {datetime.now().strftime('%H:%M:%S')} | กิจกรรมที่บันทึกทั้งหมด"
        if missing:
            note += f" | ไม่รวมเซสชันที่เสร็จแล้ว {missing} รายการ เนื่องจากไม่มีข้อมูลระยะเวลา"
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
            values = (
                session.get("session_id", "N/A"), started,
                session.get("status", "N/A"),
                duration_text(active_seconds(session)),
            )
            for column, value in enumerate(values):
                self.recent_table.setItem(
                    row, column, QTableWidgetItem(str(value))
                )
        self.empty_label.setText(
            'ยังไม่มีเซสชัน เริ่มการตรวจจับครั้งแรกได้จากด้านบน'
        )
        self.empty_label.setVisible(not sessions)
