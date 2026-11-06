"""Monitoring camera preview card.

Presentation-only component.

The card owns only the visible preview container.
Camera capture and image processing remain inside MonitoringPage.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class MonitoringVideoCard(QFrame):
    """Camera preview card used by MonitoringPage."""

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
            QSizePolicy.Policy.Expanding,
        )

        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        root_layout.setSpacing(
            10,
        )

        # ====================================================
        # CARD HEADER
        # ====================================================

        header_layout = QHBoxLayout()

        header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.title_label = QLabel(
            "กล้อง"
        )

        self.title_label.setProperty(
            "role",
            "sectionTitle",
        )

        self.camera_state_label = QLabel(
            "พร้อมตรวจจับ"
        )

        self.camera_state_label.setProperty(
            "role",
            "muted",
        )

        header_layout.addWidget(
            self.title_label
        )

        header_layout.addStretch()

        header_layout.addWidget(
            self.camera_state_label
        )

        root_layout.addLayout(
            header_layout
        )

        # ====================================================
        # PREVIEW
        # ====================================================

        preview_container = QWidget()

        preview_layout = QVBoxLayout(
            preview_container
        )

        preview_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        preview_layout.setSpacing(
            0,
        )

        self.preview_label = QLabel(
            "ภาพจากกล้องจะแสดงที่นี่"
        )

        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_label.setMinimumSize(
            480,
            270,
        )

        self.preview_label.setMaximumSize(
            960,
            540,
        )

        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.preview_label.setProperty(
            "preview",
            True,
        )

        preview_layout.addWidget(
            self.preview_label,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )

        root_layout.addWidget(
            preview_container,
            1,
        )

    # ========================================================
    # PRESENTATION
    # ========================================================

    def set_camera_state(
        self,
        text: str,
    ) -> None:
        """Update camera status text only."""

        self.camera_state_label.setText(
            str(text)
        )