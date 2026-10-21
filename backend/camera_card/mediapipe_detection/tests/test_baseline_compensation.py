from __future__ import annotations

import csv
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2


# ==========================================================
# PATH SETUP
# ==========================================================

THIS_FILE = Path(__file__).resolve()
BACKEND_DIR = THIS_FILE.parents[3]
CAMERA_CARD_DIR = THIS_FILE.parents[2]

for path in (BACKEND_DIR, CAMERA_CARD_DIR):
    path_text = str(path)

    if path_text not in sys.path:
        sys.path.insert(0, path_text)


# ==========================================================
# POSTGUARD IMPORTS
# ==========================================================

from camera_card.mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)

from camera_card.baseline.personal_baseline import (
    PersonalBaselineCollector,
    PersonalBaselineConfig,
    BASELINE_COLLECTING,
    BASELINE_SUCCESS,
    BASELINE_NEED_CONFIRMATION,
)


# ==========================================================
# CAMERA / TEST CONFIG
# ==========================================================

CAMERA_ID = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

WINDOW_NAME = (
    "PostGuard Baseline Compensation Final Test"
)

BASELINE_SAMPLES = 60
CURRENT_SAMPLES = 30

# Current stage must have at least this valid ratio.
MIN_STAGE_VALID_RATIO = 0.70


# ==========================================================
# RETURN TOLERANCE
#
# Derived from this setup's 10-repeat Personal Baseline test:
#
# Shoulder SD      = 0.448 deg
# Neck Lateral SD  = 1.168 deg
# Neck Flexion SD  = 1.417 deg
# Eye Distance SD  = 5.048 px
#
# Prototype return range = approximately +/- 2 SD
#
# IMPORTANT:
# These are internal prototype criteria for this tested setup,
# not medical or universal thresholds.
# ==========================================================

RETURN_TOLERANCE = {
    "shoulder_tilt": 0.896,
    "neck_lateral_tilt": 2.336,
    "neck_flexion": 2.834,
    "eye_distance": 10.096,
}


# ==========================================================
# MOVEMENT MINIMUM CHANGE
#
# Used only to verify that the target feature changes
# enough to be distinguishable from normal baseline noise.
# ==========================================================

MIN_CHANGE = {
    "shoulder_tilt": 3.0,
    "neck_lateral_tilt": 5.0,
    "neck_flexion": 5.0,
    "eye_distance": 8.0,
}


# ==========================================================
# FEATURE CONTRACT
# ==========================================================

REQUIRED_FEATURES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
    "eye_distance",
)

EXPECTED_FEATURE_STATUS = (
    "validated_prototype"
)


# ==========================================================
# UI COLORS
# ==========================================================

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
RED = (0, 0, 255)
CYAN = (255, 255, 0)


# ==========================================================
# TEST STAGE
# ==========================================================

@dataclass(frozen=True)
class TestStage:
    name: str
    instruction: str
    target_feature: str | None = None
    expected_direction: int = 0
    neutral_check: bool = False
    return_attempt: int | None = None


STAGES = (
    TestStage(
        name="SAME_START",
        instruction=(
            "Sit in the same natural posture as your baseline."
        ),
        neutral_check=True,
    ),

    TestStage(
        name="SHOULDER_LEFT_HIGH",
        instruction=(
            "Raise the LEFT shoulder higher and hold."
        ),
        target_feature="shoulder_tilt",
        expected_direction=-1,
    ),

    TestStage(
        name="SHOULDER_RIGHT_HIGH",
        instruction=(
            "Raise the RIGHT shoulder higher and hold."
        ),
        target_feature="shoulder_tilt",
        expected_direction=1,
    ),

    TestStage(
        name="NECK_TILT_LEFT",
        instruction=(
            "Tilt your head to the LEFT and hold."
        ),
        target_feature="neck_lateral_tilt",
        expected_direction=1,
    ),

    TestStage(
        name="NECK_TILT_RIGHT",
        instruction=(
            "Tilt your head to the RIGHT and hold."
        ),
        target_feature="neck_lateral_tilt",
        expected_direction=-1,
    ),

    TestStage(
        name="NECK_FLEXION",
        instruction=(
            "Bend your head forward / look downward and hold."
        ),
        target_feature="neck_flexion",
        expected_direction=1,
    ),

    TestStage(
        name="NECK_EXTENSION",
        instruction=(
            "Extend your head backward / look upward and hold."
        ),
        target_feature="neck_flexion",
        expected_direction=-1,
    ),

    TestStage(
        name="MOVE_NEAR",
        instruction=(
            "Move closer to the camera and hold."
        ),
        target_feature="eye_distance",
        expected_direction=1,
    ),

    TestStage(
        name="MOVE_FAR",
        instruction=(
            "Move farther from the camera and hold."
        ),
        target_feature="eye_distance",
        expected_direction=-1,
    ),

    TestStage(
        name="RETURN_FINAL_1",
        instruction=(
            "Return to your natural baseline posture. Attempt 1 of 3."
        ),
        neutral_check=True,
        return_attempt=1,
    ),

    TestStage(
        name="RETURN_FINAL_2",
        instruction=(
            "Relax, then return to your natural baseline posture. Attempt 2 of 3."
        ),
        neutral_check=True,
        return_attempt=2,
    ),

    TestStage(
        name="RETURN_FINAL_3",
        instruction=(
            "Relax, then return to your natural baseline posture. Attempt 3 of 3."
        ),
        neutral_check=True,
        return_attempt=3,
    ),
)


# ==========================================================
# NUMERIC HELPERS
# ==========================================================

def is_finite_number(value):
    if value is None:
        return False

    try:
        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError,
    ):
        return False


# ==========================================================
# UI HELPERS
# ==========================================================

def put(
    frame,
    text,
    x,
    y,
    color=WHITE,
    scale=0.52,
    thickness=1,
):
    cv2.putText(
        frame,
        str(text),
        (
            int(x),
            int(y),
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_panel(
    frame,
    width=980,
    height=540,
):
    overlay = frame.copy()

    cv2.rectangle(
        overlay,
        (0, 0),
        (width, height),
        BLACK,
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.70,
        frame,
        0.30,
        0,
        frame,
    )


# ==========================================================
# FEATURE EXTRACTION
# ==========================================================

def extract_valid_feature(
    detection_result,
    feature_name,
):
    if not isinstance(
        detection_result,
        dict,
    ):
        return (
            False,
            None,
            "INVALID_DETECTION_RESULT",
        )

    features = (
        detection_result.get(
            "features"
        )
        or {}
    )

    feature = (
        features.get(
            feature_name
        )
    )

    if not isinstance(
        feature,
        dict,
    ):
        return (
            False,
            None,
            f"{feature_name}_MISSING",
        )

    if feature.get(
        "valid"
    ) is not True:

        return (
            False,
            None,
            (
                f"{feature_name}_"
                f"{feature.get('reason', 'INVALID')}"
            ),
        )

    if (
        feature.get(
            "status"
        )
        !=
        EXPECTED_FEATURE_STATUS
    ):
        return (
            False,
            None,
            f"{feature_name}_NOT_VALIDATED",
        )

    value = (
        feature.get(
            "value"
        )
    )

    if not is_finite_number(
        value
    ):
        return (
            False,
            None,
            f"{feature_name}_INVALID_VALUE",
        )

    return (
        True,
        float(value),
        "OK",
    )


# ==========================================================
# CURRENT POSTURE COLLECTOR
# ==========================================================

class CurrentPostureCollector:
    """
    Collects a short stable current-posture window.

    This does NOT create another Personal Baseline.
    It summarizes Current posture so we can calculate:

        Delta = Current - Baseline
    """

    def __init__(
        self,
        target_samples=CURRENT_SAMPLES,
    ):
        self.target_samples = int(
            target_samples
        )

        self.reset()


    def reset(
        self,
    ):
        self.total_frames = 0

        self.accepted_samples = 0

        self.rejected_frames = 0

        self.rejection_reasons = {}

        self.samples = {
            feature_name: []
            for feature_name
            in REQUIRED_FEATURES
        }


    def _reject(
        self,
        reason,
    ):
        self.rejected_frames += 1

        self.rejection_reasons[
            reason
        ] = (
            self.rejection_reasons.get(
                reason,
                0,
            )
            +
            1
        )


    def add(
        self,
        detection_result,
    ):
        self.total_frames += 1

        if not isinstance(
            detection_result,
            dict,
        ):
            self._reject(
                "INVALID_DETECTION_RESULT"
            )
            return

        context = (
            detection_result.get(
                "context"
            )
            or {}
        )

        if (
            context.get(
                "allow_posture_evaluation"
            )
            is not True
        ):
            self._reject(
                (
                    "context_"
                    +
                    str(
                        context.get(
                            "reason",
                            "NOT_ALLOWED",
                        )
                    )
                )
            )
            return

        row = {}

        for feature_name in (
            REQUIRED_FEATURES
        ):
            (
                valid,
                value,
                reason,
            ) = extract_valid_feature(
                detection_result,
                feature_name,
            )

            if not valid:
                self._reject(
                    reason
                )
                return

            row[
                feature_name
            ] = value

        for feature_name in (
            REQUIRED_FEATURES
        ):
            self.samples[
                feature_name
            ].append(
                row[
                    feature_name
                ]
            )

        self.accepted_samples += 1


    @property
    def completed(
        self,
    ):
        return (
            self.accepted_samples
            >=
            self.target_samples
        )


    def build_result(
        self,
    ):
        current = {}

        stability = {}

        for feature_name in (
            REQUIRED_FEATURES
        ):
            values = (
                self.samples[
                    feature_name
                ]
            )

            current[
                feature_name
            ] = float(
                statistics.median(
                    values
                )
            )

            stability[
                f"{feature_name}_sd"
            ] = (
                float(
                    statistics.stdev(
                        values
                    )
                )
                if len(values) >= 2
                else 0.0
            )

        valid_ratio = (
            self.accepted_samples
            /
            self.total_frames
            if self.total_frames > 0
            else 0.0
        )

        return {
            "current": current,

            "stability": stability,

            "sample_count": (
                self.accepted_samples
            ),

            "total_frames": (
                self.total_frames
            ),

            "rejected_frames": (
                self.rejected_frames
            ),

            "valid_ratio": float(
                valid_ratio
            ),

            "quality_passed": (
                valid_ratio
                >=
                MIN_STAGE_VALID_RATIO
            ),

            "rejection_reasons": dict(
                self.rejection_reasons
            ),
        }


# ==========================================================
# DELTA
# ==========================================================

def calculate_delta(
    current,
    baseline,
):
    return {
        feature_name: (
            float(
                current[
                    feature_name
                ]
            )
            -
            float(
                baseline[
                    feature_name
                ]
            )
        )
        for feature_name
        in REQUIRED_FEATURES
    }


# ==========================================================
# EVALUATION
# ==========================================================

def evaluate_neutral(
    delta,
):
    checks = {
        feature_name: (
            abs(
                delta[
                    feature_name
                ]
            )
            <=
            RETURN_TOLERANCE[
                feature_name
            ]
        )
        for feature_name
        in REQUIRED_FEATURES
    }

    return {
        "passed": all(
            checks.values()
        ),

        "checks": checks,
    }


def evaluate_movement(
    stage,
    delta,
):
    feature_name = (
        stage.target_feature
    )

    value = (
        delta[
            feature_name
        ]
    )

    if stage.expected_direction > 0:
        direction_passed = (
            value > 0
        )

    else:
        direction_passed = (
            value < 0
        )

    magnitude_passed = (
        abs(
            value
        )
        >=
        MIN_CHANGE[
            feature_name
        ]
    )

    return {
        "passed": (
            direction_passed
            and
            magnitude_passed
        ),

        "feature": (
            feature_name
        ),

        "delta": (
            value
        ),

        "direction_passed": (
            direction_passed
        ),

        "magnitude_passed": (
            magnitude_passed
        ),

        "minimum_change": (
            MIN_CHANGE[
                feature_name
            ]
        ),
    }


def evaluate_stage(
    stage,
    current_result,
    delta,
):
    # ------------------------------------------------------
    # QUALITY GATE FIRST
    # ------------------------------------------------------

    if not current_result[
        "quality_passed"
    ]:
        return {
            "passed": False,

            "result_type": (
                "QUALITY_FAIL"
            ),

            "reason": (
                "LOW_VALID_RATIO"
            ),

            "valid_ratio": (
                current_result[
                    "valid_ratio"
                ]
            ),

            "minimum_valid_ratio": (
                MIN_STAGE_VALID_RATIO
            ),
        }


    # ------------------------------------------------------
    # POSTURE EVALUATION
    # ------------------------------------------------------

    if stage.neutral_check:
        evaluation = (
            evaluate_neutral(
                delta
            )
        )

    else:
        evaluation = (
            evaluate_movement(
                stage,
                delta,
            )
        )

    evaluation[
        "result_type"
    ] = (
        "POSTURE_RESULT"
    )

    return evaluation


# ==========================================================
# CSV SAVE
# ==========================================================

def save_csv(
    baseline,
    results,
):
    output_dir = (
        THIS_FILE.parent
        /
        "results"
        /
        "baseline_compensation"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    path = (
        output_dir
        /
        f"baseline_compensation_final_{stamp}.csv"
    )

    fields = [
        "stage",
        "return_attempt",

        "passed",
        "result_type",

        "sample_count",
        "total_frames",
        "valid_ratio",
        "quality_passed",

        "baseline_shoulder_tilt",
        "current_shoulder_tilt",
        "delta_shoulder_tilt",

        "baseline_neck_lateral_tilt",
        "current_neck_lateral_tilt",
        "delta_neck_lateral_tilt",

        "baseline_neck_flexion",
        "current_neck_flexion",
        "delta_neck_flexion",

        "baseline_eye_distance",
        "current_eye_distance",
        "delta_eye_distance",
    ]

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()

        for item in results:

            current = (
                item[
                    "current"
                ]
            )

            delta = (
                item[
                    "delta"
                ]
            )

            writer.writerow({
                "stage": (
                    item[
                        "stage"
                    ]
                ),

                "return_attempt": (
                    item.get(
                        "return_attempt"
                    )
                ),

                "passed": (
                    item[
                        "evaluation"
                    ][
                        "passed"
                    ]
                ),

                "result_type": (
                    item[
                        "evaluation"
                    ].get(
                        "result_type"
                    )
                ),

                "sample_count": (
                    item[
                        "sample_count"
                    ]
                ),

                "total_frames": (
                    item[
                        "total_frames"
                    ]
                ),

                "valid_ratio": (
                    item[
                        "valid_ratio"
                    ]
                ),

                "quality_passed": (
                    item[
                        "quality_passed"
                    ]
                ),

                "baseline_shoulder_tilt": (
                    baseline[
                        "shoulder_tilt"
                    ]
                ),

                "current_shoulder_tilt": (
                    current[
                        "shoulder_tilt"
                    ]
                ),

                "delta_shoulder_tilt": (
                    delta[
                        "shoulder_tilt"
                    ]
                ),

                "baseline_neck_lateral_tilt": (
                    baseline[
                        "neck_lateral_tilt"
                    ]
                ),

                "current_neck_lateral_tilt": (
                    current[
                        "neck_lateral_tilt"
                    ]
                ),

                "delta_neck_lateral_tilt": (
                    delta[
                        "neck_lateral_tilt"
                    ]
                ),

                "baseline_neck_flexion": (
                    baseline[
                        "neck_flexion"
                    ]
                ),

                "current_neck_flexion": (
                    current[
                        "neck_flexion"
                    ]
                ),

                "delta_neck_flexion": (
                    delta[
                        "neck_flexion"
                    ]
                ),

                "baseline_eye_distance": (
                    baseline[
                        "eye_distance"
                    ]
                ),

                "current_eye_distance": (
                    current[
                        "eye_distance"
                    ]
                ),

                "delta_eye_distance": (
                    delta[
                        "eye_distance"
                    ]
                ),
            })

    return path


# ==========================================================
# TERMINAL OUTPUT
# ==========================================================

def print_baseline(
    result,
):
    baseline = (
        result[
            "baseline"
        ]
    )

    print()
    print("=" * 78)
    print("PERSONAL BASELINE READY")
    print("=" * 78)

    print(
        f"Shoulder Tilt : "
        f"{baseline['shoulder_tilt']:+.3f} deg"
    )

    print(
        f"Neck Lateral  : "
        f"{baseline['neck_lateral_tilt']:+.3f} deg"
    )

    print(
        f"Neck Flexion  : "
        f"{baseline['neck_flexion']:+.3f} deg"
    )

    print(
        f"Eye Distance  : "
        f"{baseline['eye_distance']:.3f} px"
    )

    print("=" * 78)


def print_stage_result(
    item,
):
    print()
    print("-" * 78)

    print(
        f"STAGE : "
        f"{item['stage']}"
    )

    print(
        f"RESULT: "
        f"{'PASS' if item['evaluation']['passed'] else 'FAIL'}"
    )

    print(
        f"TYPE  : "
        f"{item['evaluation'].get('result_type')}"
    )

    print(
        f"Valid Ratio: "
        f"{item['valid_ratio']:.2%}"
    )

    print(
        f"Shoulder Delta : "
        f"{item['delta']['shoulder_tilt']:+.3f} deg"
    )

    print(
        f"Neck Lat Delta : "
        f"{item['delta']['neck_lateral_tilt']:+.3f} deg"
    )

    print(
        f"Neck Flex Delta: "
        f"{item['delta']['neck_flexion']:+.3f} deg"
    )

    print(
        f"Eye Dist Delta : "
        f"{item['delta']['eye_distance']:+.3f} px"
    )

    print("-" * 78)


# ==========================================================
# UI DRAWING
# ==========================================================

def draw_baseline(
    frame,
    status,
    detection_result,
):
    display = cv2.flip(
        frame,
        1,
    )

    draw_panel(
        display,
        height=350,
    )

    context = (
        detection_result.get(
            "context"
        )
        or {}
    )

    put(
        display,
        "STEP 1 - CREATE PERSONAL BASELINE",
        20,
        35,
        YELLOW,
        0.70,
        2,
    )

    put(
        display,
        "Sit naturally and look forward.",
        20,
        75,
    )

    put(
        display,
        (
            f"Collecting: "
            f"{status.get('sample_count', 0)}/"
            f"{status.get('target_samples', BASELINE_SAMPLES)}"
        ),
        20,
        120,
        GREEN,
        0.62,
        2,
    )

    put(
        display,
        (
            f"Valid Ratio: "
            f"{status.get('valid_ratio', 0.0):.1%}"
        ),
        20,
        155,
    )

    put(
        display,
        (
            f"Context: "
            f"{context.get('state', 'UNKNOWN')} "
            f"({context.get('reason', 'N/A')})"
        ),
        20,
        195,
        CYAN,
    )

    put(
        display,
        "ESC = Exit",
        20,
        315,
        CYAN,
    )

    return display


def draw_wait(
    frame,
    baseline,
    stage,
    stage_index,
):
    display = cv2.flip(
        frame,
        1,
    )

    draw_panel(
        display,
        height=480,
    )

    put(
        display,
        "STEP 2 - BASELINE COMPENSATION TEST",
        20,
        35,
        YELLOW,
        0.68,
        2,
    )

    put(
        display,
        (
            f"Test {stage_index + 1}/"
            f"{len(STAGES)}: "
            f"{stage.name}"
        ),
        20,
        80,
        CYAN,
        0.60,
        2,
    )

    put(
        display,
        stage.instruction,
        20,
        125,
        WHITE,
        0.52,
        1,
    )

    put(
        display,
        (
            "Hold the requested posture, "
            "then press SPACE."
        ),
        20,
        170,
    )

    put(
        display,
        (
            f"Baseline Shoulder: "
            f"{baseline['shoulder_tilt']:+.2f} deg"
        ),
        20,
        230,
    )

    put(
        display,
        (
            f"Baseline Neck Lat: "
            f"{baseline['neck_lateral_tilt']:+.2f} deg"
        ),
        20,
        265,
    )

    put(
        display,
        (
            f"Baseline Neck Flex: "
            f"{baseline['neck_flexion']:+.2f} deg"
        ),
        20,
        300,
    )

    put(
        display,
        (
            f"Baseline Eye Dist: "
            f"{baseline['eye_distance']:.2f} px"
        ),
        20,
        335,
    )

    put(
        display,
        (
            "SPACE = Start    "
            "ESC = Exit"
        ),
        20,
        430,
        CYAN,
        0.55,
        2,
    )

    return display


def draw_collect(
    frame,
    stage,
    collector,
    detection_result,
):
    display = cv2.flip(
        frame,
        1,
    )

    draw_panel(
        display,
        height=430,
    )

    context = (
        detection_result.get(
            "context"
        )
        or {}
    )

    put(
        display,
        (
            f"COLLECTING: "
            f"{stage.name}"
        ),
        20,
        35,
        YELLOW,
        0.70,
        2,
    )

    put(
        display,
        stage.instruction,
        20,
        75,
    )

    put(
        display,
        (
            f"Valid Samples: "
            f"{collector.accepted_samples}/"
            f"{collector.target_samples}"
        ),
        20,
        125,
        GREEN,
        0.62,
        2,
    )

    put(
        display,
        (
            f"Context: "
            f"{context.get('state', 'UNKNOWN')} "
            f"({context.get('reason', 'N/A')})"
        ),
        20,
        165,
        CYAN,
    )

    put(
        display,
        (
            "Keep holding the posture until "
            "collection completes."
        ),
        20,
        215,
    )

    put(
        display,
        "ESC = Exit",
        20,
        385,
        CYAN,
    )

    return display


def draw_result(
    frame,
    item,
    stage_index,
):
    display = cv2.flip(
        frame,
        1,
    )

    draw_panel(
        display,
        height=520,
    )

    passed = (
        item[
            "evaluation"
        ][
            "passed"
        ]
    )

    result_type = (
        item[
            "evaluation"
        ].get(
            "result_type"
        )
    )

    status_color = (
        GREEN
        if passed
        else RED
    )

    put(
        display,
        (
            f"RESULT {stage_index + 1}/"
            f"{len(STAGES)} - "
            f"{item['stage']}"
        ),
        20,
        35,
        WHITE,
        0.65,
        2,
    )

    put(
        display,
        (
            "PASS"
            if passed
            else
            "FAIL"
        ),
        20,
        80,
        status_color,
        0.85,
        2,
    )

    put(
        display,
        (
            f"Type: "
            f"{result_type}"
        ),
        20,
        115,
        CYAN,
    )

    delta = (
        item[
            "delta"
        ]
    )

    put(
        display,
        (
            f"Shoulder Delta : "
            f"{delta['shoulder_tilt']:+.2f} deg"
        ),
        20,
        165,
    )

    put(
        display,
        (
            f"Neck Lat Delta : "
            f"{delta['neck_lateral_tilt']:+.2f} deg"
        ),
        20,
        205,
    )

    put(
        display,
        (
            f"Neck Flex Delta: "
            f"{delta['neck_flexion']:+.2f} deg"
        ),
        20,
        245,
    )

    put(
        display,
        (
            f"Eye Dist Delta : "
            f"{delta['eye_distance']:+.2f} px"
        ),
        20,
        285,
    )

    put(
        display,
        (
            f"Valid Ratio: "
            f"{item['valid_ratio']:.1%} "
            f"(minimum {MIN_STAGE_VALID_RATIO:.0%})"
        ),
        20,
        340,
        CYAN,
    )

    put(
        display,
        (
            "ENTER = Next    "
            "ESC = Exit"
        ),
        20,
        465,
        CYAN,
        0.52,
        2,
    )

    return display


def draw_finished(
    frame,
    results,
    csv_path,
):
    display = cv2.flip(
        frame,
        1,
    )

    draw_panel(
        display,
        height=500,
    )

    non_return_results = [
        item
        for item
        in results
        if not item[
            "stage"
        ].startswith(
            "RETURN_FINAL"
        )
    ]

    return_results = [
        item
        for item
        in results
        if item[
            "stage"
        ].startswith(
            "RETURN_FINAL"
        )
    ]

    normal_pass_count = sum(
        1
        for item
        in non_return_results
        if item[
            "evaluation"
        ][
            "passed"
        ]
    )

    return_pass_count = sum(
        1
        for item
        in return_results
        if item[
            "evaluation"
        ][
            "passed"
        ]
    )

    put(
        display,
        "BASELINE COMPENSATION TEST COMPLETE",
        20,
        40,
        YELLOW,
        0.68,
        2,
    )

    put(
        display,
        (
            f"Main stages passed: "
            f"{normal_pass_count}/"
            f"{len(non_return_results)}"
        ),
        20,
        100,
        GREEN,
        0.58,
        2,
    )

    put(
        display,
        (
            f"Return attempts passed: "
            f"{return_pass_count}/"
            f"{len(return_results)}"
        ),
        20,
        145,
        (
            GREEN
            if return_pass_count > 0
            else RED
        ),
        0.58,
        2,
    )

    put(
        display,
        (
            "Return is evaluated as a natural "
            "range, not exact zero."
        ),
        20,
        205,
        WHITE,
        0.50,
    )

    put(
        display,
        "Results saved to:",
        20,
        280,
        CYAN,
    )

    put(
        display,
        csv_path.name,
        20,
        315,
        WHITE,
        0.46,
    )

    put(
        display,
        "ESC = Exit",
        20,
        450,
        CYAN,
    )

    return display


# ==========================================================
# MAIN
# ==========================================================

def main():

    cap = cv2.VideoCapture(
        CAMERA_ID,
        cv2.CAP_DSHOW,
    )

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        FRAME_WIDTH,
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        FRAME_HEIGHT,
    )

    if not cap.isOpened():
        raise RuntimeError(
            "Cannot open camera."
        )

    pipeline = (
        DetectionPipeline()
    )

    pipeline.reset_runtime()

    baseline_collector = (
        PersonalBaselineCollector(
            PersonalBaselineConfig(
                target_samples=(
                    BASELINE_SAMPLES
                )
            )
        )
    )

    current_collector = (
        CurrentPostureCollector()
    )

    mode = "BASELINE"

    baseline_result = None

    baseline = None

    stage_index = 0

    results = []

    latest = None

    csv_path = None

    cv2.namedWindow(
        WINDOW_NAME,
        cv2.WINDOW_NORMAL,
    )

    try:

        while True:

            ok, raw_frame = (
                cap.read()
            )

            if not ok:
                continue

            # DetectionPipeline MUST receive UNMIRRORED frame.
            detection_result = (
                pipeline.process_frame(
                    raw_frame
                )
            )


            # ==================================================
            # BASELINE
            # ==================================================

            if mode == "BASELINE":

                status = (
                    baseline_collector
                    .get_status()
                )

                if (
                    status.get(
                        "status"
                    )
                    ==
                    BASELINE_COLLECTING
                ):

                    status = (
                        baseline_collector
                        .add_detection_result(
                            detection_result
                        )
                    )

                display = (
                    draw_baseline(
                        raw_frame,
                        status,
                        detection_result,
                    )
                )

                result = (
                    baseline_collector
                    .get_result()
                )

                if result is not None:

                    if (
                        result.get(
                            "status"
                        )
                        ==
                        BASELINE_NEED_CONFIRMATION
                    ):

                        display = cv2.flip(
                            raw_frame,
                            1,
                        )

                        draw_panel(
                            display,
                            height=320,
                        )

                        put(
                            display,
                            "BASELINE NEEDS CONFIRMATION",
                            20,
                            40,
                            YELLOW,
                            0.70,
                            2,
                        )

                        put(
                            display,
                            (
                                f"Shoulder baseline: "
                                f"{result['baseline']['shoulder_tilt']:+.2f} deg"
                            ),
                            20,
                            95,
                        )

                        put(
                            display,
                            (
                                "Is this your normal sitting posture?"
                            ),
                            20,
                            145,
                        )

                        put(
                            display,
                            (
                                "Y = Confirm    "
                                "N = Recalibrate"
                            ),
                            20,
                            220,
                            CYAN,
                            0.56,
                            2,
                        )


                    elif (
                        result.get(
                            "status"
                        )
                        ==
                        BASELINE_SUCCESS
                    ):

                        baseline_result = (
                            result
                        )

                        baseline = (
                            result[
                                "baseline"
                            ]
                        )

                        print_baseline(
                            baseline_result
                        )

                        pipeline.reset_context()

                        mode = (
                            "WAIT_STAGE"
                        )


            # ==================================================
            # WAIT STAGE
            # ==================================================

            elif mode == "WAIT_STAGE":

                stage = (
                    STAGES[
                        stage_index
                    ]
                )

                display = (
                    draw_wait(
                        raw_frame,
                        baseline,
                        stage,
                        stage_index,
                    )
                )


            # ==================================================
            # COLLECT STAGE
            # ==================================================

            elif mode == "COLLECT_STAGE":

                stage = (
                    STAGES[
                        stage_index
                    ]
                )

                current_collector.add(
                    detection_result
                )

                display = (
                    draw_collect(
                        raw_frame,
                        stage,
                        current_collector,
                        detection_result,
                    )
                )

                if (
                    current_collector.completed
                ):

                    current_result = (
                        current_collector
                        .build_result()
                    )

                    current = (
                        current_result[
                            "current"
                        ]
                    )

                    delta = (
                        calculate_delta(
                            current,
                            baseline,
                        )
                    )

                    evaluation = (
                        evaluate_stage(
                            stage,
                            current_result,
                            delta,
                        )
                    )

                    latest = {
                        "stage": (
                            stage.name
                        ),

                        "return_attempt": (
                            stage.return_attempt
                        ),

                        "current": (
                            current
                        ),

                        "delta": (
                            delta
                        ),

                        "stability": (
                            current_result[
                                "stability"
                            ]
                        ),

                        "sample_count": (
                            current_result[
                                "sample_count"
                            ]
                        ),

                        "total_frames": (
                            current_result[
                                "total_frames"
                            ]
                        ),

                        "rejected_frames": (
                            current_result[
                                "rejected_frames"
                            ]
                        ),

                        "valid_ratio": (
                            current_result[
                                "valid_ratio"
                            ]
                        ),

                        "quality_passed": (
                            current_result[
                                "quality_passed"
                            ]
                        ),

                        "rejection_reasons": (
                            current_result[
                                "rejection_reasons"
                            ]
                        ),

                        "evaluation": (
                            evaluation
                        ),
                    }

                    # IMPORTANT:
                    # Every attempt is kept.
                    # Nothing is popped/deleted.
                    results.append(
                        latest
                    )

                    print_stage_result(
                        latest
                    )

                    mode = (
                        "STAGE_RESULT"
                    )


            # ==================================================
            # RESULT
            # ==================================================

            elif mode == "STAGE_RESULT":

                display = (
                    draw_result(
                        raw_frame,
                        latest,
                        stage_index,
                    )
                )


            # ==================================================
            # FINISHED
            # ==================================================

            elif mode == "FINISHED":

                display = (
                    draw_finished(
                        raw_frame,
                        results,
                        csv_path,
                    )
                )


            else:

                display = cv2.flip(
                    raw_frame,
                    1,
                )


            cv2.imshow(
                WINDOW_NAME,
                display,
            )

            key = (
                cv2.waitKey(1)
                &
                0xFF
            )


            # ==================================================
            # EXIT
            # ==================================================

            if key == 27:
                break


            # ==================================================
            # BASELINE CONFIRMATION
            # ==================================================

            if mode == "BASELINE":

                result = (
                    baseline_collector
                    .get_result()
                )

                if (
                    result is not None
                    and
                    result.get(
                        "status"
                    )
                    ==
                    BASELINE_NEED_CONFIRMATION
                ):

                    if key in (
                        ord("y"),
                        ord("Y"),
                    ):

                        baseline_result = (
                            baseline_collector
                            .confirm()
                        )

                        baseline = (
                            baseline_result[
                                "baseline"
                            ]
                        )

                        print_baseline(
                            baseline_result
                        )

                        pipeline.reset_context()

                        mode = (
                            "WAIT_STAGE"
                        )


                    elif key in (
                        ord("n"),
                        ord("N"),
                    ):

                        baseline_collector.reset()

                        pipeline.reset_runtime()


            # ==================================================
            # START STAGE
            # ==================================================

            elif mode == "WAIT_STAGE":

                if key == 32:  # SPACE

                    current_collector.reset()

                    pipeline.reset_context()

                    mode = (
                        "COLLECT_STAGE"
                    )


            # ==================================================
            # NEXT STAGE
            # ==================================================

            elif mode == "STAGE_RESULT":

                if key in (
                    10,
                    13,
                ):

                    stage_index += 1

                    if (
                        stage_index
                        >=
                        len(
                            STAGES
                        )
                    ):

                        csv_path = (
                            save_csv(
                                baseline,
                                results,
                            )
                        )

                        print()
                        print("=" * 78)
                        print("BASELINE COMPENSATION FINAL SUMMARY")
                        print("=" * 78)

                        for item in results:

                            print(
                                f"{item['stage']:<24} "
                                f"{'PASS' if item['evaluation']['passed'] else 'FAIL'} "
                                f"Valid={item['valid_ratio']:.2%}"
                            )

                        print("-" * 78)

                        return_results = [
                            item
                            for item
                            in results
                            if item[
                                "stage"
                            ].startswith(
                                "RETURN_FINAL"
                            )
                        ]

                        return_pass_count = sum(
                            1
                            for item
                            in return_results
                            if item[
                                "evaluation"
                            ][
                                "passed"
                            ]
                        )

                        print(
                            f"Return attempts passed: "
                            f"{return_pass_count}/"
                            f"{len(return_results)}"
                        )

                        print(
                            f"CSV: {csv_path}"
                        )

                        print("=" * 78)

                        mode = (
                            "FINISHED"
                        )

                    else:

                        pipeline.reset_context()

                        mode = (
                            "WAIT_STAGE"
                        )


    finally:

        pipeline.close()

        cap.release()

        cv2.destroyAllWindows()


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":
    main()
