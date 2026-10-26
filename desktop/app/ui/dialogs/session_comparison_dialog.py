"""User-friendly comparison of two persisted PostGuard Sessions."""

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.session_comparison_service import (
    STATUS_AVAILABLE,
    STATUS_METHOD_MISMATCH,
    STATUS_SAME_SESSION,
    STATUS_SCORE_UNAVAILABLE,
    build_comparison_candidates,
    compare_sessions,
)

from app.ui.theme import APP_QSS


class SessionComparisonDialog(
    QDialog
):
    """
    Compare a previous Session with a newer Session.

    The UI intentionally uses user-facing wording instead of
    internal engineering terminology.
    """

    def __init__(
        self,
        *,
        sessions,
        summaries,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.sessions = list(
            sessions
            or []
        )

        self.summaries = list(
            summaries
            or []
        )

        self.candidates = (
            build_comparison_candidates(
                self.sessions,
                self.summaries,
            )
        )

        self.setWindowTitle(
            "PostGuard - เปรียบเทียบผล"
        )

        self.resize(
            900,
            700,
        )

        self.setMinimumSize(
            760,
            600,
        )

        self.setStyleSheet(
            APP_QSS
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            24,
            22,
            24,
            22,
        )

        layout.setSpacing(
            14
        )

        # ====================================================
        # HEADER
        # ====================================================

        layout.addWidget(
            self._label(
                "เปรียบเทียบผลการตรวจจับ",
                "title",
            )
        )

        layout.addWidget(
            self._label(
                (
                    "ดูว่าคะแนนความเสี่ยงจากท่าทาง "
                    "เปลี่ยนไปจากครั้งก่อนอย่างไร"
                ),
                "muted",
            )
        )

        # ====================================================
        # SESSION SELECTORS
        # ====================================================

        selector_card = QFrame()

        selector_card.setProperty(
            "card",
            True,
        )

        selector_layout = QVBoxLayout(
            selector_card
        )

        selector_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        selector_row = QHBoxLayout()

        previous_layout = QVBoxLayout()

        previous_layout.addWidget(
            self._label(
                "ครั้งก่อน",
                "heading",
            )
        )

        self.session_a_combo = QComboBox()

        previous_layout.addWidget(
            self.session_a_combo
        )

        latest_layout = QVBoxLayout()

        latest_layout.addWidget(
            self._label(
                "ครั้งล่าสุด",
                "heading",
            )
        )

        self.session_b_combo = QComboBox()

        latest_layout.addWidget(
            self.session_b_combo
        )

        selector_row.addLayout(
            previous_layout,
            1,
        )

        selector_row.addLayout(
            latest_layout,
            1,
        )

        selector_layout.addLayout(
            selector_row
        )

        # Kept for compatibility and also useful when user
        # explicitly wants to refresh after selecting.
        self.compare_button = QPushButton(
            "เปรียบเทียบ"
        )

        self.compare_button.setProperty(
            "variant",
            "primary",
        )

        self.compare_button.clicked.connect(
            self.refresh_comparison
        )

        selector_layout.addWidget(
            self.compare_button
        )

        layout.addWidget(
            selector_card
        )

        # ====================================================
        # MAIN RESULT
        # ====================================================

        result_card = QFrame()

        result_card.setProperty(
            "card",
            True,
        )

        result_layout = QVBoxLayout(
            result_card
        )

        result_layout.setContentsMargins(
            18,
            18,
            18,
            18,
        )

        result_layout.setSpacing(
            8
        )

        self.progress_label = self._label(
            "ผลเปรียบเทียบ: --",
            "heading",
        )

        self.score_change_label = self._label(
            "คะแนนเฉลี่ย: --",
            "heading",
        )

        # Compatibility with earlier tests/code.
        self.delta_label = (
            self.score_change_label
        )

        self.explanation_label = self._label(
            (
                "เลือกสองครั้งที่ต้องการเปรียบเทียบ"
            ),
            "muted",
        )

        # Retained as an internal compatibility label,
        # but intentionally hidden from normal users.
        self.method_label = self._label(
            "",
            "muted",
        )

        self.method_label.hide()

        # Compatibility alias for old code/tests.
        self.status_label = (
            self.explanation_label
        )

        result_layout.addWidget(
            self.progress_label
        )

        result_layout.addWidget(
            self.score_change_label
        )

        result_layout.addWidget(
            self.explanation_label
        )

        layout.addWidget(
            result_card
        )

        # ====================================================
        # DETAILS
        # ====================================================

        details_card = QFrame()

        details_card.setProperty(
            "card",
            True,
        )

        details_layout = QVBoxLayout(
            details_card
        )

        details_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        details_layout.addWidget(
            self._label(
                "รายละเอียด",
                "heading",
            )
        )

        self.table = QTableWidget(
            6,
            4,
        )

        self.table.setHorizontalHeaderLabels(
            [
                "รายการ",
                "ครั้งก่อน",
                "ครั้งล่าสุด",
                "เปลี่ยนแปลง",
            ]
        )

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        metrics = (
            "คะแนนเฉลี่ย",
            "คะแนนต่ำสุด",
            "คะแนนสูงสุด",
            "จำนวนการแจ้งเตือน",
            "อัตราแจ้งเตือน / นาที",
            "เวลาตรวจจับ",
        )

        for row_index, metric in enumerate(
            metrics
        ):
            self.table.setItem(
                row_index,
                0,
                self._item(
                    metric
                ),
            )

        details_layout.addWidget(
            self.table
        )

        self.help_label = self._label(
            (
                "คะแนนต่ำลง หมายถึงระบบตรวจพบความเสี่ยงจากท่าทางลดลง "
                "ส่วนจำนวนการแจ้งเตือนควรดูร่วมกับระยะเวลาใช้งาน"
            ),
            "muted",
        )

        details_layout.addWidget(
            self.help_label
        )

        layout.addWidget(
            details_card,
            1,
        )

        # ====================================================
        # FOOTER
        # ====================================================

        footer = QHBoxLayout()

        footer.addStretch()

        close_button = QPushButton(
            "ปิด"
        )

        close_button.clicked.connect(
            self.accept
        )

        footer.addWidget(
            close_button
        )

        layout.addLayout(
            footer
        )

        # Automatic update when selection changes.
        self.session_a_combo.currentIndexChanged.connect(
            self.refresh_comparison
        )

        self.session_b_combo.currentIndexChanged.connect(
            self.refresh_comparison
        )

        self._populate_candidates()

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
    def _score_text(
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

    @staticmethod
    def _count_text(
        value,
    ):
        if type(value) is not int:
            return "N/A"

        return str(
            value
        )

    @staticmethod
    def _rate_text(
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

    @staticmethod
    def _duration_text(
        seconds,
    ):
        if type(seconds) not in (
            int,
            float,
        ):
            return "N/A"

        seconds = int(
            seconds
        )

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

    @staticmethod
    def _number_change_text(
        value,
        *,
        suffix="",
        decimals=True,
    ):
        if type(value) not in (
            int,
            float,
        ):
            return "N/A"

        value = float(
            value
        )

        if abs(value) < 0.000001:
            return "ไม่เปลี่ยน"

        if value < 0:
            prefix = "↓ "
        else:
            prefix = "↑ "

        magnitude = abs(
            value
        )

        if decimals:
            number = (
                f"{magnitude:.2f}"
            )
        else:
            number = (
                str(
                    int(
                        round(
                            magnitude
                        )
                    )
                )
            )

        return (
            f"{prefix}{number}{suffix}"
        )

    @classmethod
    def _duration_change_text(
        cls,
        value,
    ):
        if type(value) not in (
            int,
            float,
        ):
            return "N/A"

        if int(value) == 0:
            return "ไม่เปลี่ยน"

        arrow = (
            "↑ "
            if value > 0
            else
            "↓ "
        )

        return (
            arrow
            +
            cls._duration_text(
                abs(
                    value
                )
            )
        )

    # ========================================================
    # CANDIDATES
    # ========================================================

    def _populate_candidates(
        self,
    ):
        self.session_a_combo.blockSignals(
            True
        )

        self.session_b_combo.blockSignals(
            True
        )

        self.session_a_combo.clear()
        self.session_b_combo.clear()

        for candidate in self.candidates:
            session_id = (
                candidate[
                    "session_id"
                ]
            )

            average = (
                candidate[
                    "average_risk_score"
                ]
            )

            label = (
                f"Session #{session_id} "
                f"• คะแนนเฉลี่ย {average:.2f}"
            )

            self.session_a_combo.addItem(
                label,
                session_id,
            )

            self.session_b_combo.addItem(
                label,
                session_id,
            )

        can_compare = (
            len(
                self.candidates
            )
            >=
            2
        )

        self.compare_button.setEnabled(
            can_compare
        )

        self.session_a_combo.setEnabled(
            bool(
                self.candidates
            )
        )

        self.session_b_combo.setEnabled(
            bool(
                self.candidates
            )
        )

        if can_compare:
            # API returns newest first.
            #
            # Previous = index 1
            # Latest   = index 0
            self.session_a_combo.setCurrentIndex(
                1
            )

            self.session_b_combo.setCurrentIndex(
                0
            )

        self.session_a_combo.blockSignals(
            False
        )

        self.session_b_combo.blockSignals(
            False
        )

        if not can_compare:
            self.progress_label.setText(
                "ผลเปรียบเทียบ: ยังเปรียบเทียบไม่ได้"
            )

            self.score_change_label.setText(
                "คะแนนเฉลี่ย: N/A"
            )

            self.explanation_label.setText(
                (
                    "ต้องมีอย่างน้อย 2 Session "
                    "ที่มีคะแนนความเสี่ยงจึงจะเปรียบเทียบได้"
                )
            )

            self._clear_table()

            return

        self.refresh_comparison()

    # ========================================================
    # COMPARE
    # ========================================================

    def refresh_comparison(
        self,
        *_,
    ):
        if (
            not self.candidates
            or
            len(
                self.candidates
            )
            <
            2
        ):
            return

        session_a_id = (
            self.session_a_combo.currentData()
        )

        session_b_id = (
            self.session_b_combo.currentData()
        )

        result = compare_sessions(
            self.sessions,
            self.summaries,
            session_a_id,
            session_b_id,
        )

        self._render_result(
            result
        )

    # ========================================================
    # RENDER
    # ========================================================

    def _render_result(
        self,
        result,
    ):
        self._clear_table()

        status = result.get(
            "status"
        )

        if status == STATUS_SAME_SESSION:
            self.progress_label.setText(
                "ผลเปรียบเทียบ: เลือกคนละครั้ง"
            )

            self.score_change_label.setText(
                "คะแนนเฉลี่ย: --"
            )

            self.explanation_label.setText(
                (
                    "กรุณาเลือกครั้งก่อนและครั้งล่าสุด "
                    "ให้เป็นคนละ Session"
                )
            )

            return

        session_a = result.get(
            "session_a"
        )

        session_b = result.get(
            "session_b"
        )

        if isinstance(
            session_a,
            dict,
        ):
            self._render_session_column(
                1,
                session_a,
            )

        if isinstance(
            session_b,
            dict,
        ):
            self._render_session_column(
                2,
                session_b,
            )

        if status == STATUS_METHOD_MISMATCH:
            self.progress_label.setText(
                "ผลเปรียบเทียบ: เปรียบเทียบไม่ได้"
            )

            self.score_change_label.setText(
                "คะแนนเฉลี่ย: --"
            )

            self.explanation_label.setText(
                (
                    "สอง Session นี้ใช้วิธีคำนวณคะแนนคนละรุ่น "
                    "จึงไม่ควรนำคะแนนมาเปรียบเทียบกัน"
                )
            )

            return

        if status == STATUS_SCORE_UNAVAILABLE:
            self.progress_label.setText(
                "ผลเปรียบเทียบ: ข้อมูลไม่ครบ"
            )

            self.score_change_label.setText(
                "คะแนนเฉลี่ย: N/A"
            )

            self.explanation_label.setText(
                (
                    "อย่างน้อยหนึ่ง Session "
                    "ไม่มีคะแนนความเสี่ยงที่ใช้เปรียบเทียบได้"
                )
            )

            return

        if status != STATUS_AVAILABLE:
            self.progress_label.setText(
                "ผลเปรียบเทียบ: ไม่สามารถแสดงผลได้"
            )

            self.score_change_label.setText(
                "คะแนนเฉลี่ย: N/A"
            )

            self.explanation_label.setText(
                "ไม่สามารถเปรียบเทียบ Session ที่เลือกได้"
            )

            return

        deltas = result.get(
            "deltas",
            {},
        )

        metrics_a = result[
            "session_a"
        ]

        metrics_b = result[
            "session_b"
        ]

        trend_text = result.get(
            "trend_text",
            "ไม่สามารถสรุปได้",
        )

        self.progress_label.setText(
            (
                "ผลเมื่อเทียบกับครั้งก่อน: "
                f"{trend_text}"
            )
        )

        score_a = (
            metrics_a.get(
                "average_risk_score"
            )
        )

        score_b = (
            metrics_b.get(
                "average_risk_score"
            )
        )

        average_delta = (
            deltas.get(
                "average_risk_score"
            )
        )

        if type(
            average_delta
        ) in (
            int,
            float,
        ):
            if average_delta < 0:
                change_word = "ลดลง"
            elif average_delta > 0:
                change_word = "เพิ่มขึ้น"
            else:
                change_word = "ไม่เปลี่ยน"

            if average_delta == 0:
                change_part = (
                    "ไม่เปลี่ยนแปลง"
                )
            else:
                change_part = (
                    f"{change_word} "
                    f"{abs(float(average_delta)):.2f} คะแนน"
                )

            self.score_change_label.setText(
                (
                    "คะแนนความเสี่ยงเฉลี่ย "
                    f"{self._score_text(score_a)} "
                    "→ "
                    f"{self._score_text(score_b)} "
                    f"• {change_part}"
                )
            )

        else:
            self.score_change_label.setText(
                "คะแนนเฉลี่ย: N/A"
            )

        self.explanation_label.setText(
            result.get(
                "explanation",
                "",
            )
        )

        # Keep method available internally only.
        self.method_label.setText(
            str(
                result.get(
                    "risk_score_method",
                    "",
                )
            )
        )

        # ----------------------------------------------------
        # CHANGES
        # ----------------------------------------------------

        self.table.setItem(
            0,
            3,
            self._item(
                self._number_change_text(
                    deltas.get(
                        "average_risk_score"
                    )
                )
            ),
        )

        self.table.setItem(
            1,
            3,
            self._item(
                self._number_change_text(
                    deltas.get(
                        "minimum_risk_score"
                    )
                )
            ),
        )

        self.table.setItem(
            2,
            3,
            self._item(
                self._number_change_text(
                    deltas.get(
                        "maximum_risk_score"
                    )
                )
            ),
        )

        self.table.setItem(
            3,
            3,
            self._item(
                self._number_change_text(
                    deltas.get(
                        "total_alert_count"
                    ),
                    suffix=" ครั้ง",
                    decimals=False,
                )
            ),
        )

        self.table.setItem(
            4,
            3,
            self._item(
                self._number_change_text(
                    deltas.get(
                        "alert_rate_per_minute"
                    ),
                    suffix=" ครั้ง/นาที",
                )
            ),
        )

        self.table.setItem(
            5,
            3,
            self._item(
                self._duration_change_text(
                    deltas.get(
                        "active_seconds"
                    )
                )
            ),
        )

    # ========================================================
    # SESSION COLUMN
    # ========================================================

    def _render_session_column(
        self,
        column,
        metrics,
    ):
        values = (
            self._score_text(
                metrics.get(
                    "average_risk_score"
                )
            ),

            self._score_text(
                metrics.get(
                    "minimum_risk_score"
                )
            ),

            self._score_text(
                metrics.get(
                    "maximum_risk_score"
                )
            ),

            self._count_text(
                metrics.get(
                    "total_alert_count"
                )
            ),

            self._rate_text(
                metrics.get(
                    "alert_rate_per_minute"
                )
            ),

            self._duration_text(
                metrics.get(
                    "active_seconds"
                )
            ),
        )

        for row, value in enumerate(
            values
        ):
            self.table.setItem(
                row,
                column,
                self._item(
                    value
                ),
            )

    # ========================================================
    # CLEAR
    # ========================================================

    def _clear_table(
        self,
    ):
        for row in range(
            self.table.rowCount()
        ):
            for column in (
                1,
                2,
                3,
            ):
                self.table.setItem(
                    row,
                    column,
                    self._item(
                        "N/A"
                    ),
                )