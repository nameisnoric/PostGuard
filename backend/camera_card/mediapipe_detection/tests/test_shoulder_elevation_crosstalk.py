from pathlib import Path
import csv
import math
import statistics
import sys
import time
from datetime import datetime

import cv2


# ==========================================================
# UTF-8 Console
# ==========================================================

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ==========================================================
# Python Path
#
# camera_card/
#   mediapipe_detection/
#       tests/
#           test_shoulder_elevation_crosstalk.py
#
# parents[2] = camera_card
# ==========================================================

BASE_DIR = Path(__file__).resolve().parents[2]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ==========================================================
# PostGuard
# ==========================================================

from mediapipe_detection.detection_pipeline import DetectionPipeline


# ==========================================================
# Test Settings
# ==========================================================

SAMPLE_DURATION_SECONDS = 2.0
MIN_VALID_SAMPLES = 15
TOTAL_ROUNDS = 3

# Initial settling before scored rounds.
INITIAL_WARMUP_VALID_SECONDS = 5.0

# After each posture transition, require a stable hold before SPACE.
STATE_SETTLE_SECONDS = 1.0

# If context drops during recording, that attempt is discarded and retried.
MAX_RECORDING_ATTEMPTS_PER_STATE = 5


# ==========================================================
# Prototype Acceptance Criteria
#
# Engineering prototype criteria only.
# NOT clinical thresholds.
# ==========================================================

MAX_CROSSTALK_RATIO = 0.50
MIN_SIGNAL_TO_NORMAL_VARIABILITY = 3.0
EPSILON = 1e-9


# ==========================================================
# State Instructions
# ==========================================================

STATE_INSTRUCTIONS = {
    "NORMAL_1": (
        "Sit naturally, look forward, relax both shoulders."
    ),
    "RAISE_BOTH": (
        "Raise BOTH shoulders upward. Keep head facing forward."
    ),
    "NORMAL_2": (
        "Return to normal. Relax shoulders and look forward."
    ),
    "NECK_FLEXION_ONLY": (
        "Bend the neck forward / look downward. "
        "DO NOT raise the shoulders."
    ),
    "NORMAL_3": (
        "Return to normal. Relax shoulders and look forward."
    ),
}


TEST_SEQUENCE = []

for round_number in range(1, TOTAL_ROUNDS + 1):
    for state in (
        "NORMAL_1",
        "RAISE_BOTH",
        "NORMAL_2",
        "NECK_FLEXION_ONLY",
        "NORMAL_3",
    ):
        TEST_SEQUENCE.append(
            {
                "round": round_number,
                "state": state,
            }
        )


# ==========================================================
# Numeric Helper
# ==========================================================

def is_finite_number(value):
    if value is None:
        return False

    try:
        return math.isfinite(float(value))

    except (
        TypeError,
        ValueError,
    ):
        return False


# ==========================================================
# Statistics
# ==========================================================

def summarize_values(values):
    clean_values = [
        float(value)
        for value in values
        if is_finite_number(value)
    ]

    if not clean_values:
        return None

    if len(clean_values) >= 2:
        std_value = statistics.pstdev(clean_values)
    else:
        std_value = 0.0

    return {
        "median": float(statistics.median(clean_values)),
        "mean": float(statistics.mean(clean_values)),
        "std": float(std_value),
        "min": float(min(clean_values)),
        "max": float(max(clean_values)),
    }


def summarize_samples(samples):
    left_values = [
        sample["left"]
        for sample in samples
        if is_finite_number(sample.get("left"))
    ]

    right_values = [
        sample["right"]
        for sample in samples
        if is_finite_number(sample.get("right"))
    ]

    return {
        "valid_samples": len(samples),
        "left": summarize_values(left_values),
        "right": summarize_values(right_values),
    }


# ==========================================================
# Feature Extraction
# ==========================================================

def unwrap_feature_value(value):
    if isinstance(value, dict):
        if value.get("valid") is False:
            return None

        for key in (
            "value",
            "elevation",
            "angle",
            "score",
        ):
            candidate = value.get(key)

            if is_finite_number(candidate):
                return float(candidate)

        return None

    if is_finite_number(value):
        return float(value)

    return None


def extract_shoulder_elevation(result):
    """
    รองรับ DetectionPipeline contract ปัจจุบัน:

        result["features"]["shoulder_elevation"]

    และ fallback format เก่าเพื่อให้ test ทนต่อ contract change เล็กน้อย
    """

    if not isinstance(result, dict):
        return None, None

    containers = [result]

    for nested_key in (
        "features",
        "posture",
        "pose",
    ):
        nested = result.get(nested_key)

        if isinstance(nested, dict):
            containers.append(nested)

    for container in containers:
        shoulder_block = container.get(
            "shoulder_elevation"
        )

        if isinstance(shoulder_block, dict):
            left = unwrap_feature_value(
                shoulder_block.get("left")
            )

            right = unwrap_feature_value(
                shoulder_block.get("right")
            )

            if left is not None and right is not None:
                return left, right

    for container in containers:
        for left_key, right_key in (
            (
                "left_shoulder_elevation",
                "right_shoulder_elevation",
            ),
            (
                "shoulder_elevation_left",
                "shoulder_elevation_right",
            ),
            (
                "left_elevation",
                "right_elevation",
            ),
        ):
            left = unwrap_feature_value(
                container.get(left_key)
            )

            right = unwrap_feature_value(
                container.get(right_key)
            )

            if left is not None and right is not None:
                return left, right

    return None, None


def extract_context(result):
    if not isinstance(result, dict):
        return {
            "state": "UNKNOWN",
            "reason": "invalid_pipeline_result",
            "allow_posture_evaluation": False,
            "stable_seconds": 0.0,
        }

    context = result.get("context")

    if not isinstance(context, dict):
        return {
            "state": "UNKNOWN",
            "reason": "context_not_available",
            "allow_posture_evaluation": False,
            "stable_seconds": 0.0,
        }

    return context


def context_is_valid(context):
    return (
        isinstance(context, dict)
        and context.get("state") == "VALID"
        and context.get(
            "allow_posture_evaluation"
        ) is True
    )


# ==========================================================
# Display Helpers
# ==========================================================

WINDOW_NAME = (
    "PostGuard - Shoulder Elevation Final Validation"
)


def draw_line(
    frame,
    text,
    y,
    scale=0.65,
    thickness=2,
):
    cv2.putText(
        frame,
        str(text),
        (20, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def make_preview(frame):
    # Detection gets raw/unmirrored frame.
    # Mirror only the preview.
    return cv2.flip(frame, 1)


# ==========================================================
# Initial Warm-up
# ==========================================================

def run_initial_warmup(
    pipeline,
    capture,
):
    """
    ก่อนเริ่ม Round 1:

    1. ผู้ใช้นั่ง NORMAL
    2. Context ต้อง VALID
    3. VALID ต่อเนื่อง 5 วินาที
    4. ถ้ามี movement / UNKNOWN ให้เริ่มนับใหม่

    จุดประสงค์:
    ลด initial seating / model settling drift โดยกำหนดไว้ใน
    protocol ก่อนเริ่ม scored trials ไม่ใช่ตัด Round 1 ทิ้งภายหลัง
    """

    print()
    print("=" * 70)
    print("INITIAL WARM-UP")
    print("=" * 70)
    print(
        "Sit naturally, look forward, relax both shoulders."
    )
    print(
        f"Hold a VALID context continuously for "
        f"{INITIAL_WARMUP_VALID_SECONDS:.1f} seconds."
    )
    print("ESC = abort test")

    valid_since = None

    while True:
        success, frame = capture.read()

        if not success or frame is None:
            time.sleep(0.01)
            continue

        result = pipeline.process_frame(
            frame,
            time.perf_counter(),
        )

        context = extract_context(result)

        state = context.get(
            "state",
            "UNKNOWN",
        )

        reason = context.get(
            "reason",
            "-",
        )

        if context_is_valid(context):
            if valid_since is None:
                valid_since = time.perf_counter()

            valid_elapsed = (
                time.perf_counter()
                -
                valid_since
            )

        else:
            valid_since = None
            valid_elapsed = 0.0

        display = make_preview(frame)

        draw_line(
            display,
            "INITIAL WARM-UP - NORMAL POSTURE",
            35,
            0.75,
        )

        draw_line(
            display,
            f"Context: {state}",
            75,
        )

        draw_line(
            display,
            f"Reason: {reason}",
            110,
            0.60,
        )

        draw_line(
            display,
            (
                "Continuous VALID: "
                f"{valid_elapsed:.1f}/"
                f"{INITIAL_WARMUP_VALID_SECONDS:.1f}s"
            ),
            145,
        )

        draw_line(
            display,
            "Stay still and look forward",
            180,
            0.60,
        )

        draw_line(
            display,
            "ESC = abort",
            215,
            0.55,
            1,
        )

        cv2.imshow(
            WINDOW_NAME,
            display,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            raise KeyboardInterrupt

        if (
            valid_elapsed
            >=
            INITIAL_WARMUP_VALID_SECONDS
        ):
            print(
                "[OK] Initial warm-up completed."
            )
            return


# ==========================================================
# Wait Until State Is Ready
# ==========================================================

def wait_until_state_ready(
    pipeline,
    capture,
    round_number,
    state,
):
    """
    ผู้ใช้จัดท่าก่อน

    ระบบอนุญาตให้กด SPACE เมื่อ:
    - Context = VALID
    - allow_posture_evaluation = True
    - stable_seconds >= STATE_SETTLE_SECONDS
    """

    instruction = STATE_INSTRUCTIONS[
        state
    ]

    while True:
        success, frame = capture.read()

        if not success or frame is None:
            time.sleep(0.01)
            continue

        result = pipeline.process_frame(
            frame,
            time.perf_counter(),
        )

        context = extract_context(
            result
        )

        context_state = context.get(
            "state",
            "UNKNOWN",
        )

        context_reason = context.get(
            "reason",
            "-",
        )

        stable_seconds = context.get(
            "stable_seconds",
            0.0,
        )

        if not is_finite_number(
            stable_seconds
        ):
            stable_seconds = 0.0

        stable_seconds = float(
            stable_seconds
        )

        ready = (
            context_is_valid(
                context
            )
            and
            stable_seconds
            >=
            STATE_SETTLE_SECONDS
        )

        left, right = (
            extract_shoulder_elevation(
                result
            )
        )

        display = make_preview(
            frame
        )

        draw_line(
            display,
            (
                f"Round {round_number}/"
                f"{TOTAL_ROUNDS} | {state}"
            ),
            35,
            0.75,
        )

        draw_line(
            display,
            instruction,
            75,
            0.50,
        )

        draw_line(
            display,
            f"Context: {context_state}",
            115,
        )

        draw_line(
            display,
            f"Reason: {context_reason}",
            150,
            0.55,
        )

        draw_line(
            display,
            (
                "Stable: "
                f"{stable_seconds:.2f}s "
                f"(need >= {STATE_SETTLE_SECONDS:.1f}s)"
            ),
            185,
            0.60,
        )

        if (
            is_finite_number(left)
            and
            is_finite_number(right)
        ):
            draw_line(
                display,
                (
                    f"Shoulder L={float(left):.5f} "
                    f"R={float(right):.5f}"
                ),
                220,
                0.60,
            )

        if ready:
            draw_line(
                display,
                "READY - SPACE = start recording",
                260,
                0.70,
            )
        else:
            draw_line(
                display,
                "WAIT - hold the posture still",
                260,
                0.70,
            )

        draw_line(
            display,
            "ESC = abort test",
            295,
            0.55,
            1,
        )

        cv2.imshow(
            WINDOW_NAME,
            display,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            raise KeyboardInterrupt

        if key == 32 and ready:
            return


# ==========================================================
# Record One Continuous Valid Attempt
# ==========================================================

def record_state_attempt(
    pipeline,
    capture,
    round_number,
    state,
    raw_rows,
    attempt_number,
):
    samples = []

    start_time = (
        time.perf_counter()
    )

    while True:
        elapsed = (
            time.perf_counter()
            -
            start_time
        )

        if (
            elapsed
            >=
            SAMPLE_DURATION_SECONDS
        ):
            return {
                "success": True,
                "samples": samples,
                "reason": "completed",
            }

        success, frame = (
            capture.read()
        )

        if not success or frame is None:
            return {
                "success": False,
                "samples": [],
                "reason": "camera_frame_failed",
            }

        timestamp = (
            time.perf_counter()
        )

        result = (
            pipeline.process_frame(
                frame,
                timestamp,
            )
        )

        context = extract_context(
            result
        )

        context_state = context.get(
            "state",
            "UNKNOWN",
        )

        context_reason = context.get(
            "reason",
            "-",
        )

        allow_posture = (
            context.get(
                "allow_posture_evaluation",
                False,
            )
            is True
        )

        stable_seconds = context.get(
            "stable_seconds",
            0.0,
        )

        left, right = (
            extract_shoulder_elevation(
                result
            )
        )

        feature_valid = (
            is_finite_number(left)
            and
            is_finite_number(right)
        )

        context_valid = (
            context_state == "VALID"
            and
            allow_posture
        )

        valid = (
            feature_valid
            and
            context_valid
        )

        raw_rows.append(
            {
                "timestamp": (
                    datetime.now().isoformat(
                        timespec="milliseconds"
                    )
                ),
                "round": round_number,
                "state": state,
                "attempt": attempt_number,
                "elapsed_seconds": elapsed,
                "context_state": context_state,
                "context_reason": context_reason,
                "context_stable_seconds": (
                    stable_seconds
                ),
                "allow_posture_evaluation": (
                    allow_posture
                ),
                "valid": valid,
                "left": (
                    float(left)
                    if is_finite_number(left)
                    else ""
                ),
                "right": (
                    float(right)
                    if is_finite_number(right)
                    else ""
                ),
            }
        )

        # --------------------------------------------------
        # Strict continuous-context recording.
        #
        # If the user starts moving again, discard this
        # recording attempt. Do NOT mix transition samples
        # into the scored state.
        # --------------------------------------------------

        if not context_valid:
            return {
                "success": False,
                "samples": [],
                "reason": (
                    "context_lost_during_recording:"
                    f"{context_state}/"
                    f"{context_reason}"
                ),
            }

        if feature_valid:
            samples.append(
                {
                    "left": float(
                        left
                    ),
                    "right": float(
                        right
                    ),
                }
            )

        display = make_preview(
            frame
        )

        remaining = max(
            0.0,
            SAMPLE_DURATION_SECONDS
            -
            elapsed,
        )

        draw_line(
            display,
            (
                f"Round {round_number}/"
                f"{TOTAL_ROUNDS} | {state}"
            ),
            35,
            0.75,
        )

        draw_line(
            display,
            (
                f"RECORDING attempt "
                f"{attempt_number} | "
                f"{remaining:.1f}s"
            ),
            75,
            0.70,
        )

        draw_line(
            display,
            (
                f"Context: {context_state} | "
                f"Allow: {allow_posture}"
            ),
            115,
            0.60,
        )

        draw_line(
            display,
            (
                f"Valid samples: "
                f"{len(samples)}"
            ),
            150,
            0.60,
        )

        if feature_valid:
            draw_line(
                display,
                (
                    f"L={float(left):.5f} | "
                    f"R={float(right):.5f}"
                ),
                185,
                0.60,
            )
        else:
            draw_line(
                display,
                "Shoulder elevation: INVALID",
                185,
                0.60,
            )

        draw_line(
            display,
            "Stay completely still",
            220,
            0.60,
        )

        draw_line(
            display,
            "ESC = abort test",
            255,
            0.55,
            1,
        )

        cv2.imshow(
            WINDOW_NAME,
            display,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            raise KeyboardInterrupt


# ==========================================================
# Capture One State
# ==========================================================

def capture_state(
    pipeline,
    capture,
    round_number,
    state,
    raw_rows,
):
    print()
    print("=" * 70)
    print(
        f"ROUND {round_number}/"
        f"{TOTAL_ROUNDS} | {state}"
    )
    print(
        STATE_INSTRUCTIONS[
            state
        ]
    )
    print("=" * 70)
    print(
        "Hold the posture until Context=VALID "
        "and stable >= "
        f"{STATE_SETTLE_SECONDS:.1f}s."
    )
    print(
        "SPACE works only when the state is READY."
    )
    print(
        "If Context drops during recording, "
        "that attempt is discarded and retried."
    )

    for attempt_number in range(
        1,
        MAX_RECORDING_ATTEMPTS_PER_STATE
        +
        1,
    ):
        wait_until_state_ready(
            pipeline=pipeline,
            capture=capture,
            round_number=round_number,
            state=state,
        )

        attempt = (
            record_state_attempt(
                pipeline=pipeline,
                capture=capture,
                round_number=round_number,
                state=state,
                raw_rows=raw_rows,
                attempt_number=(
                    attempt_number
                ),
            )
        )

        if attempt[
            "success"
        ]:
            samples = (
                attempt[
                    "samples"
                ]
            )

            print(
                f"[{state}] Captured "
                f"{len(samples)} continuous "
                "VALID samples."
            )

            return samples

        print(
            f"[RETRY] {state} attempt "
            f"{attempt_number} discarded: "
            f"{attempt['reason']}"
        )

    raise RuntimeError(
        f"{state}: failed to obtain a "
        "continuous valid recording after "
        f"{MAX_RECORDING_ATTEMPTS_PER_STATE} attempts."
    )


# ==========================================================
# State Summary
# ==========================================================

def print_state_summary(
    round_number,
    state,
    summary,
):
    print()
    print(
        f"[Round {round_number}] "
        f"{state}"
    )

    print(
        "  Valid samples: "
        f"{summary['valid_samples']}"
    )

    if (
        summary["left"] is None
        or
        summary["right"] is None
    ):
        print(
            "  Result: insufficient valid data"
        )
        return

    print(
        "  LEFT  "
        f"median={summary['left']['median']:.6f} "
        f"std={summary['left']['std']:.6f}"
    )

    print(
        "  RIGHT "
        f"median={summary['right']['median']:.6f} "
        f"std={summary['right']['std']:.6f}"
    )


# ==========================================================
# Ratio
# ==========================================================

def safe_ratio(
    numerator,
    denominator,
):
    denominator = abs(
        float(
            denominator
        )
    )

    if denominator <= EPSILON:
        return math.inf

    return (
        abs(
            float(
                numerator
            )
        )
        /
        denominator
    )


# ==========================================================
# Analyze One Side
# ==========================================================

def analyze_side(
    normal_1,
    raise_both,
    normal_2,
    neck_flexion,
    normal_3,
):
    normal_values = [
        normal_1,
        normal_2,
        normal_3,
    ]

    raise_baseline = float(
        statistics.median(
            [
                normal_1,
                normal_2,
            ]
        )
    )

    neck_baseline = float(
        statistics.median(
            [
                normal_2,
                normal_3,
            ]
        )
    )

    raise_delta = (
        float(
            raise_both
        )
        -
        raise_baseline
    )

    neck_delta = (
        float(
            neck_flexion
        )
        -
        neck_baseline
    )

    shoulder_response = abs(
        raise_delta
    )

    neck_crosstalk = abs(
        neck_delta
    )

    normal_variability = (
        max(
            normal_values
        )
        -
        min(
            normal_values
        )
    )

    crosstalk_ratio = (
        safe_ratio(
            neck_crosstalk,
            shoulder_response,
        )
    )

    signal_to_normal = (
        safe_ratio(
            shoulder_response,
            normal_variability,
        )
    )

    passed = (
        shoulder_response
        >
        EPSILON

        and

        crosstalk_ratio
        <=
        MAX_CROSSTALK_RATIO

        and

        signal_to_normal
        >=
        MIN_SIGNAL_TO_NORMAL_VARIABILITY
    )

    return {
        "raise_baseline": raise_baseline,
        "neck_baseline": neck_baseline,
        "raise_delta": raise_delta,
        "neck_delta": neck_delta,
        "shoulder_response": (
            shoulder_response
        ),
        "neck_crosstalk": (
            neck_crosstalk
        ),
        "normal_variability": (
            normal_variability
        ),
        "crosstalk_ratio": (
            crosstalk_ratio
        ),
        "signal_to_normal_variability": (
            signal_to_normal
        ),
        "passed": passed,
    }


# ==========================================================
# Analyze One Round
# ==========================================================

def analyze_round(
    round_number,
    state_summaries,
):
    state_map = {
        row["state"]: row
        for row in state_summaries
        if row["round"] == round_number
    }

    required_states = (
        "NORMAL_1",
        "RAISE_BOTH",
        "NORMAL_2",
        "NECK_FLEXION_ONLY",
        "NORMAL_3",
    )

    for state in required_states:
        row = state_map.get(
            state
        )

        if row is None:
            return {
                "round": round_number,
                "status": "INSUFFICIENT_DATA",
                "reason": (
                    f"Missing state: {state}"
                ),
            }

        if (
            row["valid_samples"]
            <
            MIN_VALID_SAMPLES
        ):
            return {
                "round": round_number,
                "status": "INSUFFICIENT_DATA",
                "reason": (
                    f"{state} has only "
                    f"{row['valid_samples']} "
                    "valid samples"
                ),
            }

        if (
            row["left"] is None
            or
            row["right"] is None
        ):
            return {
                "round": round_number,
                "status": "INSUFFICIENT_DATA",
                "reason": (
                    f"{state} has no valid summary"
                ),
            }

    def median_of(
        state,
        side,
    ):
        return (
            state_map[
                state
            ][
                side
            ][
                "median"
            ]
        )

    left = analyze_side(
        median_of(
            "NORMAL_1",
            "left",
        ),
        median_of(
            "RAISE_BOTH",
            "left",
        ),
        median_of(
            "NORMAL_2",
            "left",
        ),
        median_of(
            "NECK_FLEXION_ONLY",
            "left",
        ),
        median_of(
            "NORMAL_3",
            "left",
        ),
    )

    right = analyze_side(
        median_of(
            "NORMAL_1",
            "right",
        ),
        median_of(
            "RAISE_BOTH",
            "right",
        ),
        median_of(
            "NORMAL_2",
            "right",
        ),
        median_of(
            "NECK_FLEXION_ONLY",
            "right",
        ),
        median_of(
            "NORMAL_3",
            "right",
        ),
    )

    combined_shoulder_response = float(
        statistics.median(
            [
                left[
                    "shoulder_response"
                ],
                right[
                    "shoulder_response"
                ],
            ]
        )
    )

    combined_neck_crosstalk = float(
        statistics.median(
            [
                left[
                    "neck_crosstalk"
                ],
                right[
                    "neck_crosstalk"
                ],
            ]
        )
    )

    combined_normal_variability = float(
        statistics.median(
            [
                left[
                    "normal_variability"
                ],
                right[
                    "normal_variability"
                ],
            ]
        )
    )

    combined_crosstalk_ratio = (
        safe_ratio(
            combined_neck_crosstalk,
            combined_shoulder_response,
        )
    )

    passed = (
        left[
            "passed"
        ]
        and
        right[
            "passed"
        ]
    )

    return {
        "round": round_number,
        "status": (
            "PASS"
            if passed
            else "FAIL"
        ),
        "reason": "",
        "left": left,
        "right": right,
        "combined_shoulder_response": (
            combined_shoulder_response
        ),
        "combined_neck_crosstalk": (
            combined_neck_crosstalk
        ),
        "combined_normal_variability": (
            combined_normal_variability
        ),
        "combined_crosstalk_ratio": (
            combined_crosstalk_ratio
        ),
    }


# ==========================================================
# Direction Consistency
# ==========================================================

def has_consistent_nonzero_sign(
    values
):
    signs = []

    for value in values:
        if not is_finite_number(
            value
        ):
            continue

        value = float(
            value
        )

        if abs(
            value
        ) <= EPSILON:
            continue

        signs.append(
            1
            if value > 0
            else -1
        )

    return (
        len(signs)
        ==
        TOTAL_ROUNDS

        and

        len(
            set(
                signs
            )
        )
        ==
        1
    )


# ==========================================================
# Overall
# ==========================================================

def analyze_overall(
    round_analyses
):
    complete_rounds = [
        row
        for row in round_analyses
        if (
            row.get("left")
            is not None
            and
            row.get("right")
            is not None
        )
    ]

    if (
        len(
            complete_rounds
        )
        !=
        TOTAL_ROUNDS
    ):
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": (
                "At least one round does not "
                "have enough valid data."
            ),
        }

    left_direction_consistent = (
        has_consistent_nonzero_sign(
            [
                row[
                    "left"
                ][
                    "raise_delta"
                ]
                for row in (
                    complete_rounds
                )
            ]
        )
    )

    right_direction_consistent = (
        has_consistent_nonzero_sign(
            [
                row[
                    "right"
                ][
                    "raise_delta"
                ]
                for row in (
                    complete_rounds
                )
            ]
        )
    )

    all_rounds_passed = all(
        row[
            "status"
        ]
        ==
        "PASS"
        for row in complete_rounds
    )

    passed = (
        all_rounds_passed
        and
        left_direction_consistent
        and
        right_direction_consistent
    )

    return {
        "status": (
            "PASS"
            if passed
            else "FAIL"
        ),

        "reason": "",

        "median_combined_shoulder_response": float(
            statistics.median(
                [
                    row[
                        "combined_shoulder_response"
                    ]
                    for row in complete_rounds
                ]
            )
        ),

        "median_combined_neck_crosstalk": float(
            statistics.median(
                [
                    row[
                        "combined_neck_crosstalk"
                    ]
                    for row in complete_rounds
                ]
            )
        ),

        "median_combined_normal_variability": float(
            statistics.median(
                [
                    row[
                        "combined_normal_variability"
                    ]
                    for row in complete_rounds
                ]
            )
        ),

        "median_combined_crosstalk_ratio": float(
            statistics.median(
                [
                    row[
                        "combined_crosstalk_ratio"
                    ]
                    for row in complete_rounds
                ]
            )
        ),

        "left_direction_consistent": (
            left_direction_consistent
        ),

        "right_direction_consistent": (
            right_direction_consistent
        ),
    }


# ==========================================================
# Print Analysis
# ==========================================================

def print_round_analysis(
    analysis
):
    print()
    print("=" * 70)
    print(
        f"ROUND {analysis['round']} ANALYSIS"
    )
    print("=" * 70)

    if (
        analysis[
            "status"
        ]
        ==
        "INSUFFICIENT_DATA"
    ):
        print(
            "Status: INSUFFICIENT_DATA"
        )
        print(
            f"Reason: {analysis['reason']}"
        )
        return

    for label, key in (
        (
            "LEFT",
            "left",
        ),
        (
            "RIGHT",
            "right",
        ),
    ):
        row = analysis[
            key
        ]

        print()
        print(
            label
        )

        print(
            "  Raise baseline    : "
            f"{row['raise_baseline']:.6f}"
        )

        print(
            "  Raise delta       : "
            f"{row['raise_delta']:.6f}"
        )

        print(
            "  Neck baseline     : "
            f"{row['neck_baseline']:.6f}"
        )

        print(
            "  Neck delta        : "
            f"{row['neck_delta']:.6f}"
        )

        print(
            "  Shoulder response : "
            f"{row['shoulder_response']:.6f}"
        )

        print(
            "  Neck cross-talk   : "
            f"{row['neck_crosstalk']:.6f}"
        )

        print(
            "  Normal variability: "
            f"{row['normal_variability']:.6f}"
        )

        print(
            "  Cross-talk ratio  : "
            f"{row['crosstalk_ratio']:.3f}"
        )

        print(
            "  Signal / normal   : "
            f"{row['signal_to_normal_variability']:.3f}"
        )

        print(
            "  Result            : "
            f"{'PASS' if row['passed'] else 'FAIL'}"
        )

    print()
    print(
        "Combined Shoulder response : "
        f"{analysis['combined_shoulder_response']:.6f}"
    )

    print(
        "Combined Neck cross-talk   : "
        f"{analysis['combined_neck_crosstalk']:.6f}"
    )

    print(
        "Combined Normal variability: "
        f"{analysis['combined_normal_variability']:.6f}"
    )

    print(
        "Combined Cross-talk ratio  : "
        f"{analysis['combined_crosstalk_ratio']:.3f}"
    )

    print(
        "ROUND RESULT: "
        f"{analysis['status']}"
    )


def print_overall_analysis(
    overall
):
    print()
    print("#" * 70)
    print(
        "SHOULDER ELEVATION FINAL VALIDATION TEST"
    )
    print("#" * 70)

    print(
        "OVERALL STATUS: "
        f"{overall['status']}"
    )

    if (
        overall[
            "status"
        ]
        ==
        "INSUFFICIENT_DATA"
    ):
        print(
            "Reason: "
            f"{overall['reason']}"
        )
        return

    print(
        "Median Shoulder response : "
        f"{overall['median_combined_shoulder_response']:.6f}"
    )

    print(
        "Median Neck cross-talk   : "
        f"{overall['median_combined_neck_crosstalk']:.6f}"
    )

    print(
        "Median Normal variability: "
        f"{overall['median_combined_normal_variability']:.6f}"
    )

    print(
        "Median Cross-talk ratio  : "
        f"{overall['median_combined_crosstalk_ratio']:.3f}"
    )

    print(
        "Left response direction consistent : "
        f"{overall['left_direction_consistent']}"
    )

    print(
        "Right response direction consistent: "
        f"{overall['right_direction_consistent']}"
    )

    print()
    print(
        "Prototype Criteria:"
    )

    print(
        "  Cross-talk ratio <= "
        f"{MAX_CROSSTALK_RATIO:.2f}"
    )

    print(
        "  Shoulder response / "
        "normal variability >= "
        f"{MIN_SIGNAL_TO_NORMAL_VARIABILITY:.1f}"
    )

    print(
        "  Response direction must be "
        "consistent across all 3 rounds"
    )

    print(
        "  All 3 scored rounds must PASS"
    )

    print()

    if (
        overall[
            "status"
        ]
        ==
        "PASS"
    ):
        print(
            "Decision: Shoulder Elevation v2 "
            "passes this final engineering "
            "prototype validation."
        )

        print(
            "It may be marked "
            "validated_prototype for this "
            "defined test."
        )

        print(
            "This is NOT clinical validation."
        )

    else:
        print(
            "Decision: Shoulder Elevation v2 "
            "has NOT passed final prototype "
            "validation."
        )

        print(
            "Do NOT lower thresholds only "
            "to force PASS."
        )


# ==========================================================
# CSV
# ==========================================================

def save_raw_csv(
    output_path,
    raw_rows,
):
    fieldnames = [
        "timestamp",
        "round",
        "state",
        "attempt",
        "elapsed_seconds",
        "context_state",
        "context_reason",
        "context_stable_seconds",
        "allow_posture_evaluation",
        "valid",
        "left",
        "right",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(
            raw_rows
        )


def save_summary_csv(
    output_path,
    state_summaries,
    round_analyses,
    overall,
):
    fieldnames = [
        "row_type",
        "round",
        "state",
        "status",
        "valid_samples",
        "left_median",
        "left_mean",
        "left_std",
        "left_min",
        "left_max",
        "right_median",
        "right_mean",
        "right_std",
        "right_min",
        "right_max",
        "left_shoulder_response",
        "left_neck_crosstalk",
        "left_normal_variability",
        "left_crosstalk_ratio",
        "left_signal_to_normal",
        "left_passed",
        "right_shoulder_response",
        "right_neck_crosstalk",
        "right_normal_variability",
        "right_crosstalk_ratio",
        "right_signal_to_normal",
        "right_passed",
        "combined_shoulder_response",
        "combined_neck_crosstalk",
        "combined_normal_variability",
        "combined_crosstalk_ratio",
        "left_direction_consistent",
        "right_direction_consistent",
        "reason",
    ]

    rows = []

    # ------------------------------------------------------
    # State rows
    # ------------------------------------------------------

    for summary in state_summaries:
        left = (
            summary[
                "left"
            ]
            or
            {}
        )

        right = (
            summary[
                "right"
            ]
            or
            {}
        )

        rows.append(
            {
                "row_type": "STATE",
                "round": summary[
                    "round"
                ],
                "state": summary[
                    "state"
                ],
                "status": "",
                "valid_samples": summary[
                    "valid_samples"
                ],
                "left_median": left.get(
                    "median",
                    "",
                ),
                "left_mean": left.get(
                    "mean",
                    "",
                ),
                "left_std": left.get(
                    "std",
                    "",
                ),
                "left_min": left.get(
                    "min",
                    "",
                ),
                "left_max": left.get(
                    "max",
                    "",
                ),
                "right_median": right.get(
                    "median",
                    "",
                ),
                "right_mean": right.get(
                    "mean",
                    "",
                ),
                "right_std": right.get(
                    "std",
                    "",
                ),
                "right_min": right.get(
                    "min",
                    "",
                ),
                "right_max": right.get(
                    "max",
                    "",
                ),
            }
        )

    # ------------------------------------------------------
    # Round rows
    # ------------------------------------------------------

    for analysis in round_analyses:
        row = {
            "row_type": (
                "ROUND_ANALYSIS"
            ),
            "round": analysis[
                "round"
            ],
            "state": "",
            "status": analysis[
                "status"
            ],
            "reason": analysis.get(
                "reason",
                "",
            ),
        }

        if (
            analysis.get(
                "left"
            )
            is not None

            and

            analysis.get(
                "right"
            )
            is not None
        ):
            left = analysis[
                "left"
            ]

            right = analysis[
                "right"
            ]

            row.update(
                {
                    "left_shoulder_response": (
                        left[
                            "shoulder_response"
                        ]
                    ),
                    "left_neck_crosstalk": (
                        left[
                            "neck_crosstalk"
                        ]
                    ),
                    "left_normal_variability": (
                        left[
                            "normal_variability"
                        ]
                    ),
                    "left_crosstalk_ratio": (
                        left[
                            "crosstalk_ratio"
                        ]
                    ),
                    "left_signal_to_normal": (
                        left[
                            "signal_to_normal_variability"
                        ]
                    ),
                    "left_passed": (
                        left[
                            "passed"
                        ]
                    ),
                    "right_shoulder_response": (
                        right[
                            "shoulder_response"
                        ]
                    ),
                    "right_neck_crosstalk": (
                        right[
                            "neck_crosstalk"
                        ]
                    ),
                    "right_normal_variability": (
                        right[
                            "normal_variability"
                        ]
                    ),
                    "right_crosstalk_ratio": (
                        right[
                            "crosstalk_ratio"
                        ]
                    ),
                    "right_signal_to_normal": (
                        right[
                            "signal_to_normal_variability"
                        ]
                    ),
                    "right_passed": (
                        right[
                            "passed"
                        ]
                    ),
                    "combined_shoulder_response": (
                        analysis[
                            "combined_shoulder_response"
                        ]
                    ),
                    "combined_neck_crosstalk": (
                        analysis[
                            "combined_neck_crosstalk"
                        ]
                    ),
                    "combined_normal_variability": (
                        analysis[
                            "combined_normal_variability"
                        ]
                    ),
                    "combined_crosstalk_ratio": (
                        analysis[
                            "combined_crosstalk_ratio"
                        ]
                    ),
                }
            )

        rows.append(
            row
        )

    # ------------------------------------------------------
    # Overall row
    # ------------------------------------------------------

    overall_row = {
        "row_type": "OVERALL",
        "round": "",
        "state": "",
        "status": overall[
            "status"
        ],
        "reason": overall.get(
            "reason",
            "",
        ),
    }

    if (
        overall[
            "status"
        ]
        !=
        "INSUFFICIENT_DATA"
    ):
        overall_row.update(
            {
                "combined_shoulder_response": (
                    overall[
                        "median_combined_shoulder_response"
                    ]
                ),
                "combined_neck_crosstalk": (
                    overall[
                        "median_combined_neck_crosstalk"
                    ]
                ),
                "combined_normal_variability": (
                    overall[
                        "median_combined_normal_variability"
                    ]
                ),
                "combined_crosstalk_ratio": (
                    overall[
                        "median_combined_crosstalk_ratio"
                    ]
                ),
                "left_direction_consistent": (
                    overall[
                        "left_direction_consistent"
                    ]
                ),
                "right_direction_consistent": (
                    overall[
                        "right_direction_consistent"
                    ]
                ),
            }
        )

    rows.append(
        overall_row
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


# ==========================================================
# Main
# ==========================================================

def main():
    camera_index = 0

    capture = cv2.VideoCapture(
        camera_index,
        cv2.CAP_DSHOW,
    )

    if not capture.isOpened():
        capture.release()

        capture = cv2.VideoCapture(
            camera_index
        )

    if not capture.isOpened():
        raise RuntimeError(
            "Cannot open camera index 0."
        )

    print(
        "[OK] Camera opened."
    )

    pipeline = (
        DetectionPipeline()
    )

    raw_rows = []
    state_summaries = []

    try:
        print()
        print("=" * 70)
        print(
            "PostGuard Shoulder Elevation "
            "FINAL Validation Test"
        )
        print("=" * 70)

        print(
            f"Rounds: {TOTAL_ROUNDS}"
        )

        print(
            "Warm-up continuous VALID: "
            f"{INITIAL_WARMUP_VALID_SECONDS:.1f}s"
        )

        print(
            "Required stable hold before SPACE: "
            f"{STATE_SETTLE_SECONDS:.1f}s"
        )

        print(
            "Recording duration: "
            f"{SAMPLE_DURATION_SECONDS:.1f}s/state"
        )

        print(
            "Minimum valid samples: "
            f"{MIN_VALID_SAMPLES}"
        )

        print()
        print(
            "Prototype criteria:"
        )

        print(
            "  Cross-talk ratio <= "
            f"{MAX_CROSSTALK_RATIO:.2f}"
        )

        print(
            "  Signal / normal variability >= "
            f"{MIN_SIGNAL_TO_NORMAL_VARIABILITY:.1f}"
        )

        print(
            "  All 3 rounds PASS"
        )

        print(
            "  Raise direction consistent"
        )

        print()
        print(
            "Detection uses RAW unmirrored frames."
        )

        print(
            "Preview is mirrored only for display."
        )

        # --------------------------------------------------
        # Reset context to ensure warm-up starts clean.
        # --------------------------------------------------

        if hasattr(
            pipeline,
            "reset_context",
        ):
            pipeline.reset_context()

        # --------------------------------------------------
        # Initial Warm-up
        # --------------------------------------------------

        run_initial_warmup(
            pipeline=pipeline,
            capture=capture,
        )

        # --------------------------------------------------
        # Scored States
        # --------------------------------------------------

        for test_case in (
            TEST_SEQUENCE
        ):
            round_number = (
                test_case[
                    "round"
                ]
            )

            state = (
                test_case[
                    "state"
                ]
            )

            samples = (
                capture_state(
                    pipeline=pipeline,
                    capture=capture,
                    round_number=(
                        round_number
                    ),
                    state=state,
                    raw_rows=raw_rows,
                )
            )

            summary = (
                summarize_samples(
                    samples
                )
            )

            summary.update(
                {
                    "round": (
                        round_number
                    ),
                    "state": state,
                }
            )

            state_summaries.append(
                summary
            )

            print_state_summary(
                round_number,
                state,
                summary,
            )

        # --------------------------------------------------
        # Analysis
        # --------------------------------------------------

        round_analyses = [
            analyze_round(
                round_number,
                state_summaries,
            )
            for round_number in range(
                1,
                TOTAL_ROUNDS
                +
                1,
            )
        ]

        for analysis in (
            round_analyses
        ):
            print_round_analysis(
                analysis
            )

        overall = (
            analyze_overall(
                round_analyses
            )
        )

        print_overall_analysis(
            overall
        )

        # --------------------------------------------------
        # Save
        # --------------------------------------------------

        output_dir = (
            Path(__file__)
            .resolve()
            .parent
            /
            "results"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        run_stamp = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        raw_csv_path = (
            output_dir
            /
            (
                "shoulder_elevation_"
                "final_validation_"
                f"{run_stamp}"
                "_raw.csv"
            )
        )

        summary_csv_path = (
            output_dir
            /
            (
                "shoulder_elevation_"
                "final_validation_"
                f"{run_stamp}"
                "_summary.csv"
            )
        )

        save_raw_csv(
            raw_csv_path,
            raw_rows,
        )

        save_summary_csv(
            summary_csv_path,
            state_summaries,
            round_analyses,
            overall,
        )

        print()
        print("=" * 70)
        print(
            "FILES SAVED"
        )
        print("=" * 70)

        print(
            "Raw CSV:"
        )
        print(
            raw_csv_path
        )

        print()
        print(
            "Summary CSV:"
        )
        print(
            summary_csv_path
        )

        if (
            overall[
                "status"
            ]
            ==
            "PASS"
        ):
            return 0

        return 1

    except KeyboardInterrupt:
        print()
        print(
            "Test aborted by user."
        )

        return 130

    finally:
        try:
            if hasattr(
                pipeline,
                "close",
            ):
                pipeline.close()

        finally:
            capture.release()
            cv2.destroyAllWindows()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )
