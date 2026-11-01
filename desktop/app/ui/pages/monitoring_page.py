"""PostGuard real-time monitoring using the validated risk pipeline."""

import math
import statistics
import time
from datetime import datetime

import cv2
import requests
from app.services.risk_persistence_service import (
    RiskPersistenceService,
)

from PySide6.QtCore import (
    QLocale,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QImage,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.alert_sound import AlertSoundPlayer
from app.services.api_client import APIClient
from app.services.detection_service import DetectionService
from app.services.session_summary_service import (
    save_session_summary,
)
from app.services.session_risk_score_collector import (
    SessionRiskScoreCollector,
)
from app.services.validated_risk_pipeline_service import (
    ValidatedRiskPipelineService,
)
from app.ui.dialogs.posture_alert_dialog import (
    PostureAlertDialog,
)
from app.ui.utils.preview_sizing import (
    fit_preview_label,
)
from app.services.blink_detection_service import (
    BlinkDetectionService,
)

from app.services.eye_alert_policy import (
    EyeAlertPolicy,
)

from app.ui.dialogs.eye_alert_dialog import (
    EyeAlertDialog,
)
from app.services.camera_setup.camera_movement import (
    CameraMovementConfig,
    CameraMovementGuard,
    STATUS_MOVED,
)
from app.vision.mediapipe_detection.posture.relative_screen_distance import (
    extract_eye_distance_baseline,
)

from app.vision.mediapipe_detection.posture.screen_distance_policy import (
    ScreenDistancePolicy,
    ScreenDistancePolicyConfig,
    STATE_NORMAL,
    STATE_PENDING,
    STATE_TOO_CLOSE,
    STATE_NOT_EVALUATED,
)
from app.vision.camera_setup.resolution_compatibility import (
    RESOLUTION_COMPATIBLE,
    evaluate_resolution_compatibility,
)
from app.vision.camera_setup.camera_reference_contract import (
    CameraReferenceError,
    validate_locked_camera_reference,
    prepare_detection_frame,
)
from app.vision.mediapipe_detection.eye.blink_statistics import (
    BlinkStatistics,
)
from app.services.camera_loss_tracker import (
    CameraLossTracker,
)


RISK_LEVELS = (
    "NONE",
    "LOW",
    "MODERATE",
    "HIGH",
)
CAMERA_LOSS_GRACE_SECONDS = 60.0
CAMERA_RECONNECT_INTERVAL_SECONDS = 2.0


FACTOR_THAI = {
    "LEFT_SHOULDER_HIGH": "ไหล่ซ้ายสูง",
    "RIGHT_SHOULDER_HIGH": "ไหล่ขวาสูง",
    "TILT_LEFT": "คอเอียงซ้าย",
    "TILT_RIGHT": "คอเอียงขวา",
    "FLEXION": "ก้มคอ",
    "EXTENSION": "เงยคอ",
}


class MonitoringPage(QWidget):
    stop_requested = Signal(dict)
    state_changed = Signal()

    def __init__(self):
        super().__init__()

        self.is_stopping = False

        self.selected_camera = None
        self.baseline_id = None
        self.baseline_data = None

        self.capture = None
        self.detector = None

        # ====================================================
        # CAMERA DATA GAP / RECOVERY
        # ====================================================

        self.camera_gap_started_at = None
        self.camera_gap_last_retry_at = None

        # ====================================================
        # NETWORK / BACKEND GAP
        # ====================================================
        #
        # Camera / Detection / Risk remain local and continue
        # working while Backend is temporarily unavailable.
        #
        # Session-changing operations such as Pause / Resume /
        # Stop still require authoritative Backend confirmation.
        # ====================================================

        self.network_gap_active = False
        self.network_gap_started_at = None
        self.network_gap_last_error = None

        # User requested Stop but Backend could not confirm it.
        self.network_stop_pending = False

        # Local summary snapshot captured at the moment Stop
        # was requested. It is kept until Backend confirms
        # COMPLETED.
        self.pending_stop_summary = None

        # Recovery retry is active only after a Backend/network
        # failure is detected. We intentionally do not poll the
        # Backend continuously during normal Monitoring.
        self.network_recovery_timer = QTimer(
            self
        )

        self.network_recovery_timer.setInterval(
            3000
        )

        self.network_recovery_timer.timeout.connect(
            self._retry_network_recovery
        )

        # ====================================================
        # CAMERA MOVEMENT GUARD
        # ====================================================
        #
        # Uses RAW camera frames before Camera Roll correction.
        # It tracks background/global motion so user posture
        # movement is not used as camera-movement evidence.
        # ====================================================

        self.camera_movement_guard = (
            CameraMovementGuard(
                CameraMovementConfig(
                    analysis_width=640,
                    sample_every_frames=3,
                    warmup_samples=20,

                    min_tracked_points=18,
                    min_inlier_ratio=0.55,

                    translation_ratio_threshold=0.012,
                    rotation_threshold_deg=1.50,
                    scale_change_threshold=0.030,

                    min_region_inliers=2,
                    min_active_regions=3,

                    confirmation_window=5,
                    confirmation_hits=3,
                )
            )
        )

        self.camera_movement_triggered = False

        # ====================================================
        # BLINK DETECTION
        # ====================================================

        self.blink_detector = (
            BlinkDetectionService()
        )

        self.last_blink_result = None

        self.blink_statistics = (
            BlinkStatistics(
                window_seconds=60.0
            )
        )

        self.last_blink_statistics = None

        self.eye_alert_policy = (
            EyeAlertPolicy()
        )

        self.last_eye_alert_result = None

        self.last_blink_result = None

        self.eye_alert_policy = (
            EyeAlertPolicy()
        )

        self.last_eye_alert_result = None

        self.eye_alert_popup = None

        # ====================================================
        # SCREEN DISTANCE POLICY
        # ====================================================
        #
        # Screen Distance เป็น monitoring feature แยกจาก
        # Posture Risk / RULA
        #
        # Threshold ปัจจุบันเป็น candidate engineering policy
        # ไม่ใช่ ergonomic / physical-distance threshold
        # ====================================================

        self.screen_distance_policy = (
            ScreenDistancePolicy(
                ScreenDistancePolicyConfig(
                    enter_ratio=1.25,
                    exit_ratio=1.15,
                    confirmation_seconds=3.0,
                )
            )
        )

        self.last_screen_distance_result = None

        # ====================================================
        # SESSION
        # ====================================================

        self.frame_count = 0

        self.session_id = None
        self.is_paused = False

        self.session_started_at = None
        self.session_started_monotonic = None

        # ====================================================
        # DETECTION STATISTICS
        # ====================================================

        self.detection_count = 0
        self.pose_detected_count = 0
        self.face_detected_count = 0

        self.shoulder_samples = []
        self.neck_samples = []

        # ====================================================
        # VALIDATED POSTGUARD PIPELINE
        # ====================================================

        self.risk_pipeline = (
            ValidatedRiskPipelineService()
        )

        self.risk_persistence = (
            RiskPersistenceService()
        )

        # ====================================================
        # SESSION-LEVEL RISK SCORE ANALYTICS
        #
        # Collector นี้อยู่ตลอดทั้ง Session
        # Pause/Resume ห้าม reset
        # ====================================================

        self.risk_score_collector = (
            SessionRiskScoreCollector(
                bucket_seconds=10.0
            )
        )

        self.last_pipeline_result = None
        self.screen_distance_policy.reset()

        self.last_screen_distance_result = (
            None
        )

        self.risk_sample_counts = {
            level: 0
            for level in RISK_LEVELS
        }

        self.alert_notification_count = 0

        # ====================================================
        # PRESENTATION
        # ====================================================

        self.sound_player = (
            AlertSoundPlayer()
        )

        self.alert_popup = None

        # ====================================================
        # LEGACY TEST-COMPATIBILITY CONTROLS
        # ====================================================

        self._setup_legacy_test_controls()

        # ====================================================
        # CAMERA TIMER
        # ====================================================

        self.timer = QTimer(self)
        self.timer.setInterval(30)

        self.timer.timeout.connect(
            self.update_frame
        )

        self._setup_ui()

        self.camera_loss_tracker = (
            CameraLossTracker()
        )

    # ========================================================
    # TEMPORARY OLD TEST COMPATIBILITY
    # ========================================================

    def _setup_legacy_test_controls(
        self,
    ) -> None:

        self._last_neck_threshold = 10.0

        self.threshold_enabled = QCheckBox(
            self
        )

        self.neck_threshold_spin = QDoubleSpinBox(
            self
        )

        self.neck_threshold_spin.setLocale(
            QLocale.c()
        )

        self.neck_threshold_spin.setRange(
            0.0,
            45.0,
        )

        self.neck_threshold_spin.setDecimals(
            1
        )

        self.neck_threshold_spin.setSingleStep(
            0.5
        )

        self.neck_threshold_spin.setValue(
            0.0
        )

        self.neck_threshold_spin.setEnabled(
            False
        )

        self.threshold_enabled.toggled.connect(
            self.set_threshold_enabled
        )

        self.neck_threshold_spin.valueChanged.connect(
            self._remember_legacy_threshold
        )

        self.threshold_enabled.hide()
        self.neck_threshold_spin.hide()

    def _remember_legacy_threshold(
        self,
        value: float,
    ) -> None:

        if value > 0:

            self._last_neck_threshold = (
                float(value)
            )

    def set_threshold_enabled(
        self,
        enabled: bool,
    ) -> None:

        if (
            not enabled
            and
            self.neck_threshold_spin.value() > 0
        ):

            self._last_neck_threshold = (
                self.neck_threshold_spin.value()
            )

        self.neck_threshold_spin.blockSignals(
            True
        )

        self.neck_threshold_spin.setEnabled(
            enabled
        )

        self.neck_threshold_spin.setValue(
            self._last_neck_threshold
            if enabled
            else 0.0
        )

        self.neck_threshold_spin.blockSignals(
            False
        )

    # ========================================================
    # UI
    # ========================================================

    def _setup_ui(
        self,
    ) -> None:

        self.setProperty(
            "page",
            True,
        )

        page_layout = QVBoxLayout(
            self
        )

        page_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(
            True
        )

        page_layout.addWidget(
            scroll
        )

        content = QWidget()

        content.setProperty(
            "page",
            True,
        )

        layout = QVBoxLayout(
            content
        )

        layout.setContentsMargins(
            24,
            20,
            24,
            24,
        )

        layout.setSpacing(
            12
        )

        scroll.setWidget(
            content
        )

        self.title_label = QLabel(
            "Real-time Monitoring"
        )

        self.title_label.setProperty(
            "role",
            "title",
        )

        self.description_label = QLabel(
            "Detection → Assessment → Temporal → "
            "Risk Evaluation → Risk Event → Alert Policy"
        )

        self.description_label.setProperty(
            "role",
            "muted",
        )

        info_group = (
            self._create_information_group()
        )

        self._setup_preview()

        detection_group = (
            self._create_detection_group()
        )

        risk_group = (
            self._create_risk_group()
        )

        button_layout = (
            self._create_button_layout()
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.description_label
        )

        columns = QHBoxLayout()

        columns.setSpacing(
            16
        )

        # ====================================================
        # LEFT PANEL
        # ====================================================

        camera_panel = QFrame()

        camera_panel.setProperty(
            "card",
            True,
        )

        camera_layout = QVBoxLayout(
            camera_panel
        )

        camera_layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        camera_layout.setSpacing(
            10
        )

        camera_layout.addWidget(
            info_group
        )

        camera_layout.addWidget(
            self.preview_label,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )

        camera_layout.addLayout(
            button_layout
        )

        # ====================================================
        # RIGHT PANEL
        # ====================================================

        metrics_panel = QFrame()

        metrics_panel.setProperty(
            "card",
            True,
        )

        metrics_layout = QVBoxLayout(
            metrics_panel
        )

        metrics_layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        metrics_layout.setSpacing(
            10
        )

        metrics_layout.addWidget(
            detection_group
        )

        metrics_layout.addWidget(
            risk_group
        )

        metrics_layout.addStretch()

        columns.addWidget(
            camera_panel,
            3,
        )

        columns.addWidget(
            metrics_panel,
            2,
        )

        layout.addLayout(
            columns,
            1,
        )

    # ========================================================
    # INFORMATION GROUP
    # ========================================================

    def _create_information_group(
        self,
    ) -> QGroupBox:

        info_group = QGroupBox(
            "Monitoring Information"
        )

        info_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        info_layout = QVBoxLayout(
            info_group
        )

        self.camera_label = QLabel(
            "กล้อง: -"
        )

        self.baseline_label = QLabel(
            "รหัส Baseline: -"
        )

        self.session_label = QLabel(
            "รหัส Session: -"
        )

        self.baseline_shoulder_label = QLabel(
            "ค่าพื้นฐานความเอียงไหล่: -"
        )

        self.baseline_neck_label = QLabel(
            "ค่าพื้นฐานความเอียงคอด้านข้าง: -"
        )

        self.baseline_flexion_label = QLabel(
            "ค่าพื้นฐานมุมก้ม/เงยคอ: -"
        )

        self.status_label = QLabel(
            "สถานะ: ยังไม่เริ่ม"
        )

        for label in (
            self.camera_label,
            self.baseline_label,
            self.session_label,
            self.baseline_shoulder_label,
            self.baseline_neck_label,
            self.baseline_flexion_label,
            self.status_label,
        ):
            info_layout.addWidget(
                label
            )

        return info_group

    # ========================================================
    # CAMERA PREVIEW
    # ========================================================

    def _setup_preview(
        self,
    ) -> None:

        self.preview_label = QLabel(
            "ภาพการตรวจจับจะแสดงที่นี่"
        )

        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_label.setFixedSize(
            720,
            405,
        )

        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        self.preview_label.setProperty(
            "preview",
            True,
        )

    # ========================================================
    # DETECTION GROUP
    # ========================================================

    def _create_detection_group(
        self,
    ) -> QGroupBox:

        detection_group = QGroupBox(
            "Live Detection"
        )

        detection_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        detection_layout = QVBoxLayout(
            detection_group
        )

        self.detection_label = QLabel(
            "ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ"
        )

        self.shoulder_label = QLabel(
            "ความเอียงไหล่: --"
        )

        self.neck_label = QLabel(
            "ความเอียงคอด้านข้าง: --"
        )

        self.flexion_label = QLabel(
            "มุมก้ม/เงยคอ: --"
        )
        self.screen_distance_label = QLabel(
            "ระยะห่างหน้าจอ: --"
        )

        self.screen_distance_label.setWordWrap(
            True
        )

        # ========================================================
        # EYE / BLINK
        # ========================================================

        self.right_eye_state_label = QLabel(
            "ตาขวา: --"
        )

        self.left_eye_state_label = QLabel(
            "ตาซ้าย: --"
        )

        self.eye_state_label = QLabel(
            "สถานะตารวม: --"
        )

        self.eye_pattern_label = QLabel(
            "รูปแบบตา: --"
        )

        self.eye_openness_label = QLabel(
            "Eye Openness: --"
        )

        self.blink_count_label = QLabel(
            "จำนวนการกระพริบตา: 0"
        )

        # ========================================================
        # BASELINE DIFFERENCE
        # ========================================================

        self.shoulder_difference_label = QLabel(
            "ผลต่างจาก Baseline ไหล่: --"
        )

        self.neck_difference_label = QLabel(
            "ผลต่างจาก Baseline คอด้านข้าง: --"
        )

        self.flexion_difference_label = QLabel(
            "ผลต่างจาก Baseline ก้ม/เงยคอ: --"
        )

        for label in (
            self.detection_label,
            self.shoulder_label,
            self.neck_label,
            self.flexion_label,
            self.screen_distance_label,

            self.right_eye_state_label,
            self.left_eye_state_label,
            self.eye_state_label,
            self.eye_pattern_label,
            self.eye_openness_label,
            self.blink_count_label,

            self.shoulder_difference_label,
            self.neck_difference_label,
            self.flexion_difference_label,
        ):

            detection_layout.addWidget(
                label
            )

        return detection_group

    # ========================================================
    # RISK GROUP
    # ========================================================

    def _create_risk_group(
        self,
    ) -> QGroupBox:

        risk_group = QGroupBox(
            "PostGuard Risk Pipeline"
        )

        risk_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        risk_layout = QVBoxLayout(
            risk_group
        )

        self.assessment_label = QLabel(
            "Assessment: Waiting"
        )

        self.factor_label = QLabel(
            "Posture Factors: -"
        )

        self.factor_label.setWordWrap(
            True
        )

        self.duration_label = QLabel(
            "Longest Continuous Factor: -"
        )

        self.risk_label = QLabel(
            "Risk Level: -"
        )

        self.event_label = QLabel(
            "Risk Event: -"
        )

        self.alert_label = QLabel(
            "Alert Policy: Waiting"
        )

        self.alert_label.setWordWrap(
            True
        )

        self.risk_note_label = QLabel(
            "ระดับความเสี่ยงนี้เป็น PostGuard Prototype "
            "Engineering Policy ไม่ใช่ Full RULA, "
            "RULA Action Level หรือการวินิจฉัยทางการแพทย์"
        )

        self.risk_note_label.setWordWrap(
            True
        )

        self.risk_note_label.setProperty(
            "role",
            "muted",
        )

        for label in (
            self.assessment_label,
            self.factor_label,
            self.duration_label,
            self.risk_label,
            self.event_label,
            self.alert_label,
            self.risk_note_label,
        ):

            risk_layout.addWidget(
                label
            )

        return risk_group

    # ========================================================
    # BUTTONS
    # ========================================================

    def _create_button_layout(
        self,
    ) -> QHBoxLayout:

        button_layout = QHBoxLayout()

        self.pause_button = QPushButton(
            "Pause Monitoring"
        )

        self.pause_button.setEnabled(
            False
        )

        self.pause_button.clicked.connect(
            self.handle_pause_resume
        )

        self.stop_button = QPushButton(
            "Stop Monitoring"
        )

        self.stop_button.setProperty(
            "variant",
            "danger",
        )

        self.stop_button.setEnabled(
            False
        )

        self.stop_button.clicked.connect(
            self.handle_stop
        )

        button_layout.addWidget(
            self.stop_button
        )

        button_layout.addWidget(
            self.pause_button
        )

        button_layout.setStretch(
            0,
            1,
        )

        button_layout.setStretch(
            1,
            1,
        )

        return button_layout

        # ========================================================
    # NETWORK / BACKEND GAP
    # ========================================================

    def _mark_network_gap(
        self,
        error,
        *,
        stop_pending: bool = False,
    ) -> None:
        """
        Mark Backend connectivity as temporarily unavailable.

        Important:
        - Local Detection continues unless Stop was requested.
        - Risk calculation continues locally.
        - Pause / Resume are disabled until Backend state can
          be confirmed.
        - Session ID is never cleared here.
        """

        now = time.monotonic()

        if not self.network_gap_active:

            self.network_gap_active = True

            self.network_gap_started_at = (
                now
            )

        self.network_gap_last_error = (
            str(error)
        )

        if stop_pending:

            self.network_stop_pending = (
                True
            )

        # Pause/Resume modifies Backend session state.
        # Do not allow it while Backend is unavailable.
        self.pause_button.setEnabled(
            False
        )

        if self.network_stop_pending:

            self.status_label.setText(
                "สถานะ: NETWORK GAP | "
                "หยุดตรวจจับในเครื่องแล้ว "
                "| รอ Backend ยืนยันการจบ Session"
            )

        elif self.is_paused:

            self.status_label.setText(
                "สถานะ: PAUSED | NETWORK GAP "
                "| รอเชื่อมต่อ Backend"
            )

        else:

            self.status_label.setText(
                "สถานะ: กำลังตรวจจับในเครื่อง "
                "(LOCAL RUNNING) | NETWORK GAP"
            )

        if (
            not
            self.network_recovery_timer.isActive()
        ):

            self.network_recovery_timer.start()

        self.state_changed.emit()


    def _clear_network_gap(
        self,
    ) -> None:
        """
        Backend is reachable again and authoritative Session
        state matches Desktop state.
        """

        if self.network_stop_pending:
            return

        self.network_gap_active = False
        self.network_gap_started_at = None
        self.network_gap_last_error = None

        if (
            self.network_recovery_timer.isActive()
        ):

            self.network_recovery_timer.stop()

        if self.session_id is not None:

            if self.is_paused:

                self.status_label.setText(
                    "สถานะ: หยุดชั่วคราว "
                    "(PAUSED)"
                )

            else:

                self.status_label.setText(
                    "สถานะ: กำลังตรวจจับ "
                    "(RUNNING)"
                )

                if (
                    self.capture is not None
                    and
                    self.camera_gap_started_at
                    is None
                ):

                    self.pause_button.setEnabled(
                        True
                    )

        self.state_changed.emit()


    def _retry_network_recovery(
        self,
    ) -> None:
        """
        Retry Backend reconciliation every few seconds after a
        NETWORK GAP has been detected.

        This does not create a new Session.

        Existing session_id remains authoritative until Backend
        confirms its state.
        """

        session_id = (
            self.session_id
        )

        if (
            type(session_id) is not int
            or
            session_id <= 0
        ):

            self.network_recovery_timer.stop()

            self.network_gap_active = False
            self.network_gap_started_at = None
            self.network_gap_last_error = None
            self.network_stop_pending = False
            self.pending_stop_summary = None

            return

        # ====================================================
        # QUICK AUTHORITATIVE CHECK
        #
        # Short timeout prevents a long GUI freeze while
        # Backend is still unavailable.
        # ====================================================

        try:

            response = (
                APIClient.get_session(
                    session_id,
                    timeout=2.0,
                )
            )

        except requests.RequestException:

            return

        except Exception as error:

            print(
                "NETWORK RECOVERY CHECK ERROR:",
                error,
            )

            return

        if not response.ok:

            return

        try:

            remote = (
                response.json()
            )

        except (
            ValueError,
            AttributeError,
        ):

            return

        if not isinstance(
            remote,
            dict,
        ):

            return

        if (
            remote.get(
                "session_id"
            )
            !=
            session_id
        ):

            return

        remote_status = (
            remote.get(
                "status"
            )
        )

        # ====================================================
        # PENDING STOP
        # ====================================================

        if self.network_stop_pending:

            # Another request may actually have completed before
            # the connection disappeared.
            if remote_status == "COMPLETED":

                self.session_id = None

                summary = (
                    self.pending_stop_summary
                    or
                    {}
                )

                self.network_gap_active = False
                self.network_stop_pending = False
                self.pending_stop_summary = None

                self.network_recovery_timer.stop()

                self._complete_session_after_remote_end(
                    summary,
                    remote,
                )

                return

            # Still active -> retry END now that Backend can
            # be reached.
            if remote_status not in (
                "RUNNING",
                "PAUSED",
            ):

                return

            try:

                completed = (
                    self._end_remote_session()
                )

            except requests.RequestException:

                return

            except (
                RuntimeError,
                ValueError,
            ) as error:

                print(
                    "PENDING SESSION END ERROR:",
                    error,
                )

                return

            summary = (
                self.pending_stop_summary
                or
                {}
            )

            self.network_gap_active = False
            self.network_stop_pending = False
            self.pending_stop_summary = None

            self.network_recovery_timer.stop()

            self._complete_session_after_remote_end(
                summary,
                completed,
            )

            return

        # ====================================================
        # NORMAL NETWORK GAP RECOVERY
        # ====================================================

        expected_status = (
            "PAUSED"
            if self.is_paused
            else
            "RUNNING"
        )

        if (
            remote_status
            ==
            expected_status
        ):

            self._clear_network_gap()

            return

        # Backend is reachable, but state does not agree with
        # Desktop. Do not silently overwrite local state.
        self.status_label.setText(
            "สถานะ: Backend กลับมาแล้ว "
            "แต่สถานะ Session ไม่ตรงกัน "
            f"(Local={expected_status}, "
            f"Backend={remote_status})"
        )

        self.state_changed.emit()


    def _begin_pending_stop(
        self,
        summary: dict,
        error,
    ) -> None:
        """
        User pressed Stop but Backend could not confirm END.

        Local monitoring stops immediately, but session_id and
        summary snapshot are preserved until reconciliation.
        """

        self.pending_stop_summary = (
            dict(
                summary
            )
        )

        self.network_stop_pending = True

        # ====================================================
        # STOP LOCAL CAMERA / DETECTOR
        #
        # Do NOT call _release_local_resources() yet because
        # that would destroy the local statistics required for
        # the final summary.
        # ====================================================

        self._close_capture_resources()

        self.close_posture_alert()
        self.close_eye_alert()

        self.sound_player.notify(
            False
        )

        self.pause_button.setEnabled(
            False
        )

        self.stop_button.setEnabled(
            False
        )

        self._mark_network_gap(
            error,
            stop_pending=True,
        )

        QMessageBox.warning(
            self,
            "รอยืนยันการจบเซสชัน",
            (
                "PostGuard หยุดการตรวจจับในเครื่องแล้ว "
                "แต่ Backend ยังไม่สามารถยืนยันการจบ "
                "Session ได้\n\n"
                f"Session ID: {self.session_id}\n"
                f"{error}\n\n"
                "ระบบจะลองเชื่อมต่อและจบ Session "
                "ให้อัตโนมัติเมื่อ Backend กลับมา\n"
                "ระหว่างนี้จะไม่สร้าง Session ใหม่ทับ"
            ),
        )

    # ========================================================
    # BACKEND HELPERS
    # ========================================================

    @staticmethod
    def _response_error(
        response,
    ) -> str:

        try:

            payload = (
                response.json()
            )

            detail = (
                payload.get(
                    "detail",
                    response.text,
                )
                if isinstance(
                    payload,
                    dict,
                )
                else
                response.text
            )

        except ValueError:

            detail = (
                response.text
            )

        return (
            f"HTTP {response.status_code}: "
            f"{detail}"
        )

    def _end_remote_session(
        self,
    ) -> dict | None:

        if self.session_id is None:

            return None

        try:

            response = (
                APIClient.end_session(
                    self.session_id
                )
            )

        except requests.RequestException as error:

            try:

                check = (
                    APIClient.get_session(
                        self.session_id
                    )
                )

                if (
                    check.ok
                    and
                    check.json().get(
                        "status"
                    )
                    ==
                    "COMPLETED"
                ):

                    response = (
                        check
                    )

                else:

                    raise error

            except (
                requests.RequestException,
                ValueError,
                AttributeError,
            ):

                raise error

        if not response.ok:

            if (
                response.status_code
                ==
                409
            ):

                check = (
                    APIClient.get_session(
                        self.session_id
                    )
                )

                if (
                    check.ok
                    and
                    check.json().get(
                        "status"
                    )
                    ==
                    "COMPLETED"
                ):

                    response = (
                        check
                    )

                else:

                    raise RuntimeError(
                        self._response_error(
                            response
                        )
                    )

            else:

                raise RuntimeError(
                    self._response_error(
                        response
                    )
                )

        data = (
            response.json()
        )

        if (
            not isinstance(
                data,
                dict,
            )
            or
            data.get(
                "status"
            )
            !=
            "COMPLETED"
        ):

            raise ValueError(
                "Backend did not confirm "
                "COMPLETED session status."
            )

        if (
            data.get(
                "session_id"
            )
            !=
            self.session_id
        ):

            raise ValueError(
                "Backend returned an "
                "unexpected session_id."
            )

        # สำคัญ:
        # Backend ยืนยันว่า session จบแล้ว
        # จึง clear local session id
        self.session_id = None

        return data

    # ========================================================
    # PERSONAL BASELINE
    # ========================================================

    def load_personal_baseline(
        self,
        baseline_id: int,
        camera_id: int,
    ) -> dict:

        response = (
            APIClient.get(
                f"/personal-baselines/{baseline_id}"
            )
        )

        if not response.ok:

            raise RuntimeError(
                "Cannot load baseline: "
                +
                self._response_error(
                    response
                )
            )

        baseline = (
            response.json()
        )

        if not isinstance(
            baseline,
            dict,
        ):

            raise ValueError(
                "Invalid baseline response."
            )

        if (
            baseline.get(
                "baseline_id"
            )
            !=
            baseline_id
        ):

            raise ValueError(
                "Baseline ID does not match."
            )

        if (
            baseline.get(
                "camera_id"
            )
            !=
            camera_id
        ):

            raise ValueError(
                "Baseline belongs to another camera."
            )

        shoulder = (
            baseline.get(
                "shoulder_angle"
            )
        )

        neck = (
            baseline.get(
                "lateral_tilt_baseline"
            )
        )

        flexion = (
            baseline.get(
                "neck_flexion_baseline"
            )
        )

        for name, value in (
            (
                "Shoulder",
                shoulder,
            ),
            (
                "Neck lateral",
                neck,
            ),
        ):

            if (
                type(value)
                not in
                (int, float)
                or
                not math.isfinite(
                    value
                )
            ):

                raise ValueError(
                    f"Invalid {name} baseline value."
                )

        self.baseline_shoulder_label.setText(
            "Baseline Shoulder Tilt: "
            f"{shoulder:+.2f}°"
        )

        self.baseline_neck_label.setText(
            "Baseline Neck Lateral Tilt: "
            f"{neck:+.2f}°"
        )

        if (
            type(flexion)
            in
            (int, float)
            and
            math.isfinite(
                flexion
            )
        ):

            self.baseline_flexion_label.setText(
                "Baseline Neck Flexion: "
                f"{flexion:+.2f}°"
            )

        else:

            self.baseline_flexion_label.setText(
                "Baseline Neck Flexion: N/A "
                "(Risk Evaluation may be PARTIAL)"
            )

        self.baseline_data = (
            baseline
        )

        return baseline

    # ========================================================
    # CAMERA RESOLUTION COMPATIBILITY
    # ========================================================

    def validate_monitoring_resolution(
        self,
    ) -> dict:
        """
        Validate that the camera resolution used for Monitoring
        matches the resolution stored with the Personal Baseline.

        The actual camera frame is the source of truth.

        This validation intentionally does NOT:
        - resize the frame,
        - modify the Personal Baseline,
        - apply camera roll correction,
        - apply perspective correction,
        - modify Screen Distance,
        - modify Posture Risk / RULA.
        """

        if self.capture is None:
            raise RuntimeError(
                "Camera is not available for resolution validation."
            )

        if self.baseline_data is None:
            raise RuntimeError(
                "Personal Baseline is not available "
                "for resolution validation."
            )

        # ----------------------------------------------------
        # Read a REAL frame from the newly opened camera.
        #
        # Do not trust CAP_PROP_FRAME_WIDTH / HEIGHT alone.
        # The actual frame.shape is the final source of truth.
        # ----------------------------------------------------

        success, frame = self.capture.read()

        if (
            not success
            or
            frame is None
        ):
            raise RuntimeError(
                "Unable to read camera frame for "
                "resolution validation."
            )

        result = evaluate_resolution_compatibility(
            self.baseline_data,
            frame,
        )

        if (
            result.get("status")
            !=
            RESOLUTION_COMPATIBLE
            or
            result.get("compatible")
            is not True
        ):

            expected_width = result.get(
                "expected_width"
            )

            expected_height = result.get(
                "expected_height"
            )

            actual_width = result.get(
                "actual_width"
            )

            actual_height = result.get(
                "actual_height"
            )

            reason = result.get(
                "reason",
                "unknown",
            )

            if (
                expected_width is not None
                and
                expected_height is not None
                and
                actual_width is not None
                and
                actual_height is not None
            ):
                raise RuntimeError(
                    "Camera resolution does not match "
                    "the Personal Baseline.\n\n"
                    f"Baseline: "
                    f"{expected_width}x{expected_height}\n"
                    f"Current camera: "
                    f"{actual_width}x{actual_height}\n\n"
                    "Please use the same camera resolution "
                    "used during Camera Setup / "
                    "Personal Baseline."
                )

            raise RuntimeError(
                "Camera resolution could not be validated "
                "against the Personal Baseline.\n"
                f"Reason: {reason}"
            )

        return result

    # ========================================================
    # START MONITORING
    # ========================================================

    def start_monitoring(
        self,
        camera: dict,
        baseline_id: int,
    ) -> bool:

        # ปิด session เก่าก่อน
        if not self.stop_monitoring():

            QMessageBox.warning(
                self,
                "ข้อผิดพลาดของเซสชัน",
                "The previous database session "
                "could not be ended. "
                "Check your connection and retry.",
            )

            return False

        self.selected_camera = (
            camera.copy()
        )
        try:
            camera_reference = (
                validate_locked_camera_reference(
                    self.selected_camera
                )
            )

        except CameraReferenceError as error:

            QMessageBox.warning(
                self,
                "Camera Reference",
                str(error),
            )

            return False

        # New Monitoring session starts with a fresh
        # camera-movement reference period.
        self.camera_movement_guard.reset()
        self.camera_movement_triggered = False

        self.baseline_id = (
            baseline_id
        )

        device_index = (
            camera.get(
                "device_index"
            )
        )

        camera_id = (
            camera.get(
                "camera_id"
            )
        )

        if device_index is None:

            QMessageBox.warning(
                self,
                "การตรวจจับ",
                "ไม่พบหมายเลขอุปกรณ์กล้อง",
            )

            return False

        if (
            type(baseline_id)
            is not int
            or
            baseline_id <= 0
        ):

            QMessageBox.warning(
                self,
                "การตรวจจับ",
                "ต้องมี Baseline ID ที่บันทึกแล้ว",
            )

            return False

        self.camera_loss_tracker.reset()

        # ====================================================
        # LOAD BASELINE
        # ====================================================

        try:

            if (
                type(camera_id)
                is not int
                or
                camera_id <= 0
            ):

                raise ValueError(
                    "Camera ID ไม่ถูกต้อง"
                )

            self.load_personal_baseline(
                baseline_id,
                camera_id,
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:

            QMessageBox.warning(
                self,
                "ข้อผิดพลาดของค่าอ้างอิง",
                str(error),
            )

            return False

        self.camera_label.setText(
            "Camera: "
            +
            camera.get(
                "camera_name",
                "Unknown Camera",
            )
        )

        self.baseline_label.setText(
            f"Baseline ID: {baseline_id}"
        )

        # ====================================================
        # CAMERA + DETECTOR + BACKEND SESSION
        # ====================================================

        try:

            expected_width = self.baseline_data.get(
                "camera_frame_width"
            )
            expected_height = self.baseline_data.get(
                "camera_frame_height"
            )

            if (
                type(expected_width) is not int
                or type(expected_height) is not int
                or expected_width <= 0
                or expected_height <= 0
            ):
                raise RuntimeError(
                    "Personal Baseline does not contain a valid "
                    "camera resolution."
                )

            # Monitoring must reopen the camera using the exact
            # resolution stored with the Personal Baseline.
            # On Windows, DirectShow + MJPEG is attempted first
            # because it is the same capture mode used by camera scan.
            self.capture = cv2.VideoCapture(
                int(device_index),
                cv2.CAP_DSHOW,
            )

            if not self.capture.isOpened():
                self.capture.release()
                self.capture = cv2.VideoCapture(
                    int(device_index),
                    cv2.CAP_ANY,
                )

            if not self.capture.isOpened():
                raise RuntimeError(
                    "Unable to open camera."
                )
            locked_width = (
                camera_reference[
                    "locked_frame_width"
                ]
            )
            locked_height = (
                camera_reference[
                    "locked_frame_height"
                ]
            )

            if (
                expected_width != locked_width
                or expected_height != locked_height
            ):
                raise RuntimeError(
                    "Personal Baseline camera resolution does not "
                    "match the locked Camera Reference. "
                    f"baseline={expected_width}x{expected_height}, "
                    f"reference={locked_width}x{locked_height}"
                )

            self.capture.set(
                cv2.CAP_PROP_FOURCC,
                cv2.VideoWriter_fourcc(*"MJPG"),
            )
            self.capture.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                locked_width,
            )
            self.capture.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                locked_height,
            )
            self.capture.set(
                cv2.CAP_PROP_FPS,
                30,
            )

            # =================================================
            # RESOLUTION COMPATIBILITY GATE
            #
            # IMPORTANT:
            # ต้องตรวจจาก frame จริงก่อนสร้าง Detector
            # และก่อนสร้าง Backend Session
            # =================================================

            resolution_result = (
                self.validate_monitoring_resolution()
            )

            print(
                "CAMERA RESOLUTION VALIDATED:",
                f"{resolution_result['actual_width']}"
                f"x{resolution_result['actual_height']}",
                "| BASELINE:",
                f"{resolution_result['expected_width']}"
                f"x{resolution_result['expected_height']}",
            )

            # =================================================
            # DETECTOR
            #
            # สร้างหลังจาก Resolution ผ่านแล้วเท่านั้น
            # =================================================

            self.detector = (
                DetectionService()
            )

            # =================================================
            # BACKEND SESSION
            #
            # ห้ามสร้าง Session ก่อน Resolution ผ่าน
            # =================================================

            response = (
                APIClient.start_session(
                    camera_id,
                    baseline_id,
                )
            )

            if not response.ok:

                raise RuntimeError(
                    "Cannot start session: "
                    +
                    self._response_error(
                        response
                    )
                )

            session = (
                response.json()
            )

            session_id = (
                session.get(
                    "session_id"
                )
                if isinstance(
                    session,
                    dict,
                )
                else
                None
            )

            if (
                type(session_id)
                is not int
                or
                session_id <= 0
            ):

                raise ValueError(
                    "Backend returned an "
                    "invalid session_id."
                )

            if (
                session.get(
                    "status"
                )
                !=
                "RUNNING"
            ):

                raise ValueError(
                    "Backend did not confirm "
                    "RUNNING status."
                )

            self.session_id = (
                session_id
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
            OSError,
        ) as error:

            self.stop_monitoring()

            QMessageBox.warning(
                self,
                "ข้อผิดพลาดในการตรวจจับ",
                str(error),
            )

            return False

        # ====================================================
        # RESET SESSION STATE
        # ====================================================

        self.frame_count = 0

        self.session_started_at = (
            session.get(
                "started_at"
            )
            or
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            )
        )

        self.session_started_monotonic = (
            time.monotonic()
        )

        # ====================================================
        # SESSION RISK SCORE
        # ====================================================

        self.risk_score_collector.reset(
            session_started_at_monotonic=(
                self.session_started_monotonic
            )
        )

        # ====================================================
        # DETECTION STATISTICS
        # ====================================================

        self.detection_count = 0
        self.pose_detected_count = 0
        self.face_detected_count = 0

        self.shoulder_samples.clear()
        self.neck_samples.clear()

        # ====================================================
        # RISK
        # ====================================================

        self.risk_sample_counts = {
            level: 0
            for level in RISK_LEVELS
        }

        self.alert_notification_count = 0

        self.risk_persistence.reset()

        self.reset_risk_tracking()
        self.reset_screen_distance_tracking()

        # ====================================================
        # BLINK
        # ====================================================

        blink_started_at = (
            time.monotonic()
        )

        self.blink_detector.reset(
            preserve_count=False,
            now=blink_started_at,
        )

        self.last_blink_result = None

        self.blink_statistics.start(
            timestamp=blink_started_at
        )

        self.last_blink_statistics = None

        self.eye_alert_policy.reset()
        self.last_eye_alert_result = None
        self.close_eye_alert()

        self.eye_state_label.setText(
            "สถานะตา: กำลัง Calibration"
        )

        self.blink_count_label.setText(
            "จำนวนการกระพริบตา: 0"
        )

        # ====================================================
        # UI
        # ====================================================

        self.session_label.setText(
            f"Session ID: {self.session_id}"
        )

        self.status_label.setText(
            "สถานะ: กำลังตรวจจับ (RUNNING)"
        )

        self.is_paused = False

        self.pause_button.setText(
            "Pause Monitoring"
        )

        self.pause_button.setEnabled(
            True
        )

        self.stop_button.setEnabled(
            True
        )
        # ====================================================
        # NETWORK STATE
        # ====================================================

        if (
            self.network_recovery_timer.isActive()
        ):

            self.network_recovery_timer.stop()

        self.network_gap_active = False
        self.network_gap_started_at = None
        self.network_gap_last_error = None
        self.network_stop_pending = False
        self.pending_stop_summary = None
        self.timer.start()

        self.state_changed.emit()

        print(
            "MONITORING STARTED: SESSION ID",
            self.session_id,
        )

        return True


    # ========================================================
    # PIPELINE RESET
    # ========================================================

    def reset_risk_tracking(
        self,
        *_args,
    ) -> None:

        self.close_posture_alert()

        self.sound_player.notify(
            False
        )

        self.risk_pipeline.reset()

        self.last_pipeline_result = None

        self.assessment_label.setText(
            "Assessment: Waiting"
        )

        self.factor_label.setText(
            "Posture Factors: -"
        )

        self.duration_label.setText(
            "Longest Continuous Factor: -"
        )

        self.risk_label.setText(
            "Risk Level: -"
        )

        self.event_label.setText(
            "Risk Event: -"
        )

        self.alert_label.setText(
            "Alert Policy: Waiting"
        )

    # ========================================================
    # SETTINGS
    # ========================================================

    def apply_notification_settings(
        self,
        settings: dict,
    ) -> None:

        self.sound_player.apply_settings(
            settings
        )

        if (
            not
            self.sound_player.settings[
                "notifications_enabled"
            ]
        ):

            self.close_posture_alert()
            self.close_eye_alert()

    # ========================================================
    # PIPELINE UI HELPERS
    # ========================================================

    @staticmethod
    def _factor_text(
        factors: list[dict],
    ) -> str:

        if not factors:

            return "ไม่มี"

        names = []

        for factor in factors:

            factor_name = (
                factor.get(
                    "factor"
                )
            )

            names.append(
                FACTOR_THAI.get(
                    factor_name,
                    str(
                        factor_name
                    ),
                )
            )

        return ", ".join(
            names
        )

    @staticmethod
    def _factor_names(
        factors: list[dict],
    ) -> list[str]:

        output = []

        for factor in factors:

            name = (
                factor.get(
                    "factor"
                )
            )

            if isinstance(
                name,
                str,
            ):

                output.append(
                    name
                )

        return output

    @staticmethod
    def _longest_continuous_seconds(
        temporal_result: dict,
    ) -> float:

        active_factors = (
            temporal_result.get(
                "active_factors"
            )
            or
            []
        )

        values = []

        for factor in active_factors:

            value = (
                factor.get(
                    "continuous_seconds"
                )
            )

            if (
                type(value)
                in
                (int, float)
                and
                math.isfinite(
                    value
                )
            ):

                values.append(
                    float(
                        value
                    )
                )

        return (
            max(
                values
            )
            if values
            else
            0.0
        )

    # ========================================================
    # VALIDATED RISK PIPELINE
    # ========================================================

    def update_validated_risk(
        self,
        detection_result: dict,
    ) -> dict:

        # ====================================================
        # DETECTION -> COMPLETE PIPELINE
        # ====================================================

        pipeline_result = (
            self.risk_pipeline.process_detection(
                detection_result,
                self.baseline_data,
            )
        )

        self.last_pipeline_result = (
            pipeline_result
        )

        # ====================================================
        # SESSION RISK SCORE COLLECTOR
        # ====================================================

        try:

            self.risk_score_collector.add_pipeline_result(
                pipeline_result
            )

        except Exception as error:

            print(
                "RISK SCORE COLLECTOR ERROR:",
                error,
            )

        # ====================================================
        # DATABASE PERSISTENCE
        # ====================================================

                # ====================================================
        # DATABASE PERSISTENCE
        #
        # Persistence failure must NOT stop local Detection /
        # Assessment / Risk calculation.
        # ====================================================

        if self.session_id is not None:

            try:

                self.risk_persistence.process_pipeline_result(
                    session_id=(
                        self.session_id
                    ),
                    pipeline_result=(
                        pipeline_result
                    ),
                )

            except requests.RequestException as error:

                print(
                    "RISK PERSISTENCE NETWORK ERROR:",
                    error,
                )

                self._mark_network_gap(
                    error
                )

            except Exception as error:

                # Application / contract errors are not treated
                # as Internet loss.
                print(
                    "RISK PERSISTENCE ERROR:",
                    error,
                )

        assessment = (
            pipeline_result[
                "assessment"
            ]
        )

        temporal = (
            pipeline_result[
                "temporal"
            ]
        )

        risk = (
            pipeline_result[
                "risk"
            ]
        )

        risk_event = (
            pipeline_result[
                "risk_event"
            ]
        )

        alert = (
            pipeline_result[
                "alert_policy"
            ]
        )

        # ====================================================
        # ASSESSMENT
        # ====================================================

        self.assessment_label.setText(
            "Assessment: "
            f"{assessment.get('status')} "
            f"({assessment.get('reason')})"
        )

        factors = (
            assessment.get(
                "factors"
            )
            or
            []
        )

        self.factor_label.setText(
            "Posture Factors: "
            +
            self._factor_text(
                factors
            )
        )

        # ====================================================
        # TEMPORAL
        # ====================================================

        longest_seconds = (
            self._longest_continuous_seconds(
                temporal
            )
        )

        self.duration_label.setText(
            "Longest Continuous Factor: "
            f"{longest_seconds:.1f} s"
        )

        # ====================================================
        # RISK
        # ====================================================

        risk_level = (
            risk.get(
                "risk_level"
            )
        )

        if (
            risk.get(
                "risk_level_available"
            )
            is True
            and
            risk_level
            in
            RISK_LEVELS
        ):

            self.risk_label.setText(
                "Risk Level: "
                f"{risk_level} "
                "(PostGuard Prototype)"
            )

            self.risk_sample_counts[
                risk_level
            ] += 1

        else:

            self.risk_label.setText(
                "Risk Level: N/A "
                f"({risk.get('status')})"
            )

        # ====================================================
        # RISK EVENT
        # ====================================================

        event_action = (
            risk_event.get(
                "event_action"
            )
        )

        event = (
            risk_event.get(
                "event"
            )
        )

        event_id = (
            event.get(
                "runtime_event_id"
            )
            if isinstance(
                event,
                dict,
            )
            else
            None
        )

        if event_id is not None:

            self.event_label.setText(
                "Risk Event: "
                f"{event_action} | "
                f"{event_id}"
            )

        else:

            self.event_label.setText(
                "Risk Event: "
                f"{event_action}"
            )

        # ====================================================
        # EVENT RESOLVED
        # ====================================================

        if (
            event_action
            ==
            "RESOLVED"
        ):

            self.close_posture_alert()

            self.sound_player.notify(
                False
            )

        # ====================================================
        # ALERT POLICY
        # ====================================================

        decision = (
            alert.get(
                "decision"
            )
        )

        alert_type = (
            alert.get(
                "alert_type"
            )
        )

        should_notify = (
            alert.get(
                "should_notify"
            )
            is True
        )

        if should_notify:

            self.alert_label.setText(
                "Alert Policy: "
                f"{decision} | "
                f"{alert_type} | "
                f"{alert.get('current_risk_level')}"
            )

            self.alert_notification_count += 1

            self.show_posture_alert(
                risk_level=(
                    alert.get(
                        "current_risk_level"
                    )
                ),
                alert_type=(
                    alert_type
                ),
                factors=(
                    self._factor_names(
                        factors
                    )
                ),
                duration_seconds=(
                    longest_seconds
                ),
            )

            self.sound_player.play_alert()

        else:

            self.alert_label.setText(
                "Alert Policy: "
                f"{decision}"
            )

        return pipeline_result

    # ========================================================
    # ALERT TOAST
    # ========================================================

    def _handle_posture_alert_finished(
        self,
        _result: int,
    ) -> None:
        """
        Presentation cleanup after the user acknowledges the
        toast or after auto-close.

        Closing a notification must NOT:
        - resolve Risk Event,
        - reset Alert Policy,
        - reset cooldown,
        - pause Monitoring.
        """

        self.sound_player.stop_alert()

        popup = self.sender()

        if (
            self.alert_popup
            is popup
        ):

            self.alert_popup = None

        if popup is not None:

            delete_later = getattr(
                popup,
                "deleteLater",
                None,
            )

            if callable(
                delete_later
            ):

                delete_later()

    def close_posture_alert(
        self,
    ) -> None:
        """
        Close only the current user-facing toast.

        Alert Policy and Risk Event state remain unchanged.
        """

        popup = (
            self.alert_popup
        )

        self.alert_popup = None

        self.sound_player.stop_alert()

        if popup is None:

            return

        popup.close()

    def show_posture_alert(
        self,
        *,
        risk_level: str | None,
        alert_type: str | None,
        factors: list[str] | None,
        duration_seconds: float,
    ) -> bool:
        """
        Show one compact non-intrusive PostGuard toast.

        Only one toast may be visible at a time.
        """

        notifications_enabled = (
            self.sound_player.settings.get(
                "notifications_enabled",
                True,
            )
        )

        if not notifications_enabled:

            self.close_posture_alert()

            return False

        # Never stack notifications.
        self.close_posture_alert()

        popup = PostureAlertDialog(
            risk_level=(
                risk_level
            ),
            alert_type=(
                alert_type
            ),
            factors=(
                factors
            ),
            duration_seconds=(
                duration_seconds
            ),

            # Intentionally no parent.
            #
            # Binding the toast to MonitoringPage can cause the
            # main PostGuard window to be activated/restored.
            parent=None,
        )

        popup.finished.connect(
            self._handle_posture_alert_finished
        )

        self.alert_popup = (
            popup
        )

        popup.show_alert()

        return True

    # ========================================================
    # ALERT POPUP
    # ========================================================

    def close_posture_alert(
        self,
    ) -> None:

        popup = self.alert_popup

        if popup is None:
            self.sound_player.stop_alert()
            return

        self.alert_popup = None

        self.sound_player.stop_alert()

        popup.close()

    def show_posture_alert(
        self,
        *,
        risk_level: str | None,
        alert_type: str | None,
        factors: list[str] | None,
        duration_seconds: float,
    ) -> bool:

        notifications_enabled = (
            self.sound_player.settings.get(
                "notifications_enabled",
                True,
            )
        )

        if not notifications_enabled:

            self.close_posture_alert()

            return False

        # Never stack user-facing notifications.
        self.close_posture_alert()

        popup = PostureAlertDialog(
            risk_level=risk_level,
            alert_type=alert_type,
            factors=factors,
            duration_seconds=duration_seconds,

            # Important:
            # Do not bind the alert window to MonitoringPage.
            # The popup must not activate/restore Main Window.
            parent=None,
        )

        popup.finished.connect(
            self._handle_posture_alert_finished
        )

        self.alert_popup = popup

        popup.show_alert()

        return True

    # ========================================================
    # EYE ALERT TOAST
    # ========================================================

    def _handle_eye_alert_finished(
        self,
        _result: int,
    ) -> None:
        """
        Closing Eye Reminder affects presentation only.

        It must NOT:
        - reset Eye Alert Policy,
        - reset Blink Detection,
        - pause Monitoring.
        """

        self.sound_player.stop_alert()

        popup = self.sender()

        if self.eye_alert_popup is popup:

            self.eye_alert_popup = None

        if popup is not None:

            delete_later = getattr(
                popup,
                "deleteLater",
                None,
            )

            if callable(
                delete_later
            ):

                delete_later()


    def close_eye_alert(
        self,
    ) -> None:

        popup = (
            self.eye_alert_popup
        )

        self.eye_alert_popup = None

        self.sound_player.stop_alert()

        if popup is None:

            return

        popup.close()


    def show_eye_alert(
        self,
        *,
        blink_rate_per_minute: float | None,
        alert_type: str | None,
        window_blink_count: int | None,
    ) -> bool:

        notifications_enabled = (
            self.sound_player.settings.get(
                "notifications_enabled",
                True,
            )
        )

        if not notifications_enabled:

            self.close_eye_alert()

            return False

        # Do not stack Eye Reminder notifications.
        self.close_eye_alert()

        popup = EyeAlertDialog(
            blink_rate_per_minute=(
                blink_rate_per_minute
            ),
            alert_type=(
                alert_type
            ),
            window_blink_count=(
                window_blink_count
            ),
            parent=None,
        )

        popup.finished.connect(
            self._handle_eye_alert_finished
        )

        self.eye_alert_popup = (
            popup
        )

        popup.show_alert()

        return True

    # ========================================================
    # BASELINE COMPARISON
    # ========================================================

    def update_baseline_comparison(
        self,
        result: dict,
    ) -> None:

        if self.baseline_data is None:

            return

        current_shoulder = (
            result.get(
                "shoulder_tilt"
            )
        )

        neck_result = (
            result.get(
                "neck_lateral_tilt"
            )
        )

        current_neck = (
            neck_result.get(
                "neck_tilt"
            )
            if isinstance(
                neck_result,
                dict,
            )
            else
            None
        )

        current_flexion = (
            result.get(
                "neck_flexion"
            )
        )

        baseline_shoulder = (
            self.baseline_data.get(
                "shoulder_angle"
            )
        )

        baseline_neck = (
            self.baseline_data.get(
                "lateral_tilt_baseline"
            )
        )

        baseline_flexion = (
            self.baseline_data.get(
                "neck_flexion_baseline"
            )
        )

        # ====================================================
        # SHOULDER
        # ====================================================

        if (
            type(current_shoulder)
            in
            (int, float)
            and
            type(baseline_shoulder)
            in
            (int, float)
            and
            math.isfinite(
                current_shoulder
            )
            and
            math.isfinite(
                baseline_shoulder
            )
        ):

            difference = (
                current_shoulder
                -
                baseline_shoulder
            )

            self.shoulder_difference_label.setText(
                "Shoulder Difference: "
                f"{difference:+.2f}°"
            )

        else:

            self.shoulder_difference_label.setText(
                "ผลต่างจาก Baseline ไหล่: --"
            )

        # ====================================================
        # NECK LATERAL
        # ====================================================

        if (
            type(current_neck)
            in
            (int, float)
            and
            type(baseline_neck)
            in
            (int, float)
            and
            math.isfinite(
                current_neck
            )
            and
            math.isfinite(
                baseline_neck
            )
        ):

            difference = (
                current_neck
                -
                baseline_neck
            )

            self.neck_difference_label.setText(
                "Neck Difference: "
                f"{difference:+.2f}°"
            )

        else:

            self.neck_difference_label.setText(
                "ผลต่างจาก Baseline คอด้านข้าง: --"
            )

        # ====================================================
        # FLEXION / EXTENSION
        # ====================================================

        if (
            type(current_flexion)
            in
            (int, float)
            and
            type(baseline_flexion)
            in
            (int, float)
            and
            math.isfinite(
                current_flexion
            )
            and
            math.isfinite(
                baseline_flexion
            )
        ):

            difference = (
                current_flexion
                -
                baseline_flexion
            )

            self.flexion_difference_label.setText(
                "Neck Flexion Difference: "
                f"{difference:+.2f}°"
            )

        else:

            self.flexion_difference_label.setText(
                "ผลต่างจาก Baseline ก้ม/เงยคอ: --"
            )

    # ========================================================
    # DETECTION STATISTICS
    # ========================================================

    def record_detection_sample(
        self,
        result: dict,
    ) -> None:

        self.detection_count += 1

        if (
            result.get(
                "pose_points"
            )
            is not None
        ):

            self.pose_detected_count += 1

        if result.get(
            "face_detected"
        ):

            self.face_detected_count += 1

        shoulder = (
            result.get(
                "shoulder_tilt"
            )
        )

        if (
            type(shoulder)
            in
            (int, float)
            and
            math.isfinite(
                shoulder
            )
        ):

            self.shoulder_samples.append(
                float(
                    shoulder
                )
            )

        neck_result = (
            result.get(
                "neck_lateral_tilt"
            )
        )

        neck = (
            neck_result.get(
                "neck_tilt"
            )
            if isinstance(
                neck_result,
                dict,
            )
            else
            None
        )

        if (
            type(neck)
            in
            (int, float)
            and
            math.isfinite(
                neck
            )
        ):

            self.neck_samples.append(
                float(
                    neck
                )
            )

    # ========================================================
    # BLINK DETECTION
    # ========================================================

    def update_blink_detection(
        self,
        detection_result: dict,
    ) -> dict:

        now = time.monotonic()

        blink_result = (
            self.blink_detector.process_detection(
                detection_result,
                now=now,
            )
        )

        self.last_blink_result = (
            blink_result
        )

        blink_timestamp = (
            blink_result.get(
                "timestamp_monotonic"
            )
        )

        if (
            type(blink_timestamp)
            in (int, float)
            and
            math.isfinite(
                float(blink_timestamp)
            )
        ):
            self.last_blink_statistics = (
                self.blink_statistics.update(
                    blink_event=bool(
                        blink_result.get(
                            "blink_event"
                        )
                    ),
                    timestamp=float(
                        blink_timestamp
                    ),
                )
            )

        calibrated = (
            blink_result.get(
                "calibrated"
            )
            is True
        )

        eye_alert_result = (
            self.eye_alert_policy.update(
                blink_result,
                now=now,
            )
        )

        self.last_eye_alert_result = (
            eye_alert_result
        )

        # ========================================================
        # CALIBRATION
        # ========================================================

        if not calibrated:

            progress = (
                blink_result.get(
                    "calibration_progress"
                )
                or
                0.0
            )

            calibration_text = (
                f"กำลัง Calibration "
                f"{progress * 100:.0f}%"
            )

            self.right_eye_state_label.setText(
                f"ตาขวา: {calibration_text}"
            )

            self.left_eye_state_label.setText(
                f"ตาซ้าย: {calibration_text}"
            )

            self.eye_state_label.setText(
                f"สถานะตารวม: {calibration_text}"
            )

            self.eye_pattern_label.setText(
                "รูปแบบตา: CALIBRATING"
            )

        else:

            right_state = (
                blink_result.get(
                    "right_eye_state"
                )
                or
                "UNKNOWN"
            )

            left_state = (
                blink_result.get(
                    "left_eye_state"
                )
                or
                "UNKNOWN"
            )

            combined_state = (
                blink_result.get(
                    "eye_state"
                )
                or
                "UNKNOWN"
            )

            eye_pattern = (
                blink_result.get(
                    "eye_pattern"
                )
                or
                "UNKNOWN"
            )

            self.right_eye_state_label.setText(
                f"ตาขวา: {right_state}"
            )

            self.left_eye_state_label.setText(
                f"ตาซ้าย: {left_state}"
            )

            self.eye_state_label.setText(
                f"สถานะตารวม: {combined_state}"
            )

            pattern_text = {
                "BOTH_OPEN": (
                    "ตาทั้งสองเปิด"
                ),

                "BOTH_CLOSED": (
                    "ตาทั้งสองปิด"
                ),

                "RIGHT_ONLY_CLOSED": (
                    "ปิดเฉพาะตาขวา"
                ),

                "LEFT_ONLY_CLOSED": (
                    "ปิดเฉพาะตาซ้าย"
                ),

                "UNKNOWN": (
                    "ไม่สามารถระบุได้"
                ),
            }.get(
                eye_pattern,
                eye_pattern,
            )

            self.eye_pattern_label.setText(
                "รูปแบบตา: "
                f"{pattern_text}"
            )

        # ========================================================
        # OPENNESS
        # ========================================================

        right_openness = (
            blink_result.get(
                "right_eye_openness"
            )
        )

        left_openness = (
            blink_result.get(
                "left_eye_openness"
            )
        )

        if (
            type(right_openness)
            in
            (int, float)
            and
            type(left_openness)
            in
            (int, float)
            and
            math.isfinite(
                right_openness
            )
            and
            math.isfinite(
                left_openness
            )
        ):

            self.eye_openness_label.setText(
                "Eye Openness: "
                f"R={right_openness:.3f} | "
                f"L={left_openness:.3f}"
            )

        else:

            self.eye_openness_label.setText(
                "Eye Openness: --"
            )

        # ========================================================
        # BLINK
        # ========================================================

        blink_count = (
            blink_result.get(
                "blink_count"
            )
            or
            0
        )

        blink_event = (
            blink_result.get(
                "blink_event"
            )
            is True
        )

        if blink_event:

            duration = (
                blink_result.get(
                    "blink_duration_seconds"
                )
            )

            if (
                type(duration)
                in
                (int, float)
            ):

                self.blink_count_label.setText(
                    "จำนวนการกระพริบตา: "
                    f"{blink_count} "
                    f"| Blink {duration:.2f}s"
                )

            else:

                self.blink_count_label.setText(
                    "จำนวนการกระพริบตา: "
                    f"{blink_count}"
                )

        else:

            self.blink_count_label.setText(
                "จำนวนการกระพริบตา: "
                f"{blink_count}"
            )
        if eye_alert_result.get(
            "should_notify"
        ) is True:

            if self.session_id is not None:
                try:
                    response = (
                        APIClient
                        .create_eye_alert_notification(
                            session_id=self.session_id,
                            alert_type=eye_alert_result.get(
                                "alert_type"
                            ),
                            blink_rate=float(
                                eye_alert_result.get(
                                    "blink_rate_per_minute"
                                )
                                or 0.0
                            ),
                            window_blink_count=int(
                                eye_alert_result.get(
                                    "window_blink_count"
                                )
                                or 0
                            ),
                            reason=eye_alert_result.get(
                                "reason"
                            ),
                        )
                    )

                    if not response.ok:
                        raise RuntimeError(
                            "Persist Eye Reminder failed: "
                            f"HTTP {response.status_code} "
                            f"{response.text}"
                        )

                except requests.RequestException as error:
                    print(
                        "EYE ALERT PERSISTENCE NETWORK ERROR:",
                        error,
                    )
                    self._mark_network_gap(
                        error
                    )

                except Exception as error:
                    print(
                        "EYE ALERT PERSISTENCE ERROR:",
                        error,
                    )

            popup_shown = self.show_eye_alert(
                blink_rate_per_minute=eye_alert_result.get(
                    "blink_rate_per_minute"
                ),
                alert_type=eye_alert_result.get(
                    "alert_type"
                ),
                window_blink_count=eye_alert_result.get(
                    "window_blink_count"
                ),
            )

            if popup_shown:
                self.sound_player.play_alert()

        return blink_result

    # ========================================================
    # SCREEN DISTANCE
    # ========================================================

    def reset_screen_distance_tracking(
        self,
    ) -> None:
        """
        Reset Screen Distance temporal continuity.

        ใช้เมื่อ:
        - เริ่ม Session
        - Pause
        - Resume
        - จบ Session

        Personal Baseline ไม่ถูก reset เพราะ baseline เป็น
        reference ของ Session ไม่ใช่ temporal runtime state.
        """

        self.screen_distance_policy.reset()

        self.last_screen_distance_result = None

        self.screen_distance_label.setText(
            "ระยะห่างหน้าจอ: --"
        )


    def update_screen_distance(
        self,
        detection_result: dict,
    ) -> dict:
        """
        Evaluate relative Screen Distance.

        Pipeline:

            DetectionService.eye_distance
                        +
            Personal Baseline
                        ↓
            ScreenDistancePolicy
                        ↓
            NORMAL / PENDING /
            TOO_CLOSE / NOT_EVALUATED

        Screen Distance ไม่ถูกส่งเข้า Risk/RULA.
        """

        baseline = (
            self.baseline_data
            or {}
        )

        (
            baseline_value,
            baseline_source,
            baseline_reason,
        ) = (
            extract_eye_distance_baseline(
                baseline
            )
        )

        # --------------------------------------------
        # Baseline unavailable
        # --------------------------------------------

        if baseline_value is None:
            result = (
                self.screen_distance_policy.update(
                    current_eye_distance_px=None,
                    baseline_eye_distance_px=None,
                    now=time.monotonic(),
                )
            )

            result[
                "baseline_source"
            ] = baseline_source

            result[
                "baseline_reason"
            ] = baseline_reason

            self.last_screen_distance_result = (
                result
            )

            self.screen_distance_label.setText(
                "ระยะห่างหน้าจอ: N/A "
                "(ไม่มี Eye Distance Baseline)"
            )

            return result

        # --------------------------------------------
        # Detection Contract
        # --------------------------------------------

        features = (
            detection_result.get(
                "features"
            )
            or {}
        )

        eye_feature = (
            features.get(
                "eye_distance"
            )
        )

        current_eye_distance = None

        if (
            isinstance(
                eye_feature,
                dict,
            )
            and
            eye_feature.get(
                "valid"
            )
            is True
        ):
            value = eye_feature.get(
                "value"
            )

            if (
                type(value)
                in
                (int, float)
                and
                math.isfinite(
                    value
                )
                and
                value > 0
            ):
                current_eye_distance = (
                    float(value)
                )

        # --------------------------------------------
        # Policy
        # --------------------------------------------

        result = (
            self.screen_distance_policy.update(
                current_eye_distance_px=(
                    current_eye_distance
                ),
                baseline_eye_distance_px=(
                    baseline_value
                ),
                now=time.monotonic(),
            )
        )

        result[
            "baseline_source"
        ] = baseline_source

        result[
            "baseline_reason"
        ] = baseline_reason

        self.last_screen_distance_result = (
            result
        )

        # --------------------------------------------
        # UI
        # --------------------------------------------

        state = result.get(
            "state"
        )

        ratio = result.get(
            "ratio"
        )

        if state == STATE_NORMAL:
            self.screen_distance_label.setText(
                "ระยะห่างหน้าจอ: ปกติ "
                f"(Ratio {ratio:.2f}x)"
            )

        elif state == STATE_PENDING:
            seconds = (
                result.get(
                    "candidate_seconds"
                )
                or 0.0
            )

            self.screen_distance_label.setText(
                "ระยะห่างหน้าจอ: "
                "กำลังตรวจสอบว่าใกล้เกินไป "
                f"(Ratio {ratio:.2f}x, "
                f"{seconds:.1f}s)"
            )

        elif state == STATE_TOO_CLOSE:
            self.screen_distance_label.setText(
                "ระยะห่างหน้าจอ: "
                "ใกล้กว่าค่าอ้างอิงมาก "
                f"(Ratio {ratio:.2f}x)"
            )

        elif state == STATE_NOT_EVALUATED:
            self.screen_distance_label.setText(
                "ระยะห่างหน้าจอ: "
                "ไม่สามารถประเมินได้"
            )

        else:
            self.screen_distance_label.setText(
                "ระยะห่างหน้าจอ: --"
            )

        return result

        # ========================================================
    # CAMERA DATA GAP
    # ========================================================

     # ========================================================
    # CAMERA DATA GAP
    # ========================================================

    def _enter_camera_gap(
        self,
    ) -> None:

        now = time.monotonic()
        self.camera_loss_tracker.begin(
            now
        )

        # ====================================================
        # FIRST FAILED FRAME
        # ====================================================

        if self.camera_gap_started_at is None:

            self.camera_gap_started_at = (
                now
            )

            self.camera_gap_last_retry_at = (
                None
            )

            # ระหว่างกล้องหลุด
            # ไม่อนุญาตให้ Pause/Resume
            # เพราะระบบกำลังอยู่ใน automatic recovery
            self.pause_button.setEnabled(
                False
            )
            self.state_changed.emit()

            self.preview_label.clear()

            self.preview_label.setText(
                "กล้องขาดการเชื่อมต่อ\n"
                "กำลังพยายามเชื่อมต่อใหม่..."
            )

            self.status_label.setText(
                "สถานะ: DATA GAP "
                "(กล้องขาดการเชื่อมต่อ)"
            )

            self.assessment_label.setText(
                "Assessment: NOT_EVALUATED "
                "(CAMERA_DATA_GAP)"
            )

            self.factor_label.setText(
                "Posture Factors: DATA_GAP"
            )

            self.duration_label.setText(
                "Longest Continuous Factor: 0.0 s"
            )

            self.risk_label.setText(
                "Risk Level: N/A "
                "(DATA_GAP)"
            )

            self.event_label.setText(
                "Risk Event: DATA_GAP"
            )

            self.alert_label.setText(
                "Alert Policy: DATA_GAP"
            )

            self.screen_distance_label.setText(
                "ระยะห่างหน้าจอ: DATA_GAP"
            )

            self.eye_state_label.setText(
                "สถานะตา: DATA_GAP"
            )

            # หยุด alert presentation
            # ระหว่างที่ไม่มีข้อมูลใหม่
            self.sound_player.notify(
                False
            )

            self.close_posture_alert()
            self.close_eye_alert()

            self.last_eye_alert_result = (
                self.eye_alert_policy.process_data_gap(
                    now=now,
                    reason="CAMERA_DATA_GAP",
                )
            )
            self.blink_statistics.reset()
            self.last_blink_statistics = None

            # ====================================================
            # INFORM VALIDATED PIPELINE
            #
            # สำคัญ:
            #
            # DATA_GAP ไม่ใช่ LOW/NONE
            # และไม่ใช่ posture ปกติ
            #
            # Temporal ถูกตัด continuity
            # แต่ Risk Event เดิมยังคงอยู่
            # ====================================================

            try:

                gap_result = (
                    self.risk_pipeline.process_data_gap(
                        reason=(
                            "CAMERA_DATA_GAP"
                        ),
                        now=now,
                    )
                )

                self.last_pipeline_result = (
                    gap_result
                )

                if (
                    self.session_id
                    is not None
                ):

                    self.risk_persistence.process_pipeline_result(
                        session_id=(
                            self.session_id
                        ),
                        pipeline_result=(
                            gap_result
                        ),
                    )

            except requests.RequestException as error:

                print(
                    "CAMERA DATA GAP "
                    "PERSISTENCE NETWORK ERROR:",
                    error,
                )

                self._mark_network_gap(
                    error
                )

            except Exception as error:

                print(
                    "CAMERA DATA GAP PIPELINE ERROR:",
                    error,
                )

        # ====================================================
        # GAP ELAPSED TIME
        # ====================================================

        elapsed = (
            now
            -
            self.camera_gap_started_at
        )

        remaining = max(
            0.0,
            CAMERA_LOSS_GRACE_SECONDS
            -
            elapsed,
        )

        self.status_label.setText(
            "สถานะ: กล้องขาดการเชื่อมต่อ "
            f"| รอเชื่อมต่อใหม่ "
            f"{remaining:.0f}s"
        )

        # ====================================================
        # TIMEOUT
        # ====================================================

        if (
            elapsed
            >=
            CAMERA_LOSS_GRACE_SECONDS
        ):

            self._camera_gap_timeout()

            return

        # ====================================================
        # RECONNECT INTERVAL
        # ====================================================

        if (
            self.camera_gap_last_retry_at
            is not None
            and
            now
            -
            self.camera_gap_last_retry_at
            <
            CAMERA_RECONNECT_INTERVAL_SECONDS
        ):

            return

        self.camera_gap_last_retry_at = (
            now
        )

        self._try_reconnect_camera()


    # ========================================================
    # TRY CAMERA RECONNECT
    # ========================================================

    def _try_reconnect_camera(
        self,
    ) -> None:

        camera = (
            self.selected_camera
            or
            {}
        )

        baseline = (
            self.baseline_data
            or
            {}
        )

        device_index = (
            camera.get(
                "device_index"
            )
        )

        if (
            type(device_index)
            is not int
            or
            device_index < 0
        ):

            return

        # ====================================================
        # REOPEN WITH BASELINE RESOLUTION
        #
        # Personal Baseline resolution เป็น source of truth
        # สำหรับ Monitoring Session นี้
        # ====================================================

        width = (
            baseline.get(
                "camera_frame_width"
            )
            or
            camera.get(
                "resolution_width"
            )
        )

        height = (
            baseline.get(
                "camera_frame_height"
            )
            or
            camera.get(
                "resolution_height"
            )
        )

        # ====================================================
        # CLOSE STALE CAPTURE
        # ====================================================

        if self.capture is not None:

            try:

                self.capture.release()

            except Exception:

                pass

            self.capture = None

        # ====================================================
        # OPEN CAMERA
        #
        # Windows:
        # DirectShow first
        # fallback CAP_ANY
        # ====================================================

        capture = cv2.VideoCapture(
            int(device_index),
            cv2.CAP_DSHOW,
        )

        if not capture.isOpened():

            capture.release()

            capture = cv2.VideoCapture(
                int(device_index),
                cv2.CAP_ANY,
            )

        if not capture.isOpened():

            capture.release()

            return

        # ====================================================
        # APPLY EXPECTED RESOLUTION
        # ====================================================

        if (
            type(width) is int
            and
            type(height) is int
            and
            width > 0
            and
            height > 0
        ):

            capture.set(
                cv2.CAP_PROP_FOURCC,
                cv2.VideoWriter_fourcc(
                    *"MJPG"
                ),
            )

            capture.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                width,
            )

            capture.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                height,
            )

            capture.set(
                cv2.CAP_PROP_FPS,
                30,
            )

        # ====================================================
        # READ REAL FRAME
        # ====================================================

        success, frame = (
            capture.read()
        )

        if (
            not success
            or
            frame is None
        ):

            capture.release()

            return

        # ====================================================
        # RESOLUTION COMPATIBILITY
        #
        # ห้าม resume ด้วย resolution
        # ที่ไม่ตรง Personal Baseline
        # ====================================================

        try:

            result = (
                evaluate_resolution_compatibility(
                    self.baseline_data,
                    frame,
                )
            )

        except Exception as error:

            print(
                "CAMERA RECONNECT "
                "RESOLUTION ERROR:",
                error,
            )

            capture.release()

            return

        if (
            result.get(
                "status"
            )
            !=
            RESOLUTION_COMPATIBLE
            or
            result.get(
                "compatible"
            )
            is not True
        ):

            capture.release()

            return

        # ====================================================
        # ACCEPT NEW CAPTURE
        # ====================================================

        self.capture = (
            capture
        )

        self._recover_from_camera_gap()


    # ========================================================
    # CAMERA GAP RECOVERED
    # ========================================================

    def _recover_from_camera_gap(
        self,
    ) -> None:

        if self.capture is None:

            return

        self.camera_gap_started_at = (
            None
        )

        self.camera_gap_last_retry_at = (
            None
        )

        # ====================================================
        # TEMPORAL CONTINUITY
        #
        # process_data_gap() ตัด Temporal ไปแล้ว
        #
        # Risk Event เดิม intentionally preserve
        # ====================================================

        # ====================================================
        # SCREEN DISTANCE
        #
        # ห้ามเอาเวลา/ratio ก่อน gap มาต่อ
        # ====================================================

        self.screen_distance_policy.reset()

        self.last_screen_distance_result = (
            None
        )

        # ====================================================
        # BLINK
        #
        # เก็บจำนวน Blink ของ Session เดิม
        # แต่ recalibrate หลัง stream กลับมา
        # ====================================================

        self.blink_detector.reset(
            preserve_count=True,
            now=time.monotonic(),
        )

        self.last_blink_result = (
            None
        )

        self.eye_alert_policy.reset()
        self.last_eye_alert_result = None
        self.close_eye_alert()

        # ====================================================
        # CAMERA MOVEMENT GUARD
        #
        # Camera stream ถูกสร้างใหม่
        #
        # ห้ามเอา optical-flow frame ก่อน disconnect
        # มาเทียบกับ frame หลัง reconnect เพราะ driver /
        # exposure / autofocus / timing อาจเปลี่ยนทันที
        # และทำให้เกิด false CAMERA_MOVED
        #
        # Reset เฉพาะ runtime movement reference
        #
        # Camera Reference และ Personal Baseline เดิม
        # ยังอยู่เหมือนเดิม
        # ====================================================

        self.camera_movement_guard.reset()

        # ====================================================
        # CONTROLS
        # ====================================================

        self.pause_button.setEnabled(
            True
        )

        # ====================================================
        # UI
        # ====================================================

        self.preview_label.setText(
            "เชื่อมต่อกล้องกลับมาแล้ว "
            "กำลังตรวจจับต่อ..."
        )

        self.status_label.setText(
            "สถานะ: กล้องกลับมาแล้ว "
            "(RUNNING)"
        )

        self.eye_state_label.setText(
            "สถานะตา: กำลัง Calibration"
        )

        self.screen_distance_label.setText(
            "ระยะห่างหน้าจอ: "
            "กำลังประเมินใหม่"
        )

        self.camera_loss_tracker.recover(
            time.monotonic()
        )


    # ========================================================
    # CAMERA GAP TIMEOUT
    # ========================================================

    def _camera_gap_timeout(
        self,
    ) -> None:

        self.timer.stop()

        self.status_label.setText(
            "สถานะ: กล้องขาดการเชื่อมต่อ "
            "เกิน 60 วินาที "
            "กำลังจบเซสชัน"
        )

        if self.capture is not None:

            try:

                self.capture.release()

            except Exception:

                pass

            self.capture = None

        QMessageBox.warning(
            self,
            "กล้องขาดการเชื่อมต่อ",
            (
                "PostGuard ไม่สามารถเชื่อมต่อ"
                "กล้องกลับมาได้ภายใน 60 วินาที\n\n"
                "ระบบจะจบ Session ปัจจุบัน "
                "เพื่อป้องกันการประเมินจาก"
                "ข้อมูลที่ไม่ต่อเนื่อง"
            ),
        )

        self.handle_stop()

    def _try_reconnect_camera(
        self,
    ) -> None:

        camera = (
            self.selected_camera
            or
            {}
        )

        device_index = (
            camera.get(
                "device_index"
            )
        )

        if (
            type(device_index) is not int
            or
            device_index < 0
        ):
            return

        baseline = (
            self.baseline_data
            or
            {}
        )

        # Monitoring must recover using the same resolution that
        # produced the Personal Baseline.
        width = (
            baseline.get(
                "camera_frame_width"
            )
            or
            camera.get(
                "resolution_width"
            )
        )

        height = (
            baseline.get(
                "camera_frame_height"
            )
            or
            camera.get(
                "resolution_height"
            )
        )

        # Close stale capture.
        if self.capture is not None:

            try:
                self.capture.release()

            except Exception:
                pass

            self.capture = None

        capture = cv2.VideoCapture(
            int(device_index),
            cv2.CAP_DSHOW,
        )

        if not capture.isOpened():

            capture.release()

            capture = cv2.VideoCapture(
                int(device_index),
                cv2.CAP_ANY,
            )

        if not capture.isOpened():

            capture.release()
            return

        if (
            type(width) is int
            and
            type(height) is int
            and
            width > 0
            and
            height > 0
        ):

            capture.set(
                cv2.CAP_PROP_FOURCC,
                cv2.VideoWriter_fourcc(
                    *"MJPG"
                ),
            )

            capture.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                width,
            )

            capture.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                height,
            )

            capture.set(
                cv2.CAP_PROP_FPS,
                30,
            )

        success, frame = capture.read()

        if (
            not success
            or
            frame is None
        ):

            capture.release()
            return

        # ----------------------------------------------------
        # Resolution must still match Baseline.
        # ----------------------------------------------------

        try:

            result = (
                evaluate_resolution_compatibility(
                    self.baseline_data,
                    frame,
                )
            )

        except Exception:

            capture.release()
            return

        if (
            result.get(
                "status"
            )
            !=
            RESOLUTION_COMPATIBLE
            or
            result.get(
                "compatible"
            )
            is not True
        ):

            capture.release()
            return

        self.capture = capture

        self._recover_from_camera_gap()


    def _recover_from_camera_gap(
        self,
    ) -> None:

        if self.capture is None:
            return

        self.camera_gap_started_at = None
        self.camera_gap_last_retry_at = None

        # ----------------------------------------------------
        # Temporal continuity cannot cross the gap.
        #
        # process_data_gap() already resets Temporal.
        #
        # Risk Event itself is intentionally preserved.
        # ----------------------------------------------------

        self.screen_distance_policy.reset()

        self.last_screen_distance_result = None

        self.blink_detector.reset(
            preserve_count=True,
            now=time.monotonic(),
        )

        self.last_blink_result = None
        blink_started_at = (
            time.monotonic()
        )

        self.blink_statistics.start(
            timestamp=blink_started_at
        )

        self.last_blink_statistics = None
        # IMPORTANT:
        # Do not reset camera_movement_guard here. Keeping the
        # pre-gap reference allows the existing movement guard
        # to detect a physical camera-placement change after
        # reconnection. If the camera moved, the validated
        # camera-movement path will end the Session instead of
        # continuing with a stale Personal Baseline.

        self.pause_button.setEnabled(
            True
        )
        self.state_changed.emit()

        self.preview_label.setText(
            "เชื่อมต่อกล้องกลับมาแล้ว "
            "กำลังตรวจจับต่อ..."
        )

        self.status_label.setText(
            "สถานะ: กล้องกลับมาแล้ว "
            "(RUNNING)"
        )

        self.eye_state_label.setText(
            "สถานะตา: กำลัง Calibration"
        )

        self.screen_distance_label.setText(
            "ระยะห่างหน้าจอ: "
            "กำลังประเมินใหม่"
        )


    def _camera_gap_timeout(
        self,
    ) -> None:

        self.timer.stop()

        self.status_label.setText(
            "สถานะ: กล้องขาดการเชื่อมต่อ "
            "เกิน 60 วินาที กำลังจบเซสชัน"
        )

        if self.capture is not None:

            try:
                self.capture.release()

            except Exception:
                pass

            self.capture = None

        QMessageBox.warning(
            self,
            "กล้องขาดการเชื่อมต่อ",
            "PostGuard ไม่สามารถเชื่อมต่อกล้องกลับมาได้"
            "ภายใน 60 วินาที\n\n"
            "ระบบจะจบ Session ปัจจุบันเพื่อป้องกัน"
            "การประเมินจากข้อมูลที่ไม่ต่อเนื่อง",
        )

        self.handle_stop()

     # ========================================================
    # CAMERA LOOP
    # ========================================================

    def update_frame(
        self,
    ) -> None:

        # ====================================================
        # LIFECYCLE GUARD
        # ====================================================

        if (
            self.is_paused
            or
            self.is_stopping
        ):

            return

        # ====================================================
        # ACTIVE CAMERA DATA GAP
        #
        # สำคัญ:
        #
        # Timer ต้องยังทำงานต่อระหว่าง DATA_GAP
        # เพื่อให้:
        #
        # - retry camera ทุก 2 วินาที
        # - timeout 60 วินาทีทำงาน
        #
        # ห้าม return เพียงเพราะ capture=None
        # ====================================================

        if (
            self.camera_gap_started_at
            is not None
        ):

            self._enter_camera_gap()

            return

        # ====================================================
        # CAMERA OBJECT LOST
        # ====================================================

        if self.capture is None:

            self._enter_camera_gap()

            return

        # ====================================================
        # 1. READ RAW CAMERA FRAME
        # ====================================================

        success, raw_frame = (
            self.capture.read()
        )

        if (
            not success
            or
            raw_frame is None
        ):

            self._enter_camera_gap()

            return

        # ====================================================
        # 2. CAMERA MOVEMENT GUARD
        #
        # IMPORTANT:
        # - inspect RAW frame
        # - before Camera Roll correction
        # - before mirror
        # - before Detection / Risk
        # ====================================================

        movement_result = (
            self.camera_movement_guard.update(
                raw_frame
            )
        )

        if movement_result.get("status") in {
            "STABLE",
            "MOVED",
            "UNAVAILABLE",
        }:
            print(
                "[CAMERA_MOVEMENT]",
                "status=",
                movement_result.get("status"),
                "| reason=",
                movement_result.get("reason"),
                "| translation_px=",
                round(
                    float(
                        movement_result.get(
                            "translation_px",
                            0.0,
                        )
                    ),
                    2,
                ),
                "| ratio=",
                round(
                    float(
                        movement_result.get(
                            "translation_ratio",
                            0.0,
                        )
                    ),
                    5,
                ),
                "| rotation=",
                round(
                    float(
                        movement_result.get(
                            "rotation_deg",
                            0.0,
                        )
                    ),
                    2,
                ),
                "| scale_change=",
                round(
                    float(
                        movement_result.get(
                            "scale_change",
                            0.0,
                        )
                    )
                    * 100.0,
                    2,
                ),
                "%",
                "| inliers=",
                movement_result.get(
                    "inlier_count"
                ),
                "| inlier_ratio=",
                movement_result.get(
                    "inlier_ratio"
                ),
                "| spatial=",
                movement_result.get(
                    "spatial_support_valid"
                ),
                "| regions=",
                movement_result.get(
                    "active_regions"
                ),
                "| TL/TR/BL/BR=",
                movement_result.get(
                    "top_left_inliers"
                ),
                movement_result.get(
                    "top_right_inliers"
                ),
                movement_result.get(
                    "bottom_left_inliers"
                ),
                movement_result.get(
                    "bottom_right_inliers"
                ),
                "| votes=",
                movement_result.get(
                    "movement_votes"
                ),
                "/",
                movement_result.get(
                    "movement_window"
                ),
            )
        if (
            movement_result.get(
                "status"
            )
            ==
            STATUS_MOVED
        ):

            self._handle_camera_movement(
                movement_result
            )

            return

        # ====================================================
        # 3. APPLY LOCKED CAMERA REFERENCE
        #
        # Personal Baseline และ Monitoring
        # ต้องใช้ preprocessing contract เดียวกัน
        # ====================================================

        try:

            corrected_frame = (
                prepare_detection_frame(
                    raw_frame,
                    self.selected_camera,
                )
            )

        except CameraReferenceError as error:

            self._finish_after_capture_error()

            QMessageBox.warning(
                self,
                "Camera Reference",
                str(error),
            )

            return

        self.frame_count += 1

        # ====================================================
        # 4. DETECTION
        #
        # Process every 5 camera frames.
        # ====================================================

        if (
            self.detector is not None
            and
            self.frame_count % 5 == 0
        ):

            try:

                result = (
                    self.detector.process_frame(
                        corrected_frame
                    )
                )

                # --------------------------------------------
                # Session statistics
                # --------------------------------------------

                self.record_detection_sample(
                    result
                )

                # --------------------------------------------
                # Personal Baseline comparison
                # --------------------------------------------

                self.update_baseline_comparison(
                    result
                )

                # --------------------------------------------
                # Blink
                # --------------------------------------------

                self.update_blink_detection(
                    result
                )

                # --------------------------------------------
                # Relative screen distance
                # --------------------------------------------

                self.update_screen_distance(
                    result
                )

                # --------------------------------------------
                # Validated PostGuard Risk Pipeline
                # --------------------------------------------

                self.update_validated_risk(
                    result
                )

                # --------------------------------------------
                # UI
                # --------------------------------------------

                self._update_detection_labels(
                    result
                )

            except Exception as error:

                self._finish_after_capture_error()

                QMessageBox.warning(
                    self,
                    "ข้อผิดพลาดของระบบตรวจจับ",
                    str(error),
                )

                return

        # ====================================================
        # 5. PREVIEW
        #
        # Preview ใช้ corrected frame เดียวกับ Detection
        # แต่ mirror เฉพาะใน _update_preview()
        # ====================================================

        self._update_preview(
            corrected_frame
        )

    # ========================================================
    # CAMERA MOVEMENT
    # ========================================================

    def _handle_camera_movement(
        self,
        movement_result: dict,
    ) -> None:
        """Stop the current session when physical camera placement changes."""

        if self.camera_movement_triggered:
            return

        self.camera_movement_triggered = True

        # Stop local frame processing immediately so no new
        # posture/risk sample is produced with an invalid reference.
        self.timer.stop()

        translation_px = (
            movement_result.get(
                "translation_px"
            )
        )

        rotation_deg = (
            movement_result.get(
                "rotation_deg"
            )
        )

        scale_change = (
            movement_result.get(
                "scale_change"
            )
        )

        details = []

        if (
            type(translation_px)
            in
            (int, float)
            and
            math.isfinite(
                translation_px
            )
        ):
            details.append(
                "การเลื่อนภาพรวม: "
                f"{translation_px:.1f} px"
            )

        if (
            type(rotation_deg)
            in
            (int, float)
            and
            math.isfinite(
                rotation_deg
            )
        ):
            details.append(
                "การหมุนภาพรวม: "
                f"{rotation_deg:+.2f}°"
            )

        if (
            type(scale_change)
            in
            (int, float)
            and
            math.isfinite(
                scale_change
            )
        ):
            details.append(
                "การเปลี่ยนสเกล: "
                f"{scale_change * 100.0:.1f}%"
            )

        detail_text = (
            "\n".join(
                details
            )
            if details
            else
            "ตรวจพบการเปลี่ยนตำแหน่งของกล้อง"
        )

        self.status_label.setText(
            "สถานะ: ตรวจพบการขยับกล้อง "
            "กำลังจบเซสชัน"
        )

        self.assessment_label.setText(
            "Assessment: NOT_EVALUATED "
            "(CAMERA_MOVED)"
        )

        self.factor_label.setText(
            "Posture Factors: CAMERA_MOVED"
        )

        self.duration_label.setText(
            "Longest Continuous Factor: 0.0 s"
        )

        self.risk_label.setText(
            "Risk Level: N/A "
            "(CAMERA_MOVED)"
        )

        self.event_label.setText(
            "Risk Event: DATA_GAP"
        )

        self.alert_label.setText(
            "Alert Policy: CAMERA_MOVED"
        )

        self.sound_player.notify(
            False
        )

        self.close_posture_alert()

        QMessageBox.warning(
            self,
            "ตรวจพบการขยับกล้อง",
            "PostGuard ตรวจพบว่าตำแหน่งกล้องเปลี่ยน"
            "ระหว่างการตรวจจับ\n\n"
            f"{detail_text}\n\n"
            "Camera Reference และ Personal Baseline เดิม"
            "อาจไม่ตรงกับตำแหน่งกล้องปัจจุบัน "
            "ระบบจึงจบเซสชันนี้เพื่อไม่ให้ประเมินความเสี่ยงต่อ"
            "ด้วยข้อมูลอ้างอิงที่ไม่ถูกต้อง\n\n"
            "กรุณาเริ่ม Monitoring ใหม่ แล้วทำ Camera Setup "
            "และ Personal Baseline ใหม่",
        )

        # Existing validated session-finish path:
        # backend COMPLETED -> summary persistence -> Summary page.
        self.handle_stop()

    # ========================================================
    # DETECTION DISPLAY
    # ========================================================

    def _update_detection_labels(
        self,
        result: dict,
    ) -> None:

        pose_text = (
            "ตรวจพบ"
            if result.get(
                "pose_points"
            )
            is not None
            else
            "ไม่พบ"
        )

        face_text = (
            "ตรวจพบ"
            if result.get(
                "face_detected"
            )
            else
            "ไม่พบ"
        )

        self.detection_label.setText(
            f"ท่าทาง: {pose_text} | "
            f"ใบหน้า: {face_text}"
        )

        # ====================================================
        # SHOULDER
        # ====================================================

        shoulder = (
            result.get(
                "shoulder_tilt"
            )
        )

        self.shoulder_label.setText(
            f"ความเอียงไหล่: {shoulder:+.2f}°"
            if (
                type(shoulder)
                in
                (int, float)
                and
                math.isfinite(
                    shoulder
                )
            )
            else
            "ความเอียงไหล่: --"
        )

        # ====================================================
        # NECK LATERAL
        # ====================================================

        neck_result = (
            result.get(
                "neck_lateral_tilt"
            )
        )

        neck = (
            neck_result.get(
                "neck_tilt"
            )
            if isinstance(
                neck_result,
                dict,
            )
            else
            None
        )

        self.neck_label.setText(
            f"ความเอียงคอด้านข้าง: {neck:+.2f}°"
            if (
                type(neck)
                in
                (int, float)
                and
                math.isfinite(
                    neck
                )
            )
            else
            "ความเอียงคอด้านข้าง: --"
        )

        # ====================================================
        # FLEXION
        # ====================================================

        flexion = (
            result.get(
                "neck_flexion"
            )
        )

        self.flexion_label.setText(
            f"มุมก้ม/เงยคอ: {flexion:+.2f}°"
            if (
                type(flexion)
                in
                (int, float)
                and
                math.isfinite(
                    flexion
                )
            )
            else
            "มุมก้ม/เงยคอ: --"
        )

    # ========================================================
    # PREVIEW
    # ========================================================

    def _update_preview(
        self,
        frame,
    ) -> None:
        """Show a mirror-style preview without changing detector input.

        `frame` has already been through the shared camera preprocessing
        (including confirmed Camera Roll correction). The validated
        detection/risk pipeline continues to use that non-mirrored frame.

        Only the UI preview is horizontally flipped so Monitoring behaves
        like a normal webcam mirror and matches Camera Setup / Personal
        Baseline from the user's point of view.
        """

        display_frame = cv2.flip(
            frame,
            1,
        )

        frame_rgb = (
            cv2.cvtColor(
                display_frame,
                cv2.COLOR_BGR2RGB,
            )
        )

        height, width, channels = (
            frame_rgb.shape
        )

        fit_preview_label(
            self.preview_label,
            width,
            height,
            720,
            480,
        )

        image = (
            QImage(
                frame_rgb.data,
                width,
                height,
                channels * width,
                QImage.Format.Format_RGB888,
            )
            .copy()
        )

        pixmap = (
            QPixmap.fromImage(
                image
            )
            .scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        self.preview_label.setPixmap(
            pixmap
        )

    # ========================================================
    # RESOURCE MANAGEMENT
    # ========================================================

    def _finish_after_capture_error(
        self,
    ) -> None:

        self._close_capture_resources()

        self.pause_button.setEnabled(
            False
        )

        self.status_label.setText(
            "สถานะ: หยุดตรวจจับ "
            "กำลังจบเซสชัน"
        )

        self.handle_stop()

    def _close_capture_resources(
        self,
    ) -> None:

        self.timer.stop()

        # ====================================================
        # DETECTOR
        # ====================================================

        if self.detector is not None:

            try:

                self.detector.close()

            except Exception as error:

                print(
                    "DETECTION CLOSE ERROR:",
                    error,
                )

            finally:

                self.detector = None

        # ====================================================
        # CAMERA
        # ====================================================

        if self.capture is not None:

            try:

                self.capture.release()

            finally:

                self.capture = None

    def _release_local_resources(
            self,
        ) -> None:

            self._close_capture_resources()

            self.close_posture_alert()
            self.close_eye_alert()

            # ====================================================
            # CAMERA DATA GAP
            # ====================================================

            self.camera_gap_started_at = None
            self.camera_gap_last_retry_at = None

            # ====================================================
            # CAMERA MOVEMENT
            # ====================================================

            self.camera_movement_guard.reset()
            self.camera_movement_triggered = False

            # ====================================================
            # RISK PIPELINE
            # ====================================================

            self.risk_pipeline.reset()

            self.last_pipeline_result = (
                None
            )

            self.sound_player.notify(
                False
            )

            # ====================================================
            # SCREEN DISTANCE
            # ====================================================

            self.screen_distance_policy.reset()

            self.last_screen_distance_result = (
                None
            )

            self.screen_distance_label.setText(
                "ระยะห่างหน้าจอ: --"
            )

            # ====================================================
            # BLINK
            # ====================================================

            self.blink_detector.reset(
                preserve_count=False,
                now=time.monotonic(),
            )

            self.last_blink_result = (
                None
            )

            self.eye_alert_policy.reset()
            self.last_eye_alert_result = None

            self.eye_state_label.setText(
                "สถานะตา: --"
            )

            self.blink_count_label.setText(
                "จำนวนการกระพริบตา: 0"
            )

            # ====================================================
            # FRAME
            # ====================================================

            self.frame_count = 0

            # ====================================================
            # DETECTION UI
            # ====================================================

            self.detection_label.setText(
                "ท่าทาง: กำลังรอ | "
                "ใบหน้า: กำลังรอ"
            )

            self.shoulder_label.setText(
                "ความเอียงไหล่: --"
            )

            self.neck_label.setText(
                "ความเอียงคอด้านข้าง: --"
            )

            self.flexion_label.setText(
                "มุมก้ม/เงยคอ: --"
            )

            self.shoulder_difference_label.setText(
                "ผลต่างจาก Baseline ไหล่: --"
            )

            self.neck_difference_label.setText(
                "ผลต่างจาก Baseline คอด้านข้าง: --"
            )

            self.flexion_difference_label.setText(
                "ผลต่างจาก Baseline ก้ม/เงยคอ: --"
            )

            # ====================================================
            # PREVIEW
            # ====================================================

            self.preview_label.clear()

            self.preview_label.setText(
                "ภาพการตรวจจับจะแสดงที่นี่"
            )

            # ====================================================
            # BUTTONS
            # ====================================================

            self.stop_button.setEnabled(
                False
            )

            self.pause_button.setEnabled(
                False
            )

            self.pause_button.setText(
                "Pause Monitoring"
            )

            self.is_paused = False

            # ====================================================
            # SESSION LOCAL DATA
            # ====================================================

            self.session_started_at = None
            self.session_started_monotonic = None

            self.baseline_data = None

            # ====================================================
            # BASELINE UI
            # ====================================================

            self.baseline_shoulder_label.setText(
                "Baseline Shoulder Tilt: --"
            )

            self.baseline_neck_label.setText(
                "Baseline Neck Lateral Tilt: --"
            )

            self.baseline_flexion_label.setText(
                "Baseline Neck Flexion: --"
            )

            # ====================================================
            # NETWORK / BACKEND GAP
            # ====================================================

            if (
                self.network_recovery_timer.isActive()
            ):

                self.network_recovery_timer.stop()

            self.network_gap_active = False
            self.network_gap_started_at = None
            self.network_gap_last_error = None
            self.network_stop_pending = False
            self.pending_stop_summary = None

            # ====================================================
            # SESSION STATS
            # ====================================================

            self.detection_count = 0
            self.pose_detected_count = 0
            self.face_detected_count = 0

            self.shoulder_samples.clear()
            self.neck_samples.clear()

            # ====================================================
            # PIPELINE UI
            # ====================================================

            self.assessment_label.setText(
                "Assessment: Waiting"
            )

            self.factor_label.setText(
                "Posture Factors: -"
            )

            self.duration_label.setText(
                "Longest Continuous Factor: -"
            )

            self.risk_label.setText(
                "Risk Level: -"
            )

            self.event_label.setText(
                "Risk Event: -"
            )

            self.alert_label.setText(
                "Alert Policy: Waiting"
            )

    # ========================================================
    # STOP MONITORING
    # ========================================================

    def stop_monitoring(
        self,
    ) -> bool:

        ended = True

        if self.session_id is not None:

            try:

                self._end_remote_session()

            except (
                requests.RequestException,
                RuntimeError,
                ValueError,
            ) as error:

                ended = False

                print(
                    "SESSION END ERROR:",
                    error,
                )

                QMessageBox.warning(
                    self,
                    "ยังไม่สามารถจบเซสชัน",
                    f"Session {self.session_id} "
                    "may still be RUNNING "
                    "on the server.\n"
                    f"{error}\n"
                    "Reconnect and retry "
                    "before starting another session.",
                )

        self._release_local_resources()

        if ended:

            self.status_label.setText(
                "สถานะ: หยุดแล้ว"
            )

            self.session_label.setText(
                "Session ID: -"
            )

        else:

            self.status_label.setText(
                "สถานะ: รอยืนยันการจบเซสชัน"
                "จากฐานข้อมูล"
            )

            self.session_label.setText(
                f"Session ID: {self.session_id} "
                "(pending)"
            )

        self.state_changed.emit()

        return ended

    # ========================================================
    # BUILD SESSION SUMMARY
    # ========================================================

    def build_session_summary(
        self,
    ) -> dict:

        if (
            self.session_started_monotonic
            is None
        ):

            raise RuntimeError(
                "No active monitoring session."
            )

        duration = max(
            0.0,
            time.monotonic()
            -
            self.session_started_monotonic,
        )

        baseline = (
            self.baseline_data
            or
            {}
        )

        camera = (
            self.selected_camera
            or
            {}
        )

        # ====================================================
        # RISK SCORE
        # ====================================================

        risk_score_summary = (
            self.risk_score_collector.get_summary()
        )

        # ====================================================
        # BLINK
        # ====================================================

        blink_count = (
            int(
                self.blink_detector.total_blinks
            )
        )

        # ====================================================
        # SCREEN DISTANCE
        # ====================================================

        screen_distance = (
            self.last_screen_distance_result
            or
            {}
        )

        camera_gap_duration = (
            self.camera_loss_tracker.duration(
                time.monotonic()
            )
        )

        return {
            # =================================================
            # SESSION
            # =================================================

            "session_id": (
                self.session_id
            ),

            "database_status": (
                "RUNNING"
            ),

            "camera_name": (
                camera.get(
                    "camera_name",
                    "Unknown Camera",
                )
            ),

            "camera_id": (
                camera.get(
                    "camera_id"
                )
            ),

            "baseline_id": (
                self.baseline_id
            ),

            "started_at": (
                self.session_started_at
            ),

            "ended_at": (
                datetime.now()
                .astimezone()
                .isoformat(
                    timespec="seconds"
                )
            ),

            "duration_seconds": (
                duration
            ),

            "paused_duration": (
                0
            ),

            "pause_count": (
                0
            ),

            # =================================================
            # DETECTION
            # =================================================

            "detection_count": (
                self.detection_count
            ),

            "pose_detected_count": (
                self.pose_detected_count
            ),

            "face_detected_count": (
                self.face_detected_count
            ),

            "average_shoulder": (
                statistics.mean(
                    self.shoulder_samples
                )
                if
                self.shoulder_samples
                else
                None
            ),

            "average_neck": (
                statistics.mean(
                    self.neck_samples
                )
                if
                self.neck_samples
                else
                None
            ),

            # =================================================
            # BASELINE
            # =================================================

            "baseline_shoulder": (
                baseline.get(
                    "shoulder_angle"
                )
            ),

            "baseline_neck": (
                baseline.get(
                    "lateral_tilt_baseline"
                )
            ),

            # =================================================
            # BLINK
            # =================================================

            "blink_count": (
                blink_count
            ),

            # คำนวณตอน Stop หลังได้
            # total_duration / paused_duration จาก Backend
            "blink_rate": (
                None
            ),

            # =================================================
            # RISK STATISTICS
            # =================================================

            "risk_sample_counts": (
                dict(
                    self.risk_sample_counts
                )
            ),

            "alert_notification_count": (
                self.alert_notification_count
            ),

            # =================================================
            # SESSION RISK SCORE
            # =================================================

            "average_risk_score": (
                risk_score_summary.get(
                    "average_risk_score"
                )
            ),

            "minimum_risk_score": (
                risk_score_summary.get(
                    "minimum_risk_score"
                )
            ),

            "maximum_risk_score": (
                risk_score_summary.get(
                    "maximum_risk_score"
                )
            ),

            "risk_score_method": (
                "POSTGUARD_MODIFIED_RULA_FRONT_VIEW_V1"
                if (
                    risk_score_summary.get(
                        "status"
                    )
                    ==
                    "AVAILABLE"
                )
                else
                None
            ),

            "risk_score_sample_count": (
                risk_score_summary.get(
                    "accepted_score_samples",
                    0,
                )
            ),

            "risk_score_skipped_count": (
                risk_score_summary.get(
                    "skipped_score_samples",
                    0,
                )
            ),

            "risk_score_buckets": (
                risk_score_summary.get(
                    "buckets",
                    [],
                )
            ),

            "modified_rula_distribution": (
                risk_score_summary.get(
                    "modified_rula_distribution",
                    {},
                )
            ),

            # =================================================
            # SCREEN DISTANCE
            # =================================================

            "screen_distance_state": (
                screen_distance.get(
                    "state"
                )
            ),

            "screen_distance_stable_state": (
                screen_distance.get(
                    "stable_state"
                )
            ),

            "screen_distance_ratio": (
                screen_distance.get(
                    "ratio"
                )
            ),

            "screen_distance_percent_change": (
                screen_distance.get(
                    "percent_change"
                )
            ),

            "screen_distance_reason": (
                screen_distance.get(
                    "reason"
                )
            ),

            "screen_distance_threshold_status": (
                screen_distance.get(
                    "threshold_status"
                )
            ),
        }

    # ========================================================
    # REMOTE SESSION STATUS
    # ========================================================

    def _change_remote_session_status(
        self,
        action: str,
        expected_status: str,
    ) -> dict:

        session_id = (
            self.session_id
        )

        if (
            type(session_id)
            is not int
            or
            session_id <= 0
        ):

            raise ValueError(
                "No valid active session"
            )

        if action == "pause":

            request_function = (
                APIClient.pause_session
            )

        elif action == "resume":

            request_function = (
                APIClient.resume_session
            )

        else:

            raise ValueError(
                "Unsupported session action"
            )

        response = None

        try:

            response = (
                request_function(
                    session_id
                )
            )

        except requests.RequestException:

            pass

        # ====================================================
        # REQUEST SUCCESS
        # ====================================================

        if (
            response is not None
            and
            response.ok
        ):

            data = (
                response.json()
            )

        # ====================================================
        # FALLBACK CHECK CURRENT STATE
        # ====================================================

        else:

            check = (
                APIClient.get_session(
                    session_id
                )
            )

            if not check.ok:

                if response is not None:

                    raise RuntimeError(
                        self._response_error(
                            response
                        )
                    )

                raise RuntimeError(
                    "Session state could "
                    "not be confirmed"
                )

            data = (
                check.json()
            )

            if (
                data.get(
                    "status"
                )
                !=
                expected_status
            ):

                if response is not None:

                    raise RuntimeError(
                        self._response_error(
                            response
                        )
                    )

                raise RuntimeError(
                    "Backend did not confirm "
                    +
                    expected_status
                )

        # ====================================================
        # VALIDATE
        # ====================================================

        if not isinstance(
            data,
            dict,
        ):

            raise ValueError(
                "Invalid session response"
            )

        if (
            data.get(
                "session_id"
            )
            !=
            session_id
        ):

            raise ValueError(
                "Session ID mismatch"
            )

        if (
            data.get(
                "status"
            )
            !=
            expected_status
        ):

            raise RuntimeError(
                f"Expected {expected_status}, "
                f"received "
                f"{data.get('status')}"
            )

        return data

    # ========================================================
    # PAUSE / RESUME BUTTON
    # ========================================================

    def handle_pause_resume(
        self,
    ) -> None:

        if (
            self.session_id is None
            or
            self.is_stopping
            or
            self.network_stop_pending
            or
            self.capture is None
        ):

            return

        # Backend state cannot safely be changed while a known
        # NETWORK GAP is active.
        if self.network_gap_active:

            QMessageBox.warning(
                self,
                "Backend ยังไม่พร้อม",
                (
                    "ยังไม่สามารถ Pause / Resume ได้ "
                    "จนกว่า PostGuard จะยืนยันสถานะ Session "
                    "กับ Backend อีกครั้ง"
                ),
            )

            return

        self.pause_button.setEnabled(
            False
        )

        if self.is_paused:

            self._resume_monitoring()

        else:

            self._pause_monitoring()

        if (
            self.session_id is not None
            and
            not self.network_gap_active
            and
            not self.network_stop_pending
            and
            self.capture is not None
        ):

            self.pause_button.setEnabled(
                True
            )

        self.state_changed.emit()

    # ========================================================
    # PAUSE
    # ========================================================

    def _pause_monitoring(
        self,
    ) -> None:

        try:

            remote = (
                self._change_remote_session_status(
                    action="pause",
                    expected_status="PAUSED",
                )
            )

        except requests.RequestException as error:

            self._mark_network_gap(
                error
            )

            QMessageBox.warning(
                self,
                "หยุดชั่วคราวไม่สำเร็จ",
                (
                    "ไม่สามารถติดต่อ Backend "
                    "เพื่อยืนยันสถานะ PAUSED ได้\n\n"
                    "Local Monitoring จะยังทำงานต่อ "
                    "จนกว่า Backend จะกลับมา"
                ),
            )

            return

        except (
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:

            QMessageBox.warning(
                self,
                "หยุดชั่วคราวไม่สำเร็จ",
                (
                    "ไม่สามารถยืนยันสถานะ "
                    "PAUSED ได้\n"
                    f"{error}"
                ),
            )

            return

        # Backend has authoritatively confirmed PAUSED.

        self.timer.stop()

        self.is_paused = True

        # ====================================================
        # RISK CONTINUITY
        # ====================================================

        self.reset_risk_tracking()

        self.reset_screen_distance_tracking()

        # ====================================================
        # BLINK
        # ====================================================

        self.blink_detector.reset(
            preserve_count=True,
            now=time.monotonic(),
        )

        self.last_blink_result = (
            None
        )

        self.eye_alert_policy.reset()
        self.last_eye_alert_result = None
        self.close_eye_alert()

        self.eye_state_label.setText(
            "สถานะตา: PAUSED"
        )

        # ====================================================
        # UI
        # ====================================================

        self.preview_label.clear()

        self.preview_label.setText(
            "หยุดการตรวจจับชั่วคราว"
        )

        self.assessment_label.setText(
            "Assessment: PAUSED"
        )

        self.factor_label.setText(
            "Posture Factors: PAUSED"
        )

        self.duration_label.setText(
            "Longest Continuous Factor: PAUSED"
        )

        self.risk_label.setText(
            "Risk Level: PAUSED"
        )

        self.event_label.setText(
            "Risk Event: PAUSED"
        )

        self.alert_label.setText(
            "Alert Policy: PAUSED"
        )

        self.screen_distance_label.setText(
            "ระยะห่างหน้าจอ: PAUSED"
        )

        self.status_label.setText(
            "สถานะ: หยุดชั่วคราว "
            f"(จำนวนครั้ง: "
            f"{remote['pause_count']})"
        )

        self.pause_button.setText(
            "Resume Monitoring"
        )

    # ========================================================
    # RESUME
    # ========================================================

    def _resume_monitoring(
        self,
    ) -> None:

        try:

            remote = (
                self._change_remote_session_status(
                    action="resume",
                    expected_status="RUNNING",
                )
            )

        except requests.RequestException as error:

            self._mark_network_gap(
                error
            )

            QMessageBox.warning(
                self,
                "ตรวจจับต่อไม่สำเร็จ",
                (
                    "ไม่สามารถติดต่อ Backend "
                    "เพื่อยืนยันสถานะ RUNNING ได้\n\n"
                    "Session จะยังคง PAUSED "
                    "จนกว่า Backend จะกลับมา"
                ),
            )

            return

        except (
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:

            QMessageBox.warning(
                self,
                "ตรวจจับต่อไม่สำเร็จ",
                (
                    "ไม่สามารถยืนยันสถานะ "
                    "RUNNING ได้\n"
                    f"{error}"
                ),
            )

            return

        # Backend confirmed RUNNING.
        self.is_paused = False

        # ====================================================
        # RISK
        # ====================================================

        self.reset_risk_tracking()
        self.reset_screen_distance_tracking()

        # ====================================================
        # BLINK
        # ====================================================

        self.blink_detector.reset(
            preserve_count=True,
            now=time.monotonic(),
        )

        self.last_blink_result = None

        self.eye_alert_policy.reset()
        self.last_eye_alert_result = None
        self.close_eye_alert()

        self.eye_state_label.setText(
            "สถานะตา: กำลัง Calibration"
        )

        self.blink_count_label.setText(
            "จำนวนการกระพริบตา: "
            f"{self.blink_detector.total_blinks}"
        )

        self.screen_distance_label.setText(
            "ระยะห่างหน้าจอ: "
            "กำลังประเมินใหม่"
        )

        # ====================================================
        # UI
        # ====================================================

        self.preview_label.setText(
            "กำลังตรวจจับต่อ..."
        )

        self.status_label.setText(
            "สถานะ: กำลังตรวจจับ "
            "(RUNNING) "
            "| เวลาหยุดรวม: "
            f"{remote['paused_duration']} "
            "วินาที"
        )

        self.pause_button.setText(
            "Pause Monitoring"
        )

        self.timer.start()
    # ========================================================
    # STOP BUTTON
    # ========================================================

    def handle_stop(
        self,
    ) -> None:

        if (
            self.is_stopping
            or
            self.network_stop_pending
        ):

            return

        self.is_stopping = True

        self.state_changed.emit()

        try:

            self._finish_session()

        finally:

            self.is_stopping = False

            self.state_changed.emit()
    # ========================================================
    # FINISH SESSION
    # ========================================================

    def _finish_session(
        self,
    ) -> None:

        if (
            self.session_started_monotonic
            is None
            or
            self.session_id is None
        ):

            return

        # ====================================================
        # 1. SNAPSHOT LOCAL DATA
        # ====================================================

        summary = (
            self.build_session_summary()
        )

        # ====================================================
        # 2. END BACKEND SESSION
        # ====================================================

        try:

            remote = (
                self._end_remote_session()
            )

        except requests.RequestException as error:

            # =================================================
            # NETWORK GAP
            #
            # User has explicitly requested Stop.
            #
            # Stop local camera immediately, preserve Session
            # ID + summary, and automatically retry END later.
            # =================================================

            self._begin_pending_stop(
                summary,
                error,
            )

            return

        except (
            RuntimeError,
            ValueError,
        ) as error:

            # Backend responded but could not confirm a valid
            # completed Session. This is not classified as a
            # simple Internet loss.

            QMessageBox.warning(
                self,
                "ไม่สามารถจบเซสชัน",
                (
                    "Backend ยังไม่ยืนยันว่า "
                    "Session สิ้นสุด\n"
                    f"{error}\n\n"
                    "กรุณาตรวจสอบ Backend "
                    "แล้วกด Stop อีกครั้ง"
                ),
            )

            return

        # ====================================================
        # 3. BACKEND CONFIRMED COMPLETED
        # ====================================================

        self._complete_session_after_remote_end(
            summary,
            remote,
        )
        # ========================================================
    # COMPLETE SESSION AFTER BACKEND END
    # ========================================================

    def _complete_session_after_remote_end(
        self,
        summary: dict,
        remote: dict,
    ) -> None:

        if not isinstance(
            summary,
            dict,
        ):

            summary = {}

        if not isinstance(
            remote,
            dict,
        ):

            raise ValueError(
                "Invalid completed session response."
            )

        # ====================================================
        # AUTHORITATIVE BACKEND DATA
        # ====================================================

        summary[
            "database_status"
        ] = (
            remote[
                "status"
            ]
        )

        summary[
            "session_id"
        ] = (
            remote[
                "session_id"
            ]
        )

        summary[
            "started_at"
        ] = (
            remote.get(
                "started_at"
            )
            or
            summary.get(
                "started_at"
            )
        )

        summary[
            "ended_at"
        ] = (
            remote.get(
                "ended_at"
            )
            or
            summary.get(
                "ended_at"
            )
        )

        # ====================================================
        # TOTAL DURATION
        # ====================================================

        remote_total_duration = (
            remote.get(
                "total_duration"
            )
        )

        if (
            remote_total_duration
            is not None
        ):

            summary[
                "duration_seconds"
            ] = (
                remote_total_duration
            )

        # ====================================================
        # PAUSED DURATION
        # ====================================================

        paused_duration = (
            remote.get(
                "paused_duration"
            )
        )

        if (
            type(paused_duration)
            not in
            (int, float)
        ):

            paused_duration = 0

        paused_duration = max(
            0.0,
            float(
                paused_duration
            ),
        )

        summary[
            "paused_duration"
        ] = (
            paused_duration
        )

        # ====================================================
        # PAUSE COUNT
        # ====================================================

        pause_count = (
            remote.get(
                "pause_count"
            )
        )

        if (
            type(pause_count)
            is not int
        ):

            pause_count = 0

        summary[
            "pause_count"
        ] = max(
            0,
            pause_count,
        )

        # ====================================================
        # BLINK RATE
        # ====================================================

        total_seconds = (
            summary.get(
                "duration_seconds"
            )
        )

        if (
            type(total_seconds)
            in
            (int, float)
            and
            math.isfinite(
                float(
                    total_seconds
                )
            )
        ):

            total_seconds = max(
                0.0,
                float(
                    total_seconds
                ),
            )

        else:

            total_seconds = 0.0

        active_seconds = max(
            0.0,
            total_seconds
            -
            paused_duration,
        )

        blink_count = (
            summary.get(
                "blink_count"
            )
            or
            0
        )

        if active_seconds > 0.0:

            summary[
                "blink_rate"
            ] = (
                float(
                    blink_count
                )
                /
                active_seconds
                *
                60.0
            )

        else:

            summary[
                "blink_rate"
            ] = None

        # ====================================================
        # CLEAR NETWORK PENDING STATE
        # ====================================================

        self.network_gap_active = False
        self.network_gap_started_at = None
        self.network_gap_last_error = None
        self.network_stop_pending = False
        self.pending_stop_summary = None

        if (
            self.network_recovery_timer.isActive()
        ):

            self.network_recovery_timer.stop()

        # ====================================================
        # RELEASE LOCAL RESOURCES
        #
        # _end_remote_session() already cleared session_id.
        # ====================================================

        self.stop_monitoring()

        # ====================================================
        # SAVE SESSION SUMMARY
        # ====================================================

        summary[
            "summary_save_status"
        ] = "FAILED"

        summary[
            "summary_save_error"
        ] = None

        try:

            result = (
                save_session_summary(
                    summary
                )
            )

            summary[
                "summary_save_status"
            ] = (
                result[
                    "status"
                ]
            )

            summary[
                "saved_summary"
            ] = (
                result[
                    "summary"
                ]
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
            TypeError,
        ) as error:

            summary[
                "summary_save_error"
            ] = (
                str(
                    error
                )
            )

            QMessageBox.warning(
                self,
                "เกิดข้อผิดพลาดในการบันทึกสรุป",
                (
                    "Session สิ้นสุดแล้ว "
                    "แต่ยังบันทึก Summary "
                    "ไม่สำเร็จ\n\n"
                    f"{error}\n\n"
                    "สามารถกด Retry "
                    "ที่หน้า Summary ได้"
                ),
            )

        # ====================================================
        # OPEN SUMMARY PAGE
        # ====================================================

        self.stop_requested.emit(
            summary
        )