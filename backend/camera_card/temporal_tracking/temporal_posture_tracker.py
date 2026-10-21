from __future__ import annotations

import math
import time
from copy import deepcopy
from typing import Any, Mapping


# ============================================================
# CONTRACT
# ============================================================

TEMPORAL_CONTRACT_VERSION = "1.0"

EXPECTED_ASSESSMENT_CONTRACT_VERSION = "1.1"


# ============================================================
# REQUIRED FEATURES
# ============================================================

REQUIRED_FEATURES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
)


# ============================================================
# TEMPORAL FEATURE STATES
# ============================================================

TEMPORAL_ACTIVE = "ACTIVE"
TEMPORAL_NEUTRAL = "NEUTRAL"
TEMPORAL_NOT_EVALUATED = "NOT_EVALUATED"


# ============================================================
# TEMPORAL OVERALL STATES
# ============================================================

TEMPORAL_COMPLETE = "COMPLETE"
TEMPORAL_PARTIAL = "PARTIAL"
TEMPORAL_OVERALL_NOT_EVALUATED = "NOT_EVALUATED"


# ============================================================
# HELPERS
# ============================================================

def _finite_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    if not isinstance(
        value,
        (int, float),
    ):
        return None

    number = float(
        value
    )

    if not math.isfinite(
        number
    ):
        return None

    return number


def _as_mapping(
    value: Any,
) -> Mapping[str, Any] | None:

    if isinstance(
        value,
        Mapping,
    ):
        return value

    return None


# ============================================================
# INTERNAL FEATURE STATE
# ============================================================

def _empty_internal_state() -> dict[str, Any]:

    return {
        "factor": None,
        "started_at": None,
        "last_update_at": None,
    }


# ============================================================
# TEMPORAL TRACKER
# ============================================================

class TemporalPostureTracker:

    """
    Track continuous Current Posture Assessment factors.

    IMPORTANT
    ---------

    This class does NOT:

    - calculate posture classification
    - calculate Measurement-Change Gate
    - compare Personal Baseline
    - calculate Risk
    - calculate Alert
    - apply sustained-duration thresholds
    - suppress Assessment factors
    - modify Assessment interaction metadata

    It only records how long the SAME Assessment factor
    has remained continuously evaluable and active.
    """

    def __init__(self):

        self.reset()


    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
    ) -> None:

        self._feature_states = {
            feature_name: (
                _empty_internal_state()
            )

            for feature_name
            in REQUIRED_FEATURES
        }

        self._last_now = None


    # ========================================================
    # RESET ONE FEATURE
    # ========================================================

    def _reset_feature(
        self,
        feature_name: str,
    ) -> None:

        self._feature_states[
            feature_name
        ] = (
            _empty_internal_state()
        )


    # ========================================================
    # CLOCK VALIDATION
    # ========================================================

    def _resolve_now(
        self,
        now: float | None,
    ) -> float:

        if now is None:

            now = time.monotonic()

        timestamp = _finite_number(
            now
        )

        if timestamp is None:

            raise ValueError(
                "now must be a finite monotonic timestamp"
            )

        if (
            self._last_now is not None
            and
            timestamp
            <
            self._last_now
        ):

            raise ValueError(
                "now must not move backwards"
            )

        self._last_now = (
            timestamp
        )

        return timestamp


    # ========================================================
    # ASSESSMENT CONTRACT
    # ========================================================

    def _validate_assessment(
        self,
        assessment_result: Mapping[str, Any],
    ) -> str:

        if not isinstance(
            assessment_result,
            Mapping,
        ):

            raise ValueError(
                "assessment_result must be a mapping"
            )

        contract_version = (
            assessment_result.get(
                "contract_version"
            )
        )

        if (
            contract_version
            !=
            EXPECTED_ASSESSMENT_CONTRACT_VERSION
        ):

            raise ValueError(
                "Unsupported Current Posture Assessment "
                "contract_version: "
                f"{contract_version!r}"
            )

        return str(
            contract_version
        )


    # ========================================================
    # BUILD NOT EVALUATED FEATURE
    # ========================================================

    def _not_evaluated_result(
        self,
        *,
        feature_name: str,
        reason: str,
    ) -> dict[str, Any]:

        return {
            "feature": feature_name,

            "state": (
                TEMPORAL_NOT_EVALUATED
            ),

            "reason": reason,

            "factor": None,

            "continuous_seconds": None,

            "started_at": None,

            "last_update_at": None,

            "evaluable": False,

            "active": False,
        }


    # ========================================================
    # BUILD NEUTRAL FEATURE
    # ========================================================

    def _neutral_result(
        self,
        *,
        feature_name: str,
        now: float,
    ) -> dict[str, Any]:

        return {
            "feature": feature_name,

            "state": (
                TEMPORAL_NEUTRAL
            ),

            "reason": (
                "NO_POSTURE_FACTOR"
            ),

            "factor": None,

            "continuous_seconds": 0.0,

            "started_at": None,

            "last_update_at": now,

            "evaluable": True,

            "active": False,
        }


    # ========================================================
    # BUILD ACTIVE FEATURE
    # ========================================================

    def _active_result(
        self,
        *,
        feature_name: str,
        factor: str,
        now: float,
    ) -> dict[str, Any]:

        state = (
            self._feature_states[
                feature_name
            ]
        )

        current_factor = (
            state[
                "factor"
            ]
        )

        started_at = (
            state[
                "started_at"
            ]
        )

        # ----------------------------------------------------
        # New factor or direction/status changed.
        #
        # Example:
        #
        # LEFT_SHOULDER_HIGH
        #        ↓
        # RIGHT_SHOULDER_HIGH
        #
        # This is NOT continuous same-factor exposure.
        # Restart duration from 0.
        # ----------------------------------------------------

        if (
            current_factor
            !=
            factor
            or
            started_at is None
        ):

            started_at = now

            state[
                "factor"
            ] = factor

            state[
                "started_at"
            ] = started_at

        state[
            "last_update_at"
        ] = now

        continuous_seconds = max(
            0.0,
            now
            -
            started_at,
        )

        return {
            "feature": feature_name,

            "state": (
                TEMPORAL_ACTIVE
            ),

            "reason": (
                "POSTURE_FACTOR_ACTIVE"
            ),

            "factor": factor,

            "continuous_seconds": (
                continuous_seconds
            ),

            "started_at": (
                started_at
            ),

            "last_update_at": (
                now
            ),

            "evaluable": True,

            "active": True,
        }


    # ========================================================
    # UPDATE ONE FEATURE
    # ========================================================

    def _update_feature(
        self,
        *,
        feature_name: str,
        assessment_feature: Mapping[str, Any] | None,
        now: float,
    ) -> dict[str, Any]:

        # ----------------------------------------------------
        # Missing feature
        # ----------------------------------------------------

        if assessment_feature is None:

            self._reset_feature(
                feature_name
            )

            return (
                self._not_evaluated_result(
                    feature_name=(
                        feature_name
                    ),

                    reason=(
                        "ASSESSMENT_FEATURE_MISSING"
                    ),
                )
            )

        # ----------------------------------------------------
        # Feature not evaluable
        #
        # Conservative rule:
        #
        # continuity is reset because uninterrupted posture
        # cannot be proven during an unevaluable period.
        # ----------------------------------------------------

        if (
            assessment_feature.get(
                "evaluated"
            )
            is not True
        ):

            reason = (
                assessment_feature.get(
                    "reason"
                )
                or
                "ASSESSMENT_FEATURE_NOT_EVALUATED"
            )

            self._reset_feature(
                feature_name
            )

            return (
                self._not_evaluated_result(
                    feature_name=(
                        feature_name
                    ),

                    reason=str(
                        reason
                    ),
                )
            )

        # ----------------------------------------------------
        # Valid Assessment feature
        # ----------------------------------------------------

        status = (
            assessment_feature.get(
                "status"
            )
        )

        if status is None:

            self._reset_feature(
                feature_name
            )

            return (
                self._not_evaluated_result(
                    feature_name=(
                        feature_name
                    ),

                    reason=(
                        "ASSESSMENT_STATUS_MISSING"
                    ),
                )
            )

        is_factor = (
            assessment_feature.get(
                "is_posture_factor"
            )
            is True
        )

        # ----------------------------------------------------
        # Neutral
        # ----------------------------------------------------

        if not is_factor:

            self._reset_feature(
                feature_name
            )

            return (
                self._neutral_result(
                    feature_name=(
                        feature_name
                    ),

                    now=now,
                )
            )

        # ----------------------------------------------------
        # Active factor
        # ----------------------------------------------------

        return (
            self._active_result(
                feature_name=(
                    feature_name
                ),

                factor=str(
                    status
                ),

                now=now,
            )
        )


    # ========================================================
    # UPDATE
    # ========================================================

    def update(
        self,
        assessment_result: Mapping[str, Any],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:

        assessment_contract = (
            self._validate_assessment(
                assessment_result
            )
        )

        now_value = (
            self._resolve_now(
                now
            )
        )

        assessment_features = (
            _as_mapping(
                assessment_result.get(
                    "features"
                )
            )
        )

        if assessment_features is None:

            assessment_features = {}

        temporal_features = {}

        evaluable_count = 0
        not_evaluated_count = 0
        active_count = 0

        active_factors = []

        # ====================================================
        # FEATURE LOOP
        # ====================================================

        for feature_name in (
            REQUIRED_FEATURES
        ):

            assessment_feature = (
                _as_mapping(
                    assessment_features.get(
                        feature_name
                    )
                )
            )

            temporal_result = (
                self._update_feature(
                    feature_name=(
                        feature_name
                    ),

                    assessment_feature=(
                        assessment_feature
                    ),

                    now=(
                        now_value
                    ),
                )
            )

            temporal_features[
                feature_name
            ] = (
                temporal_result
            )

            if temporal_result[
                "evaluable"
            ]:

                evaluable_count += 1

            else:

                not_evaluated_count += 1

            if temporal_result[
                "active"
            ]:

                active_count += 1

                active_factors.append({
                    "feature": (
                        feature_name
                    ),

                    "factor": (
                        temporal_result[
                            "factor"
                        ]
                    ),

                    "continuous_seconds": (
                        temporal_result[
                            "continuous_seconds"
                        ]
                    ),
                })

        # ====================================================
        # OVERALL TEMPORAL STATUS
        # ====================================================

        if (
            evaluable_count
            ==
            len(
                REQUIRED_FEATURES
            )
        ):

            overall_status = (
                TEMPORAL_COMPLETE
            )

            overall_reason = (
                "ALL_REQUIRED_FEATURES_TRACKED"
            )

        elif evaluable_count > 0:

            overall_status = (
                TEMPORAL_PARTIAL
            )

            overall_reason = (
                "SOME_FEATURES_NOT_EVALUATED"
            )

        else:

            overall_status = (
                TEMPORAL_OVERALL_NOT_EVALUATED
            )

            overall_reason = (
                "NO_FEATURES_EVALUATED"
            )

        # ====================================================
        # OUTPUT
        # ====================================================

        return {
            "contract_version": (
                TEMPORAL_CONTRACT_VERSION
            ),

            "source_assessment_contract_version": (
                assessment_contract
            ),

            "assessment_timestamp": (
                assessment_result.get(
                    "timestamp"
                )
            ),

            "temporal_timestamp": (
                now_value
            ),

            "status": (
                overall_status
            ),

            "reason": (
                overall_reason
            ),

            "evaluable": (
                evaluable_count > 0
            ),

            "features": (
                temporal_features
            ),

            "evaluated_feature_count": (
                evaluable_count
            ),

            "not_evaluated_feature_count": (
                not_evaluated_count
            ),

            "active_factor_count": (
                active_count
            ),

            "active_factors": (
                active_factors
            ),

            # ------------------------------------------------
            # Explicit contract boundaries
            # ------------------------------------------------

            "policy": {
                "tracks_same_factor_continuity": True,

                "neutral_resets_duration": True,

                "factor_change_resets_duration": True,

                "not_evaluated_resets_duration": True,

                "uses_duration_threshold": False,

                "uses_baseline": False,

                "uses_measurement_change_gate": False,

                "uses_interaction_metadata": False,

                "calculates_risk": False,

                "calculates_alert": False,
            },

            # ------------------------------------------------
            # Reserved downstream layers
            # ------------------------------------------------

            "risk": None,

            "alert": None,
        }


    # ========================================================
    # SNAPSHOT
    # ========================================================

    def get_internal_state(
        self,
    ) -> dict[str, Any]:

        """
        Diagnostic copy only.

        Returning deepcopy prevents external code from
        mutating tracker state.
        """

        return deepcopy(
            self._feature_states
        )