"""PostGuard Session Summary and Risk Score visualization."""

import requests

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.api_client import (
    APIClient,
)
from app.services.alert_history_service import (
    duration_text,
    event_type_label,
    local_datetime,
)
from app.services.session_risk_score_service import (
    load_session_risk_score_buckets,
)
from app.services.session_summary_service import (
    save_session_summary,
)
from app.ui.dialogs.alert_history_dialog import (
    AlertHistoryDialog,
)
from app.ui.risk_score_chart import (
    RiskScoreChart,
)


class SessionSummaryPage(
    QWidget
):
    back_requested = Signal()

    def __init__(
        self,
    ):
        super().__init__()

        self.setProperty(
            "page",
            True,
        )

        self.current_session_id = None
        self.current_summary = None
        self.risk_score_buckets = []

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

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        scroll_area.setFrameShape(
            QScrollArea.Shape.NoFrame
        )

        content = QWidget()
        content.setProperty("page", True)

        layout = QVBoxLayout(content)

        layout.setContentsMargins(
            28,
            22,
            28,
            28,
        )

        layout.setSpacing(16)

        layout.setSizeConstraint(
            QLayout.SizeConstraint.SetMinimumSize
        )

        scroll_area.setWidget(content)
        page_layout.addWidget(scroll_area)

        # ====================================================
        # HEADER
        # ====================================================

        header = QHBoxLayout()

        header_copy = QVBoxLayout()

        self.title_label = QLabel(
            "สรุปผลเซสชัน"
        )

        self.title_label.setProperty(
            "role",
            "title",
        )

        self.description_label = QLabel(
            "ภาพรวมการใช้งาน ท่าทาง สายตา "
            "ความเสี่ยง และการแจ้งเตือนในเซสชันนี้"
        )

        self.description_label.setProperty(
            "role",
            "muted",
        )

        header_copy.addWidget(
            self.title_label
        )

        header_copy.addWidget(
            self.description_label
        )

        header.addLayout(
            header_copy,
            1,
        )

        self.database_label = QLabel(
            "สถานะเซสชัน: --"
        )

        self.database_label.setProperty(
            "role",
            "positive",
        )

        header.addWidget(
            self.database_label,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        layout.addLayout(header)

        # ====================================================
        # SESSION OVERVIEW
        # ====================================================

        session_card = QFrame()
        session_card.setProperty("card", True)

        session_layout = QVBoxLayout(
            session_card
        )

        session_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        session_layout.setSpacing(12)

        session_heading = QLabel(
            "ภาพรวมการใช้งาน"
        )

        session_heading.setProperty(
            "role",
            "heading",
        )

        session_layout.addWidget(
            session_heading
        )

        session_top = QHBoxLayout()
        session_top.setSpacing(12)

        self.session_label = QLabel(
            "รหัสเซสชัน: --"
        )

        self.camera_label = QLabel(
            "กล้อง: --"
        )

        self.baseline_label = QLabel(
            "ค่าท่าทางอ้างอิง: --"
        )

        for label in (
            self.session_label,
            self.camera_label,
            self.baseline_label,
        ):
            label.setProperty(
                "role",
                "metricSmall",
            )

            session_top.addWidget(
                label,
                1,
            )

        session_layout.addLayout(
            session_top
        )

        timing = QHBoxLayout()
        timing.setSpacing(12)

        time_card = QFrame()
        time_card.setProperty(
            "cardTone",
            "blue",
        )

        time_layout = QVBoxLayout(
            time_card
        )

        self.duration_label = QLabel(
            "ระยะเวลา: --"
        )

        self.duration_label.setProperty(
            "role",
            "metric",
        )

        duration_hint = QLabel(
            "เวลาตรวจจับจริง"
        )

        duration_hint.setProperty(
            "role",
            "muted",
        )

        time_layout.addWidget(
            self.duration_label
        )

        time_layout.addWidget(
            duration_hint
        )

        pause_card = QFrame()
        pause_card.setProperty(
            "cardTone",
            "amber",
        )

        pause_layout = QVBoxLayout(
            pause_card
        )

        self.paused_duration_label = QLabel(
            "เวลาหยุดชั่วคราว: --"
        )

        self.pause_count_label = QLabel(
            "จำนวนครั้งที่หยุด: --"
        )

        pause_layout.addWidget(
            self.paused_duration_label
        )

        pause_layout.addWidget(
            self.pause_count_label
        )

        timing.addWidget(
            time_card,
            1,
        )

        timing.addWidget(
            pause_card,
            1,
        )

        session_layout.addLayout(
            timing
        )

        dates = QHBoxLayout()

        self.start_label = QLabel(
            "เริ่มเมื่อ: --"
        )

        self.end_label = QLabel(
            "สิ้นสุดเมื่อ: --"
        )

        self.start_label.setProperty(
            "role",
            "muted",
        )

        self.end_label.setProperty(
            "role",
            "muted",
        )

        dates.addWidget(
            self.start_label
        )

        dates.addStretch()

        dates.addWidget(
            self.end_label
        )

        session_layout.addLayout(
            dates
        )

        layout.addWidget(
            session_card
        )

        # ====================================================
        # DETECTION OVERVIEW
        # ====================================================

        detection_card = QFrame()
        detection_card.setProperty(
            "card",
            True,
        )

        detection_layout = QVBoxLayout(
            detection_card
        )

        detection_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        detection_layout.setSpacing(12)

        detection_title = QLabel(
            "ผลการตรวจจับ"
        )

        detection_title.setProperty(
            "role",
            "heading",
        )

        detection_layout.addWidget(
            detection_title
        )

        detection_metrics = QHBoxLayout()
        detection_metrics.setSpacing(10)

        self.count_label = QLabel(
            "รอบการตรวจจับ: --"
        )

        self.pose_label = QLabel(
            "ตรวจพบท่าทาง: --"
        )

        self.face_label = QLabel(
            "ตรวจพบใบหน้า: --"
        )

        for label, tone in (
            (
                self.count_label,
                "blue",
            ),
            (
                self.pose_label,
                "green",
            ),
            (
                self.face_label,
                "cyan",
            ),
        ):
            card = QFrame()
            card.setProperty(
                "cardTone",
                tone,
            )

            card_layout = QVBoxLayout(
                card
            )

            label.setProperty(
                "role",
                "metricSmall",
            )

            card_layout.addWidget(
                label
            )

            detection_metrics.addWidget(
                card,
                1,
            )

        detection_layout.addLayout(
            detection_metrics
        )

        posture_row = QHBoxLayout()
        posture_row.setSpacing(10)

        shoulder_card = QFrame()
        shoulder_card.setProperty(
            "cardTone",
            "purple",
        )

        shoulder_layout = QVBoxLayout(
            shoulder_card
        )

        shoulder_title = QLabel(
            "ไหล่"
        )

        shoulder_title.setProperty(
            "role",
            "heading",
        )

        self.shoulder_label = QLabel(
            "ความเอียงไหล่เฉลี่ย: --"
        )

        self.baseline_shoulder_label = QLabel(
            "ค่าอ้างอิงไหล่: --"
        )

        self.baseline_shoulder_label.setProperty(
            "role",
            "muted",
        )

        shoulder_layout.addWidget(
            shoulder_title
        )

        shoulder_layout.addWidget(
            self.shoulder_label
        )

        shoulder_layout.addWidget(
            self.baseline_shoulder_label
        )

        neck_card = QFrame()
        neck_card.setProperty(
            "cardTone",
            "cyan",
        )

        neck_layout = QVBoxLayout(
            neck_card
        )

        neck_title = QLabel(
            "คอ"
        )

        neck_title.setProperty(
            "role",
            "heading",
        )

        self.neck_label = QLabel(
            "ความเอียงคอเฉลี่ย: --"
        )

        self.baseline_neck_label = QLabel(
            "ค่าอ้างอิงคอ: --"
        )

        self.baseline_neck_label.setProperty(
            "role",
            "muted",
        )

        neck_layout.addWidget(
            neck_title
        )

        neck_layout.addWidget(
            self.neck_label
        )

        neck_layout.addWidget(
            self.baseline_neck_label
        )

        posture_row.addWidget(
            shoulder_card,
            1,
        )

        posture_row.addWidget(
            neck_card,
            1,
        )

        detection_layout.addLayout(
            posture_row
        )

        layout.addWidget(
            detection_card
        )

        # ====================================================
        # RISK SCORE
        # ====================================================

        risk_score_group = QFrame()
        risk_score_group.setProperty(
            "card",
            True,
        )

        risk_score_layout = QVBoxLayout(
            risk_score_group
        )

        risk_score_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        risk_title = QLabel(
            "PostGuard Risk Score"
        )

        risk_title.setProperty(
            "role",
            "heading",
        )

        risk_score_layout.addWidget(
            risk_title
        )

        score_cards = QHBoxLayout()
        score_cards.setSpacing(10)

        self.average_score_card = (
            self._create_score_card(
                "คะแนนเฉลี่ย",
                "--",
            )
        )

        self.average_score_card.setProperty(
            "cardTone",
            "blue",
        )

        self.minimum_score_card = (
            self._create_score_card(
                "ต่ำสุด",
                "--",
            )
        )

        self.minimum_score_card.setProperty(
            "cardTone",
            "green",
        )

        self.maximum_score_card = (
            self._create_score_card(
                "สูงสุด",
                "--",
            )
        )

        self.maximum_score_card.setProperty(
            "cardTone",
            "amber",
        )

        score_cards.addWidget(
            self.average_score_card
        )

        score_cards.addWidget(
            self.minimum_score_card
        )

        score_cards.addWidget(
            self.maximum_score_card
        )

        risk_score_layout.addLayout(
            score_cards
        )

        # Existing update targets.
        # Hidden because cards above already show the same values.
        self.average_risk_label = QLabel(
            "คะแนนความเสี่ยงเฉลี่ย: N/A"
        )

        self.minimum_risk_label = QLabel(
            "คะแนนความเสี่ยงต่ำสุด: N/A"
        )

        self.maximum_risk_label = QLabel(
            "คะแนนความเสี่ยงสูงสุด: N/A"
        )

        self.average_risk_label.hide()
        self.minimum_risk_label.hide()
        self.maximum_risk_label.hide()

        self.risk_score_method_label = QLabel(
            "วิธีคำนวณคะแนน: N/A"
        )

        self.risk_score_method_label.setProperty(
            "role",
            "muted",
        )

        risk_score_layout.addWidget(
            self.risk_score_method_label
        )

        layout.addWidget(
            risk_score_group
        )

        # ====================================================
        # RISK CHART
        # ====================================================

        chart_group = QFrame()
        chart_group.setProperty(
            "card",
            True,
        )

        chart_layout = QVBoxLayout(
            chart_group
        )

        chart_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        chart_title = QLabel(
            "แนวโน้มความเสี่ยงตลอดเซสชัน"
        )

        chart_title.setProperty(
            "role",
            "heading",
        )

        chart_layout.addWidget(
            chart_title
        )

        self.risk_score_chart = (
            RiskScoreChart()
        )

        self.chart_status_label = QLabel(
            "กำลังรอข้อมูล Risk Score..."
        )

        self.chart_status_label.setProperty(
            "role",
            "muted",
        )

        self.chart_status_label.setWordWrap(
            True
        )

        chart_layout.addWidget(
            self.risk_score_chart
        )

        chart_layout.addWidget(
            self.chart_status_label
        )

        layout.addWidget(
            chart_group
        )

        # ====================================================
        # USER-FACING SESSION INSIGHTS
        # ====================================================

        insight_row = QHBoxLayout()
        insight_row.setSpacing(12)

        # ----------------------------------------------------
        # EYE
        # ----------------------------------------------------

        eye_card = QFrame()
        eye_card.setProperty(
            "cardTone",
            "cyan",
        )

        eye_layout = QVBoxLayout(
            eye_card
        )

        eye_title = QLabel(
            "สายตาและการกระพริบตา"
        )

        eye_title.setProperty(
            "role",
            "heading",
        )

        self.blink_rate_label = QLabel(
            "อัตราการกะพริบตา: N/A"
        )

        self.blink_rate_label.setProperty(
            "role",
            "metricSmall",
        )

        self.eye_alert_count_label = QLabel(
            "การแจ้งเตือนการกระพริบตา: --"
        )

        self.eye_alert_count_label.setWordWrap(
            True
        )

        eye_layout.addWidget(
            eye_title
        )

        eye_layout.addWidget(
            self.blink_rate_label
        )

        eye_layout.addWidget(
            self.eye_alert_count_label
        )

        # ----------------------------------------------------
        # ALERT
        # ----------------------------------------------------

        alert_summary_card = QFrame()
        alert_summary_card.setProperty(
            "cardTone",
            "amber",
        )

        alert_summary_layout = QVBoxLayout(
            alert_summary_card
        )

        alert_summary_title = QLabel(
            "การแจ้งเตือน"
        )

        alert_summary_title.setProperty(
            "role",
            "heading",
        )

        self.report_alert_count_label = QLabel(
            "การแจ้งเตือนท่าทาง: --"
        )

        self.report_alert_count_label.setProperty(
            "role",
            "metricSmall",
        )

        self.frequent_event_label = QLabel(
            "รายการที่พบบ่อยที่สุด: N/A"
        )

        self.frequent_event_label.setWordWrap(
            True
        )

        alert_summary_layout.addWidget(
            alert_summary_title
        )

        alert_summary_layout.addWidget(
            self.report_alert_count_label
        )

        alert_summary_layout.addWidget(
            self.frequent_event_label
        )

        insight_row.addWidget(
            eye_card,
            1,
        )

        insight_row.addWidget(
            alert_summary_card,
            1,
        )

        layout.addLayout(
            insight_row
        )

        # ====================================================
        # RISK EVENT SUMMARY
        # ====================================================

        alert_group = QFrame()
        alert_group.setProperty(
            "card",
            True,
        )

        alert_layout = QVBoxLayout(
            alert_group
        )

        alert_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        alert_heading = QLabel(
            "เหตุการณ์ความเสี่ยง"
        )

        alert_heading.setProperty(
            "role",
            "heading",
        )

        alert_layout.addWidget(
            alert_heading
        )

        alert_metrics = QHBoxLayout()
        alert_metrics.setSpacing(10)

        self.alert_total_label = QLabel(
            "การแจ้งเตือนทั้งหมด: --"
        )

        self.alert_closed_label = QLabel(
            "สิ้นสุดแล้ว: --"
        )

        self.alert_active_label = QLabel(
            "กำลังเกิดขึ้น: --"
        )

        self.alert_duration_label = QLabel(
            "ระยะเวลาความเสี่ยงรวม: --"
        )

        for label in (
            self.alert_total_label,
            self.alert_closed_label,
            self.alert_active_label,
            self.alert_duration_label,
        ):
            metric = QFrame()
            metric.setProperty(
                "cardTone",
                "blue",
            )

            metric_layout = QVBoxLayout(
                metric
            )

            label.setWordWrap(True)

            metric_layout.addWidget(
                label
            )

            alert_metrics.addWidget(
                metric,
                1,
            )

        alert_layout.addLayout(
            alert_metrics
        )

        self.alert_error_label = QLabel("")
        self.alert_error_label.setWordWrap(True)

        self.alert_error_label.setProperty(
            "role",
            "dangerText",
        )

        alert_layout.addWidget(
            self.alert_error_label
        )

        alert_buttons = QHBoxLayout()

        self.refresh_alerts_button = QPushButton(
            "รีเฟรชข้อมูล"
        )

        self.refresh_alerts_button.clicked.connect(
            self.refresh_alerts
        )

        self.view_alerts_button = QPushButton(
            "ดูประวัติการแจ้งเตือน"
        )

        self.view_alerts_button.setProperty(
            "variant",
            "primary",
        )

        self.view_alerts_button.clicked.connect(
            self.open_alert_history
        )

        alert_buttons.addStretch()

        alert_buttons.addWidget(
            self.refresh_alerts_button
        )

        alert_buttons.addWidget(
            self.view_alerts_button
        )

        alert_layout.addLayout(
            alert_buttons
        )

        layout.addWidget(
            alert_group
        )

        # ====================================================
        # TECHNICAL DETAIL
        # ====================================================

        detail_card = QFrame()
        detail_card.setProperty(
            "card",
            True,
        )

        detail_layout = QVBoxLayout(
            detail_card
        )

        detail_heading = QLabel(
            "รายละเอียดเพิ่มเติม"
        )

        detail_heading.setProperty(
            "role",
            "heading",
        )

        self.risk_breakdown_label = QLabel(
            "รายละเอียดความเสี่ยง: --"
        )

        self.risk_breakdown_label.setWordWrap(
            True
        )

        self.risk_breakdown_label.setProperty(
            "role",
            "muted",
        )

        detail_layout.addWidget(
            detail_heading
        )

        detail_layout.addWidget(
            self.risk_breakdown_label
        )

        layout.addWidget(
            detail_card
        )

        # ====================================================
        # SAVE STATUS
        # ====================================================

        self.save_group = QGroupBox(
            "เกิดปัญหาในการบันทึกสรุป"
        )

        self.save_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        save_layout = QVBoxLayout(
            self.save_group
        )

        self.save_status_label = QLabel(
            "ไม่มีข้อมูลสถานะการบันทึกรายงาน"
        )

        self.save_status_label.setWordWrap(
            True
        )

        self.retry_button = QPushButton(
            "ลองบันทึกสรุปอีกครั้ง"
        )

        self.retry_button.setEnabled(
            False
        )

        self.retry_button.clicked.connect(
            self.retry_save
        )

        save_layout.addWidget(
            self.save_status_label
        )

        save_layout.addWidget(
            self.retry_button
        )

        layout.addWidget(
            self.save_group
        )

        # ====================================================
        # DISCLAIMER
        # ====================================================

        self.note_label = QLabel(
            "PostGuard Risk Score เป็นคะแนนสรุปสำหรับระบบต้นแบบ "
            "ไม่ใช่ความน่าจะเป็นของการบาดเจ็บ "
            "และไม่ใช่การวินิจฉัยทางการแพทย์"
        )

        self.note_label.setWordWrap(True)

        self.note_label.setProperty(
            "role",
            "muted",
        )

        layout.addWidget(
            self.note_label
        )

        # ====================================================
        # BACK
        # ====================================================

        self.back_button = QPushButton(
            "กลับไปหน้าภาพรวม"
        )

        self.back_button.clicked.connect(
            self.go_back
        )

        layout.addWidget(
            self.back_button
        )
    # ========================================================
    # SCORE CARD
    # ========================================================

    @staticmethod
    def _create_score_card(
        title: str,
        value: str,
    ) -> QFrame:
        frame = QFrame()

        frame.setProperty(
            "card",
            True,
        )

        frame.setMinimumHeight(
            92
        )

        layout = QVBoxLayout(
            frame
        )

        title_label = QLabel(
            title
        )

        title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title_label.setProperty(
            "role",
            "muted",
        )

        value_label = QLabel(
            value
        )

        value_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        font = value_label.font()

        font.setPointSize(
            20
        )

        font.setBold(
            True
        )

        value_label.setFont(
            font
        )

        value_label.setObjectName(
            "scoreValue"
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            value_label
        )

        return frame

    @staticmethod
    def _score_card_value_label(
        frame: QFrame,
    ) -> QLabel | None:
        return frame.findChild(
            QLabel,
            "scoreValue",
        )

    def _set_score_card(
        self,
        frame: QFrame,
        value,
    ) -> None:
        label = (
            self._score_card_value_label(
                frame
            )
        )

        if label is None:
            return

        label.setText(
            self._number_or_na(
                value
            )
        )

    # ========================================================
    # FORMATTERS
    # ========================================================

    @staticmethod
    def format_angle(
        value,
    ) -> str:
        if value is None:
            return "N/A"

        try:
            return (
                f"{float(value):+.2f}"
                "\N{DEGREE SIGN}"
            )

        except (
            TypeError,
            ValueError,
        ):
            return "N/A"

    @staticmethod
    def _number_or_na(
        value,
    ) -> str:
        if value is None:
            return "N/A"

        try:
            return (
                f"{float(value):.2f}"
            )

        except (
            TypeError,
            ValueError,
        ):
            return "N/A"

    @staticmethod
    def _risk_breakdown(
        summary,
    ) -> str:
        parts = []

        for level in (
            "low",
            "medium",
            "high",
        ):
            count = summary.get(
                f"{level}_risk_alert_count"
            )

            seconds = summary.get(
                f"{level}_risk_duration"
            )

            if (
                count is None
                and
                seconds is None
            ):
                parts.append(
                    f"{level.title()} N/A"
                )

            else:
                count_text = (
                    count
                    if count is not None
                    else "N/A"
                )

                parts.append(
                    (
                        f"{level.title()} "
                        f"{count_text} ครั้ง, "
                        f"{duration_text(seconds)} "
                        "ระยะเวลาที่เกิดเหตุการณ์"
                    )
                )

        return " | ".join(
            parts
        )

    # ========================================================
    # SAVED REPORT
    # ========================================================

    def set_saved_report(
        self,
        session: dict,
        saved: dict,
    ) -> None:
        """
        Display persisted values without recalculating
        Detection or Risk Score.
        """

        report = {
            **saved,

            "database_status": (
                session.get(
                    "status",
                    "N/A",
                )
            ),

            "camera_name": (
                session.get(
                    "camera_name"
                )
                or
                (
                    "ID "
                    f"{session.get('camera_id', 'N/A')}"
                )
            ),

            "baseline_id": (
                session.get(
                    "baseline_id",
                    "N/A",
                )
            ),

            "started_at": (
                session.get(
                    "started_at",
                    "N/A",
                )
            ),

            "ended_at": (
                session.get(
                    "ended_at",
                    "N/A",
                )
            ),

            "duration_seconds": (
                session.get(
                    "total_duration"
                )
            ),

            "paused_duration": (
                session.get(
                    "paused_duration"
                )
            ),

            "pause_count": (
                session.get(
                    "pause_count",
                    0,
                )
            ),

            "summary_save_status": (
                "LOADED"
            ),
        }

        self.set_summary(
            report
        )

        self.title_label.setText(
            "รายงานเซสชันที่บันทึกไว้"
        )

        self.back_button.setText(
            "ปิดรายงาน"
        )

    # ========================================================
    # SET SUMMARY
    # ========================================================

    def set_summary(
        self,
        summary: dict,
    ) -> None:
        self.current_summary = (
            summary.copy()
        )

        self.current_session_id = (
            summary.get(
                "session_id"
            )
        )

        saved_metrics = summary.get(
            "saved_summary"
        )

        report_metrics = (
            saved_metrics
            if isinstance(
                saved_metrics,
                dict,
            )
            else summary
        )

        # ----------------------------------------------------
        # Session
        # ----------------------------------------------------

        self.session_label.setText(
            (
                "รหัสเซสชัน: "
                f"{self.current_session_id}"
            )
        )

        self.database_label.setText(
            (
                "สถานะเซสชัน: "
                +
                str(
                    summary.get(
                        "database_status",
                        "--",
                    )
                )
            )
        )

        self.camera_label.setText(
            (
                "กล้อง: "
                +
                str(
                    summary.get(
                        "camera_name",
                        "--",
                    )
                )
            )
        )

        self.baseline_label.setText(
            (
                "รหัสค่าท่าทางอ้างอิง: "
                +
                str(
                    summary.get(
                        "baseline_id",
                        "--",
                    )
                )
            )
        )

        self.start_label.setText(
            (
                "เริ่มเมื่อ: "
                +
                local_datetime(
                    summary.get(
                        "started_at"
                    )
                )
            )
        )

        self.end_label.setText(
            (
                "สิ้นสุดเมื่อ: "
                +
                local_datetime(
                    summary.get(
                        "ended_at"
                    )
                )
            )
        )

        self.duration_label.setText(
            (
                "ระยะเวลารวม: "
                +
                duration_text(
                    summary.get(
                        "duration_seconds"
                    )
                )
            )
        )

        self.paused_duration_label.setText(
            (
                "เวลาหยุดชั่วคราว: "
                +
                duration_text(
                    summary.get(
                        "paused_duration"
                    )
                )
            )
        )

        self.pause_count_label.setText(
            (
                "จำนวนครั้งที่หยุด: "
                f"{summary.get('pause_count', 0)}"
            )
        )

        # ----------------------------------------------------
        # Detection
        # ----------------------------------------------------

        for (
            label,
            title,
            key,
        ) in (
            (
                self.count_label,
                "รอบการตรวจจับ",
                "detection_count",
            ),
            (
                self.pose_label,
                "ตรวจพบท่าทาง",
                "pose_detected_count",
            ),
            (
                self.face_label,
                "ตรวจพบใบหน้า",
                "face_detected_count",
            ),
        ):
            value = summary.get(
                key
            )

            label.setText(
                (
                    f"{title}: "
                    +
                    str(
                        value
                        if value is not None
                        else "N/A"
                    )
                )
            )

        self.shoulder_label.setText(
            (
                "ความเอียงไหล่เฉลี่ย: "
                +
                self.format_angle(
                    summary.get(
                        "average_shoulder"
                    )
                )
            )
        )

        self.neck_label.setText(
            (
                "ความเอียงคอเฉลี่ย: "
                +
                self.format_angle(
                    summary.get(
                        "average_neck"
                    )
                )
            )
        )

        self.baseline_shoulder_label.setText(
            (
                "ค่าอ้างอิงไหล่: "
                +
                self.format_angle(
                    summary.get(
                        "baseline_shoulder"
                    )
                )
            )
        )

        self.baseline_neck_label.setText(
            (
                "ค่าอ้างอิงคอ: "
                +
                self.format_angle(
                    summary.get(
                        "baseline_neck"
                    )
                )
            )
        )

        # ----------------------------------------------------
        # PostGuard Risk Score
        # ----------------------------------------------------

        average_score = (
            report_metrics.get(
                "average_risk_score"
            )
        )

        minimum_score = (
            report_metrics.get(
                "minimum_risk_score"
            )
        )

        maximum_score = (
            report_metrics.get(
                "maximum_risk_score"
            )
        )

        self.average_risk_label.setText(
            (
                "คะแนนความเสี่ยงเฉลี่ย: "
                +
                self._number_or_na(
                    average_score
                )
            )
        )

        self.minimum_risk_label.setText(
            (
                "คะแนนความเสี่ยงต่ำสุด: "
                +
                self._number_or_na(
                    minimum_score
                )
            )
        )

        self.maximum_risk_label.setText(
            (
                "คะแนนความเสี่ยงสูงสุด: "
                +
                self._number_or_na(
                    maximum_score
                )
            )
        )

        self._set_score_card(
            self.average_score_card,
            average_score,
        )

        self._set_score_card(
            self.minimum_score_card,
            minimum_score,
        )

        self._set_score_card(
            self.maximum_score_card,
            maximum_score,
        )

        method = report_metrics.get(
            "risk_score_method"
        )

        self.risk_score_method_label.setText(
            (
                "วิธีคำนวณคะแนน: "
                +
                (
                    str(
                        method
                    )
                    if method
                    else "N/A"
                )
            )
        )

        # ----------------------------------------------------
        # Existing report values
        # ----------------------------------------------------

        self.blink_rate_label.setText(
            (
                "อัตราการกะพริบตา: "
                +
                self._number_or_na(
                    report_metrics.get(
                        "blink_rate"
                    )
                )
            )
        )

        alert_count = report_metrics.get(
            "total_alert_count"
        )

        self.report_alert_count_label.setText(
            (
                "การแจ้งเตือนท่าทางที่บันทึก: "
                +
                (
                    str(
                        alert_count
                    )
                    if alert_count is not None
                    else "N/A"
                )
            )
        )

        eye_alert_count = report_metrics.get(
            "eye_alert_count"
        )
        eye_first_count = report_metrics.get(
            "eye_first_alert_count"
        )
        eye_repeat_count = report_metrics.get(
            "eye_repeat_alert_count"
        )

        self.eye_alert_count_label.setText(
            (
                "การแจ้งเตือนการกระพริบตาที่บันทึก: "
                f"{eye_alert_count if eye_alert_count is not None else 'N/A'} "
                f"(FIRST {eye_first_count if eye_first_count is not None else 'N/A'}, "
                f"REPEAT {eye_repeat_count if eye_repeat_count is not None else 'N/A'})"
            )
        )

        frequent = report_metrics.get(
            "most_frequent_alert_event"
        )

        self.frequent_event_label.setText(
            (
                "การแจ้งเตือนที่พบบ่อยที่สุด: "
                +
                event_type_label(
                    frequent
                )
            )
        )

        self.risk_breakdown_label.setText(
            (
                "รายละเอียดความเสี่ยง: "
                +
                self._risk_breakdown(
                    report_metrics
                )
            )
        )

        self.update_save_status()

        # ----------------------------------------------------
        # Load persisted graph data.
        # ----------------------------------------------------

        self.refresh_risk_score_chart()

        self.refresh_alerts()

    # ========================================================
    # RISK SCORE CHART
    # ========================================================

    def refresh_risk_score_chart(
        self,
    ) -> None:
        session_id = (
            self.current_session_id
        )

        self.risk_score_chart.clear_chart()

        self.risk_score_buckets = []

        if (
            type(session_id)
            is not int
            or
            session_id <= 0
        ):
            self.chart_status_label.setText(
                "ไม่พบรหัสเซสชันสำหรับโหลดกราฟ"
            )

            return

        try:
            buckets = (
                load_session_risk_score_buckets(
                    session_id
                )
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            self.chart_status_label.setText(
                (
                    "ไม่สามารถโหลดกราฟ Risk Score ได้: "
                    f"{error}"
                )
            )

            return

        self.risk_score_buckets = (
            buckets
        )

        self.risk_score_chart.set_buckets(
            buckets
        )

        if not buckets:
            self.chart_status_label.setText(
                (
                    "เซสชันนี้ไม่มีข้อมูล Risk Score ที่สมบูรณ์ "
                    "ที่สามารถนำมาแสดงบนกราฟได้"
                )
            )

            return

        total_samples = sum(
            bucket.get(
                "sample_count",
                0,
            )
            for bucket
            in buckets
        )

        first_second = buckets[0].get(
            "start_second"
        )

        last_second = buckets[-1].get(
            "end_second"
        )

        self.chart_status_label.setText(
            (
                f"{len(buckets)} ช่วง | "
                f"{total_samples} ตัวอย่างคะแนนที่ใช้ได้ | "
                f"{first_second:.0f}-"
                f"{last_second:.0f} วินาที"
            )
        )

    # ========================================================
    # SAVE STATUS
    # ========================================================

    def update_save_status(
        self,
    ) -> None:
        summary = (
            self.current_summary
            or {}
        )

        status = summary.get(
            "summary_save_status"
        )

        error = summary.get(
            "summary_save_error"
        )

        if status == "LOADED":
            self.save_status_label.setText(
                "โหลดรายงานจากฐานข้อมูลแล้ว"
            )

            self.retry_button.setEnabled(
                False
            )

            self.save_group.hide()

        elif status == "SAVED":
            self.save_status_label.setText(
                "บันทึกรายงานเซสชันสำเร็จ"
            )

            self.retry_button.setEnabled(
                False
            )

            self.save_group.hide()

        elif status == "ALREADY_EXISTS":
            self.save_status_label.setText(
                (
                    "เซสชันนี้มีรายงาน"
                    "ที่บันทึกไว้แล้ว"
                )
            )

            self.retry_button.setEnabled(
                False
            )

            self.save_group.hide()

        else:
            self.save_status_label.setText(
                (
                    "รายงานของเซสชันยังไม่ได้"
                    "ถูกบันทึก\n"
                    +
                    str(
                        error
                        or
                        "ข้อผิดพลาดที่ไม่ทราบสาเหตุ"
                    )
                )
            )

            self.retry_button.setEnabled(
                self.current_session_id
                is not None
            )

            self.save_group.show()

    # ========================================================
    # RETRY SAVE
    # ========================================================

    def retry_save(
        self,
    ) -> None:
        if not self.current_summary:
            return

        self.retry_button.setEnabled(
            False
        )

        try:
            result = (
                save_session_summary(
                    self.current_summary
                )
            )

            self.current_summary[
                "summary_save_status"
            ] = result[
                "status"
            ]

            self.current_summary[
                "saved_summary"
            ] = result[
                "summary"
            ]

            self.current_summary[
                "summary_save_error"
            ] = None

            # Refresh displayed persisted metrics.
            self.set_summary(
                self.current_summary
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            self.current_summary[
                "summary_save_status"
            ] = "FAILED"

            self.current_summary[
                "summary_save_error"
            ] = str(
                error
            )

            self.update_save_status()

    # ========================================================
    # RISK EVENT / ALERT SUMMARY
    # ========================================================

    def refresh_alerts(
        self,
    ) -> None:
        """
        Refresh user-facing risk and alert summary.

        Presentation only.
        Detection / Risk / Alert policy is not modified here.
        """

        self.alert_total_label.setText(
            "--"
        )

        self.alert_closed_label.setText(
            "--"
        )

        self.alert_active_label.setText(
            "--"
        )

        self.alert_duration_label.setText(
            "--:--"
        )

        if hasattr(
            self,
            "alert_total_detail_label",
        ):
            self.alert_total_detail_label.setText(
                "???????????????..."
            )

        self.alert_error_label.setText(
            ""
        )

        session_id = (
            self.current_session_id
        )

        if (
            type(session_id) is not int
            or session_id <= 0
        ):
            self.alert_error_label.setText(
                "?????????????????????????"
            )

            return

        try:
            risk_response = (
                APIClient
                .get_session_risk_events(
                    session_id
                )
            )

            if not risk_response.ok:
                raise RuntimeError(
                    "???????????????????????????????????"
                )

            risk_events = (
                risk_response.json()
            )

            if not isinstance(
                risk_events,
                list,
            ):
                raise ValueError(
                    "???????????????????????????????????"
                )

            notification_response = (
                APIClient
                .get_session_alert_notifications(
                    session_id
                )
            )

            if not notification_response.ok:
                raise RuntimeError(
                    "??????????????????????????????????"
                )

            notifications = (
                notification_response.json()
            )

            if not isinstance(
                notifications,
                list,
            ):
                raise ValueError(
                    "??????????????????????????????????"
                )

            eye_response = (
                APIClient
                .get_session_eye_alert_notifications(
                    session_id
                )
            )

            if not eye_response.ok:
                raise RuntimeError(
                    "?????????????????????????????????"
                )

            eye_notifications = (
                eye_response.json()
            )

            if not isinstance(
                eye_notifications,
                list,
            ):
                raise ValueError(
                    "?????????????????????????????????"
                )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            self.alert_error_label.setText(
                str(
                    error
                )
            )

            return

        resolved_events = [
            event
            for event
            in risk_events
            if (
                isinstance(
                    event,
                    dict,
                )
                and event.get(
                    "status"
                ) == "RESOLVED"
            )
        ]

        active_events = [
            event
            for event
            in risk_events
            if (
                isinstance(
                    event,
                    dict,
                )
                and event.get(
                    "status"
                ) == "ACTIVE"
            )
        ]

        total_risk_seconds = 0.0

        for event in risk_events:
            if not isinstance(
                event,
                dict,
            ):
                continue

            duration = event.get(
                "duration_seconds"
            )

            if type(duration) in (
                int,
                float,
            ):
                total_risk_seconds += max(
                    0.0,
                    float(
                        duration
                    ),
                )

        notification_count = len(
            notifications
        )

        first_count = sum(
            1
            for item in notifications
            if (
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "alert_type"
                ) == "FIRST"
            )
        )

        repeat_count = sum(
            1
            for item in notifications
            if (
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "alert_type"
                ) == "REPEAT"
            )
        )

        escalation_count = sum(
            1
            for item in notifications
            if (
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "alert_type"
                ) == "ESCALATION"
            )
        )

        eye_count = len(
            eye_notifications
        )

        eye_first = sum(
            1
            for item in eye_notifications
            if (
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "alert_type"
                ) == "FIRST"
            )
        )

        eye_repeat = sum(
            1
            for item in eye_notifications
            if (
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "alert_type"
                ) == "REPEAT"
            )
        )

        # ====================================================
        # USER-FACING VALUES
        # ====================================================

        self.alert_total_label.setText(
            str(
                notification_count
            )
        )

        if hasattr(
            self,
            "alert_total_detail_label",
        ):
            self.alert_total_detail_label.setText(
                (
                    f"???????? {first_count}  ?  "
                    f"??? {repeat_count}  ?  "
                    f"?????????? {escalation_count}\n"
                    f"????? {eye_count} ????? "
                    f"(???????? {eye_first}, "
                    f"??? {eye_repeat})"
                )
            )

        self.alert_closed_label.setText(
            str(
                len(
                    resolved_events
                )
            )
        )

        self.alert_active_label.setText(
            str(
                len(
                    active_events
                )
            )
        )

        minutes = int(
            total_risk_seconds // 60
        )

        seconds = int(
            total_risk_seconds % 60
        )

        self.alert_duration_label.setText(
            f"{minutes:02d}:{seconds:02d}"
        )


    # ========================================================
    # ALERT HISTORY
    # ========================================================

    def open_alert_history(
        self,
    ) -> None:
        dialog = (
            AlertHistoryDialog(
                self,
                session_id=(
                    self.current_session_id
                ),
            )
        )

        dialog.exec()

    # ========================================================
    # BACK
    # ========================================================

    def go_back(
        self,
    ) -> None:
        status = (
            self.current_summary
            or {}
        ).get(
            "summary_save_status"
        )

        if status not in (
            "SAVED",
            "ALREADY_EXISTS",
            "LOADED",
        ):
            answer = QMessageBox.question(
                self,
                "รายงานยังไม่ถูกบันทึก",
                (
                    "รายงานของเซสชันนี้ยังไม่ได้"
                    "บันทึกสำเร็จ "
                    "หากออกจากหน้านี้ตอนนี้ คุณอาจไม่สามารถ"
                    "ลองบันทึกใหม่ด้วยข้อมูลชุดเดิมได้\n\n"
                    "ต้องการออกจากรายงานนี้หรือไม่?"
                ),
                (
                    QMessageBox.StandardButton.Yes
                    |
                    QMessageBox.StandardButton.No
                ),
                QMessageBox.StandardButton.No,
            )

            if (
                answer
                !=
                QMessageBox.StandardButton.Yes
            ):
                return

        self.back_requested.emit()
