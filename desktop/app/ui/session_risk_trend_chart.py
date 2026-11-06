"""Qt chart for historical PostGuard Session Risk Scores."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class SessionRiskTrendChart(QWidget):
    """Visualization-only chart for persisted session risk scores."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.series = []
        self.setMinimumHeight(280)
        self.setMinimumWidth(360)
        self.setToolTip(
            "กราฟแสดงค่าเฉลี่ย PostGuard Risk Score "
            "ของแต่ละเซสชันที่สามารถเปรียบเทียบได้"
        )

    def set_series(self, series) -> None:
        validated = []

        if isinstance(series, list):
            for item in series:
                if not isinstance(item, dict):
                    continue

                session_id = item.get("session_id")
                score = item.get("score")

                if type(session_id) is not int or session_id <= 0:
                    continue

                if type(score) not in (int, float):
                    continue

                score = float(score)

                if not math.isfinite(score) or not 0.0 <= score <= 100.0:
                    continue

                validated.append(
                    {
                        "session_id": session_id,
                        "score": score,
                        "risk_score_method": item.get("risk_score_method"),
                    }
                )

        self.series = validated
        self.update()

    def clear(self) -> None:
        self.series = []
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        background = QColor("#ffffff")
        text = QColor("#334155")
        muted = QColor("#64748b")
        grid = QColor("#e2e8f0")
        line = QColor("#2563eb")
        area = QColor("#dbeafe")
        point = QColor("#1d4ed8")

        painter.fillRect(self.rect(), background)

        width = self.width()
        height = self.height()

        left = 56.0
        right = 24.0
        top = 34.0
        bottom = 52.0

        plot_width = max(1.0, width - left - right)
        plot_height = max(1.0, height - top - bottom)

        if not self.series:
            painter.setPen(muted)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "ยังไม่มีประวัติ Risk Score ที่สามารถเปรียบเทียบได้",
            )
            return

        grid_pen = QPen(grid)
        grid_pen.setWidthF(1.0)

        for score_level in (0, 25, 50, 75, 100):
            y = top + plot_height * (1.0 - score_level / 100.0)

            painter.setPen(grid_pen)
            painter.drawLine(
                QPointF(left, y),
                QPointF(left + plot_width, y),
            )

            painter.setPen(text)
            painter.drawText(
                QRectF(4.0, y - 10.0, left - 12.0, 20.0),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(score_level),
            )

        count = len(self.series)

        if count == 1:
            x_positions = [left + plot_width / 2.0]
        else:
            spacing = plot_width / (count - 1)
            x_positions = [
                left + index * spacing
                for index in range(count)
            ]

        points = []

        for x, item in zip(x_positions, self.series):
            y = top + plot_height * (1.0 - item["score"] / 100.0)
            points.append(QPointF(x, y))

        if len(points) >= 2:
            area_path = QPainterPath()
            area_path.moveTo(points[0].x(), top + plot_height)
            area_path.lineTo(points[0])

            for p in points[1:]:
                area_path.lineTo(p)

            area_path.lineTo(points[-1].x(), top + plot_height)
            area_path.closeSubpath()
            painter.fillPath(area_path, area)

            path = QPainterPath()
            path.moveTo(points[0])

            for p in points[1:]:
                path.lineTo(p)

            line_pen = QPen(line)
            line_pen.setWidthF(2.8)
            painter.setPen(line_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        for p, item in zip(points, self.series):
            painter.setPen(QPen(QColor("#ffffff"), 2.0))
            painter.setBrush(point)
            painter.drawEllipse(p, 5.5, 5.5)

            painter.setPen(text)
            painter.drawText(
                QRectF(p.x() - 34.0, p.y() - 30.0, 68.0, 20.0),
                Qt.AlignmentFlag.AlignCenter,
                f"{item['score']:.2f}",
            )

            painter.setPen(muted)
            painter.drawText(
                QRectF(
                    p.x() - 34.0,
                    top + plot_height + 10.0,
                    68.0,
                    20.0,
                ),
                Qt.AlignmentFlag.AlignCenter,
                f"#{item['session_id']}",
            )

        painter.setPen(muted)
        painter.drawText(
            QRectF(left, height - 22.0, plot_width, 18.0),
            Qt.AlignmentFlag.AlignCenter,
            "เซสชัน",
        )
