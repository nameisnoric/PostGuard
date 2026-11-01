"""Non-intrusive PostGuard eye reminder toast."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.ui.theme import APP_QSS


TOAST_WIDTH = 380
TOAST_SCREEN_MARGIN = 24
TOAST_AUTO_CLOSE_MS = 8_000


ALERT_TYPE_TEXT = {
    "FIRST": "แจ้งเตือนครั้งแรก",
    "REPEAT": "แจ้งเตือนซ้ำ",
}


class EyeAlertDialog(QDialog):
    """
    Compact eye reminder toast.

    Important:
    - Does not pause Monitoring.
    - Does not reset Eye Alert Policy.
    - Does not change Blink Detection state.
    - Does not steal keyboard focus.
    """

    def __init__(
        self,
        *,
        blink_rate_per_minute: float | None,
        alert_type: str | None,
        window_blink_count: int | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.setWindowTitle(
            "PostGuard - Eye Reminder"
        )

        self.setWindowModality(
            Qt.WindowModality.NonModal
        )

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            False,
        )

        self.setStyleSheet(
            APP_QSS
        )

        self.setFixedWidth(
            TOAST_WIDTH
        )

        root_layout = QVBoxLayout(
            self
        )

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        card = QFrame()

        card.setProperty(
            "card",
            True,
        )

        card_layout = QVBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            18,
            16,
            18,
            14,
        )

        card_layout.setSpacing(
            10
        )

        root_layout.addWidget(
            card
        )

        # ====================================================
        # HEADER
        # ====================================================

        header = QHBoxLayout()

        icon = QLabel(
            "👁"
        )

        icon.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        icon.setFixedSize(
            36,
            36,
        )

        title_layout = QVBoxLayout()

        title = QLabel(
            "Eye Reminder"
        )

        title.setProperty(
            "role",
            "title",
        )

        subtitle = QLabel(
            "อัตราการกะพริบตาค่อนข้างต่ำ"
        )

        subtitle.setProperty(
            "role",
            "muted",
        )

        title_layout.addWidget(
            title
        )

        title_layout.addWidget(
            subtitle
        )

        header.addWidget(
            icon
        )

        header.addLayout(
            title_layout,
            1,
        )

        # ====================================================
        # MESSAGE
        # ====================================================

        message = QLabel(
            "ตรวจพบว่าอัตราการกะพริบตาต่ำต่อเนื่อง "
            "ลองกะพริบตาให้เต็มที่และพักสายตาเป็นระยะ"
        )

        message.setWordWrap(
            True
        )

        # ====================================================
        # DETAILS
        # ====================================================

        if (
            type(blink_rate_per_minute)
            in
            (int, float)
        ):

            rate_text = (
                f"{float(blink_rate_per_minute):.1f} ครั้ง/นาที"
            )

        else:

            rate_text = "N/A"

        rate_label = QLabel(
            f"Blink Rate: {rate_text}"
        )

        rate_label.setProperty(
            "role",
            "muted",
        )

        if (
            type(window_blink_count)
            is int
        ):

            count_label = QLabel(
                "จำนวนในช่วงล่าสุด: "
                f"{window_blink_count} ครั้ง"
            )

        else:

            count_label = QLabel(
                "จำนวนในช่วงล่าสุด: N/A"
            )

        count_label.setProperty(
            "role",
            "muted",
        )

        alert_text = ALERT_TYPE_TEXT.get(
            alert_type,
            "การแจ้งเตือน",
        )

        type_label = QLabel(
            alert_text
        )

        type_label.setProperty(
            "role",
            "muted",
        )

        # ====================================================
        # ACTION
        # ====================================================

        action_row = QHBoxLayout()

        action_row.addStretch()

        self.acknowledge_button = QPushButton(
            "รับทราบ"
        )

        self.acknowledge_button.setProperty(
            "variant",
            "primary",
        )

        self.acknowledge_button.setFixedWidth(
            92
        )

        self.acknowledge_button.clicked.connect(
            self.accept
        )

        action_row.addWidget(
            self.acknowledge_button
        )

        # ====================================================
        # ASSEMBLE
        # ====================================================

        card_layout.addLayout(
            header
        )

        card_layout.addWidget(
            message
        )

        card_layout.addWidget(
            rate_label
        )

        card_layout.addWidget(
            count_label
        )

        card_layout.addWidget(
            type_label
        )

        card_layout.addLayout(
            action_row
        )

        # ====================================================
        # AUTO CLOSE
        # ====================================================

        self.auto_close_timer = QTimer(
            self
        )

        self.auto_close_timer.setSingleShot(
            True
        )

        self.auto_close_timer.setInterval(
            TOAST_AUTO_CLOSE_MS
        )

        self.auto_close_timer.timeout.connect(
            self.accept
        )

    def _target_screen(
        self,
    ):

        screen = QGuiApplication.screenAt(
            QCursor.pos()
        )

        if screen is None:

            screen = (
                QGuiApplication.primaryScreen()
            )

        return screen

    def _move_to_bottom_right(
        self,
    ) -> None:

        screen = self._target_screen()

        if screen is None:

            return

        available = (
            screen.availableGeometry()
        )

        x = (
            available.x()
            + available.width()
            - self.width()
            - TOAST_SCREEN_MARGIN
        )

        y = (
            available.y()
            + available.height()
            - self.height()
            - TOAST_SCREEN_MARGIN
        )

        self.move(
            x,
            y,
        )

    def show_alert(
        self,
    ) -> None:

        self.adjustSize()

        self._move_to_bottom_right()

        self.show()

        self.auto_close_timer.start()

    def done(
        self,
        result: int,
    ) -> None:

        if self.auto_close_timer.isActive():

            self.auto_close_timer.stop()

        super().done(
            result
        )
