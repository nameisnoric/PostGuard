"""Posture monitoring presentation card.

UI-only component.

All posture calculations remain inside MonitoringPage and the
validated detection/risk pipeline.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)


class MonitoringPostureCard(QFrame):
    """Display posture and screen-distance information."""

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
            "ท่าทาง"
        )

        self.title_label.setProperty(
            "role",
            "sectionTitle",
        )

        self.detection_label = QLabel(
            "ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ"
        )

        self.detection_label.setProperty(
            "role",
            "muted",
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.detection_label
        )

        # ====================================================
        # PRIMARY METRICS
        # ====================================================

        self.shoulder_label = QLabel(
            "ความเอียงไหล่: --"
        )

        self.neck_label = QLabel(
            "ความเอียงคอด้านข้าง: --"
        )

        self.flexion_label = QLabel(
            "มุมก้ม/เงยคอ: --"
        )

        self.screen_distance_label = QLabel(
            "ระยะห่างหน้าจอ: --"
        )

        self.screen_distance_label.setWordWrap(
            True
        )

        for label in (
            self.shoulder_label,
            self.neck_label,
            self.flexion_label,
            self.screen_distance_label,
        ):
            layout.addWidget(
                label
            )

        # ====================================================
        # BASELINE DIFFERENCE
        # ====================================================

        self.detail_title_label = QLabel(
            "เทียบกับค่าท่าทางอ้างอิง"
        )

        self.detail_title_label.setProperty(
            "role",
            "muted",
        )

        self.shoulder_difference_label = QLabel(
            "ไหล่: --"
        )

        self.neck_difference_label = QLabel(
            "คอด้านข้าง: --"
        )

        self.flexion_difference_label = QLabel(
            "ก้ม/เงยคอ: --"
        )

        layout.addWidget(
            self.detail_title_label
        )

        for label in (
            self.shoulder_difference_label,
            self.neck_difference_label,
            self.flexion_difference_label,
        ):
            label.setProperty(
                "role",
                "muted",
            )

            layout.addWidget(
                label
            )