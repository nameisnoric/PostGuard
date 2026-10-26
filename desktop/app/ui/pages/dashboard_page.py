"""PostGuard Dashboard using persisted Session and Risk Score data."""

import math
from datetime import datetime

import requests

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.api_client import APIClient
from app.services.session_summary_service import (
    load_session_summary,
)
from app.services.session_risk_insight_service import (
    build_session_risk_insight,
    build_session_risk_trend_series,
    risk_trend_description,
    risk_trend_label,
)

from app.ui.session_risk_trend_chart import (
    SessionRiskTrendChart,
)
from app.ui.dialogs.saved_session_report_dialog import (
    SavedSessionReportDialog,
)


# ============================================================
# BACKGROUND LOAD
# ============================================================

class _LoadSignals(QObject):
    finished = Signal(
        object,
        object,
        str,
    )


class _DashboardLoader(QRunnable):
    """
    Load Sessions and Session Summaries outside the Qt UI thread.
    """

    def __init__(self):
        super().__init__()

        self.signals = _LoadSignals()

    def run(self):
        try:
            # ------------------------------------------------
            # Sessions
            # ------------------------------------------------

            session_response = (
                APIClient.get_sessions()
            )

            if not session_response.ok:
                raise ValueError(
                    "Session API returned HTTP "
                    f"{session_response.status_code}"
                )

            sessions = (
                session_response.json()
            )

            if (
                not isinstance(sessions, list)
                or
                any(
                    not isinstance(session, dict)
                    for session in sessions
                )
            ):
                raise ValueError(
                    "Invalid Session response"
                )

            # ------------------------------------------------
            # Summaries
            # ------------------------------------------------

            summary_response = (
                APIClient
                .get_session_summaries()
            )

            if not summary_response.ok:
                raise ValueError(
                    "Summary API returned HTTP "
                    f"{summary_response.status_code}"
                )

            summaries = (
                summary_response.json()
            )

            if (
                not isinstance(summaries, list)
                or
                any(
                    not isinstance(summary, dict)
                    for summary in summaries
                )
            ):
                raise ValueError(
                    "Invalid Summary response"
                )

            self.signals.finished.emit(
                sessions,
                summaries,
                "",
            )

        except (
            requests.RequestException,
            ValueError,
            TypeError,
        ):
            self.signals.finished.emit(
                None,
                None,
                (
                    "Cannot load saved activity. "
                    "Use Refresh to retry."
                ),
            )


# ============================================================
# HELPERS
# ============================================================

def active_seconds(session):
    """
    Return active monitoring time for a completed Session.

    active_seconds =
        total_duration - paused_duration
    """

    if not isinstance(session, dict):
        return None

    if (
        session.get("status")
        !=
        "COMPLETED"
    ):
        return None

    total = session.get(
        "total_duration"
    )

    paused = session.get(
        "paused_duration"
    )

    if any(
        (
            type(value)
            not in (int, float)
            or
            not math.isfinite(value)
        )
        for value in (total, paused)
    ):
        return None

    if (
        total < 0
        or
        paused < 0
        or
        paused > total
    ):
        return None

    return int(
        total - paused
    )


def duration_text(seconds):
    if seconds is None:
        return "N/A"

    try:
        seconds = int(seconds)
    except (
        TypeError,
        ValueError,
    ):
        return "N/A"

    if seconds < 0:
        return "N/A"

    hours, rest = divmod(
        seconds,
        3600,
    )

    minutes, seconds = divmod(
        rest,
        60,
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def number_text(value):
    if (
        type(value)
        not in (int, float)
    ):
        return "N/A"

    value = float(value)

    if not math.isfinite(value):
        return "N/A"

    return f"{value:.2f}"


def local_datetime_text(value):
    if not isinstance(value, str):
        return "N/A"

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo:
            parsed = (
                parsed.astimezone()
            )

        return parsed.strftime(
            "%d %b %Y %H:%M"
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
    ):
        return "N/A"


# ============================================================
# DASHBOARD
# ============================================================

class DashboardPage(QWidget):
    monitor_requested = Signal()
    history_requested = Signal()

    def __init__(
        self,
        user_data: dict,
    ):
        super().__init__()

        self._loader = None

        self.sessions = []
        self.summaries = []

        self.summary_by_session_id = {}

        self.current_risk_insight = (
            build_session_risk_insight(
                [],
                [],
            )
        )

        self.setProperty(
            "page",
            True,
        )

        # ====================================================
        # PAGE
        # ====================================================

        page_layout = QVBoxLayout(
            self
        )

        page_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        page_layout.addWidget(
            scroll
        )

        content = QWidget()

        content.setProperty(
            "page",
            True,
        )

        layout = QVBoxLayout(
            content
        )

        layout.setContentsMargins(
            32,
            24,
            32,
            32,
        )

        layout.setSpacing(
            16
        )

        scroll.setWidget(
            content
        )

        # ====================================================
        # WELCOME
        # ====================================================

        welcome, welcome_layout = (
            self._card(
                "welcome"
            )
        )

        welcome_row = QHBoxLayout()
        welcome_copy = QVBoxLayout()

        name = (
            user_data.get("full_name")
            or
            user_data.get("username")
            or
            "User"
        )

        welcome_copy.addWidget(
            self._label(
                f"Welcome back, {name}",
                "title",
            )
        )

        welcome_copy.addWidget(
            self._label(
                (
                    "ภาพรวมการตรวจจับ "
                    "Risk Score และรายงานล่าสุด"
                ),
                "muted",
            )
        )

        welcome_row.addLayout(
            welcome_copy,
            1,
        )

        welcome_row.addWidget(
            self._label(
                "POSTGUARD DESKTOP",
                "eyebrow",
            ),
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        welcome_layout.addLayout(
            welcome_row
        )

        layout.addWidget(
            welcome
        )

        # ====================================================
        # LIVE SESSION STATE
        # ====================================================

        self.live_label = self._label(
            "พร้อมเมื่อคุณพร้อม",
            "heading",
        )

        self.live_note = self._label(
            (
                "เลือกกล้อง ตรวจสอบภาพตัวอย่าง "
                "และบันทึกค่าท่าทางอ้างอิง"
            ),
            "muted",
        )

        layout.addWidget(
            self.live_label
        )

        layout.addWidget(
            self.live_note
        )

        # ====================================================
        # ACTIONS
        # ====================================================

        actions = QHBoxLayout()

        self.monitor_button = QPushButton(
            "Start Monitoring"
        )

        self.monitor_button.setProperty(
            "variant",
            "primary",
        )

        self.monitor_button.clicked.connect(
            self.monitor_requested.emit
        )

        self.history_button = QPushButton(
            "View History"
        )

        self.history_button.clicked.connect(
            self.history_requested.emit
        )

        self.refresh_button = QPushButton(
            "Refresh"
        )

        self.refresh_button.clicked.connect(
            self.refresh
        )

        actions.addWidget(
            self.monitor_button
        )

        actions.addWidget(
            self.history_button
        )

        actions.addStretch()

        actions.addWidget(
            self.refresh_button
        )

        layout.addLayout(
            actions
        )

        # ====================================================
        # SESSION METRICS
        # ====================================================

        summary_grid = QGridLayout()

        summary_grid.setHorizontalSpacing(
            12
        )

        self.completed_value = self._metric(
            summary_grid,
            0,
            "เซสชันที่เสร็จสิ้น",
            "Completed Sessions",
        )

        self.time_value = self._metric(
            summary_grid,
            1,
            "เวลาตรวจจับจริง",
            "ไม่รวมเวลาหยุดชั่วคราว",
        )

        self.interrupted_value = self._metric(
            summary_grid,
            2,
            "เซสชันที่ถูกขัดจังหวะ",
            "ไม่นำมารวมใน Risk Report",
        )

        layout.addLayout(
            summary_grid
        )

        # ====================================================
        # SESSION RISK INSIGHT
        # ====================================================

        risk_grid = QGridLayout()

        risk_grid.setHorizontalSpacing(
            12
        )

        self.overall_risk_value = self._metric(
            risk_grid,
            0,
            "Overall Session Risk",
            "คะแนนเฉลี่ย 0-100 ของ Session ล่าสุด",
        )

        # Compatibility with Task 4.2/4.3 tests/code.
        # Latest AVG and Overall Session Risk mean the same
        # persisted average_risk_score.
        self.latest_average_value = (
            self.overall_risk_value
        )

        self.risk_trend_value = self._metric(
            risk_grid,
            1,
            "Risk Trend",
            (
                "เทียบกับ Session ก่อนหน้า"
                "ที่ใช้สูตรเดียวกัน"
            ),
        )

        self.latest_maximum_value = self._metric(
            risk_grid,
            2,
            "Latest MAX Risk",
            "คะแนนสูงสุดใน Session ล่าสุด",
        )

        self.latest_alert_value = self._metric(
            risk_grid,
            3,
            "Latest Alerts",
            "จำนวน Notification ที่บันทึก",
        )

        self.latest_duration_value = self._metric(
            risk_grid,
            4,
            "Latest Duration",
            "เวลาตรวจจับจริง",
        )

        layout.addLayout(
            risk_grid
        )

        # ====================================================
        # STATUS
        # ====================================================

        self.data_status = self._label(
            (
                "กด Refresh เพื่อโหลด"
                "กิจกรรมที่บันทึกไว้"
            ),
            "muted",
        )

        layout.addWidget(
            self.data_status
        )

        # ====================================================
        # MAIN CONTENT
        # ====================================================

        columns = QHBoxLayout()

        columns.setSpacing(
            16
        )

        columns.addWidget(
            self._build_usage_card(),
            3,
        )

        columns.addLayout(
            self._build_insights_column(),
            2,
        )

        layout.addLayout(
            columns
        )

        layout.addStretch()

    # ========================================================
    # RECENT SESSIONS
    # ========================================================

    def _build_usage_card(self):
        card, layout = self._card()

        layout.addWidget(
            self._label(
                "Recent Sessions",
                "heading",
            )
        )

        layout.addWidget(
            self._label(
                (
                    "ดับเบิลคลิก Session "
                    "เพื่อเปิด Saved Report โดยตรง"
                ),
                "muted",
            )
        )

        self.recent_table = QTableWidget(
            0,
            6,
        )

        self.recent_table.setHorizontalHeaderLabels(
            [
                "เซสชัน",
                "เริ่มเมื่อ",
                "สถานะ",
                "เวลาตรวจจับ",
                "AVG Risk",
                "MAX Risk",
            ]
        )

        self.recent_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.recent_table.verticalHeader().setVisible(
            False
        )

        self.recent_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.recent_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.recent_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.recent_table.setMinimumHeight(
            300
        )

        self.recent_table.cellDoubleClicked.connect(
            self.open_recent_report
        )

        layout.addWidget(
            self.recent_table
        )

        self.empty_label = self._label(
            "ยังไม่ได้โหลดข้อมูล",
            "muted",
        )

        layout.addWidget(
            self.empty_label
        )

        return card

    # ========================================================
    # INSIGHT COLUMN
    # ========================================================

    def _build_insights_column(self):
        column = QVBoxLayout()

        risk, risk_layout = self._card()

        risk_layout.addWidget(
            self._label(
                "Latest Risk Report",
                "heading",
            )
        )

        self.latest_session_label = self._label(
            "Session: N/A",
            "muted",
        )

        self.latest_score_label = self._label(
            "AVG / MIN / MAX: N/A",
            "heading",
        )

        self.latest_trend_label = self._label(
            "Trend: N/A",
            "heading",
        )

        self.latest_comparison_label = self._label(
            "Comparison: N/A",
            "muted",
        )

        self.latest_method_label = self._label(
            "Risk Score Method: N/A",
            "muted",
        )

        self.latest_report_button = QPushButton(
            "Open Latest Report"
        )

        self.latest_report_button.setProperty(
            "variant",
            "primary",
        )

        self.latest_report_button.setEnabled(
            False
        )

        self.latest_report_button.clicked.connect(
            self.open_latest_report
        )

        risk_layout.addWidget(
            self.latest_session_label
        )

        risk_layout.addWidget(
            self.latest_score_label
        )

        risk_layout.addWidget(
            self.latest_trend_label
        )

        risk_layout.addWidget(
            self.latest_comparison_label
        )

        risk_layout.addWidget(
            self.latest_method_label
        )

        risk_layout.addWidget(
            self.latest_report_button
        )

        column.addWidget(
            risk
        )

        trend_card, trend_layout = (
            self._card()
        )

        trend_layout.addWidget(
            self._label(
                "Risk Trend History",
                "heading",
            )
        )

        self.trend_history_note = self._label(
            (
                "แสดง average PostGuard Risk Score "
                "สูงสุด 10 Session ล่าสุดที่ใช้ Risk Score Method เดียวกัน"
            ),
            "muted",
        )

        trend_layout.addWidget(
            self.trend_history_note
        )

        self.risk_trend_chart = (
            SessionRiskTrendChart()
        )

        trend_layout.addWidget(
            self.risk_trend_chart
        )

        column.addWidget(
            trend_card
        )

        # ----------------------------------------------------
        # Score explanation
        # ----------------------------------------------------

        explanation, explanation_layout = (
            self._card()
        )

        explanation_layout.addWidget(
            self._label(
                "Risk Score",
                "heading",
            )
        )

        explanation_layout.addWidget(
            self._label(
                (
                    "คะแนน 0-100 เป็นคะแนนนำเสนอจาก "
                    "PostGuard Modified RULA สำหรับกล้องด้านหน้า "
                    "ไม่ใช่ความน่าจะเป็นของการบาดเจ็บ "
                    "และไม่ใช่การวินิจฉัยทางการแพทย์\n\n"
                    "Risk Trend ใช้การเปลี่ยนแปลง ±5 คะแนน "
                    "เป็น engineering deadband สำหรับการแสดงผล "
                    "และเปรียบเทียบเฉพาะ Session "
                    "ที่ใช้ Risk Score Method เดียวกัน"
                ),
                "muted",
            )
        )

        column.addWidget(
            explanation
        )

        # ----------------------------------------------------
        # Blink placeholder
        # ----------------------------------------------------

        blink, blink_layout = (
            self._card()
        )

        blink_layout.addWidget(
            self._label(
                "Blink Rate",
                "heading",
            )
        )

        blink_layout.addWidget(
            self._label(
                (
                    "N/A\n"
                    "ยังไม่ได้เปิดใช้ Blink Rate "
                    "ใน Production Report"
                ),
                "muted",
            )
        )

        column.addWidget(
            blink
        )

        column.addStretch()

        return column

    # ========================================================
    # UI HELPERS
    # ========================================================

    @staticmethod
    def _label(
        text,
        role,
    ):
        label = QLabel(
            text
        )

        label.setTextFormat(
            Qt.TextFormat.PlainText
        )

        label.setProperty(
            "role",
            role,
        )

        label.setWordWrap(
            True
        )

        return label

    @staticmethod
    def _card(
        variant=None,
    ):
        card = QFrame()

        card.setProperty(
            "card",
            True,
        )

        if variant:
            card.setProperty(
                "variant",
                variant,
            )

        layout = QVBoxLayout(
            card
        )

        layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        layout.setSpacing(
            8
        )

        return (
            card,
            layout,
        )

    def _metric(
        self,
        grid,
        column,
        title,
        note,
    ):
        card, layout = self._card()

        layout.addWidget(
            self._label(
                title,
                "muted",
            )
        )

        value = self._label(
            "--",
            "metric",
        )

        layout.addWidget(
            value
        )

        layout.addWidget(
            self._label(
                note,
                "muted",
            )
        )

        grid.addWidget(
            card,
            0,
            column,
        )

        grid.setColumnStretch(
            column,
            1,
        )

        return value

    # ========================================================
    # MONITORING STATE
    # ========================================================

    def set_monitoring_state(
        self,
        session_id,
        paused=False,
        stopping=False,
        camera_ready=True,
    ):
        if stopping:
            title = (
                "กำลังบันทึกเซสชัน..."
            )

            note = (
                "โปรดรอขณะระบบจบเซสชัน"
                "และบันทึกรายงาน"
            )

        elif session_id is not None:
            title = (
                f"เซสชัน {session_id} - "
                +
                (
                    "หยุดชั่วคราว"
                    if paused
                    else
                    "กำลังตรวจจับ"
                )
            )

            note = (
                (
                    "การตรวจจับหยุดชั่วคราว "
                    "เริ่มเซสชันนี้ต่อเมื่อพร้อม"
                )
                if paused
                else
                (
                    "กล้องกำลังทำงาน "
                    "และจะตรวจจับต่อเนื่อง"
                    "เมื่อเปลี่ยนหน้า"
                )
            )

            if not camera_ready:
                title = (
                    f"เซสชัน {session_id} "
                    "- ต้องดำเนินการ"
                )

                note = (
                    "การตรวจจับหยุดแล้ว "
                    "โปรดกลับไปหน้าการตรวจจับ"
                    "และจบเซสชัน"
                )

        else:
            title = (
                "พร้อมเมื่อคุณพร้อม"
            )

            note = (
                "เลือกกล้อง ตรวจสอบภาพตัวอย่าง "
                "และบันทึกค่าท่าทางอ้างอิง"
            )

        self.live_label.setText(
            title
        )

        self.live_note.setText(
            note
        )

        self.monitor_button.setText(
            (
                "Return to Monitoring"
                if session_id is not None
                else
                "Start Monitoring"
            )
        )

        self.monitor_button.setEnabled(
            not stopping
        )

    # ========================================================
    # REFRESH
    # ========================================================

    def refresh(self):
        if self._loader is not None:
            return

        self.refresh_button.setEnabled(
            False
        )

        self.data_status.setText(
            (
                "กำลังโหลด Sessions "
                "และ Risk Reports..."
            )
        )

        self._loader = (
            _DashboardLoader()
        )

        self._loader.signals.finished.connect(
            self._loaded
        )

        QThreadPool.globalInstance().start(
            self._loader
        )

    # ========================================================
    # LOADED
    # ========================================================

    @Slot(
        object,
        object,
        str,
    )
    def _loaded(
        self,
        sessions,
        summaries=None,
        error="",
    ):
        """
        Supports both:

            _loaded(sessions, summaries, error)

        and legacy tests:

            _loaded(sessions, error)
        """

        if isinstance(
            summaries,
            str,
        ):
            error = summaries
            summaries = []

        if summaries is None:
            summaries = []

        self._loader = None

        self.refresh_button.setEnabled(
            True
        )

        self.recent_table.setRowCount(
            0
        )

        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        if error:
            self.sessions = []
            self.summaries = []
            self.summary_by_session_id = {}

            self.current_risk_insight = (
                build_session_risk_insight(
                    [],
                    [],
                )
            )

            self.current_risk_trend_series = []

            self.current_risk_trend_series = []

            self.risk_trend_chart.clear()

            self.trend_history_note.setText(
                "Risk Trend History unavailable"
            )

            for label in (
                self.completed_value,
                self.time_value,
                self.interrupted_value,
                self.overall_risk_value,
                self.risk_trend_value,
                self.latest_maximum_value,
                self.latest_alert_value,
                self.latest_duration_value,
            ):
                label.setText(
                    "--"
                )

            self.latest_session_label.setText(
                "Session: N/A"
            )

            self.latest_score_label.setText(
                "AVG / MIN / MAX: N/A"
            )

            self.latest_trend_label.setText(
                "Trend: N/A"
            )

            self.latest_comparison_label.setText(
                "Comparison: N/A"
            )

            self.latest_method_label.setText(
                "Risk Score Method: N/A"
            )

            self.latest_report_button.setEnabled(
                False
            )

            self.empty_label.setText(
                "ไม่สามารถเรียกข้อมูลเซสชันได้"
            )

            self.empty_label.show()

            self.data_status.setText(
                error
            )

            return

        # ----------------------------------------------------
        # CACHE
        # ----------------------------------------------------

        self.sessions = list(
            sessions
            or []
        )

        self.summaries = list(
            summaries
            or []
        )

        self.summary_by_session_id = {
            summary.get("session_id"): summary
            for summary in self.summaries
            if (
                isinstance(summary, dict)
                and
                type(
                    summary.get("session_id")
                )
                is int
            )
        }

        self.current_risk_insight = (
            build_session_risk_insight(
                self.sessions,
                self.summaries,
            )
        )

        self.current_risk_trend_series = (
            build_session_risk_trend_series(
                self.sessions,
                self.summaries,
                max_points=10,
            )
        )

        # ----------------------------------------------------
        # GENERAL STATISTICS
        # ----------------------------------------------------

        completed = [
            session
            for session in self.sessions
            if (
                session.get("status")
                ==
                "COMPLETED"
            )
        ]

        known = [
            value
            for value in (
                active_seconds(session)
                for session in completed
            )
            if value is not None
        ]

        self.completed_value.setText(
            str(
                len(completed)
            )
        )

        self.interrupted_value.setText(
            str(
                sum(
                    session.get("status")
                    ==
                    "INTERRUPTED"
                    for session in self.sessions
                )
            )
        )

        self.time_value.setText(
            (
                duration_text(
                    sum(known)
                )
                if (
                    known
                    or
                    not completed
                )
                else
                "N/A"
            )
        )

        missing = (
            len(completed)
            -
            len(known)
        )

        note = (
            "อัปเดตเมื่อ "
            f"{datetime.now().strftime('%H:%M:%S')}"
            " | กิจกรรมที่บันทึกทั้งหมด"
        )

        if missing:
            note += (
                " | ไม่รวมเซสชันที่เสร็จแล้ว "
                f"{missing} รายการ "
                "เนื่องจากไม่มีข้อมูลระยะเวลา"
            )

        self.data_status.setText(
            note
        )

        # ----------------------------------------------------
        # LATEST REPORT
        # ----------------------------------------------------

        latest_summary = (
            self._latest_summary()
        )

        latest_session = None

        if latest_summary is not None:
            latest_session = (
                self._find_session(
                    latest_summary.get(
                        "session_id"
                    )
                )
            )

        self._update_latest_metrics(
            latest_summary,
            latest_session,
        )

        self._update_risk_insight(
            self.current_risk_insight
        )

        self.risk_trend_chart.set_series(
            self.current_risk_trend_series
        )

        point_count = len(
            self.current_risk_trend_series
        )

        if point_count == 0:
            self.trend_history_note.setText(
                (
                    "ยังไม่มี Session ที่มี Risk Score "
                    "สำหรับแสดงแนวโน้ม"
                )
            )

        elif point_count == 1:
            self.trend_history_note.setText(
                (
                    "มี Risk Score แล้ว 1 Session "
                    "จึงยังไม่มีเส้นแนวโน้มสำหรับเปรียบเทียบ"
                )
            )

        else:
            self.trend_history_note.setText(
                (
                    f"แสดง {point_count} Session ล่าสุด "
                    "ที่ใช้ Risk Score Method เดียวกัน"
                )
            )

        # ----------------------------------------------------
        # RECENT SESSIONS
        # ----------------------------------------------------

        recent = (
            self.sessions[:5]
        )

        self.recent_table.setRowCount(
            len(recent)
        )

        for row, session in enumerate(
            recent
        ):
            session_id = (
                session.get(
                    "session_id"
                )
            )

            summary = (
                self.summary_by_session_id.get(
                    session_id
                )
            )

            values = (
                (
                    session_id
                    if session_id is not None
                    else "N/A"
                ),

                local_datetime_text(
                    session.get(
                        "started_at"
                    )
                ),

                session.get(
                    "status",
                    "N/A",
                ),

                duration_text(
                    active_seconds(
                        session
                    )
                ),

                number_text(
                    summary.get(
                        "average_risk_score"
                    )
                    if summary
                    else None
                ),

                number_text(
                    summary.get(
                        "maximum_risk_score"
                    )
                    if summary
                    else None
                ),
            )

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    str(value)
                )

                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                self.recent_table.setItem(
                    row,
                    column,
                    item,
                )

        self.empty_label.setText(
            (
                "ยังไม่มีเซสชัน "
                "เริ่มการตรวจจับครั้งแรก"
                "ได้จากด้านบน"
            )
        )

        self.empty_label.setVisible(
            not self.sessions
        )

    # ========================================================
    # SESSION LOOKUP
    # ========================================================

    def _find_session(
        self,
        session_id,
    ) -> dict | None:
        if (
            type(session_id) is not int
            or
            session_id <= 0
        ):
            return None

        return next(
            (
                session
                for session in self.sessions
                if (
                    session.get(
                        "session_id"
                    )
                    ==
                    session_id
                )
            ),
            None,
        )

    # ========================================================
    # LATEST SUMMARY
    # ========================================================

    def _latest_summary(self):
        """
        Find the newest Session that has a persisted summary.

        Session order is preserved from /sessions.
        """

        for session in self.sessions:
            session_id = (
                session.get(
                    "session_id"
                )
            )

            summary = (
                self.summary_by_session_id.get(
                    session_id
                )
            )

            if summary is not None:
                return summary

        return None

    # ========================================================
    # LATEST SUMMARY METRICS
    # ========================================================

    def _update_latest_metrics(
        self,
        summary,
        session,
    ) -> None:
        if not isinstance(
            summary,
            dict,
        ):
            self.latest_maximum_value.setText(
                "N/A"
            )

            self.latest_alert_value.setText(
                "N/A"
            )

            self.latest_duration_value.setText(
                "N/A"
            )

            self.latest_session_label.setText(
                "Session: N/A"
            )

            self.latest_score_label.setText(
                "AVG / MIN / MAX: N/A"
            )

            self.latest_method_label.setText(
                "Risk Score Method: N/A"
            )

            self.latest_report_button.setEnabled(
                False
            )

            return

        average = summary.get(
            "average_risk_score"
        )

        minimum = summary.get(
            "minimum_risk_score"
        )

        maximum = summary.get(
            "maximum_risk_score"
        )

        alerts = summary.get(
            "total_alert_count"
        )

        method = summary.get(
            "risk_score_method"
        )

        session_id = summary.get(
            "session_id"
        )

        self.latest_maximum_value.setText(
            number_text(
                maximum
            )
        )

        self.latest_alert_value.setText(
            (
                str(alerts)
                if (
                    type(alerts) is int
                    and
                    alerts >= 0
                )
                else
                "N/A"
            )
        )

        self.latest_duration_value.setText(
            duration_text(
                (
                    active_seconds(
                        session
                    )
                    if isinstance(
                        session,
                        dict,
                    )
                    else None
                )
            )
        )

        self.latest_session_label.setText(
            (
                "Session: #"
                f"{session_id}"
            )
        )

        self.latest_score_label.setText(
            (
                "AVG "
                f"{number_text(average)}"
                "  |  MIN "
                f"{number_text(minimum)}"
                "  |  MAX "
                f"{number_text(maximum)}"
            )
        )

        self.latest_method_label.setText(
            (
                "Risk Score Method: "
                +
                (
                    str(method)
                    if method
                    else
                    "N/A"
                )
            )
        )

        can_open = (
            isinstance(
                session,
                dict,
            )
            and
            session.get("status")
            ==
            "COMPLETED"
            and
            type(session_id) is int
            and
            session_id > 0
        )

        self.latest_report_button.setEnabled(
            can_open
        )

    # ========================================================
    # RISK INSIGHT
    # ========================================================

    def _update_risk_insight(
        self,
        insight,
    ) -> None:
        if not isinstance(
            insight,
            dict,
        ):
            self.overall_risk_value.setText(
                "N/A"
            )

            self.risk_trend_value.setText(
                "N/A"
            )

            self.latest_trend_label.setText(
                "Trend: N/A"
            )

            self.latest_comparison_label.setText(
                "Comparison: N/A"
            )

            return

        overall_score = insight.get(
            "overall_session_risk_score"
        )

        trend = insight.get(
            "trend"
        )

        trend_text = (
            risk_trend_label(
                trend
            )
        )

        description = (
            risk_trend_description(
                insight
            )
        )

        self.overall_risk_value.setText(
            number_text(
                overall_score
            )
        )

        self.risk_trend_value.setText(
            trend_text
        )

        self.risk_trend_value.setToolTip(
            description
        )

        self.latest_trend_label.setText(
            (
                "Trend: "
                f"{trend_text}"
            )
        )

        self.latest_comparison_label.setText(
            description
        )

    # ========================================================
    # OPEN RECENT REPORT
    # ========================================================

    def open_recent_report(
        self,
        row: int,
        _column: int = 0,
    ) -> None:
        if (
            type(row) is not int
            or
            row < 0
            or
            row >= min(
                5,
                len(self.sessions),
            )
        ):
            return

        session = (
            self.sessions[row]
        )

        self._open_saved_report(
            session
        )

    # ========================================================
    # OPEN LATEST REPORT
    # ========================================================

    def open_latest_report(self) -> None:
        summary = (
            self._latest_summary()
        )

        if not isinstance(
            summary,
            dict,
        ):
            return

        session = self._find_session(
            summary.get(
                "session_id"
            )
        )

        if session is None:
            return

        self._open_saved_report(
            session
        )

    # ========================================================
    # OPEN SAVED REPORT
    # ========================================================

    def _open_saved_report(
        self,
        session: dict,
    ) -> None:
        """
        Load authoritative persisted data from the one-session
        summary endpoint before displaying the report.
        """

        if not isinstance(
            session,
            dict,
        ):
            return

        session_id = (
            session.get(
                "session_id"
            )
        )

        if (
            type(session_id) is not int
            or
            session_id <= 0
        ):
            return

        if (
            session.get("status")
            !=
            "COMPLETED"
        ):
            QMessageBox.information(
                self,
                "Saved Session Report",
                (
                    "Session นี้ยังไม่ COMPLETED "
                    "จึงไม่สามารถเปิด Final Report ได้"
                ),
            )

            return

        if (
            session_id
            not in
            self.summary_by_session_id
        ):
            QMessageBox.information(
                self,
                "Saved Session Report",
                (
                    "Session นี้ยังไม่มี "
                    "Saved Session Report"
                ),
            )

            return

        try:
            saved = (
                load_session_summary(
                    session_id
                )
            )

            if saved is None:
                QMessageBox.information(
                    self,
                    "Saved Session Report",
                    (
                        "ไม่พบรายงานที่บันทึก"
                        "สำหรับ Session นี้"
                    ),
                )

                return

            dialog = (
                SavedSessionReportDialog(
                    session=session,
                    saved_summary=saved,
                    parent=self,
                )
            )

            dialog.exec()

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            QMessageBox.warning(
                self,
                "ไม่สามารถเปิด Saved Report",
                str(error),
            )