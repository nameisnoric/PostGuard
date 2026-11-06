"""PostGuard risk presentation card.

UI-only component.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)


class MetricValueLabel(QLabel):
    def __init__(self, prefixes=(), parent=None):
        super().__init__("--", parent)
        self.prefixes = tuple(prefixes)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)

    def setText(self, text):
        value = str(text)

        for prefix in self.prefixes:
            if value.startswith(prefix):
                value = value[len(prefix):].strip()
                break

        replacements = {
            "NOT_EVALUATED": "ยังไม่ประเมิน",
            "DATA_GAP": "รอข้อมูล",
        }

        for source, target in replacements.items():
            if source in value:
                value = target
                break

        super().setText(value)


def _tile(title, icon, value_label, background="#ffffff", accent="#0f172a"):
    tile = QFrame()
    tile.setObjectName("riskMetricTile")
    tile.setStyleSheet(
        "QFrame#riskMetricTile {"
        f"background: {background};"
        "border: 1px solid #dbe4ef;"
        "border-radius: 12px;"
        "}"
    )
    tile.setMinimumHeight(104)

    layout = QVBoxLayout(tile)
    layout.setContentsMargins(11, 9, 11, 9)
    layout.setSpacing(5)

    heading = QLabel(f"{icon}  {title}")
    heading.setAlignment(
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignTop
    )
    heading.setStyleSheet(
        "font-size: 12px;"
        "font-weight: 700;"
        "color: #475569;"
        "border: none;"
    )

    value_label.setStyleSheet(
        f"font-size: 19px;"
        f"font-weight: 800;"
        f"color: {accent};"
        "border: none;"
    )

    layout.addWidget(heading)
    layout.addStretch(1)
    layout.addWidget(value_label)
    layout.addStretch(1)

    return tile


class MonitoringRiskCard(QFrame):
    """Display validated PostGuard risk results."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setProperty("card", True)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()

        self.title_label = QLabel("⚠  ความเสี่ยง")
        self.title_label.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 800;"
            "color: #0f172a;"
        )

        self.risk_note_label = QLabel(
            "การประเมินของ PostGuard"
        )
        self.risk_note_label.setStyleSheet(
            "font-size: 11px;"
            "color: #64748b;"
        )

        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.risk_note_label)

        root.addLayout(header)

        self.risk_label = MetricValueLabel(
            ("ระดับความเสี่ยง:", "ความเสี่ยง:")
        )
        self.assessment_label = MetricValueLabel(
            ("ผลการประเมิน:", "การประเมินท่าทาง:")
        )
        self.duration_label = MetricValueLabel(
            ("ปัจจัยต่อเนื่องนานที่สุด:", "ต่อเนื่องนานสุด:")
        )
        self.alert_label = MetricValueLabel(
            ("การแจ้งเตือน:",)
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        grid.addWidget(
            _tile(
                "ระดับความเสี่ยง",
                "🛡",
                self.risk_label,
                "#fffaf0",
                "#92400e",
            ),
            0, 0,
        )
        grid.addWidget(
            _tile(
                "ผลการประเมิน",
                "📋",
                self.assessment_label,
                "#f8fafc",
                "#334155",
            ),
            0, 1,
        )
        grid.addWidget(
            _tile(
                "ต่อเนื่องนานสุด",
                "⏱",
                self.duration_label,
                "#f8fafc",
                "#1e3a8a",
            ),
            0, 2,
        )
        grid.addWidget(
            _tile(
                "การแจ้งเตือน",
                "🔔",
                self.alert_label,
                "#fffaf0",
                "#92400e",
            ),
            0, 3,
        )

        root.addLayout(grid)

        # Compatibility-only values; keep updating but hide from main UI.
        self.factor_label = QLabel("ปัจจัยด้านท่าทาง: -")
        self.event_label = QLabel("เหตุการณ์: -")

        self.factor_label.hide()
        self.event_label.hide()
