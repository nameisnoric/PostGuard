from __future__ import annotations

import math
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


# ============================================================
# CONTRACT
# ============================================================

ALERT_POLICY_CONTRACT_VERSION = "1.0"

EXPECTED_RISK_EVENT_CONTRACT_VERSION = "1.0"


# ============================================================
# RISK LEVELS
# ============================================================

RISK_LEVEL_MODERATE = "MODERATE"
RISK_LEVEL_HIGH = "HIGH"

SUPPORTED_EVENT_LEVELS = (
    RISK_LEVEL_MODERATE,
    RISK_LEVEL_HIGH,
)


# ============================================================
# RISK EVENT ACTIONS
# ============================================================

EVENT_ACTION_NONE = "NONE"
EVENT_ACTION_STARTED = "STARTED"
EVENT_ACTION_UPDATED = "UPDATED"
EVENT_ACTION_ESCALATED = "ESCALATED"
EVENT_ACTION_DEESCALATED = "DEESCALATED"
EVENT_ACTION_RESOLVED = "RESOLVED"
EVENT_ACTION_DATA_GAP = "DATA_GAP"

SUPPORTED_EVENT_ACTIONS = (
    EVENT_ACTION_NONE,
    EVENT_ACTION_STARTED,
    EVENT_ACTION_UPDATED,
    EVENT_ACTION_ESCALATED,
    EVENT_ACTION_DEESCALATED,
    EVENT_ACTION_RESOLVED,
    EVENT_ACTION_DATA_GAP,
)


# ============================================================
# ALERT DECISIONS
# ============================================================

ALERT_DECISION_ALERT = "ALERT"

ALERT_DECISION_NO_ALERT = "NO_ALERT"

ALERT_DECISION_SUPPRESSED = "SUPPRESSED"

ALERT_DECISION_DATA_GAP = "DATA_GAP"


# ============================================================
# ALERT TYPES
# ============================================================

ALERT_TYPE_FIRST = "FIRST"

ALERT_TYPE_REPEAT = "REPEAT"

ALERT_TYPE_ESCALATION = "ESCALATION"

ALERT_TYPE_RESOLUTION = "RESOLUTION"


# ============================================================
# PROCESSING STATUS
# ============================================================

ALERT_STATUS_EVALUATED = "EVALUATED"

ALERT_STATUS_PARTIAL = "PARTIAL"


# ============================================================
# ERROR
# ============================================================

class AlertPolicyError(ValueError):
    pass


# ============================================================
# NUMERIC VALIDATION
# ============================================================

def _finite_non_negative_number(
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

    if number < 0.0:
        return None

    return number


# ============================================================
# CONFIG
#
# IMPORTANT:
#
# No timing default is provided here intentionally.
#
# The caller must explicitly define:
#
# - first alert delay
# - repeat cooldown
# - escalation behavior
# - resolution behavior
#
# Therefore this module does not silently invent a clinical
# or ergonomic timing standard.
# ============================================================

@dataclass(frozen=True)
class AlertPolicyConfig:

    moderate_first_alert_delay_seconds: float

    high_first_alert_delay_seconds: float

    moderate_repeat_cooldown_seconds: float

    high_repeat_cooldown_seconds: float

    escalation_bypasses_cooldown: bool

    notify_on_resolution: bool

    def __post_init__(self):

        numeric_fields = {
            "moderate_first_alert_delay_seconds": (
                self.moderate_first_alert_delay_seconds
            ),

            "high_first_alert_delay_seconds": (
                self.high_first_alert_delay_seconds
            ),

            "moderate_repeat_cooldown_seconds": (
                self.moderate_repeat_cooldown_seconds
            ),

            "high_repeat_cooldown_seconds": (
                self.high_repeat_cooldown_seconds
            ),
        }

        for (
            field_name,
            value,
        ) in numeric_fields.items():

            if (
                _finite_non_negative_number(
                    value
                )
                is None
            ):

                raise AlertPolicyError(
                    f"{field_name} must be a finite "
                    "non-negative number"
                )

        if not isinstance(
            self.escalation_bypasses_cooldown,
            bool,
        ):

            raise AlertPolicyError(
                "escalation_bypasses_cooldown "
                "must be bool"
            )

        if not isinstance(
            self.notify_on_resolution,
            bool,
        ):

            raise AlertPolicyError(
                "notify_on_resolution must be bool"
            )


# ============================================================
# ALERT POLICY
# ============================================================

class AlertPolicy:
    """
    PostGuard Alert Policy v1.0.

    Input
    -----
    Risk Event v1.0

    Responsibilities
    ----------------
    - Decide when the first alert should occur.
    - Prevent alerts every frame.
    - Apply repeat cooldown.
    - Apply separate MODERATE/HIGH cooldown.
    - Handle escalation.
    - Preserve alert state across DATA_GAP.
    - Optionally generate resolution alert decision.
    - Keep one state per active Risk Event.

    Does NOT
    --------
    - detect posture,
    - classify posture,
    - calculate duration,
    - calculate Risk Level,
    - create Risk Event,
    - send notifications,
    - play sounds,
    - show UI popups,
    - write database records.

    Output is an alert DECISION only.

    Notification remains a downstream responsibility.
    """

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        config: AlertPolicyConfig,
    ):

        if not isinstance(
            config,
            AlertPolicyConfig,
        ):

            raise AlertPolicyError(
                "config must be AlertPolicyConfig"
            )

        self.config = config

        self.reset()

    # ========================================================
    # RESET
    # ========================================================

    def reset(self) -> None:

        self._active_state: (
            dict[str, Any]
            | None
        ) = None

        self._last_now: (
            float
            | None
        ) = None

    # ========================================================
    # STATE COPY
    # ========================================================

    def get_active_state(
        self,
    ) -> dict[str, Any] | None:

        if self._active_state is None:
            return None

        return deepcopy(
            self._active_state
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

        timestamp = (
            _finite_non_negative_number(
                now
            )
        )

        if timestamp is None:

            raise AlertPolicyError(
                "now must be a finite "
                "non-negative monotonic timestamp"
            )

        if (
            self._last_now is not None
            and
            timestamp
            <
            self._last_now
        ):

            raise AlertPolicyError(
                "now must not move backwards"
            )

        self._last_now = timestamp

        return timestamp

    # ========================================================
    # FIRST ALERT DELAY
    # ========================================================

    def _first_alert_delay(
        self,
        risk_level: str,
    ) -> float:

        if (
            risk_level
            ==
            RISK_LEVEL_MODERATE
        ):

            return float(
                self.config
                .moderate_first_alert_delay_seconds
            )

        if (
            risk_level
            ==
            RISK_LEVEL_HIGH
        ):

            return float(
                self.config
                .high_first_alert_delay_seconds
            )

        raise AlertPolicyError(
            "Unsupported event risk level "
            f"for first alert: {risk_level!r}"
        )

    # ========================================================
    # REPEAT COOLDOWN
    # ========================================================

    def _repeat_cooldown(
        self,
        risk_level: str,
    ) -> float:

        if (
            risk_level
            ==
            RISK_LEVEL_MODERATE
        ):

            return float(
                self.config
                .moderate_repeat_cooldown_seconds
            )

        if (
            risk_level
            ==
            RISK_LEVEL_HIGH
        ):

            return float(
                self.config
                .high_repeat_cooldown_seconds
            )

        raise AlertPolicyError(
            "Unsupported event risk level "
            f"for cooldown: {risk_level!r}"
        )

    # ========================================================
    # EVENT READER
    # ========================================================

    def _read_event(
        self,
        value: Any,
    ) -> dict[str, Any] | None:

        if value is None:
            return None

        if not isinstance(
            value,
            Mapping,
        ):

            raise AlertPolicyError(
                "Risk Event event must be a mapping"
            )

        event_id = value.get(
            "runtime_event_id"
        )

        if (
            not isinstance(
                event_id,
                str,
            )
            or
            not event_id
        ):

            raise AlertPolicyError(
                "Risk Event runtime_event_id "
                "must be a non-empty string"
            )

        started_at = (
            _finite_non_negative_number(
                value.get(
                    "started_at_monotonic"
                )
            )
        )

        if started_at is None:

            raise AlertPolicyError(
                "Risk Event started_at_monotonic "
                "must be a finite non-negative number"
            )

        current_level = value.get(
            "current_risk_level"
        )

        if (
            current_level
            not in
            SUPPORTED_EVENT_LEVELS
        ):

            raise AlertPolicyError(
                "Active Risk Event has unsupported "
                f"current_risk_level: "
                f"{current_level!r}"
            )

        return {
            "runtime_event_id": (
                event_id
            ),

            "started_at_monotonic": (
                started_at
            ),

            "current_risk_level": (
                str(
                    current_level
                )
            ),

            "peak_risk_level": (
                value.get(
                    "peak_risk_level"
                )
            ),
        }

    # ========================================================
    # RESOLVED EVENT READER
    # ========================================================

    def _read_resolved_event(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if not isinstance(
            value,
            Mapping,
        ):

            raise AlertPolicyError(
                "RESOLVED Risk Event must provide "
                "resolved_event mapping"
            )

        event_id = value.get(
            "runtime_event_id"
        )

        if (
            not isinstance(
                event_id,
                str,
            )
            or
            not event_id
        ):

            raise AlertPolicyError(
                "resolved_event.runtime_event_id "
                "must be a non-empty string"
            )

        return {
            "runtime_event_id": (
                event_id
            ),

            "current_risk_level": (
                value.get(
                    "current_risk_level"
                )
            ),

            "peak_risk_level": (
                value.get(
                    "peak_risk_level"
                )
            ),

            "resolved_to_risk_level": (
                value.get(
                    "resolved_to_risk_level"
                )
            ),
        }

    # ========================================================
    # CONTRACT VALIDATION
    # ========================================================

    def _validate_risk_event_result(
        self,
        risk_event_result: Mapping[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(
            risk_event_result,
            Mapping,
        ):

            raise AlertPolicyError(
                "risk_event_result must be a mapping"
            )

        contract_version = (
            risk_event_result.get(
                "risk_event_contract_version"
            )
        )

        if (
            contract_version
            !=
            EXPECTED_RISK_EVENT_CONTRACT_VERSION
        ):

            raise AlertPolicyError(
                "Unsupported Risk Event "
                "contract_version: "
                f"{contract_version!r}"
            )

        action = (
            risk_event_result.get(
                "event_action"
            )
        )

        if (
            action
            not in
            SUPPORTED_EVENT_ACTIONS
        ):

            raise AlertPolicyError(
                "Unsupported Risk Event action: "
                f"{action!r}"
            )

        event_active = (
            risk_event_result.get(
                "event_active"
            )
        )

        if not isinstance(
            event_active,
            bool,
        ):

            raise AlertPolicyError(
                "event_active must be bool"
            )

        event = None

        resolved_event = None

        # ====================================================
        # ACTIVE EVENT ACTIONS
        # ====================================================

        if action in (
            EVENT_ACTION_STARTED,
            EVENT_ACTION_UPDATED,
            EVENT_ACTION_ESCALATED,
            EVENT_ACTION_DEESCALATED,
        ):

            if event_active is not True:

                raise AlertPolicyError(
                    f"{action} must have "
                    "event_active=True"
                )

            event = self._read_event(
                risk_event_result.get(
                    "event"
                )
            )

            if event is None:

                raise AlertPolicyError(
                    f"{action} must provide event"
                )

        # ====================================================
        # DATA GAP
        #
        # Can occur with or without active event.
        # ====================================================

        elif (
            action
            ==
            EVENT_ACTION_DATA_GAP
        ):

            if event_active:

                event = self._read_event(
                    risk_event_result.get(
                        "event"
                    )
                )

                if event is None:

                    raise AlertPolicyError(
                        "DATA_GAP with active event "
                        "must provide event"
                    )

            else:

                if (
                    risk_event_result.get(
                        "event"
                    )
                    is not None
                ):

                    raise AlertPolicyError(
                        "DATA_GAP without active event "
                        "must not provide event"
                    )

        # ====================================================
        # RESOLVED
        # ====================================================

        elif (
            action
            ==
            EVENT_ACTION_RESOLVED
        ):

            if event_active is not False:

                raise AlertPolicyError(
                    "RESOLVED must have "
                    "event_active=False"
                )

            if (
                risk_event_result.get(
                    "event"
                )
                is not None
            ):

                raise AlertPolicyError(
                    "RESOLVED must not provide "
                    "active event"
                )

            resolved_event = (
                self._read_resolved_event(
                    risk_event_result.get(
                        "resolved_event"
                    )
                )
            )

        # ====================================================
        # NONE
        # ====================================================

        elif (
            action
            ==
            EVENT_ACTION_NONE
        ):

            if event_active is not False:

                raise AlertPolicyError(
                    "NONE action must have "
                    "event_active=False"
                )

            if (
                risk_event_result.get(
                    "event"
                )
                is not None
            ):

                raise AlertPolicyError(
                    "NONE action must not "
                    "provide active event"
                )

        return {
            "action": (
                str(action)
            ),

            "event_active": (
                event_active
            ),

            "event": (
                event
            ),

            "resolved_event": (
                resolved_event
            ),

            "source_status": (
                risk_event_result.get(
                    "status"
                )
            ),
        }

    # ========================================================
    # CREATE ALERT STATE
    # ========================================================

    def _create_state(
        self,
        event: Mapping[str, Any],
    ) -> dict[str, Any]:

        state = {
            "event_id": (
                event[
                    "runtime_event_id"
                ]
            ),

            "event_started_at_monotonic": (
                float(
                    event[
                        "started_at_monotonic"
                    ]
                )
            ),

            "first_alert_sent": False,

            "first_alert_at_monotonic": None,

            "last_alert_at_monotonic": None,

            "last_alerted_risk_level": None,

            "alert_count": 0,
        }

        self._active_state = state

        return state

    # ========================================================
    # EVENT ID CONSISTENCY
    # ========================================================

    def _require_same_event(
        self,
        event: Mapping[str, Any],
    ) -> dict[str, Any]:

        if self._active_state is None:

            raise AlertPolicyError(
                "Alert Policy has no active state "
                "for this Risk Event"
            )

        event_id = (
            event[
                "runtime_event_id"
            ]
        )

        if (
            self._active_state[
                "event_id"
            ]
            !=
            event_id
        ):

            raise AlertPolicyError(
                "Risk Event changed without "
                "RESOLVED transition"
            )

        return self._active_state

    # ========================================================
    # RECORD ALERT
    # ========================================================

    def _record_alert(
        self,
        *,
        now: float,
        risk_level: str | None,
    ) -> None:

        if self._active_state is None:

            raise AlertPolicyError(
                "Cannot record alert without "
                "active alert state"
            )

        if (
            self._active_state[
                "first_alert_sent"
            ]
            is False
        ):

            self._active_state[
                "first_alert_sent"
            ] = True

            self._active_state[
                "first_alert_at_monotonic"
            ] = now

        self._active_state[
            "last_alert_at_monotonic"
        ] = now

        self._active_state[
            "last_alerted_risk_level"
        ] = risk_level

        self._active_state[
            "alert_count"
        ] += 1

    # ========================================================
    # STATE SNAPSHOT
    # ========================================================

    def _state_snapshot(
        self,
    ) -> dict[str, Any] | None:

        if self._active_state is None:
            return None

        return deepcopy(
            self._active_state
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    def _build_output(
        self,
        *,
        status: str,
        decision: str,
        reason: str,
        should_notify: bool,
        alert_type: str | None,
        event_id: str | None,
        current_risk_level: str | None,
        now: float,
        state_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        if state_snapshot is None:
            state_snapshot = (
                self._state_snapshot()
            )

        return {
            "alert_policy_contract_version": (
                ALERT_POLICY_CONTRACT_VERSION
            ),

            "source_risk_event_contract_version": (
                EXPECTED_RISK_EVENT_CONTRACT_VERSION
            ),

            "status": status,

            "decision": decision,

            "reason": reason,

            "should_notify": (
                should_notify
            ),

            "alert_type": (
                alert_type
            ),

            "event_id": (
                event_id
            ),

            "current_risk_level": (
                current_risk_level
            ),

            "evaluated_at_monotonic": (
                now
            ),

            "state": (
                state_snapshot
            ),

            # ------------------------------------------------
            # This layer decides notification eligibility.
            # It does NOT send the notification.
            # ------------------------------------------------

            "notification": None,

            "policy": {
                "type": (
                    "POSTGUARD_PROTOTYPE_ALERT_POLICY"
                ),

                "moderate_first_alert_delay_seconds": (
                    float(
                        self.config
                        .moderate_first_alert_delay_seconds
                    )
                ),

                "high_first_alert_delay_seconds": (
                    float(
                        self.config
                        .high_first_alert_delay_seconds
                    )
                ),

                "moderate_repeat_cooldown_seconds": (
                    float(
                        self.config
                        .moderate_repeat_cooldown_seconds
                    )
                ),

                "high_repeat_cooldown_seconds": (
                    float(
                        self.config
                        .high_repeat_cooldown_seconds
                    )
                ),

                "escalation_bypasses_cooldown": (
                    self.config
                    .escalation_bypasses_cooldown
                ),

                "notify_on_resolution": (
                    self.config
                    .notify_on_resolution
                ),

                "sends_notification": False,

                "is_clinical_timing_standard": False,
            },
        }

    # ========================================================
    # FIRST ALERT DECISION
    # ========================================================

    def _evaluate_first_alert(
        self,
        *,
        event: Mapping[str, Any],
        now: float,
        alert_type: str = ALERT_TYPE_FIRST,
    ) -> dict[str, Any]:

        state = self._require_same_event(
            event
        )

        risk_level = (
            event[
                "current_risk_level"
            ]
        )

        delay = (
            self._first_alert_delay(
                risk_level
            )
        )

        elapsed = (
            now
            -
            state[
                "event_started_at_monotonic"
            ]
        )

        if elapsed < 0.0:

            raise AlertPolicyError(
                "Alert clock occurs before "
                "Risk Event start time"
            )

        if elapsed < delay:

            return self._build_output(
                status=(
                    ALERT_STATUS_EVALUATED
                ),

                decision=(
                    ALERT_DECISION_SUPPRESSED
                ),

                reason=(
                    "FIRST_ALERT_DELAY_NOT_MET"
                ),

                should_notify=False,

                alert_type=None,

                event_id=(
                    state[
                        "event_id"
                    ]
                ),

                current_risk_level=(
                    risk_level
                ),

                now=now,
            )

        self._record_alert(
            now=now,
            risk_level=risk_level,
        )

        return self._build_output(
            status=(
                ALERT_STATUS_EVALUATED
            ),

            decision=(
                ALERT_DECISION_ALERT
            ),

            reason=(
                "FIRST_ALERT_READY"
                if alert_type == ALERT_TYPE_FIRST
                else
                "ESCALATION_ALERT_READY"
            ),

            should_notify=True,

            alert_type=(
                alert_type
            ),

            event_id=(
                state[
                    "event_id"
                ]
            ),

            current_risk_level=(
                risk_level
            ),

            now=now,
        )

    # ========================================================
    # REPEAT DECISION
    # ========================================================

    def _evaluate_repeat_alert(
        self,
        *,
        event: Mapping[str, Any],
        now: float,
        alert_type: str = ALERT_TYPE_REPEAT,
    ) -> dict[str, Any]:

        state = self._require_same_event(
            event
        )

        risk_level = (
            event[
                "current_risk_level"
            ]
        )

        last_alert_at = (
            state[
                "last_alert_at_monotonic"
            ]
        )

        if last_alert_at is None:

            return self._evaluate_first_alert(
                event=event,
                now=now,
                alert_type=alert_type,
            )

        cooldown = (
            self._repeat_cooldown(
                risk_level
            )
        )

        elapsed = (
            now
            -
            float(
                last_alert_at
            )
        )

        if elapsed < 0.0:

            raise AlertPolicyError(
                "Alert clock occurs before "
                "last alert timestamp"
            )

        if elapsed < cooldown:

            return self._build_output(
                status=(
                    ALERT_STATUS_EVALUATED
                ),

                decision=(
                    ALERT_DECISION_SUPPRESSED
                ),

                reason=(
                    "REPEAT_COOLDOWN_ACTIVE"
                ),

                should_notify=False,

                alert_type=None,

                event_id=(
                    state[
                        "event_id"
                    ]
                ),

                current_risk_level=(
                    risk_level
                ),

                now=now,
            )

        self._record_alert(
            now=now,
            risk_level=risk_level,
        )

        return self._build_output(
            status=(
                ALERT_STATUS_EVALUATED
            ),

            decision=(
                ALERT_DECISION_ALERT
            ),

            reason=(
                "REPEAT_COOLDOWN_COMPLETED"
                if alert_type == ALERT_TYPE_REPEAT
                else
                "ESCALATION_COOLDOWN_COMPLETED"
            ),

            should_notify=True,

            alert_type=(
                alert_type
            ),

            event_id=(
                state[
                    "event_id"
                ]
            ),

            current_risk_level=(
                risk_level
            ),

            now=now,
        )

    # ========================================================
    # MAIN
    # ========================================================

    def update(
        self,
        risk_event_result: Mapping[str, Any],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:

        source = (
            self._validate_risk_event_result(
                risk_event_result
            )
        )

        now_value = (
            self._resolve_now(
                now
            )
        )

        action = (
            source[
                "action"
            ]
        )

        event = (
            source[
                "event"
            ]
        )

        # ====================================================
        # NONE
        # ====================================================

        if action == EVENT_ACTION_NONE:

            if self._active_state is not None:

                raise AlertPolicyError(
                    "Risk Event reported NONE without "
                    "resolving the active event first"
                )

            return self._build_output(
                status=(
                    ALERT_STATUS_EVALUATED
                ),

                decision=(
                    ALERT_DECISION_NO_ALERT
                ),

                reason=(
                    "NO_ACTIVE_RISK_EVENT"
                ),

                should_notify=False,

                alert_type=None,

                event_id=None,

                current_risk_level=None,

                now=now_value,
            )

        # ====================================================
        # STARTED
        # ====================================================

        if action == EVENT_ACTION_STARTED:

            assert event is not None

            if self._active_state is not None:

                raise AlertPolicyError(
                    "Received STARTED while another "
                    "Alert Policy event state is active"
                )

            if (
                event[
                    "started_at_monotonic"
                ]
                >
                now_value
            ):

                raise AlertPolicyError(
                    "Risk Event start time cannot be "
                    "after Alert Policy current time"
                )

            self._create_state(
                event
            )

            return self._evaluate_first_alert(
                event=event,
                now=now_value,
                alert_type=ALERT_TYPE_FIRST,
            )

        # ====================================================
        # DATA GAP
        #
        # Never creates an alert.
        # Never resets cooldown.
        # Never resets first-alert state.
        # ====================================================

        if action == EVENT_ACTION_DATA_GAP:

            if event is None:

                if self._active_state is not None:

                    raise AlertPolicyError(
                        "DATA_GAP reports no active event "
                        "while Alert Policy still tracks one"
                    )

                return self._build_output(
                    status=(
                        ALERT_STATUS_PARTIAL
                    ),

                    decision=(
                        ALERT_DECISION_DATA_GAP
                    ),

                    reason=(
                        "DATA_GAP_WITHOUT_ACTIVE_EVENT"
                    ),

                    should_notify=False,

                    alert_type=None,

                    event_id=None,

                    current_risk_level=None,

                    now=now_value,
                )

            # ------------------------------------------------
            # If policy starts while an existing event is
            # already in DATA_GAP, adopt that event.
            # ------------------------------------------------

            if self._active_state is None:

                self._create_state(
                    event
                )

            else:

                self._require_same_event(
                    event
                )

            return self._build_output(
                status=(
                    ALERT_STATUS_PARTIAL
                ),

                decision=(
                    ALERT_DECISION_DATA_GAP
                ),

                reason=(
                    "DATA_GAP_PRESERVES_ALERT_STATE"
                ),

                should_notify=False,

                alert_type=None,

                event_id=(
                    event[
                        "runtime_event_id"
                    ]
                ),

                current_risk_level=(
                    event[
                        "current_risk_level"
                    ]
                ),

                now=now_value,
            )

        # ====================================================
        # UPDATED
        # ====================================================

        if action == EVENT_ACTION_UPDATED:

            assert event is not None

            state = (
                self._require_same_event(
                    event
                )
            )

            if (
                state[
                    "first_alert_sent"
                ]
                is False
            ):

                return self._evaluate_first_alert(
                    event=event,
                    now=now_value,
                )

            return self._evaluate_repeat_alert(
                event=event,
                now=now_value,
            )

        # ====================================================
        # ESCALATED
        #
        # Usually MODERATE -> HIGH.
        # ====================================================

        if action == EVENT_ACTION_ESCALATED:

            assert event is not None

            state = (
                self._require_same_event(
                    event
                )
            )

            # ------------------------------------------------
            # Immediate escalation alert.
            # ------------------------------------------------

            if (
                self.config
                .escalation_bypasses_cooldown
            ):

                self._record_alert(
                    now=now_value,
                    risk_level=(
                        event[
                            "current_risk_level"
                        ]
                    ),
                )

                return self._build_output(
                    status=(
                        ALERT_STATUS_EVALUATED
                    ),

                    decision=(
                        ALERT_DECISION_ALERT
                    ),

                    reason=(
                        "ESCALATION_BYPASSES_COOLDOWN"
                    ),

                    should_notify=True,

                    alert_type=(
                        ALERT_TYPE_ESCALATION
                    ),

                    event_id=(
                        state[
                            "event_id"
                        ]
                    ),

                    current_risk_level=(
                        event[
                            "current_risk_level"
                        ]
                    ),

                    now=now_value,
                )

            # ------------------------------------------------
            # No bypass.
            #
            # If event has never alerted, use current HIGH
            # first-alert delay.
            #
            # Otherwise use current HIGH cooldown.
            # ------------------------------------------------

            if (
                state[
                    "first_alert_sent"
                ]
                is False
            ):

                return self._evaluate_first_alert(
                    event=event,
                    now=now_value,
                    alert_type=(
                        ALERT_TYPE_ESCALATION
                    ),
                )

            return self._evaluate_repeat_alert(
                event=event,
                now=now_value,
                alert_type=(
                    ALERT_TYPE_ESCALATION
                ),
            )

        # ====================================================
        # DEESCALATED
        #
        # Do NOT alert.
        # Do NOT reset cooldown.
        # Do NOT reset event state.
        # ====================================================

        if (
            action
            ==
            EVENT_ACTION_DEESCALATED
        ):

            assert event is not None

            state = (
                self._require_same_event(
                    event
                )
            )

            return self._build_output(
                status=(
                    ALERT_STATUS_EVALUATED
                ),

                decision=(
                    ALERT_DECISION_NO_ALERT
                ),

                reason=(
                    "DEESCALATION_DOES_NOT_ALERT"
                ),

                should_notify=False,

                alert_type=None,

                event_id=(
                    state[
                        "event_id"
                    ]
                ),

                current_risk_level=(
                    event[
                        "current_risk_level"
                    ]
                ),

                now=now_value,
            )

        # ====================================================
        # RESOLVED
        # ====================================================

        if action == EVENT_ACTION_RESOLVED:

            resolved_event = (
                source[
                    "resolved_event"
                ]
            )

            assert resolved_event is not None

            event_id = (
                resolved_event[
                    "runtime_event_id"
                ]
            )

            # ------------------------------------------------
            # It is possible for Alert Policy to receive a
            # resolved event that it never alerted.
            # ------------------------------------------------

            if self._active_state is None:

                return self._build_output(
                    status=(
                        ALERT_STATUS_EVALUATED
                    ),

                    decision=(
                        ALERT_DECISION_NO_ALERT
                    ),

                    reason=(
                        "RESOLVED_EVENT_NOT_TRACKED"
                    ),

                    should_notify=False,

                    alert_type=None,

                    event_id=(
                        event_id
                    ),

                    current_risk_level=None,

                    now=now_value,

                    state_snapshot=None,
                )

            if (
                self._active_state[
                    "event_id"
                ]
                !=
                event_id
            ):

                raise AlertPolicyError(
                    "Resolved Risk Event ID does not "
                    "match active Alert Policy state"
                )

            state_before_clear = (
                self._state_snapshot()
            )

            should_resolution_notify = (
                self.config
                .notify_on_resolution
                and
                self._active_state[
                    "first_alert_sent"
                ]
                is True
            )

            if should_resolution_notify:

                self._record_alert(
                    now=now_value,
                    risk_level=None,
                )

                state_before_clear = (
                    self._state_snapshot()
                )

            # ------------------------------------------------
            # Resolution always clears event alert state.
            # ------------------------------------------------

            self._active_state = None

            if should_resolution_notify:

                return self._build_output(
                    status=(
                        ALERT_STATUS_EVALUATED
                    ),

                    decision=(
                        ALERT_DECISION_ALERT
                    ),

                    reason=(
                        "RESOLUTION_NOTIFICATION_ENABLED"
                    ),

                    should_notify=True,

                    alert_type=(
                        ALERT_TYPE_RESOLUTION
                    ),

                    event_id=(
                        event_id
                    ),

                    current_risk_level=None,

                    now=now_value,

                    state_snapshot=(
                        state_before_clear
                    ),
                )

            return self._build_output(
                status=(
                    ALERT_STATUS_EVALUATED
                ),

                decision=(
                    ALERT_DECISION_NO_ALERT
                ),

                reason=(
                    "RISK_EVENT_RESOLVED"
                ),

                should_notify=False,

                alert_type=None,

                event_id=(
                    event_id
                ),

                current_risk_level=None,

                now=now_value,

                state_snapshot=(
                    state_before_clear
                ),
            )

        raise AlertPolicyError(
            f"Unhandled Risk Event action: {action!r}"
        )