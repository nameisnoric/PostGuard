"""
PostGuard - Measurement Change Gate
===================================

หน้าที่:
    เปรียบเทียบค่าปัจจุบันกับ Personal Baseline
    แล้วบอกว่าแต่ละ posture feature:

        STABLE
        CHANGED
        NOT_EVALUATED
        NOT_CONFIGURED

สำคัญ:
    Measurement Change != Posture Risk

    Gate นี้ไม่ได้ตัดสินว่า:
        - ท่าดี / ท่าไม่ดี
        - ปลอดภัย / เสี่ยง
        - ต้อง Alert หรือไม่

Architecture:
    Session Monitoring
        ↓
    Measurement Change Gate
        ↓
    STABLE / CHANGED
        ↓
    Current Posture Assessment      (ขั้นต่อไป)
        ↓
    Temporal Tracking
        ↓
    Risk Evaluation
        ↓
    Alert

Version:
    Measurement-Change Gate v1
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# ============================================================
# Version
# ============================================================

MEASUREMENT_CHANGE_GATE_VERSION = "1.0"

# Backward compatibility
# session_monitoring/__init__.py และโค้ดเก่าบางส่วน
# ยัง import ชื่อนี้อยู่
CHANGE_GATE_VERSION = MEASUREMENT_CHANGE_GATE_VERSION


# ============================================================
# Status
# ============================================================

STATUS_STABLE = "STABLE"
STATUS_CHANGED = "CHANGED"
STATUS_NOT_EVALUATED = "NOT_EVALUATED"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"


# ============================================================
# Reasons
# ============================================================

REASON_WITHIN_THRESHOLD = (
    "ABS_DELTA_WITHIN_THRESHOLD"
)

REASON_ABOVE_THRESHOLD = (
    "ABS_DELTA_ABOVE_THRESHOLD"
)

REASON_MEASUREMENT_INVALID = (
    "MEASUREMENT_INVALID"
)

REASON_COMPARISON_NOT_ELIGIBLE = (
    "BASELINE_COMPARISON_NOT_ELIGIBLE"
)

REASON_DELTA_INVALID = (
    "DELTA_INVALID"
)

REASON_FEATURE_MISSING = (
    "FEATURE_MISSING"
)

REASON_THRESHOLD_NOT_CONFIGURED = (
    "THRESHOLD_NOT_CONFIGURED"
)

REASON_THRESHOLD_INVALID = (
    "THRESHOLD_INVALID"
)

REASON_UNIT_MISMATCH = (
    "UNIT_MISMATCH"
)


# ============================================================
# Posture Features
# ============================================================
#
# IMPORTANT
# ---------
#
# eye_distance ไม่อยู่ใน Measurement-Change Gate v1
#
# Eye Distance ยังคงอยู่ใน:
#     DetectionPipeline
#     Personal Baseline
#     Session Monitoring
#
# แต่จะนำไปใช้ใน:
#     Camera / User Position Monitoring
#
# ไม่ใช้ตัดสิน posture change
# ============================================================

FEATURE_SPECS = {
    "shoulder_tilt": {
        "unit": "deg",
    },

    "neck_lateral_tilt": {
        "unit": "deg",
    },

    "neck_flexion": {
        "unit": "deg",
    },
}


POSTURE_FEATURES = tuple(
    FEATURE_SPECS.keys()
)


# ============================================================
# Numeric Validation
# ============================================================

def _is_finite_number(
    value: Any,
) -> bool:
    """
    True เฉพาะ int / float ที่เป็น finite number

    ไม่ยอมรับ:
        None
        string เช่น "5.0"
        bool
        NaN
        +Inf
        -Inf

    เหตุผล:
        bool ใน Python เป็น subclass ของ int

        isinstance(True, int)
        → True

    ดังนั้นต้องกัน bool ออกเอง
    """

    if isinstance(value, bool):
        return False

    if not isinstance(
        value,
        (int, float),
    ):
        return False

    return math.isfinite(
        float(value)
    )


# ============================================================
# Threshold Config
# ============================================================

def load_threshold_config(
    path: str | Path,
) -> Dict[str, Any]:
    """
    โหลด Measurement-Change Threshold Config จาก JSON

    ใช้ utf-8-sig เพื่อรองรับทั้ง:
        - UTF-8 ปกติ
        - UTF-8 ที่มี BOM จาก Windows / PowerShell
    """

    config_path = Path(path)

    with config_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            "Threshold config must be a JSON object."
        )

    return data


def _get_feature_threshold(
    threshold_config: Dict[str, Any],
    feature_name: str,
) -> Dict[str, Any]:
    """
    อ่าน threshold ของ feature

    คืน structure:

        {
            "configured": bool,
            "reason": ...,
            "threshold": ...,
            "unit": ...,
        }
    """

    if not isinstance(
        threshold_config,
        dict,
    ):
        return {
            "configured": False,
            "reason": REASON_THRESHOLD_NOT_CONFIGURED,
            "threshold": None,
            "unit": None,
        }

    features_config = (
        threshold_config.get(
            "features"
        )
    )

    if not isinstance(
        features_config,
        dict,
    ):
        return {
            "configured": False,
            "reason": REASON_THRESHOLD_NOT_CONFIGURED,
            "threshold": None,
            "unit": None,
        }

    config_row = (
        features_config.get(
            feature_name
        )
    )

    if not isinstance(
        config_row,
        dict,
    ):
        return {
            "configured": False,
            "reason": REASON_THRESHOLD_NOT_CONFIGURED,
            "threshold": None,
            "unit": None,
        }

    threshold = (
        config_row.get(
            "threshold"
        )
    )

    unit = (
        config_row.get(
            "unit"
        )
    )

    # ห้าม convert string → float
    #
    # "1.153" ต้องถือว่า config ผิด
    # ไม่ใช่ยอมรับโดยอัตโนมัติ
    if not _is_finite_number(
        threshold
    ):
        return {
            "configured": False,
            "reason": REASON_THRESHOLD_INVALID,
            "threshold": None,
            "unit": unit,
        }

    threshold = float(
        threshold
    )

    if threshold <= 0.0:
        return {
            "configured": False,
            "reason": REASON_THRESHOLD_INVALID,
            "threshold": None,
            "unit": unit,
        }

    expected_unit = (
        FEATURE_SPECS[
            feature_name
        ][
            "unit"
        ]
    )

    if unit != expected_unit:
        return {
            "configured": False,
            "reason": REASON_UNIT_MISMATCH,
            "threshold": threshold,
            "unit": unit,
        }

    return {
        "configured": True,
        "reason": None,
        "threshold": threshold,
        "unit": unit,
    }


# ============================================================
# Feature Evaluation
# ============================================================

def _make_not_evaluated_row(
    *,
    reason: str,
    delta: Any = None,
    unit: Optional[str] = None,
) -> Dict[str, Any]:

    absolute_delta = None

    if _is_finite_number(
        delta
    ):
        absolute_delta = abs(
            float(delta)
        )

    return {
        "status": STATUS_NOT_EVALUATED,
        "reason": reason,
        "delta": delta,
        "absolute_delta": absolute_delta,
        "threshold": None,
        "unit": unit,
    }


def _make_not_configured_row(
    *,
    reason: str,
    delta: Any = None,
    threshold: Any = None,
    unit: Optional[str] = None,
) -> Dict[str, Any]:

    absolute_delta = None

    if _is_finite_number(
        delta
    ):
        absolute_delta = abs(
            float(delta)
        )

    return {
        "status": STATUS_NOT_CONFIGURED,
        "reason": reason,
        "delta": delta,
        "absolute_delta": absolute_delta,
        "threshold": threshold,
        "unit": unit,
    }


def _evaluate_feature(
    feature_name: str,
    snapshot_features: Dict[str, Any],
    threshold_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluate posture feature 1 ตัว
    """

    expected_unit = (
        FEATURE_SPECS[
            feature_name
        ][
            "unit"
        ]
    )

    feature = (
        snapshot_features.get(
            feature_name
        )
    )

    # --------------------------------------------------------
    # Feature ไม่มีใน snapshot
    # --------------------------------------------------------

    if not isinstance(
        feature,
        dict,
    ):
        return (
            _make_not_evaluated_row(
                reason=REASON_FEATURE_MISSING,
                unit=expected_unit,
            )
        )

    delta = feature.get(
        "delta"
    )

    # --------------------------------------------------------
    # Measurement validity
    # --------------------------------------------------------

    measurement_valid = (
        feature.get(
            "measurement_valid",
            False,
        )
    )

    if measurement_valid is not True:
        return (
            _make_not_evaluated_row(
                reason=REASON_MEASUREMENT_INVALID,
                delta=delta,
                unit=expected_unit,
            )
        )

    # --------------------------------------------------------
    # Baseline comparison eligibility
    # --------------------------------------------------------

    comparison_eligible = (
        feature.get(
            "baseline_comparison_eligible",
            False,
        )
    )

    if comparison_eligible is not True:
        return (
            _make_not_evaluated_row(
                reason=(
                    REASON_COMPARISON_NOT_ELIGIBLE
                ),
                delta=delta,
                unit=expected_unit,
            )
        )

    # --------------------------------------------------------
    # Delta validation
    # --------------------------------------------------------

    if not _is_finite_number(
        delta
    ):
        return (
            _make_not_evaluated_row(
                reason=REASON_DELTA_INVALID,
                delta=delta,
                unit=expected_unit,
            )
        )

    delta = float(
        delta
    )

    absolute_delta = abs(
        delta
    )

    # --------------------------------------------------------
    # Threshold config
    # --------------------------------------------------------

    threshold_result = (
        _get_feature_threshold(
            threshold_config,
            feature_name,
        )
    )

    if not threshold_result[
        "configured"
    ]:
        return (
            _make_not_configured_row(
                reason=threshold_result[
                    "reason"
                ],
                delta=delta,
                threshold=threshold_result[
                    "threshold"
                ],
                unit=threshold_result[
                    "unit"
                ]
                or expected_unit,
            )
        )

    threshold = (
        threshold_result[
            "threshold"
        ]
    )

    unit = (
        threshold_result[
            "unit"
        ]
    )

    # --------------------------------------------------------
    # Gate Decision
    # --------------------------------------------------------
    #
    # IMPORTANT:
    #
    # equal threshold
    #     → STABLE
    #
    # strictly above threshold
    #     → CHANGED
    # --------------------------------------------------------

    if absolute_delta > threshold:
        return {
            "status": STATUS_CHANGED,
            "reason": REASON_ABOVE_THRESHOLD,
            "delta": delta,
            "absolute_delta": absolute_delta,
            "threshold": threshold,
            "unit": unit,
        }

    return {
        "status": STATUS_STABLE,
        "reason": REASON_WITHIN_THRESHOLD,
        "delta": delta,
        "absolute_delta": absolute_delta,
        "threshold": threshold,
        "unit": unit,
    }


# ============================================================
# Overall Status
# ============================================================

def _derive_overall_status(
    feature_results: Dict[
        str,
        Dict[str, Any],
    ],
) -> str:
    """
    Priority ของ Overall Status:

        1. CHANGED
        2. NOT_CONFIGURED
        3. NOT_EVALUATED
        4. STABLE

    สำคัญ:
        STABLE ได้ก็ต่อเมื่อ posture feature
        ทั้ง 3 ตัวเป็น STABLE ครบเท่านั้น
    """

    statuses = [
        row.get(
            "status"
        )
        for row in feature_results.values()
    ]

    # --------------------------------------------------------
    # Safety guard
    # --------------------------------------------------------

    if (
        len(statuses)
        != len(POSTURE_FEATURES)
    ):
        return STATUS_NOT_EVALUATED

    # --------------------------------------------------------
    # Priority 1
    # --------------------------------------------------------

    if STATUS_CHANGED in statuses:
        return STATUS_CHANGED

    # --------------------------------------------------------
    # Priority 2
    # --------------------------------------------------------

    if (
        STATUS_NOT_CONFIGURED
        in statuses
    ):
        return STATUS_NOT_CONFIGURED

    # --------------------------------------------------------
    # Priority 3
    # --------------------------------------------------------

    if (
        STATUS_NOT_EVALUATED
        in statuses
    ):
        return STATUS_NOT_EVALUATED

    # --------------------------------------------------------
    # Priority 4
    # --------------------------------------------------------

    if all(
        status == STATUS_STABLE
        for status in statuses
    ):
        return STATUS_STABLE

    # Defensive fallback
    return STATUS_NOT_EVALUATED


# ============================================================
# Public Gate
# ============================================================

def evaluate_measurement_change(
    monitoring_snapshot: Dict[str, Any],
    threshold_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Main Measurement-Change Gate

    Parameters
    ----------
    monitoring_snapshot:
        Output จาก Session Monitoring

    threshold_config:
        Threshold configuration

    Returns
    -------
    dict

    ตัวอย่าง:

        {
            "gate_version": "1.0",

            "features": {
                "shoulder_tilt": {...},
                "neck_lateral_tilt": {...},
                "neck_flexion": {...},
            },

            "overall_status": "STABLE",

            "posture_assessment_status":
                "NOT_IMPLEMENTED",

            "risk_score_status":
                "NOT_IMPLEMENTED",

            "alert_status":
                "NOT_IMPLEMENTED",
        }
    """

    snapshot_features = {}

    if isinstance(
        monitoring_snapshot,
        dict,
    ):
        value = (
            monitoring_snapshot.get(
                "features"
            )
        )

        if isinstance(
            value,
            dict,
        ):
            snapshot_features = value

    # --------------------------------------------------------
    # Evaluate ONLY posture features
    # --------------------------------------------------------

    feature_results = {}

    for feature_name in POSTURE_FEATURES:
        feature_results[
            feature_name
        ] = _evaluate_feature(
            feature_name,
            snapshot_features,
            threshold_config,
        )

    overall_status = (
        _derive_overall_status(
            feature_results
        )
    )

    return {
        "gate_version": (
            MEASUREMENT_CHANGE_GATE_VERSION
        ),

        "contract_version": "1.0",

        "features": feature_results,

        "overall_status": overall_status,

        "summary": {
            "expected_features": list(
                POSTURE_FEATURES
            ),

            "evaluated_feature_count": (
                len(
                    feature_results
                )
            ),
        },

        # ----------------------------------------------------
        # Architecture Boundary
        # ----------------------------------------------------
        #
        # Change Gate ไม่ทำงานของ subsystem เหล่านี้
        # ----------------------------------------------------

        "posture_assessment_status": (
            "NOT_IMPLEMENTED"
        ),

        "risk_score_status": (
            "NOT_IMPLEMENTED"
        ),

        "alert_status": (
            "NOT_IMPLEMENTED"
        ),
    }


# ============================================================
# Legacy Experimental Threshold Derivation
# ============================================================
#
# IMPORTANT
# ---------
#
# ตัวนี้เก็บไว้รองรับ experiment / test เดิมเท่านั้น
#
# Final Measurement-Change Threshold ปัจจุบัน
# ไม่ได้ derive จาก stable P95 + changed P05 midpoint
#
# Final method:
#
#   Fresh Personal Baseline
#       ↓
#   Same Session
#       ↓
#   Stable Round 1 → P95
#   Stable Round 2 → P95
#   Stable Round 3 → P95
#       ↓
#   max(P95)
#       ↓
#   Candidate Threshold
#
# Intentional Changes ใช้ validate sensitivity
# ไม่ได้ใช้สร้าง threshold
# ============================================================

def _percentile(
    values: Iterable[float],
    percentile: float,
) -> float:
    """
    Linear-interpolated percentile

    ใช้ implementation ภายในเพื่อไม่ต้องเพิ่ม numpy dependency
    """

    sorted_values = sorted(
        float(value)
        for value in values
    )

    if not sorted_values:
        raise ValueError(
            "Cannot calculate percentile "
            "from empty values."
        )

    if len(sorted_values) == 1:
        return sorted_values[
            0
        ]

    position = (
        (len(sorted_values) - 1)
        * percentile
    )

    lower_index = int(
        math.floor(
            position
        )
    )

    upper_index = int(
        math.ceil(
            position
        )
    )

    if (
        lower_index
        == upper_index
    ):
        return sorted_values[
            lower_index
        ]

    fraction = (
        position
        - lower_index
    )

    lower_value = (
        sorted_values[
            lower_index
        ]
    )

    upper_value = (
        sorted_values[
            upper_index
        ]
    )

    return (
        lower_value
        + (
            upper_value
            - lower_value
        )
        * fraction
    )


def _clean_numeric_samples(
    values: Iterable[Any],
) -> List[float]:
    """
    เก็บเฉพาะ finite numeric samples

    Legacy experimental helper เท่านั้น
    """

    result = []

    for value in values:

        if not _is_finite_number(
            value
        ):
            continue

        result.append(
            abs(
                float(value)
            )
        )

    return result


def derive_threshold_from_samples(
    stable_samples: Iterable[Any],
    changed_samples: Iterable[Any],
    *,
    min_samples: int = 30,
) -> Dict[str, Any]:
    """
    LEGACY EXPERIMENT ONLY

    เดิมใช้:

        stable P95
        changed P05

    ถ้าแยกกันได้:

        threshold =
            midpoint(
                stable P95,
                changed P05
            )

    Method นี้ไม่ได้ใช้เป็น Final Threshold Method แล้ว
    แต่เก็บไว้เพื่อ:
        - รองรับ experiment เดิม
        - regression test
        - historical comparison
    """

    stable = (
        _clean_numeric_samples(
            stable_samples
        )
    )

    changed = (
        _clean_numeric_samples(
            changed_samples
        )
    )

    base_result = {
        "usage": (
            "LEGACY_EXPERIMENT_ONLY"
        ),

        "method": (
            "STABLE_P95_CHANGED_P05_MIDPOINT"
        ),

        "stable_sample_count": (
            len(stable)
        ),

        "changed_sample_count": (
            len(changed)
        ),

        "threshold": None,

        "stable_p95_abs_delta": None,

        "changed_p05_abs_delta": None,
    }

    if len(stable) < min_samples:
        return {
            **base_result,

            "status": (
                "INSUFFICIENT_STABLE_SAMPLES"
            ),
        }

    if len(changed) < min_samples:
        return {
            **base_result,

            "status": (
                "INSUFFICIENT_CHANGED_SAMPLES"
            ),
        }

    stable_p95 = (
        _percentile(
            stable,
            0.95,
        )
    )

    changed_p05 = (
        _percentile(
            changed,
            0.05,
        )
    )

    base_result[
        "stable_p95_abs_delta"
    ] = stable_p95

    base_result[
        "changed_p05_abs_delta"
    ] = changed_p05

    # --------------------------------------------------------
    # Distribution overlap
    # --------------------------------------------------------

    if stable_p95 >= changed_p05:
        return {
            **base_result,

            "status": (
                "NOT_SEPARABLE"
            ),

            "threshold": None,
        }

    threshold = (
        (
            stable_p95
            + changed_p05
        )
        / 2.0
    )

    return {
        **base_result,

        "status": "READY",

        "threshold": threshold,
    }


# ============================================================
# Aliases / Compatibility
# ============================================================

def load_measurement_change_thresholds(
    path: str | Path,
) -> Dict[str, Any]:
    """
    Compatibility alias
    """

    return load_threshold_config(
        path
    )