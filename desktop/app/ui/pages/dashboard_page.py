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
                    "ไม่สามารถโหลดข้อมูลเซสชันได้ HTTP "
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
                    "ข้อมูลเซสชันที่ได้รับไม่ถูกต้อง"
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
                    "ไม่สามารถโหลดข้อมูลสรุปเซสชันได้ HTTP "
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
                    "ข้อมูลสรุปเซสชันที่ได้รับไม่ถูกต้อง"
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
                    "ไม่สามารถโหลดกิจกรรมที่บันทึกไว้ได้ "
                    "กดรีเฟรชเพื่อลองอีกครั้ง"
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
            "ผู้ใช้"
        )

        welcome_copy.addWidget(
            self._label(
                f"ยินดีต้อนรับกลับมา, {name}",
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
            "เริ่มการตรวจจับ"
        )

        self.monitor_button.setProperty(
            "variant",
            "primary",
        )

        self.monitor_button.clicked.connect(
            self.monitor_requested.emit
        )

        self.history_button = QPushButton(
            "ดูประวัติ"
        )

        self.history_button.clicked.connect(
            self.history_requested.emit
        )

        self.refresh_button = QPushButton(
            "รีเฟรช"
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

        section = self._label("ภาพรวมการใช้งาน", "heading")
        section.setStyleSheet(
            "font-size:20px;font-weight:700;color:#0f172a;margin-top:6px;"
        )
        layout.addWidget(section)

        section_note = self._label(
            "ตัวเลขสำคัญจากเซสชันที่บันทึกไว้",
            "muted",
        )
        section_note.setStyleSheet("font-size:12px;color:#64748b;")
        layout.addWidget(section_note)

        summary_grid = QGridLayout()

        summary_grid.setHorizontalSpacing(
            12
        )

        self.completed_value = self._metric(
            summary_grid,
            0,
            "เซสชันที่เสร็จสิ้น",
            "จำนวนเซสชันที่ตรวจจับเสร็จสิ้น",
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
            "ไม่นำมารวมในรายงานความเสี่ยง",
        )

        layout.addLayout(
            summary_grid
        )

        # ====================================================
        # SESSION RISK INSIGHT
        # ====================================================

        risk_section = self._label("ความเสี่ยงล่าสุด", "heading")
        risk_section.setStyleSheet(
            "font-size:20px;font-weight:700;color:#0f172a;margin-top:10px;"
        )
        layout.addWidget(risk_section)

        risk_note = self._label(
            "คะแนน แนวโน้ม การแจ้งเตือน และเวลาของเซสชันล่าสุด",
            "muted",
        )
        risk_note.setStyleSheet("font-size:12px;color:#64748b;")
        layout.addWidget(risk_note)

        risk_grid = QGridLayout()

        risk_grid.setHorizontalSpacing(
            12
        )

        self.overall_risk_value = self._metric(
            risk_grid,
            0,
            "ความเสี่ยงโดยรวมของเซสชัน",
            "คะแนนเฉลี่ย 0-100 ของเซสชันล่าสุด",
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
            "แนวโน้มความเสี่ยง",
            (
                "เทียบกับเซสชันก่อนหน้า"
                "ที่ใช้วิธีคำนวณเดียวกัน"
            ),
        )

        self.latest_maximum_value = self._metric(
            risk_grid,
            2,
            "ความเสี่ยงสูงสุดล่าสุด",
            "คะแนนสูงสุดในเซสชันล่าสุด",
        )

        self.latest_alert_value = self._metric(
            risk_grid,
            3,
            "การแจ้งเตือนล่าสุด",
            "จำนวนการแจ้งเตือนที่บันทึก",
        )

        self.latest_duration_value = self._metric(
            risk_grid,
            4,
            "ระยะเวลาล่าสุด",
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
                "กดรีเฟรชเพื่อโหลด"
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
                "เซสชันล่าสุด",
                "heading",
            )
        )

        layout.addWidget(
            self._label(
                (
                    "ดับเบิลคลิกเซสชัน "
                    "เพื่อเปิดรายงานที่บันทึกไว้โดยตรง"
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

        self.recent_table.setMinimumHeight(300)
        self.recent_table.verticalHeader().setDefaultSectionSize(42)
        self.recent_table.setShowGrid(False)
        self.recent_table.setStyleSheet(
            "QTableWidget{background:#fff;alternate-background-color:#f8fafc;"
            "border:1px solid #dbe4ef;border-radius:10px;gridline-color:transparent;}"
            "QHeaderView::section{background:#eef3f8;color:#334155;font-weight:700;"
            "font-size:12px;padding:9px;border:none;border-bottom:1px solid #dbe4ef;}"
            "QTableWidget::item{padding:7px;border-bottom:1px solid #edf2f7;}"
            "QTableWidget::item:selected{background:#dbeafe;color:#0f172a;}"
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
                "รายงานความเสี่ยงล่าสุด",
                "heading",
            )
        )

        self.latest_session_label = self._label(
            "เซสชัน: N/A",
            "muted",
        )

        self.latest_score_label = self._label(
            "AVG / MIN / MAX: N/A",
            "heading",
        )

        self.latest_trend_label = self._label(
            "แนวโน้ม: N/A",
            "heading",
        )

        self.latest_comparison_label = self._label(
            "การเปรียบเทียบ: N/A",
            "muted",
        )

        self.latest_method_label = self._label(
            "วิธีคำนวณ Risk Score: N/A",
            "muted",
        )

        self.latest_report_button = QPushButton(
            "เปิดรายงานล่าสุด"
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
                "ประวัติแนวโน้มความเสี่ยง",
                "heading",
            )
        )

        self.trend_history_note = self._label(
            (
                "แสดงค่าเฉลี่ย PostGuard Risk Score "
                "สูงสุด 10 เซสชันล่าสุดที่ใช้วิธีคำนวณ Risk Score เดียวกัน"
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
                    "แนวโน้มความเสี่ยงใช้การเปลี่ยนแปลง ±5 คะแนน "
                    "เป็นช่วงค่าคงที่สำหรับลดการเปลี่ยนสถานะจากความผันผวนเล็กน้อย "
                    "และเปรียบเทียบเฉพาะเซสชัน "
                    "ที่ใช้วิธีคำนวณ Risk Score เดียวกัน"
                ),
                "muted",
            )
        )

        column.addWidget(
            explanation
        )

        # ----------------------------------------------------
        # Blink summary
        # ----------------------------------------------------

        blink, blink_layout = self._card()
        blink.setProperty("cardTone", "blue")

        blink_layout.addWidget(
            self._label(
                "การกระพริบตา",
                "cardTitle",
            )
        )

        self.latest_blink_value = self._label(
            "N/A",
            "cardValueInfo",
        )
        self.latest_blink_value.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.latest_blink_note = self._label(
            "ยังไม่มีข้อมูลอัตราการกระพริบตา",
            "cardSubtitle",
        )
        self.latest_blink_note.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        blink_layout.addStretch()
        blink_layout.addWidget(self.latest_blink_value)
        blink_layout.addWidget(
            self._label(
                "ครั้ง / นาที",
                "cardSubtitle",
            )
        )
        blink_layout.addWidget(self.latest_blink_note)
        blink_layout.addStretch()

        column.addWidget(blink)

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
        colors = {
            "เซสชันที่เสร็จสิ้น": ("#16a34a", "#15803d"),
            "เวลาตรวจจับจริง": ("#2563eb", "#1d4ed8"),
            "เซสชันที่ถูกขัดจังหวะ": ("#dc2626", "#b91c1c"),
            "ความเสี่ยงโดยรวมของเซสชัน": ("#2563eb", "#1d4ed8"),
            "แนวโน้มความเสี่ยง": ("#16a34a", "#15803d"),
            "ความเสี่ยงสูงสุดล่าสุด": ("#d97706", "#b45309"),
            "การแจ้งเตือนล่าสุด": ("#d97706", "#b45309"),
            "ระยะเวลาล่าสุด": ("#2563eb", "#1d4ed8"),
        }
        accent, value_color = colors.get(title, ("#2563eb", "#1d4ed8"))

        card, card_layout = self._card()
        card.setMinimumHeight(138)
        card.setStyleSheet(
            "QFrame{background:#fff;border:1px solid #dbe4ef;"
            "border-left:4px solid " + accent + ";border-radius:12px;}"
        )

        title_label = self._label(title, "cardTitle")
        title_label.setStyleSheet(
            "font-size:13px;font-weight:650;color:#334155;"
            "border:none;background:transparent;"
        )

        value = self._label("--", "metric")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet(
            "font-size:30px;font-weight:800;color:" + value_color + ";"
            "border:none;background:transparent;"
        )

        note_label = self._label(note, "cardSubtitle")
        note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note_label.setStyleSheet(
            "font-size:11px;color:#64748b;border:none;background:transparent;"
        )

        card_layout.addWidget(title_label)
        card_layout.addStretch()
        card_layout.addWidget(value)
        card_layout.addWidget(note_label)
        card_layout.addStretch()

        row, real_column = divmod(column, 3)
        grid.addWidget(card, row, real_column)
        grid.setColumnStretch(real_column, 1)
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
                "กลับไปหน้าการตรวจจับ"
                if session_id is not None
                else
                "เริ่มการตรวจจับ"
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
                "กำลังโหลดเซสชัน "
                "และรายงานความเสี่ยง..."
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
                "ไม่สามารถแสดงประวัติแนวโน้มความเสี่ยงได้"
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
                "เซสชัน: N/A"
            )

            self.latest_score_label.setText(
                "AVG / MIN / MAX: N/A"
            )

            self.latest_trend_label.setText(
                "แนวโน้ม: N/A"
            )

            self.latest_comparison_label.setText(
                "การเปรียบเทียบ: N/A"
            )

            self.latest_method_label.setText(
                "วิธีคำนวณ Risk Score: N/A"
            )

            self.latest_report_button.setEnabled(
                False
            )

            if hasattr(self, "latest_blink_value"):
                self.latest_blink_value.setText("N/A")
                self.latest_blink_note.setText(
                    "ไม่สามารถโหลดข้อมูลการกระพริบตาได้"
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
                    "ยังไม่มีเซสชันที่มี Risk Score "
                    "สำหรับแสดงแนวโน้ม"
                )
            )

        elif point_count == 1:
            self.trend_history_note.setText(
                (
                    "มี Risk Score แล้ว 1 เซสชัน "
                    "จึงยังไม่มีเส้นแนวโน้มสำหรับเปรียบเทียบ"
                )
            )

        else:
            self.trend_history_note.setText(
                (
                    f"แสดง {point_count} เซสชันล่าสุด "
                    "ที่ใช้วิธีคำนวณ Risk Score เดียวกัน"
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
                "เซสชัน: N/A"
            )

            self.latest_score_label.setText(
                "AVG / MIN / MAX: N/A"
            )

            self.latest_method_label.setText(
                "วิธีคำนวณ Risk Score: N/A"
            )

            self.latest_report_button.setEnabled(
                False
            )

            if hasattr(self, "latest_blink_value"):
                self.latest_blink_value.setText("N/A")
                self.latest_blink_note.setText(
                    "ยังไม่มีรายงานที่มีข้อมูลการกระพริบตา"
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

        blink_rate = summary.get(
            "blink_rate"
        )

        eye_alert_count = summary.get(
            "eye_alert_count"
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
                "เซสชัน: #"
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
                "วิธีคำนวณ Risk Score: "
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

        if hasattr(self, "latest_blink_value"):
            self.latest_blink_value.setText(
                number_text(blink_rate)
            )

            if type(eye_alert_count) is int and eye_alert_count >= 0:
                self.latest_blink_note.setText(
                    f"แจ้งเตือนสายตา {eye_alert_count} ครั้ง"
                )
            elif blink_rate is None:
                self.latest_blink_note.setText(
                    "เซสชันนี้ไม่มีข้อมูล Blink Rate ที่บันทึกไว้"
                )
            else:
                self.latest_blink_note.setText(
                    "ค่าเฉลี่ยของเซสชันล่าสุด"
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
                "แนวโน้ม: N/A"
            )

            self.latest_comparison_label.setText(
                "การเปรียบเทียบ: N/A"
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
                "แนวโน้ม: "
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
                "รายงานเซสชันที่บันทึกไว้",
                (
                    "เซสชันนี้ยังไม่เสร็จสิ้น "
                    "จึงไม่สามารถเปิดรายงานฉบับสมบูรณ์ได้"
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
                "รายงานเซสชันที่บันทึกไว้",
                (
                    "เซสชันนี้ยังไม่มี "
                    "รายงานเซสชันที่บันทึกไว้"
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
                    "รายงานเซสชันที่บันทึกไว้",
                    (
                        "ไม่พบรายงานที่บันทึก"
                        "สำหรับเซสชันนี้"
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
                "ไม่สามารถเปิดรายงานที่บันทึกไว้",
                str(error),
            )