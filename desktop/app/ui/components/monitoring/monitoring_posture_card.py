"""Posture monitoring presentation card.

UI-only component.
All posture calculations remain inside MonitoringPage.
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
    """Keep existing setText contracts but show only the value."""

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


def _metric_tile(title, icon, value_label):
    tile = QFrame()
    tile.setObjectName("metricTile")
    tile.setStyleSheet(
        "QFrame#metricTile {"
        "background: #ffffff;"
        "border: 1px solid #dbe4ef;"
        "border-radius: 12px;"
        "}"
    )
    tile.setMinimumHeight(108)

    layout = QVBoxLayout(tile)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(5)

    heading = QLabel(f"{icon}  {title}")
    heading.setStyleSheet(
        "font-size: 12px;"
        "font-weight: 700;"
        "color: #475569;"
        "border: none;"
    )
    heading.setAlignment(
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignTop
    )

    value_label.setStyleSheet(
        "font-size: 22px;"
        "font-weight: 800;"
        "color: #0f172a;"
        "border: none;"
    )

    layout.addWidget(heading)
    layout.addStretch(1)
    layout.addWidget(value_label)
    layout.addStretch(1)

    return tile


class MonitoringPostureCard(QFrame):
    """Display posture and screen-distance information."""

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

        self.title_label = QLabel("🧍  ท่าทาง")
        self.title_label.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 800;"
            "color: #0f172a;"
        )

        self.detection_label = QLabel(
            "ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ"
        )
        self.detection_label.setStyleSheet(
            "font-size: 11px;"
            "color: #64748b;"
        )

        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.detection_label)

        root.addLayout(header)

        self.shoulder_label = MetricValueLabel(
            ("ความเอียงไหล่:", "ไหล่:")
        )
        self.neck_label = MetricValueLabel(
            ("ความเอียงคอด้านข้าง:", "คอด้านข้าง:")
        )
        self.flexion_label = MetricValueLabel(
            ("มุมก้ม/เงยคอ:", "ก้ม/เงยคอ:")
        )
        self.screen_distance_label = MetricValueLabel(
            ("ระยะห่างหน้าจอ:",)
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        grid.addWidget(
            _metric_tile("ไหล่", "↔", self.shoulder_label),
            0, 0,
        )
        grid.addWidget(
            _metric_tile("คอด้านข้าง", "🧭", self.neck_label),
            0, 1,
        )
        grid.addWidget(
            _metric_tile("ก้ม / เงยคอ", "↕", self.flexion_label),
            0, 2,
        )
        grid.addWidget(
            _metric_tile("ระยะห่างหน้าจอ", "📏", self.screen_distance_label),
            0, 3,
        )

        root.addLayout(grid)

        # Kept for MonitoringPage compatibility; hidden from primary UI.
        self.detail_title_label = QLabel("เทียบกับค่าท่าทางอ้างอิง")
        self.shoulder_difference_label = QLabel("ไหล่: --")
        self.neck_difference_label = QLabel("คอด้านข้าง: --")
        self.flexion_difference_label = QLabel("ก้ม/เงยคอ: --")

        for widget in (
            self.detail_title_label,
            self.shoulder_difference_label,
            self.neck_difference_label,
            self.flexion_difference_label,
        ):
            widget.hide()
