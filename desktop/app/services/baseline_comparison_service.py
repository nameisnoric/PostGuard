from __future__ import annotations

import math
from typing import Any, Mapping


BASELINE_COMPARISON_CONTRACT_VERSION = "1.0"
EXPECTED_DETECTION_CONTRACT_VERSION = "1.0"

STATUS_EVALUATED = "EVALUATED"
STATUS_NOT_EVALUATED = "NOT_EVALUATED"

GATE_STABLE = "STABLE"
GATE_CHANGED = "CHANGED"
GATE_NOT_CONFIGURED = "NOT_CONFIGURED"
GATE_NOT_EVALUATED = "NOT_EVALUATED"


FEATURE_CONFIG = {
    "shoulder_tilt": {
        "baseline_field": "shoulder_angle",
        "sd_field": "shoulder_tilt_sd",
        "unit": "deg",
    },
    "neck_lateral_tilt": {
        "baseline_field": "lateral_tilt_baseline",
        "sd_field": "neck_lateral_tilt_sd",
        "unit": "deg",
    },
    "neck_flexion": {
        "baseline_field": "neck_flexion_baseline",
        "sd_field": "neck_flexion_sd",
        "unit": "deg",
    },
}


def _finite_number(
    value: Any,
) -> float | None:
    """
    Convert an int/float to a finite float.

    bool is intentionally rejected because bool is a subclass of int
    in Python and must not be accepted as a posture measurement.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if not isinstance(value, (int, float)):
        return None

    number = float(value)

    if not math.isfinite(number):
        return None

    return number


def _extract_current_feature(
    detection_result: Mapping[str, Any],
    feature_name: str,
) -> tuple[
    bool,
    float | None,
    str | None,
    str,
]:
    """
    Read one feature from Detection Contract 1.0.

    This function only reads the current measured value.
    It does not modify, normalize or compensate the value.
    """

    features = detection_result.get("features")

    if not isinstance(features, Mapping):
        return (
            False,
            None,
            None,
            "FEATURES_MISSING",
        )

    feature = features.get(feature_name)

    if not isinstance(feature, Mapping):
        return (
            False,
            None,
            None,
            "FEATURE_MISSING",
        )

    unit = feature.get("unit")

    if feature.get("valid") is not True:
        return (
            False,
            None,
            unit,
            feature.get("reason") or "FEATURE_INVALID",
        )

    expected_unit = FEATURE_CONFIG[feature_name]["unit"]

    if unit != expected_unit:
        return (
            False,
            None,
            unit,
            "INVALID_UNIT",
        )

    value = _finite_number(
        feature.get("value")
    )

    if value is None:
        return (
            False,
            None,
            unit,
            "INVALID_VALUE",
        )

    return (
        True,
        value,
        unit,
        "OK",
    )


def _extract_baseline(
    baseline_data: Mapping[str, Any] | None,
    feature_name: str,
) -> tuple[
    float | None,
    float | None,
    str,
]:
    """
    Read the personal baseline and optional baseline SD.

    Missing baseline is treated as unavailable comparison data.
    It does NOT make the current posture measurement invalid.
    """

    if not isinstance(baseline_data, Mapping):
        return (
            None,
            None,
            "BASELINE_MISSING",
        )

    config = FEATURE_CONFIG[feature_name]

    baseline_value = _finite_number(
        baseline_data.get(
            config["baseline_field"]
        )
    )

    if baseline_value is None:
        return (
            None,
            None,
            "BASELINE_VALUE_MISSING",
        )

    sd_value = _finite_number(
        baseline_data.get(
            config["sd_field"]
        )
    )

    return (
        baseline_value,
        sd_value,
        "OK",
    )


def _extract_gate_threshold(
    gate_rules: Mapping[str, Any] | None,
    feature_name: str,
) -> float | None:
    """
    Read an explicitly configured Measurement-Change Gate threshold.

    IMPORTANT:
    PostGuard does not currently define validated production thresholds
    for this gate.

    Therefore this module intentionally has NO default threshold.

    A threshold is only used when the caller explicitly supplies one.
    """

    if not isinstance(gate_rules, Mapping):
        return None

    features = gate_rules.get("features")

    if not isinstance(features, Mapping):
        return None

    feature_rule = features.get(feature_name)

    if not isinstance(feature_rule, Mapping):
        return None

    threshold = _finite_number(
        feature_rule.get(
            "change_threshold_deg"
        )
    )

    if threshold is None:
        return None

    if threshold < 0.0:
        raise ValueError(
            f"change_threshold_deg for {feature_name} "
            "must be >= 0"
        )

    return threshold


def compare_detection_to_baseline(
    detection_result: Mapping[str, Any],
    baseline_data: Mapping[str, Any] | None,
    *,
    gate_rules: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Compare current posture measurements with Personal Baseline.

    This layer has two responsibilities:

    1. Baseline comparison
       - current
       - baseline
       - delta
       - absolute_delta

    2. Measurement-Change Gate
       - STABLE
       - CHANGED
       - NOT_CONFIGURED
       - NOT_EVALUATED

    IMPORTANT:

    STABLE does NOT mean safe.
    CHANGED does NOT mean risky.

    This result must not replace Current Posture Assessment.
    """

    if not isinstance(detection_result, Mapping):
        raise ValueError(
            "detection_result must be a mapping"
        )

    detection_contract = detection_result.get(
        "contract_version"
    )

    if (
        detection_contract
        != EXPECTED_DETECTION_CONTRACT_VERSION
    ):
        raise ValueError(
            "Unsupported Detection contract_version: "
            f"{detection_contract!r}"
        )

    feature_results: dict[str, dict[str, Any]] = {}

    evaluated_count = 0

    for feature_name in FEATURE_CONFIG:
        (
            current_valid,
            current_value,
            unit,
            current_reason,
        ) = _extract_current_feature(
            detection_result,
            feature_name,
        )

        if not current_valid:
            feature_results[feature_name] = {
                "feature": feature_name,
                "status": STATUS_NOT_EVALUATED,
                "reason": current_reason,
                "current": None,
                "baseline": None,
                "delta": None,
                "absolute_delta": None,
                "baseline_sd": None,
                "unit": unit,
                "gate": {
                    "state": GATE_NOT_EVALUATED,
                    "changed": None,
                    "threshold": None,
                },
            }
            continue

        (
            baseline_value,
            baseline_sd,
            baseline_reason,
        ) = _extract_baseline(
            baseline_data,
            feature_name,
        )

        if baseline_value is None:
            feature_results[feature_name] = {
                "feature": feature_name,
                "status": STATUS_NOT_EVALUATED,
                "reason": baseline_reason,
                "current": current_value,
                "baseline": None,
                "delta": None,
                "absolute_delta": None,
                "baseline_sd": baseline_sd,
                "unit": unit,
                "gate": {
                    "state": GATE_NOT_EVALUATED,
                    "changed": None,
                    "threshold": None,
                },
            }
            continue

        delta = (
            current_value
            -
            baseline_value
        )

        absolute_delta = abs(delta)

        threshold = _extract_gate_threshold(
            gate_rules,
            feature_name,
        )

        if threshold is None:
            gate_state = GATE_NOT_CONFIGURED
            changed = None

        else:
            # Exact boundary is treated as STABLE.
            # CHANGED requires strictly greater difference.
            changed = (
                absolute_delta > threshold
            )

            gate_state = (
                GATE_CHANGED
                if changed
                else GATE_STABLE
            )

        feature_results[feature_name] = {
            "feature": feature_name,
            "status": STATUS_EVALUATED,
            "reason": "OK",
            "current": current_value,
            "baseline": baseline_value,
            "delta": delta,
            "absolute_delta": absolute_delta,
            "baseline_sd": baseline_sd,
            "unit": unit,
            "gate": {
                "state": gate_state,
                "changed": changed,
                "threshold": threshold,
            },
        }

        evaluated_count += 1

    all_evaluated = (
        evaluated_count
        ==
        len(FEATURE_CONFIG)
    )

    any_changed = any(
        result.get("gate", {}).get("state")
        == GATE_CHANGED
        for result in feature_results.values()
    )

    any_gate_configured = any(
        result.get("gate", {}).get("state")
        in (GATE_STABLE, GATE_CHANGED)
        for result in feature_results.values()
    )

    if not all_evaluated:
        overall_status = "PARTIAL"

    else:
        overall_status = "COMPLETE"

    if not any_gate_configured:
        overall_gate_state = GATE_NOT_CONFIGURED

    elif any_changed:
        overall_gate_state = GATE_CHANGED

    else:
        overall_gate_state = GATE_STABLE

    return {
        "contract_version": (
            BASELINE_COMPARISON_CONTRACT_VERSION
        ),
        "source_detection_contract_version": (
            detection_contract
        ),
        "status": overall_status,
        "features": feature_results,
        "gate": {
            "state": overall_gate_state,
            "configured": any_gate_configured,
            "has_changed_feature": (
                any_changed
                if any_gate_configured
                else None
            ),
        },
        "semantics": {
            "stable_means_safe": False,
            "changed_means_risky": False,
            "blocks_posture_assessment": False,
            "modifies_detection_measurements": False,
        },
    }