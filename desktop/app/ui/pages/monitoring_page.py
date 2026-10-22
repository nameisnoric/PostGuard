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
from app.services.validated_risk_pipeline_service import (
    ValidatedRiskPipelineService,
)
from app.ui.dialogs.posture_alert_dialog import (
    PostureAlertDialog,
)
from app.ui.utils.preview_sizing import (
    fit_preview_label,
)


RISK_LEVELS = (
    "NONE",
    "LOW",
    "MODERATE",
    "HIGH",
)

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

        self.frame_count = 0

        self.session_id = None
        self.is_paused = False

        self.session_started_at = None
        self.session_started_monotonic = None

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

        self.last_pipeline_result = None

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
        #
        # These controls are NOT displayed and are NOT consumed
        # by the validated runtime pipeline.
        #
        # They are kept temporarily so the teammate's existing
        # desktop_workflow test does not fail only because an
        # obsolete experimental threshold widget disappeared.
        #
        # Remove these together with the old threshold test once
        # the new integration suite is adopted.
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

    # ========================================================
    # TEMPORARY OLD TEST COMPATIBILITY
    # ========================================================

    def _setup_legacy_test_controls(self) -> None:
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

    def _setup_ui(self) -> None:
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
        scroll.setWidgetResizable(True)

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

        layout.setSpacing(12)

        scroll.setWidget(content)

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
        columns.setSpacing(16)

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

        camera_layout.setSpacing(10)

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

        metrics_layout.setSpacing(10)

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
            "Baseline ID: -"
        )

        self.session_label = QLabel(
            "Session ID: -"
        )

        self.baseline_shoulder_label = QLabel(
            "Baseline Shoulder Tilt: -"
        )

        self.baseline_neck_label = QLabel(
            "Baseline Neck Lateral Tilt: -"
        )

        self.baseline_flexion_label = QLabel(
            "Baseline Neck Flexion: -"
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

    def _setup_preview(self) -> None:
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
            self.shoulder_difference_label,
            self.neck_difference_label,
            self.flexion_difference_label,
        ):
            detection_layout.addWidget(
                label
            )

        return detection_group

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
    # BACKEND HELPERS
    # ========================================================

    @staticmethod
    def _response_error(
        response,
    ) -> str:
        try:
            payload = response.json()

            detail = (
                payload.get(
                    "detail",
                    response.text,
                )
                if isinstance(
                    payload,
                    dict,
                )
                else response.text
            )

        except ValueError:
            detail = response.text

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
            response = APIClient.end_session(
                self.session_id
            )

        except requests.RequestException as error:
            try:
                check = APIClient.get_session(
                    self.session_id
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
                    response = check

                else:
                    raise error

            except (
                requests.RequestException,
                ValueError,
                AttributeError,
            ):
                raise error

        if not response.ok:
            if response.status_code == 409:
                check = APIClient.get_session(
                    self.session_id
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
                    response = check

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

        data = response.json()

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
        response = APIClient.get(
            f"/personal-baselines/{baseline_id}"
        )

        if not response.ok:
            raise RuntimeError(
                "Cannot load baseline: "
                +
                self._response_error(
                    response
                )
            )

        baseline = response.json()

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

        shoulder = baseline.get(
            "shoulder_angle"
        )

        neck = baseline.get(
            "lateral_tilt_baseline"
        )

        flexion = baseline.get(
            "neck_flexion_baseline"
        )

        for name, value in (
            ("Shoulder", shoulder),
            ("Neck lateral", neck),
        ):
            if (
                type(value)
                not in
                (int, float)
                or
                not math.isfinite(value)
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
            math.isfinite(flexion)
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

        self.baseline_data = baseline

        return baseline

    # ========================================================
    # START
    # ========================================================

    def start_monitoring(
        self,
        camera: dict,
        baseline_id: int,
    ) -> bool:
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

        self.baseline_id = baseline_id

        device_index = camera.get(
            "device_index"
        )

        camera_id = camera.get(
            "camera_id"
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

        try:
            self.capture = cv2.VideoCapture(
                int(device_index)
            )

            if not self.capture.isOpened():
                raise RuntimeError(
                    "Unable to open camera."
                )

            self.detector = (
                DetectionService()
            )

            response = APIClient.start_session(
                camera_id,
                baseline_id,
            )

            if not response.ok:
                raise RuntimeError(
                    "Cannot start session: "
                    +
                    self._response_error(
                        response
                    )
                )

            session = response.json()

            session_id = (
                session.get(
                    "session_id"
                )
                if isinstance(
                    session,
                    dict,
                )
                else None
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

            self.session_id = session_id

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

        self.detection_count = 0
        self.pose_detected_count = 0
        self.face_detected_count = 0

        self.shoulder_samples.clear()
        self.neck_samples.clear()

        self.risk_sample_counts = {
            level: 0
            for level in RISK_LEVELS
        }

        self.alert_notification_count = 0

        self.risk_persistence.reset()

        self.reset_risk_tracking()  

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
            not self.sound_player.settings[
                "notifications_enabled"
            ]
        ):
            self.close_posture_alert()

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
            factor_name = factor.get(
                "factor"
            )

            names.append(
                FACTOR_THAI.get(
                    factor_name,
                    str(factor_name),
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
            name = factor.get(
                "factor"
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
            or []
        )

        values = []

        for factor in active_factors:
            value = factor.get(
                "continuous_seconds"
            )

            if (
                type(value)
                in
                (int, float)
                and
                math.isfinite(value)
            ):
                values.append(
                    float(value)
                )

        return (
            max(values)
            if values
            else 0.0
        )

    # ========================================================
    # VALIDATED RISK PIPELINE
    # ========================================================

    def update_validated_risk(
        self,
        detection_result: dict,
    ) -> dict:
        pipeline_result = (
            self.risk_pipeline.process_detection(
                detection_result,
                self.baseline_data,
            )
        )

        self.last_pipeline_result = (
            pipeline_result
        )

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

            except Exception as error:
                print(
                    "RISK PERSISTENCE ERROR:",
                    error,
                )

        assessment = pipeline_result[
            "assessment"
        ]

        temporal = pipeline_result[
            "temporal"
        ]

        risk = pipeline_result[
            "risk"
        ]

        risk_event = pipeline_result[
            "risk_event"
        ]

        alert = pipeline_result[
            "alert_policy"
        ]

        # ----------------------------------------------------
        # Assessment
        # ----------------------------------------------------

        self.assessment_label.setText(
            "Assessment: "
            f"{assessment.get('status')} "
            f"({assessment.get('reason')})"
        )

        factors = (
            assessment.get(
                "factors"
            )
            or []
        )

        self.factor_label.setText(
            "Posture Factors: "
            +
            self._factor_text(
                factors
            )
        )

        # ----------------------------------------------------
        # Temporal
        # ----------------------------------------------------

        longest_seconds = (
            self._longest_continuous_seconds(
                temporal
            )
        )

        self.duration_label.setText(
            "Longest Continuous Factor: "
            f"{longest_seconds:.1f} s"
        )

        # ----------------------------------------------------
        # Risk
        # ----------------------------------------------------

        risk_level = risk.get(
            "risk_level"
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

        # ----------------------------------------------------
        # Risk Event
        # ----------------------------------------------------

        event_action = risk_event.get(
            "event_action"
        )

        event = risk_event.get(
            "event"
        )

        event_id = (
            event.get(
                "runtime_event_id"
            )
            if isinstance(
                event,
                dict,
            )
            else None
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

        # ----------------------------------------------------
        # Risk Event lifecycle -> presentation lifecycle
        # ----------------------------------------------------

        if event_action == "RESOLVED":
            self.close_posture_alert()

            self.sound_player.notify(
                False
            )

        # ----------------------------------------------------
        # Alert Policy
        # ----------------------------------------------------

        decision = alert.get(
            "decision"
        )

        alert_type = alert.get(
            "alert_type"
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
                alert_type=alert_type,
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
    # ALERT POPUP LIFECYCLE
    # ========================================================

    def close_posture_alert(
        self,
    ) -> None:
        """
        Close the currently visible posture alert popup.

        Closing the popup only changes presentation state.
        It does not alter:
        - Risk Evaluation
        - Risk Event
        - Alert Policy
        """

        if self.alert_popup is None:
            return

        try:
            self.alert_popup.close()

        finally:
            self.alert_popup = None

    # ========================================================
    # POPUP
    # ========================================================

        # ========================================================
    # POPUP
    # ========================================================

    def show_posture_alert(
        self,
        *,
        risk_level: str | None,
        alert_type: str | None,
        factors: list[str] | None,
        duration_seconds: float,
    ) -> bool:
        """
        Show a non-blocking posture alert popup.

        Returns:
            True:
                A popup was created and shown.

            False:
                Notification presentation is disabled, so no
                popup was created.

        Important:
        Disabling popup presentation does NOT alter:
        - Risk Evaluation
        - Risk Event
        - Alert Policy

        Alert Policy may still decide that an alert event exists.
        This method only controls whether the Desktop UI presents
        that notification to the user.
        """

        notifications_enabled = (
            self.sound_player.settings.get(
                "notifications_enabled",
                True,
            )
        )

        # ----------------------------------------------------
        # User disabled notification presentation
        # ----------------------------------------------------

        if not notifications_enabled:
            self.close_posture_alert()

            return False

        # ----------------------------------------------------
        # Never stack multiple posture alert dialogs.
        # Replace the previous presentation with the newest one.
        # ----------------------------------------------------

        self.close_posture_alert()

        self.alert_popup = (
            PostureAlertDialog(
                risk_level=risk_level,
                alert_type=alert_type,
                factors=factors,
                duration_seconds=duration_seconds,
                parent=self,
            )
        )

        # Non-blocking presentation.
        self.alert_popup.show()

        self.alert_popup.raise_()

        return True
    # ========================================================
    # BASELINE COMPARISON DISPLAY
    # ========================================================

    def update_baseline_comparison(
        self,
        result: dict,
    ) -> None:
        if self.baseline_data is None:
            return

        current_shoulder = result.get(
            "shoulder_tilt"
        )

        neck_result = result.get(
            "neck_lateral_tilt"
        )

        current_neck = (
            neck_result.get(
                "neck_tilt"
            )
            if isinstance(
                neck_result,
                dict,
            )
            else None
        )

        current_flexion = result.get(
            "neck_flexion"
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

        shoulder = result.get(
            "shoulder_tilt"
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
                float(shoulder)
            )

        neck_result = result.get(
            "neck_lateral_tilt"
        )

        neck = (
            neck_result.get(
                "neck_tilt"
            )
            if isinstance(
                neck_result,
                dict,
            )
            else None
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
                float(neck)
            )

    # ========================================================
    # CAMERA LOOP
    # ========================================================

    def update_frame(self) -> None:
        if (
            self.capture is None
            or
            self.is_paused
            or
            self.is_stopping
        ):
            return

        success, frame = (
            self.capture.read()
        )

        if (
            not success
            or
            frame is None
        ):
            self._finish_after_capture_error()

            QMessageBox.warning(
                self,
                "ข้อผิดพลาดของกล้อง",
                "Unable to read camera frame.",
            )

            return

        self.frame_count += 1

        # Detection is intentionally not run on every camera
        # frame to preserve the teammate's existing behavior.
        if (
            self.detector is not None
            and
            self.frame_count % 5 == 0
        ):
            try:
                result = (
                    self.detector.process_frame(
                        frame
                    )
                )

                self.record_detection_sample(
                    result
                )

                self.update_baseline_comparison(
                    result
                )

                self.update_validated_risk(
                    result
                )

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

        self._update_preview(
            frame
        )

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
            else "ไม่พบ"
        )

        face_text = (
            "ตรวจพบ"
            if result.get(
                "face_detected"
            )
            else "ไม่พบ"
        )

        self.detection_label.setText(
            f"ท่าทาง: {pose_text} | "
            f"ใบหน้า: {face_text}"
        )

        shoulder = result.get(
            "shoulder_tilt"
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

        neck_result = result.get(
            "neck_lateral_tilt"
        )

        neck = (
            neck_result.get(
                "neck_tilt"
            )
            if isinstance(
                neck_result,
                dict,
            )
            else None
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

        flexion = result.get(
            "neck_flexion"
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
        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
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

        image = QImage(
            frame_rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        ).copy()

        pixmap = QPixmap.fromImage(
            image
        ).scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
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

        self.risk_pipeline.reset()
        self.last_pipeline_result = None

        self.sound_player.notify(
            False
        )

        self.frame_count = 0

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

        self.preview_label.clear()

        self.preview_label.setText(
            "ภาพการตรวจจับจะแสดงที่นี่"
        )

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

        self.session_started_at = None
        self.session_started_monotonic = None

        self.baseline_data = None

        self.baseline_shoulder_label.setText(
            "Baseline Shoulder Tilt: --"
        )

        self.baseline_neck_label.setText(
            "Baseline Neck Lateral Tilt: --"
        )

        self.baseline_flexion_label.setText(
            "Baseline Neck Flexion: --"
        )

        self.detection_count = 0
        self.pose_detected_count = 0
        self.face_detected_count = 0

        self.shoulder_samples.clear()
        self.neck_samples.clear()

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
    # STOP
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
    # SUMMARY
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
            or {}
        )

        camera = (
            self.selected_camera
            or {}
        )

        return {
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
                if self.shoulder_samples
                else None
            ),

            "average_neck": (
                statistics.mean(
                    self.neck_samples
                )
                if self.neck_samples
                else None
            ),

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

            # Local validated pipeline statistics.
            # session_summary_service currently ignores these
            # until persistent Risk Event storage is added.
            "risk_sample_counts": (
                dict(
                    self.risk_sample_counts
                )
            ),

            "alert_notification_count": (
                self.alert_notification_count
            ),
        }

    # ========================================================
    # REMOTE PAUSE / RESUME
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
            response = request_function(
                session_id
            )

        except requests.RequestException:
            pass

        if (
            response is not None
            and
            response.ok
        ):
            data = response.json()

        else:
            check = APIClient.get_session(
                session_id
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

            data = check.json()

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
                f"received {data.get('status')}"
            )

        return data

    def handle_pause_resume(
        self,
    ) -> None:
        if (
            self.session_id is None
            or
            self.is_stopping
            or
            self.capture is None
        ):
            return

        self.pause_button.setEnabled(
            False
        )

        if self.is_paused:
            self._resume_monitoring()

        else:
            self._pause_monitoring()

        if self.session_id is not None:
            self.pause_button.setEnabled(
                True
            )

        self.state_changed.emit()

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

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            QMessageBox.warning(
                self,
                "หยุดชั่วคราวไม่สำเร็จ",
                "ไม่สามารถยืนยันสถานะ "
                "PAUSED ได้\n"
                f"{error}\n"
                "กรุณาตรวจสอบการเชื่อมต่อ",
            )

            return

        self.timer.stop()
        self.is_paused = True

        # Risk continuity must not cross a user pause.
        self.reset_risk_tracking()

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

        self.status_label.setText(
            "สถานะ: หยุดชั่วคราว "
            f"(จำนวนครั้ง: "
            f"{remote['pause_count']})"
        )

        self.pause_button.setText(
            "Resume Monitoring"
        )

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

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            TypeError,
        ) as error:
            QMessageBox.warning(
                self,
                "ตรวจจับต่อไม่สำเร็จ",
                "ไม่สามารถยืนยันสถานะ "
                "RUNNING ได้\n"
                f"{error}\n"
                "กรุณาตรวจสอบการเชื่อมต่อ",
            )

            return

        self.is_paused = False

        # Resume starts a new temporal/risk continuity window.
        self.reset_risk_tracking()

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
    # FINISH
    # ========================================================

    def handle_stop(
        self,
    ) -> None:
        if self.is_stopping:
            return

        self.is_stopping = True
        self.state_changed.emit()

        try:
            self._finish_session()

        finally:
            self.is_stopping = False
            self.state_changed.emit()

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

        # 1. Snapshot statistics before resource reset.
        summary = (
            self.build_session_summary()
        )

        # 2. End authoritative Backend Session.
        try:
            remote = (
                self._end_remote_session()
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
        ) as error:
            QMessageBox.warning(
                self,
                "ไม่สามารถจบเซสชัน",
                "Backend ยังไม่ยืนยันว่า "
                "Session สิ้นสุด\n"
                f"{error}\n"
                "กรุณาตรวจสอบ Backend "
                "แล้วกด Stop อีกครั้ง",
            )

            return

        # 3. Use authoritative backend data.
        summary["database_status"] = (
            remote["status"]
        )

        summary["session_id"] = (
            remote["session_id"]
        )

        summary["started_at"] = (
            remote.get(
                "started_at"
            )
            or
            summary["started_at"]
        )

        summary["ended_at"] = (
            remote.get(
                "ended_at"
            )
            or
            summary["ended_at"]
        )

        summary["duration_seconds"] = (
            remote.get(
                "total_duration"
            )
            if remote.get(
                "total_duration"
            )
            is not None
            else
            summary["duration_seconds"]
        )

        # 4. Release local resources.
        self.stop_monitoring()

        # 5. Save teammate's existing measured summary.
        summary["summary_save_status"] = (
            "FAILED"
        )

        summary["summary_save_error"] = (
            None
        )

        try:
            result = save_session_summary(
                summary
            )

            summary["summary_save_status"] = (
                result["status"]
            )

            summary["saved_summary"] = (
                result["summary"]
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
            ] = str(error)

            QMessageBox.warning(
                self,
                "เกิดข้อผิดพลาดในการบันทึกสรุป",
                "Session สิ้นสุดแล้ว "
                "แต่ยังบันทึก Summary "
                "ไม่สำเร็จ\n\n"
                f"{error}\n\n"
                "สามารถกด Retry "
                "ที่หน้า Summary ได้",
            )

        # 6. Open teammate's summary page.
        self.stop_requested.emit(
            summary
        )

    # Page visibility does not own Session lifetime.
    # MainWindow explicitly ends and saves the Session on
    # Stop, logout, or application close.