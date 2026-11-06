"""Monitoring page header.

Presentation-only component.

The header displays:
- Monitoring page title
- Session status
- Camera information
- Session ID
- Baseline ID

It does not own Monitoring state or business logic.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from app.ui.components.status_badge import StatusBadge


class MonitoringHeader(QFrame):
    """Compact header for the real-time Monitoring page."""

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setProperty(
            "variant",
            "monitoringHeader",
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        root_layout = QHBoxLayout(self)

        root_layout.setContentsMargins(
            16,
            12,
            16,
            12,
        )

        root_layout.setSpacing(
            16,
        )

        # ====================================================
        # LEFT
        # ====================================================

        title_layout = QVBoxLayout()

        title_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        title_layout.setSpacing(
            3,
        )

        self.title_label = QLabel(
            "การตรวจจับแบบเรียลไทม์"
        )

        self.title_label.setProperty(
            "role",
            "title",
        )

        self.subtitle_label = QLabel(
            "ติดตามท่าทาง ระยะห่าง และการกระพริบตา"
        )

        self.subtitle_label.setProperty(
            "role",
            "muted",
        )

        title_layout.addWidget(
            self.title_label
        )

        title_layout.addWidget(
            self.subtitle_label
        )

        root_layout.addLayout(
            title_layout,
            1,
        )

        # ====================================================
        # RIGHT
        # ====================================================

        details_layout = QVBoxLayout()

        details_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        details_layout.setSpacing(
            4,
        )

        top_row = QHBoxLayout()

        top_row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        top_row.setSpacing(
            8,
        )

        self.status_badge = StatusBadge(
            "กำลังเริ่มตรวจจับ...",
            tone="neutral",
        )

        top_row.addStretch()

        top_row.addWidget(
            self.status_badge
        )

        details_layout.addLayout(
            top_row
        )

        meta_row = QHBoxLayout()

        meta_row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        meta_row.setSpacing(
            12,
        )

        self.camera_label = QLabel(
            "กล้อง: -"
        )

        self.camera_label.setProperty(
            "role",
            "muted",
        )

        self.session_label = QLabel(
            "เซสชัน: -"
        )

        self.session_label.setProperty(
            "role",
            "muted",
        )

        self.baseline_label = QLabel(
            "Baseline: -"
        )

        self.baseline_label.setProperty(
            "role",
            "muted",
        )

        meta_row.addWidget(
            self.camera_label
        )

        meta_row.addWidget(
            self.session_label
        )

        meta_row.addWidget(
            self.baseline_label
        )

        details_layout.addLayout(
            meta_row
        )

        root_layout.addLayout(
            details_layout,
        )

    # ========================================================
    # PRESENTATION
    # ========================================================

    def set_status(
        self,
        text: str,
        tone: str = "neutral",
    ) -> None:
        """Update visible Monitoring status."""

        self.status_badge.set_status(
            str(text),
            tone,
        )