"""Non-blocking PostGuard notification produced by Alert Policy."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.ui.theme import APP_QSS


RISK_TEXT = {
    "MODERATE": "ระดับความเสี่ยงปานกลาง",
    "HIGH": "ระดับความเสี่ยงสูง",
}

ALERT_TYPE_TEXT = {
    "FIRST": "การแจ้งเตือนครั้งแรก",
    "REPEAT": "การแจ้งเตือนซ้ำ",
    "ESCALATION": "ระดับความเสี่ยงเพิ่มขึ้น",
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
    """Show an Alert Policy decision without pausing monitoring."""

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

        self.setWindowTitle(
            "PostGuard - Posture Alert"
        )

        self.setWindowModality(
            Qt.WindowModality.NonModal
        )

        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            False,
        )

        self.setStyleSheet(APP_QSS)
        self.setFixedWidth(520)

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
            if isinstance(factor, str)
        ]

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            26,
            24,
            26,
            22,
        )

        layout.setSpacing(14)

        # ====================================================
        # HEADING
        # ====================================================

        heading_row = QHBoxLayout()

        icon = QLabel("!")
        icon.setProperty(
            "role",
            "warningIcon",
        )
        icon.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        icon.setFixedSize(48, 48)

        heading = QLabel("Posture Alert")
        heading.setProperty(
            "role",
            "title",
        )

        heading_row.addWidget(icon)
        heading_row.addWidget(
            heading,
            1,
        )

        # ====================================================
        # MESSAGE
        # ====================================================

        if normalized_risk == "HIGH":
            message_text = (
                "ตรวจพบท่าทางที่มีความเสี่ยงสูงต่อเนื่อง "
                "กรุณาปรับท่าทางและจัดตำแหน่งศีรษะ "
                "คอ และไหล่ให้เหมาะสม"
            )

        elif normalized_risk == "MODERATE":
            message_text = (
                "ตรวจพบท่าทางที่มีความเสี่ยงปานกลาง "
                "กรุณาปรับท่าทางกลับสู่ตำแหน่งที่เหมาะสม"
            )

        else:
            # Compatibility message for the old dialog caller.
            message_text = (
                "ตรวจพบท่าทางที่ควรปรับ "
                "กรุณาปรับศีรษะและลำตัวกลับสู่ท่าปกติ"
            )

        message = QLabel(message_text)
        message.setWordWrap(True)

        # ====================================================
        # DETAILS
        # ====================================================

        details = QFrame()
        details.setProperty(
            "card",
            True,
        )

        details_layout = QVBoxLayout(
            details
        )

        details_layout.setContentsMargins(
            18,
            14,
            18,
            14,
        )

        risk_text = (
            RISK_TEXT.get(
                normalized_risk,
                "N/A",
            )
        )

        alert_text = (
            ALERT_TYPE_TEXT.get(
                normalized_alert_type,
                "การแจ้งเตือน",
            )
        )

        self.risk_label = QLabel(
            f"Risk Level: {risk_text}"
        )

        self.alert_type_label = QLabel(
            f"ประเภท: {alert_text}"
        )

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
                "เอียงคอด้านขวา (+)"
                if direction > 0
                else "เอียงคอด้านซ้าย (-)"
            )
        else:
            factor_text = "ไม่ระบุ"

        # Keep this attribute name for compatibility with
        # older Desktop popup tests.
        self.direction_label = QLabel(
            f"ปัจจัยที่ตรวจพบ: {factor_text}"
        )

        self.duration_label = QLabel(
            "ระยะเวลาต่อเนื่องสูงสุด: "
            f"{max(0.0, float(duration_seconds)):.1f} วินาที"
        )

        source_label = QLabel(
            "การแจ้งเตือนนี้มาจาก PostGuard Alert Policy v1.0"
        )

        source_label.setProperty(
            "role",
            "muted",
        )

        details_layout.addWidget(
            self.risk_label
        )
        details_layout.addWidget(
            self.alert_type_label
        )
        details_layout.addWidget(
            self.direction_label
        )
        details_layout.addWidget(
            self.duration_label
        )
        details_layout.addWidget(
            source_label
        )

        # ====================================================
        # ACTION
        # ====================================================

        actions = QHBoxLayout()
        actions.addStretch()

        acknowledge = QPushButton(
            "รับทราบ"
        )

        acknowledge.setProperty(
            "variant",
            "primary",
        )

        acknowledge.clicked.connect(
            self.accept
        )

        actions.addWidget(
            acknowledge
        )

        layout.addLayout(
            heading_row
        )
        layout.addWidget(
            message
        )
        layout.addWidget(
            details
        )
        layout.addLayout(
            actions
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
            12_000
        )

        self.auto_close_timer.timeout.connect(
            self.accept
        )

    def show_alert(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.auto_close_timer.start()

    def done(self, result: int) -> None:
        self.auto_close_timer.stop()
        super().done(result)