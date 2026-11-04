from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MonitoringMiniController(QWidget):
    """
    Lightweight UI controller for an active PostGuard Monitoring session.

    IMPORTANT:
    This widget never owns or recreates any Monitoring resource.

    It does NOT create or reset:
    - cv2.VideoCapture
    - CameraMovementGuard
    - Personal Baseline
    - MediaPipe detectors
    - Blink detection
    - Risk / Temporal pipeline
    - Monitoring Session

    The preview is copied from MonitoringPage.preview_label through a provider.
    Therefore the Mini window displays the already-rendered Monitoring frame and
    never opens a second camera or runs a second detection pipeline.
    """

    pause_resume_requested = Signal()
    restore_requested = Signal()
    end_requested = Signal()
    hide_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._elapsed_seconds_provider = None
        self._is_paused_provider = None
        self._preview_pixmap_provider = None
        self._status_text_provider = None

        self.setWindowTitle("PostGuard Monitoring")

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setFixedWidth(380)

        self._build_ui()

        # 500 ms is UI-only refresh. Camera/detection still use MonitoringPage's
        # existing timer and are not controlled by this timer.
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(50)
        self.refresh_timer.timeout.connect(
            self.refresh_state
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            14,
            12,
            14,
            12,
        )
        root.setSpacing(9)

        title_row = QHBoxLayout()

        title = QLabel(
            "PostGuard Monitoring"
        )
        title.setStyleSheet(
            "font-size: 16px; "
            "font-weight: 600;"
        )

        title_row.addWidget(title)
        title_row.addStretch()

        self.status_label = QLabel(
            "RUNNING"
        )
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        title_row.addWidget(
            self.status_label
        )

        root.addLayout(title_row)

        # ----------------------------------------------------
        # Reused Monitoring preview
        # ----------------------------------------------------
        self.preview_label = QLabel(
            "Monitoring preview"
        )
        self.preview_label.setFixedSize(
            352,
            198,
        )
        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.preview_label.setStyleSheet(
            "background: #111; "
            "border-radius: 8px;"
        )

        root.addWidget(
            self.preview_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.elapsed_label = QLabel(
            "00:00:00"
        )
        self.elapsed_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.elapsed_label.setStyleSheet(
            "font-size: 22px; "
            "font-weight: 700;"
        )

        root.addWidget(
            self.elapsed_label
        )

        self.detail_status_label = QLabel(
            "Monitoring is running"
        )
        self.detail_status_label.setWordWrap(True)
        self.detail_status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        root.addWidget(
            self.detail_status_label
        )

        divider = QFrame()
        divider.setFrameShape(
            QFrame.Shape.HLine
        )

        root.addWidget(divider)

        first_row = QHBoxLayout()

        self.pause_button = QPushButton(
            "Pause"
        )

        self.restore_button = QPushButton(
            "Restore"
        )

        first_row.addWidget(
            self.pause_button
        )

        first_row.addWidget(
            self.restore_button
        )

        root.addLayout(
            first_row
        )

        second_row = QHBoxLayout()

        self.dock_button = QPushButton(
            "Dock"
        )

        self.end_button = QPushButton(
            "End Monitoring"
        )
        self.end_button.setProperty(
            "variant",
            "danger",
        )

        second_row.addWidget(
            self.dock_button
        )

        second_row.addWidget(
            self.end_button
        )

        root.addLayout(
            second_row
        )

        self.pause_button.clicked.connect(
            self.pause_resume_requested.emit
        )

        self.restore_button.clicked.connect(
            self.restore_requested.emit
        )

        self.dock_button.clicked.connect(
            self.dock_to_bottom_right
        )

        self.end_button.clicked.connect(
            self.end_requested.emit
        )

    def set_state_providers(
        self,
        elapsed_seconds_provider,
        is_paused_provider,
        preview_pixmap_provider=None,
        status_text_provider=None,
    ) -> None:
        """Attach read-only providers owned by MainWindow/MonitoringPage."""

        self._elapsed_seconds_provider = (
            elapsed_seconds_provider
        )

        self._is_paused_provider = (
            is_paused_provider
        )

        self._preview_pixmap_provider = (
            preview_pixmap_provider
        )

        self._status_text_provider = (
            status_text_provider
        )

    def show_controller(self) -> None:
        self.refresh_state()

        if not self.refresh_timer.isActive():
            self.refresh_timer.start()

        self.show()
        self.raise_()
        self.activateWindow()

        # Dock only after the widget has a final size/screen association.
        QTimer.singleShot(
            0,
            self.dock_to_bottom_right,
        )

    def hide_controller(self) -> None:
        self.hide()

        if self.refresh_timer.isActive():
            self.refresh_timer.stop()

    def dock_to_bottom_right(self) -> None:
        """Place the Mini controller at the working area's bottom-right."""

        screen = self.screen()

        if screen is None:
            screen = QApplication.primaryScreen()

        if screen is None:
            return

        geometry = screen.availableGeometry()

        margin = 16

        x = (
            geometry.right()
            - self.width()
            - margin
            + 1
        )

        y = (
            geometry.bottom()
            - self.height()
            - margin
            + 1
        )

        self.move(
            max(geometry.left(), x),
            max(geometry.top(), y),
        )

    def refresh_state(self) -> None:
        elapsed = 0

        if (
            self._elapsed_seconds_provider
            is not None
        ):
            try:
                elapsed = max(
                    0,
                    int(
                        self._elapsed_seconds_provider()
                    ),
                )

            except (
                TypeError,
                ValueError,
            ):
                elapsed = 0

        hours, remainder = divmod(
            elapsed,
            3600,
        )

        minutes, seconds = divmod(
            remainder,
            60,
        )

        self.elapsed_label.setText(
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

        paused = False

        if (
            self._is_paused_provider
            is not None
        ):
            try:
                paused = bool(
                    self._is_paused_provider()
                )

            except Exception:
                paused = False

        if paused:
            self.status_label.setText(
                "PAUSED"
            )

            self.pause_button.setText(
                "Resume"
            )

        else:
            self.status_label.setText(
                "RUNNING"
            )

            self.pause_button.setText(
                "Pause"
            )

        if (
            self._status_text_provider
            is not None
        ):
            try:
                status_text = str(
                    self._status_text_provider()
                    or ""
                ).strip()
            except Exception:
                status_text = ""

            if status_text:
                self.detail_status_label.setText(
                    status_text
                )

        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """
        Copy the pixmap already rendered by MonitoringPage.

        No frame capture and no detection work happens here.
        """

        if self._preview_pixmap_provider is None:
            return

        try:
            pixmap = (
                self._preview_pixmap_provider()
            )
        except Exception:
            return

        if (
            pixmap is None
            or not isinstance(pixmap, QPixmap)
            or pixmap.isNull()
        ):
            return

        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.preview_label.setPixmap(
            scaled
        )

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """
        X on the Mini UI means "hide to tray", never "end session".
        """

        event.ignore()

        self.hide_controller()

        self.hide_requested.emit()
