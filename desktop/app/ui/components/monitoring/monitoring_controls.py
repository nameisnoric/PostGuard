"""Monitoring session controls for PostGuard.

UI-only component.

This component presents the single visible set of Monitoring
controls under the camera preview.

It does not own:
- session state
- camera state
- detection state
- pause/resume logic
- stop logic
- mini-window logic
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
)


class MonitoringControls(QFrame):
    """Single visible control bar for Monitoring."""

    pause_requested = Signal()
    minimize_requested = Signal()
    stop_requested = Signal()

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setProperty(
            "variant",
            "monitoringControls",
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(
            10,
        )

        # ====================================================
        # PAUSE / RESUME
        # ====================================================

        self.pause_button = QPushButton(
            "หยุดชั่วคราว"
        )
        self.pause_button.setProperty(
            "variant",
            "primary",
        )

        self.pause_button.setEnabled(
            False
        )

        self.pause_button.clicked.connect(
            self.pause_requested.emit
        )

        # ====================================================
        # MINI WINDOW
        # ====================================================

        self.minimize_button = QPushButton(
            "ย่อหน้าต่าง"
        )

        self.minimize_button.setEnabled(
            False
        )

        self.minimize_button.clicked.connect(
            self.minimize_requested.emit
        )

        # ====================================================
        # STOP
        # ====================================================

        self.stop_button = QPushButton(
            "จบการตรวจจับ"
        )

        self.stop_button.setProperty(
            "variant",
            "danger",
        )

        self.stop_button.setEnabled(
            False
        )

        self.stop_button.clicked.connect(
            self.stop_requested.emit
        )

        # ====================================================
        # LAYOUT
        # ====================================================

        layout.addWidget(
            self.pause_button,
            1,
        )

        layout.addWidget(
            self.minimize_button,
            1,
        )

        layout.addWidget(
            self.stop_button,
            1,
        )

    # ========================================================
    # PRESENTATION
    # ========================================================

    def set_paused(
        self,
        paused: bool,
    ) -> None:
        """Update Pause/Resume text only."""

        self.pause_button.setText(
            "ทำต่อ"
            if paused
            else "หยุดชั่วคราว"
        )

    def set_controls_enabled(
        self,
        *,
        pause: bool,
        minimize: bool,
        stop: bool,
    ) -> None:
        """Update button availability only."""

        self.pause_button.setEnabled(
            bool(pause)
        )

        self.minimize_button.setEnabled(
            bool(minimize)
        )

        self.stop_button.setEnabled(
            bool(stop)
        )