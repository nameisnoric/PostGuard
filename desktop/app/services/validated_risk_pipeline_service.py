from __future__ import annotations

import time
from pathlib import Path
import sys
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


from app.services.baseline_comparison_service import (  # noqa: E402
    compare_detection_to_baseline,
)


# ============================================================
# Integration contract
# ============================================================

VALIDATED_RISK_PIPELINE_SERVICE_VERSION = "1.1"


# ============================================================
# Alert Policy configuration
#
# These remain prototype UX timings.
# They are NOT clinical standards.
# ============================================================

DEFAULT_ALERT_POLICY_CONFIG = AlertPolicyConfig(
    moderate_first_alert_delay_seconds=0.0,
    high_first_alert_delay_seconds=0.0,
    moderate_repeat_cooldown_seconds=600.0,
    high_repeat_cooldown_seconds=300.0,
    escalation_bypasses_cooldown=True,
    notify_on_resolution=False,
)


class ValidatedRiskPipelineService:
    """
    Desktop adapter for the validated PostGuard posture-risk pipeline.

    Runtime authority:

        Detection Contract 1.0
              │
              ├──> Baseline Comparison / Measurement-Change Gate
              │
              └──> Current Posture Assessment
                          ↓
                   Temporal Tracking
                          ↓
                    Risk Evaluation
                          ↓
                      Risk Event
                          ↓
                     Alert Policy

    Important design rules:

    1. Baseline Comparison does not overwrite Detection values.

    2. Measurement-Change Gate is not a risk classifier.

    3. Current Posture Assessment always receives the original
       Detection Contract.

    4. Risk Event does not send notifications.

    5. Alert Policy only decides whether a notification should occur.

    6. This service does not persist database records.

    7. Modified RULA / PostGuard posture score is not implemented
       in this service yet. A future score module must be separately
       designed and validated.
    """

    def __init__(
        self,
        *,
        alert_policy_config: AlertPolicyConfig | None = None,
        baseline_gate_rules: Mapping[str, Any] | None = None,
    ) -> None:

        self.alert_policy_config = (
            alert_policy_config
            or DEFAULT_ALERT_POLICY_CONFIG
        )

        # No production gate thresholds are currently assumed.
        self.baseline_gate_rules = (
            baseline_gate_rules
        )

        self.temporal_tracker = (
            TemporalPostureTracker()
        )

        self.risk_event_tracker = (
            RiskEventTracker()
        )

        self.alert_policy = (
            AlertPolicy(
                config=self.alert_policy_config
            )
        )

        self.last_result: dict[str, Any] | None = None

    # ========================================================
    # Reset
    # ========================================================

    def reset(self) -> None:
        """
        Reset all stateful temporal/risk/alert layers.

        Used when:
        - starting a new Session
        - Pause / Resume boundary
        - stopping Monitoring
        """

        self.temporal_tracker = (
            TemporalPostureTracker()
        )

        self.risk_event_tracker = (
            RiskEventTracker()
        )

        self.alert_policy = (
            AlertPolicy(
                config=self.alert_policy_config
            )
        )

        self.last_result = None

    # ========================================================
    # Process one Detection result
    # ========================================================

    def process_detection(
        self,
        detection_result: Mapping[str, Any],
        baseline_data: Mapping[str, Any] | None,
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
        # 1. Personal Baseline comparison
        #
        # IMPORTANT:
        #
        # This is parallel evidence.
        # It does NOT modify detection_result.
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
        #
        # ORIGINAL Detection values are used.
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
        # 4. Risk Evaluation
        # ====================================================

        risk_result = (
            evaluate_risk(
                assessment_result,
                temporal_result,
            )
        )

        # ====================================================
        # 5. Risk Event
        # ====================================================

        risk_event_result = (
            self.risk_event_tracker.update(
                risk_result,
                now=now_value,
            )
        )

        # ====================================================
        # 6. Alert Policy
        # ====================================================

        alert_policy_result = (
            self.alert_policy.update(
                risk_event_result,
                now=now_value,
            )
        )

        # ====================================================
        # 7. Modified RULA / posture score
        #
        # Intentionally NOT fabricated.
        #
        # This placeholder makes the integration contract ready
        # for the dedicated score module that we will build next.
        # ====================================================

        posture_score_result = {
            "status": "NOT_IMPLEMENTED",
            "modified_rula_score": None,
            "reason": (
                "POSTGUARD_MODIFIED_RULA_SCORE_NOT_YET_VALIDATED"
            ),
        }

        result = {
            "service_version": (
                VALIDATED_RISK_PIPELINE_SERVICE_VERSION
            ),
            "timestamp_monotonic": (
                now_value
            ),
            "detection": detection_result,
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