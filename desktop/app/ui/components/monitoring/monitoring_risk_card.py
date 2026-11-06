"""PostGuard risk presentation card.

UI-only component.

Risk evaluation, temporal continuity, risk events and alert
policy decisions remain inside the validated pipeline.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)


class MonitoringRiskCard(QFrame):
    """Display validated PostGuard risk results."""

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setProperty(
            "card",
            True,
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        layout.setSpacing(
            7,
        )

        # ====================================================
        # HEADER
        # ====================================================

        self.title_label = QLabel(
            "ความเสี่ยง"
        )

        self.title_label.setProperty(
            "role",
            "heading",
        )

        layout.addWidget(
            self.title_label
        )

        # ====================================================
        # PRIMARY RESULT
        # ====================================================

        self.risk_label = QLabel(
            "ระดับความเสี่ยง: -"
        )

        self.risk_label.setProperty(
            "role",
            "metricValue",
        )

        self.assessment_label = QLabel(
            "การประเมินท่าทาง: กำลังรอข้อมูล"
        )

        layout.addWidget(
            self.risk_label
        )

        layout.addWidget(
            self.assessment_label
        )

        # ====================================================
        # DETAILS
        # ====================================================

        self.factor_label = QLabel(
            "ปัจจัยด้านท่าทาง: -"
        )

        self.factor_label.setWordWrap(
            True
        )

        self.duration_label = QLabel(
            "ปัจจัยต่อเนื่องนานที่สุด: -"
        )

        self.event_label = QLabel(
            "เหตุการณ์ความเสี่ยง: -"
        )

        self.alert_label = QLabel(
            "การแจ้งเตือน: กำลังรอข้อมูล"
        )

        self.alert_label.setWordWrap(
            True
        )

        for label in (
            self.factor_label,
            self.duration_label,
            self.event_label,
            self.alert_label,
        ):
            layout.addWidget(
                label
            )

        # ====================================================
        # NOTE
        # ====================================================

        self.risk_note_label = QLabel(
            "เป็นการประเมินตามเกณฑ์ของ PostGuard "
            "ไม่ใช่การวินิจฉัยทางการแพทย์"
        )

        self.risk_note_label.setWordWrap(
            True
        )

        self.risk_note_label.setProperty(
            "role",
            "muted",
        )

        layout.addWidget(
            self.risk_note_label
        )