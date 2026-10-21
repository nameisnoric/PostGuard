"""Manual observations required to complete an official RULA lookup."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.ui.theme import APP_QSS
from app.vision.risk_evaluation.rula import assess_full_rula


BODY_OPTIONS = {
    "upper_arm": (
        (1, "20° extension to 20° flexion"),
        (2, ">20° extension or 20–45° flexion"),
        (3, "45–90° flexion"),
        (4, ">90° flexion"),
        (5, "Score 5 after shoulder/abduction/support adjustment"),
        (6, "Score 6 after shoulder/abduction/support adjustment"),
    ),
    "lower_arm": (
        (1, "60–100°"),
        (2, "Outside 60–100°"),
        (3, "Outside range + across midline/outside body"),
    ),
    "wrist": (
        (1, "Neutral"), (2, "Up to 15°"),
        (3, ">15°"), (4, "Score 3 + deviation from midline"),
    ),
    "wrist_twist": ((1, "Mid-range"), (2, "Near end range")),
    "neck": (
        (1, "0–10° flexion"), (2, ">10–20° flexion"),
        (3, ">20° flexion"), (4, "Extension"),
        (5, "Score after twist/side-bend adjustment"),
        (6, "Score after both adjustments"),
    ),
    "trunk": (
        (1, "Erect/supported"), (2, ">0–20° flexion"),
        (3, ">20–60° flexion"), (4, ">60° flexion"),
        (5, "Score after twist/side-bend adjustment"),
        (6, "Score after both adjustments"),
    ),
    "legs": ((1, "Supported and balanced"), (2, "Unsupported/unbalanced")),
}

MUSCLE_OPTIONS = ((0, "No"), (1, "Static >60 s or ≥4 repetitions/min"))
FORCE_OPTIONS = (
    (0, "<2 kg intermittent"), (1, "2–10 kg intermittent"),
    (2, "2–10 kg static/repeated"), (3, ">10 kg or shock/rapid force"),
)

FIELDS = (
    ("upper_arm", "Upper arm", BODY_OPTIONS["upper_arm"]),
    ("lower_arm", "Lower arm", BODY_OPTIONS["lower_arm"]),
    ("wrist", "Wrist", BODY_OPTIONS["wrist"]),
    ("wrist_twist", "Wrist twist", BODY_OPTIONS["wrist_twist"]),
    ("neck", "Neck", BODY_OPTIONS["neck"]),
    ("trunk", "Trunk", BODY_OPTIONS["trunk"]),
    ("legs", "Legs", BODY_OPTIONS["legs"]),
    ("muscle_use_a", "Muscle use — arm/wrist", MUSCLE_OPTIONS),
    ("force_load_a", "Force/load — arm/wrist", FORCE_OPTIONS),
    ("muscle_use_b", "Muscle use — neck/trunk/legs", MUSCLE_OPTIONS),
    ("force_load_b", "Force/load — neck/trunk/legs", FORCE_OPTIONS),
)


class RulaAssessmentDialog(QDialog):
    """Collect observations that the current camera cannot infer safely."""

    def __init__(self, camera_partial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostGuard - Full RULA Assessment")
        self.setStyleSheet(APP_QSS)
        self.setMinimumWidth(620)
        self.result_data = None
        self.controls = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(14)
        title = QLabel("Full RULA Assessment")
        title.setProperty("role", "title")
        note = QLabel(
            "เลือกคะแนนจากการสังเกตท่าทางตามเกณฑ์ RULA การคำนวณนี้ต้องใช้ "
            "ข้อมูลแขน ข้อมือ คอ ลำตัว ขา Muscle Use และ Force/Load ครบทุกช่อง"
        )
        note.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(note)

        partial = camera_partial if isinstance(camera_partial, dict) else {}
        camera_note = QLabel(
            "Camera suggestion: RULA-derived neck lower bound = "
            + (
                str(partial.get("neck_score_lower_bound"))
                if partial.get("neck_score_lower_bound") is not None
                else "N/A"
            )
            + ". ตรวจสอบ Neck twist ก่อนยืนยันคะแนน Neck"
        )
        camera_note.setProperty("role", "muted")
        camera_note.setWordWrap(True)
        layout.addWidget(camera_note)

        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(10)
        for key, label, options in FIELDS:
            control = QComboBox()
            for value, description in options:
                control.addItem(f"{value} — {description}", value)
            self.controls[key] = control
            form.addRow(label, control)
        layout.addLayout(form)

        if partial.get("neck_score_lower_bound") is not None:
            self._select("neck", partial["neck_score_lower_bound"])
        self._select("muscle_use_b", partial.get("muscle_use_score", 0))

        self.preview_label = QLabel("Final RULA: รอการคำนวณ")
        self.preview_label.setProperty("role", "heading")
        layout.addWidget(self.preview_label)

        actions = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        calculate = QPushButton("Calculate and Use")
        calculate.setProperty("variant", "primary")
        calculate.clicked.connect(self._calculate)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(calculate)
        layout.addLayout(actions)

    def _select(self, key, value):
        index = self.controls[key].findData(value)
        if index >= 0:
            self.controls[key].setCurrentIndex(index)

    def _calculate(self):
        observations = {
            key: control.currentData()
            for key, control in self.controls.items()
        }
        result = assess_full_rula(observations)
        self.preview_label.setText(
            f"Final RULA: {result['final_score']}/7 | "
            f"Action Level {result['action_level']}"
        )
        self.result_data = {**result, "observations": observations}
        self.accept()
