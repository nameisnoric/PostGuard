import cv2

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal
)

from PySide6.QtGui import (
    QImage,
    QPixmap
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QSizePolicy,
    QMessageBox,
    QDialog,
    QFrame,
    QGridLayout,
)

from app.services.detection_service import DetectionService
from app.services.api_client import APIClient
from app.vision.camera_setup.camera_reference_contract import (
    CameraReferenceError,
    prepare_detection_frame,
)
from app.services.personal_baseline_service import (
    BASELINE_COLLECTING,
    BASELINE_FAILED,
    BASELINE_NEED_CONFIRMATION,
    BASELINE_SUCCESS,
    CONFIRMATION_CONFIRMED,
    PersonalBaselineCollector,
)
from app.ui.theme import APP_QSS


def add_detail_rows(layout, rows):
    """Add readable label/value pairs to a popup details card."""
    layout.setColumnStretch(0, 1)
    layout.setColumnStretch(1, 1)
    for row, (label, value) in enumerate(rows):
        name = QLabel(label)
        name.setProperty("role", "muted")
        value_label = QLabel(str(value))
        value_label.setProperty("role", "heading")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(name, row, 0)
        layout.addWidget(value_label, row, 1)


def _normalized_reason(value) -> str:
    return str(value or "").strip().upper()


def _rejections_indicate_visibility_problem(
    rejection_names: list[str],
) -> bool:
    """
    Detect rejection reasons that indicate incomplete posture observations.

    This is intentionally described as a visibility/detection problem.
    It does not claim that lighting is the confirmed cause.
    """
    visibility_tokens = (
        "MISSING",
        "NOT_FOUND",
        "NO_FACE",
        "NO_POSE",
        "LANDMARK",
        "FACE_NOT",
        "POSE_NOT",
        "INSUFFICIENT",
        "OUT_OF_FRAME",
    )

    return any(
        token in reason
        for reason in rejection_names
        for token in visibility_tokens
    )


def _rejections_indicate_contract_problem(
    rejection_names: list[str],
) -> bool:
    contract_tokens = (
        "INVALID_CONTRACT",
        "INVALID_DETECTION_RESULT_CONTRACT",
        "INVALID_FEATURES_CONTRACT",
        "UNSUPPORTED_CONTRACT_VERSION",
        "UNSUPPORTED_STATUS",
        "INVALID_UNIT",
        "INVALID_VALUE",
    )

    return any(
        token in reason
        for reason in rejection_names
        for token in contract_tokens
    )


def build_baseline_failure_message(result: dict) -> str:
    """
    Convert Personal Baseline technical/debug reasons into user-facing guidance.

    This function changes presentation only. It does not change validation
    thresholds, collector state, or session safety rules.
    """
    if not isinstance(result, dict):
        return (
            "ไม่สามารถสร้างค่าท่าทางอ้างอิงได้ "
            "กรุณาตรวจสอบตำแหน่งกล้องและลองใหม่อีกครั้ง"
        )

    failure_reason = _normalized_reason(
        result.get("failure_reason")
    )

    validation = result.get("validation")
    if not isinstance(validation, dict):
        validation = {}

    issues = {
        _normalized_reason(issue)
        for issue in validation.get("issues", [])
        if issue
    }

    rejection_reasons = result.get("rejection_reasons")
    if not isinstance(rejection_reasons, dict):
        rejection_reasons = {}

    rejection_names = [
        _normalized_reason(reason)
        for reason, _count in sorted(
            rejection_reasons.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if reason
    ]

    unstable_issues = {
        "SHOULDER_TILT_UNSTABLE",
        "NECK_LATERAL_UNSTABLE",
        "NECK_FLEXION_UNSTABLE",
        "EYE_DISTANCE_UNSTABLE",
    }

    if issues & unstable_issues:
        return (
            "ท่าทางมีการเปลี่ยนแปลงระหว่างการเก็บค่าอ้างอิง "
            "กรุณานั่งในท่าทำงานตามปกติ ผ่อนคลายศีรษะและหัวไหล่ "
            "และพยายามอยู่นิ่งระหว่างการปรับเทียบ"
        )

    if "LOW_VALID_RATIO" in issues:
        return (
            "ระบบได้รับข้อมูลท่าทางที่สามารถใช้สร้างค่าอ้างอิงได้ไม่เพียงพอ "
            "กรุณาจัดใบหน้าและหัวไหล่ให้อยู่ในภาพอย่างชัดเจน "
            "แล้วลองปรับเทียบอีกครั้ง"
        )

    if (
        failure_reason == "CALIBRATION_TIMEOUT"
        or "CALIBRATION_TIMEOUT" in issues
    ):
        if _rejections_indicate_visibility_problem(
            rejection_names
        ):
            return (
                "ระบบไม่สามารถเก็บข้อมูลท่าทางที่เพียงพอภายในเวลาที่กำหนด "
                "กรุณาจัดใบหน้าและหัวไหล่ให้อยู่ในภาพ "
                "จากนั้นลองปรับเทียบอีกครั้ง"
            )

        if _rejections_indicate_contract_problem(
            rejection_names
        ):
            return (
                "ข้อมูลจากระบบตรวจจับไม่พร้อมสำหรับการสร้างค่าอ้างอิง "
                "กรุณาลองปรับเทียบใหม่ หากยังเกิดปัญหาให้กลับไปเตรียมกล้องอีกครั้ง"
            )

        return (
            "ระบบไม่สามารถเก็บข้อมูลท่าทางที่เพียงพอภายในเวลาที่กำหนด "
            "กรุณานั่งในท่าปกติและอยู่นิ่งระหว่างการปรับเทียบ "
            "แล้วลองใหม่อีกครั้ง"
        )

    if _rejections_indicate_visibility_problem(
        rejection_names
    ):
        return (
            "ระบบตรวจจับใบหน้าและหัวไหล่ได้ไม่ครบถ้วน "
            "กรุณาจัดตำแหน่งให้ใบหน้าและหัวไหล่อยู่ภายในภาพ "
            "แล้วลองปรับเทียบอีกครั้ง"
        )

    if _rejections_indicate_contract_problem(
        rejection_names
    ):
        return (
            "ข้อมูลจากระบบตรวจจับไม่พร้อมสำหรับการสร้างค่าอ้างอิง "
            "กรุณาลองปรับเทียบใหม่ หากยังเกิดปัญหาให้กลับไปเตรียมกล้องอีกครั้ง"
        )

    if failure_reason == "VALIDATION_FAILED":
        return (
            "ข้อมูลที่เก็บได้ยังไม่เหมาะสำหรับใช้เป็นค่าท่าทางอ้างอิง "
            "กรุณานั่งในท่าทำงานตามปกติและอยู่นิ่ง "
            "แล้วลองปรับเทียบอีกครั้ง"
        )

    return (
        "ไม่สามารถสร้างค่าท่าทางอ้างอิงได้ "
        "กรุณาตรวจสอบว่ากล้องเห็นใบหน้าและหัวไหล่ชัดเจน "
        "จากนั้นลองปรับเทียบอีกครั้ง"
    )


class CalibrationCompletedDialog(QDialog):
    """
    Ask the user whether a technically valid Personal Baseline candidate
    represents the posture they want to use as the session reference.

    User confirmation is not medical validation.
    """

    DECISION_USE = "USE"
    DECISION_RECALIBRATE = "RECALIBRATE"
    DECISION_UNSURE = "UNSURE"

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.decision = None

        self.setWindowTitle(
            "PostGuard - ตรวจสอบค่าท่าทางอ้างอิง"
        )
        self.setModal(True)
        self.setFixedWidth(500)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        icon = QLabel("i")
        icon.setProperty("role", "infoIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(50, 50)
        layout.addWidget(
            icon,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        title = QLabel("ตรวจสอบค่าท่าทางอ้างอิง")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        note = QLabel(
            "ท่านี้เป็นท่านั่งทำงานตามปกติของคุณหรือไม่?"
        )
        note.setProperty("role", "muted")
        note.setStyleSheet(
            "font-size: 18px;"
            "font-weight: 800;"
            "color: #0f172a;"
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)

        summary_card = QFrame()

        summary_card.setStyleSheet(
            "QFrame {"
            "background: #ffffff;"
            "border: 1px solid #bfdbfe;"
            "border-left: 4px solid #2563eb;"
            "border-radius: 12px;"
            "}"
        )

        summary_layout = QVBoxLayout(
            summary_card
        )

        summary_layout.setContentsMargins(
            16,
            14,
            16,
            14,
        )

        summary_title = QLabel(
            "ระบบจะใช้ท่านี้เป็นจุดอ้างอิง"
        )

        summary_title.setStyleSheet(
            "font-size: 17px;"
            "font-weight: 800;"
            "color: #0f172a;"
            "border: none;"
        )

        summary_text = QLabel(
            "PostGuard จะใช้ลักษณะหัวไหล่ "
            "การเอียงคอ และการก้มเงยคอ "
            "ของท่านี้เป็นจุดเริ่มต้นสำหรับ "
            "เปรียบเทียบระหว่างการตรวจจับ "
            "โปรดยืนยันเมื่อท่านี้เป็นท่านั่ง "
            "ทำงานตามปกติของคุณ"
        )

        summary_text.setWordWrap(
            True
        )

        summary_text.setStyleSheet(
            "font-size: 12px;"
            "color: #475569;"
            "border: none;"
        )

        summary_layout.addWidget(
            summary_title
        )

        summary_layout.addWidget(
            summary_text
        )

        layout.addWidget(
            summary_card
        )

        technical_title = QLabel(
            "ค่าที่ระบบวัดได้"
        )

        technical_title.setStyleSheet(
            "font-size: 14px;"
            "font-weight: 700;"
            "color: #334155;"
        )

        layout.addWidget(
            technical_title
        )

        card = QFrame()
        card.setProperty("card", True)
        details = QGridLayout(card)
        details.setContentsMargins(18, 16, 18, 16)

        add_detail_rows(
            details,
            (
                (
                    "ความเอียงของหัวไหล่",
                    f"{result['shoulder_tilt']:+.2f}°",
                ),
                (
                    "ความเอียงคอด้านข้าง",
                    f"{result['neck_lateral_tilt']:+.2f}°",
                ),
                (
                    "การก้มเงยของคอ",
                    f"{result['neck_flexion']:+.2f}°",
                ),
                (
                    "ระยะตาในภาพ",
                    f"{result['eye_distance']:.2f} px",
                ),
                (
                    "จำนวนข้อมูลที่ใช้",
                    result["sample_count"],
                ),
                (
                    "สัดส่วนข้อมูลที่ใช้ได้",
                    f"{result['valid_ratio']:.0%}",
                ),
            ),
        )
        layout.addWidget(card)

        state = QLabel(
            "การยืนยันหมายถึงคุณยอมรับค่าที่วัดได้เป็นท่าทางอ้างอิง "
            "ไม่ได้หมายความว่าระบบยืนยันว่าท่านี้ถูกต้องหรือปลอดภัย "
            "ตามหลักการแพทย์"
        )
        state.setProperty("role", "muted")
        state.setWordWrap(True)
        state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state.hide()

        unsure_note = QLabel(
            "หากไม่แน่ใจ แนะนำให้วัดใหม่อีกครั้งเพื่อให้ได้ "
            "ค่าท่าทางที่คุณมั่นใจมากขึ้น"
        )
        unsure_note.setProperty("role", "muted")
        unsure_note.setWordWrap(True)
        unsure_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unsure_note.hide()

        actions = QHBoxLayout()
        actions.setSpacing(8)

        retry = QPushButton("วัดใหม่")
        retry.clicked.connect(
            self._choose_recalibrate
        )

        unsure = QPushButton("ยังไม่แน่ใจ")
        unsure.clicked.connect(
            self._choose_unsure
        )

        done = QPushButton("ใช่ ใช้ท่านี้")
        done.setProperty("variant", "primary")
        done.clicked.connect(
            self._choose_use
        )

        actions.addWidget(retry)
        actions.addWidget(unsure)
        actions.addWidget(done)
        layout.addLayout(actions)

    def _choose_use(self) -> None:
        self.decision = self.DECISION_USE
        self.accept()

    def _choose_recalibrate(self) -> None:
        self.decision = self.DECISION_RECALIBRATE
        self.reject()

    def _choose_unsure(self) -> None:
        self.decision = self.DECISION_UNSURE
        self.reject()


class BaselineSavedDialog(QDialog):
    """Non-blocking confirmation shown after the API saves a baseline."""

    def __init__(self, baseline_id, camera_id, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostGuard - บันทึกค่าอ้างอิงแล้ว")
        self.setModal(True)
        self.setFixedWidth(460)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        icon = QLabel("✓")
        icon.setProperty("role", "successIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(50, 50)
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("บันทึกค่าท่าทางอ้างอิงแล้ว")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        note = QLabel(
            "ค่าท่าทางอ้างอิงพร้อมใช้งาน คุณสามารถเริ่มการตรวจจับได้แล้ว"
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)

        card = QFrame()
        card.setProperty("card", True)
        details = QGridLayout(card)
        details.setContentsMargins(18, 16, 18, 16)
        rows = (
            ("รหัสค่าอ้างอิง", baseline_id),
            ("รหัสกล้อง", camera_id),
            ("ความเอียงของหัวไหล่", f"{result['shoulder_tilt']:+.2f}°"),
            ("ความเอียงคอด้านข้าง", f"{result['neck_lateral_tilt']:+.2f}°"),
            ("การก้มเงยของคอ", f"{result['neck_flexion']:+.2f}°"),
            ("ระยะตาในภาพ", f"{result['eye_distance']:.2f} px"),
        )
        add_detail_rows(details, rows)
        layout.addWidget(card)

        done = QPushButton("เสร็จสิ้น")
        done.setProperty("variant", "primary")
        done.clicked.connect(self.accept)
        layout.addWidget(done)


class BaselinePage(QWidget):

    # ส่งข้อมูลกล้องกลับไป MainWindow
    back_requested = Signal(dict)
    
    monitoring_requested = Signal(dict, int)

    def __init__(self):
        super().__init__()

        # -------------------------
        # Variables
        # -------------------------

        self.selected_camera = None
        self.capture = None
        self.detector = None
        self.frame_count = 0
        
        #Calibrate State
        
        self.is_calibrating = False
        self.baseline_result = None
        self.baseline_collection_result = None
        self.baseline_collector = PersonalBaselineCollector()
        self.required_samples = self.baseline_collector.config.target_samples

        self.saved_baseline_id = None   
        # -------------------------
        # Camera Timer
        # -------------------------

        self.timer = QTimer(self)
        self.timer.setInterval(30)

        self.timer.timeout.connect(
            self.update_frame
        )

        # -------------------------
        # Main Layout
        # -------------------------

        layout = QVBoxLayout(self)
        self.setProperty("page", True)
        layout.setContentsMargins(32, 18, 32, 20)
        layout.setSpacing(8)

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "ตั้งค่าท่าทางอ้างอิง"
        )
        self.title_label.setProperty("role", "title")

        self.description_label = QLabel(
            "ขั้นตอน 4 จาก 4  ·  นั่งในท่าธรรมชาติและอยู่นิ่งขณะระบบเก็บค่าอ้างอิง"
        )
        self.description_label.setProperty("role", "muted")

        # -------------------------
        # Camera Information
        # -------------------------

        camera_group = QGroupBox(
            "กล้องที่เลือก"
        )

        camera_layout = QGridLayout(
            camera_group
        )
        camera_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        camera_group.setStyleSheet(
            "QGroupBox {"
            "font-size: 13px;"
            "font-weight: 700;"
            "color: #334155;"
            "background: #ffffff;"
            "border: 1px solid #dbe4ef;"
            "border-radius: 12px;"
            "margin-top: 12px;"
            "padding-top: 8px;"
            "}"
            "QGroupBox::title {"
            "subcontrol-origin: margin;"
            "left: 12px;"
            "padding: 0 6px;"
            "}"
        )

        self.camera_name_label = QLabel(
            'กล้อง: ยังไม่ได้เลือก'
        )

        self.device_label = QLabel(
            'อุปกรณ์: -'
        )

        self.camera_id_label = QLabel(
            'รหัสกล้อง: -'
        )

        self.resolution_label = QLabel(
            'ความละเอียด: -'
        )
        self.camera_reference_label = QLabel('การเตรียมกล้อง: ยังไม่เสร็จ')
        for label in (
            self.camera_name_label,
            self.device_label,
            self.camera_id_label,
            self.resolution_label,
            self.camera_reference_label,
        ):
            label.setProperty("role", "muted")

        camera_layout.setHorizontalSpacing(32)
        camera_layout.setVerticalSpacing(6)
        camera_layout.addWidget(self.camera_name_label, 0, 0)
        camera_layout.addWidget(self.device_label, 0, 1)
        camera_layout.addWidget(self.camera_id_label, 1, 0)
        camera_layout.addWidget(self.resolution_label, 1, 1)
        camera_layout.addWidget(self.camera_reference_label, 2, 0, 1, 2)
        camera_layout.setColumnStretch(0, 1)
        camera_layout.setColumnStretch(1, 1)

        # -------------------------
        # Camera Preview
        # -------------------------

        self.preview_label = QLabel(
            "ภาพตัวอย่างจากกล้องจะแสดงที่นี่"
        )

        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_label.setMinimumSize(
            640,
            360
        )
        self.preview_label.setMaximumSize(720, 405)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )

        self.preview_label.setProperty("preview", True)

        # -------------------------
        # Calibration Information
        # -------------------------

        calibration_group = QGroupBox(
            "การปรับเทียบ"
        )

        calibration_layout = QVBoxLayout(
            calibration_group
        )
        calibration_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        calibration_group.setStyleSheet(
            "QGroupBox {"
            "font-size: 13px;"
            "font-weight: 700;"
            "color: #334155;"
            "background: #ffffff;"
            "border: 1px solid #dbe4ef;"
            "border-left: 4px solid #2563eb;"
            "border-radius: 12px;"
            "margin-top: 12px;"
            "padding-top: 8px;"
            "}"
            "QGroupBox::title {"
            "subcontrol-origin: margin;"
            "left: 12px;"
            "padding: 0 6px;"
            "}"
        )

        self.instruction_label = QLabel(
            "1. นั่งในท่าทำงานตามปกติ\n"
            "2. ผ่อนคลายศีรษะและหัวไหล่\n"
            "3. หันหน้าเข้าหากล้องและให้ใบหน้าและหัวไหล่อยู่ในภาพ\n"
            "4. อยู่นิ่งระหว่างที่ระบบเก็บค่าท่าทางอ้างอิง"
        )

        self.status_label = QLabel(
            'สถานะ: รอกล้อง'
        )

        # -------------------------
        # Detection Information
        # -------------------------

        self.detection_label = QLabel(
            'ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ'
        )

        self.shoulder_tilt_label = QLabel(
            'ความเอียงไหล่: --'
        )

        self.neck_tilt_label = QLabel(
            'ความเอียงคอด้านข้าง: --'
        )

        calibration_layout.addWidget(
            self.instruction_label
        )

        calibration_layout.addWidget(
            self.status_label
        )

        calibration_layout.addWidget(
            self.detection_label
        )

        calibration_layout.addWidget(
            self.shoulder_tilt_label
        )

        calibration_layout.addWidget(
            self.neck_tilt_label
        )

        # -------------------------
        # Buttons
        # -------------------------

        button_layout = QHBoxLayout()

        self.back_button = QPushButton(
            "กลับไปเตรียมกล้อง"
        )

        self.calibrate_button = QPushButton(
            "เริ่มปรับเทียบ"
        )
        
        self.save_button = QPushButton(
            "บันทึกค่าท่าทางอ้างอิง"
        )
        #Save ไม่ได้จนกว่า calibrate จะเสร็จ
        self.save_button.setEnabled(False)
        
        self.monitor_button = QPushButton(
            "เริ่มตรวจจับ"
        )
        self.monitor_button.setProperty("variant", "primary")
        self.monitor_button.setEnabled(False)
        # ยังไม่เปิดจนกว่าจะทำ Calibration Logic
        self.calibrate_button.setEnabled(False)
        
        button_layout.addWidget(
            self.back_button
        )

        button_layout.addWidget(
            self.calibrate_button
        )
        
        button_layout.addWidget(
            self.save_button
        )
        
        button_layout.addWidget(
            self.monitor_button
        )

        # -------------------------
        # Add Widgets
        # -------------------------

        self.title_label.setStyleSheet(
            "font-size: 28px;"
            "font-weight: 800;"
            "color: #0f172a;"
        )

        self.description_label.setStyleSheet(
            "font-size: 13px;"
            "color: #64748b;"
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.description_label
        )

        body = QHBoxLayout()

        body.setSpacing(
            18
        )

        # ====================================================
        # Camera
        # ====================================================

        preview_card = QFrame()

        preview_card.setStyleSheet(
            "QFrame {"
            "background: #ffffff;"
            "border: 1px solid #dbe4ef;"
            "border-radius: 14px;"
            "}"
        )

        preview_layout = QVBoxLayout(
            preview_card
        )

        preview_layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        preview_title = QLabel(
            "ท่าทางอ้างอิงของคุณ"
        )

        preview_title.setStyleSheet(
            "font-size: 17px;"
            "font-weight: 800;"
            "color: #0f172a;"
            "border: none;"
        )

        preview_note = QLabel(
            "นั่งในท่าทำงานตามปกติ "
            "ให้ใบหน้าและหัวไหล่อยู่ในภาพ "
            "และอยู่นิ่งระหว่างการเก็บค่า"
        )

        preview_note.setWordWrap(
            True
        )

        preview_note.setStyleSheet(
            "font-size: 11px;"
            "color: #64748b;"
            "border: none;"
        )

        preview_layout.addWidget(
            preview_title
        )

        preview_layout.addWidget(
            preview_note
        )

        preview_layout.addWidget(
            self.preview_label,
            1,
        )

        # ====================================================
        # Right Panel
        # ====================================================

        side = QVBoxLayout()

        side.setSpacing(
            12
        )

        side.addWidget(
            camera_group
        )

        side.addWidget(
            calibration_group
        )

        side.addStretch()

        body.addWidget(
            preview_card,
            3,
        )

        body.addLayout(
            side,
            2,
        )

        layout.addLayout(
            body,
            1,
        )

        layout.addLayout(
            button_layout
        )

        # -------------------------
        # Events
        # -------------------------

        self.back_button.clicked.connect(
            self.handle_back
        )
        
        self.calibrate_button.clicked.connect(
            self.start_calibration
        )
        
        self.save_button.clicked.connect(
            self.save_baseline
        )
        
        self.monitor_button.clicked.connect(
            self.handle_start_monitoring
        )

    # =========================================================
    # Receive Camera
    # =========================================================

    def set_camera(
        self,
        camera: dict
    ) -> None:

        self.selected_camera = camera.copy()
        self.is_calibrating = False
        self.baseline_collector.reset()
        self.baseline_result = None
        self.baseline_collection_result = None
        self.saved_baseline_id = None
        self.save_button.setEnabled(False)
        self.monitor_button.setEnabled(False)

        camera_id = camera.get(
            "camera_id"
        )

        camera_name = camera.get(
            "camera_name",
            "กล้องไม่ทราบชื่อ"
        )

        device_index = camera.get(
            "device_index"
        )

        width = camera.get(
            "resolution_width"
        )

        height = camera.get(
            "resolution_height"
        )

        self.camera_id_label.setText(
            f"รหัสกล้อง: {camera_id}"
        )

        self.camera_name_label.setText(
            f"กล้อง: {camera_name}"
        )

        self.device_label.setText(
            f"อุปกรณ์: {device_index}"
        )

        self.resolution_label.setText(
            f"ความละเอียด: {width}x{height}"
        )

        camera_reference = camera.get("camera_calibration")
        if not isinstance(camera_reference, dict) or camera_reference.get("status") != "VALID":
            self.camera_reference_label.setText('การเตรียมกล้อง: จำเป็น')
            self.status_label.setText('สถานะ: โปรดเตรียมกล้องให้เสร็จก่อน')
            self.calibrate_button.setEnabled(False)
            return
        self.camera_reference_label.setText(
            "การเตรียมกล้อง: พร้อมใช้งาน | "
            f"สเกล {camera_reference.get('scale_avg', 0):.2f} px/mm | "
            f"มุมกล้อง {camera_reference.get('card_roll_deg', 0):+.2f}°"
        )

        print(
            "BASELINE CAMERA:",
            self.selected_camera
        )

        # เปิด Webcam และ Detection
        self.start_camera_preview()

    # =========================================================
    # Start Camera Preview
    # =========================================================

    def start_camera_preview(self) -> None:

        # ปิดทรัพยากรเดิมก่อนเปิดใหม่
        self.stop_camera_preview()

        if self.selected_camera is None:
            return

        device_index = self.selected_camera.get(
            "device_index"
        )

        if device_index is None:

            self.status_label.setText(
                'สถานะ: ยังไม่ได้เลือกกล้อง'
            )

            return

        # -------------------------
        # Open Webcam
        # -------------------------

        try:
            self.capture = cv2.VideoCapture(
                int(device_index)
            )

            if not self.capture.isOpened():
                raise RuntimeError(
                    'ไม่สามารถเปิดกล้องที่เลือกได้'
                )

            width = self.selected_camera.get(
                "resolution_width"
            )
            height = self.selected_camera.get(
                "resolution_height"
            )

            if (
                type(width) is int
                and type(height) is int
                and width > 0
                and height > 0
            ):
                self.capture.set(
                    cv2.CAP_PROP_FRAME_WIDTH,
                    width,
                )
                self.capture.set(
                    cv2.CAP_PROP_FRAME_HEIGHT,
                    height,
                )

        except Exception as error:

            self.stop_camera_preview()

            self.status_label.setText(
                'สถานะ: กล้องไม่พร้อมใช้งาน'
            )

            QMessageBox.warning(
                self,
                'ข้อผิดพลาดของกล้อง',
                str(error)
            )

            return

        # -------------------------
        # Initialize Detection
        # -------------------------

        try:
            self.detector = DetectionService()

        except Exception as error:

            self.stop_camera_preview()

            self.status_label.setText(
                'สถานะ: ระบบตรวจจับไม่พร้อมใช้งาน'
            )

            QMessageBox.critical(
                self,
                'ข้อผิดพลาดของระบบตรวจจับ',
                str(error)
            )

            return

        # -------------------------
        # Start Timer
        # -------------------------

        self.frame_count = 0

        self.status_label.setText(
            'สถานะ: กล้องและระบบตรวจจับพร้อม'
        )

       # เปิดปุ่มเมื่อกล้องและ Detection พร้อมแล้ว  
        self.calibrate_button.setEnabled(True)

        self.calibrate_button.setText(
            "เริ่มปรับเทียบ"
        )

        self.timer.start()

    #Start Calibration

    def start_calibration(self) -> None:

        if (
            self.capture is None
            or self.detector is None
        ):
            QMessageBox.warning(
                self,
                "การปรับเทียบ",
                'กล้องหรือระบบตรวจจับยังไม่พร้อม'
            )
            return

        # เริ่มเก็บข้อมูลใหม่
        self.is_calibrating = True

        self.baseline_collector.reset()
        self.required_samples = self.baseline_collector.config.target_samples
        self.baseline_result = None
        self.baseline_collection_result = None
        
        self.saved_baseline_id = None
        self.save_button.setEnabled(False)
        self.monitor_button.setEnabled(False)

        self.calibrate_button.setEnabled(False)

        self.status_label.setText(
            "สถานะ: กำลังเก็บข้อมูล "
            f"0/{self.required_samples} เฟรมที่ใช้ได้ · "
            "0.0/"
            f"{self.baseline_collector.config.min_calibration_seconds:.0f} วินาที"
        )
        
    def collect_calibration_sample(
        self,
        result: dict
    ) -> None:

        if not self.is_calibrating:
            return

        status = self.baseline_collector.add_detection_result(result)
        state = status.get("status")

        if state == BASELINE_COLLECTING:
            count = status.get("sample_count", 0)
            target = status.get("target_samples", self.required_samples)
            elapsed = status.get("elapsed_seconds", 0.0)
            minimum = status.get(
                "min_calibration_seconds",
                self.baseline_collector.config.min_calibration_seconds,
            )
            rejected = status.get("rejected_frames", 0)
            self.status_label.setText(
                "สถานะ: กำลังเก็บข้อมูล "
                f"{count}/{target} เฟรมที่ใช้ได้ · "
                f"{elapsed:.1f}/{minimum:.0f} วินาที · "
                f"ข้าม {rejected} เฟรม"
            )
            return

        self.is_calibrating = False
        self.calibrate_button.setEnabled(True)
        self.calibrate_button.setText('ปรับเทียบใหม่')
        self.baseline_collection_result = status

        if state == BASELINE_FAILED:
            message = build_baseline_failure_message(
                status
            )
            self.status_label.setText(
                "สถานะ: ไม่สามารถสร้างค่าท่าทางอ้างอิงได้"
            )
            QMessageBox.warning(
                self,
                "ไม่สามารถสร้างค่าท่าทางอ้างอิง",
                message,
            )
            return

        if state != BASELINE_NEED_CONFIRMATION:
            self.status_label.setText('สถานะ: ค่าท่าทางอ้างอิงผิดปกติ')
            return

        candidate = status.get("baseline") or {}
        dialog_result = {
            **candidate,
            "sample_count": status.get("sample_count", 0),
            "valid_ratio": status.get("valid_ratio", 0.0),
        }
        self.status_label.setText(
            "สถานะ: เก็บข้อมูลสำเร็จ · รอการยืนยันค่าท่าทางอ้างอิง"
        )
        self.calibration_dialog = CalibrationCompletedDialog(dialog_result, self)
        self.calibration_dialog.accepted.connect(self.confirm_baseline)
        self.calibration_dialog.rejected.connect(self.reject_baseline)
        self.calibration_dialog.open()

    def confirm_baseline(self) -> None:
        """Make a technically valid candidate usable only after user confirmation."""
        try:
            confirmed = self.baseline_collector.confirm()
            usable = self.baseline_collector.get_usable_baseline()
        except RuntimeError as error:
            QMessageBox.warning(self, 'ค่าท่าทางอ้างอิงส่วนบุคคล', str(error))
            return

        statistics_by_feature = confirmed.get("statistics", {})
        self.baseline_result = {
            **usable,
            "shoulder_std": statistics_by_feature.get("shoulder_tilt", {}).get("sd"),
            "neck_std": statistics_by_feature.get("neck_lateral_tilt", {}).get("sd"),
            "neck_flexion_std": statistics_by_feature.get("neck_flexion", {}).get("sd"),
            "eye_distance_std": statistics_by_feature.get("eye_distance", {}).get("sd"),
            "sample_count": confirmed.get("sample_count", 0),
            "valid_ratio": confirmed.get("valid_ratio", 0.0),
            "duration_seconds": confirmed.get("duration_seconds", 0.0),
        }
        self.baseline_collection_result = confirmed
        self.save_button.setEnabled(True)
        self.status_label.setText('สถานะ: ยืนยันค่าท่าทางอ้างอิงแล้ว พร้อมบันทึก')

    def reject_baseline(self) -> None:
        """
        Discard a technically valid candidate because the user does not
        want to use it as the session reference.

        User rejection remains separate from technical validation.
        """
        decision = None

        if hasattr(
            self,
            "calibration_dialog",
        ):
            decision = getattr(
                self.calibration_dialog,
                "decision",
                None,
            )

        if (
            self.baseline_collection_result
            and self.baseline_collection_result.get("status")
            == BASELINE_NEED_CONFIRMATION
        ):
            try:
                self.baseline_collection_result = (
                    self.baseline_collector.reject()
                )
            except RuntimeError:
                pass

        self.baseline_result = None
        self.save_button.setEnabled(False)

        if (
            decision
            == CalibrationCompletedDialog.DECISION_UNSURE
        ):
            self.status_label.setText(
                "สถานะ: ยังไม่ได้ยืนยันค่าอ้างอิง · "
                "แนะนำให้ปรับเทียบอีกครั้ง"
            )
        else:
            self.status_label.setText(
                "สถานะ: ไม่ใช้ค่าที่วัดได้ · "
                "กดปรับเทียบใหม่เพื่อเก็บค่าอีกครั้ง"
            )

    # =========================================================
    # Save Personal Baseline
    # =========================================================

    def save_baseline(self) -> None:

        # -------------------------
        # Validate Calibration
        # -------------------------

        if self.baseline_result is None:

            QMessageBox.warning(
                self,
                'บันทึกค่าอ้างอิง',
                'โปรดปรับเทียบให้เสร็จก่อน'
            )

            return

        if self.selected_camera is None:

            QMessageBox.warning(
                self,
                'บันทึกค่าอ้างอิง',
                "ยังไม่ได้เลือกกล้อง"
            )

            return

        # ป้องกันการบันทึกซ้ำ
        if self.saved_baseline_id is not None:
            return

        camera_id = self.selected_camera.get(
            "camera_id"
        )

        if (
            not isinstance(camera_id, int)
            or camera_id <= 0
        ):

            QMessageBox.warning(
                self,
                'บันทึกค่าอ้างอิง',
                'รหัสกล้องไม่ถูกต้อง'
            )

            return

        # -------------------------
        # Prepare Measurements
        # -------------------------

        measurements = {
            "shoulder_angle": (
                self.baseline_result["shoulder_tilt"]
            ),
            "lateral_tilt_baseline": (
                self.baseline_result["neck_lateral_tilt"]
            ),
            "neck_flexion_baseline": self.baseline_result["neck_flexion"],
            "ipd_baseline": self.baseline_result["eye_distance"],
            "shoulder_tilt_status": "validated_prototype",
            "baseline_status": BASELINE_SUCCESS,
            "confirmation_status": CONFIRMATION_CONFIRMED,
            "baseline_sample_count": self.baseline_result["sample_count"],
            "baseline_duration_seconds": self.baseline_result["duration_seconds"],
            "baseline_valid_ratio": self.baseline_result["valid_ratio"],
            "shoulder_tilt_sd": self.baseline_result["shoulder_std"],
            "neck_lateral_tilt_sd": self.baseline_result["neck_std"],
            "neck_flexion_sd": self.baseline_result["neck_flexion_std"],
            "eye_distance_sd": self.baseline_result["eye_distance_std"],
            "camera_frame_width": self.selected_camera["camera_calibration"]["frame_width"],
            "camera_frame_height": self.selected_camera["camera_calibration"]["frame_height"],
            "camera_scale_x": self.selected_camera["camera_calibration"]["scale_x"],
            "camera_scale_y": self.selected_camera["camera_calibration"]["scale_y"],
            "camera_scale_avg": self.selected_camera["camera_calibration"]["scale_avg"],
            "camera_card_roll": self.selected_camera["camera_calibration"]["card_roll_deg"],
            "camera_horizontal_perspective": self.selected_camera["camera_calibration"]["horizontal_perspective"],
            "camera_vertical_perspective": self.selected_camera["camera_calibration"]["vertical_perspective"],
            "camera_calibrated_at": self.selected_camera["camera_calibration"]["captured_at"],
        }

        # -------------------------
        # Send to Backend
        # -------------------------

        self.save_button.setEnabled(False)

        self.status_label.setText(
            'สถานะ: กำลังบันทึกค่าอ้างอิง...'
        )

        try:

            response = APIClient.create_personal_baseline(
                camera_id=camera_id,
                measurements=measurements
            )

            # -------------------------
            # Check API Response
            # -------------------------

            if response.status_code != 201:

                try:
                    detail = response.json().get(
                        "detail",
                        response.text
                    )
                except ValueError:
                    detail = response.text

                raise RuntimeError(
                    f"HTTP {response.status_code}: {detail}"
                )

            saved_data = response.json()

            baseline_id = saved_data.get(
                "baseline_id"
            )

            if baseline_id is None:
                raise RuntimeError(
                    "เซิร์ฟเวอร์ไม่ส่งรหัสค่าท่าทางอ้างอิงกลับมา"
                )

            # -------------------------
            # Save Successful
            # -------------------------

            self.saved_baseline_id = baseline_id
            
            self.monitor_button.setEnabled(True)

            self.status_label.setText(
                'สถานะ: บันทึกค่าอ้างอิงสำเร็จ'
            )

            print(
                "SAVED PERSONAL BASELINE:",
                saved_data
            )

            self.saved_dialog = BaselineSavedDialog(
                baseline_id,
                camera_id,
                self.baseline_result,
                self,
            )
            self.saved_dialog.open()

        except Exception as error:

            self.status_label.setText(
                'สถานะ: บันทึกค่าอ้างอิงไม่สำเร็จ'
            )

            QMessageBox.warning(
                self,
                'เกิดข้อผิดพลาดในการบันทึกค่าอ้างอิง',
                str(error)
            )

        finally:

            # ถ้าบันทึกไม่สำเร็จ ให้ลองใหม่ได้
            # ถ้าสำเร็จแล้ว ป้องกันการบันทึกซ้ำ
            self.save_button.setEnabled(
                self.baseline_result is not None
                and self.saved_baseline_id is None
            )

    # =========================================================
    # Update Frame
    # =========================================================

    def update_frame(self) -> None:

        if self.capture is None:
            return

        # -------------------------
        # Read Webcam Frame 
        # -------------------------

        success, frame = self.capture.read()

        if not success or frame is None:

            self.stop_camera_preview()

            self.status_label.setText(
                'สถานะ: อ่านภาพจากกล้องไม่สำเร็จ'
            )

            QMessageBox.warning(
                self,
                'ข้อผิดพลาดของกล้อง',
                'ไม่สามารถอ่านภาพจากกล้องได้'
            )

            return

        # Same locked Camera Reference contract as Monitoring.
        try:
            frame = prepare_detection_frame(
                frame,
                self.selected_camera or {},
            )
        except CameraReferenceError as error:
            self.stop_camera_preview()
            self.status_label.setText(
                'สถานะ: ข้อมูลการเตรียมกล้องไม่ถูกต้อง'
            )
            QMessageBox.warning(
                self,
                'การเตรียมกล้อง',
                str(error)
            )
            return

        # -------------------------
        # Count Frames
        # -------------------------

        self.frame_count += 1

        # -------------------------
        # Detection Every 5 Frames
        # -------------------------

        if (
            self.detector is not None
            and self.frame_count % 5 == 0
        ):

            try:
                result = self.detector.process_frame(
                    frame
                )
                
                self.collect_calibration_sample(
                    result
                )

                # -------------------------
                # Pose / Face Status
                # -------------------------

                pose_detected = (
                    result["pose_points"] is not None
                )

                face_detected = result[
                    "face_detected"
                ]

                pose_text = (
                    "ตรวจพบ"
                    if pose_detected
                    else "ไม่พบ"
                )

                face_text = (
                    "ตรวจพบ"
                    if face_detected
                    else "ไม่พบ"
                )

                self.detection_label.setText(
                    f"ท่าทาง: {pose_text} | "
                    f"ใบหน้า: {face_text}"
                )

                # -------------------------
                # Shoulder Tilt
                # -------------------------

                shoulder_tilt = result[
                    "shoulder_tilt"
                ]

                if shoulder_tilt is not None:

                    self.shoulder_tilt_label.setText(
                        "ความเอียงไหล่: "
                        f"{shoulder_tilt:+.2f}°"
                    )

                else:

                    self.shoulder_tilt_label.setText(
                        'ความเอียงไหล่: --'
                    )

                # -------------------------
                # Neck Lateral Tilt
                # -------------------------

                neck_result = result[
                    "neck_lateral_tilt"
                ]

                if neck_result is not None:

                    neck_angle = neck_result[
                        "neck_tilt"
                    ]

                    self.neck_tilt_label.setText(
                        "ความเอียงคอด้านข้าง: "
                        f"{neck_angle:+.2f}°"
                    )

                else:

                    self.neck_tilt_label.setText(
                        'ความเอียงคอด้านข้าง: --'
                    )

            except Exception as error:

                self.stop_camera_preview()

                self.status_label.setText(
                    'สถานะ: ระบบตรวจจับเกิดข้อผิดพลาด'
                )

                QMessageBox.warning(
                    self,
                    'ข้อผิดพลาดของระบบตรวจจับ',
                    str(error)
                )

                return

        # -------------------------
        # Mirror Preview for User
        # -------------------------

        display_frame = cv2.flip(
            frame,
            1,
        )

        # -------------------------
        # Convert Display Frame to RGB
        # -------------------------

        frame_rgb = cv2.cvtColor(
            display_frame,
            cv2.COLOR_BGR2RGB
        )

        height, width, channels = (
            frame_rgb.shape
        )

        bytes_per_line = (
            channels * width
        )

        # -------------------------
        # Convert to QImage
        # -------------------------

        image = QImage(
            frame_rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888
        ).copy()

        # -------------------------
        # Display Frame
        # -------------------------

        pixmap = QPixmap.fromImage(
            image
        )

        pixmap = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.preview_label.setPixmap(
            pixmap
        )

    # =========================================================
    # Stop Camera Preview
    # =========================================================

    def stop_camera_preview(self) -> None:

        # -------------------------
        # Stop Timer
        # -------------------------

        if self.timer.isActive():
            self.timer.stop()

        # -------------------------
        # Close Detection
        # -------------------------

        if self.detector is not None:

            try:
                self.detector.close()

            finally:
                self.detector = None

        # -------------------------
        # Release Webcam
        # -------------------------

        if self.capture is not None:

            if self.capture.isOpened():
                self.capture.release()

            self.capture = None

        # -------------------------
        # Reset Detection Values
        # -------------------------

        self.frame_count = 0
        
        # -------------------------
        # Reset Calibration State
        # -------------------------
        self.monitor_button.setEnabled(False)
        self.is_calibrating = False

        self.baseline_collector.reset()
        self.baseline_result = None
        self.baseline_collection_result = None

        self.calibrate_button.setEnabled(False)

        self.calibrate_button.setText(
            "เริ่มปรับเทียบ"
        )


        self.detection_label.setText(
            'ท่าทาง: กำลังรอ | ใบหน้า: กำลังรอ'
        )

        self.shoulder_tilt_label.setText(
            'ความเอียงไหล่: --'
        )

        self.neck_tilt_label.setText(
            'ความเอียงคอด้านข้าง: --'
        )

        # -------------------------
        # Reset Preview
        # -------------------------

        self.preview_label.clear()

        self.preview_label.setText(
            "ภาพตัวอย่างจากกล้องจะแสดงที่นี่"
        )

        print(
            "BASELINE CAMERA STOPPED"
        )

    # =========================================================
    # Back to Camera Preview
    # =========================================================

    def handle_back(self) -> None:

        if self.selected_camera is None:

            QMessageBox.warning(
                self,
                "PostGuard",
                "ยังไม่ได้เลือกกล้อง"
            )

            return

        camera = self.selected_camera.copy()

        self.stop_camera_preview()

        self.back_requested.emit(
            camera
        )
        


    # =========================================================
    # Stop Camera When Page Is Hidden
    # =========================================================

    def hideEvent(self, event) -> None:

        self.stop_camera_preview()

        super().hideEvent(event)
         
    def handle_start_monitoring(self) -> None:

        if (
            self.selected_camera is None
            or self.saved_baseline_id is None
        ):
            QMessageBox.warning(
                self,
                "การตรวจจับ",
                'โปรดบันทึกค่าท่าทางอ้างอิงส่วนบุคคลก่อน'
            )
            return

        camera = self.selected_camera.copy()
        baseline_id = self.saved_baseline_id

        # ปิดกล้องหน้า Baseline ก่อน
        # เพื่อไม่ให้เปิด Webcam ซ้อนกัน
        self.stop_camera_preview()

        self.monitoring_requested.emit(
            camera,
            baseline_id
        )

