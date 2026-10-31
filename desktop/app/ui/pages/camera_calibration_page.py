"""Camera preparation before Personal Baseline.

Final PostGuard Camera Setup workflow
-------------------------------------

    Camera
        ↓
    Automatic Camera Roll detection
        ↓
    Automatic image correction
        ↓
    Reference Card
        ↓
    Personal Baseline
        ↓
    Monitoring

Normal users do NOT need to measure camera angle themselves.

The angle values shown in this page are informational / diagnostic only.
The system automatically decides and applies the correction.

Manual adjustment is only a fallback:
    - Auto cannot find a reliable correction, or
    - the user visually notices that the corrected image is still tilted.

Manual adjustment rotates the SOFTWARE IMAGE.
The user does not physically rotate the webcam.

Sign convention
---------------

The internal estimator uses image/OpenCV coordinates.

Real-camera testing established:

    internal detected +X
        -> physical camera angle -X

    internal detected -X
        -> physical camera angle +X

Therefore:

    displayed_physical_angle = -internal_detected

Do not use the displayed value as the image correction.
The internal correction contract remains unchanged.
"""

import cv2

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
)

from PySide6.QtGui import (
    QImage,
    QPixmap,
)

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.services.camera_setup import (
    CameraCalibrationTracker,
)

from app.services.camera_setup.roll_correction import (
    ROLL_LIMIT_DEG,
    ROLL_SOURCE_AUTO,
    ROLL_SOURCE_USER,
    ROLL_SOURCES,
    AutoRollCollector,
    draw_level_grid,
    level_frame,
    prepare_frame,
)


# ============================================================
# SETTINGS
# ============================================================

ROLL_STEP_DEG = 0.5

# The estimator is heavier than normal preview rendering.
ESTIMATE_EVERY_N_FRAMES = 3


# ============================================================
# DISPLAY HELPERS
# ============================================================

def display_camera_tilt_deg(
    internal_detected_deg,
):
    """
    Convert internal image-coordinate tilt into the
    physical Camera Roll convention shown to the user.

    DISPLAY ONLY.

        internal +4°
            -> displayed -4°

        internal -4°
            -> displayed +4°
    """

    if internal_detected_deg is None:
        return None

    value = -float(
        internal_detected_deg
    )

    if abs(value) < 0.005:
        return 0.0

    return value


def display_image_rotation_deg(
    correction_deg,
):
    """
    Return the actual OpenCV image correction.
    """

    if correction_deg is None:
        return None

    value = float(
        correction_deg
    )

    if abs(value) < 0.005:
        return 0.0

    return value


# ============================================================
# PAGE
# ============================================================

class CameraCalibrationPage(
    QWidget
):

    back_requested = Signal(
        dict
    )

    continue_requested = Signal(
        dict,
        dict,
    )

    def __init__(
        self,
    ):
        super().__init__()

        self.setProperty(
            "page",
            True,
        )

        self.capture = None

        self.selected_camera = None

        self.calibration_reference = None

        self.completion_notified = False

        self.tracker = (
            CameraCalibrationTracker(
                stable_frames=10
            )
        )

        # ====================================================
        # Camera Roll state
        # ====================================================

        self.auto_roll = (
            AutoRollCollector()
        )

        self.locked_roll = None

        self.manual_mode = False

        self.frame_index = 0

        # ====================================================
        # Camera timer
        # ====================================================

        self.timer = QTimer(
            self
        )

        self.timer.setInterval(
            30
        )

        self.timer.timeout.connect(
            self.update_frame
        )

        # ====================================================
        # Root layout
        # ====================================================

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            48,
            24,
            48,
            32,
        )

        layout.setSpacing(
            12
        )

        title = QLabel(
            "เตรียมกล้อง"
        )

        title.setProperty(
            "role",
            "title",
        )

        subtitle = QLabel(
            "Step 3 of 4  ·  "
            "PostGuard จะตรวจและปรับแนวภาพจากกล้องให้อัตโนมัติ "
            "จากนั้นใช้บัตรขนาดมาตรฐานเพื่อสร้าง Camera Reference"
        )

        subtitle.setProperty(
            "role",
            "muted",
        )

        subtitle.setWordWrap(
            True
        )

        layout.addWidget(
            title
        )

        layout.addWidget(
            subtitle
        )

        body = QHBoxLayout()

        body.setSpacing(
            16
        )

        # ====================================================
        # Preview
        # ====================================================

        preview_card = QFrame()

        preview_card.setProperty(
            "card",
            True,
        )

        preview_layout = QVBoxLayout(
            preview_card
        )

        preview_layout.setContentsMargins(
            16,
            14,
            16,
            16,
        )

        preview_layout.setSpacing(
            10
        )

        self.preview_label = QLabel(
            "ภาพสำหรับเตรียมกล้องจะแสดงที่นี่"
        )

        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_label.setProperty(
            "preview",
            True,
        )

        self.preview_label.setMinimumSize(
            640,
            360,
        )

        self.preview_label.setMaximumSize(
            820,
            461,
        )

        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )

        preview_layout.addWidget(
            self.preview_label,
            1,
        )

        body.addWidget(
            preview_card,
            3,
        )

        # ====================================================
        # Status
        # ====================================================

        status_card = QFrame()

        status_card.setProperty(
            "card",
            True,
        )

        status_layout = QVBoxLayout(
            status_card
        )

        status_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        status_layout.setSpacing(
            10
        )

        heading = QLabel(
            "ข้อมูลอ้างอิงกล้อง"
        )

        heading.setProperty(
            "role",
            "heading",
        )

        status_layout.addWidget(
            heading
        )

        self.camera_label = QLabel(
            "กล้อง: --"
        )

        self.camera_label.setProperty(
            "role",
            "muted",
        )

        self.guidance_label = QLabel(
            "กำลังตรวจและปรับแนวภาพอัตโนมัติ..."
        )

        self.guidance_label.setWordWrap(
            True
        )

        self.progress_label = QLabel(
            "เฟรมบัตรที่นิ่ง: 0 / 10"
        )

        self.progress_label.setProperty(
            "role",
            "muted",
        )

        status_layout.addWidget(
            self.camera_label
        )

        status_layout.addWidget(
            self.guidance_label
        )

        status_layout.addWidget(
            self.progress_label
        )

        # ====================================================
        # Diagnostic information
        # ====================================================

        diagnostic_title = QLabel(
            "รายละเอียดการปรับแนวภาพ"
        )

        diagnostic_title.setProperty(
            "role",
            "muted",
        )

        self.alignment_label = QLabel(
            "สถานะ:\nกำลังตรวจสอบ"
        )

        self.detected_label = QLabel(
            "มุมกล้องที่ระบบประเมิน:\n--"
        )

        self.applied_label = QLabel(
            "การหมุนภาพที่ใช้:\n--"
        )

        for label in (
            self.alignment_label,
            self.detected_label,
            self.applied_label,
        ):
            label.setProperty(
                "role",
                "muted",
            )

        status_layout.addWidget(
            diagnostic_title
        )

        status_layout.addWidget(
            self.alignment_label
        )

        status_layout.addWidget(
            self.detected_label
        )

        status_layout.addWidget(
            self.applied_label
        )

        # ====================================================
        # Manual override
        # ====================================================

        self.manual_button = QPushButton(
            "ปรับแนวภาพเอง"
        )

        self.manual_button.clicked.connect(
            self.start_manual_roll
        )

        self.manual_button.hide()

        status_layout.addWidget(
            self.manual_button
        )

        # ====================================================
        # Manual panel
        # ====================================================

        self.manual_panel = QWidget()

        manual_layout = QVBoxLayout(
            self.manual_panel
        )

        manual_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        manual_layout.setSpacing(
            6
        )

        self.roll_hint_label = QLabel(
            "ใช้เมื่อภาพยังดูเอียงหลังจากระบบปรับอัตโนมัติ "
            "เลื่อนแถบเพื่อหมุนภาพบนหน้าจอจนแนวประตู ผนัง "
            "หรือโต๊ะขนานกับเส้นตาราง "
            "ไม่ต้องหมุนกล้องจริง"
        )

        self.roll_hint_label.setProperty(
            "role",
            "muted",
        )

        self.roll_hint_label.setWordWrap(
            True
        )

        self.roll_value_label = QLabel(
            "การหมุนภาพ: +0.0°"
        )

        self.roll_value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        limit_steps = int(
            ROLL_LIMIT_DEG
            /
            ROLL_STEP_DEG
        )

        self.roll_slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.roll_slider.setRange(
            -limit_steps,
            limit_steps,
        )

        self.roll_slider.setValue(
            0
        )

        self.roll_slider.valueChanged.connect(
            self.handle_roll_changed
        )

        self.roll_confirm_button = QPushButton(
            "ยืนยันแนวภาพ"
        )

        self.roll_confirm_button.clicked.connect(
            self.confirm_roll
        )

        manual_layout.addWidget(
            self.roll_hint_label
        )

        manual_layout.addWidget(
            self.roll_value_label
        )

        manual_layout.addWidget(
            self.roll_slider
        )

        manual_layout.addWidget(
            self.roll_confirm_button
        )

        self.manual_panel.hide()

        status_layout.addWidget(
            self.manual_panel
        )

        # ====================================================
        # Camera Reference results
        # ====================================================

        result_grid = QGridLayout()

        result_grid.setHorizontalSpacing(
            12
        )

        self.result_values = {}

        fields = (
            (
                "resolution",
                "Reference resolution",
            ),
            (
                "scale",
                "Pixel scale",
            ),
            (
                "roll",
                "Card orientation",
            ),
            (
                "perspective",
                "Perspective difference",
            ),
        )

        for row, (
            key,
            label,
        ) in enumerate(
            fields
        ):
            name = QLabel(
                label
            )

            name.setProperty(
                "role",
                "muted",
            )

            value = QLabel(
                "--"
            )

            value.setAlignment(
                Qt.AlignmentFlag.AlignRight
            )

            self.result_values[
                key
            ] = value

            result_grid.addWidget(
                name,
                row,
                0,
            )

            result_grid.addWidget(
                value,
                row,
                1,
            )

        status_layout.addLayout(
            result_grid
        )

        privacy = QLabel(
            "ภาพจากกล้องและภาพบัตรจะอยู่บนอุปกรณ์นี้ "
            "โดยไม่บันทึกหรืออัปโหลด"
        )

        privacy.setProperty(
            "role",
            "muted",
        )

        privacy.setWordWrap(
            True
        )

        status_layout.addStretch()

        status_layout.addWidget(
            privacy
        )

        body.addWidget(
            status_card,
            2,
        )

        layout.addLayout(
            body,
            1,
        )

        # ====================================================
        # Navigation
        # ====================================================

        actions = QHBoxLayout()

        self.back_button = QPushButton(
            "กลับไปดูภาพตัวอย่าง"
        )

        self.retry_button = QPushButton(
            "เริ่มเตรียมกล้องใหม่"
        )

        self.continue_button = QPushButton(
            "ไปยังค่าท่าทางอ้างอิงส่วนบุคคล"
        )

        self.continue_button.setProperty(
            "variant",
            "primary",
        )

        self.continue_button.setEnabled(
            False
        )

        self.back_button.clicked.connect(
            self.handle_back
        )

        self.retry_button.clicked.connect(
            self.restart_preparation
        )

        self.continue_button.clicked.connect(
            self.handle_continue
        )

        actions.addWidget(
            self.back_button
        )

        actions.addWidget(
            self.retry_button
        )

        actions.addStretch()

        actions.addWidget(
            self.continue_button
        )

        layout.addLayout(
            actions
        )

    # ========================================================
    # Camera lifecycle
    # ========================================================

    def set_camera(
        self,
        camera,
    ):
        self.stop_camera()

        self.selected_camera = (
            camera.copy()
        )

        self._reset_all()

        self.camera_label.setText(
            f"กล้อง: "
            f"{camera.get('camera_name', 'ไม่ทราบ')} | "
            f"{camera.get('resolution_width', '--')}x"
            f"{camera.get('resolution_height', '--')}"
        )

        self._open_camera()

    def _open_camera(
        self,
    ):
        if not self.selected_camera:
            return

        device_index = (
            self.selected_camera.get(
                "device_index"
            )
        )

        if (
            type(device_index)
            is not int
            or
            device_index < 0
        ):
            QMessageBox.warning(
                self,
                "การเตรียมกล้อง",
                "ต้องเลือกอุปกรณ์กล้องที่ถูกต้อง",
            )

            return

        self.capture = cv2.VideoCapture(
            device_index
        )

        if not self.capture.isOpened():
            self.stop_camera()

            QMessageBox.critical(
                self,
                "การเตรียมกล้อง",
                "ไม่สามารถเปิดกล้องที่เลือกได้",
            )

            return

        width = (
            self.selected_camera.get(
                "resolution_width"
            )
        )

        height = (
            self.selected_camera.get(
                "resolution_height"
            )
        )

        if (
            type(width) is int
            and
            type(height) is int
        ):
            self.capture.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                width,
            )

            self.capture.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                height,
            )

        self.timer.start()

    def restart_preparation(
        self,
    ):
        self._reset_all()

        if self.capture is None:
            self._open_camera()

    def _reset_all(
        self,
    ):
        self.tracker.reset()

        self.calibration_reference = None

        self.completion_notified = False

        self.auto_roll.reset()

        self.locked_roll = None

        self.manual_mode = False

        self.frame_index = 0

        self.roll_slider.blockSignals(
            True
        )

        self.roll_slider.setValue(
            0
        )

        self.roll_slider.blockSignals(
            False
        )

        self.roll_value_label.setText(
            "การหมุนภาพ: +0.0°"
        )

        self.manual_panel.hide()

        self.manual_button.hide()

        self.continue_button.setEnabled(
            False
        )

        self._clear_result()

        self._show_roll_status(
            "DETECTING"
        )

        self.guidance_label.setText(
            "กำลังตรวจและปรับแนวภาพอัตโนมัติ..."
        )

    # ========================================================
    # Card guidance
    # ========================================================

    def _card_guidance_text(
        self,
        result,
    ):
        """
        Convert Card Tracker guidance into user-facing Thai.

        The tracker may internally return English messages.
        The UI must not expose those raw implementation strings.

        We primarily use the tracker state rather than requiring
        the normal user to interpret calibration terminology.
        """

        reference = result.get(
            "reference"
        )

        stable_count = int(
            result.get(
                "stable_count",
                0,
            )
            or
            0
        )

        stable_frames = int(
            result.get(
                "stable_frames",
                self.tracker.stable_frames,
            )
            or
            self.tracker.stable_frames
        )

        raw_guidance = str(
            result.get(
                "guidance",
                "",
            )
            or
            ""
        )

        lower = (
            raw_guidance
            .strip()
            .lower()
        )

        if reference is not None:
            return (
                "ตรวจบัตรสำเร็จ "
                "Camera Reference พร้อมใช้งาน"
            )

        # Common tracker guidance mappings.
        if (
            "place"
            in lower
            and
            "card"
            in lower
        ):
            return (
                "วางบัตรขนาดมาตรฐานภายในกรอบ "
                "แล้วถือให้นิ่ง"
            )

        if (
            "hold"
            in lower
            and
            "steady"
            in lower
        ):
            return (
                "ถือบัตรให้นิ่งภายในกรอบ "
                f"กำลังตรวจสอบ {stable_count}/{stable_frames}"
            )

        if (
            "steady"
            in lower
        ):
            return (
                "ถือบัตรให้นิ่งภายในกรอบ "
                f"กำลังตรวจสอบ {stable_count}/{stable_frames}"
            )

        if (
            "move"
            in lower
            and
            "closer"
            in lower
        ):
            return (
                "ขยับบัตรเข้าใกล้กล้องเล็กน้อย "
                "และให้อยู่ภายในกรอบ"
            )

        if (
            "move"
            in lower
            and
            (
                "farther"
                in lower
                or
                "further"
                in lower
            )
        ):
            return (
                "ขยับบัตรออกจากกล้องเล็กน้อย "
                "และให้อยู่ภายในกรอบ"
            )

        if (
            "perspective"
            in lower
            or
            "parallel"
            in lower
        ):
            return (
                "ถือบัตรให้หันตรงเข้าหากล้อง "
                "และพยายามให้ขอบบัตรขนานกับกรอบ"
            )

        if (
            "inside"
            in lower
            and
            "guide"
            in lower
        ):
            return (
                "จัดบัตรให้อยู่ภายในกรอบทั้งหมด "
                "แล้วถือให้นิ่ง"
            )

        if stable_count > 0:
            return (
                "ถือบัตรให้นิ่งภายในกรอบ "
                f"กำลังตรวจสอบ {stable_count}/{stable_frames}"
            )

        # Safe user-facing fallback.
        return (
            "วางบัตรขนาดมาตรฐานภายในกรอบ "
            "แล้วถือให้นิ่ง"
        )

    # ========================================================
    # Frame loop
    # ========================================================

    def update_frame(
        self,
    ):
        if (
            self.capture is None
            or
            not self.capture.isOpened()
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
            self.stop_camera()

            self.guidance_label.setText(
                "ไม่สามารถอ่านภาพจากกล้องได้"
            )

            return

        # ====================================================
        # STEP 1 — CAMERA ROLL
        # ====================================================

        if self.locked_roll is None:

            # ------------------------------------------------
            # Manual fallback
            # ------------------------------------------------

            if self.manual_mode:
                preview = level_frame(
                    frame,
                    self.current_roll_deg(),
                )

                draw_level_grid(
                    preview
                )

                self._show_frame(
                    cv2.flip(
                        preview,
                        1,
                    )
                )

                return

            # ------------------------------------------------
            # Automatic detection
            # ------------------------------------------------

            self.frame_index += 1

            if (
                self.frame_index
                %
                ESTIMATE_EVERY_N_FRAMES
                ==
                0
            ):
                status = (
                    self.auto_roll.add(
                        frame
                    )
                )

                self._show_auto_candidate(
                    status
                )

                if (
                    status
                    ==
                    AutoRollCollector.AUTO
                ):
                    self._lock_roll(
                        self.auto_roll.roll_correction_deg,
                        ROLL_SOURCE_AUTO,
                        self.auto_roll.detected_camera_tilt_deg,
                    )

                elif (
                    status
                    ==
                    AutoRollCollector.UNAVAILABLE
                ):
                    self._show_roll_status(
                        "AUTO UNAVAILABLE",
                        keep_candidate=True,
                    )

                    self.start_manual_roll()

            if self.locked_roll is None:
                preview = (
                    frame.copy()
                )

                draw_level_grid(
                    preview
                )

                self._show_frame(
                    cv2.flip(
                        preview,
                        1,
                    )
                )

                return

        # ====================================================
        # STEP 2 — REFERENCE CARD
        # ====================================================

        corrected = prepare_frame(
            frame,
            self.roll_fields(),
        )

        result = self.tracker.process(
            cv2.flip(
                corrected,
                1,
            )
        )

        # Never show raw English Card Tracker guidance.
        self.guidance_label.setText(
            self._card_guidance_text(
                result
            )
        )

        self.progress_label.setText(
            f"เฟรมบัตรที่นิ่ง: "
            f"{result['stable_count']} / "
            f"{result['stable_frames']}"
        )

        if (
            result[
                "reference"
            ]
            is not None
            and
            self.calibration_reference
            is None
        ):
            reference = (
                result[
                    "reference"
                ].copy()
            )

            reference.update(
                self.roll_fields()
            )

            self._complete_preparation(
                reference
            )

        self._show_frame(
            result[
                "display_frame"
            ]
        )

    # ========================================================
    # Auto candidate display
    # ========================================================

    def _show_auto_candidate(
        self,
        status,
    ):
        internal_detected = (
            self.auto_roll
            .latest_detected_camera_tilt_deg
        )

        correction = (
            self.auto_roll
            .latest_candidate_correction_deg
        )

        physical_tilt = (
            display_camera_tilt_deg(
                internal_detected
            )
        )

        image_rotation = (
            display_image_rotation_deg(
                correction
            )
        )

        if (
            status
            ==
            AutoRollCollector.DETECTING
        ):
            self.alignment_label.setText(
                "สถานะ:\nกำลังตรวจสอบ"
            )

        if physical_tilt is None:
            self.detected_label.setText(
                "มุมกล้องที่ระบบประเมิน:\n--"
            )

        else:
            self.detected_label.setText(
                f"มุมกล้องที่ระบบประเมิน:\n"
                f"{physical_tilt:+.2f}°"
            )

        if image_rotation is None:
            self.applied_label.setText(
                "การหมุนภาพที่เตรียมใช้:\n--"
            )

        else:
            self.applied_label.setText(
                f"การหมุนภาพที่เตรียมใช้:\n"
                f"{image_rotation:+.2f}°"
            )

    # ========================================================
    # Roll state
    # ========================================================

    def current_roll_deg(
        self,
    ):
        return (
            self.roll_slider.value()
            *
            ROLL_STEP_DEG
        )

    def roll_fields(
        self,
    ):
        if self.locked_roll is None:
            return {}

        return {
            "roll_correction_deg":
                self.locked_roll[
                    "deg"
                ],

            "roll_correction_source":
                self.locked_roll[
                    "source"
                ],
        }

    def _lock_roll(
        self,
        deg,
        source,
        detected=None,
    ):
        self.locked_roll = {
            "deg":
                float(
                    deg
                ),

            "source":
                source,

            "detected":
                detected,
        }

        self.manual_mode = False

        self.manual_panel.hide()

        self.manual_button.show()

        self.tracker.reset()

        if (
            source
            ==
            ROLL_SOURCE_AUTO
        ):
            self._show_roll_status(
                "AUTO"
            )

            self.guidance_label.setText(
                "ปรับแนวภาพอัตโนมัติเรียบร้อย "
                "วางบัตรขนาดมาตรฐานภายในกรอบเพื่อดำเนินการต่อ"
            )

        else:
            self._show_roll_status(
                "MANUAL"
            )

            self.guidance_label.setText(
                "ยืนยันแนวภาพเรียบร้อย "
                "วางบัตรขนาดมาตรฐานภายในกรอบเพื่อดำเนินการต่อ"
            )

    # ========================================================
    # Manual fallback / override
    # ========================================================

    def start_manual_roll(
        self,
    ):
        start_deg = (
            self.locked_roll[
                "deg"
            ]
            if self.locked_roll
            else
            0.0
        )

        self.locked_roll = None

        self.manual_mode = True

        self._invalidate_card_reference()

        steps = round(
            start_deg
            /
            ROLL_STEP_DEG
        )

        limit = int(
            ROLL_LIMIT_DEG
            /
            ROLL_STEP_DEG
        )

        self.roll_slider.blockSignals(
            True
        )

        self.roll_slider.setValue(
            max(
                -limit,
                min(
                    limit,
                    steps,
                ),
            )
        )

        self.roll_slider.blockSignals(
            False
        )

        self.roll_value_label.setText(
            f"การหมุนภาพ: "
            f"{self.current_roll_deg():+.1f}°"
        )

        self.manual_button.hide()

        self.manual_panel.show()

        self._show_roll_status(
            "MANUAL",
            keep_candidate=True,
        )

        self.guidance_label.setText(
            "ปรับแนวภาพด้วยตนเอง: "
            "เลื่อนแถบจนแนวผนัง ประตู หรือโต๊ะขนานกับเส้นตาราง "
            "จากนั้นกดยืนยันแนวภาพ"
        )

    def handle_roll_changed(
        self,
        _value,
    ):
        self.roll_value_label.setText(
            f"การหมุนภาพ: "
            f"{self.current_roll_deg():+.1f}°"
        )

    def confirm_roll(
        self,
    ):
        if not self.manual_mode:
            return

        self._lock_roll(
            self.current_roll_deg(),
            ROLL_SOURCE_USER,
            detected=None,
        )

    def _invalidate_card_reference(
        self,
    ):
        self.tracker.reset()

        self.calibration_reference = None

        self.completion_notified = False

        self.continue_button.setEnabled(
            False
        )

        self._clear_result()

    # ========================================================
    # Roll status
    # ========================================================

    def _show_roll_status(
        self,
        status,
        keep_candidate=False,
    ):
        if status == "AUTO":
            friendly_status = (
                "ปรับอัตโนมัติเรียบร้อย"
            )

        elif status == "MANUAL":
            friendly_status = (
                "ปรับด้วยตนเอง"
            )

        elif status == "AUTO UNAVAILABLE":
            friendly_status = (
                "ไม่สามารถปรับอัตโนมัติได้"
            )

        else:
            friendly_status = (
                "กำลังตรวจสอบ"
            )

        self.alignment_label.setText(
            f"สถานะ:\n"
            f"{friendly_status}"
        )

        if self.locked_roll is not None:
            internal_detected = (
                self.locked_roll[
                    "detected"
                ]
            )

            physical_tilt = (
                display_camera_tilt_deg(
                    internal_detected
                )
            )

            image_rotation = (
                display_image_rotation_deg(
                    self.locked_roll[
                        "deg"
                    ]
                )
            )

            if physical_tilt is None:
                self.detected_label.setText(
                    "มุมกล้องที่ระบบประเมิน:\n"
                    "ปรับด้วยตนเอง"
                )

            else:
                self.detected_label.setText(
                    f"มุมกล้องที่ระบบประเมิน:\n"
                    f"{physical_tilt:+.2f}°"
                )

            self.applied_label.setText(
                f"การหมุนภาพที่ใช้:\n"
                f"{image_rotation:+.2f}°"
            )

            return

        if keep_candidate:
            internal_detected = (
                self.auto_roll
                .latest_detected_camera_tilt_deg
            )

            correction = (
                self.auto_roll
                .latest_candidate_correction_deg
            )

            physical_tilt = (
                display_camera_tilt_deg(
                    internal_detected
                )
            )

            image_rotation = (
                display_image_rotation_deg(
                    correction
                )
            )

            if physical_tilt is None:
                self.detected_label.setText(
                    "ค่าล่าสุดที่ระบบประเมิน:\n--"
                )

            else:
                self.detected_label.setText(
                    f"ค่าล่าสุดที่ระบบประเมิน:\n"
                    f"{physical_tilt:+.2f}°"
                )

            if image_rotation is None:
                self.applied_label.setText(
                    "การหมุนภาพที่แนะนำ:\n--"
                )

            else:
                self.applied_label.setText(
                    f"การหมุนภาพที่แนะนำ:\n"
                    f"{image_rotation:+.2f}°"
                )

            return

        self.detected_label.setText(
            "มุมกล้องที่ระบบประเมิน:\n--"
        )

        self.applied_label.setText(
            "การหมุนภาพที่ใช้:\n--"
        )

    # ========================================================
    # Card completion
    # ========================================================

    def _complete_preparation(
        self,
        reference,
    ):
        self.calibration_reference = (
            reference.copy()
        )

        self.continue_button.setEnabled(
            True
        )

        self._show_result(
            self.calibration_reference
        )

        self.guidance_label.setText(
            "เตรียมกล้องและ Camera Reference สำเร็จ "
            "สามารถไปสร้างค่าท่าทางอ้างอิงส่วนบุคคลได้"
        )

        if self.completion_notified:
            return

        self.completion_notified = True

        QMessageBox.information(
            self,
            "เตรียมกล้องสำเร็จ",

            "เตรียมกล้องสำเร็จ\n\n"

            "ระบบได้ปรับแนวภาพและสร้าง "
            "Camera Reference เรียบร้อยแล้ว\n\n"

            f"เฟรมบัตรที่นิ่ง: "
            f"{self.tracker.stable_frames}/"
            f"{self.tracker.stable_frames}\n"

            f"Pixel scale: "
            f"{reference['scale_avg']:.2f} px/mm\n\n"

            "สามารถไปสร้างค่าท่าทางอ้างอิงส่วนบุคคลต่อได้",
        )

    # ========================================================
    # Display
    # ========================================================

    def _show_frame(
        self,
        frame,
    ):
        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
        )

        (
            height,
            width,
            channels,
        ) = rgb.shape

        image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        ).copy()

        pixmap = (
            QPixmap.fromImage(
                image
            ).scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        self.preview_label.setPixmap(
            pixmap
        )

    def _show_result(
        self,
        reference,
    ):
        self.result_values[
            "resolution"
        ].setText(
            f"{reference['frame_width']}x"
            f"{reference['frame_height']}"
        )

        self.result_values[
            "scale"
        ].setText(
            f"{reference['scale_avg']:.2f} px/mm"
        )

        self.result_values[
            "roll"
        ].setText(
            f"{reference['card_roll_deg']:+.2f}°"
        )

        self.result_values[
            "perspective"
        ].setText(
            f"H "
            f"{reference['horizontal_perspective']:.1%}"
            f" | "
            f"V "
            f"{reference['vertical_perspective']:.1%}"
        )

    def _clear_result(
        self,
    ):
        for value in (
            self.result_values.values()
        ):
            value.setText(
                "--"
            )

        self.progress_label.setText(
            "เฟรมบัตรที่นิ่ง: 0 / 10"
        )

    # ========================================================
    # Navigation / cleanup
    # ========================================================

    def stop_camera(
        self,
    ):
        self.timer.stop()

        if self.capture is not None:
            if self.capture.isOpened():
                self.capture.release()

            self.capture = None

        self.preview_label.clear()

        self.preview_label.setText(
            "ภาพสำหรับเตรียมกล้องจะแสดงที่นี่"
        )

    def handle_back(
        self,
    ):
        camera = (
            self.selected_camera.copy()
            if self.selected_camera
            else {}
        )

        self.stop_camera()

        self.back_requested.emit(
            camera
        )

    def handle_continue(
        self,
    ):
        if (
            not self.selected_camera
            or
            not self.calibration_reference
        ):
            return

        if (
            self.calibration_reference.get(
                "roll_correction_source"
            )
            not in
            ROLL_SOURCES
        ):
            return

        camera = (
            self.selected_camera.copy()
        )

        reference = (
            self.calibration_reference.copy()
        )

        self.stop_camera()

        self.continue_requested.emit(
            camera,
            reference,
        )

    def hideEvent(
        self,
        event,
    ):
        self.stop_camera()

        super().hideEvent(
            event
        )