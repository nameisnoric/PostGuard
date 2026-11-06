"""Reusable PostGuard risk-level badge.

UI-only component.

RiskBadge displays a risk value that has already been calculated
by PostGuard production logic.

It must never calculate or modify the actual risk level.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from app.ui.theme import polish


class RiskBadge(QLabel):
    """
    Compact visual representation of PostGuard risk level.

    Supported production values:
        NONE
        LOW
        MODERATE
        HIGH

    Additional display-only states:
        NOT_EVALUATED
        DATA_GAP
        UNKNOWN
    """

    RISK_TEXT = {
        "NONE": "ปกติ",
        "LOW": "ความเสี่ยงต่ำ",
        "MODERATE": "ความเสี่ยงปานกลาง",
        "HIGH": "ความเสี่ยงสูง",
        "NOT_EVALUATED": "ยังประเมินไม่ได้",
        "DATA_GAP": "ข้อมูลไม่เพียงพอ",
        "UNKNOWN": "ไม่ทราบสถานะ",
    }

    RISK_SYMBOL = {
        "NONE": "✓",
        "LOW": "●",
        "MODERATE": "!",
        "HIGH": "!",
        "NOT_EVALUATED": "—",
        "DATA_GAP": "—",
        "UNKNOWN": "?",
    }

    VALID_RISKS = set(
        RISK_TEXT.keys()
    )

    def __init__(
        self,
        risk_level: str | None = None,
        *,
        show_prefix: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._risk_level = "UNKNOWN"
        self._show_prefix = bool(
            show_prefix
        )

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

        self.setMinimumHeight(30)

        self.setProperty(
            "role",
            "riskBadge",
        )

        self.set_risk(
            risk_level,
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    @property
    def risk_level(self) -> str:
        return self._risk_level

    def set_risk(
        self,
        risk_level: str | None,
    ) -> None:
        """
        Display an already-calculated PostGuard risk level.

        This does not evaluate or modify risk.
        """

        normalized = str(
            risk_level or "UNKNOWN"
        ).strip().upper()

        if normalized not in self.VALID_RISKS:
            normalized = "UNKNOWN"

        self._risk_level = normalized

        # ----------------------------------------------------
        # QSS currently defines:
        # NONE / LOW / MODERATE / HIGH
        #
        # Display-only unavailable states use neutral NONE
        # styling without pretending that their logical value
        # is actually NONE.
        # ----------------------------------------------------

        visual_risk = (
            normalized
            if normalized
            in {
                "NONE",
                "LOW",
                "MODERATE",
                "HIGH",
            }
            else "NONE"
        )

        self.setProperty(
            "risk",
            visual_risk,
        )

        self._refresh_text()

        polish(self)

    def set_show_prefix(
        self,
        enabled: bool,
    ) -> None:
        self._show_prefix = bool(
            enabled
        )

        self._refresh_text()

    # ========================================================
    # INTERNAL
    # ========================================================

    def _refresh_text(self) -> None:
        risk = self._risk_level

        text = self.RISK_TEXT.get(
            risk,
            self.RISK_TEXT["UNKNOWN"],
        )

        symbol = self.RISK_SYMBOL.get(
            risk,
            "?",
        )

        if self._show_prefix:
            self.setText(
                f"{symbol}  {text}"
            )
        else:
            self.setText(text)