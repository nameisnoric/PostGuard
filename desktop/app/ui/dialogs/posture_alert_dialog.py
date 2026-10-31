"""Non-intrusive PostGuard toast notification produced by Alert Policy."""

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


RISK_TEXT = {
    "MODERATE": "ความเสี่ยงปานกลาง",
    "HIGH": "ความเสี่ยงสูง",
}

ALERT_TYPE_TEXT = {
    "FIRST": "แจ้งเตือนครั้งแรก",
    "REPEAT": "แจ้งเตือนซ้ำ",
    "ESCALATION": "ความเสี่ยงเพิ่มขึ้น",
    "RESOLUTION": "เหตุการณ์สิ้นสุด",
}

FACTOR_TEXT = {
    "LEFT_SHOULDER_HIGH": "ไหล่ซ้ายสูง",
    "RIGHT_SHOULDER_HIGH": "ไหล่ขวาสูง",
    "TILT_LEFT": "คอเอียงซ้าย",
    "TILT_RIGHT": "คอเอียงขวา",
    "FLEXION": "ก้มคอ",
    "EXTENSION": "เงยคอ",
}


class PostureAlertDialog(QDialog):
    """
    Compact non-intrusive PostGuard toast notification.

    UX contract
    -----------
    - Show at the bottom-right of the user's current screen.
    - Do not activate the PostGuard Main Window.
    - Do not steal keyboard focus.
    - Do not pause Monitoring.
    - Do not resolve Risk Event.
    - Do not reset Alert Policy cooldown.
    - Automatically disappear after a short period.
    - "รับทราบ" only dismisses the current notification.

    Alert timing remains the responsibility of Alert Policy.
    """

    def __init__(
        self,
        direction: int | None = None,
        duration_seconds: float = 0.0,
        parent=None,
        *,
        risk_level: str | None = None,
        alert_type: str | None = None,
        factors: list[str] | None = None,
    ):
        super().__init__(parent)

        # ====================================================
        # WINDOW BEHAVIOR
        # ====================================================

        self.setWindowTitle(
            "PostGuard - Posture Alert"
        )

        self.setWindowModality(
            Qt.WindowModality.NonModal
        )

        # Tool:
        #     Notification-like auxiliary window.
        #
        # FramelessWindowHint:
        #     Remove the large native title bar so the window
        #     behaves visually like a toast.
        #
        # WindowStaysOnTopHint:
        #     Keep the toast visible briefly above other apps.
        #
        # WindowDoesNotAcceptFocus:
        #     Do not steal keyboard focus from the application
        #     currently being used.
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        # Prevent Qt from activating PostGuard when the toast
        # becomes visible.
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

        # ====================================================
        # NORMALIZE INPUT
        # ====================================================

        normalized_risk = (
            risk_level
            if risk_level in RISK_TEXT
            else None
        )

        normalized_alert_type = (
            alert_type
            if alert_type in ALERT_TYPE_TEXT
            else None
        )

        normalized_factors = [
            factor
            for factor in (factors or [])
            if isinstance(
                factor,
                str,
            )
        ]

        # ====================================================
        # ROOT CARD
        # ====================================================

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

        header.setSpacing(
            10
        )

        icon = QLabel(
            "!"
        )

        icon.setProperty(
            "role",
            "warningIcon",
        )

        icon.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        icon.setFixedSize(
            36,
            36,
        )

        title_layout = QVBoxLayout()

        title_layout.setSpacing(
            1
        )

        title = QLabel(
            "Posture Alert"
        )

        title.setProperty(
            "role",
            "title",
        )

        risk_text = RISK_TEXT.get(
            normalized_risk,
            "ตรวจพบท่าทางที่ควรปรับ",
        )

        risk_label = QLabel(
            risk_text
        )

        risk_label.setProperty(
            "role",
            "muted",
        )

        title_layout.addWidget(
            title
        )

        title_layout.addWidget(
            risk_label
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

        if normalized_risk == "HIGH":

            message_text = (
                "ตรวจพบท่าทางที่มีความเสี่ยงสูงต่อเนื่อง "
                "กรุณาปรับตำแหน่งศีรษะ คอ และไหล่"
            )

        elif normalized_risk == "MODERATE":

            message_text = (
                "ตรวจพบท่าทางที่มีความเสี่ยงต่อเนื่อง "
                "กรุณาปรับท่าทางให้อยู่ในตำแหน่งที่เหมาะสม"
            )

        else:

            message_text = (
                "ตรวจพบท่าทางที่ควรปรับ "
                "กรุณาปรับท่าทางกลับสู่ตำแหน่งที่เหมาะสม"
            )

        message = QLabel(
            message_text
        )

        message.setWordWrap(
            True
        )

        # ====================================================
        # FACTORS
        # ====================================================

        if normalized_factors:

            factor_text = ", ".join(
                FACTOR_TEXT.get(
                    factor,
                    factor,
                )
                for factor in normalized_factors
            )

        elif direction is not None:

            factor_text = (
                "คอเอียงขวา"
                if direction > 0
                else "คอเอียงซ้าย"
            )

        else:

            factor_text = "ไม่ระบุ"

        # Keep the old attribute name for compatibility with
        # existing Desktop tests.
        self.direction_label = QLabel(
            f"ตรวจพบ: {factor_text}"
        )

        self.direction_label.setWordWrap(
            True
        )

        self.direction_label.setProperty(
            "role",
            "muted",
        )

        # ====================================================
        # ALERT TYPE / DURATION
        # ====================================================

        alert_text = ALERT_TYPE_TEXT.get(
            normalized_alert_type,
            "การแจ้งเตือน",
        )

        safe_duration = max(
            0.0,
            float(duration_seconds),
        )

        self.alert_type_label = QLabel(
            f"{alert_text}"
        )

        self.alert_type_label.setProperty(
            "role",
            "muted",
        )

        self.duration_label = QLabel(
            f"ต่อเนื่อง {safe_duration:.1f} วินาที"
        )

        self.duration_label.setProperty(
            "role",
            "muted",
        )

        meta_row = QHBoxLayout()

        meta_row.addWidget(
            self.alert_type_label
        )

        meta_row.addStretch()

        meta_row.addWidget(
            self.duration_label
        )

        # Compatibility with old popup tests / code.
        self.risk_label = risk_label

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

        # Acknowledge means only dismissing this presentation.
        #
        # It must NOT:
        # - resolve Risk Event,
        # - pause monitoring,
        # - reset Alert Policy,
        # - reset cooldown.
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
            self.direction_label
        )

        card_layout.addLayout(
            meta_row
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

    # ========================================================
    # SCREEN POSITION
    # ========================================================

    def _target_screen(self):
        """
        Prefer the screen currently used by the user.

        QCursor position is used because the toast intentionally
        does not activate or depend on the PostGuard Main Window.
        """

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
        """
        Position the toast inside the available desktop area,
        leaving space for the Windows taskbar.
        """

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

    # ========================================================
    # SHOW
    # ========================================================

    def show_alert(
        self,
    ) -> None:
        """
        Display the toast without stealing focus.

        Intentionally no:
            raise_()
            activateWindow()

        because those operations can pull the user away from
        the application they are currently using.
        """

        self.adjustSize()

        self._move_to_bottom_right()

        self.show()

        self.auto_close_timer.start()

    # ========================================================
    # CLOSE
    # ========================================================

    def done(
        self,
        result: int,
    ) -> None:

        if self.auto_close_timer.isActive():

            self.auto_close_timer.stop()

        super().done(
            result
        )