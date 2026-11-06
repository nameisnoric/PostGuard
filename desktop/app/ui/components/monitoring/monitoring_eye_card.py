"""Eye and blink monitoring presentation card.

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

        super().setText(value)


def _tile(title, icon, value_label, accent="#0f172a"):
    tile = QFrame()
    tile.setObjectName("eyeMetricTile")
    tile.setStyleSheet(
        "QFrame#eyeMetricTile {"
        "background: #ffffff;"
        "border: 1px solid #dbe4ef;"
        "border-radius: 12px;"
        "}"
    )
    tile.setMinimumHeight(100)

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
        f"font-size: 20px;"
        f"font-weight: 800;"
        f"color: {accent};"
        "border: none;"
    )

    layout.addWidget(heading)
    layout.addStretch(1)
    layout.addWidget(value_label)
    layout.addStretch(1)

    return tile


class MonitoringEyeCard(QFrame):
    """Display eye state and blink information."""

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

        self.title_label = QLabel(
            "👁  สายตาและการกระพริบตา"
        )
        self.title_label.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 800;"
            "color: #0f172a;"
        )

        status = QLabel("● ตรวจจับอยู่")
        status.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 700;"
            "color: #15803d;"
        )

        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(status)

        root.addLayout(header)

        self.eye_state_label = MetricValueLabel(
            ("สถานะตารวม:", "สถานะตา:")
        )
        self.blink_count_label = MetricValueLabel(
            ("จำนวนการกระพริบตา:", "กระพริบตา:")
        )
        self.right_eye_state_label = MetricValueLabel(
            ("ตาขวา:",)
        )
        self.left_eye_state_label = MetricValueLabel(
            ("ตาซ้าย:",)
        )
        self.eye_openness_label = MetricValueLabel(
            ("การเปิดตา:", "ค่าการเปิดตา:")
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        grid.addWidget(
            _tile("สถานะตารวม", "👁", self.eye_state_label, "#15803d"),
            0, 0,
        )
        grid.addWidget(
            _tile("กระพริบตา", "✨", self.blink_count_label, "#1d4ed8"),
            0, 1,
        )
        grid.addWidget(
            _tile("ตาขวา", "◉", self.right_eye_state_label, "#15803d"),
            0, 2,
        )
        grid.addWidget(
            _tile("ตาซ้าย", "◉", self.left_eye_state_label, "#15803d"),
            0, 3,
        )
        grid.addWidget(
            _tile("การเปิดตา (R | L)", "〽", self.eye_openness_label, "#334155"),
            0, 4,
        )

        root.addLayout(grid)

        self.detail_title_label = QLabel("รายละเอียด")
        self.eye_pattern_label = QLabel("รูปแบบตา: --")

        self.detail_title_label.hide()
        self.eye_pattern_label.hide()
