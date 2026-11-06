import time

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
    QSystemTrayIcon,
)

from app.core.token_store import TokenStore

from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.camera_setup_page import CameraSetupPage
from app.ui.pages.camera_preview_page import CameraPreviewPage
from app.ui.pages.camera_calibration_page import CameraCalibrationPage
from app.ui.pages.baseline_page import BaselinePage
from app.ui.pages.monitoring_page import MonitoringPage
from app.ui.pages.session_summary_page import SessionSummaryPage
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.profile_page import ProfilePage
from app.ui.pages.settings_page import SettingsPage
from app.ui.theme import APP_QSS, polish, set_centered_window
from app.ui.components import StatusBadge
from app.ui.dialogs.privacy_notice_dialog import PrivacyNoticeDialog
from app.ui.widgets.monitoring_mini_controller import MonitoringMiniController

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

        # ============================================================
        # MINI / TRAY DISPLAY STATE
        # ============================================================
        # These values are UI-only. They do not own Monitoring state.
        self._mini_clock_session_id = None
        self._mini_total_paused_seconds = 0.0
        self._mini_pause_started_monotonic = None
        self._mini_last_paused_state = False

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

        self.monitor_button = self._nav_button("การตรวจจับ")
        self.dashboard_button = self._nav_button("ภาพรวม")
        self.history_button = self._nav_button("ประวัติ")
        navigation_layout.addWidget(self.monitor_button)
        navigation_layout.addWidget(self.dashboard_button)
        navigation_layout.addWidget(self.history_button)

        self.account_button = QToolButton()
        self.account_button.setText(self._account_initials())
        self.account_button.setProperty("account", True)
        self.account_button.setProperty("accountActive", False)
        self.account_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        account_menu = QMenu(self.account_button)
        self.profile_action = account_menu.addAction("โปรไฟล์")
        self.settings_action = account_menu.addAction("การตั้งค่า")
        account_menu.addSeparator()
        self.logout_action = account_menu.addAction("ออกจากระบบ")
        self.account_button.setMenu(account_menu)
        navigation_layout.addWidget(self.account_button)
        main_layout.addWidget(navigation)

        # ============================================================
        # ACTIVE SESSION STATUS
        # ============================================================
        #
        # This bar displays status only.
        #
        # Session actions live in MonitoringPage under the camera so
        # the user has one control location and one set of buttons.
        # ============================================================

        self.session_bar = QFrame()

        self.session_bar.setProperty(
            "variant",
            "sessionBar",
        )

        session_layout = QHBoxLayout(
            self.session_bar
        )

        session_layout.setContentsMargins(
            32,
            8,
            24,
            8,
        )

        self.monitoring_status_label = StatusBadge(
            "ยังไม่เริ่ม",
            tone="neutral",
        )

        session_layout.addWidget(
            self.monitoring_status_label
        )

        session_layout.addStretch()

        main_layout.addWidget(
            self.session_bar
        )

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

        self.camera_calibration_page = CameraCalibrationPage()

        self.baseline_page = (
            BaselinePage()
        )

        self.monitoring_page = (
            MonitoringPage()
        )

        # ============================================================
        # MONITORING CONTROL COMPATIBILITY REFERENCES
        # ============================================================
        #
        # These are references to the SAME visible buttons inside
        # MonitoringPage.
        #
        # They do not create another button set in MainWindow.
        #
        # Existing workflow tests and legacy code may still access
        # these names.
        # ============================================================

        self.global_pause_button = (
            self.monitoring_page.pause_button
        )

        self.global_mini_button = (
            self.monitoring_page.mini_button
        )

        self.global_stop_button = (
            self.monitoring_page.stop_button
        )

        # ============================================================
        # MINI MONITORING CONTROLLER
        # ============================================================

        self.mini_controller = MonitoringMiniController()

        self.mini_controller.set_state_providers(
            elapsed_seconds_provider=self._monitoring_elapsed_seconds,
            is_paused_provider=lambda: self.monitoring_page.is_paused,
            preview_pixmap_provider=self._mini_preview_pixmap,
            status_text_provider=self._mini_status_text,
        )

        self.mini_controller.pause_resume_requested.connect(
            self._mini_pause_resume
        )

        self.mini_controller.restore_requested.connect(
            self._restore_from_mini
        )

        self.mini_controller.end_requested.connect(
            self._end_from_mini
        )

        self.mini_controller.hide_requested.connect(
            self._mini_hidden
        )

        self._setup_monitoring_tray()

        # NEW: Session Summary
        self.session_summary_page = (
            SessionSummaryPage()
        )

        self.history_page = (
            HistoryPage()
        )

        self.profile_page = ProfilePage(self.user_data)
        self.settings_page = SettingsPage(self.monitoring_page.sound_player)
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

        self.pages.addWidget(self.camera_calibration_page)

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
        self.pages.addWidget(self.settings_page)

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
        self.settings_action.triggered.connect(self.show_settings)
        self.logout_action.triggered.connect(self.logout)
        self.profile_page.profile_updated.connect(self.update_profile)
        self.settings_page.account_deletion_requested.connect(self.delete_account)
        self.settings_page.settings_updated.connect(
            self.monitoring_page.apply_notification_settings
        )
        self.settings_page.privacy_consent_changed.connect(
            self._privacy_consent_changed
        )
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

        # Camera Preview -> Camera Preparation
        self.camera_preview_page.continue_requested.connect(
            self.handle_preview_continue
        )

        self.camera_calibration_page.back_requested.connect(
            self.show_camera_preview
        )
        self.camera_calibration_page.continue_requested.connect(
            self.handle_camera_calibration_continue
        )

        # Personal Baseline -> Camera Preparation
        self.baseline_page.back_requested.connect(
            self.show_camera_calibration
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
        self.monitoring_page.state_changed.connect(
            self._on_monitoring_state_changed
        )

        self.monitoring_page.mini_requested.connect(
            self.show_mini_monitoring
        )
        self.update_monitoring_controls()
        self.settings_page.load_settings()
        self.settings_page.load_privacy_consent()

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
            self.camera_calibration_page,
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
            "accountActive", current in (self.profile_page, self.settings_page)
        )
        polish(self.account_button)

    # ============================================
    # Dashboard
    # ============================================

    def show_dashboard(self):

        self.camera_preview_page.stop_preview()
        self.camera_calibration_page.stop_camera()

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
        if not self._ensure_privacy_consent():
            return
        if not self.check_previous_sessions():
            return

        self.camera_preview_page.stop_preview()
        self.camera_calibration_page.stop_camera()

        self.pages.setCurrentWidget(
            self.camera_setup_page
        )

    # ============================================
    # History
    # ============================================

    def show_history(self):

        # Stop camera preview before switching pages
        self.camera_preview_page.stop_preview()
        self.camera_calibration_page.stop_camera()

        # Display History page
        self.pages.setCurrentWidget(
            self.history_page
        )

        # Load saved sessions from PostgreSQL
        self.history_page.load_sessions()

    def show_profile(self):
        self.camera_preview_page.stop_preview()
        self.camera_calibration_page.stop_camera()
        self.profile_page.reset_form()
        self.pages.setCurrentWidget(self.profile_page)

    def show_settings(self):
        self.camera_preview_page.stop_preview()
        self.camera_calibration_page.stop_camera()
        self.settings_page.load_settings()
        self.settings_page.load_privacy_consent()
        self.pages.setCurrentWidget(self.settings_page)

    def _ensure_privacy_consent(self) -> bool:
        try:
            response = APIClient.get_privacy_consent()
        except requests.RequestException:
            QMessageBox.warning(
                self,
                'ประกาศความเป็นส่วนตัว',
                "ไม่สามารถตรวจสอบการตั้งค่าความเป็นส่วนตัวได้ โปรดตรวจสอบการเชื่อมต่อก่อน "
                "เปิดใช้งานกล้อง",
            )
            return False
        if not response.ok:
            QMessageBox.warning(
                self,
                'ประกาศความเป็นส่วนตัว',
                "ไม่สามารถโหลดการตั้งค่าความเป็นส่วนตัวได้ โปรดรีสตาร์ต backend แล้ว "
                "ลองอีกครั้ง",
            )
            return False
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            payload = None
        if isinstance(payload, dict) and payload.get("has_current_consent") is True:
            return True

        dialog = PrivacyNoticeDialog(self, require_acceptance=True)
        accepted = dialog.exec() == dialog.DialogCode.Accepted
        if accepted:
            self.settings_page.load_privacy_consent()
        return accepted

    def _privacy_consent_changed(self, accepted: bool) -> None:
        self.user_data["has_current_privacy_consent"] = accepted

    def update_profile(self, updated: dict) -> None:
        self.user_data.update(updated)
        self._update_account_avatar()

    def delete_account(self) -> None:
        """Finish local work, request deletion, then return to login."""
        if not self._finish_before_exit():
            self.settings_page.account_status_label.setText(
                'โปรดจบและบันทึกเซสชันปัจจุบันก่อนลบบัญชี'
            )
            return

        self.settings_page.delete_account_button.setEnabled(False)
        self.settings_page.account_status_label.setText('กำลังส่งคำขอลบบัญชี...')
        try:
            response = APIClient.request_account_deletion()
        except requests.RequestException:
            self.settings_page.delete_account_button.setEnabled(True)
            self.settings_page.account_status_label.setText(
                "ไม่สามารถส่งคำขอลบบัญชีได้ โปรดตรวจสอบการเชื่อมต่อ"
            )
            return
        if not response.ok:
            self.settings_page.delete_account_button.setEnabled(True)
            try:
                detail = response.json().get(
                    "detail", "ไม่สามารถส่งคำขอลบบัญชีได้"
                )
            except (ValueError, AttributeError):
                detail = "ไม่สามารถส่งคำขอลบบัญชีได้"
            self.settings_page.account_status_label.setText(str(detail))
            return

        try:
            scheduled_for = response.json().get("deletion_scheduled_for")
        except (ValueError, AttributeError):
            scheduled_for = None
        QMessageBox.information(
            self,
            'ส่งคำขอลบบัญชีแล้ว',
            "บัญชีของคุณถูกปิดใช้งานและมีกำหนดลบถาวรภายใน 14 วัน "
            "เข้าสู่ระบบอีกครั้งก่อนถึงกำหนดหากต้องการกู้คืนบัญชี"
            + (f"\n\nกำหนดเวลาลบบัญชี: {scheduled_for}" if scheduled_for else ""),
        )
        TokenStore.clear_token()
        self._exit_ready = True
        self.hide()
        from app.ui.windows.login_window import LoginWindow

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
        self.camera_calibration_page.stop_camera()

        # Clear Authentication Token
        TokenStore.clear_token()

        self.hide()

        from app.ui.windows.login_window import LoginWindow

        self.login_window = LoginWindow()
        self.login_window.show()

        self.close()

    def update_monitoring_controls(
        self,
    ):
        monitor = (
            self.monitoring_page
        )

        active = (
            monitor.session_id
            is not None
        )

        if monitor.network_stop_pending:

            status = (
                f"เซสชัน {monitor.session_id}: "
                "กำลังรอสิ้นสุด | การเชื่อมต่อเครือข่ายขาดหาย"
            )

        elif monitor.is_stopping:

            status = (
                "การตรวจจับ: กำลังสิ้นสุดและบันทึกข้อมูล..."
            )

        elif active:

            if monitor.network_gap_active:

                if monitor.is_paused:

                    state = (
                        "หยุดชั่วคราว | การเชื่อมต่อเครือข่ายขาดหาย"
                    )

                else:

                    state = (
                        "กำลังทำงานภายในเครื่อง | การเชื่อมต่อเครือข่ายขาดหาย"
                    )

            elif (
                monitor.camera_gap_started_at
                is not None
            ):

                state = (
                    "กำลังทำงาน | ข้อมูลจากกล้องขาดหาย"
                )

            elif monitor.is_paused:

                state = "หยุดชั่วคราว"

            else:

                state = "กำลังตรวจจับ (เปิดกล้อง)"

            status = (
                f"เซสชัน "
                f"{monitor.session_id}: "
                f"{state}"
            )

        else:

            status = (
                "การตรวจจับ: ยังไม่ทำงาน"
            )



        if monitor.network_stop_pending:
            status_tone = "danger"

        elif monitor.is_stopping:
            status_tone = "info"

        elif active and monitor.network_gap_active:
            status_tone = "warning"

        elif active and monitor.camera_gap_started_at is not None:
            status_tone = "warning"

        elif active and monitor.is_paused:
            status_tone = "warning"

        elif active:
            status_tone = "success"

        else:
            status_tone = "neutral"


        self.monitoring_status_label.set_status(
            status,
            status_tone,
        )

        monitor.refresh_controls()

        self._sync_monitoring_tray_state()

        if self.mini_controller.isVisible():
            self.mini_controller.refresh_state()

        self.dashboard_page.set_monitoring_state(
            monitor.session_id,
            monitor.is_paused,
            monitor.is_stopping,
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
                    self, 'พบเซสชันที่ยังไม่จบ',
                    f"เซสชัน {session['session_id']} ยังอยู่ในสถานะ {session['status']}.\n"
                    "เซสชันนี้อาจกำลังทำงานอยู่บนอุปกรณ์อื่น\n\n"
                    "ต้องการกำหนดเซสชันนี้เป็นถูกขัดจังหวะ เพื่อเริ่มเซสชันใหม่หรือไม่?\n"
                    "ข้อมูลที่บันทึกไว้เดิมจะยังคงอยู่ แต่เวลาสิ้นสุดจริงและสถิติการตรวจจับ "
                    "ที่สูญหายจะไม่สามารถกู้คืนได้ และระบบจะไม่สร้างข้อมูลสรุปขึ้นมาแทน",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    self.monitoring_status_label.setText("เซสชันก่อนหน้ายังไม่ได้รับการแก้ไข กรุณาลองเริ่มการตรวจจับอีกครั้ง")
                    return False
                interrupt_previous_session(session["session_id"])
            self.update_monitoring_controls()
            return True
        except (requests.RequestException, RuntimeError, ValueError) as error:
            self.monitoring_status_label.setText("ตรวจสอบเซสชันไม่สำเร็จ กรุณาลองเริ่มการตรวจจับอีกครั้ง")
            QMessageBox.warning(self, 'การกู้คืนเซสชัน', str(error))
            return False
        finally:
            self._recovery_in_progress = False

    def _show_unsaved_summary(self) -> bool:
        summary = self.session_summary_page.current_summary
        if summary and summary.get("summary_save_status") not in ("SAVED", "ALREADY_EXISTS"):
            self.pages.setCurrentWidget(self.session_summary_page)
            QMessageBox.warning(
                self, 'สรุปยังไม่ถูกบันทึก',
                'โปรดลองบันทึกสรุปนี้อีกครั้งก่อนเริ่มเซสชันใหม่หรือออกจากโปรแกรม',
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
            self.camera_calibration_page.stop_camera()
            self.baseline_page.stop_camera_preview()
            return True
        finally:
            self._exit_in_progress = False

    # ============================================
    # Mini Monitoring / Tray
    # ============================================

    def _ensure_mini_clock_session(self) -> None:
        """Keep a UI-only active-time clock synchronized with the session."""

        monitor = self.monitoring_page
        session_id = monitor.session_id

        if session_id is None:
            self._mini_clock_session_id = None
            self._mini_total_paused_seconds = 0.0
            self._mini_pause_started_monotonic = None
            self._mini_last_paused_state = False
            return

        if self._mini_clock_session_id != session_id:
            self._mini_clock_session_id = session_id
            self._mini_total_paused_seconds = 0.0
            self._mini_pause_started_monotonic = (
                time.monotonic()
                if monitor.is_paused
                else None
            )
            self._mini_last_paused_state = bool(
                monitor.is_paused
            )

    def _sync_mini_pause_clock(self) -> None:
        """Track pause intervals without changing MonitoringPage state."""

        monitor = self.monitoring_page
        self._ensure_mini_clock_session()

        if monitor.session_id is None:
            return

        paused = bool(monitor.is_paused)
        now = time.monotonic()

        if paused and not self._mini_last_paused_state:
            self._mini_pause_started_monotonic = now

        elif (
            not paused
            and self._mini_last_paused_state
            and self._mini_pause_started_monotonic is not None
        ):
            self._mini_total_paused_seconds += max(
                0.0,
                now - self._mini_pause_started_monotonic,
            )
            self._mini_pause_started_monotonic = None

        self._mini_last_paused_state = paused

    def _monitoring_elapsed_seconds(self) -> int:
        """
        Return active Monitoring seconds for the Mini display.

        This clock is display-only and never controls camera/detection/session
        timing. Time spent paused is excluded.
        """

        monitor = self.monitoring_page

        if monitor.session_started_monotonic is None:
            return 0

        self._ensure_mini_clock_session()

        now = time.monotonic()
        paused_seconds = self._mini_total_paused_seconds

        if (
            monitor.is_paused
            and self._mini_pause_started_monotonic is not None
        ):
            paused_seconds += max(
                0.0,
                now - self._mini_pause_started_monotonic,
            )

        return max(
            0,
            int(
                now
                - monitor.session_started_monotonic
                - paused_seconds
            ),
        )

    def _mini_preview_pixmap(self):
        """Return a copy of MonitoringPage's already-rendered preview."""

        pixmap = self.monitoring_page.preview_label.pixmap()

        if pixmap is None or pixmap.isNull():
            return None

        return pixmap.copy()

    def _mini_status_text(self) -> str:
        monitor = self.monitoring_page

        if monitor.session_id is None:
            return "ยังไม่ได้เริ่มการตรวจจับ"

        if monitor.network_stop_pending:
            return "กำลังรอสิ้นสุด | การเชื่อมต่อเครือข่ายขาดหาย"

        if monitor.network_gap_active:
            return (
                "หยุดชั่วคราว | การเชื่อมต่อเครือข่ายขาดหาย"
                if monitor.is_paused
                else "กำลังทำงานภายในเครื่อง | การเชื่อมต่อเครือข่ายขาดหาย"
            )

        if monitor.camera_gap_started_at is not None:
            return "CAMERA DATA GAP"

        return (
            "หยุดการตรวจจับชั่วคราว"
            if monitor.is_paused
            else "กล้องและระบบตรวจจับกำลังทำงาน"
        )

    def _on_monitoring_state_changed(self) -> None:
        self._sync_mini_pause_clock()
        self.update_monitoring_controls()

    def show_mini_monitoring(self) -> None:
        """
        Hide MainWindow and show Mini UI. The existing MonitoringPage keeps
        running unchanged; no camera/reference/pipeline object is recreated.
        """

        monitor = self.monitoring_page

        if monitor.session_id is None:
            return

        self._sync_mini_pause_clock()
        self._sync_monitoring_tray_state()

        self.hide()
        self.mini_controller.show_controller()

    def _restore_from_mini(self) -> None:
        self.mini_controller.hide_controller()

        self.showNormal()
        self.show()

        if self.monitoring_page.session_id is not None:
            self.pages.setCurrentWidget(
                self.monitoring_page
            )

        self.raise_()
        self.activateWindow()

    def _mini_pause_resume(self) -> None:
        monitor = self.monitoring_page

        if monitor.session_id is None:
            return

        monitor.handle_pause_resume()
        self._sync_mini_pause_clock()
        self.update_monitoring_controls()
        self.mini_controller.refresh_state()

    def _end_from_mini(self) -> None:
        monitor = self.monitoring_page

        if monitor.session_id is None:
            return

        # Restore first so Backend/network errors and the Summary page are
        # visible to the user. This does not restart the camera.
        self._restore_from_mini()
        monitor.handle_stop()

    def _mini_hidden(self) -> None:
        """
        X on Mini restores the full PostGuard window.

        Monitoring continues unchanged. This is UI-only and does
        not recreate the camera, baseline, movement guard, or session.
        """
        self._restore_from_mini()

    def _setup_monitoring_tray(self) -> None:
        self.monitoring_tray = QSystemTrayIcon(self)
        self.monitoring_tray.setToolTip(
            "การตรวจจับ PostGuard"
        )

        tray_icon = self.windowIcon()
        if not tray_icon.isNull():
            self.monitoring_tray.setIcon(
                tray_icon
            )

        tray_menu = QMenu(self)

        self.tray_restore_action = tray_menu.addAction(
            "เปิด PostGuard"
        )
        self.tray_pause_action = tray_menu.addAction(
            "หยุดการตรวจจับชั่วคราว"
        )
        self.tray_end_action = tray_menu.addAction(
            "สิ้นสุดการตรวจจับ"
        )

        tray_menu.addSeparator()

        self.tray_exit_action = tray_menu.addAction(
            "ออกจาก PostGuard"
        )

        self.monitoring_tray.setContextMenu(
            tray_menu
        )

        self.tray_restore_action.triggered.connect(
            self._restore_from_tray
        )
        self.tray_pause_action.triggered.connect(
            self._mini_pause_resume
        )
        self.tray_end_action.triggered.connect(
            self._end_from_tray
        )
        self.tray_exit_action.triggered.connect(
            self._exit_from_tray
        )

        self.monitoring_tray.activated.connect(
            self._on_tray_activated
        )

    def _sync_monitoring_tray_state(self) -> None:
        monitor = self.monitoring_page
        active = monitor.session_id is not None

        if QSystemTrayIcon.isSystemTrayAvailable():
            if active:
                if not self.monitoring_tray.isVisible():
                    self.monitoring_tray.show()
            elif self.monitoring_tray.isVisible():
                self.monitoring_tray.hide()

        can_pause = (
            active
            and not monitor.is_stopping
            and not monitor.network_stop_pending
            and monitor.capture is not None
            and not monitor.network_gap_active
            and monitor.camera_gap_started_at is None
        )

        self.tray_pause_action.setEnabled(
            can_pause
        )
        self.tray_pause_action.setText(
            "ทำการตรวจจับต่อ"
            if monitor.is_paused
            else "หยุดการตรวจจับชั่วคราว"
        )

        self.tray_end_action.setEnabled(
            active
            and not monitor.is_stopping
            and not monitor.network_stop_pending
        )

    def _restore_from_tray(self) -> None:
        self._restore_from_mini()

    def _end_from_tray(self) -> None:
        self._restore_from_mini()

        if self.monitoring_page.session_id is not None:
            self.monitoring_page.handle_stop()

    def _exit_from_tray(self) -> None:
        """Explicit Exit keeps the original finish/save-before-exit policy."""

        self._restore_from_mini()

        if not self._finish_before_exit():
            return

        self._exit_ready = True
        TokenStore.clear_token()
        self.mini_controller.hide_controller()
        self.monitoring_tray.hide()
        self.close()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def closeEvent(self, event):
        """
        Close PostGuard using the existing safe session-finalization policy.

        Closing the MainWindow is different from minimizing Monitoring:
        - Minimize Monitoring / tray keeps the current session alive.
        - Closing the MainWindow explicitly exits PostGuard.
        - An active session must be ended and saved before credentials
        are cleared and the application is allowed to close.
        """
        if not self._finish_before_exit():
            event.ignore()
            return

        self._exit_ready = True

        TokenStore.clear_token()

        self.mini_controller.hide_controller()

        if self.monitoring_tray.isVisible():
            self.monitoring_tray.hide()

        event.accept()

    # ============================================
    # Camera Preview
    # ============================================

    def show_camera_preview(
        self,
        camera: dict
    ):

        self.camera_calibration_page.stop_camera()
        self.camera_preview_page.start_preview(
            camera
        )

        self.pages.setCurrentWidget(
            self.camera_preview_page
        )

    def show_camera_calibration(self, camera: dict) -> None:
        """Open local reference-card preparation before personal baseline."""
        self.camera_preview_page.stop_preview()
        self.camera_calibration_page.set_camera(camera)
        self.pages.setCurrentWidget(self.camera_calibration_page)

    # ============================================
    # Camera Setup
    # ============================================

    def show_camera_setup(self):

        self.camera_preview_page.stop_preview()
        self.camera_calibration_page.stop_camera()

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
                    'ไม่พบหมายเลขอุปกรณ์กล้อง'
                )

            # Temporary Device Identifier
            device_id = (
                f"opencv-index:{device_index}"
            )

            # 2. Load Registered Cameras
            response = APIClient.get_cameras()

            if not response.ok:
                raise RuntimeError(
                    f"ไม่สามารถโหลดรายการกล้องได้: "
                    f"HTTP {response.status_code}"
                )

            saved_cameras = response.json()

            if not isinstance(saved_cameras, list):
                raise ValueError(
                    "รายการกล้องที่ได้รับจากเซิร์ฟเวอร์ไม่ถูกต้อง"
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
                        f"กล้อง {device_index}"
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
                        f"ลงทะเบียนกล้องไม่สำเร็จ: "
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
                    "รหัสกล้องที่ได้รับจากเซิร์ฟเวอร์ไม่ถูกต้อง"
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
                'เกิดข้อผิดพลาดในการลงทะเบียนกล้อง',
                str(error)
            )

            # Reopen Preview for Retry
            self.camera_preview_page.start_preview(
                camera
            )

            return

        # 7. Prepare physical camera placement before collecting a baseline.
        self.show_camera_calibration(camera_data)

    def handle_camera_calibration_continue(
        self,
        camera: dict,
        calibration_reference: dict,
    ) -> None:
        """Attach the numeric camera reference to the baseline capture flow."""
        if (
            calibration_reference.get("status") != "VALID"
            or calibration_reference.get("roll_correction_source")
            not in ("AUTO_CONFIRMED", "USER_CONFIRMED")
        ):
            QMessageBox.warning(
                self,
                'การเตรียมกล้อง',
                'โปรดเตรียมกล้องและยืนยันมุมกล้องให้เสร็จก่อนสร้างค่าท่าทางอ้างอิงส่วนบุคคล',
            )
            return
        camera_data = camera.copy()
        camera_data["camera_calibration"] = calibration_reference.copy()
        self.baseline_page.set_camera(camera_data)
        self.pages.setCurrentWidget(self.baseline_page)

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
            return

        self._ensure_mini_clock_session()
        self._sync_monitoring_tray_state()
        self.update_monitoring_controls()

    # ============================================
    # Session Summary
    # ============================================

    def show_session_summary(
        self,
        summary: dict
    ) -> None:

        self.mini_controller.hide_controller()
        self._ensure_mini_clock_session()
        self._sync_monitoring_tray_state()

        if not self.isVisible():
            self.showNormal()
            self.show()
            self.raise_()
            self.activateWindow()

        # Display Session Information
        self.session_summary_page.set_summary(
            summary
        )

        # Switch Monitoring -> Session Summary
        self.pages.setCurrentWidget(
            self.session_summary_page
        )
