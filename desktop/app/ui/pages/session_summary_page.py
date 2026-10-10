
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
)


class SessionSummaryPage(QWidget):

    back_requested = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.title_label = QLabel(
            "Session Summary"
        )

        self.description_label = QLabel(
            "Summary of the completed monitoring session."
        )

        # Session Information
        info_group = QGroupBox(
            "Session Information"
        )

        info_layout = QVBoxLayout(info_group)

        self.session_label = QLabel(
            "Session ID: --"
        )

        self.database_label = QLabel(
            "Database Status: --"
        )

        self.camera_label = QLabel(
            "Camera: --"
        )

        self.baseline_label = QLabel(
            "Baseline ID: --"
        )

        self.start_label = QLabel(
            "Started: --"
        )

        self.end_label = QLabel(
            "Ended: --"
        )

        self.duration_label = QLabel(
            "Duration: --"
        )

        for label in (
            self.session_label,
            self.database_label,
            self.camera_label,
            self.baseline_label,
            self.start_label,
            self.end_label,
            self.duration_label,
        ):
            info_layout.addWidget(label)

        # Detection Summary
        result_group = QGroupBox(
            "Detection Summary"
        )

        result_layout = QVBoxLayout(
            result_group
        )

        self.count_label = QLabel(
            "Detection Cycles: --"
        )

        self.pose_label = QLabel(
            "Pose Detected: --"
        )

        self.face_label = QLabel(
            "Face Detected: --"
        )

        self.shoulder_label = QLabel(
            "Average Shoulder Tilt: --"
        )

        self.neck_label = QLabel(
            "Average Neck Lateral Tilt: --"
        )

        self.baseline_shoulder_label = QLabel(
            "Baseline Shoulder Tilt: --"
        )

        self.baseline_neck_label = QLabel(
            "Baseline Neck Lateral Tilt: --"
        )

        for label in (
            self.count_label,
            self.pose_label,
            self.face_label,
            self.shoulder_label,
            self.neck_label,
            self.baseline_shoulder_label,
            self.baseline_neck_label,
        ):
            result_layout.addWidget(label)

        self.note_label = QLabel(
            "Database: Session lifecycle saved "
            "(RUNNING → COMPLETED).\n"
            "Local detection averages are displayed "
            "only; they are NOT stored in the "
            "Session Summary database table.\n"
            "Risk assessment and blink rate "
            "are not enabled yet."
        )

        self.note_label.setWordWrap(True)

        self.back_button = QPushButton(
            "Back to Dashboard"
        )

        self.back_button.clicked.connect(
            lambda: self.back_requested.emit()
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(info_group)
        layout.addWidget(result_group)
        layout.addWidget(self.note_label)
        layout.addStretch()
        layout.addWidget(self.back_button)

    @staticmethod
    def format_angle(value):

        if value is None:
            return "--"

        return f"{value:+.2f}°"

    def set_summary(self, summary: dict) -> None:

        self.session_label.setText(
            f"Session ID: {summary.get('session_id', '--')}"
        )

        self.database_label.setText(
            "Database Status: "
            + str(summary.get("database_status", "--"))
        )

        self.camera_label.setText(
            f"Camera: {summary.get('camera_name', '--')}"
        )

        self.baseline_label.setText(
            f"Baseline ID: {summary.get('baseline_id', '--')}"
        )

        self.start_label.setText(
            f"Started: {summary.get('started_at', '--')}"
        )

        self.end_label.setText(
            f"Ended: {summary.get('ended_at', '--')}"
        )

        seconds = summary.get("duration_seconds") or 0

        minutes, remaining = divmod(
            int(seconds),
            60,
        )

        self.duration_label.setText(
            f"Duration: {minutes:02d}:{remaining:02d}"
        )

        self.count_label.setText(
            "Detection Cycles: "
            + str(summary.get("detection_count", 0))
        )

        self.pose_label.setText(
            "Pose Detected: "
            + str(summary.get("pose_detected_count", 0))
        )

        self.face_label.setText(
            "Face Detected: "
            + str(summary.get("face_detected_count", 0))
        )

        self.shoulder_label.setText(
            "Average Shoulder Tilt: "
            + self.format_angle(
                summary.get("average_shoulder")
            )
        )

        self.neck_label.setText(
            "Average Neck Lateral Tilt: "
            + self.format_angle(
                summary.get("average_neck")
            )
        )

        self.baseline_shoulder_label.setText(
            "Baseline Shoulder Tilt: "
            + self.format_angle(
                summary.get("baseline_shoulder")
            )
        )

        self.baseline_neck_label.setText(
            "Baseline Neck Lateral Tilt: "
            + self.format_angle(
                summary.get("baseline_neck")
            )
        )
