"""Reusable metric card for PostGuard UI.

Examples:
- Blink rate
- Session duration
- Risk score
- Alert count
- Monitoring statistics

UI-only component.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from app.ui.theme import polish


class MetricCard(QFrame):
    """
    Reusable visual card for a single metric.

    Example:

        card = MetricCard(
            "อัตราการกระพริบตา",
            "--",
            "ครั้ง/นาที",
        )

        card.set_value("12.4")
        card.set_tone("success")
    """

    VALID_TONES = {
        "neutral",
        "info",
        "success",
        "warning",
        "danger",
    }

    def __init__(
        self,
        title: str,
        value: str = "--",
        subtitle: str = "",
        *,
        tone: str = "neutral",
        large: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._tone = "neutral"

        # ====================================================
        # FRAME
        # ====================================================

        self.setProperty(
            "card",
            True,
        )

        self.setProperty(
            "variant",
            "metricCard",
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.setMinimumHeight(118)

        # ====================================================
        # LAYOUT
        # ====================================================

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            16,
            14,
            16,
            14,
        )

        layout.setSpacing(7)

        # ====================================================
        # TITLE
        # ====================================================

        self.title_label = QLabel(
            str(title or "")
        )

        self.title_label.setTextFormat(
            Qt.TextFormat.PlainText
        )

        self.title_label.setProperty(
            "role",
            "muted",
        )

        self.title_label.setWordWrap(
            True
        )

        # ====================================================
        # VALUE
        # ====================================================

        self.value_label = QLabel(
            str(value or "--")
        )

        self.value_label.setTextFormat(
            Qt.TextFormat.PlainText
        )

        self.value_label.setProperty(
            "role",
            (
                "metricLarge"
                if large
                else "metric"
            ),
        )

        self.value_label.setWordWrap(
            True
        )

        # ====================================================
        # SUBTITLE
        # ====================================================

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

        # ====================================================
        # ASSEMBLE
        # ====================================================

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.value_label
        )

        layout.addWidget(
            self.subtitle_label
        )

        layout.addStretch()

        self.set_tone(
            tone,
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    @property
    def tone(self) -> str:
        return self._tone

    def set_title(
        self,
        title: str,
    ) -> None:
        self.title_label.setText(
            str(title or "")
        )

    def set_value(
        self,
        value,
    ) -> None:
        if value is None:
            text = "--"
        else:
            text = str(value)

        self.value_label.setText(
            text
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

    def set_tone(
        self,
        tone: str,
    ) -> None:
        normalized = (
            tone
            if tone in self.VALID_TONES
            else "neutral"
        )

        self._tone = normalized

        self.setProperty(
            "tone",
            normalized,
        )

        polish(self)

    def set_large_value(
        self,
        enabled: bool,
    ) -> None:
        self.value_label.setProperty(
            "role",
            (
                "metricLarge"
                if enabled
                else "metric"
            ),
        )

        polish(
            self.value_label
        )