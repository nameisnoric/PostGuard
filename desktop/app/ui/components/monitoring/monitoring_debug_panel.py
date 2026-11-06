"""Monitoring system detail panel.

Presentation-only component.

This panel displays supporting Monitoring information that is
useful for diagnostics but should not compete with the primary
Posture, Eye and Risk results.

Business logic remains inside MonitoringPage.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class MonitoringDebugPanel(QFrame):
    """Compact expandable system-detail panel."""

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

        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )

        root_layout.setSpacing(
            8,
        )

        # ====================================================
        # TOGGLE
        # ====================================================

        self.toggle_button = QPushButton(
            "รายละเอียดระบบ"
        )

        self.toggle_button.setCheckable(
            True
        )

        self.toggle_button.setChecked(
            False
        )

        self.toggle_button.setProperty(
            "variant",
            "secondary",
        )

        root_layout.addWidget(
            self.toggle_button
        )

        # ====================================================
        # DETAIL CONTAINER
        # ====================================================

        self.detail_container = QWidget(
            self
        )

        detail_layout = QVBoxLayout(
            self.detail_container
        )

        detail_layout.setContentsMargins(
            2,
            4,
            2,
            2,
        )

        detail_layout.setSpacing(
            5,
        )

        self.status_label = QLabel(
            "สถานะ: กำลังเริ่มตรวจจับ..."
        )

        self.status_label.setWordWrap(
            True
        )

        self.baseline_shoulder_label = QLabel(
            "ค่าพื้นฐานความเอียงไหล่: -"
        )

        self.baseline_neck_label = QLabel(
            "ค่าพื้นฐานความเอียงคอด้านข้าง: -"
        )

        self.baseline_flexion_label = QLabel(
            "ค่าพื้นฐานมุมก้ม/เงยคอ: -"
        )

        for label in (
            self.status_label,
            self.baseline_shoulder_label,
            self.baseline_neck_label,
            self.baseline_flexion_label,
        ):
            label.setProperty(
                "role",
                "muted",
            )

            label.setWordWrap(
                True
            )

            detail_layout.addWidget(
                label
            )

        root_layout.addWidget(
            self.detail_container
        )

        self.detail_container.hide()

        self.toggle_button.toggled.connect(
            self._set_expanded
        )

    def _set_expanded(
        self,
        expanded: bool,
    ) -> None:
        """Show or hide secondary technical information."""

        self.detail_container.setVisible(
            bool(expanded)
        )

        self.toggle_button.setText(
            "ซ่อนรายละเอียดระบบ"
            if expanded
            else "รายละเอียดระบบ"
        )