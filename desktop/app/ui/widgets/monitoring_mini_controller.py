from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QGuiApplication,
    QMouseEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import APP_QSS


class MonitoringMiniController(QWidget):
    pause_resume_requested = Signal()
    restore_requested = Signal()
    end_requested = Signal()
    hide_requested = Signal()

    DEFAULT_WIDTH = 380
    DEFAULT_HEIGHT = 356

    EDGE_TAB_WIDTH = 74
    EDGE_TAB_HEIGHT = 40

    SNAP_THRESHOLD = 28
    SCREEN_MARGIN = 8

    REFRESH_INTERVAL_MS = 500

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            "PostGuard Monitoring"
        )

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setStyleSheet(
            APP_QSS
        )

        # =========================================================
        # DISPLAY-ONLY PROVIDERS
        # =========================================================

        self._elapsed_seconds_provider: (
            Callable[[], int | float]
            | None
        ) = None

        self._is_paused_provider: (
            Callable[[], bool]
            | None
        ) = None

        self._preview_pixmap_provider: (
            Callable[[], QPixmap | None]
            | None
        ) = None

        self._status_text_provider: (
            Callable[[], str]
            | None
        ) = None

        # =========================================================
        # DRAG / POSITION STATE
        # =========================================================

        self._drag_active = False

        self._drag_offset = QPoint()

        self._has_been_positioned = False

        self._expanded_position = QPoint()

        # =========================================================
        # EDGE MODE STATE
        # =========================================================

        self._edge_hidden = False

        self._edge_side = "left"

        # =========================================================
        # WINDOW SIZE
        # =========================================================

        self.setFixedSize(
            self.DEFAULT_WIDTH,
            self.DEFAULT_HEIGHT,
        )

        # =========================================================
        # ROOT LAYOUT
        # =========================================================

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            12,
            10,
            12,
            12,
        )

        root.setSpacing(
            8
        )

        # =========================================================
        # HEADER
        # =========================================================

        self.header = QFrame(
            self
        )

        self.header.setObjectName(
            "miniMonitoringHeader"
        )

        self.header.setCursor(
            Qt.CursorShape.SizeAllCursor
        )

        self.header.installEventFilter(
            self
        )

        header_layout = QHBoxLayout(
            self.header
        )

        header_layout.setContentsMargins(
            4,
            2,
            4,
            2,
        )

        header_layout.setSpacing(
            8
        )

        self.title_label = QLabel(
            "PostGuard"
        )

        self.title_label.setProperty(
            "role",
            "heading",
        )

        self.title_label.installEventFilter(
            self
        )

        self.elapsed_label = QLabel(
            "00:00:00"
        )

        self.elapsed_label.setProperty(
            "role",
            "muted",
        )

        self.elapsed_label.installEventFilter(
            self
        )

        self.edge_hide_button = QPushButton(
            "ซ่อนขอบ"
        )

        self.edge_hide_button.setToolTip(
            "ซ่อน Mini ไว้ที่ขอบจอ "
            "โดยการตรวจจับยังทำงานต่อ"
        )

        self.edge_hide_button.clicked.connect(
            self.hide_to_edge
        )

        header_layout.addWidget(
            self.title_label
        )

        header_layout.addStretch()

        header_layout.addWidget(
            self.elapsed_label
        )

        header_layout.addWidget(
            self.edge_hide_button
        )

        root.addWidget(
            self.header
        )

        # =========================================================
        # CONTENT
        # =========================================================

        self.content_container = QWidget(
            self
        )

        content_layout = QVBoxLayout(
            self.content_container
        )

        content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        content_layout.setSpacing(
            8
        )

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------

        self.status_label = QLabel(
            "Monitoring is not running"
        )

        self.status_label.setProperty(
            "role",
            "muted",
        )

        self.status_label.setWordWrap(
            True
        )

        content_layout.addWidget(
            self.status_label
        )

        # ---------------------------------------------------------
        # Preview
        # ---------------------------------------------------------

        self.preview_label = QLabel(
            "กำลังรอภาพจาก Monitoring"
        )

        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_label.setProperty(
            "preview",
            True,
        )

        self.preview_label.setFixedSize(
            352,
            198,
        )

        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        content_layout.addWidget(
            self.preview_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        # =========================================================
        # ACTION BUTTONS
        # =========================================================

        actions = QHBoxLayout()

        actions.setSpacing(
            6
        )

        self.pause_button = QPushButton(
            "Pause"
        )

        self.restore_button = QPushButton(
            "เปิด PostGuard"
        )

        self.end_button = QPushButton(
            "จบการตรวจจับ"
        )

        self.end_button.setProperty(
            "variant",
            "danger",
        )

        self.pause_button.clicked.connect(
            self.pause_resume_requested.emit
        )

        self.restore_button.clicked.connect(
            self.restore_requested.emit
        )

        self.end_button.clicked.connect(
            self.end_requested.emit
        )

        actions.addWidget(
            self.pause_button
        )

        actions.addWidget(
            self.restore_button
        )

        actions.addWidget(
            self.end_button
        )

        content_layout.addLayout(
            actions
        )

        root.addWidget(
            self.content_container
        )

        # =========================================================
        # EDGE TAB
        # =========================================================

        self.edge_tab_button = QPushButton(
            "PG  ›",
            self,
        )

        self.edge_tab_button.setToolTip(
            "แสดง Mini Monitoring"
        )

        self.edge_tab_button.clicked.connect(
            self.reveal_from_edge
        )

        self.edge_tab_button.hide()

        # =========================================================
        # UI REFRESH TIMER
        # =========================================================

        self.refresh_timer = QTimer(
            self
        )

        self.refresh_timer.setInterval(
            self.REFRESH_INTERVAL_MS
        )

        self.refresh_timer.timeout.connect(
            self.refresh_state
        )

    # =============================================================
    # STATE PROVIDERS
    # =============================================================

    def set_state_providers(
        self,
        *,
        elapsed_seconds_provider: Callable[
            [],
            int | float,
        ] | None = None,
        is_paused_provider: Callable[
            [],
            bool,
        ] | None = None,
        preview_pixmap_provider: Callable[
            [],
            QPixmap | None,
        ] | None = None,
        status_text_provider: Callable[
            [],
            str,
        ] | None = None,
    ) -> None:

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

        self.refresh_state()

    # =============================================================
    # SHOW CONTROLLER
    # =============================================================

    def show_controller(
        self,
    ) -> None:

        if self._edge_hidden:

            self._restore_full_layout()

        if not self._has_been_positioned:

            self._move_to_default_position()

            self._has_been_positioned = True

        else:

            self._move_clamped(
                self.pos()
            )

        self.refresh_state()

        self.show()

        self.raise_()

        self.activateWindow()

        if not self.refresh_timer.isActive():

            self.refresh_timer.start()

    # =============================================================
    # HIDE CONTROLLER
    # =============================================================

    def hide_controller(
        self,
    ) -> None:

        if self.refresh_timer.isActive():

            self.refresh_timer.stop()

        self.hide()

    # =============================================================
    # REFRESH STATE
    # =============================================================

    def refresh_state(
        self,
    ) -> None:

        elapsed_seconds = (
            self._read_elapsed_seconds()
        )

        self.elapsed_label.setText(
            self._format_elapsed_time(
                elapsed_seconds
            )
        )

        is_paused = (
            self._read_is_paused()
        )

        self.pause_button.setText(
            "Resume"
            if is_paused
            else "Pause"
        )

        self.status_label.setText(
            self._read_status_text()
        )

        pixmap = (
            self._read_preview_pixmap()
        )

        if (
            pixmap is None
            or pixmap.isNull()
        ):

            self.preview_label.setPixmap(
                QPixmap()
            )

            self.preview_label.setText(
                "กำลังรอภาพจาก Monitoring"
            )

        else:

            self.preview_label.setText(
                ""
            )

            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.preview_label.setPixmap(
                scaled
            )

    # =============================================================
    # PROVIDER HELPERS
    # =============================================================

    def _read_elapsed_seconds(
        self,
    ) -> int:

        if (
            self._elapsed_seconds_provider
            is None
        ):

            return 0

        try:

            value = float(
                self._elapsed_seconds_provider()
            )

        except (
            TypeError,
            ValueError,
            RuntimeError,
        ):

            return 0

        if value < 0:

            return 0

        return int(
            value
        )

    def _read_is_paused(
        self,
    ) -> bool:

        if (
            self._is_paused_provider
            is None
        ):

            return False

        try:

            return bool(
                self._is_paused_provider()
            )

        except RuntimeError:

            return False

    def _read_preview_pixmap(
        self,
    ) -> QPixmap | None:

        if (
            self._preview_pixmap_provider
            is None
        ):

            return None

        try:

            pixmap = (
                self._preview_pixmap_provider()
            )

        except RuntimeError:

            return None

        if not isinstance(
            pixmap,
            QPixmap,
        ):

            return None

        return pixmap

    def _read_status_text(
        self,
    ) -> str:

        if (
            self._status_text_provider
            is None
        ):

            return "Monitoring"

        try:

            text = str(
                self._status_text_provider()
                or ""
            ).strip()

        except RuntimeError:

            return "Monitoring"

        return (
            text
            or "Monitoring"
        )

    @staticmethod
    def _format_elapsed_time(
        total_seconds: int,
    ) -> str:

        safe_seconds = max(
            0,
            int(total_seconds),
        )

        hours, remainder = divmod(
            safe_seconds,
            3600,
        )

        minutes, seconds = divmod(
            remainder,
            60,
        )

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    # =============================================================
    # DRAGGING
    # =============================================================

    def eventFilter(
        self,
        watched,
        event,
    ) -> bool:

        # Qt may dispatch events while QWidget.__init__ is still running.
        # At that time header/title/elapsed widgets may not exist yet.
        header = getattr(
            self,
            "header",
            None,
        )

        title_label = getattr(
            self,
            "title_label",
            None,
        )

        elapsed_label = getattr(
            self,
            "elapsed_label",
            None,
        )

        drag_targets = tuple(
            widget
            for widget in (
                header,
                title_label,
                elapsed_label,
            )
            if widget is not None
        )

        if watched not in drag_targets:

            return super().eventFilter(
                watched,
                event,
            )

        if getattr(
            self,
            "_edge_hidden",
            False,
        ):

            return super().eventFilter(
                watched,
                event,
            )

        # ---------------------------------------------------------
        # Mouse Press
        # ---------------------------------------------------------

        if (
            event.type()
            ==
            QEvent.Type.MouseButtonPress
            and isinstance(
                event,
                QMouseEvent,
            )
            and event.button()
            ==
            Qt.MouseButton.LeftButton
        ):

            self._drag_active = True

            self._drag_offset = (
                event.globalPosition()
                .toPoint()
                -
                self.frameGeometry()
                .topLeft()
            )

            return True

        # ---------------------------------------------------------
        # Mouse Move
        # ---------------------------------------------------------

        if (
            event.type()
            ==
            QEvent.Type.MouseMove
            and isinstance(
                event,
                QMouseEvent,
            )
            and getattr(
                self,
                "_drag_active",
                False,
            )
            and (
                event.buttons()
                &
                Qt.MouseButton.LeftButton
            )
        ):

            target = (
                event.globalPosition()
                .toPoint()
                -
                self._drag_offset
            )

            self._move_clamped(
                target
            )

            return True

        # ---------------------------------------------------------
        # Mouse Release
        # ---------------------------------------------------------

        if (
            event.type()
            ==
            QEvent.Type.MouseButtonRelease
            and isinstance(
                event,
                QMouseEvent,
            )
            and event.button()
            ==
            Qt.MouseButton.LeftButton
            and getattr(
                self,
                "_drag_active",
                False,
            )
        ):

            self._drag_active = False

            self._snap_to_nearby_edge()

            self._expanded_position = (
                self.pos()
            )

            return True

        return super().eventFilter(
            watched,
            event,
        )
    # =============================================================
    # AVAILABLE SCREEN GEOMETRY
    # =============================================================

    def _available_geometry(
        self,
    ):

        center = (
            self.frameGeometry()
            .center()
        )

        screen = (
            QGuiApplication.screenAt(
                center
            )
        )

        if screen is None:

            screen = (
                self.screen()
                or
                QGuiApplication.primaryScreen()
            )

        if screen is None:

            raise RuntimeError(
                "No screen is available"
            )

        return (
            screen.availableGeometry()
        )

    # =============================================================
    # CLAMP POSITION
    # =============================================================

    def _clamped_position(
        self,
        point: QPoint,
    ) -> QPoint:

        geometry = (
            self._available_geometry()
        )

        margin = (
            self.SCREEN_MARGIN
        )

        min_x = (
            geometry.left()
            +
            margin
        )

        min_y = (
            geometry.top()
            +
            margin
        )

        max_x = (
            geometry.right()
            -
            self.width()
            -
            margin
            +
            1
        )

        max_y = (
            geometry.bottom()
            -
            self.height()
            -
            margin
            +
            1
        )

        if max_x < min_x:

            max_x = min_x

        if max_y < min_y:

            max_y = min_y

        return QPoint(
            max(
                min_x,
                min(
                    point.x(),
                    max_x,
                ),
            ),
            max(
                min_y,
                min(
                    point.y(),
                    max_y,
                ),
            ),
        )

    def _move_clamped(
        self,
        point: QPoint,
    ) -> None:

        self.move(
            self._clamped_position(
                point
            )
        )

    # =============================================================
    # DEFAULT POSITION
    # =============================================================

    def _move_to_default_position(
        self,
    ) -> None:

        geometry = (
            self._available_geometry()
        )

        target = QPoint(
            geometry.left()
            +
            self.SCREEN_MARGIN,

            geometry.bottom()
            -
            self.height()
            -
            self.SCREEN_MARGIN
            +
            1,
        )

        self._move_clamped(
            target
        )

        self._expanded_position = (
            self.pos()
        )

    # =============================================================
    # SNAP
    # =============================================================

    def _snap_to_nearby_edge(
        self,
    ) -> None:

        if self._edge_hidden:

            return

        geometry = (
            self._available_geometry()
        )

        margin = (
            self.SCREEN_MARGIN
        )

        left_x = (
            geometry.left()
            +
            margin
        )

        right_x = (
            geometry.right()
            -
            self.width()
            -
            margin
            +
            1
        )

        top_y = (
            geometry.top()
            +
            margin
        )

        bottom_y = (
            geometry.bottom()
            -
            self.height()
            -
            margin
            +
            1
        )

        x = (
            self.x()
        )

        y = (
            self.y()
        )

        if (
            abs(
                x
                -
                left_x
            )
            <=
            self.SNAP_THRESHOLD
        ):

            x = left_x

        elif (
            abs(
                x
                -
                right_x
            )
            <=
            self.SNAP_THRESHOLD
        ):

            x = right_x

        if (
            abs(
                y
                -
                top_y
            )
            <=
            self.SNAP_THRESHOLD
        ):

            y = top_y

        elif (
            abs(
                y
                -
                bottom_y
            )
            <=
            self.SNAP_THRESHOLD
        ):

            y = bottom_y

        self._move_clamped(
            QPoint(
                x,
                y,
            )
        )

    # =============================================================
    # HIDE TO EDGE
    # =============================================================

    def hide_to_edge(
        self,
    ) -> None:

        if self._edge_hidden:

            return

        self._expanded_position = (
            self.pos()
        )

        self._edge_side = (
            self._nearest_edge()
        )

        self._edge_hidden = True

        # Hide full Mini content
        self.header.hide()

        self.content_container.hide()

        # Shrink window to edge tab size
        self.setFixedSize(
            self.EDGE_TAB_WIDTH,
            self.EDGE_TAB_HEIGHT,
        )

        self.edge_tab_button.setGeometry(
            0,
            0,
            self.EDGE_TAB_WIDTH,
            self.EDGE_TAB_HEIGHT,
        )

        self.edge_tab_button.setText(
            self._edge_tab_text(
                self._edge_side
            )
        )

        self.edge_tab_button.show()

        self.edge_tab_button.raise_()

        self.move(
            self._edge_tab_position(
                self._edge_side
            )
        )

    # =============================================================
    # REVEAL FROM EDGE
    # =============================================================

    def reveal_from_edge(
        self,
    ) -> None:

        if not self._edge_hidden:

            return

        self._restore_full_layout()

        self._move_clamped(
            self._expanded_position
        )

        self._snap_to_nearby_edge()

        self.raise_()

        self.activateWindow()

    # =============================================================
    # RESTORE FULL LAYOUT
    # =============================================================

    def _restore_full_layout(
        self,
    ) -> None:

        self._edge_hidden = False

        self.edge_tab_button.hide()

        self.setFixedSize(
            self.DEFAULT_WIDTH,
            self.DEFAULT_HEIGHT,
        )

        self.header.show()

        self.content_container.show()

    # =============================================================
    # FIND NEAREST EDGE
    # =============================================================

    def _nearest_edge(
        self,
    ) -> str:

        geometry = (
            self._available_geometry()
        )

        center = (
            self.frameGeometry()
            .center()
        )

        distances = {
            "left":
                abs(
                    center.x()
                    -
                    geometry.left()
                ),

            "right":
                abs(
                    geometry.right()
                    -
                    center.x()
                ),

            "top":
                abs(
                    center.y()
                    -
                    geometry.top()
                ),

            "bottom":
                abs(
                    geometry.bottom()
                    -
                    center.y()
                ),
        }

        return min(
            distances,
            key=distances.get,
        )

    # =============================================================
    # EDGE TAB POSITION
    # =============================================================

    def _edge_tab_position(
        self,
        side: str,
    ) -> QPoint:

        geometry = (
            self._available_geometry()
        )

        margin = (
            self.SCREEN_MARGIN
        )

        previous_center_x = (
            self._expanded_position.x()
            +
            self.DEFAULT_WIDTH
            //
            2
        )

        previous_center_y = (
            self._expanded_position.y()
            +
            self.DEFAULT_HEIGHT
            //
            2
        )

        if side == "left":

            x = (
                geometry.left()
                +
                margin
            )

            y = (
                previous_center_y
                -
                self.EDGE_TAB_HEIGHT
                //
                2
            )

        elif side == "right":

            x = (
                geometry.right()
                -
                self.EDGE_TAB_WIDTH
                -
                margin
                +
                1
            )

            y = (
                previous_center_y
                -
                self.EDGE_TAB_HEIGHT
                //
                2
            )

        elif side == "top":

            x = (
                previous_center_x
                -
                self.EDGE_TAB_WIDTH
                //
                2
            )

            y = (
                geometry.top()
                +
                margin
            )

        else:

            x = (
                previous_center_x
                -
                self.EDGE_TAB_WIDTH
                //
                2
            )

            y = (
                geometry.bottom()
                -
                self.EDGE_TAB_HEIGHT
                -
                margin
                +
                1
            )

        return self._clamped_position(
            QPoint(
                x,
                y,
            )
        )

    # =============================================================
    # EDGE TAB TEXT
    # =============================================================

    @staticmethod
    def _edge_tab_text(
        side: str,
    ) -> str:

        if side == "left":

            return "PG  ›"

        if side == "right":

            return "‹  PG"

        if side == "top":

            return "PG  ↓"

        return "PG  ↑"

    # =============================================================
    # CLOSE EVENT
    # =============================================================

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:

        # X ของ Mini ต้องไม่จบ Monitoring
        event.ignore()

        self.hide_requested.emit()