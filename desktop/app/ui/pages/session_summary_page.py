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

        scroll_area.setWidgetResizable(
            True
        )

        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        scroll_area.setFrameShape(
            QScrollArea.Shape.NoFrame
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
            24,
            18,
            24,
            20,
        )

        layout.setSpacing(
            14
        )

        layout.setSizeConstraint(
            QLayout.SizeConstraint.SetMinimumSize
        )

        scroll_area.setWidget(
            content
        )

        page_layout.addWidget(
            scroll_area
        )

        # ====================================================
        # HEADER
        # ====================================================

        self.title_label = QLabel(
            "Session Summary"
        )

        self.title_label.setProperty(
            "role",
            "title",
        )

        self.description_label = QLabel(
            (
                "สรุปผลการตรวจจับ "
                "Posture Risk และ "
                "PostGuard Risk Score"
            )
        )

        self.description_label.setProperty(
            "role",
            "muted",
        )

        # ====================================================
        # SESSION INFORMATION
        # ====================================================

        info_group = QGroupBox(
            "Session Information"
        )

        info_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        info_layout = QVBoxLayout(
            info_group
        )

        self.session_label = QLabel(
            "Session ID: --"
        )

        self.database_label = QLabel(
            "สถานะเซสชัน: --"
        )

        self.camera_label = QLabel(
            "กล้อง: --"
        )

        self.baseline_label = QLabel(
            "Baseline ID: --"
        )

        self.start_label = QLabel(
            "เริ่มเมื่อ: --"
        )

        self.end_label = QLabel(
            "สิ้นสุดเมื่อ: --"
        )

        self.duration_label = QLabel(
            "ระยะเวลา: --"
        )

        self.paused_duration_label = QLabel(
            "เวลาหยุดชั่วคราว: --"
        )

        self.pause_count_label = QLabel(
            "จำนวนครั้งที่หยุด: --"
        )

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
            info_layout.addWidget(
                widget
            )

        # ====================================================
        # DETECTION SUMMARY
        # ====================================================

        detection_group = QGroupBox(
            "Detection Summary"
        )

        detection_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        detection_layout = QVBoxLayout(
            detection_group
        )

        self.count_label = QLabel(
            "รอบการตรวจจับ: --"
        )

        self.pose_label = QLabel(
            "ตรวจพบท่าทาง: --"
        )

        self.face_label = QLabel(
            "ตรวจพบใบหน้า: --"
        )

        self.shoulder_label = QLabel(
            "ความเอียงไหล่เฉลี่ย: --"
        )

        self.neck_label = QLabel(
            "ความเอียงคอเฉลี่ย: --"
        )

        self.baseline_shoulder_label = QLabel(
            "ค่าอ้างอิงไหล่: --"
        )

        self.baseline_neck_label = QLabel(
            "ค่าอ้างอิงคอ: --"
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
            detection_layout.addWidget(
                widget
            )

        # ====================================================
        # RISK SCORE SUMMARY
        # ====================================================

        risk_score_group = QGroupBox(
            "PostGuard Risk Score"
        )

        risk_score_layout = QVBoxLayout(
            risk_score_group
        )

        score_cards = QHBoxLayout()

        self.average_score_card = (
            self._create_score_card(
                "AVERAGE",
                "--",
            )
        )

        self.minimum_score_card = (
            self._create_score_card(
                "MINIMUM",
                "--",
            )
        )

        self.maximum_score_card = (
            self._create_score_card(
                "MAXIMUM",
                "--",
            )
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

        self.average_risk_label = QLabel(
            "คะแนนความเสี่ยงเฉลี่ย: N/A"
        )

        self.minimum_risk_label = QLabel(
            "คะแนนความเสี่ยงต่ำสุด: N/A"
        )

        self.maximum_risk_label = QLabel(
            "คะแนนความเสี่ยงสูงสุด: N/A"
        )

        self.risk_score_method_label = QLabel(
            "วิธีคำนวณคะแนน: N/A"
        )

        self.risk_score_method_label.setProperty(
            "role",
            "muted",
        )

        for widget in (
            self.average_risk_label,
            self.minimum_risk_label,
            self.maximum_risk_label,
            self.risk_score_method_label,
        ):
            risk_score_layout.addWidget(
                widget
            )

        # ====================================================
        # RISK SCORE GRAPH
        # ====================================================

        chart_group = QGroupBox(
            "Risk Score Over Session"
        )

        chart_layout = QVBoxLayout(
            chart_group
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

        # ====================================================
        # REPORT SUMMARY
        # ====================================================

        report_group = QGroupBox(
            "ข้อมูลสรุปในรายงาน"
        )

        report_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        report_layout = QVBoxLayout(
            report_group
        )

        self.blink_rate_label = QLabel(
            "อัตราการกะพริบตา: N/A"
        )

        self.report_alert_count_label = QLabel(
            "จำนวนการแจ้งเตือนที่บันทึก: --"
        )

        self.frequent_event_label = QLabel(
            "การแจ้งเตือนที่พบบ่อยที่สุด: N/A"
        )

        self.risk_breakdown_label = QLabel(
            "รายละเอียดความเสี่ยง: --"
        )

        self.risk_breakdown_label.setWordWrap(
            True
        )

        for widget in (
            self.blink_rate_label,
            self.report_alert_count_label,
            self.frequent_event_label,
            self.risk_breakdown_label,
        ):
            report_layout.addWidget(
                widget
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

        # ====================================================
        # ALERT / RISK EVENTS
        # ====================================================

        alert_group = QGroupBox(
            "เหตุการณ์ความเสี่ยงและการแจ้งเตือน"
        )

        alert_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        alert_layout = QVBoxLayout(
            alert_group
        )

        self.alert_total_label = QLabel(
            "การแจ้งเตือนทั้งหมด: --"
        )

        self.alert_closed_label = QLabel(
            "เหตุการณ์ความเสี่ยงที่สิ้นสุดแล้ว: --"
        )

        self.alert_active_label = QLabel(
            "เหตุการณ์ความเสี่ยงที่ยังทำงานอยู่: --"
        )

        self.alert_duration_label = QLabel(
            "ระยะเวลาความเสี่ยงรวม: --"
        )

        self.alert_error_label = QLabel(
            ""
        )

        self.alert_error_label.setWordWrap(
            True
        )

        for widget in (
            self.alert_total_label,
            self.alert_closed_label,
            self.alert_active_label,
            self.alert_duration_label,
            self.alert_error_label,
        ):
            alert_layout.addWidget(
                widget
            )

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

        alert_layout.addLayout(
            alert_buttons
        )

        # ====================================================
        # NOTE
        # ====================================================

        self.note_label = QLabel(
            (
                "PostGuard Risk Score 0-100 "
                "เป็นคะแนนนำเสนอที่แปลงมาจาก "
                "PostGuard Modified RULA สำหรับระบบกล้องด้านหน้า "
                "ไม่ใช่ความน่าจะเป็นของการบาดเจ็บ "
                "ไม่ใช่ Full RULA และไม่ใช่การวินิจฉัยทางการแพทย์"
            )
        )

        self.note_label.setWordWrap(
            True
        )

        self.note_label.setProperty(
            "role",
            "muted",
        )

        # ====================================================
        # BACK
        # ====================================================

        self.back_button = QPushButton(
            "Back to Dashboard"
        )

        self.back_button.clicked.connect(
            self.go_back
        )

        # ====================================================
        # ADD TO PAGE
        # ====================================================

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.description_label
        )

        layout.addWidget(
            info_group
        )

        layout.addWidget(
            detection_group
        )

        layout.addWidget(
            risk_score_group
        )

        layout.addWidget(
            chart_group
        )

        layout.addWidget(
            report_group
        )

        layout.addWidget(
            self.save_group
        )

        layout.addWidget(
            alert_group
        )

        layout.addWidget(
            self.note_label
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
                        f"{count_text} alert(s), "
                        f"{duration_text(seconds)} "
                        "open time"
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
            "Saved Session Report"
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
                "Session ID: "
                f"{self.current_session_id}"
            )
        )

        self.database_label.setText(
            (
                "Session Status: "
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
                "Camera: "
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
                "Baseline ID: "
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
                "Started: "
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
                "Ended: "
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
                "จำนวนการแจ้งเตือนที่บันทึก: "
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
                "ไม่พบ Session ID สำหรับโหลดกราฟ"
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
                    "ไม่สามารถโหลด Risk Score graph ได้: "
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
                    "Session นี้ไม่มี COMPLETE "
                    "Risk Score samples"
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
                f"{len(buckets)} buckets | "
                f"{total_samples} valid score samples | "
                f"{first_second:.0f}-"
                f"{last_second:.0f} sec"
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
                    "The session report has not "
                    "been saved.\n"
                    +
                    str(
                        error
                        or
                        "Unknown error"
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
        self.alert_total_label.setText(
            "การแจ้งเตือนทั้งหมด: --"
        )

        self.alert_closed_label.setText(
            "เหตุการณ์ความเสี่ยงที่สิ้นสุดแล้ว: --"
        )

        self.alert_active_label.setText(
            "เหตุการณ์ความเสี่ยงที่ยังทำงานอยู่: --"
        )

        self.alert_duration_label.setText(
            "ระยะเวลาความเสี่ยงรวม: --"
        )

        self.alert_error_label.setText(
            ""
        )

        session_id = (
            self.current_session_id
        )

        if (
            type(session_id)
            is not int
            or
            session_id <= 0
        ):
            self.alert_error_label.setText(
                "ไม่พบ Session ID ที่ถูกต้อง"
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
                    (
                        "GET risk-events returned "
                        f"HTTP "
                        f"{risk_response.status_code}"
                    )
                )

            risk_events = (
                risk_response.json()
            )

            if not isinstance(
                risk_events,
                list,
            ):
                raise ValueError(
                    "Invalid Risk Event response."
                )

            notification_response = (
                APIClient
                .get_session_alert_notifications(
                    session_id
                )
            )

            if not notification_response.ok:
                raise RuntimeError(
                    (
                        "GET alert-notifications returned "
                        f"HTTP "
                        f"{notification_response.status_code}"
                    )
                )

            notifications = (
                notification_response.json()
            )

            if not isinstance(
                notifications,
                list,
            ):
                raise ValueError(
                    (
                        "Invalid Alert Notification "
                        "response."
                    )
                )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            self.alert_error_label.setText(
                (
                    "ไม่สามารถโหลดข้อมูล "
                    "Risk Event / Alert Notification ได้: "
                    f"{error}"
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
                and
                event.get(
                    "status"
                )
                ==
                "RESOLVED"
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
                and
                event.get(
                    "status"
                )
                ==
                "ACTIVE"
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

            if (
                type(duration)
                in
                (
                    int,
                    float,
                )
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
            for notification
            in notifications
            if (
                isinstance(
                    notification,
                    dict,
                )
                and
                notification.get(
                    "alert_type"
                )
                ==
                "FIRST"
            )
        )

        repeat_count = sum(
            1
            for notification
            in notifications
            if (
                isinstance(
                    notification,
                    dict,
                )
                and
                notification.get(
                    "alert_type"
                )
                ==
                "REPEAT"
            )
        )

        escalation_count = sum(
            1
            for notification
            in notifications
            if (
                isinstance(
                    notification,
                    dict,
                )
                and
                notification.get(
                    "alert_type"
                )
                ==
                "ESCALATION"
            )
        )

        self.alert_total_label.setText(
            (
                "การแจ้งเตือนทั้งหมด: "
                f"{notification_count} ครั้ง "
                f"(ครั้งแรก {first_count}, "
                f"ซ้ำ {repeat_count}, "
                "ระดับความเสี่ยงเพิ่มขึ้น "
                f"{escalation_count})"
            )
        )

        self.alert_closed_label.setText(
            (
                "เหตุการณ์ความเสี่ยงที่สิ้นสุดแล้ว: "
                f"{len(resolved_events)} ครั้ง"
            )
        )

        self.alert_active_label.setText(
            (
                "เหตุการณ์ความเสี่ยงที่ยังทำงานอยู่: "
                f"{len(active_events)} ครั้ง"
            )
        )

        minutes = int(
            total_risk_seconds
            //
            60
        )

        seconds = int(
            total_risk_seconds
            %
            60
        )

        self.alert_duration_label.setText(
            (
                "ระยะเวลาความเสี่ยงรวม: "
                f"{minutes:02d}:{seconds:02d}"
            )
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
                    "This session report has not been "
                    "saved successfully. "
                    "If you leave now, you may not be "
                    "able to retry with the same data.\n\n"
                    "Leave this report?"
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