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
# SUPPORTED RISK LEVELS
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


# ============================================================
# EVENT POLICY
# ============================================================

EVENT_TRIGGER_MINIMUM_LEVEL = (
    RISK_LEVEL_MODERATE
)

EVENT_TRIGGER_MINIMUM_RANK = (
    RISK_LEVEL_RANK[
        EVENT_TRIGGER_MINIMUM_LEVEL
    ]
)


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
# ERROR
# ============================================================

class RiskEventError(ValueError):
    pass


# ============================================================
# NUMERIC VALIDATION
# ============================================================

def _finite_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

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


# ============================================================
# TRACKER
# ============================================================

class RiskEventTracker:
    """
    Track meaningful PostGuard Risk Events over time.

    Input
    -----
    Risk Evaluation v1.2

    Responsibilities
    ----------------
    - Start event at MODERATE / HIGH
    - Continue same event while risk remains meaningful
    - Escalate MODERATE -> HIGH
    - De-escalate HIGH -> MODERATE
    - Resolve on LOW / NONE
    - Preserve event during temporary data gaps

    Does NOT
    --------
    - calculate posture
    - calculate Temporal duration
    - calculate Risk Level
    - calculate Full RULA
    - decide Alert
    - send Notification
    - persist database records
    """

    def __init__(self):
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

    # ========================================================
    # ACTIVE EVENT COPY
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
                "now must be a finite "
                "monotonic timestamp"
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
    # RISK CONTRACT VALIDATION
    # ========================================================

    def _validate_risk_result(
        self,
        risk_result: Mapping[str, Any],
    ) -> tuple[
        str,
        str | None,
    ]:

        if not isinstance(
            risk_result,
            Mapping,
        ):

            raise RiskEventError(
                "risk_result must be a mapping"
            )

        # ----------------------------------------------------
        # Contract version
        # ----------------------------------------------------

        contract_version = (
            risk_result.get(
                "risk_contract_version"
            )
        )

        if (
            contract_version
            !=
            EXPECTED_RISK_CONTRACT_VERSION
        ):

            raise RiskEventError(
                "Unsupported Risk Evaluation "
                "contract_version: "
                f"{contract_version!r}"
            )

        # ----------------------------------------------------
        # Evaluation status
        # ----------------------------------------------------

        status = (
            risk_result.get(
                "status"
            )
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

        risk_level = (
            risk_result.get(
                "risk_level"
            )
        )

        risk_level_available = (
            risk_result.get(
                "risk_level_available"
            )
        )

        # ====================================================
        # EVALUATED
        #
        # Must have:
        #
        # risk_level_available = True
        # risk_level = valid level
        # ====================================================

        if status == "EVALUATED":

            if (
                risk_level_available
                is not True
            ):

                raise RiskEventError(
                    "EVALUATED risk result must "
                    "have risk_level_available=True"
                )

            if (
                risk_level
                not in
                RISK_LEVEL_RANK
            ):

                raise RiskEventError(
                    "EVALUATED risk result has "
                    "invalid risk_level: "
                    f"{risk_level!r}"
                )

            return (
                str(status),
                str(risk_level),
            )

        # ====================================================
        # PARTIAL / NOT_EVALUATED
        #
        # Must have:
        #
        # risk_level_available = False
        # risk_level = None
        #
        # This prevents contradictory contracts such as:
        #
        # PARTIAL + risk_level_available=True
        # ====================================================

        if (
            risk_level_available
            is not False
        ):

            raise RiskEventError(
                "Incomplete Risk Evaluation must "
                "have risk_level_available=False"
            )

        if risk_level is not None:

            raise RiskEventError(
                "Incomplete Risk Evaluation must "
                "not provide risk_level"
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
    # START EVENT
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

            "last_evaluated_at_monotonic": (
                now
            ),

            "current_risk_level": (
                risk_level
            ),

            "peak_risk_level": (
                risk_level
            ),

            "active": True,
        }

        self._active_event = event

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
    ) -> dict[str, Any]:

        event_copy = (
            deepcopy(
                dict(event)
            )
            if event is not None
            else None
        )

        resolved_copy = (
            deepcopy(
                dict(resolved_event)
            )
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

            "status": (
                processing_status
            ),

            "reason": reason,

            "event_action": action,

            "source_risk_status": (
                risk_status
            ),

            "current_risk_level": (
                current_risk_level
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

            # Risk Event never decides alert.
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
        # DATA GAP
        #
        # PARTIAL / NOT_EVALUATED does NOT mean posture
        # returned to safe state.
        #
        # Therefore active event is preserved.
        # ====================================================

        if (
            risk_status
            !=
            "EVALUATED"
        ):

            previous_level = None

            if (
                self._active_event
                is not None
            ):

                previous_level = (
                    self._active_event[
                        "current_risk_level"
                    ]
                )

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

                risk_status=(
                    risk_status
                ),

                current_risk_level=None,

                previous_risk_level=(
                    previous_level
                ),

                event=(
                    self._active_event
                ),
            )

        # ====================================================
        # EVALUATED guarantees a real risk level
        # ====================================================

        assert risk_level is not None

        risk_rank = (
            RISK_LEVEL_RANK[
                risk_level
            ]
        )

        # ====================================================
        # NO ACTIVE EVENT
        # ====================================================

        if self._active_event is None:

            # ------------------------------------------------
            # NONE / LOW
            # ------------------------------------------------

            if (
                risk_rank
                <
                EVENT_TRIGGER_MINIMUM_RANK
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

                    risk_status=(
                        risk_status
                    ),

                    current_risk_level=(
                        risk_level
                    ),

                    previous_risk_level=None,

                    event=None,
                )

            # ------------------------------------------------
            # MODERATE / HIGH
            # ------------------------------------------------

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

                risk_status=(
                    risk_status
                ),

                current_risk_level=(
                    risk_level
                ),

                previous_risk_level=None,

                event=event,
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
        # RESOLVE EVENT
        #
        # MODERATE/HIGH -> LOW/NONE
        # ====================================================

        if (
            risk_rank
            <
            EVENT_TRIGGER_MINIMUM_RANK
        ):

            resolved_event = deepcopy(
                self._active_event
            )

            resolved_event[
                "active"
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
                "RISK_BELOW_EVENT_THRESHOLD"
            )

            self._active_event = None

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

                risk_status=(
                    risk_status
                ),

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
            )

        # ====================================================
        # EVENT REMAINS ACTIVE
        # ====================================================

        self._active_event[
            "current_risk_level"
        ] = risk_level

        self._active_event[
            "last_evaluated_at_monotonic"
        ] = now_value

        # ====================================================
        # ESCALATION
        # ====================================================

        if (
            risk_rank
            >
            previous_rank
        ):

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

            if (
                risk_rank
                >
                peak_rank
            ):

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

                risk_status=(
                    risk_status
                ),

                current_risk_level=(
                    risk_level
                ),

                previous_risk_level=(
                    previous_level
                ),

                event=(
                    self._active_event
                ),
            )

        # ====================================================
        # DE-ESCALATION
        # ====================================================

        if (
            risk_rank
            <
            previous_rank
        ):

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

                risk_status=(
                    risk_status
                ),

                current_risk_level=(
                    risk_level
                ),

                previous_risk_level=(
                    previous_level
                ),

                event=(
                    self._active_event
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

            risk_status=(
                risk_status
            ),

            current_risk_level=(
                risk_level
            ),

            previous_risk_level=(
                previous_level
            ),

            event=(
                self._active_event
            ),
        )