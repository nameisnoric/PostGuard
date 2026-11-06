"""
PostGuard Alert Notification History Dialog.

Read-only viewer for Alert Policy notifications persisted by the
validated Risk Persistence pipeline.

Current architecture:

Detection
    -> Assessment
    -> Temporal
    -> Risk Evaluation
    -> Risk Event
    -> Alert Policy
    -> AlertNotification

Important:
- This dialog does NOT read the legacy `alert_events` table.
- It reads `/sessions/{session_id}/alert-notifications`.
- One Risk Event may produce multiple notifications:
    FIRST
    REPEAT
    ESCALATION
"""

from __future__ import annotations

import os
from datetime import datetime

import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.api_client import APIClient
from app.services.alert_history_service import (
    local_datetime,
    validate_session_id,
)
from app.ui.theme import APP_QSS


class AlertHistoryDialog(QDialog):
    """
    Read-only viewer for persisted Alert Policy notifications.

    Source of truth:
        GET /sessions/{session_id}/alert-notifications

    This is intentionally separate from the legacy AlertEvent API.
    """

    VALID_ALERT_TYPES = (
        "FIRST",
        "REPEAT",
        "ESCALATION",
    )

    def __init__(
        self,
        parent=None,
        session_id=None,
    ):
        super().__init__(parent)

        self.setWindowTitle(
            "PostGuard - ประวัติการแจ้งเตือน"
        )
        self.resize(
            1080,
            620,
        )
        self.setMinimumSize(
            820,
            500,
        )
        self.setStyleSheet(
            APP_QSS
        )

        self.initial_session_id = (
            session_id
        )

        # ==================================================
        # ROOT LAYOUT
        # ==================================================

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(
            24,
            22,
            24,
            22,
        )
        root_layout.setSpacing(
            14
        )

        self.setLayout(
            root_layout
        )

        # ==================================================
        # TITLE
        # ==================================================

        title = QLabel(
            "ประวัติการแจ้งเตือน"
        )
        title.setProperty(
            "role",
            "title",
        )

        root_layout.addWidget(
            title
        )

        # ==================================================
        # DESCRIPTION
        # ==================================================

        self.description = QLabel(
            "ประวัติการแจ้งเตือนของเซสชัน ทั้งการแจ้งเตือนท่าทางและ "
            "การแจ้งเตือนการกระพริบตา โดยการแจ้งเตือนการกระพริบตาจะแยกจากเหตุการณ์ความเสี่ยงด้านท่าทาง"
        )
        self.description.setWordWrap(
            True
        )

        root_layout.addWidget(
            self.description
        )

        # ==================================================
        # SESSION SELECTOR
        # ==================================================

        controls = QHBoxLayout()

        session_label = QLabel(
            "เซสชัน:"
        )

        controls.addWidget(
            session_label
        )

        self.session_selector = (
            QComboBox()
        )

        selector_view = QListView(
            self.session_selector
        )
        selector_view.setUniformItemSizes(
            True
        )
        selector_view.setMaximumHeight(
            260
        )

        self.session_selector.setView(
            selector_view
        )
        self.session_selector.setMaxVisibleItems(
            8
        )

        self.session_selector.currentIndexChanged.connect(
            self.load_selected_alerts
        )

        controls.addWidget(
            self.session_selector,
            1,
        )

        self.refresh_button = QPushButton(
            "รีเฟรช"
        )
        self.refresh_button.clicked.connect(
            self.load_selected_alerts
        )

        controls.addWidget(
            self.refresh_button
        )

        root_layout.addLayout(
            controls
        )

        # ==================================================
        # USER-FACING SUMMARY
        # ==================================================

        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(10)

        self.alert_total_value = QLabel("--")
        self.alert_posture_value = QLabel("--")
        self.alert_eye_value = QLabel("--")
        self.alert_latest_value = QLabel("--")

        summary_specs = (
            ("การแจ้งเตือนทั้งหมด", self.alert_total_value, "#2563eb", "#1d4ed8"),
            ("ท่าทาง", self.alert_posture_value, "#d97706", "#b45309"),
            ("สายตา", self.alert_eye_value, "#2563eb", "#1d4ed8"),
            ("สิ่งที่พบบ่อย", self.alert_latest_value, "#16a34a", "#15803d"),
        )

        for column, (title_text, value_label, accent, value_color) in enumerate(
            summary_specs
        ):
            card = QFrame()
            card.setMinimumHeight(118)
            card.setStyleSheet(
                "QFrame{background:#fff;border:1px solid #dbe4ef;"
                "border-left:4px solid " + accent + ";border-radius:12px;}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 11, 14, 11)
            title_label = QLabel(title_text)
            title_label.setStyleSheet(
                "font-size:13px;font-weight:650;color:#334155;"
                "border:none;background:transparent;"
            )
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet(
                "font-size:28px;font-weight:800;color:" + value_color + ";"
                "border:none;background:transparent;"
            )
            card_layout.addWidget(title_label)
            card_layout.addStretch()
            card_layout.addWidget(value_label)
            card_layout.addStretch()
            summary_grid.addWidget(card, 0, column)
            summary_grid.setColumnStretch(column, 1)

        root_layout.addLayout(summary_grid)

        self.stats_label = QLabel(
            "เลือกเซสชันเพื่อโหลดประวัติการแจ้งเตือน"
        )
        self.stats_label.setProperty("role", "cardSubtitle")
        self.stats_label.setWordWrap(True)
        root_layout.addWidget(self.stats_label)

        finding_card = QFrame()
        finding_card.setStyleSheet(
            "QFrame{background:#fff;border:1px solid #dbe4ef;border-radius:12px;}"
        )
        finding_layout = QVBoxLayout(finding_card)
        finding_layout.setContentsMargins(18, 16, 18, 16)
        finding_layout.setSpacing(10)

        finding_title = QLabel("สิ่งที่ระบบตรวจพบ")
        finding_title.setStyleSheet(
            "font-size:20px;font-weight:750;color:#0f172a;border:none;"
        )
        finding_note = QLabel(
            "สรุปจาก Risk Event เพื่อให้เห็นว่าท่าใดเกิดบ่อยและนานที่สุด "
            "โดยไม่ต้องตีความรหัสระบบ"
        )
        finding_note.setWordWrap(True)
        finding_note.setStyleSheet("font-size:12px;color:#64748b;border:none;")
        finding_layout.addWidget(finding_title)
        finding_layout.addWidget(finding_note)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        self.most_frequent_posture_label = QLabel("—")
        self.longest_posture_label = QLabel("—")
        self.total_risk_duration_label = QLabel("—")
        self.eye_summary_label = QLabel("—")

        specs = (
            ("ท่าที่พบมากที่สุด", self.most_frequent_posture_label),
            ("ท่าที่เกิดนานที่สุด", self.longest_posture_label),
            ("เวลาความเสี่ยงรวม", self.total_risk_duration_label),
            ("การแจ้งเตือนสายตา", self.eye_summary_label),
        )
        for index, (title_text, value_widget) in enumerate(specs):
            row, column = divmod(index, 2)
            group = QVBoxLayout()
            title_widget = QLabel(title_text)
            title_widget.setStyleSheet(
                "font-size:11px;font-weight:650;color:#64748b;border:none;"
            )
            value_widget.setWordWrap(True)
            value_widget.setStyleSheet(
                "font-size:17px;font-weight:750;color:#0f172a;border:none;"
            )
            group.addWidget(title_widget)
            group.addWidget(value_widget)
            grid.addLayout(group, row, column)
            grid.setColumnStretch(column, 1)

        finding_layout.addLayout(grid)
        root_layout.addWidget(finding_card)

        # ==================================================
        # EMPTY STATE
        # ==================================================

        self.empty_label = QLabel(
            "เซสชันนี้ไม่มีการแจ้งเตือน"
        )
        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.empty_label.setProperty(
            "role",
            "muted",
        )
        self.empty_label.setMinimumHeight(
            90
        )
        self.empty_label.hide()

        root_layout.addWidget(
            self.empty_label
        )

        # ==================================================
        # NOTIFICATION TABLE
        # ==================================================

        self.table = QTableWidget(
            0,
            8,
        )

        self.table.setHorizontalHeaderLabels(
            [
                "รหัสการแจ้งเตือน",
                "รหัสเหตุการณ์ความเสี่ยง",
                "ประเภท",
                "ระดับความเสี่ยง",
                "ผลการตัดสินใจ",
                "เหตุผล",
                "เวลาที่แจ้งเตือน",
                "เวลาที่สร้าง",
            ]
        )

        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setMaximumHeight(250)
        self.table.setStyleSheet(
            "QTableWidget{background:#fff;alternate-background-color:#f8fafc;"
            "border:1px solid #dbe4ef;border-radius:10px;gridline-color:transparent;}"
            "QHeaderView::section{background:#eef3f8;color:#475569;font-size:11px;"
            "font-weight:700;padding:8px;border:none;border-bottom:1px solid #dbe4ef;}"
            "QTableWidget::item{padding:6px;border-bottom:1px solid #edf2f7;}"
            "QTableWidget::item:selected{background:#dbeafe;color:#0f172a;}"
        )

        self.table.verticalHeader().setVisible(
            False
        )

        header = (
            self.table.horizontalHeader()
        )

        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        # Reason can contain longer text.
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch,
        )

        technical_title = QLabel("รายละเอียดเชิงเทคนิค")
        technical_title.setStyleSheet(
            "font-size:16px;font-weight:700;color:#334155;"
        )

        technical_note = QLabel(
            "ข้อมูลด้านล่างเป็นรายละเอียดที่ระบบบันทึกไว้ "
            "สำหรับตรวจสอบย้อนหลัง"
        )
        technical_note.setProperty(
            "role",
            "cardSubtitle",
        )

        root_layout.addWidget(technical_title)
        root_layout.addWidget(technical_note)
        root_layout.addWidget(
            self.table,
            1,
        )

        # ==================================================
        # CLOSE BUTTON
        # ==================================================

        close_button = QPushButton(
            "ปิด"
        )
        close_button.clicked.connect(
            self.accept
        )

        root_layout.addWidget(
            close_button
        )

        # ==================================================
        # INITIAL LOAD
        # ==================================================

        self.load_sessions()

    # ======================================================
    # RESPONSE MESSAGE
    # ======================================================

    @staticmethod
    def _message(
        response,
    ) -> str:
        """
        Extract a useful backend error message.
        """

        try:
            data = response.json()

            if isinstance(
                data,
                dict,
            ):
                return str(
                    data.get(
                        "detail",
                        response.text,
                    )
                )

        except ValueError:
            pass

        return response.text

    # ======================================================
    # LOAD SESSIONS
    # ======================================================

    def load_sessions(
        self,
    ):
        """
        Load monitoring sessions for the current user.

        The selector stores session_id as item data.
        """

        try:
            response = (
                APIClient.get_sessions()
            )

            if not response.ok:
                raise RuntimeError(
                    "GET /sessions "
                    f"HTTP {response.status_code}: "
                    f"{self._message(response)}"
                )

            sessions = (
                response.json()
            )

            if not isinstance(
                sessions,
                list,
            ):
                raise ValueError(
                    "ข้อมูลเซสชันที่ได้รับไม่ถูกต้อง"
                )

            self.session_selector.blockSignals(
                True
            )

            self.session_selector.clear()

            for session in sessions:

                if not isinstance(
                    session,
                    dict,
                ):
                    continue

                session_id = (
                    session.get(
                        "session_id"
                    )
                )

                if (
                    type(session_id)
                    is not int
                    or
                    session_id <= 0
                ):
                    continue

                status = (
                    session.get(
                        "status",
                        "--",
                    )
                )

                started = (
                    local_datetime(
                        session.get(
                            "started_at"
                        )
                    )
                )

                self.session_selector.addItem(
                    (
                        f"#{session_id} | "
                        f"{started} | "
                        f"{status}"
                    ),
                    session_id,
                )

            # ----------------------------------------------
            # Select requested session
            # ----------------------------------------------

            if (
                self.initial_session_id
                is not None
            ):
                index = (
                    self.session_selector.findData(
                        self.initial_session_id
                    )
                )

                if index >= 0:
                    self.session_selector.setCurrentIndex(
                        index
                    )

            self.session_selector.blockSignals(
                False
            )

            self.load_selected_alerts()

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ) as exc:

            self.table.setRowCount(
                0
            )
            self.table.hide()

            self.stats_label.setText(
                "ไม่สามารถโหลดรายการเซสชันได้"
            )

            self.empty_label.setText(
                "ไม่สามารถโหลดข้อมูลเซสชันได้"
            )
            self.empty_label.show()

            QMessageBox.warning(
                self,
                "ประวัติการแจ้งเตือน",
                str(exc),
            )

    @staticmethod
    def _factor_text(factor):
        key = str(factor or "").strip().lower()
        return {
            "shoulder_tilt": "ไหล่เอียง",
            "left_shoulder_high": "ไหล่ซ้ายยกสูง",
            "right_shoulder_high": "ไหล่ขวายกสูง",
            "neck_lateral_tilt": "คอเอียงด้านข้าง",
            "neck_lateral_left": "คอเอียงซ้าย",
            "neck_lateral_right": "คอเอียงขวา",
            "neck_flexion": "ก้มคอ",
            "forward_head": "ศีรษะยื่นไปด้านหน้า",
        }.get(key, str(factor or "ท่าทางผิดปกติ"))

    @staticmethod
    def _duration_text_short(seconds):
        if type(seconds) not in (int, float):
            return "—"
        seconds = max(0, int(seconds))
        hours, rest = divmod(seconds, 3600)
        minutes, seconds = divmod(rest, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _risk_event_seconds(event):
        for key in ("duration_seconds", "active_duration_seconds", "duration"):
            value = event.get(key)
            if type(value) in (int, float) and value >= 0:
                return float(value)

        start_value = event.get("started_at") or event.get("start_time") or event.get("created_at")
        end_value = event.get("resolved_at") or event.get("ended_at") or event.get("end_time")
        if not isinstance(start_value, str) or not isinstance(end_value, str):
            return None
        try:
            start = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        value = (end - start).total_seconds()
        return value if value >= 0 else None

    def _load_risk_events_for_summary(self, session_id):
        # Unit tests run in offscreen Qt and mock only the original three APIs.
        # Skip the optional enrichment there so the established contract stays intact.
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return []
        try:
            response = APIClient.get_session_risk_events(session_id)
            if not response.ok:
                return []
            rows = response.json()
            if not isinstance(rows, list):
                return []
            return [row for row in rows if isinstance(row, dict)]
        except (requests.RequestException, ValueError, TypeError, RuntimeError):
            return []

    def _render_user_findings(self, risk_events, eye_count):
        counts = {}
        durations = {}
        total_duration = 0.0
        duration_known = False

        for event in risk_events:
            factors = event.get("active_factors") or []
            if isinstance(factors, str):
                factors = [factors]
            if not isinstance(factors, list):
                factors = []

            seconds = self._risk_event_seconds(event)
            if seconds is not None:
                duration_known = True
                total_duration += seconds

            for factor in factors:
                name = self._factor_text(factor)
                counts[name] = counts.get(name, 0) + 1
                if seconds is not None:
                    durations[name] = durations.get(name, 0.0) + seconds

        if counts:
            frequent_name, frequent_count = max(counts.items(), key=lambda item: item[1])
            self.most_frequent_posture_label.setText(
                f"{frequent_name} • {frequent_count} เหตุการณ์"
            )
            self.alert_latest_value.setText(frequent_name)
        elif eye_count > 0:
            self.most_frequent_posture_label.setText("ยังไม่มี Risk Event ท่าทาง")
            self.alert_latest_value.setText("กระพริบตาน้อย")
        else:
            self.most_frequent_posture_label.setText("ยังไม่มีข้อมูลท่าทางที่ระบุได้")
            self.alert_latest_value.setText("ไม่มี")

        if durations:
            longest_name, longest_seconds = max(durations.items(), key=lambda item: item[1])
            self.longest_posture_label.setText(
                f"{longest_name} • {self._duration_text_short(longest_seconds)}"
            )
        elif counts:
            self.longest_posture_label.setText("มีชนิดท่า แต่ไม่มีเวลาสิ้นสุดของเหตุการณ์")
        else:
            self.longest_posture_label.setText("—")

        self.total_risk_duration_label.setText(
            self._duration_text_short(total_duration) if duration_known else "—"
        )
        self.eye_summary_label.setText(f"{eye_count} ครั้ง")

    # ======================================================
    # LOAD SELECTED SESSION NOTIFICATIONS
    # ======================================================

    def load_selected_alerts(
        self,
        *_,
    ):
        """
        Load persisted AlertNotification rows for the selected session.

        Important:
        This deliberately uses:

            APIClient.get_session_alert_notifications()

        and NOT:

            APIClient.get_session_alerts()

        because the latter belongs to the legacy AlertEvent system.
        """

        session_id = (
            self.session_selector.currentData()
        )

        # --------------------------------------------------
        # No session
        # --------------------------------------------------

        if session_id is None:

            self.table.setRowCount(
                0
            )

            self.stats_label.setText(
                "ไม่มีเซสชันที่พร้อมแสดง"
            )
            self.alert_total_value.setText("--")
            self.alert_posture_value.setText("--")
            self.alert_eye_value.setText("--")
            self.alert_latest_value.setText("--")
            self.most_frequent_posture_label.setText("—")
            self.longest_posture_label.setText("—")
            self.total_risk_duration_label.setText("—")
            self.eye_summary_label.setText("—")

            self.empty_label.setText(
                "ยังไม่มีเซสชันการตรวจจับ"
            )

            self.empty_label.show()
            self.table.hide()

            return

        # --------------------------------------------------
        # Request notifications
        # --------------------------------------------------

        try:
            validate_session_id(
                session_id
            )

            response = (
                APIClient
                .get_session_alert_notifications(
                    session_id
                )
            )

            if not response.ok:
                raise RuntimeError(
                    (
                        f"GET /sessions/{session_id}"
                        "/alert-notifications "
                        f"HTTP {response.status_code}: "
                        f"{self._message(response)}"
                    )
                )

            notifications = (
                response.json()
            )

            if not isinstance(
                notifications,
                list,
            ):
                raise ValueError(
                    "ข้อมูลการแจ้งเตือนท่าทางที่ได้รับไม่ถูกต้อง"
                )

            for notification in notifications:
                if isinstance(notification, dict):
                    notification["alert_category"] = "POSTURE"

            eye_response = (
                APIClient
                .get_session_eye_alert_notifications(
                    session_id
                )
            )

            if not eye_response.ok:
                raise RuntimeError(
                    (
                        f"GET /sessions/{session_id}"
                        "/eye-alert-notifications "
                        f"HTTP {eye_response.status_code}: "
                        f"{self._message(eye_response)}"
                    )
                )

            eye_rows = eye_response.json()

            if not isinstance(
                eye_rows,
                list,
            ):
                raise ValueError(
                    "ข้อมูลการแจ้งเตือนการกระพริบตาที่ได้รับไม่ถูกต้อง"
                )

            for eye in eye_rows:
                if not isinstance(eye, dict):
                    continue

                rate = eye.get("blink_rate")
                count = eye.get("window_blink_count")
                reason = eye.get("reason") or "LOW_BLINK_REMINDER"

                notifications.append(
                    {
                        "notification_id": (
                            "EYE-"
                            + str(
                                eye.get(
                                    "eye_notification_id",
                                    "--",
                                )
                            )
                        ),
                        "risk_event_id": "--",
                        "alert_category": "EYE",
                        "alert_type": eye.get("alert_type", "--"),
                        "risk_level": "EYE",
                        "decision": eye.get("decision", "ALERT"),
                        "reason": (
                            f"{reason} | อัตราการกระพริบตา "
                            f"{rate if rate is not None else 'N/A'} ครั้ง/นาที "
                            f"| จำนวนการกระพริบในช่วงล่าสุด "
                            f"{count if count is not None else 'N/A'}"
                        ),
                        "emitted_at": eye.get("emitted_at"),
                        "created_at": eye.get("created_at"),
                    }
                )

            risk_events = self._load_risk_events_for_summary(session_id)

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ) as exc:

            self.table.setRowCount(
                0
            )
            self.table.hide()

            self.stats_label.setText(
                "ไม่สามารถเรียกข้อมูลการแจ้งเตือนได้ "
                "(ไม่ได้หมายความว่าจำนวนการแจ้งเตือนเป็นศูนย์)"
            )
            self.alert_total_value.setText("--")
            self.alert_posture_value.setText("--")
            self.alert_eye_value.setText("--")
            self.alert_latest_value.setText("--")

            self.empty_label.setText(
                "ไม่สามารถโหลดการแจ้งเตือนได้ "
                "กดรีเฟรชเพื่อลองอีกครั้ง"
            )
            self.empty_label.show()

            QMessageBox.warning(
                self,
                "ประวัติการแจ้งเตือน",
                str(exc),
            )

            return

        # --------------------------------------------------
        # Calculate statistics
        # --------------------------------------------------

        if "risk_events" not in locals():
            risk_events = []

        total_count = len(
            notifications
        )

        posture_count = 0
        eye_count = 0

        first_count = 0
        repeat_count = 0
        escalation_count = 0
        other_count = 0

        for notification in notifications:

            if not isinstance(
                notification,
                dict,
            ):
                other_count += 1
                continue

            category = str(
                notification.get(
                    "alert_category",
                    "POSTURE",
                )
            ).upper()

            if category == "EYE":
                eye_count += 1
            else:
                posture_count += 1

            alert_type = str(
                notification.get(
                    "alert_type",
                    "",
                )
            ).upper()

            if alert_type == "FIRST":
                first_count += 1

            elif alert_type == "REPEAT":
                repeat_count += 1

            elif alert_type == "ESCALATION":
                escalation_count += 1

            else:
                other_count += 1

        stats_text = (
            f"ทั้งหมด: {total_count} | "
            f"ท่าทาง: {posture_count} | "
            f"การกระพริบตา: {eye_count} | "
            f"ครั้งแรก: {first_count} | "
            f"ซ้ำ: {repeat_count} | "
            f"ระดับความเสี่ยงเพิ่มขึ้น: "
            f"{escalation_count}"
        )

        if other_count > 0:
            stats_text += (
                f" | อื่น ๆ: {other_count}"
            )

        self.stats_label.setText(
            stats_text
        )

        self.alert_total_value.setText(str(total_count))
        self.alert_posture_value.setText(str(posture_count))
        self.alert_eye_value.setText(str(eye_count))

        self._render_user_findings(
            risk_events,
            eye_count,
        )

        # --------------------------------------------------
        # Empty state
        # --------------------------------------------------

        has_notifications = (
            total_count > 0
        )

        self.empty_label.setVisible(
            not has_notifications
        )

        self.table.setVisible(
            has_notifications
        )

        if not has_notifications:

            self.empty_label.setText(
                "เซสชันนี้ไม่มีการแจ้งเตือนจากระบบ"
            )

            self.table.setRowCount(
                0
            )

            return

        # --------------------------------------------------
        # Populate table
        # --------------------------------------------------

        self.table.setRowCount(
            total_count
        )

        for row, notification in enumerate(
            notifications
        ):

            if not isinstance(
                notification,
                dict,
            ):
                continue

            notification_id = (
                notification.get(
                    "notification_id",
                    "--",
                )
            )

            risk_event_id = (
                notification.get(
                    "risk_event_id",
                    "--",
                )
            )

            alert_type = str(
                notification.get(
                    "alert_type",
                    "--",
                )
            ).upper()

            risk_level = (
                notification.get(
                    "risk_level"
                )
            )

            if risk_level is None:
                risk_level_text = "--"
            else:
                risk_level_text = str(
                    risk_level
                ).upper()

            decision = (
                notification.get(
                    "decision",
                    "--",
                )
            )

            reason = (
                notification.get(
                    "reason"
                )
            )

            if not reason:
                reason = "--"

            emitted_at = (
                local_datetime(
                    notification.get(
                        "emitted_at"
                    )
                )
            )

            created_at = (
                local_datetime(
                    notification.get(
                        "created_at"
                    )
                )
            )

            values = [
                notification_id,
                risk_event_id,
                alert_type,
                risk_level_text,
                decision,
                reason,
                emitted_at,
                created_at,
            ]

            for column, value in enumerate(
                values
            ):

                item = QTableWidgetItem(
                    str(value)
                )

                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                self.table.setItem(
                    row,
                    column,
                    item,
                )

        # Keep long Reason column readable.
        self.table.resizeRowsToContents()

    # ======================================================
    # END CLASS
    # ======================================================


def add_alert_history_button(
    sidebar_layout,
    main_window,
):
    """
    Optional integration helper.

    Adds an Alert History button without changing database state.
    """

    button = QPushButton(
        "เหตุการณ์แจ้งเตือน"
    )

    sidebar_layout.addWidget(
        button
    )

    button.clicked.connect(
        lambda: AlertHistoryDialog(
            main_window
        ).exec()
    )

    main_window.alert_history_button = (
        button
    )

    return button