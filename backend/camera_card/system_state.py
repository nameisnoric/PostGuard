from enum import Enum


class SystemState(Enum):
    CAMERA_SETUP = "camera_setup"
    CAMERA_SETUP_COMPLETE = "camera_setup_complete"
    PERSONAL_BASELINE = "personal_baseline"
    BASELINE_COMPLETE = "baseline_complete"
    MONITORING = "monitoring"