"""Compact controls shown while the main PostGuard window is minimized."""

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import APP_QSS, polish


class MonitoringMiniWindow(QWidget):
    """Keep the active session controllable without duplicating its state."""

    restore_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()

    def __init__(self) -> None:
        # This must be a separate top-level window. An owned tool window is hidden
        # by Windows together with its minimized parent.
        super().__init__(None)
        self._allow_close = False

        self.setObjectName("appRoot")
        self.setWindowTitle("PostGuard Monitoring")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setFixedSize(410, 150)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(8)
        self.status_dot = QLabel("●")
        self.status_dot.setProperty("status", "running")
        self.title_label = QLabel("Monitoring is active")
        self.title_label.setProperty("role", "heading")
        heading_row.addWidget(self.status_dot)
        heading_row.addWidget(self.title_label)
        heading_row.addStretch()
        layout.addLayout(heading_row)

        self.session_label = QLabel("Session --")
        self.session_label.setProperty("role", "muted")
        layout.addWidget(self.session_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.restore_button = QPushButton("Open PostGuard")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setProperty("variant", "danger")
        self.restore_button.setToolTip("Return to the main PostGuard window")
        self.pause_button.setToolTip("Pause or resume this same session")
        self.stop_button.setToolTip("Stop the camera and finish this session")
        actions.addWidget(self.restore_button, 1)
        actions.addWidget(self.pause_button)
        actions.addWidget(self.stop_button)
        layout.addLayout(actions)

        self.restore_button.clicked.connect(self.restore_requested)
        self.pause_button.clicked.connect(self.pause_requested)
        self.stop_button.clicked.connect(self.stop_requested)

    def sync_state(
        self,
        session_id: int | None,
        *,
        paused: bool,
        stopping: bool,
        camera_available: bool,
    ) -> None:
        """Render the state owned by MonitoringPage."""

        if session_id is None:
            self.hide()
            return

        if stopping:
            title = "Ending and saving session…"
            status = "paused"
        elif paused:
            title = "Monitoring is paused"
            status = "paused"
        elif not camera_available:
            title = "Camera unavailable"
            status = "paused"
        else:
            title = "Monitoring is active"
            status = "running"

        self.title_label.setText(title)
        self.session_label.setText(f"Session {session_id} • PostGuard is minimized")
        self.status_dot.setProperty("status", status)
        polish(self.status_dot)
        self.pause_button.setText("Resume" if paused else "Pause")
        can_control = not stopping
        self.pause_button.setEnabled(can_control)
        self.stop_button.setEnabled(can_control)

    def show_near_screen_corner(self, screen=None) -> None:
        """Show the controller in the lower-right available desktop area."""

        screen = screen or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            margin = 20
            self.move(
                available.right() - self.width() - margin + 1,
                available.bottom() - self.height() - margin + 1,
            )
        self.show()
        self.raise_()

    def shutdown(self) -> None:
        """Close permanently when its owning application window exits."""

        self._allow_close = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.restore_requested.emit()
