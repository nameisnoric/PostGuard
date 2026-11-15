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

        normalized = value.strip().upper()

        if "DATA_GAP" in normalized:
            value = "รอข้อมูล"
        elif "CAMERA_MOVED" in normalized or "CAMERA_DATA_GAP" in normalized:
            value = "ไม่มีข้อมูล"
        elif "NOT_EVALUATED" in normalized:
            value = "กำลังประเมิน"
        elif normalized in {"N/A", "--", "-"}:
            value = "รอข้อมูล"
        elif normalized.startswith("N/A"):
            value = "รอข้อมูล"
        elif normalized.startswith("LOW"):
            value = "ต่ำ"
        elif normalized.startswith("MODERATE") or normalized.startswith("MEDIUM"):
            value = "ปานกลาง"
        elif normalized.startswith("HIGH"):
            value = "สูง"
        elif normalized.startswith("NONE"):
            value = "ปกติ"
        elif normalized == "COMPLETE":
            value = "ประเมินแล้ว"
        elif normalized.startswith("NO_ALERT"):
            value = "ไม่มีการแจ้งเตือน"
        elif normalized.startswith("ALERT"):
            value = "แจ้งเตือนแล้ว"
        elif normalized.startswith("SUPPRESSED"):
            value = "กำลังติดตาม"

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
    tile.setFixedHeight(104)
    tile.setSizePolicy(
        QSizePolicy.Policy.Ignored,
        QSizePolicy.Policy.Fixed,
    )

    layout = QVBoxLayout(tile)
    layout.setContentsMargins(11, 9, 11, 9)
    layout.setSpacing(5)

    heading = QLabel(f"{icon}  {title}")
    heading.setAlignment(
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignTop
    )
    heading.setStyleSheet(
        "font-size: 11px;"
        "font-weight: 700;"
        "color: #475569;"
        "border: none;"
    )

    value_label.setStyleSheet(
        f"font-size: 16px;"
        f"font-weight: 800;"
        f"color: {accent};"
        "border: none;"
    )
    value_label.setSizePolicy(
        QSizePolicy.Policy.Ignored,
        QSizePolicy.Policy.Preferred,
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
            "font-size: 19px;"
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
            ("สถานะการแจ้งเตือน:", "การแจ้งเตือน:")
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

        for column in range(4):
            grid.setColumnStretch(column, 1)
            grid.setColumnMinimumWidth(column, 0)

        root.addLayout(grid)

        # Compatibility-only values; keep updating but hide from main UI.
        self.factor_label = QLabel("ปัจจัยด้านท่าทาง: -")
        self.event_label = QLabel("เหตุการณ์: -")

        self.factor_label.hide()
        self.event_label.hide()
