"""Saved monitoring history, Risk Reports and Session Comparison."""

import requests

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.alert_history_service import (
    duration_text,
    local_datetime,
)
from app.services.api_client import (
    APIClient,
)
from app.services.session_comparison_service import (
    build_comparison_candidates,
)
from app.services.session_summary_service import (
    load_session_summary,
)
from app.ui.dialogs.alert_history_dialog import (
    AlertHistoryDialog,
)
from app.ui.dialogs.saved_session_report_dialog import (
    SavedSessionReportDialog,
)
from app.ui.dialogs.session_comparison_dialog import (
    SessionComparisonDialog,
)


class HistoryPage(
    QWidget
):
    COLUMNS = (
        "เซสชัน",
        "เริ่มเมื่อ",
        "เวลาตรวจจับ",
        "สถานะ",
        "AVG Risk",
        "MAX Risk",
        "Report",
    )

    def __init__(
        self,
    ):
        super().__init__()

        self.setProperty(
            "page",
            True,
        )

        self.sessions = []
        self.visible_sessions = []

        self.summaries = []
        self.summary_by_session_id = {}

        self.report_session_ids = set()
        self.report_index_available = False

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
        # HEADER
        # ====================================================

        header = QHBoxLayout()

        copy = QVBoxLayout()

        self.title_label = self._label(
            "Monitoring History",
            "title",
        )

        self.description_label = self._label(
            (
                "ตรวจสอบ Session, Risk Score, "
                "Alert Events, Saved Report "
                "และเปรียบเทียบความเปลี่ยนแปลงระหว่าง Session"
            ),
            "muted",
        )

        copy.addWidget(
            self.title_label
        )

        copy.addWidget(
            self.description_label
        )

        header.addLayout(
            copy,
            1,
        )

        self.compare_button = QPushButton(
            "Compare Sessions"
        )

        self.compare_button.setEnabled(
            False
        )

        self.compare_button.clicked.connect(
            self.open_session_comparison
        )

        self.alert_history_button = QPushButton(
            "All Alert Events"
        )

        self.alert_history_button.clicked.connect(
            self.open_alert_history
        )

        self.refresh_button = QPushButton(
            "Refresh"
        )

        self.refresh_button.setProperty(
            "variant",
            "primary",
        )

        self.refresh_button.clicked.connect(
            self.load_sessions
        )

        header.addWidget(
            self.compare_button
        )

        header.addWidget(
            self.alert_history_button
        )

        header.addWidget(
            self.refresh_button
        )

        layout.addLayout(
            header
        )

        # ====================================================
        # METRICS
        # ====================================================

        metrics = QGridLayout()

        metrics.setHorizontalSpacing(
            12
        )

        self.total_value = self._metric(
            metrics,
            0,
            "เซสชันทั้งหมด",
        )

        self.completed_value = self._metric(
            metrics,
            1,
            "เสร็จสิ้น",
        )

        self.interrupted_value = self._metric(
            metrics,
            2,
            "ถูกขัดจังหวะ",
        )

        self.reports_value = self._metric(
            metrics,
            3,
            "รายงานที่บันทึก",
        )

        layout.addLayout(
            metrics
        )

        # ====================================================
        # HISTORY
        # ====================================================

        history_card, history_layout = (
            self._card()
        )

        controls = QHBoxLayout()

        self.search_input = QLineEdit()

        self.search_input.setPlaceholderText(
            (
                "ค้นหาด้วย Session, "
                "Camera หรือ Baseline ID"
            )
        )

        self.search_input.setClearButtonEnabled(
            True
        )

        self.search_input.textChanged.connect(
            self._apply_filters
        )

        self.status_filter = QComboBox()

        self.status_filter.addItem(
            "ทุกสถานะ",
            "",
        )

        for status in (
            "COMPLETED",
            "RUNNING",
            "PAUSED",
            "INTERRUPTED",
            "ENDED",
        ):
            self.status_filter.addItem(
                status.title(),
                status,
            )

        self.status_filter.currentIndexChanged.connect(
            self._apply_filters
        )

        controls.addWidget(
            self.search_input,
            1,
        )

        controls.addWidget(
            self.status_filter
        )

        history_layout.addLayout(
            controls
        )

        self.status_label = self._label(
            "กำลังโหลดเซสชันที่บันทึกไว้...",
            "muted",
        )

        history_layout.addWidget(
            self.status_label
        )

        self.empty_label = self._label(
            "ยังไม่มีเซสชันการตรวจจับ",
            "muted",
        )

        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_label.setMinimumHeight(
            120
        )

        history_layout.addWidget(
            self.empty_label
        )

        self.table = QTableWidget(
            0,
            len(
                self.COLUMNS
            ),
        )

        self.table.setHorizontalHeaderLabels(
            self.COLUMNS
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

        self.table.setAlternatingRowColors(
            True
        )

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.table.itemSelectionChanged.connect(
            self.show_selected_session
        )

        self.table.cellDoubleClicked.connect(
            lambda *_: (
                self.open_saved_report()
            )
        )

        history_layout.addWidget(
            self.table
        )

        layout.addWidget(
            history_card,
            1,
        )

        # ====================================================
        # DETAILS
        # ====================================================

        details_card, details_layout = (
            self._card()
        )

        details_layout.addWidget(
            self._label(
                "Session Details",
                "heading",
            )
        )

        self.details_hint = self._label(
            (
                "เลือกเซสชันเพื่อดู"
                "รายละเอียดที่บันทึกไว้"
            ),
            "muted",
        )

        details_layout.addWidget(
            self.details_hint
        )

        details_grid = QGridLayout()

        details_grid.setHorizontalSpacing(
            28
        )

        details_grid.setVerticalSpacing(
            8
        )

        self.detail_values = {}

        detail_fields = (
            ("session", "เซสชัน"),
            ("status", "สถานะ"),
            ("started", "เริ่มเมื่อ"),
            ("ended", "Ended"),
            ("active", "เวลาตรวจจับ"),
            ("total", "Total time"),
            ("paused", "Paused time"),
            ("pauses", "Pause count"),
            ("camera", "Camera ID"),
            ("baseline", "Baseline ID"),
            ("avg_risk", "AVG Risk"),
            ("min_risk", "MIN Risk"),
            ("max_risk", "MAX Risk"),
            ("alerts", "Alerts"),
            ("report", "Saved report"),
        )

        for index, (
            key,
            title,
        ) in enumerate(
            detail_fields
        ):
            row, column = divmod(
                index,
                3,
            )

            block = QVBoxLayout()

            block.addWidget(
                self._label(
                    title,
                    "muted",
                )
            )

            value = self._label(
                "--",
                "heading",
            )

            self.detail_values[
                key
            ] = value

            block.addWidget(
                value
            )

            details_grid.addLayout(
                block,
                row,
                column,
            )

            details_grid.setColumnStretch(
                column,
                1,
            )

        details_layout.addLayout(
            details_grid
        )

        actions = QHBoxLayout()

        self.selected_alerts_button = QPushButton(
            "View Session Alerts"
        )

        self.selected_alerts_button.setEnabled(
            False
        )

        self.selected_alerts_button.clicked.connect(
            self.open_selected_alert_history
        )

        self.report_button = QPushButton(
            "View Saved Report"
        )

        self.report_button.setProperty(
            "variant",
            "primary",
        )

        self.report_button.setEnabled(
            False
        )

        self.report_button.clicked.connect(
            self.open_saved_report
        )

        actions.addStretch()

        actions.addWidget(
            self.selected_alerts_button
        )

        actions.addWidget(
            self.report_button
        )

        details_layout.addLayout(
            actions
        )

        layout.addWidget(
            details_card
        )

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
    def _card():
        card = QFrame()

        card.setProperty(
            "card",
            True,
        )

        card_layout = QVBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        card_layout.setSpacing(
            10
        )

        return (
            card,
            card_layout,
        )

    def _metric(
        self,
        grid,
        column,
        title,
    ):
        card, card_layout = (
            self._card()
        )

        card_layout.addWidget(
            self._label(
                title,
                "muted",
            )
        )

        value = self._label(
            "--",
            "metric",
        )

        card_layout.addWidget(
            value
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

    @staticmethod
    def _item(
        value,
    ):
        item = QTableWidgetItem(
            str(
                value
            )
        )

        item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        return item

    @staticmethod
    def _risk_score_text(
        value,
    ):
        if type(value) not in (
            int,
            float,
        ):
            return "N/A"

        return (
            f"{float(value):.2f}"
        )

    # ========================================================
    # SESSION TIME
    # ========================================================

    @staticmethod
    def _active_seconds(
        session,
    ):
        total = session.get(
            "total_duration"
        )

        paused = session.get(
            "paused_duration"
        )

        if (
            type(total)
            not in (
                int,
                float,
            )
            or
            total < 0
        ):
            return None

        if (
            type(paused)
            not in (
                int,
                float,
            )
            or
            paused < 0
            or
            paused > total
        ):
            return None

        return int(
            total - paused
        )

    # ========================================================
    # REPORT
    # ========================================================

    def _report_text(
        self,
        session_id,
    ):
        if not self.report_index_available:
            return "Unavailable"

        return (
            "Saved"
            if session_id
            in self.report_session_ids
            else
            "Not available"
        )

    def _summary_for_session(
        self,
        session_id,
    ):
        return (
            self.summary_by_session_id.get(
                session_id
            )
        )

    # ========================================================
    # LOAD
    # ========================================================

    def load_sessions(
        self,
    ):
        self.refresh_button.setEnabled(
            False
        )

        self.compare_button.setEnabled(
            False
        )

        self.status_label.setText(
            (
                "กำลังโหลด Sessions "
                "และ Saved Risk Reports..."
            )
        )

        self.sessions = []
        self.visible_sessions = []

        self.summaries = []
        self.summary_by_session_id = {}

        self.report_session_ids = set()
        self.report_index_available = False

        self._clear_selection()

        try:
            response = (
                APIClient.get_sessions()
            )

            if not response.ok:
                raise RuntimeError(
                    (
                        "Server returned HTTP "
                        f"{response.status_code}"
                    )
                )

            sessions = (
                response.json()
            )

            if (
                not isinstance(
                    sessions,
                    list,
                )
                or
                any(
                    not isinstance(
                        session,
                        dict,
                    )
                    for session
                    in sessions
                )
            ):
                raise ValueError(
                    "Invalid sessions response"
                )

            self.sessions = sessions

            # ------------------------------------------------
            # Summaries
            # ------------------------------------------------

            try:
                report_response = (
                    APIClient
                    .get_session_summaries()
                )

                if report_response.ok:
                    reports = (
                        report_response.json()
                    )

                    if isinstance(
                        reports,
                        list,
                    ):
                        valid_reports = [
                            report
                            for report
                            in reports
                            if (
                                isinstance(
                                    report,
                                    dict,
                                )
                                and
                                type(
                                    report.get(
                                        "session_id"
                                    )
                                )
                                is int
                            )
                        ]

                        self.summaries = (
                            valid_reports
                        )

                        self.summary_by_session_id = {
                            report[
                                "session_id"
                            ]: report
                            for report
                            in valid_reports
                        }

                        self.report_session_ids = set(
                            self.summary_by_session_id
                        )

                        self.report_index_available = (
                            True
                        )

            except (
                requests.RequestException,
                ValueError,
                TypeError,
            ):
                pass

            self._update_metrics()
            self._update_compare_button()
            self._apply_filters()

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            self.table.setRowCount(
                0
            )

            self.table.hide()

            self.compare_button.setEnabled(
                False
            )

            self.empty_label.setText(
                (
                    "โหลดประวัติเซสชันไม่สำเร็จ "
                    "โปรดตรวจสอบการเชื่อมต่อ"
                )
            )

            self.empty_label.show()

            self.status_label.setText(
                (
                    "History unavailable: "
                    f"{error}"
                )
            )

            for value in (
                self.total_value,
                self.completed_value,
                self.interrupted_value,
                self.reports_value,
            ):
                value.setText(
                    "--"
                )

        finally:
            self.refresh_button.setEnabled(
                True
            )

    # ========================================================
    # METRICS
    # ========================================================

    def _update_metrics(
        self,
    ):
        self.total_value.setText(
            str(
                len(
                    self.sessions
                )
            )
        )

        self.completed_value.setText(
            str(
                sum(
                    session.get(
                        "status"
                    )
                    ==
                    "COMPLETED"
                    for session
                    in self.sessions
                )
            )
        )

        self.interrupted_value.setText(
            str(
                sum(
                    session.get(
                        "status"
                    )
                    ==
                    "INTERRUPTED"
                    for session
                    in self.sessions
                )
            )
        )

        self.reports_value.setText(
            (
                str(
                    len(
                        self.report_session_ids
                    )
                )
                if self.report_index_available
                else
                "N/A"
            )
        )

    def _update_compare_button(
        self,
    ):
        candidates = (
            build_comparison_candidates(
                self.sessions,
                self.summaries,
            )
        )

        self.compare_button.setEnabled(
            len(candidates)
            >=
            2
        )

    # ========================================================
    # FILTERS
    # ========================================================

    def _apply_filters(
        self,
        *_,
    ):
        query = (
            self.search_input
            .text()
            .strip()
            .lower()
        )

        wanted_status = (
            self.status_filter
            .currentData()
        )

        self.visible_sessions = []

        for session in self.sessions:
            if (
                wanted_status
                and
                session.get(
                    "status"
                )
                !=
                wanted_status
            ):
                continue

            haystack = " ".join(
                str(
                    session.get(
                        key,
                        "",
                    )
                )
                for key
                in (
                    "session_id",
                    "camera_id",
                    "baseline_id",
                )
            ).lower()

            if (
                query
                and
                query not in haystack
            ):
                continue

            self.visible_sessions.append(
                session
            )

        self.table.setRowCount(
            len(
                self.visible_sessions
            )
        )

        for row, session in enumerate(
            self.visible_sessions
        ):
            session_id = (
                session.get(
                    "session_id"
                )
            )

            summary = (
                self._summary_for_session(
                    session_id
                )
            )

            values = (
                (
                    f"#{session_id}"
                    if session_id
                    is not None
                    else
                    "--"
                ),

                local_datetime(
                    session.get(
                        "started_at"
                    )
                ),

                duration_text(
                    self._active_seconds(
                        session
                    )
                ),

                session.get(
                    "status",
                    "--",
                ),

                self._risk_score_text(
                    summary.get(
                        "average_risk_score"
                    )
                    if summary
                    else None
                ),

                self._risk_score_text(
                    summary.get(
                        "maximum_risk_score"
                    )
                    if summary
                    else None
                ),

                self._report_text(
                    session_id
                ),
            )

            for column, value in enumerate(
                values
            ):
                self.table.setItem(
                    row,
                    column,
                    self._item(
                        value
                    ),
                )

        has_rows = bool(
            self.visible_sessions
        )

        self.table.setVisible(
            has_rows
        )

        self.empty_label.setVisible(
            not has_rows
        )

        if (
            self.sessions
            and
            not has_rows
        ):
            self.empty_label.setText(
                (
                    "ไม่มีเซสชันตรงกับ"
                    "ตัวกรองปัจจุบัน"
                )
            )

        else:
            self.empty_label.setText(
                "ยังไม่มีเซสชันการตรวจจับ"
            )

        self.status_label.setText(
            (
                (
                    f"Showing "
                    f"{len(self.visible_sessions)} "
                    f"of {len(self.sessions)} "
                    "session(s)."
                )
                if self.sessions
                else
                "No saved sessions found."
            )
        )

        self._clear_selection()

    # ========================================================
    # SELECTION
    # ========================================================

    def _clear_selection(
        self,
    ):
        self.table.clearSelection()

        self.report_button.setEnabled(
            False
        )

        self.selected_alerts_button.setEnabled(
            False
        )

        if hasattr(
            self,
            "details_hint",
        ):
            self.details_hint.setText(
                (
                    "เลือกเซสชันเพื่อดู"
                    "รายละเอียดที่บันทึกไว้"
                )
            )

        for value in getattr(
            self,
            "detail_values",
            {},
        ).values():
            value.setText(
                "--"
            )

    def _selected_session(
        self,
    ):
        row = (
            self.table.currentRow()
        )

        if (
            0
            <=
            row
            <
            len(
                self.visible_sessions
            )
        ):
            return (
                self.visible_sessions[
                    row
                ]
            )

        return None

    def show_selected_session(
        self,
    ):
        session = (
            self._selected_session()
        )

        self.report_button.setEnabled(
            False
        )

        self.selected_alerts_button.setEnabled(
            session is not None
        )

        if session is None:
            return

        session_id = session.get(
            "session_id"
        )

        summary = (
            self._summary_for_session(
                session_id
            )
        )

        report_saved = (
            session_id
            in
            self.report_session_ids
        )

        can_try_report = (
            session.get(
                "status"
            )
            ==
            "COMPLETED"
            and
            (
                report_saved
                or
                not
                self.report_index_available
            )
        )

        self.report_button.setEnabled(
            can_try_report
        )

        self.details_hint.setText(
            (
                "ข้อมูลเซสชันและ Risk Score "
                "ที่บันทึกไว้ โดยเวลาตรวจจับ "
                "ไม่รวมช่วงหยุดชั่วคราว"
            )
        )

        values = {
            "session": (
                f"#{session_id}"
            ),

            "status": session.get(
                "status",
                "--",
            ),

            "started": local_datetime(
                session.get(
                    "started_at"
                )
            ),

            "ended": local_datetime(
                session.get(
                    "ended_at"
                )
            ),

            "active": duration_text(
                self._active_seconds(
                    session
                )
            ),

            "total": duration_text(
                session.get(
                    "total_duration"
                )
            ),

            "paused": duration_text(
                session.get(
                    "paused_duration"
                )
            ),

            "pauses": session.get(
                "pause_count",
                0,
            ),

            "camera": session.get(
                "camera_id",
                "--",
            ),

            "baseline": session.get(
                "baseline_id",
                "--",
            ),

            "avg_risk": (
                self._risk_score_text(
                    summary.get(
                        "average_risk_score"
                    )
                    if summary
                    else None
                )
            ),

            "min_risk": (
                self._risk_score_text(
                    summary.get(
                        "minimum_risk_score"
                    )
                    if summary
                    else None
                )
            ),

            "max_risk": (
                self._risk_score_text(
                    summary.get(
                        "maximum_risk_score"
                    )
                    if summary
                    else None
                )
            ),

            "alerts": (
                (
                    summary.get(
                        "total_alert_count"
                    )
                    if (
                        summary
                        and
                        summary.get(
                            "total_alert_count"
                        )
                        is not None
                    )
                    else
                    "N/A"
                )
            ),

            "report": (
                self._report_text(
                    session_id
                )
            ),
        }

        for key, value in values.items():
            self.detail_values[
                key
            ].setText(
                str(
                    value
                )
            )

        if (
            session.get(
                "status"
            )
            ==
            "INTERRUPTED"
        ):
            self.details_hint.setText(
                (
                    "เซสชันนี้สิ้นสุดอย่างไม่สมบูรณ์ "
                    "จึงไม่มี Final Risk Report "
                    "ที่เชื่อถือได้"
                )
            )

    # ========================================================
    # COMPARISON
    # ========================================================

    def open_session_comparison(
        self,
    ):
        candidates = (
            build_comparison_candidates(
                self.sessions,
                self.summaries,
            )
        )

        if len(
            candidates
        ) < 2:
            QMessageBox.information(
                self,
                "Session Comparison",
                (
                    "ต้องมีอย่างน้อย 2 Session "
                    "ที่มี Persisted Risk Score "
                    "จึงจะเปรียบเทียบได้"
                ),
            )

            return

        dialog = (
            SessionComparisonDialog(
                sessions=self.sessions,
                summaries=self.summaries,
                parent=self,
            )
        )

        dialog.exec()

    # ========================================================
    # ALERT HISTORY
    # ========================================================

    def open_alert_history(
        self,
    ):
        session = (
            self._selected_session()
        )

        AlertHistoryDialog(
            self,
            session_id=(
                session.get(
                    "session_id"
                )
                if session
                else None
            ),
        ).exec()

    def open_selected_alert_history(
        self,
    ):
        session = (
            self._selected_session()
        )

        if session:
            AlertHistoryDialog(
                self,
                session_id=(
                    session.get(
                        "session_id"
                    )
                ),
            ).exec()

    # ========================================================
    # SAVED REPORT
    # ========================================================

    def open_saved_report(
        self,
    ):
        session = (
            self._selected_session()
        )

        if (
            not session
            or
            session.get(
                "status"
            )
            !=
            "COMPLETED"
        ):
            return

        session_id = (
            session.get(
                "session_id"
            )
        )

        self.report_button.setEnabled(
            False
        )

        try:
            saved = (
                load_session_summary(
                    session_id
                )
            )

            if saved is None:
                QMessageBox.information(
                    self,
                    "รายงานที่บันทึก",
                    (
                        "ไม่มีรายงานที่บันทึก"
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
                "เกิดข้อผิดพลาดของรายงานที่บันทึก",
                str(
                    error
                ),
            )

        finally:
            self.show_selected_session()