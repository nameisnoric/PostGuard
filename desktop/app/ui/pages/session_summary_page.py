from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox
)

class SessionSummaryPage(QWidget):

    back_requested = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.title_label = QLabel("Session Summary")
        self.description_label = QLabel(
            "Summary of the completed monitoring session."
        )

        info_group = QGroupBox("Session Information")
        info_layout = QVBoxLayout(info_group)

        self.camera_label = QLabel("Camera: --")
        self.baseline_label = QLabel("Baseline ID: --")
        self.start_label = QLabel("Started: --")
        self.end_label = QLabel("Ended: --")
        self.duration_label = QLabel("Duration: --")

        for label in (
            self.camera_label,
            self.baseline_label,
            self.start_label,
            self.end_label,
            self.duration_label
        ):
            info_layout.addWidget(label)

        result_group = QGroupBox("Detection Summary")
        result_layout = QVBoxLayout(result_group)

        self.count_label = QLabel("Detection Cycles: --")
        self.pose_label = QLabel("Pose Detected: --")
        self.face_label = QLabel("Face Detected: --")
        self.shoulder_label = QLabel("Average Shoulder Tilt: --")
        self.neck_label = QLabel("Average Neck Lateral Tilt: --")
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
            self.baseline_neck_label
        ):
            result_layout.addWidget(label)

        self.note_label = QLabel(
            "Risk assessment: Not available yet.\n"
            "This summary is not saved to the database."
        )

        self.back_button = QPushButton("Back to Dashboard")
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

        self.camera_label.setText(
            f"Camera: {summary['camera_name']}"
        )

        self.baseline_label.setText(
            f"Baseline ID: {summary['baseline_id']}"
        )

        self.start_label.setText(
            f"Started: {summary['started_at']}"
        )

        self.end_label.setText(
            f"Ended: {summary['ended_at']}"
        )

        seconds = summary["duration_seconds"]
        minutes, remaining = divmod(int(seconds), 60)

        self.duration_label.setText(
            f"Duration: {minutes:02d}:{remaining:02d}"
        )

        self.count_label.setText(
            f"Detection Cycles: {summary['detection_count']}"
        )

        self.pose_label.setText(
            f"Pose Detected: {summary['pose_detected_count']}"
        )

        self.face_label.setText(
            f"Face Detected: {summary['face_detected_count']}"
        )

        self.shoulder_label.setText(
            "Average Shoulder Tilt: "
            + self.format_angle(summary["average_shoulder"])
        )

        self.neck_label.setText(
            "Average Neck Lateral Tilt: "
            + self.format_angle(summary["average_neck"])
        )

        self.baseline_shoulder_label.setText(
            "Baseline Shoulder Tilt: "
            + self.format_angle(summary["baseline_shoulder"])
        )

        self.baseline_neck_label.setText(
            "Baseline Neck Lateral Tilt: "
            + self.format_angle(summary["baseline_neck"])
        )
