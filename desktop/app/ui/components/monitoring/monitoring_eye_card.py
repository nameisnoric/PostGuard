"""Eye and blink monitoring presentation card.

UI-only component.

Blink detection, statistics and alert policies remain outside
this component.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)


class MonitoringEyeCard(QFrame):
    """Display eye state and blink information."""

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
            "สายตาและการกระพริบตา"
        )

        self.title_label.setProperty(
            "role",
            "sectionTitle",
        )

        layout.addWidget(
            self.title_label
        )

        # ====================================================
        # SUMMARY
        # ====================================================

        self.eye_state_label = QLabel(
            "สถานะตา: --"
        )

        self.blink_count_label = QLabel(
            "กระพริบตา: 0"
        )

        layout.addWidget(
            self.eye_state_label
        )

        layout.addWidget(
            self.blink_count_label
        )

        # ====================================================
        # DETAILS
        # ====================================================

        self.detail_title_label = QLabel(
            "รายละเอียด"
        )

        self.detail_title_label.setProperty(
            "role",
            "muted",
        )

        self.right_eye_state_label = QLabel(
            "ตาขวา: --"
        )

        self.left_eye_state_label = QLabel(
            "ตาซ้าย: --"
        )

        self.eye_pattern_label = QLabel(
            "รูปแบบตา: --"
        )

        self.eye_openness_label = QLabel(
            "ค่าการเปิดตา: --"
        )

        layout.addWidget(
            self.detail_title_label
        )

        for label in (
            self.right_eye_state_label,
            self.left_eye_state_label,
            self.eye_pattern_label,
            self.eye_openness_label,
        ):
            label.setProperty(
                "role",
                "muted",
            )

            layout.addWidget(
                label
            )