"""PostGuard prototype risk evaluation from assessment and temporal evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .risk_level_mapper import map_prototype_risk_level


RISK_CONTRACT_VERSION = "1.2"
STATIC_DURATION_SECONDS = 60.0
FEATURES = ("shoulder_tilt", "neck_lateral_tilt", "neck_flexion")
GROUPS = {
    "LATERAL_ASYMMETRY": ("shoulder_tilt", "neck_lateral_tilt"),
    "NECK_SAGITTAL": ("neck_flexion",),
}
PROTOTYPE_RISK_VALUES = {"NONE": 0.0, "LOW": 1.0, "MODERATE": 2.0, "HIGH": 3.0}


class RiskEvaluationError(ValueError):
    """Raised when an upstream contract cannot be evaluated safely."""


def _contract(source: Mapping[str, Any], current_key: str, legacy_key: str, expected):
    version = source.get(current_key, source.get(legacy_key))
    if version not in expected:
        raise RiskEvaluationError(f"Unsupported {legacy_key}: {version!r}")
    return version


def _assessment_feature(row: Any) -> tuple[bool, str | None]:
    if not isinstance(row, Mapping):
        return False, None
    if "evaluated" in row:
        evaluated = row.get("evaluated") is True
        factor = str(row.get("status")) if row.get("is_posture_factor") is True else None
        return evaluated, factor
    evaluated = row.get("valid") is True and row.get("status") == "EVALUATED"
    factor = row.get("factor") if evaluated else None
    return evaluated, str(factor) if factor is not None else None


def _temporal_feature(row: Any) -> tuple[bool, bool, str | None, float | None]:
    if not isinstance(row, Mapping):
        return False, False, None, None
    if "evaluable" in row:
        evaluable = row.get("evaluable") is True
        active = row.get("active") is True
    else:
        state = row.get("state")
        evaluable = state in {"ACTIVE", "NEUTRAL"}
        active = state == "ACTIVE"
    factor = row.get("factor") if active else None
    seconds = row.get("continuous_seconds")
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(seconds)
        or seconds < 0
    ):
        seconds = None
    return evaluable, active, str(factor) if factor is not None else None, seconds


def evaluate_risk(
    assessment_result: Mapping[str, Any],
    temporal_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Combine consistent posture and duration evidence into a prototype level."""
    if not isinstance(assessment_result, Mapping) or not isinstance(temporal_result, Mapping):
        raise RiskEvaluationError("assessment_result and temporal_result must be mappings")

    assessment_contract = _contract(
        assessment_result, "contract_version", "assessment_contract_version", {"1.0", "1.1"}
    )
    temporal_contract = _contract(
        temporal_result, "contract_version", "temporal_contract_version", {"1.0"}
    )
    assessment_features = assessment_result.get("features", {})
    temporal_features = temporal_result.get("features", {})
    if not isinstance(assessment_features, Mapping) or not isinstance(temporal_features, Mapping):
        raise RiskEvaluationError("features must be mappings")

    feature_results: dict[str, dict[str, Any]] = {}
    ready_count = 0
    assessment_evaluable_count = 0
    rula_evidence = []
    postguard_evidence = []
    temporal_evidence = []

    for name in FEATURES:
        assessment_evaluable, assessment_factor = _assessment_feature(
            assessment_features.get(name)
        )
        temporal_evaluable, temporal_active, temporal_factor, seconds = _temporal_feature(
            temporal_features.get(name)
        )
        if assessment_evaluable:
            assessment_evaluable_count += 1

        if not assessment_evaluable:
            consistency = "ASSESSMENT_NOT_EVALUATED"
        elif not temporal_evaluable:
            consistency = "TEMPORAL_UNAVAILABLE"
        elif assessment_factor != temporal_factor:
            consistency = "FACTOR_MISMATCH"
        else:
            consistency = "READY"
            ready_count += 1

        ready_factor = assessment_factor if consistency == "READY" else None
        ready_seconds = seconds if consistency == "READY" and ready_factor is not None else (
            0.0 if consistency == "READY" else None
        )
        feature_results[name] = {
            "feature": name,
            "factor": ready_factor,
            "continuous_seconds": ready_seconds,
            "active": ready_factor is not None,
            "consistency": {"status": consistency},
        }

        if ready_factor is None:
            continue
        evidence_item = {
            "feature": name,
            "factor": ready_factor,
            "continuous_seconds": ready_seconds,
        }
        if name == "shoulder_tilt":
            postguard_evidence.append({
                **evidence_item,
                "type": "SHOULDER_ASYMMETRY",
                "source": "POSTGUARD_POSTURE_PROTOTYPE",
                "rula_equivalent": False,
            })
        elif name == "neck_lateral_tilt":
            rula_evidence.append({
                **evidence_item,
                "type": "NECK_SIDE_BENDING",
                "source": "RULA_DERIVED",
            })
        else:
            rula_evidence.append({
                **evidence_item,
                "type": "NECK_FLEXION_EXTENSION",
                "source": "RULA_DERIVED",
            })
        if ready_seconds is not None and ready_seconds >= STATIC_DURATION_SECONDS:
            temporal_evidence.append({
                **evidence_item,
                "type": "STATIC_DURATION",
                "source": "POSTGUARD_TEMPORAL_PROTOTYPE",
                "threshold_seconds": STATIC_DURATION_SECONDS,
            })

    if ready_count == len(FEATURES):
        status = "EVALUATED"
    elif assessment_evaluable_count == 0:
        status = "NOT_EVALUATED"
    else:
        status = "PARTIAL"

    evidence_groups = {}
    for group_name, names in GROUPS.items():
        active_features = [
            name for name in names if feature_results[name]["active"]
        ]
        static_features = [
            name for name in active_features
            if (feature_results[name]["continuous_seconds"] or 0.0) >= STATIC_DURATION_SECONDS
        ]
        evidence_groups[group_name] = {
            "active": bool(active_features),
            "active_features": active_features,
            "static_duration_met": bool(static_features),
            "static_features": static_features,
        }

    mapping = map_prototype_risk_level(
        evaluation_status=status,
        evidence_groups=evidence_groups,
    )
    level = mapping["level"] if mapping["available"] else None

    return {
        "risk_contract_version": RISK_CONTRACT_VERSION,
        "assessment_contract_version": assessment_contract,
        "temporal_contract_version": temporal_contract,
        "status": status,
        "feature_results": feature_results,
        "evidence": {
            "rula_derived": rula_evidence,
            "postguard_specific": postguard_evidence,
            "temporal": temporal_evidence,
        },
        "evidence_groups": evidence_groups,
        "interaction_policy": {
            "automatic_score_addition": False,
            "coupled_features_share_evidence_group": True,
        },
        "risk_level_mapping_enabled": True,
        "risk_level_mapping": mapping,
        "risk_level_available": mapping["available"],
        "risk_level": level,
        "prototype_score": PROTOTYPE_RISK_VALUES.get(level),
        "risk_score": None,
        "full_rula": {"supported": False, "score": None, "action_level": None},
        "risk_event": None,
        "alert": None,
    }
