"""Reusable semantic status badge for PostGuard UI.

UI-only component.

This widget does not contain:
- monitoring business logic
- detection logic
- risk calculation
- alert policy
- database logic

It only renders a short visual status.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from app.ui.theme import polish


class StatusBadge(QLabel):
    """
    Small semantic status badge.

    Supported tones:
        neutral
        info
        success
        warning
        danger

    Example:
        badge = StatusBadge(
            "กำลังตรวจจับ",
            tone="success",
        )

        badge.set_status(
            "การเชื่อมต่อขาดหาย",
            "danger",
        )
    """

    VALID_TONES = {
        "neutral",
        "info",
        "success",
        "warning",
        "danger",
    }

    DEFAULT_SYMBOLS = {
        "neutral": "○",
        "info": "i",
        "success": "✓",
        "warning": "!",
        "danger": "!",
    }

    def __init__(
        self,
        text: str = "",
        tone: str = "neutral",
        *,
        show_symbol: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._raw_text = str(text or "")
        self._tone = "neutral"
        self._show_symbol = bool(show_symbol)

        self.setTextFormat(
            Qt.TextFormat.PlainText
        )

        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Fixed,
        )

        self.setMinimumHeight(28)

        self.setProperty(
            "role",
            "statusPill",
        )

        self.set_tone(
            tone,
            refresh=False,
        )

        self._refresh_text()

    # ========================================================
    # PUBLIC API
    # ========================================================

    @property
    def tone(self) -> str:
        return self._tone

    @property
    def raw_text(self) -> str:
        return self._raw_text

    def set_status(
        self,
        text: str,
        tone: str | None = None,
    ) -> None:
        """
        Update badge text and optionally its semantic tone.
        """

        self._raw_text = str(
            text or ""
        )

        if tone is not None:
            self.set_tone(
                tone,
                refresh=False,
            )

        self._refresh_text()

        polish(self)

    def set_tone(
        self,
        tone: str,
        *,
        refresh: bool = True,
    ) -> None:
        """
        Change visual tone without changing business state.
        """

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

        # ----------------------------------------------------
        # Legacy compatibility
        # ----------------------------------------------------
        # Some existing PostGuard QSS/tests still inspect the
        # old "status" property.
        #
        # Keep it available while the UI is gradually migrated.
        # ----------------------------------------------------

        legacy_status = {
            "neutral": "idle",
            "info": "idle",
            "success": "running",
            "warning": "paused",
            "danger": "error",
        }[normalized]

        self.setProperty(
            "status",
            legacy_status,
        )

        if refresh:
            self._refresh_text()
            polish(self)

    def set_show_symbol(
        self,
        enabled: bool,
    ) -> None:
        self._show_symbol = bool(
            enabled
        )

        self._refresh_text()

    # ========================================================
    # INTERNAL
    # ========================================================

    def _refresh_text(self) -> None:
        text = self._raw_text.strip()

        if not self._show_symbol:
            self.setText(text)
            return

        symbol = self.DEFAULT_SYMBOLS.get(
            self._tone,
            "○",
        )

        if text:
            self.setText(
                f"{symbol}  {text}"
            )
        else:
            self.setText(symbol)