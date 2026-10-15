import requests

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QStackedWidget,
    QMessageBox,
    QMenu,
    QToolButton,
)

from app.core.token_store import TokenStore

from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.camera_setup_page import CameraSetupPage
from app.ui.pages.camera_preview_page import CameraPreviewPage
from app.ui.pages.baseline_page import BaselinePage
from app.ui.pages.monitoring_page import MonitoringPage
from app.ui.pages.session_summary_page import SessionSummaryPage
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.profile_page import ProfilePage
from app.ui.theme import APP_QSS, polish, set_centered_window

from app.services.api_client import APIClient
from app.services.session_recovery_service import (
    find_unclosed_sessions,
    interrupt_previous_session,
)

class MainWindow(QMainWindow):

    def __init__(self, user_data: dict):
        super().__init__()

        self.user_data = user_data
        self._exit_ready = False
        self._exit_in_progress = False
        self._recovery_in_progress = False

        self.setWindowTitle("PostGuard")
        set_centered_window(self, 1280, 800, 980, 680)
        self.setStyleSheet(APP_QSS)

        central_widget = QWidget()
        central_widget.setObjectName("appRoot")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        navigation = QWidget()
        navigation.setObjectName("topNavigation")
        navigation.setFixedHeight(72)
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(32, 0, 24, 0)
        navigation_layout.setSpacing(6)

        app_title = QLabel("PostGuard")
        app_title.setObjectName("brandLabel")
        navigation_layout.addWidget(app_title)
        navigation_layout.addStretch()

        self.monitor_button = self._nav_button("Monitoring")
        self.dashboard_button = self._nav_button("Dashboard")
        self.history_button = self._nav_button("History")
        navigation_layout.addWidget(self.monitor_button)
        navigation_layout.addWidget(self.dashboard_button)
        navigation_layout.addWidget(self.history_button)

        self.account_button = QToolButton()
        self.account_button.setText(self._account_initials())
        self.account_button.setProperty("account", True)
        self.account_button.setProperty("accountActive", False)
        self.account_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        account_menu = QMenu(self.account_button)
        self.profile_action = account_menu.addAction("Profile")
        self.settings_action = account_menu.addAction("Settings (coming soon)")
        self.settings_action.setEnabled(False)
        account_menu.addSeparator()
        self.logout_action = account_menu.addAction("Log out")
        self.account_button.setMenu(account_menu)
        navigation_layout.addWidget(self.account_button)
        main_layout.addWidget(navigation)

        self.session_bar = QFrame()
        self.session_bar.setProperty("variant", "sessionBar")
        session_layout = QHBoxLayout(self.session_bar)
        session_layout.setContentsMargins(32, 8, 24, 8)
        self.monitoring_status_label = QLabel("Monitoring: Not started")
        self.monitoring_status_label.setProperty("status", "idle")
        self.global_pause_button = QPushButton("Pause Monitoring")
        self.global_stop_button = QPushButton("Stop Monitoring")
        self.global_stop_button.setProperty("variant", "danger")
        session_layout.addWidget(self.monitoring_status_label, 1)
        session_layout.addWidget(self.global_pause_button)
        session_layout.addWidget(self.global_stop_button)
        main_layout.addWidget(self.session_bar)

        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")

        self.dashboard_page = DashboardPage(
            self.user_data
        )
        self.dashboard_page.monitor_requested.connect(self.show_monitor)
        self.dashboard_page.history_requested.connect(self.show_history)

        self.camera_setup_page = (
            CameraSetupPage()
        )

        self.camera_preview_page = (
            CameraPreviewPage()
        )

        self.baseline_page = (
            BaselinePage()
        )

        self.monitoring_page = (
            MonitoringPage()
        )

        # NEW: Session Summary
        self.session_summary_page = (
            SessionSummaryPage()
        )

        self.history_page = (
            HistoryPage()
        )

        self.profile_page = ProfilePage(self.user_data)
        self._update_account_avatar()

        # ========================================
        # 4. Register Pages
        # ========================================

        self.pages.addWidget(
            self.dashboard_page
        )

        self.pages.addWidget(
            self.camera_setup_page
        )

        self.pages.addWidget(
            self.camera_preview_page
        )

        self.pages.addWidget(
            self.baseline_page
        )

        self.pages.addWidget(
            self.monitoring_page
        )

        # NEW: Register Session Summary
        self.pages.addWidget(
            self.session_summary_page
        )

        self.pages.addWidget(
            self.history_page
        )

        self.pages.addWidget(self.profile_page)

        main_layout.addWidget(self.pages, 1)

        self.dashboard_button.clicked.connect(
            self.show_dashboard
        )

        self.monitor_button.clicked.connect(
            self.show_monitor
        )

        self.history_button.clicked.connect(
            self.show_history
        )

        self.profile_action.triggered.connect(self.show_profile)
        self.logout_action.triggered.connect(self.logout)
        self.profile_page.profile_updated.connect(self.update_profile)
        self.profile_page.account_deletion_requested.connect(self.delete_account)
        self.pages.currentChanged.connect(self._sync_navigation)

        # ========================================
        # 7. Camera Page Events
        # ========================================

        # Camera Setup -> Camera Preview
        self.camera_setup_page.camera_selected.connect(
            self.show_camera_preview
        )

        # Camera Preview -> Camera Setup
        self.camera_preview_page.back_requested.connect(
            self.show_camera_setup
        )

        # Camera Preview -> Personal Baseline
        self.camera_preview_page.continue_requested.connect(
            self.handle_preview_continue
        )

        # Personal Baseline -> Camera Preview
        self.baseline_page.back_requested.connect(
            self.show_camera_preview
        )

        # ========================================
        # 8. Monitoring Events
        # ========================================

        # Personal Baseline -> Monitoring
        self.baseline_page.monitoring_requested.connect(
            self.show_monitoring_page
        )

        # Monitoring -> Session Summary
        self.monitoring_page.stop_requested.connect(
            self.show_session_summary
        )
        self.monitoring_page.state_changed.connect(self.update_monitoring_controls)
        self.global_pause_button.clicked.connect(self.monitoring_page.handle_pause_resume)
        self.global_stop_button.clicked.connect(self.monitoring_page.handle_stop)
        self.update_monitoring_controls()

        # Session Summary -> Dashboard
        self.session_summary_page.back_requested.connect(
            self.show_dashboard
        )

        # ========================================
        # 9. Default Page
        # ========================================

        self.pages.setCurrentWidget(
            self.dashboard_page
        )

    @staticmethod
    def _nav_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("nav", True)
        button.setProperty("navActive", False)
        return button

    def _account_initials(self) -> str:
        name = self.user_data.get("full_name") or self.user_data.get("username") or "U"
        words = str(name).split()
        return "".join(word[0].upper() for word in words[:2]) or "U"

    def _sync_navigation(self, _index: int = 0) -> None:
        current = self.pages.currentWidget()
        monitor_pages = {
            self.camera_setup_page,
            self.camera_preview_page,
            self.baseline_page,
            self.monitoring_page,
        }
        active = self.monitor_button if current in monitor_pages else (
            self.dashboard_button if current is self.dashboard_page else (
                self.history_button if current is self.history_page else None
            )
        )
        for button in (
            self.monitor_button,
            self.dashboard_button,
            self.history_button,
        ):
            button.setProperty("navActive", button is active)
            polish(button)
        self.account_button.setProperty(
            "accountActive", current is self.profile_page
        )
        polish(self.account_button)

    # ============================================
    # Dashboard
    # ============================================

    def show_dashboard(self):

        self.camera_preview_page.stop_preview()

        self.pages.setCurrentWidget(
            self.dashboard_page
        )
        self.dashboard_page.refresh()

    # ============================================
    # Monitor Menu
    # ============================================

    def show_monitor(self):

        if self.monitoring_page.session_id is not None:
            self.pages.setCurrentWidget(self.monitoring_page)
            return
        if self._show_unsaved_summary():
            return
        if not self.check_previous_sessions():
            return

        self.camera_preview_page.stop_preview()

        self.pages.setCurrentWidget(
            self.camera_setup_page
        )

    # ============================================
    # History
    # ============================================

    def show_history(self):

        # Stop camera preview before switching pages
        self.camera_preview_page.stop_preview()

        # Display History page
        self.pages.setCurrentWidget(
            self.history_page
        )

        # Load saved sessions from PostgreSQL
        self.history_page.load_sessions()

    def show_profile(self):
        self.camera_preview_page.stop_preview()
        self.profile_page.reset_form()
        self.pages.setCurrentWidget(self.profile_page)

    def update_profile(self, updated: dict) -> None:
        self.user_data.update(updated)
        self._update_account_avatar()

    def delete_account(self) -> None:
        """Finish local work, request deletion, then return to login."""
        if not self._finish_before_exit():
            self.profile_page.status_label.setText(
                "Finish and save the current monitoring session before deleting the account."
            )
            return

        self.profile_page.delete_account_button.setEnabled(False)
        self.profile_page.status_label.setText("Requesting account deletion...")
        try:
            response = APIClient.request_account_deletion()
        except requests.RequestException:
            self.profile_page.delete_account_button.setEnabled(True)
            self.profile_page.status_label.setText(
                "Cannot request account deletion. Check your connection."
            )
            return
        if not response.ok:
            self.profile_page.delete_account_button.setEnabled(True)
            try:
                detail = response.json().get(
                    "detail", "Account deletion could not be requested."
                )
            except (ValueError, AttributeError):
                detail = "Account deletion could not be requested."
            self.profile_page.status_label.setText(str(detail))
            return

        try:
            scheduled_for = response.json().get("deletion_scheduled_for")
        except (ValueError, AttributeError):
            scheduled_for = None
        QMessageBox.information(
            self,
            "Account deletion requested",
            "Your account is disabled and scheduled for permanent deletion in 14 days. "
            "Sign in again before the deadline to recover it."
            + (f"\n\nDeletion deadline: {scheduled_for}" if scheduled_for else ""),
        )
        TokenStore.clear_token()
        self._exit_ready = True
        self.hide()
        from app.ui.login_window import LoginWindow

        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

    def _update_account_avatar(self) -> None:
        pixmap = self.profile_page.avatar_label.pixmap()
        if pixmap is not None and not pixmap.isNull():
            self.account_button.setText("")
            self.account_button.setIcon(QIcon(pixmap))
            self.account_button.setIconSize(QSize(32, 32))
            return
        self.account_button.setIcon(QIcon())
        self.account_button.setText(self._account_initials())

    # ============================================
    # Logout
    # ============================================

    def logout(self):

        if not self._finish_before_exit():
            return
        self._exit_ready = True

        # Stop Camera Preview
        self.camera_preview_page.stop_preview()

        # Clear Authentication Token
        TokenStore.clear_token()

        self.hide()

        from app.ui.login_window import LoginWindow

        self.login_window = LoginWindow()
        self.login_window.show()

        self.close()

    def update_monitoring_controls(self):
        monitor = self.monitoring_page
        active = monitor.session_id is not None
        if monitor.is_stopping:
            status = "Monitoring: Ending and saving..."
        elif active:
            state = "Paused" if monitor.is_paused else "Running (camera on)"
            if monitor.capture is None:
                state = "Stopped locally; session end pending"
            status = f"Session {monitor.session_id}: {state}"
        else:
            status = "Monitoring: Not running"
        self.monitoring_status_label.setText(status)
        self.monitoring_status_label.setProperty(
            "status",
            "paused" if active and monitor.is_paused else (
                "running" if active else "idle"
            ),
        )
        polish(self.monitoring_status_label)
        self.global_pause_button.setText(
            "Resume Monitoring" if monitor.is_paused else "Pause Monitoring"
        )
        can_control = active and not monitor.is_stopping
        self.session_bar.setVisible(active or monitor.is_stopping)
        self.global_pause_button.setEnabled(can_control and monitor.capture is not None)
        self.global_stop_button.setEnabled(can_control)
        self.dashboard_page.set_monitoring_state(
            monitor.session_id, monitor.is_paused, monitor.is_stopping,
            monitor.capture is not None,
        )

    def check_previous_sessions(self) -> bool:
        if self.monitoring_page.session_id is not None:
            return True
        if self._recovery_in_progress:
            return False
        self._recovery_in_progress = True
        try:
            sessions = find_unclosed_sessions()
            for session in sessions:
                answer = QMessageBox.question(
                    self, "Unclosed Session",
                    f"Session {session['session_id']} is still {session['status']}.\n"
                    "It may be running on another device.\n\n"
                    "Mark it as interrupted so you can start a new session?\n"
                    "Existing records will be kept. The actual end time and lost "
                    "detection statistics cannot be recovered; no summary will be fabricated.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    self.monitoring_status_label.setText("Previous session unresolved; Monitor to retry")
                    return False
                interrupt_previous_session(session["session_id"])
            self.update_monitoring_controls()
            return True
        except (requests.RequestException, RuntimeError, ValueError) as error:
            self.monitoring_status_label.setText("Session check failed; Monitor to retry")
            QMessageBox.warning(self, "Session Recovery", str(error))
            return False
        finally:
            self._recovery_in_progress = False

    def _show_unsaved_summary(self) -> bool:
        summary = self.session_summary_page.current_summary
        if summary and summary.get("summary_save_status") not in ("SAVED", "ALREADY_EXISTS"):
            self.pages.setCurrentWidget(self.session_summary_page)
            QMessageBox.warning(
                self, "Unsaved Summary",
                "Please retry saving this summary before starting another session or exiting.",
            )
            return True
        return False

    def _finish_before_exit(self) -> bool:
        """Keep credentials and statistics until both end and save succeed."""
        if self._exit_ready:
            return True
        if self._exit_in_progress or self.monitoring_page.is_stopping:
            return False
        self._exit_in_progress = True
        try:
            monitor = self.monitoring_page
            if monitor.session_id is not None:
                if monitor.session_started_monotonic is not None:
                    monitor.handle_stop()
                else:
                    monitor.stop_monitoring()
                if monitor.session_id is not None:
                    self.pages.setCurrentWidget(monitor)
                    return False
            if self._show_unsaved_summary():
                return False
            self.camera_preview_page.stop_preview()
            self.baseline_page.stop_camera_preview()
            return True
        finally:
            self._exit_in_progress = False

    def closeEvent(self, event):
        if not self._finish_before_exit():
            event.ignore()
            return
        self._exit_ready = True
        TokenStore.clear_token()
        event.accept()

    # ============================================
    # Camera Preview
    # ============================================

    def show_camera_preview(
        self,
        camera: dict
    ):

        self.camera_preview_page.start_preview(
            camera
        )

        self.pages.setCurrentWidget(
            self.camera_preview_page
        )

    # ============================================
    # Camera Setup
    # ============================================

    def show_camera_setup(self):

        self.camera_preview_page.stop_preview()

        self.pages.setCurrentWidget(
            self.camera_setup_page
        )

    # ============================================
    # Camera Registration
    # ============================================

    def handle_preview_continue(
        self,
        camera: dict
    ) -> None:

        try:

            # 1. Get Camera Device Index
            device_index = camera.get(
                "device_index"
            )

            if device_index is None:
                raise ValueError(
                    "Camera device index is missing."
                )

            # Temporary Device Identifier
            device_id = (
                f"opencv-index:{device_index}"
            )

            # 2. Load Registered Cameras
            response = APIClient.get_cameras()

            if not response.ok:
                raise RuntimeError(
                    f"Cannot load cameras: "
                    f"HTTP {response.status_code}"
                )

            saved_cameras = response.json()

            if not isinstance(saved_cameras, list):
                raise ValueError(
                    "Invalid camera list from server."
                )

            # 3. Find Existing Camera
            registered_camera = next(
                (
                    item
                    for item in saved_cameras
                    if item.get("device_id") == device_id
                ),
                None
            )

            # 4. Register New Camera
            if registered_camera is None:

                print(
                    "REGISTERING CAMERA:",
                    device_id
                )

                response = APIClient.create_camera(
                    device_id=device_id,
                    camera_name=camera.get(
                        "camera_name",
                        f"Camera {device_index}"
                    ),
                    resolution_width=camera[
                        "resolution_width"
                    ],
                    resolution_height=camera[
                        "resolution_height"
                    ]
                )

                if not response.ok:
                    raise RuntimeError(
                        f"Camera registration failed: "
                        f"HTTP {response.status_code}"
                    )

                registered_camera = response.json()

                print("NEW CAMERA REGISTERED")

            else:

                print("USING EXISTING CAMERA")

            # 5. Get Camera ID from Database
            camera_id = registered_camera.get(
                "camera_id"
            )

            if (
                not isinstance(camera_id, int)
                or isinstance(camera_id, bool)
                or camera_id <= 0
            ):
                raise ValueError(
                    "Invalid camera_id from server."
                )

            # 6. Prepare Camera Data
            camera_data = camera.copy()

            camera_data["camera_id"] = camera_id
            camera_data["device_id"] = device_id

            print("CAMERA ID:", camera_id)
            print("BASELINE CAMERA:", camera_data)

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
            TypeError
        ) as error:

            QMessageBox.warning(
                self,
                "Camera Registration Error",
                str(error)
            )

            # Reopen Preview for Retry
            self.camera_preview_page.start_preview(
                camera
            )

            return

        # 7. Send Camera Data to Baseline
        self.baseline_page.set_camera(
            camera_data
        )

        # 8. Open Personal Baseline Page
        self.pages.setCurrentWidget(
            self.baseline_page
        )

    # ============================================
    # Real-time Monitoring
    # ============================================

    def show_monitoring_page(
        self,
        camera: dict,
        baseline_id: int
    ) -> None:

        if self.monitoring_page.session_id is not None:
            self.pages.setCurrentWidget(self.monitoring_page)
            return
        if self._show_unsaved_summary():
            return
        if not self.check_previous_sessions():
            return

        # Switch to Monitoring Page
        self.pages.setCurrentWidget(
            self.monitoring_page
        )

        # Start Monitoring with Camera
        # and Saved Personal Baseline
        started = self.monitoring_page.start_monitoring(
            camera,
            baseline_id
        )

        # If Monitoring Cannot Start
        if not started:

            self.pages.setCurrentWidget(
                self.camera_setup_page
            )

    # ============================================
    # Session Summary
    # ============================================

    def show_session_summary(
        self,
        summary: dict
    ) -> None:

        # Display Session Information
        self.session_summary_page.set_summary(
            summary
        )

        # Switch Monitoring -> Session Summary
        self.pages.setCurrentWidget(
            self.session_summary_page
        )
