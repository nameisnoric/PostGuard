"""Generic non-intrusive PostGuard alert toast.

This module handles presentation only.

It MUST NOT:
- decide when an alert should appear
- calculate risk
- modify alert cooldown
- resolve a risk event
- pause monitoring
- change blink detection state

Alert timing and decisions remain the responsibility
of PostGuard production services.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import (
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QCursor,
    QGuiApplication,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.ui.theme import APP_QSS


class AlertToast(QDialog):
    """
    Shared non-blocking toast used by PostGuard UI.

    Severity:
        info
        warning
        danger

    Example:

        toast = AlertToast(
            title="แจ้งเตือนท่าทาง",
            message="ตรวจพบการก้มคอต่อเนื่อง",
            severity="warning",
            icon_text="!",
            details=[
                "ก้มคอ",
                "ควรปรับท่าทาง",
            ],
        )

        toast.show()
    """

    VALID_SEVERITIES = {
        "info",
        "warning",
        "danger",
    }

    DEFAULT_ICON = {
        "info": "i",
        "warning": "!",
        "danger": "!",
    }

    DEFAULT_WIDTH = 390

    SCREEN_MARGIN = 24

    DEFAULT_AUTO_CLOSE_MS = 8_000

    def __init__(
        self,
        *,
        title: str,
        message: str,
        severity: str = "info",
        subtitle: str = "",
        icon_text: str | None = None,
        details: Iterable[str] | None = None,
        acknowledge_text: str = "รับทราบ",
        auto_close_ms: int | None = DEFAULT_AUTO_CLOSE_MS,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._severity = (
            severity
            if severity in self.VALID_SEVERITIES
            else "info"
        )

        self._auto_close_ms = (
            int(auto_close_ms)
            if (
                isinstance(
                    auto_close_ms,
                    int,
                )
                and auto_close_ms > 0
            )
            else None
        )

        # ====================================================
        # WINDOW BEHAVIOUR
        # ====================================================

        self.setWindowTitle(
            str(title or "PostGuard")
        )

        self.setWindowModality(
            Qt.WindowModality.NonModal
        )

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            False,
        )

        self.setStyleSheet(
            APP_QSS
        )

        self.setFixedWidth(
            self.DEFAULT_WIDTH
        )

        # ====================================================
        # TIMER
        # ====================================================

        self._auto_close_timer = QTimer(
            self
        )

        self._auto_close_timer.setSingleShot(
            True
        )

        self._auto_close_timer.timeout.connect(
            self.close
        )

        # ====================================================
        # ROOT
        # ====================================================

        root_layout = QVBoxLayout(
            self
        )

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        # ====================================================
        # CARD
        # ====================================================

        self.card = QFrame()

        self.card.setProperty(
            "card",
            True,
        )

        self.card.setProperty(
            "severity",
            self._severity,
        )

        card_layout = QVBoxLayout(
            self.card
        )

        card_layout.setContentsMargins(
            18,
            16,
            18,
            14,
        )

        card_layout.setSpacing(
            10
        )

        root_layout.addWidget(
            self.card
        )

        # ====================================================
        # HEADER
        # ====================================================

        header_layout = QHBoxLayout()

        header_layout.setSpacing(
            10
        )

        # ----------------------------------------------------
        # Icon
        # ----------------------------------------------------

        self.icon_label = QLabel(
            (
                str(icon_text)
                if icon_text is not None
                else self.DEFAULT_ICON[
                    self._severity
                ]
            )
        )

        self.icon_label.setTextFormat(
            Qt.TextFormat.PlainText
        )

        self.icon_label.setProperty(
            "role",
            "alertIcon",
        )

        self.icon_label.setProperty(
            "tone",
            self._severity,
        )

        self.icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.icon_label.setFixedSize(
            36,
            36,
        )

        # ----------------------------------------------------
        # Title / subtitle
        # ----------------------------------------------------

        title_layout = QVBoxLayout()

        title_layout.setSpacing(
            1
        )

        self.title_label = QLabel(
            str(title or "")
        )

        self.title_label.setTextFormat(
            Qt.TextFormat.PlainText
        )

        self.title_label.setProperty(
            "role",
            "heading",
        )

        self.subtitle_label = QLabel(
            str(subtitle or "")
        )

        self.subtitle_label.setTextFormat(
            Qt.TextFormat.PlainText
        )

        self.subtitle_label.setProperty(
            "role",
            "muted",
        )

        self.subtitle_label.setWordWrap(
            True
        )

        self.subtitle_label.setVisible(
            bool(
                str(subtitle or "").strip()
            )
        )

        title_layout.addWidget(
            self.title_label
        )

        title_layout.addWidget(
            self.subtitle_label
        )

        header_layout.addWidget(
            self.icon_label,
            alignment=Qt.AlignmentFlag.AlignTop,
        )

        header_layout.addLayout(
            title_layout,
            1,
        )

        card_layout.addLayout(
            header_layout
        )

        # ====================================================
        # MESSAGE
        # ====================================================

        self.message_label = QLabel(
            str(message or "")
        )

        self.message_label.setTextFormat(
            Qt.TextFormat.PlainText
        )

        self.message_label.setWordWrap(
            True
        )

        self.message_label.setProperty(
            "role",
            "secondary",
        )

        card_layout.addWidget(
            self.message_label
        )

        # ====================================================
        # DETAILS
        # ====================================================

        self.details_container = QFrame()

        details_layout = QVBoxLayout(
            self.details_container
        )

        details_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        details_layout.setSpacing(
            4
        )

        detail_values = [
            str(value).strip()
            for value in (
                details or []
            )
            if str(value).strip()
        ]

        for value in detail_values:
            label = QLabel(
                value
            )

            label.setTextFormat(
                Qt.TextFormat.PlainText
            )

            label.setWordWrap(
                True
            )

            label.setProperty(
                "role",
                "muted",
            )

            details_layout.addWidget(
                label
            )

        self.details_container.setVisible(
            bool(detail_values)
        )

        card_layout.addWidget(
            self.details_container
        )

        # ====================================================
        # ACTION
        # ====================================================

        action_layout = QHBoxLayout()

        action_layout.addStretch()

        self.acknowledge_button = QPushButton(
            str(
                acknowledge_text
                or "รับทราบ"
            )
        )

        self.acknowledge_button.setProperty(
            "variant",
            (
                "danger"
                if self._severity
                == "danger"
                else "primary"
            ),
        )

        self.acknowledge_button.clicked.connect(
            self.close
        )

        action_layout.addWidget(
            self.acknowledge_button
        )

        card_layout.addLayout(
            action_layout
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    @property
    def severity(self) -> str:
        return self._severity

    def set_message(
        self,
        message: str,
    ) -> None:
        self.message_label.setText(
            str(message or "")
        )

    def set_subtitle(
        self,
        subtitle: str | None,
    ) -> None:
        text = str(
            subtitle or ""
        )

        self.subtitle_label.setText(
            text
        )

        self.subtitle_label.setVisible(
            bool(text.strip())
        )

    # ========================================================
    # SHOW
    # ========================================================

    def showEvent(
        self,
        event: QShowEvent,
    ) -> None:
        super().showEvent(
            event
        )

        # Move after Qt has calculated the actual widget size.
        QTimer.singleShot(
            0,
            self._move_to_screen_corner,
        )

        if self._auto_close_ms:
            self._auto_close_timer.start(
                self._auto_close_ms
            )

    def closeEvent(
        self,
        event,
    ) -> None:
        if self._auto_close_timer.isActive():
            self._auto_close_timer.stop()

        super().closeEvent(
            event
        )

    # ========================================================
    # POSITION
    # ========================================================

    def _move_to_screen_corner(
        self,
    ) -> None:
        """
        Place toast at bottom-right of the screen currently being used.

        This is presentation behaviour only.
        """

        self.adjustSize()

        screen = (
            QGuiApplication.screenAt(
                QCursor.pos()
            )
            or self.screen()
            or QGuiApplication.primaryScreen()
        )

        if screen is None:
            return

        available = (
            screen.availableGeometry()
        )

        x = (
            available.right()
            - self.width()
            - self.SCREEN_MARGIN
            + 1
        )

        y = (
            available.bottom()
            - self.height()
            - self.SCREEN_MARGIN
            + 1
        )

        self.move(
            x,
            y,
        )