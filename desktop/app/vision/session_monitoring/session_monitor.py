import math
from collections.abc import Mapping
from typing import Any


# ============================================================
# Session Monitoring Contract
# ============================================================

MONITORING_VERSION = "1.0"

EXPECTED_DETECTION_CONTRACT_VERSION = "1.0"

EXPECTED_FEATURE_STATUS = "validated_prototype"

EXPECTED_CONTEXT_STATE = "VALID"


# ============================================================
# Feature Specification
#
# DetectionPipeline feature
#       ↓
# PersonalBaseline database column
# ============================================================

FEATURE_SPECS = {
    "shoulder_tilt": {
        "label": "Shoulder Tilt",
        "unit": "deg",
        "baseline_key": "shoulder_angle",
    },

    "neck_lateral_tilt": {
        "label": "Neck Lateral Tilt",
        "unit": "deg",
        "baseline_key": "lateral_tilt_baseline",
    },

    "neck_flexion": {
        "label": "Neck Flexion",
        "unit": "deg",
        "baseline_key": "neck_flexion_baseline",
    },

    "eye_distance": {
        "label": "Relative Eye Distance",
        "unit": "px",
        "baseline_key": "eye_distance_baseline_px",
    },
}


# ============================================================
# Numeric Helper
# ============================================================

def _finite_number(
    value: Any,
) -> float | None:
    """
    Convert a numeric value to float only when it is usable.

    Important:
    - None is invalid
    - bool is invalid
    - NaN is invalid
    - +inf / -inf are invalid
    """

    if value is None:
        return None

    # bool is a subclass of int in Python.
    # We do not want True -> 1.0 or False -> 0.0.
    if isinstance(value, bool):
        return None

    try:
        numeric_value = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        numeric_value
    ):
        return None

    return numeric_value


# ============================================================
# Mapping / ORM Reader
# ============================================================

def _read_value(
    source: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Read a value from either:

    1. dict / Mapping
    2. SQLAlchemy ORM object

    This allows the Session Monitor core to work with:
    - Unit-test dictionaries
    - Real PostureSession objects
    - Real PersonalBaseline objects
    """

    if isinstance(
        source,
        Mapping,
    ):
        return source.get(
            key,
            default,
        )

    return getattr(
        source,
        key,
        default,
    )


# ============================================================
# Positive Integer Validation
# ============================================================

def _positive_int(
    value: Any,
    field_name: str,
) -> int:
    """
    Validate identifiers such as:
    - session_id
    - baseline_id
    - camera_id
    - user_id
    """

    if (
        isinstance(value, bool)
        or
        not isinstance(value, int)
        or
        value <= 0
    ):
        raise ValueError(
            f"{field_name} must be a positive integer"
        )

    return value


# ============================================================
# Session / Baseline Relationship Validation
# ============================================================

def _validate_session_baseline_relationship(
    session: Any,
    baseline: Any,
) -> dict[str, Any]:
    """
    Ensure that the baseline being used is exactly the baseline
    attached to this Session.

    Rules:

    1 Session = 1 Personal Baseline

    Session.baseline_id must match Baseline.baseline_id.

    Session.camera_id must match Baseline.camera_id.

    If user_id is available on both objects, it must also match.

    Monitoring snapshot is created only for RUNNING sessions.
    """

    session_id = _positive_int(
        _read_value(
            session,
            "session_id",
        ),
        "session.session_id",
    )

    session_baseline_id = _positive_int(
        _read_value(
            session,
            "baseline_id",
        ),
        "session.baseline_id",
    )

    baseline_id = _positive_int(
        _read_value(
            baseline,
            "baseline_id",
        ),
        "baseline.baseline_id",
    )

    session_camera_id = _positive_int(
        _read_value(
            session,
            "camera_id",
        ),
        "session.camera_id",
    )

    baseline_camera_id = _positive_int(
        _read_value(
            baseline,
            "camera_id",
        ),
        "baseline.camera_id",
    )

    session_status = str(
        _read_value(
            session,
            "status",
            "UNKNOWN",
        )
    ).upper()

    if session_status != "RUNNING":
        raise ValueError(
            "Session Monitoring requires a RUNNING session"
        )

    if (
        session_baseline_id
        !=
        baseline_id
    ):
        raise ValueError(
            "Loaded baseline_id does not match "
            "session.baseline_id"
        )

    if (
        session_camera_id
        !=
        baseline_camera_id
    ):
        raise ValueError(
            "Session and baseline belong "
            "to different cameras"
        )

    # --------------------------------------------------------
    # User ownership
    #
    # Both real SQLAlchemy models have user_id.
    # Unit tests may intentionally omit it.
    # --------------------------------------------------------

    session_user_id = _read_value(
        session,
        "user_id",
        None,
    )

    baseline_user_id = _read_value(
        baseline,
        "user_id",
        None,
    )

    if (
        session_user_id is not None
        and
        baseline_user_id is not None
    ):
        session_user_id = _positive_int(
            session_user_id,
            "session.user_id",
        )

        baseline_user_id = _positive_int(
            baseline_user_id,
            "baseline.user_id",
        )

        if (
            session_user_id
            !=
            baseline_user_id
        ):
            raise ValueError(
                "Session and baseline belong "
                "to different users"
            )

    return {
        "session_id": session_id,
        "baseline_id": baseline_id,
        "camera_id": session_camera_id,
        "user_id": session_user_id,
        "status": session_status,
    }


# ============================================================
# Context Reader
# ============================================================

def _read_context(
    detection_result: Mapping,
) -> dict[str, Any]:
    """
    Read Context Filter output.

    DetectionPipeline 1.0 normally provides:

    {
        "state": "VALID",
        "allow_posture_evaluation": True,
        "reason": "...",
        ...
    }

    Malformed or missing context is never treated as valid.
    """

    context = detection_result.get(
        "context"
    )

    if not isinstance(
        context,
        Mapping,
    ):
        return {
            "state": "UNKNOWN",
            "allow_posture_evaluation": False,
            "reason": "CONTEXT_MISSING_OR_INVALID",
        }

    state = context.get(
        "state",
        "UNKNOWN",
    )

    allow_posture_evaluation = (
        context.get(
            "allow_posture_evaluation"
        )
        is True
    )

    reason = context.get(
        "reason"
    )

    return {
        "state": str(
            state
        ).upper(),
        "allow_posture_evaluation": (
            allow_posture_evaluation
        ),
        "reason": reason,
    }


# ============================================================
# Detection Contract Validation
# ============================================================

def _validate_detection_contract(
    detection_result: Any,
) -> Mapping:
    """
    Validate DetectionPipeline contract before using its output.
    """

    if not isinstance(
        detection_result,
        Mapping,
    ):
        raise ValueError(
            "detection_result must be a mapping"
        )

    contract_version = (
        detection_result.get(
            "contract_version"
        )
    )

    if (
        contract_version
        !=
        EXPECTED_DETECTION_CONTRACT_VERSION
    ):
        raise ValueError(
            "Unsupported DetectionPipeline "
            f"contract_version: {contract_version!r}"
        )

    features = detection_result.get(
        "features"
    )

    if not isinstance(
        features,
        Mapping,
    ):
        raise ValueError(
            "DetectionPipeline features "
            "must be a mapping"
        )

    return features


# ============================================================
# Feature Reader
# ============================================================

def _read_detection_feature(
    features: Mapping,
    feature_name: str,
    expected_unit: str,
) -> dict[str, Any]:
    """
    Read one feature from DetectionPipeline contract 1.0.

    Expected shape:

    {
        "valid": True,
        "value": 1.23,
        "unit": "deg",
        "reason": "OK",
        "status": "validated_prototype"
    }

    Only validated_prototype features are eligible for
    Session Monitoring downstream rules in v1.
    """

    raw_feature = features.get(
        feature_name
    )

    if not isinstance(
        raw_feature,
        Mapping,
    ):
        return {
            "value": None,
            "valid": False,
            "quality_status": "FAIL",
            "feature_status": None,
            "unit": expected_unit,
            "reason": "FEATURE_MISSING_OR_INVALID",
        }

    feature_valid = (
        raw_feature.get(
            "valid"
        )
        is True
    )

    value = _finite_number(
        raw_feature.get(
            "value"
        )
    )

    unit = raw_feature.get(
        "unit"
    )

    feature_status = (
        raw_feature.get(
            "status"
        )
    )

    reason = raw_feature.get(
        "reason"
    )

    # --------------------------------------------------------
    # Detection feature says invalid
    # --------------------------------------------------------

    if not feature_valid:
        return {
            "value": None,
            "valid": False,
            "quality_status": "FAIL",
            "feature_status": feature_status,
            "unit": unit,
            "reason": (
                reason
                or
                "FEATURE_REPORTED_INVALID"
            ),
        }

    # --------------------------------------------------------
    # Invalid numeric value
    # --------------------------------------------------------

    if value is None:
        return {
            "value": None,
            "valid": False,
            "quality_status": "FAIL",
            "feature_status": feature_status,
            "unit": unit,
            "reason": "INVALID_NUMERIC_VALUE",
        }

    # --------------------------------------------------------
    # Unit mismatch
    # --------------------------------------------------------

    if unit != expected_unit:
        return {
            "value": None,
            "valid": False,
            "quality_status": "FAIL",
            "feature_status": feature_status,
            "unit": unit,
            "reason": (
                f"UNEXPECTED_UNIT:"
                f"{unit!r}"
            ),
        }

    # --------------------------------------------------------
    # Feature capability
    #
    # Candidate / Experimental / Diagnostic features
    # are NOT silently promoted into Session Monitoring Core.
    # --------------------------------------------------------

    if (
        feature_status
        !=
        EXPECTED_FEATURE_STATUS
    ):
        return {
            "value": value,
            "valid": False,
            "quality_status": "NOT_APPROVED",
            "feature_status": feature_status,
            "unit": unit,
            "reason": (
                "FEATURE_STATUS_NOT_APPROVED"
            ),
        }

    return {
        "value": value,
        "valid": True,
        "quality_status": "PASS",
        "feature_status": feature_status,
        "unit": unit,
        "reason": (
            reason
            or
            "OK"
        ),
    }


# ============================================================
# Session Monitoring Snapshot
# ============================================================

def build_session_monitoring_snapshot(
    session: Any,
    baseline: Any,
    detection_result: Any,
) -> dict[str, Any]:
    """
    Build one Session Monitoring snapshot.

    This function DOES:

    - Validate Session/Baseline relationship
    - Validate DetectionPipeline contract
    - Read Context Filter result
    - Read the four approved Personal Baseline features
    - Calculate Baseline / Current / Delta
    - Determine measurement validity
    - Determine baseline-comparison eligibility

    This function DOES NOT:

    - Decide CHANGED / STABLE
    - Apply Measurement-Change Gate thresholds
    - Calculate RULA
    - Calculate PostGuard Risk Score
    - Create Risk Event
    - Create Alert
    - Modify Session
    - Modify Personal Baseline
    """

    # ========================================================
    # Session / Baseline
    # ========================================================

    session_info = (
        _validate_session_baseline_relationship(
            session=session,
            baseline=baseline,
        )
    )

    # ========================================================
    # Detection Contract
    # ========================================================

    features = (
        _validate_detection_contract(
            detection_result
        )
    )

    # ========================================================
    # Context
    # ========================================================

    context = _read_context(
        detection_result
    )

    context_valid = (
        context["state"]
        ==
        EXPECTED_CONTEXT_STATE
        and
        context[
            "allow_posture_evaluation"
        ]
        is True
    )

    # ========================================================
    # Feature Rows
    # ========================================================

    feature_rows: dict[
        str,
        dict[str, Any],
    ] = {}

    for (
        feature_name,
        spec,
    ) in FEATURE_SPECS.items():

        # ----------------------------------------------------
        # Baseline
        # ----------------------------------------------------

        baseline_value = (
            _finite_number(
                _read_value(
                    baseline,
                    spec[
                        "baseline_key"
                    ],
                )
            )
        )

        # ----------------------------------------------------
        # Current Detection
        # ----------------------------------------------------

        current = (
            _read_detection_feature(
                features=features,
                feature_name=feature_name,
                expected_unit=spec[
                    "unit"
                ],
            )
        )

        current_value = (
            current[
                "value"
            ]
        )

        # ----------------------------------------------------
        # Measurement Validity
        #
        # Important:
        # This does NOT depend on the Baseline.
        # ----------------------------------------------------

        measurement_valid = (
            current[
                "valid"
            ]
            and
            context_valid
        )

        # ----------------------------------------------------
        # Delta
        #
        # Delta can be calculated whenever both numbers exist.
        # It is still observation data until quality/context
        # says the comparison can be used downstream.
        # ----------------------------------------------------

        delta = None

        if (
            baseline_value
            is not None
            and
            current_value
            is not None
        ):
            delta = (
                current_value
                -
                baseline_value
            )

        # ----------------------------------------------------
        # Baseline Comparison Eligibility
        # ----------------------------------------------------

        baseline_comparison_eligible = (
            measurement_valid
            and
            baseline_value
            is not None
            and
            delta
            is not None
        )

        # ----------------------------------------------------
        # Posture Assessment Eligibility
        #
        # v1 intentionally does not claim that all technically
        # valid measurements are anatomically validated for a
        # RULA/PostGuard posture assessment.
        # ----------------------------------------------------

        posture_assessment_eligible = False

        # ----------------------------------------------------
        # Monitoring Status
        # ----------------------------------------------------

        if baseline_value is None:
            status = "NOT_EVALUATED"

            reason = (
                "BASELINE_VALUE_MISSING_OR_INVALID"
            )

        elif current_value is None:
            status = "NOT_EVALUATED"

            reason = current[
                "reason"
            ]

        elif not measurement_valid:
            status = "OBSERVATION_ONLY"

            if not context_valid:
                reason = (
                    "CONTEXT_NOT_VALID"
                )

            else:
                reason = current[
                    "reason"
                ]

        else:
            status = (
                "READY_FOR_BASELINE_COMPARISON"
            )

            reason = None

        feature_rows[
            feature_name
        ] = {
            "label": spec[
                "label"
            ],

            "unit": spec[
                "unit"
            ],

            "baseline": (
                baseline_value
            ),

            "current": (
                current_value
            ),

            "delta": (
                delta
            ),

            "measurement_valid": (
                measurement_valid
            ),

            "baseline_comparison_eligible": (
                baseline_comparison_eligible
            ),

            "posture_assessment_eligible": (
                posture_assessment_eligible
            ),

            "quality_status": (
                current[
                    "quality_status"
                ]
            ),

            "feature_status": (
                current[
                    "feature_status"
                ]
            ),

            "status": status,

            "reason": reason,
        }

    # ========================================================
    # Final Monitoring Snapshot
    # ========================================================

    return {
        "monitoring_version": (
            MONITORING_VERSION
        ),

        "detection_contract_version": (
            detection_result[
                "contract_version"
            ]
        ),

        "timestamp": (
            detection_result.get(
                "timestamp"
            )
        ),

        "session": (
            session_info
        ),

        "context": (
            context
        ),

        "features": (
            feature_rows
        ),

        # ----------------------------------------------------
        # Explicitly NOT implemented in Monitoring v1
        # ----------------------------------------------------

        "measurement_change_gate_status": (
            "NOT_IMPLEMENTED"
        ),

        "posture_assessment_status": (
            "NOT_IMPLEMENTED"
        ),

        "risk_score_status": (
            "NOT_IMPLEMENTED"
        ),

        "risk_event_status": (
            "NOT_IMPLEMENTED"
        ),

        "alert_status": (
            "NOT_IMPLEMENTED"
        ),
    }
