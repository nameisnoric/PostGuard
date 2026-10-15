"""Dashboard: real session totals, live state, and clearly unavailable insights."""

import math
from datetime import datetime

import requests
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
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
            if not isinstance(sessions, list) or any(not isinstance(s, dict) for s in sessions):
                raise ValueError("Invalid session response")
            self.signals.finished.emit(sessions, "")
        except (requests.RequestException, ValueError):
            self.signals.finished.emit(None, "Cannot load saved activity. Use Refresh to retry.")


def active_seconds(session):
    if session.get("status") != "COMPLETED":
        return None
    total, paused = session.get("total_duration"), session.get("paused_duration")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (total, paused)):
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
        self.setObjectName("dashboard")
        self.setStyleSheet("""
            QWidget#dashboard { background: #101923; color: #e8eef5; }
            QWidget#dashboard QLabel { color: #e8eef5; background: transparent; }
            QFrame[card="true"] { background: #192633; border: 1px solid #304252; border-radius: 12px; }
            QLabel[kind="muted"] { color: #a5b6c7; }
            QLabel[kind="value"] { font-size: 27px; font-weight: 600; color: #73dfc4; }
            QLabel[kind="heading"] { font-size: 23px; font-weight: 600; }
            QPushButton { padding: 10px 16px; border-radius: 7px; background: #263c4c; color: #e8eef5; }
            QPushButton:hover { background: #34546a; }
            QPushButton:disabled { color: #8095a6; }
            QPushButton#primary { background: #68d9bc; color: #102b27; font-weight: 600; }
            QTableWidget { background: #192633; color: #e8eef5; border: 0; gridline-color: #304252; }
            QHeaderView::section { background: #233544; color: #c7d5e2; border: 0; padding: 9px; }
            QScrollArea { border: 0; background: transparent; }
        """)
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("dashboardContent")
        content.setStyleSheet("QWidget#dashboardContent { background: #101923; }")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(self._label("YOUR WORKDAY", "muted"))
        name = user_data.get("full_name") or user_data.get("username") or "User"
        titles.addWidget(self._label(f"Welcome back, {name}", "heading"))
        titles.addWidget(self._label("Your monitoring activity, all in one place.", "muted"))
        header.addLayout(titles, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        hero, hero_layout = self._card()
        hero_layout.addWidget(self._label("LIVE MONITORING", "muted"))
        self.live_label = self._label("Ready when you are", "heading")
        self.live_note = self._label("Choose your camera and save a baseline to start.", "muted")
        hero_layout.addWidget(self.live_label)
        hero_layout.addWidget(self.live_note)
        actions = QHBoxLayout()
        self.monitor_button = QPushButton("Start Monitoring")
        self.monitor_button.setObjectName("primary")
        self.monitor_button.clicked.connect(self.monitor_requested.emit)
        self.history_button = QPushButton("View History")
        self.history_button.clicked.connect(self.history_requested.emit)
        actions.addWidget(self.monitor_button)
        actions.addWidget(self.history_button)
        actions.addStretch()
        hero_layout.addLayout(actions)
        layout.addWidget(hero)

        cards = QGridLayout()
        self.completed_value = self._metric(cards, 0, "COMPLETED SESSIONS", "All completed session records")
        self.time_value = self._metric(cards, 1, "ACTIVE MONITORING TIME", "Completed sessions, excluding pauses")
        self.interrupted_value = self._metric(cards, 2, "INTERRUPTED SESSIONS", "Incomplete records excluded from time")
        layout.addLayout(cards)
        self.data_status = self._label("Refresh to load your saved activity.", "muted")
        layout.addWidget(self.data_status)

        recent, recent_layout = self._card()
        recent_layout.addWidget(self._label("Recent sessions", "heading"))
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(["Session", "Started", "Status", "Active time"])
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setMinimumHeight(210)
        self.recent_table.cellDoubleClicked.connect(lambda *_: self.history_requested.emit())
        recent_layout.addWidget(self.recent_table)
        self.empty_label = self._label("No data loaded yet.", "muted")
        recent_layout.addWidget(self.empty_label)
        recent_layout.addWidget(self._label("Open History to select a session and view its saved report.", "muted"))
        layout.addWidget(recent)

        upcoming, upcoming_layout = self._card()
        upcoming_layout.addWidget(self._label("Posture insights - Coming soon", "heading"))
        upcoming_layout.addWidget(self._label(
            "Full risk score: N/A    |    Blink rate: N/A\n"
            "These features are not available yet. No estimated scores are shown.", "muted"
        ))
        layout.addWidget(upcoming)
        layout.addStretch()

    @staticmethod
    def _label(text, kind):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setProperty("kind", kind)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _card():
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        return card, layout

    def _metric(self, grid, column, title, note):
        card, layout = self._card()
        layout.addWidget(self._label(title, "muted"))
        value = self._label("--", "value")
        layout.addWidget(value)
        layout.addWidget(self._label(note, "muted"))
        grid.addWidget(card, 0, column)
        grid.setColumnStretch(column, 1)
        return value

    def set_monitoring_state(self, session_id, paused=False, stopping=False, camera_ready=True):
        if stopping:
            title, note = "Saving your session...", "Please wait while your session ends and the report is saved."
        elif session_id is not None:
            title = f"Session {session_id} - {'Paused' if paused else 'Running'}"
            note = "Monitoring is paused; the camera remains open." if paused else "Camera is on. Detection continues when you switch pages."
            if not camera_ready:
                title, note = f"Session {session_id} - Action needed", "Detection stopped. Return to Monitoring to retry ending this session."
        else:
            title, note = "Ready when you are", "Choose your camera and save a baseline to start."
        self.live_label.setText(title)
        self.live_note.setText(note)
        self.monitor_button.setText("Return to Monitoring" if session_id is not None else "Start Monitoring")
        self.monitor_button.setEnabled(not stopping)

    def refresh(self):
        if self._loader is not None:
            return
        self.refresh_button.setEnabled(False)
        self.data_status.setText("Loading saved activity...")
        self._loader = _SessionLoader()
        self._loader.signals.finished.connect(self._loaded)
        QThreadPool.globalInstance().start(self._loader)

    @Slot(object, str)
    def _loaded(self, sessions, error):
        self._loader = None
        self.refresh_button.setEnabled(True)
        self.recent_table.setRowCount(0)
        if error:
            for label in (self.completed_value, self.time_value, self.interrupted_value):
                label.setText("--")
            self.empty_label.setText("Session data unavailable.")
            self.empty_label.show()
            self.data_status.setText(error)
            return
        completed = [s for s in sessions if s.get("status") == "COMPLETED"]
        known = [v for v in (active_seconds(s) for s in completed) if v is not None]
        self.completed_value.setText(str(len(completed)))
        self.interrupted_value.setText(str(sum(s.get("status") == "INTERRUPTED" for s in sessions)))
        self.time_value.setText(duration_text(sum(known)) if known or not completed else "N/A")
        missing = len(completed) - len(known)
        note = f"Updated {datetime.now().strftime('%H:%M:%S')} | All-time saved activity"
        if missing:
            note += f" | {missing} completed session(s) excluded: duration unavailable"
        self.data_status.setText(note)
        # GET /sessions returns newest first.
        recent = sessions[:5]
        self.recent_table.setRowCount(len(recent))
        for row, session in enumerate(recent):
            started = session.get("started_at")
            try:
                parsed = datetime.fromisoformat(started.replace("Z", "+00:00"))
                started = (parsed.astimezone() if parsed.tzinfo else parsed).strftime("%d %b %Y %H:%M")
            except (ValueError, TypeError, AttributeError):
                started = "N/A"
            values = (session.get("session_id", "N/A"), started, session.get("status", "N/A"), duration_text(active_seconds(session)))
            for column, value in enumerate(values):
                self.recent_table.setItem(row, column, QTableWidgetItem(str(value)))
        self.empty_label.setText("No sessions yet. Start your first monitoring session above.")
        self.empty_label.setVisible(not sessions)
