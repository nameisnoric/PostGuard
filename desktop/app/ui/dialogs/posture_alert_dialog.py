"""Non-blocking in-app notification for a newly created posture alert."""

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


class PostureAlertDialog(QDialog):
    """Show one visible warning without pausing the monitoring timer."""

    def __init__(self, direction: int, duration_seconds: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostGuard - Posture Alert")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setStyleSheet(APP_QSS)
        self.setFixedWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(14)

        heading_row = QHBoxLayout()
        icon = QLabel("!")
        icon.setProperty("role", "warningIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(48, 48)
        heading = QLabel("Posture Alert")
        heading.setProperty("role", "title")
        heading_row.addWidget(icon)
        heading_row.addWidget(heading, 1)

        message = QLabel(
            "ตรวจพบท่าทางเอียงคอด้านข้างต่อเนื่อง "
            "กรุณาปรับศีรษะและลำตัวกลับสู่ท่าปกติ"
        )
        message.setWordWrap(True)

        details = QFrame()
        details.setProperty("card", True)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(18, 14, 18, 14)
        direction_text = "ด้านขวา (+)" if direction > 0 else "ด้านซ้าย (-)"
        self.direction_label = QLabel(f"ทิศทาง: {direction_text}")
        self.duration_label = QLabel(
            f"ระยะเวลาต่อเนื่อง: {max(0.0, float(duration_seconds)):.1f} วินาที"
        )
        saved_label = QLabel("บันทึกเหตุการณ์นี้ใน Alert Events แล้ว")
        saved_label.setProperty("role", "muted")
        details_layout.addWidget(self.direction_label)
        details_layout.addWidget(self.duration_label)
        details_layout.addWidget(saved_label)

        actions = QHBoxLayout()
        actions.addStretch()
        acknowledge = QPushButton("รับทราบ")
        acknowledge.setProperty("variant", "primary")
        acknowledge.clicked.connect(self.accept)
        actions.addWidget(acknowledge)

        layout.addLayout(heading_row)
        layout.addWidget(message)
        layout.addWidget(details)
        layout.addLayout(actions)

        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.setInterval(12_000)
        self.auto_close_timer.timeout.connect(self.accept)

    def show_alert(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.auto_close_timer.start()

    def done(self, result: int) -> None:
        self.auto_close_timer.stop()
        super().done(result)
