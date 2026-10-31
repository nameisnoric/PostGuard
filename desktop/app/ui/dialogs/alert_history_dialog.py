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

import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
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
            "PostGuard - Alert History"
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
            "Alert Notifications"
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
            "ประวัติการแจ้งเตือนที่เกิดจาก PostGuard Alert Policy "
            "โดยหนึ่ง Risk Event สามารถมีการแจ้งเตือนได้หลายครั้ง "
            "เช่น FIRST, REPEAT และ ESCALATION"
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
            "Refresh"
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
        # STATISTICS
        # ==================================================

        self.stats_label = QLabel(
            "เลือกเซสชันเพื่อโหลดประวัติการแจ้งเตือน"
        )
        self.stats_label.setWordWrap(
            True
        )

        root_layout.addWidget(
            self.stats_label
        )

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
                "Notification ID",
                "Risk Event ID",
                "ประเภท",
                "ระดับความเสี่ยง",
                "Decision",
                "Reason",
                "เวลาที่แจ้งเตือน",
                "Created At",
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

        self.table.setAlternatingRowColors(
            True
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
                    "Invalid sessions response"
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
                    "Invalid alert notifications response"
                )

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

            self.empty_label.setText(
                "ไม่สามารถโหลดการแจ้งเตือนได้ "
                "กด Refresh เพื่อลองอีกครั้ง"
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

        total_count = len(
            notifications
        )

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
                "เซสชันนี้ไม่มีการแจ้งเตือนจาก Alert Policy"
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