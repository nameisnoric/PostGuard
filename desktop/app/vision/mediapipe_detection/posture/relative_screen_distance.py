"""
PostGuard Relative Screen Distance
==================================

Calculate relative face-to-camera distance from apparent inter-eye
distance compared with the user's Personal Baseline.

Important:
- This module does NOT calculate physical distance in cm.
- eye_distance is an apparent Inter-Eye Distance / IPD Proxy.
- This module does NOT define SCREEN_TOO_CLOSE.
- This module does NOT define a production threshold.
- This module does NOT perform Risk Evaluation.
- This module does NOT create Risk Events or Alerts.

Validated relationship:

    eye_distance increases -> user appears closer
    eye_distance decreases -> user appears farther

Relative ratio:

    current_eye_distance_px / baseline_eye_distance_px
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


# ============================================================
# Version
# ============================================================

RELATIVE_SCREEN_DISTANCE_VERSION = "1.0"


# ============================================================
# Status
# ============================================================

STATUS_EVALUATED = "EVALUATED"

STATUS_NOT_EVALUATED = "NOT_EVALUATED"


# ============================================================
# Direction
# ============================================================

DIRECTION_BASELINE = "BASELINE"

DIRECTION_CLOSER = "CLOSER"

DIRECTION_FARTHER = "FARTHER"


# ============================================================
# Numeric Helpers
# ============================================================

def _finite_number(
    value: Any,
) -> float | None:
    """
    Convert a value to a finite float.

    bool is explicitly rejected because:

        isinstance(True, int) == True

    but True/False must never be interpreted as an eye-distance
    measurement.
    """

    if isinstance(value, bool):
        return None

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(number):
        return None

    return number


def _positive_number(
    value: Any,
) -> float | None:
    """
    Return a finite positive number.

    Eye distance must always be greater than zero.
    """

    number = _finite_number(
        value
    )

    if number is None:
        return None

    if number <= 0.0:
        return None

    return number


# ============================================================
# Core Relative Distance Calculation
# ============================================================

def calculate_relative_screen_distance(
    *,
    current_eye_distance_px: Any,
    baseline_eye_distance_px: Any,
) -> dict[str, Any]:
    """
    Calculate Relative Screen Distance.

    Formula:

        relative_ratio
            =
        current_eye_distance_px
            /
        baseline_eye_distance_px

    Examples:

        current  = 100 px
        baseline = 100 px

        ratio = 1.00
        direction = BASELINE


        current  = 130 px
        baseline = 100 px

        ratio = 1.30
        direction = CLOSER


        current  = 75 px
        baseline = 100 px

        ratio = 0.75
        direction = FARTHER


    Important
    ---------

    CLOSER does NOT mean SCREEN_TOO_CLOSE.

    FARTHER does NOT mean SCREEN_TOO_FAR.

    At this stage PostGuard only describes movement relative
    to the Personal Baseline.

    No ergonomic/risk threshold is applied here.
    """

    current = _positive_number(
        current_eye_distance_px
    )

    baseline = _positive_number(
        baseline_eye_distance_px
    )

    if current is None:
        raise ValueError(
            "current_eye_distance_px must be "
            "a finite positive number"
        )

    if baseline is None:
        raise ValueError(
            "baseline_eye_distance_px must be "
            "a finite positive number"
        )

    relative_ratio = (
        current
        /
        baseline
    )

    relative_change = (
        relative_ratio
        -
        1.0
    )

    percent_change = (
        relative_change
        *
        100.0
    )

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    # Use isclose only for floating-point equality around 1.0.
    # This is NOT a risk threshold.
    if math.isclose(
        relative_ratio,
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        direction = (
            DIRECTION_BASELINE
        )

    elif relative_ratio > 1.0:
        direction = (
            DIRECTION_CLOSER
        )

    else:
        direction = (
            DIRECTION_FARTHER
        )

    return {
        "version":
            RELATIVE_SCREEN_DISTANCE_VERSION,

        "status":
            STATUS_EVALUATED,

        "reason":
            "OK",

        "current_eye_distance_px":
            current,

        "baseline_eye_distance_px":
            baseline,

        "relative_ratio":
            relative_ratio,

        "relative_change":
            relative_change,

        "percent_change":
            percent_change,

        "direction":
            direction,

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # These intentionally remain None.
        #
        # We have NOT validated a production threshold yet.
        # ----------------------------------------------------

        "is_too_close":
            None,

        "is_too_far":
            None,

        "threshold_applied":
            False,

        # ----------------------------------------------------
        # Semantic Contract
        # ----------------------------------------------------

        "semantics": {

            "relative_to_personal_baseline":
                True,

            "physical_distance":
                False,

            "physical_distance_cm":
                False,

            "screen_too_close":
                False,

            "screen_too_far":
                False,

            "risk_evaluation":
                False,

            "medical_interpretation":
                False,
        },
    }


# ============================================================
# Personal Baseline Extraction
# ============================================================

def extract_eye_distance_baseline(
    baseline_data: Mapping[str, Any] | None,
) -> tuple[
    float | None,
    str | None,
    str,
]:
    """
    Extract eye-distance baseline from PostGuard baseline data.

    Supported formats
    -----------------

    1. New explicit field:

        eye_distance_baseline_px

    2. Current backend field:

        ipd_baseline

    3. PersonalBaselineCollector format:

        eye_distance


    Priority:

        eye_distance_baseline_px
            >
        ipd_baseline
            >
        eye_distance


    Returns
    -------

    (
        value,
        source,
        reason,
    )
    """

    if not isinstance(
        baseline_data,
        Mapping,
    ):
        return (
            None,
            None,
            "BASELINE_MISSING",
        )

    candidates = (
        "eye_distance_baseline_px",
        "ipd_baseline",
        "eye_distance",
    )

    for field_name in candidates:

        if field_name not in baseline_data:
            continue

        raw_value = (
            baseline_data.get(
                field_name
            )
        )

        value = _positive_number(
            raw_value
        )

        if value is not None:
            return (
                value,
                field_name,
                "OK",
            )

    return (
        None,
        None,
        "EYE_DISTANCE_BASELINE_MISSING",
    )


# ============================================================
# Detection Contract Extraction
# ============================================================

def _extract_current_eye_distance(
    detection_result: Mapping[str, Any] | None,
) -> tuple[
    float | None,
    str,
]:
    """
    Read eye_distance from PostGuard Detection Contract 1.0.

    Expected:

        detection_result
            ["features"]
            ["eye_distance"]

    Example:

        {
            "valid": True,
            "value": 120.0,
            "unit": "px",
            "reason": "OK",
            "status": "validated_prototype",
        }
    """

    if not isinstance(
        detection_result,
        Mapping,
    ):
        return (
            None,
            "DETECTION_RESULT_MISSING",
        )

    features = (
        detection_result.get(
            "features"
        )
    )

    if not isinstance(
        features,
        Mapping,
    ):
        return (
            None,
            "FEATURES_MISSING",
        )

    eye_feature = (
        features.get(
            "eye_distance"
        )
    )

    if not isinstance(
        eye_feature,
        Mapping,
    ):
        return (
            None,
            "EYE_DISTANCE_FEATURE_MISSING",
        )

    # --------------------------------------------------------
    # Feature validity
    # --------------------------------------------------------

    if eye_feature.get(
        "valid"
    ) is not True:

        reason = (
            eye_feature.get(
                "reason"
            )
        )

        if not isinstance(
            reason,
            str,
        ) or not reason:

            reason = (
                "EYE_DISTANCE_NOT_AVAILABLE"
            )

        return (
            None,
            reason,
        )

    # --------------------------------------------------------
    # Unit
    # --------------------------------------------------------

    unit = (
        eye_feature.get(
            "unit"
        )
    )

    if unit != "px":
        return (
            None,
            "INVALID_EYE_DISTANCE_UNIT",
        )

    # --------------------------------------------------------
    # Numeric value
    # --------------------------------------------------------

    value = _positive_number(
        eye_feature.get(
            "value"
        )
    )

    if value is None:
        return (
            None,
            "INVALID_EYE_DISTANCE_VALUE",
        )

    return (
        value,
        "OK",
    )


# ============================================================
# Not-Evaluated Result
# ============================================================

def _not_evaluated_result(
    reason: str,
    *,
    current_eye_distance_px: float | None = None,
    baseline_eye_distance_px: float | None = None,
    baseline_source: str | None = None,
) -> dict[str, Any]:
    """
    Build a stable NOT_EVALUATED contract.
    """

    return {
        "version":
            RELATIVE_SCREEN_DISTANCE_VERSION,

        "status":
            STATUS_NOT_EVALUATED,

        "reason":
            reason,

        "current_eye_distance_px":
            current_eye_distance_px,

        "baseline_eye_distance_px":
            baseline_eye_distance_px,

        "baseline_source":
            baseline_source,

        "relative_ratio":
            None,

        "relative_change":
            None,

        "percent_change":
            None,

        "direction":
            None,

        "is_too_close":
            None,

        "is_too_far":
            None,

        "threshold_applied":
            False,

        "semantics": {

            "relative_to_personal_baseline":
                True,

            "physical_distance":
                False,

            "physical_distance_cm":
                False,

            "screen_too_close":
                False,

            "screen_too_far":
                False,

            "risk_evaluation":
                False,

            "medical_interpretation":
                False,
        },
    }


# ============================================================
# Detection + Personal Baseline Adapter
# ============================================================

def evaluate_relative_screen_distance(
    detection_result: Mapping[str, Any] | None,
    baseline_data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """
    Evaluate Relative Screen Distance using:

        Detection Contract 1.0
                +
        Personal Baseline


    Pipeline:

        DetectionService

            features["eye_distance"]

                ↓

        Current Eye Distance

                +

        Personal Baseline

                ↓

        Relative Ratio

                ↓

        BASELINE / CLOSER / FARTHER


    This function intentionally stops here.

    It does NOT produce:

        SCREEN_TOO_CLOSE

    and does NOT call:

        Risk Evaluation
        Risk Event
        Alert Policy
    """

    # --------------------------------------------------------
    # 1. Current Detection
    # --------------------------------------------------------

    (
        current_eye_distance,
        detection_reason,
    ) = _extract_current_eye_distance(
        detection_result
    )

    if current_eye_distance is None:
        return _not_evaluated_result(
            detection_reason
        )

    # --------------------------------------------------------
    # 2. Personal Baseline
    # --------------------------------------------------------

    (
        baseline_eye_distance,
        baseline_source,
        baseline_reason,
    ) = extract_eye_distance_baseline(
        baseline_data
    )

    if baseline_eye_distance is None:
        return _not_evaluated_result(
            baseline_reason,
            current_eye_distance_px=(
                current_eye_distance
            ),
        )

    # --------------------------------------------------------
    # 3. Relative Calculation
    # --------------------------------------------------------

    result = (
        calculate_relative_screen_distance(
            current_eye_distance_px=(
                current_eye_distance
            ),
            baseline_eye_distance_px=(
                baseline_eye_distance
            ),
        )
    )

    # --------------------------------------------------------
    # 4. Add Integration Metadata
    # --------------------------------------------------------

    result[
        "baseline_source"
    ] = baseline_source

    return result