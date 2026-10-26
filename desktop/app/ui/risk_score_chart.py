"""PostGuard Risk Score time-series chart."""

from PySide6.QtCore import (
    QPointF,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QWidget,
)


class RiskScoreChart(
    QWidget
):
    """
    Lightweight PostGuard Risk Score chart.

    Uses QPainter directly so PostGuard does not need
    matplotlib as a Desktop dependency.

    X axis:
        elapsed Session seconds

    Y axis:
        PostGuard Risk Score 0-100

    Main line:
        average_risk_score for each 10-second bucket

    Vertical range:
        minimum -> maximum score for each bucket
    """

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self._buckets = []

        self.setMinimumHeight(
            300
        )

        self.setMinimumWidth(
            600
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def set_buckets(
        self,
        buckets: list[dict],
    ) -> None:
        if not isinstance(
            buckets,
            list,
        ):
            buckets = []

        self._buckets = [
            dict(
                bucket
            )
            for bucket
            in buckets
            if isinstance(
                bucket,
                dict,
            )
        ]

        self.update()

    def clear_chart(
        self,
    ) -> None:
        self._buckets = []
        self.update()

    def sizeHint(
        self,
    ) -> QSize:
        return QSize(
            900,
            340,
        )

    # ========================================================
    # COORDINATE HELPERS
    # ========================================================

    @staticmethod
    def _score_y(
        score: float,
        chart_rect: QRectF,
    ) -> float:
        score = max(
            0.0,
            min(
                100.0,
                float(score),
            ),
        )

        fraction = (
            score
            /
            100.0
        )

        return (
            chart_rect.bottom()
            -
            (
                fraction
                *
                chart_rect.height()
            )
        )

    @staticmethod
    def _time_x(
        seconds: float,
        maximum_seconds: float,
        chart_rect: QRectF,
    ) -> float:
        if maximum_seconds <= 0:
            return chart_rect.left()

        fraction = (
            float(seconds)
            /
            maximum_seconds
        )

        fraction = max(
            0.0,
            min(
                1.0,
                fraction,
            ),
        )

        return (
            chart_rect.left()
            +
            fraction
            *
            chart_rect.width()
        )

    # ========================================================
    # DRAW
    # ========================================================

    def paintEvent(
        self,
        _event,
    ) -> None:
        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        painter.fillRect(
            self.rect(),
            QColor(
                "#FFFFFF"
            ),
        )

        outer = QRectF(
            self.rect()
        )

        chart_rect = QRectF(
            outer.left() + 62,
            outer.top() + 26,
            max(
                10.0,
                outer.width()
                - 86,
            ),
            max(
                10.0,
                outer.height()
                - 76,
            ),
        )

        self._draw_grid(
            painter,
            chart_rect,
        )

        if not self._buckets:
            self._draw_empty_state(
                painter,
                chart_rect,
            )

            return

        maximum_seconds = max(
            float(
                bucket.get(
                    "end_second",
                    0.0,
                )
            )
            for bucket
            in self._buckets
        )

        if maximum_seconds <= 0:
            self._draw_empty_state(
                painter,
                chart_rect,
            )

            return

        self._draw_time_labels(
            painter,
            chart_rect,
            maximum_seconds,
        )

        self._draw_ranges(
            painter,
            chart_rect,
            maximum_seconds,
        )

        self._draw_average_line(
            painter,
            chart_rect,
            maximum_seconds,
        )

    # ========================================================
    # GRID
    # ========================================================

    def _draw_grid(
        self,
        painter: QPainter,
        chart_rect: QRectF,
    ) -> None:
        grid_pen = QPen(
            QColor(
                "#D9E2EF"
            )
        )

        grid_pen.setWidthF(
            1.0
        )

        painter.setPen(
            grid_pen
        )

        font = QFont(
            painter.font()
        )

        font.setPointSize(
            9
        )

        painter.setFont(
            font
        )

        label_color = QColor(
            "#64748B"
        )

        for score in (
            0,
            20,
            40,
            60,
            80,
            100,
        ):
            y = self._score_y(
                score,
                chart_rect,
            )

            painter.drawLine(
                QPointF(
                    chart_rect.left(),
                    y,
                ),
                QPointF(
                    chart_rect.right(),
                    y,
                ),
            )

            painter.setPen(
                label_color
            )

            painter.drawText(
                QRectF(
                    4,
                    y - 10,
                    50,
                    20,
                ),
                Qt.AlignmentFlag.AlignRight
                |
                Qt.AlignmentFlag.AlignVCenter,
                str(
                    score
                ),
            )

            painter.setPen(
                grid_pen
            )

        axis_pen = QPen(
            QColor(
                "#94A3B8"
            )
        )

        axis_pen.setWidthF(
            1.2
        )

        painter.setPen(
            axis_pen
        )

        painter.drawLine(
            chart_rect.bottomLeft(),
            chart_rect.bottomRight(),
        )

        painter.drawLine(
            chart_rect.topLeft(),
            chart_rect.bottomLeft(),
        )

    # ========================================================
    # TIME LABELS
    # ========================================================

    def _draw_time_labels(
        self,
        painter: QPainter,
        chart_rect: QRectF,
        maximum_seconds: float,
    ) -> None:
        painter.setPen(
            QColor(
                "#64748B"
            )
        )

        label_count = 5

        for index in range(
            label_count + 1
        ):
            fraction = (
                index
                /
                label_count
            )

            seconds = (
                maximum_seconds
                *
                fraction
            )

            x = (
                chart_rect.left()
                +
                chart_rect.width()
                *
                fraction
            )

            painter.drawLine(
                QPointF(
                    x,
                    chart_rect.bottom(),
                ),
                QPointF(
                    x,
                    chart_rect.bottom() + 5,
                ),
            )

            painter.drawText(
                QRectF(
                    x - 35,
                    chart_rect.bottom() + 8,
                    70,
                    22,
                ),
                Qt.AlignmentFlag.AlignHCenter
                |
                Qt.AlignmentFlag.AlignTop,
                self._format_time(
                    seconds
                ),
            )

    @staticmethod
    def _format_time(
        seconds: float,
    ) -> str:
        seconds = max(
            0,
            int(
                round(
                    seconds
                )
            ),
        )

        minutes = (
            seconds
            //
            60
        )

        remaining = (
            seconds
            %
            60
        )

        return (
            f"{minutes}:{remaining:02d}"
        )

    # ========================================================
    # MIN-MAX RANGE
    # ========================================================

    def _draw_ranges(
        self,
        painter: QPainter,
        chart_rect: QRectF,
        maximum_seconds: float,
    ) -> None:
        pen = QPen(
            QColor(
                "#93C5FD"
            )
        )

        pen.setWidthF(
            3.0
        )

        painter.setPen(
            pen
        )

        for bucket in self._buckets:
            midpoint = (
                float(
                    bucket[
                        "start_second"
                    ]
                )
                +
                float(
                    bucket[
                        "end_second"
                    ]
                )
            ) / 2.0

            x = self._time_x(
                midpoint,
                maximum_seconds,
                chart_rect,
            )

            minimum_y = (
                self._score_y(
                    bucket[
                        "minimum_risk_score"
                    ],
                    chart_rect,
                )
            )

            maximum_y = (
                self._score_y(
                    bucket[
                        "maximum_risk_score"
                    ],
                    chart_rect,
                )
            )

            painter.drawLine(
                QPointF(
                    x,
                    maximum_y,
                ),
                QPointF(
                    x,
                    minimum_y,
                ),
            )

    # ========================================================
    # AVG LINE
    # ========================================================

    def _draw_average_line(
        self,
        painter: QPainter,
        chart_rect: QRectF,
        maximum_seconds: float,
    ) -> None:
        path = QPainterPath()

        points = []

        for bucket in self._buckets:
            midpoint = (
                float(
                    bucket[
                        "start_second"
                    ]
                )
                +
                float(
                    bucket[
                        "end_second"
                    ]
                )
            ) / 2.0

            x = self._time_x(
                midpoint,
                maximum_seconds,
                chart_rect,
            )

            y = self._score_y(
                bucket[
                    "average_risk_score"
                ],
                chart_rect,
            )

            points.append(
                QPointF(
                    x,
                    y,
                )
            )

        if not points:
            return

        path.moveTo(
            points[0]
        )

        for point in points[1:]:
            path.lineTo(
                point
            )

        line_pen = QPen(
            QColor(
                "#2563EB"
            )
        )

        line_pen.setWidthF(
            2.5
        )

        painter.setPen(
            line_pen
        )

        painter.drawPath(
            path
        )

        painter.setBrush(
            QColor(
                "#2563EB"
            )
        )

        for point in points:
            painter.drawEllipse(
                point,
                4.0,
                4.0,
            )

    # ========================================================
    # EMPTY STATE
    # ========================================================

    @staticmethod
    def _draw_empty_state(
        painter: QPainter,
        chart_rect: QRectF,
    ) -> None:
        painter.setPen(
            QColor(
                "#64748B"
            )
        )

        painter.drawText(
            chart_rect,
            Qt.AlignmentFlag.AlignCenter,
            (
                "ไม่มีข้อมูล Risk Score "
                "สำหรับสร้างกราฟ"
            ),
        )