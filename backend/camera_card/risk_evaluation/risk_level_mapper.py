from __future__ import annotations

from typing import Any, Dict, Mapping


RISK_LEVEL_POLICY_VERSION = "1.0"

RISK_LEVEL_NONE = "NONE"
RISK_LEVEL_LOW = "LOW"
RISK_LEVEL_MODERATE = "MODERATE"
RISK_LEVEL_HIGH = "HIGH"


def map_prototype_risk_level(
    *,
    evaluation_status: str,
    evidence_groups: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Map completed PostGuard evidence into a prototype risk level.

    Important
    ---------
    This is a PostGuard Prototype Engineering Policy.

    It is NOT:
    - a Full RULA score,
    - a RULA Action Level,
    - a clinical diagnosis,
    - an alert decision.

    Mapping
    -------
    Incomplete data:
        risk level unavailable

    EVALUATED + 0 active groups:
        NONE

    EVALUATED + 1 active group + no static evidence:
        LOW

    EVALUATED + 1 active group + static evidence:
        MODERATE

    EVALUATED + >=2 active groups + no static evidence:
        MODERATE

    EVALUATED + >=2 active groups + >=1 static group:
        HIGH
    """

    if evaluation_status != "EVALUATED":
        return {
            "policy_version": RISK_LEVEL_POLICY_VERSION,
            "policy_type": "POSTGUARD_PROTOTYPE_ENGINEERING_POLICY",
            "available": False,
            "level": None,
            "reason": "INCOMPLETE_EVALUATION",
            "active_group_count": None,
            "active_groups": [],
            "static_group_count": None,
            "static_groups": [],
        }

    active_groups = []
    static_groups = []

    for group_name, group_result in evidence_groups.items():
        if not isinstance(group_result, Mapping):
            continue

        if group_result.get("active") is not True:
            continue

        active_groups.append(group_name)

        if group_result.get("static_duration_met") is True:
            static_groups.append(group_name)

    active_group_count = len(active_groups)
    static_group_count = len(static_groups)

    if active_group_count == 0:
        level = RISK_LEVEL_NONE
        reason = "NO_ACTIVE_EVIDENCE_GROUP"

    elif (
        active_group_count == 1
        and static_group_count == 0
    ):
        level = RISK_LEVEL_LOW
        reason = "SINGLE_ACTIVE_GROUP_WITHOUT_STATIC_DURATION"

    elif (
        active_group_count == 1
        and static_group_count >= 1
    ):
        level = RISK_LEVEL_MODERATE
        reason = "SINGLE_ACTIVE_GROUP_WITH_STATIC_DURATION"

    elif (
        active_group_count >= 2
        and static_group_count == 0
    ):
        level = RISK_LEVEL_MODERATE
        reason = "MULTIPLE_ACTIVE_GROUPS_WITHOUT_STATIC_DURATION"

    else:
        level = RISK_LEVEL_HIGH
        reason = "MULTIPLE_ACTIVE_GROUPS_WITH_STATIC_DURATION"

    return {
        "policy_version": RISK_LEVEL_POLICY_VERSION,
        "policy_type": "POSTGUARD_PROTOTYPE_ENGINEERING_POLICY",
        "available": True,
        "level": level,
        "reason": reason,
        "active_group_count": active_group_count,
        "active_groups": active_groups,
        "static_group_count": static_group_count,
        "static_groups": static_groups,
    }