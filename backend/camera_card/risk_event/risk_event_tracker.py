from __future__ import annotations

import math
import time
from copy import deepcopy
from typing import Any, Mapping


# ============================================================
# CONTRACT
# ============================================================

RISK_EVENT_CONTRACT_VERSION = "1.0"
EXPECTED_RISK_CONTRACT_VERSION = "1.2"


# ============================================================
# RISK LEVELS
# ============================================================

RISK_LEVEL_NONE = "NONE"
RISK_LEVEL_LOW = "LOW"
RISK_LEVEL_MODERATE = "MODERATE"
RISK_LEVEL_HIGH = "HIGH"

RISK_LEVEL_RANK = {
    RISK_LEVEL_NONE: 0,
    RISK_LEVEL_LOW: 1,
    RISK_LEVEL_MODERATE: 2,
    RISK_LEVEL_HIGH: 3,
}

EVENT_TRIGGER_MINIMUM_LEVEL = RISK_LEVEL_MODERATE

EVENT_TRIGGER_MINIMUM_RANK = RISK_LEVEL_RANK[
    EVENT_TRIGGER_MINIMUM_LEVEL
]


# ============================================================
# EVENT ACTIONS
# ============================================================

EVENT_ACTION_NONE = "NONE"
EVENT_ACTION_STARTED = "STARTED"
EVENT_ACTION_UPDATED = "UPDATED"
EVENT_ACTION_ESCALATED = "ESCALATED"
EVENT_ACTION_DEESCALATED = "DEESCALATED"
EVENT_ACTION_RESOLVED = "RESOLVED"
EVENT_ACTION_DATA_GAP = "DATA_GAP"


# ============================================================
# PROCESSING STATUS
# ============================================================

EVENT_STATUS_EVALUATED = "EVALUATED"
EVENT_STATUS_PARTIAL = "PARTIAL"


# ============================================================
# DEFAULT PROTOTYPE UX POLICY
# ============================================================

DEFAULT_RECOVERY_GRACE_SECONDS = 5.0


# ============================================================
# ERROR
# ============================================================

class RiskEventError(ValueError):
    pass


# ============================================================
# NUMERIC HELPERS
# ============================================================

def _finite_number(
    value: Any,
) -> float | None:

    if value is None or isinstance(value, bool):
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


def _finite_non_negative_number(
    value: Any,
) -> float | None:

    number = _finite_number(value)

    if number is None:
        return None

    if number < 0.0:
        return None

    return number


# ============================================================
# TRACKER
# ============================================================

class RiskEventTracker:
    """
    Track meaningful PostGuard Risk Events over time.

    Risk Event starts at:
        MODERATE / HIGH

    Risk Event does NOT immediately resolve when one LOW/NONE
    sample appears.

    Instead:

        MODERATE/HIGH
            ↓
        LOW/NONE
            ↓
        recovery grace
            ↓
        still LOW/NONE after grace
            ↓
        RESOLVED

    If MODERATE/HIGH returns before grace expires,
    the same Risk Event continues.

    This prevents small posture movements / measurement noise
    from creating many new Risk Events and FIRST alerts.

    This module does NOT:
    - calculate posture
    - calculate Risk Level
    - decide notification
    - show popup
    - persist database records
    """

    def __init__(
        self,
        *,
        recovery_grace_seconds: float = (
            DEFAULT_RECOVERY_GRACE_SECONDS
        ),
    ) -> None:

        grace = _finite_non_negative_number(
            recovery_grace_seconds
        )

        if grace is None:
            raise RiskEventError(
                "recovery_grace_seconds must be "
                "a finite non-negative number"
            )

        self.recovery_grace_seconds = grace

        self.reset()

    # ========================================================
    # RESET
    # ========================================================

    def reset(self) -> None:

        self._active_event: (
            dict[str, Any]
            | None
        ) = None

        self._next_sequence = 1

        self._last_now: (
            float
            | None
        ) = None

        # Time at which continuous LOW/NONE recovery started.
        self._recovery_started_at: (
            float
            | None
        ) = None

    # ========================================================
    # STATE
    # ========================================================

    def get_active_event(
        self,
    ) -> dict[str, Any] | None:

        if self._active_event is None:
            return None

        return deepcopy(
            self._active_event
        )

    # ========================================================
    # CLOCK
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
            raise RiskEventError(
                "now must be a finite monotonic timestamp"
            )

        if (
            self._last_now is not None
            and
            timestamp < self._last_now
        ):
            raise RiskEventError(
                "now must not move backwards"
            )

        self._last_now = timestamp

        return timestamp

    # ========================================================
    # RISK CONTRACT
    # ========================================================

    def _validate_risk_result(
        self,
        risk_result: Mapping[str, Any],
    ) -> tuple[str, str | None]:

        if not isinstance(
            risk_result,
            Mapping,
        ):
            raise RiskEventError(
                "risk_result must be a mapping"
            )

        contract_version = risk_result.get(
            "risk_contract_version"
        )

        if (
            contract_version
            != EXPECTED_RISK_CONTRACT_VERSION
        ):
            raise RiskEventError(
                "Unsupported Risk Evaluation "
                "contract_version: "
                f"{contract_version!r}"
            )

        status = risk_result.get(
            "status"
        )

        if status not in (
            "EVALUATED",
            "PARTIAL",
            "NOT_EVALUATED",
        ):
            raise RiskEventError(
                "Unsupported Risk Evaluation "
                f"status: {status!r}"
            )

        risk_level = risk_result.get(
            "risk_level"
        )

        risk_level_available = risk_result.get(
            "risk_level_available"
        )

        if status == "EVALUATED":

            if risk_level_available is not True:
                raise RiskEventError(
                    "EVALUATED risk result must have "
                    "risk_level_available=True"
                )

            if risk_level not in RISK_LEVEL_RANK:
                raise RiskEventError(
                    "EVALUATED risk result has "
                    "invalid risk_level: "
                    f"{risk_level!r}"
                )

            return (
                str(status),
                str(risk_level),
            )

        if risk_level_available is not False:
            raise RiskEventError(
                "Incomplete Risk Evaluation must have "
                "risk_level_available=False"
            )

        if risk_level is not None:
            raise RiskEventError(
                "Incomplete Risk Evaluation must not "
                "provide risk_level"
            )

        return (
            str(status),
            None,
        )

    # ========================================================
    # EVENT ID
    # ========================================================

    def _new_runtime_event_id(
        self,
    ) -> str:

        event_id = (
            "risk-event-"
            f"{self._next_sequence:06d}"
        )

        self._next_sequence += 1

        return event_id

    # ========================================================
    # START
    # ========================================================

    def _start_event(
        self,
        *,
        risk_level: str,
        now: float,
    ) -> dict[str, Any]:

        event = {
            "runtime_event_id": (
                self._new_runtime_event_id()
            ),

            "started_at_monotonic": now,

            "last_evaluated_at_monotonic": now,

            "current_risk_level": risk_level,

            "peak_risk_level": risk_level,

            "active": True,

            "recovery_pending": False,

            "recovery_started_at_monotonic": None,
        }

        self._active_event = event

        self._recovery_started_at = None

        return event

    # ========================================================
    # OUTPUT
    # ========================================================

    def _build_output(
        self,
        *,
        processing_status: str,
        reason: str,
        action: str,
        risk_status: str,
        current_risk_level: str | None,
        previous_risk_level: str | None,
        event: Mapping[str, Any] | None,
        resolved_event: Mapping[str, Any] | None = None,
        observed_risk_level: str | None = None,
    ) -> dict[str, Any]:

        event_copy = (
            deepcopy(dict(event))
            if event is not None
            else None
        )

        resolved_copy = (
            deepcopy(dict(resolved_event))
            if resolved_event is not None
            else None
        )

        return {
            "risk_event_contract_version": (
                RISK_EVENT_CONTRACT_VERSION
            ),

            "source_risk_contract_version": (
                EXPECTED_RISK_CONTRACT_VERSION
            ),

            "status": processing_status,

            "reason": reason,

            "event_action": action,

            "source_risk_status": (
                risk_status
            ),

            # Risk Level represented by the active Event.
            "current_risk_level": (
                current_risk_level
            ),

            # Actual evaluated Risk Level for this sample.
            "observed_risk_level": (
                observed_risk_level
            ),

            "previous_risk_level": (
                previous_risk_level
            ),

            "event_active": (
                event is not None
            ),

            "event": event_copy,

            "resolved_event": (
                resolved_copy
            ),

            # This layer never decides notifications.
            "alert": None,

            "policy": {
                "type": (
                    "POSTGUARD_PROTOTYPE_ENGINEERING_POLICY"
                ),

                "event_trigger_minimum_level": (
                    EVENT_TRIGGER_MINIMUM_LEVEL
                ),

                "event_levels": [
                    RISK_LEVEL_MODERATE,
                    RISK_LEVEL_HIGH,
                ],

                "non_event_levels": [
                    RISK_LEVEL_NONE,
                    RISK_LEVEL_LOW,
                ],

                "recovery_grace_seconds": (
                    self.recovery_grace_seconds
                ),

                "partial_data_resolves_event": False,

                "creates_alert": False,

                "is_rula_action_level": False,

                "is_clinical_event_definition": False,

                "runtime_event_id_is_persistent_db_id": False,
            },
        }

    # ========================================================
    # UPDATE
    # ========================================================

    def update(
        self,
        risk_result: Mapping[str, Any],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:

        (
            risk_status,
            risk_level,
        ) = self._validate_risk_result(
            risk_result
        )

        now_value = self._resolve_now(
            now
        )

        # ====================================================
        # PARTIAL / NOT_EVALUATED
        #
        # Missing data is NOT evidence of recovery.
        #
        # Cancel recovery countdown because safe posture was
        # not continuously observed.
        # ====================================================

        if risk_status != "EVALUATED":

            previous_level = None

            if self._active_event is not None:

                previous_level = (
                    self._active_event[
                        "current_risk_level"
                    ]
                )

                self._recovery_started_at = None

                self._active_event[
                    "recovery_pending"
                ] = False

                self._active_event[
                    "recovery_started_at_monotonic"
                ] = None

            return self._build_output(
                processing_status=(
                    EVENT_STATUS_PARTIAL
                ),
                reason=(
                    "RISK_EVALUATION_UNAVAILABLE"
                ),
                action=(
                    EVENT_ACTION_DATA_GAP
                ),
                risk_status=risk_status,
                current_risk_level=(
                    previous_level
                ),
                previous_risk_level=(
                    previous_level
                ),
                event=self._active_event,
                observed_risk_level=None,
            )

        assert risk_level is not None

        risk_rank = RISK_LEVEL_RANK[
            risk_level
        ]

        # ====================================================
        # NO ACTIVE EVENT
        # ====================================================

        if self._active_event is None:

            self._recovery_started_at = None

            if (
                risk_rank
                < EVENT_TRIGGER_MINIMUM_RANK
            ):
                return self._build_output(
                    processing_status=(
                        EVENT_STATUS_EVALUATED
                    ),
                    reason=(
                        "RISK_BELOW_EVENT_THRESHOLD"
                    ),
                    action=(
                        EVENT_ACTION_NONE
                    ),
                    risk_status=risk_status,
                    current_risk_level=(
                        risk_level
                    ),
                    previous_risk_level=None,
                    event=None,
                    observed_risk_level=(
                        risk_level
                    ),
                )

            event = self._start_event(
                risk_level=risk_level,
                now=now_value,
            )

            return self._build_output(
                processing_status=(
                    EVENT_STATUS_EVALUATED
                ),
                reason=(
                    "RISK_EVENT_STARTED"
                ),
                action=(
                    EVENT_ACTION_STARTED
                ),
                risk_status=risk_status,
                current_risk_level=(
                    risk_level
                ),
                previous_risk_level=None,
                event=event,
                observed_risk_level=(
                    risk_level
                ),
            )

        # ====================================================
        # ACTIVE EVENT
        # ====================================================

        previous_level = (
            self._active_event[
                "current_risk_level"
            ]
        )

        previous_rank = (
            RISK_LEVEL_RANK[
                previous_level
            ]
        )

        # ====================================================
        # LOW / NONE
        #
        # Do NOT immediately resolve.
        # Require continuous recovery for grace period.
        # ====================================================

        if (
            risk_rank
            < EVENT_TRIGGER_MINIMUM_RANK
        ):

            if (
                self._recovery_started_at
                is None
            ):
                self._recovery_started_at = (
                    now_value
                )

            recovery_elapsed = (
                now_value
                -
                self._recovery_started_at
            )

            self._active_event[
                "recovery_pending"
            ] = True

            self._active_event[
                "recovery_started_at_monotonic"
            ] = (
                self._recovery_started_at
            )

            self._active_event[
                "last_evaluated_at_monotonic"
            ] = now_value

            # ------------------------------------------------
            # Still inside recovery grace.
            #
            # DATA_GAP action is intentionally used here as a
            # notification-suppression transition compatible
            # with Alert Policy v1.0.
            #
            # Data collection continues normally.
            # ------------------------------------------------

            if (
                recovery_elapsed
                <
                self.recovery_grace_seconds
            ):
                return self._build_output(
                    processing_status=(
                        EVENT_STATUS_EVALUATED
                    ),
                    reason=(
                        "RISK_EVENT_RECOVERY_GRACE"
                    ),
                    action=(
                        EVENT_ACTION_DATA_GAP
                    ),
                    risk_status=risk_status,

                    # Keep Event's meaningful risk level.
                    current_risk_level=(
                        previous_level
                    ),

                    previous_risk_level=(
                        previous_level
                    ),

                    event=self._active_event,

                    # Actual sample is still exposed.
                    observed_risk_level=(
                        risk_level
                    ),
                )

            # ------------------------------------------------
            # Continuous safe/lower-risk posture lasted long
            # enough -> resolve.
            # ------------------------------------------------

            resolved_event = deepcopy(
                self._active_event
            )

            resolved_event[
                "active"
            ] = False

            resolved_event[
                "recovery_pending"
            ] = False

            resolved_event[
                "resolved_at_monotonic"
            ] = now_value

            resolved_event[
                "resolved_to_risk_level"
            ] = risk_level

            resolved_event[
                "resolution_reason"
            ] = (
                "RISK_BELOW_EVENT_THRESHOLD_"
                "FOR_RECOVERY_GRACE"
            )

            resolved_event[
                "recovery_duration_seconds"
            ] = recovery_elapsed

            self._active_event = None
            self._recovery_started_at = None

            return self._build_output(
                processing_status=(
                    EVENT_STATUS_EVALUATED
                ),
                reason=(
                    "RISK_EVENT_RESOLVED"
                ),
                action=(
                    EVENT_ACTION_RESOLVED
                ),
                risk_status=risk_status,
                current_risk_level=(
                    risk_level
                ),
                previous_risk_level=(
                    previous_level
                ),
                event=None,
                resolved_event=(
                    resolved_event
                ),
                observed_risk_level=(
                    risk_level
                ),
            )

        # ====================================================
        # MODERATE / HIGH RETURNED
        #
        # Recovery attempt is cancelled.
        # Same Event continues.
        # ====================================================

        self._recovery_started_at = None

        self._active_event[
            "recovery_pending"
        ] = False

        self._active_event[
            "recovery_started_at_monotonic"
        ] = None

        self._active_event[
            "current_risk_level"
        ] = risk_level

        self._active_event[
            "last_evaluated_at_monotonic"
        ] = now_value

        # ====================================================
        # ESCALATION
        # ====================================================

        if risk_rank > previous_rank:

            peak_level = (
                self._active_event[
                    "peak_risk_level"
                ]
            )

            peak_rank = (
                RISK_LEVEL_RANK[
                    peak_level
                ]
            )

            if risk_rank > peak_rank:
                self._active_event[
                    "peak_risk_level"
                ] = risk_level

            return self._build_output(
                processing_status=(
                    EVENT_STATUS_EVALUATED
                ),
                reason=(
                    "RISK_EVENT_ESCALATED"
                ),
                action=(
                    EVENT_ACTION_ESCALATED
                ),
                risk_status=risk_status,
                current_risk_level=(
                    risk_level
                ),
                previous_risk_level=(
                    previous_level
                ),
                event=self._active_event,
                observed_risk_level=(
                    risk_level
                ),
            )

        # ====================================================
        # DE-ESCALATION
        # HIGH -> MODERATE
        # ====================================================

        if risk_rank < previous_rank:

            return self._build_output(
                processing_status=(
                    EVENT_STATUS_EVALUATED
                ),
                reason=(
                    "RISK_EVENT_DEESCALATED"
                ),
                action=(
                    EVENT_ACTION_DEESCALATED
                ),
                risk_status=risk_status,
                current_risk_level=(
                    risk_level
                ),
                previous_risk_level=(
                    previous_level
                ),
                event=self._active_event,
                observed_risk_level=(
                    risk_level
                ),
            )

        # ====================================================
        # SAME LEVEL
        # ====================================================

        return self._build_output(
            processing_status=(
                EVENT_STATUS_EVALUATED
            ),
            reason=(
                "RISK_EVENT_CONTINUES"
            ),
            action=(
                EVENT_ACTION_UPDATED
            ),
            risk_status=risk_status,
            current_risk_level=(
                risk_level
            ),
            previous_risk_level=(
                previous_level
            ),
            event=self._active_event,
            observed_risk_level=(
                risk_level
            ),
        )