"""Qt chart for historical PostGuard Session Risk Scores."""

import math

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QWidget,
)


class SessionRiskTrendChart(
    QWidget
):
    """
    Display persisted average PostGuard Risk Scores
    across multiple Sessions.

    The widget performs visualization only.
    It never calculates Risk Scores.
    """

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.series = []

        self.setMinimumHeight(
            260
        )

        self.setMinimumWidth(
            360
        )

        self.setToolTip(
            (
                "กราฟแสดง average PostGuard Risk Score "
                "ของแต่ละ Session ที่เปรียบเทียบได้"
            )
        )

    def set_series(
        self,
        series,
    ) -> None:
        """
        Replace displayed chart data.

        Expected point:

        {
            "session_id": 38,
            "score": 21.25,
            "risk_score_method": "..."
        }
        """

        validated = []

        if isinstance(
            series,
            list,
        ):
            for point in series:
                if not isinstance(
                    point,
                    dict,
                ):
                    continue

                session_id = point.get(
                    "session_id"
                )

                score = point.get(
                    "score"
                )

                if (
                    type(session_id)
                    is not int
                    or
                    session_id <= 0
                ):
                    continue

                if (
                    type(score)
                    not in (
                        int,
                        float,
                    )
                ):
                    continue

                score = float(
                    score
                )

                if (
                    not math.isfinite(
                        score
                    )
                    or
                    not (
                        0.0
                        <=
                        score
                        <=
                        100.0
                    )
                ):
                    continue

                validated.append(
                    {
                        "session_id": (
                            session_id
                        ),
                        "score": score,
                        "risk_score_method": (
                            point.get(
                                "risk_score_method"
                            )
                        ),
                    }
                )

        self.series = (
            validated
        )

        self.update()

    def clear(
        self,
    ) -> None:
        self.series = []

        self.update()

    def paintEvent(
        self,
        _event,
    ):
        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        palette = self.palette()

        text_color = palette.color(
            palette.ColorRole.Text
        )

        muted_color = palette.color(
            palette.ColorRole.PlaceholderText
        )

        line_color = palette.color(
            palette.ColorRole.Highlight
        )

        background_color = palette.color(
            palette.ColorRole.Base
        )

        painter.fillRect(
            self.rect(),
            background_color,
        )

        width = self.width()
        height = self.height()

        left = 52.0
        right = 22.0
        top = 24.0
        bottom = 48.0

        plot_width = max(
            1.0,
            width - left - right,
        )

        plot_height = max(
            1.0,
            height - top - bottom,
        )

        plot_rect = QRectF(
            left,
            top,
            plot_width,
            plot_height,
        )

        # ----------------------------------------------------
        # Empty
        # ----------------------------------------------------

        if not self.series:
            painter.setPen(
                muted_color
            )

            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                (
                    "ยังไม่มี Risk Score History "
                    "ที่สามารถเปรียบเทียบได้"
                ),
            )

            return

        # ----------------------------------------------------
        # Horizontal grid
        # ----------------------------------------------------

        grid_pen = QPen(
            muted_color
        )

        grid_pen.setWidthF(
            0.7
        )

        painter.setPen(
            grid_pen
        )

        for score_level in (
            0,
            25,
            50,
            75,
            100,
        ):
            y = (
                top
                +
                plot_height
                *
                (
                    1.0
                    -
                    score_level
                    /
                    100.0
                )
            )

            painter.drawLine(
                QPointF(
                    left,
                    y,
                ),
                QPointF(
                    left + plot_width,
                    y,
                ),
            )

            painter.setPen(
                text_color
            )

            painter.drawText(
                QRectF(
                    4.0,
                    y - 10.0,
                    left - 10.0,
                    20.0,
                ),
                Qt.AlignmentFlag.AlignRight
                |
                Qt.AlignmentFlag.AlignVCenter,
                str(
                    score_level
                ),
            )

            painter.setPen(
                grid_pen
            )

        # ----------------------------------------------------
        # Points
        # ----------------------------------------------------

        count = len(
            self.series
        )

        if count == 1:
            x_positions = [
                left
                +
                plot_width
                /
                2.0
            ]

        else:
            spacing = (
                plot_width
                /
                (
                    count
                    -
                    1
                )
            )

            x_positions = [
                left
                +
                index
                *
                spacing
                for index
                in range(
                    count
                )
            ]

        points = []

        for x, item in zip(
            x_positions,
            self.series,
        ):
            score = (
                item[
                    "score"
                ]
            )

            y = (
                top
                +
                plot_height
                *
                (
                    1.0
                    -
                    score
                    /
                    100.0
                )
            )

            points.append(
                QPointF(
                    x,
                    y,
                )
            )

        # ----------------------------------------------------
        # Trend line
        # ----------------------------------------------------

        if len(
            points
        ) >= 2:
            path = QPainterPath()

            path.moveTo(
                points[
                    0
                ]
            )

            for point in points[
                1:
            ]:
                path.lineTo(
                    point
                )

            line_pen = QPen(
                line_color
            )

            line_pen.setWidthF(
                2.2
            )

            painter.setPen(
                line_pen
            )

            painter.drawPath(
                path
            )

        # ----------------------------------------------------
        # Point markers + labels
        # ----------------------------------------------------

        painter.setPen(
            QPen(
                line_color,
                2.0,
            )
        )

        painter.setBrush(
            line_color
        )

        for point, item in zip(
            points,
            self.series,
        ):
            painter.drawEllipse(
                point,
                4.5,
                4.5,
            )

            painter.setPen(
                text_color
            )

            score_text = (
                f"{item['score']:.2f}"
            )

            painter.drawText(
                QRectF(
                    point.x() - 32.0,
                    point.y() - 28.0,
                    64.0,
                    20.0,
                ),
                Qt.AlignmentFlag.AlignCenter,
                score_text,
            )

            painter.drawText(
                QRectF(
                    point.x() - 32.0,
                    top + plot_height + 8.0,
                    64.0,
                    22.0,
                ),
                Qt.AlignmentFlag.AlignCenter,
                (
                    f"#{item['session_id']}"
                ),
            )

            painter.setPen(
                QPen(
                    line_color,
                    2.0,
                )
            )

        # ----------------------------------------------------
        # Axis title
        # ----------------------------------------------------

        painter.setPen(
            muted_color
        )

        painter.drawText(
            QRectF(
                left,
                height - 22.0,
                plot_width,
                18.0,
            ),
            Qt.AlignmentFlag.AlignCenter,
            "Session",
        )