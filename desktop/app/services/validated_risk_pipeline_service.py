from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Mapping


# ============================================================
# Backend camera_card import path
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

BACKEND_ROOT = (
    PROJECT_ROOT
    / "backend"
)

backend_path = str(
    BACKEND_ROOT
)

if backend_path not in sys.path:
    sys.path.insert(
        0,
        backend_path,
    )


# ============================================================
# Validated PostGuard core pipeline
# ============================================================

from camera_card.alert_policy.alert_policy import (  # noqa: E402
    AlertPolicy,
    AlertPolicyConfig,
)

from camera_card.posture_assessment.current_posture_assessment import (  # noqa: E402
    assess_current_posture,
)

from camera_card.risk_evaluation.risk_evaluator import (  # noqa: E402
    evaluate_risk,
)

from camera_card.risk_event.risk_event_tracker import (  # noqa: E402
    RiskEventTracker,
)

from camera_card.temporal_tracking.temporal_posture_tracker import (  # noqa: E402
    TemporalPostureTracker,
)

from camera_card.posture_score import (  # noqa: E402
    calculate_modified_rula_score,
)

from app.services.baseline_comparison_service import (  # noqa: E402
    compare_detection_to_baseline,
)


# ============================================================
# Integration contract
# ============================================================

VALIDATED_RISK_PIPELINE_SERVICE_VERSION = "1.2"


# ============================================================
# Risk Event UX stability
#
# Prototype UX timing, not a clinical standard.
# ============================================================

DEFAULT_RISK_EVENT_RECOVERY_GRACE_SECONDS = 5.0


# ============================================================
# Alert Policy
#
# Prototype UX timings, not clinical standards.
#
# MODERATE:
#     Must remain an active Risk Event for 5 seconds before
#     the first user-facing notification.
#
# HIGH:
#     First alert is immediate.
#
# REPEAT:
#     MODERATE = 5 minutes
#     HIGH     = 3 minutes
#
# Escalation:
#     MODERATE -> HIGH bypasses cooldown.
# ============================================================

DEFAULT_ALERT_POLICY_CONFIG = AlertPolicyConfig(
    moderate_first_alert_delay_seconds=5.0,
    high_first_alert_delay_seconds=0.0,

    moderate_repeat_cooldown_seconds=300.0,
    high_repeat_cooldown_seconds=180.0,

    escalation_bypasses_cooldown=True,

    notify_on_resolution=False,
)


class ValidatedRiskPipelineService:
    """
    Desktop adapter for the PostGuard posture-risk pipeline.

    Runtime flow:

        Detection
             │
             ├── Baseline Comparison
             │
             └── Current Posture Assessment
                        ↓
                 Temporal Tracking
                        ↓
                  Risk Evaluation
                        ↓
                    Risk Event
                        ↓
                   Alert Policy

    Important:

    - Detection continues every processing cycle.
    - Cooldown only suppresses user-facing notification.
    - Risk Event recovery grace prevents short LOW/NONE
      fluctuations from splitting one real-world event into
      many events.
    - Baseline comparison does not rewrite Detection values.
    - Modified RULA is still intentionally not implemented.
    """

    def __init__(
        self,
        *,
        alert_policy_config: (
            AlertPolicyConfig
            | None
        ) = None,
        baseline_gate_rules: (
            Mapping[str, Any]
            | None
        ) = None,
        risk_event_recovery_grace_seconds: float = (
            DEFAULT_RISK_EVENT_RECOVERY_GRACE_SECONDS
        ),
    ) -> None:

        self.alert_policy_config = (
            alert_policy_config
            or DEFAULT_ALERT_POLICY_CONFIG
        )

        self.baseline_gate_rules = (
            baseline_gate_rules
        )

        self.risk_event_recovery_grace_seconds = (
            float(
                risk_event_recovery_grace_seconds
            )
        )

        self._create_runtime_components()

        self.last_result: (
            dict[str, Any]
            | None
        ) = None

    # ========================================================
    # Runtime components
    # ========================================================

    def _create_runtime_components(
        self,
    ) -> None:

        self.temporal_tracker = (
            TemporalPostureTracker()
        )

        self.risk_event_tracker = (
            RiskEventTracker(
                recovery_grace_seconds=(
                    self.risk_event_recovery_grace_seconds
                )
            )
        )

        self.alert_policy = (
            AlertPolicy(
                config=(
                    self.alert_policy_config
                )
            )
        )

    # ========================================================
    # Reset
    # ========================================================

    def reset(
        self,
    ) -> None:
        """
        Reset stateful pipeline components.

        Used for a new Session or an intentional lifecycle
        boundary.

        IMPORTANT:
        Persist/resolve any active Risk Event before calling
        reset when ending a real Session.
        """

        self._create_runtime_components()

        self.last_result = None

    # ========================================================
    # Process one Detection result
    # ========================================================

    def process_detection(
        self,
        detection_result: Mapping[str, Any],
        baseline_data: (
            Mapping[str, Any]
            | None
        ),
        *,
        now: float | None = None,
    ) -> dict[str, Any]:

        if not isinstance(
            detection_result,
            Mapping,
        ):
            raise ValueError(
                "detection_result must be a mapping"
            )

        now_value = (
            time.monotonic()
            if now is None
            else float(now)
        )

        # ====================================================
        # 1. Baseline Comparison
        #
        # Parallel evidence only.
        # It never overwrites current Detection.
        # ====================================================

        baseline_comparison = (
            compare_detection_to_baseline(
                detection_result,
                baseline_data,
                gate_rules=(
                    self.baseline_gate_rules
                ),
            )
        )

        # ====================================================
        # 2. Current Posture Assessment
        # ====================================================

        assessment_result = (
            assess_current_posture(
                detection_result
            )
        )

        # ====================================================
        # 3. Temporal Tracking
        # ====================================================

        temporal_result = (
            self.temporal_tracker.update(
                assessment_result,
                now=now_value,
            )
        )

        # ====================================================
        # 4. PostGuard Modified RULA
        #
        # Current posture score.
        #
        # Does NOT decide Risk Event.
        # ====================================================

        posture_score_result = (
            calculate_modified_rula_score(
                assessment_result,
                temporal_result,
            )
        )

        # ====================================================
        # 5. Risk Evaluation
        # ====================================================

        risk_result = (
            evaluate_risk(
                assessment_result,
                temporal_result,
            )
        )

        # ====================================================
        # 6. Risk Event
        # ====================================================

        risk_event_result = (
            self.risk_event_tracker.update(
                risk_result,
                now=now_value,
            )
        )

        # ====================================================
        # 7. Alert Policy
        # ====================================================

        alert_policy_result = (
            self.alert_policy.update(
                risk_event_result,
                now=now_value,
            )
        )


        # ====================================================
        # Result
        # ====================================================

        result = {
            "service_version": (
                VALIDATED_RISK_PIPELINE_SERVICE_VERSION
            ),

            "timestamp_monotonic": (
                now_value
            ),

            "detection": (
                detection_result
            ),

            "baseline_comparison": (
                baseline_comparison
            ),

            "assessment": (
                assessment_result
            ),

            "posture_score": (
                posture_score_result
            ),

            "temporal": (
                temporal_result
            ),

            "risk": (
                risk_result
            ),

            "risk_event": (
                risk_event_result
            ),

            "alert_policy": (
                alert_policy_result
            ),
        }

        self.last_result = result

        return result

    # ========================================================
    # Last result
    # ========================================================

    def get_last_result(
        self,
    ) -> dict[str, Any] | None:

        return self.last_result