from __future__ import annotations

import copy
import unittest

from app.vision.alert_policy import (
    AlertPolicy,
    AlertPolicyConfig,
    AlertPolicyError,
)


# ============================================================
# CONFIG BUILDERS
# ============================================================

def immediate_test_config(
    *,
    escalation_bypasses_cooldown=True,
    notify_on_resolution=False,
):

    return AlertPolicyConfig(
        moderate_first_alert_delay_seconds=0.0,
        high_first_alert_delay_seconds=0.0,

        moderate_repeat_cooldown_seconds=600.0,
        high_repeat_cooldown_seconds=300.0,

        escalation_bypasses_cooldown=(
            escalation_bypasses_cooldown
        ),

        notify_on_resolution=(
            notify_on_resolution
        ),
    )


def delayed_test_config():

    return AlertPolicyConfig(
        moderate_first_alert_delay_seconds=10.0,
        high_first_alert_delay_seconds=5.0,

        moderate_repeat_cooldown_seconds=600.0,
        high_repeat_cooldown_seconds=300.0,

        escalation_bypasses_cooldown=True,

        notify_on_resolution=False,
    )


# ============================================================
# RISK EVENT BUILDERS
# ============================================================

def active_event(
    event_id,
    level,
    *,
    started_at=100.0,
):

    return {
        "runtime_event_id": event_id,

        "started_at_monotonic": (
            float(started_at)
        ),

        "last_evaluated_at_monotonic": (
            float(started_at)
        ),

        "current_risk_level": level,

        "peak_risk_level": level,

        "active": True,
    }


def started(
    level="MODERATE",
    *,
    event_id="risk-event-000001",
    started_at=100.0,
):

    event = active_event(
        event_id,
        level,
        started_at=started_at,
    )

    return {
        "risk_event_contract_version": "1.0",

        "status": "EVALUATED",

        "event_action": "STARTED",

        "source_risk_status": "EVALUATED",

        "current_risk_level": level,

        "previous_risk_level": None,

        "event_active": True,

        "event": event,

        "resolved_event": None,

        "alert": None,
    }


def updated(
    level="MODERATE",
    *,
    event_id="risk-event-000001",
    started_at=100.0,
):

    event = active_event(
        event_id,
        level,
        started_at=started_at,
    )

    return {
        "risk_event_contract_version": "1.0",
        "status": "EVALUATED",
        "event_action": "UPDATED",
        "source_risk_status": "EVALUATED",
        "current_risk_level": level,
        "previous_risk_level": level,
        "event_active": True,
        "event": event,
        "resolved_event": None,
        "alert": None,
    }


def escalated(
    *,
    event_id="risk-event-000001",
    started_at=100.0,
):

    event = active_event(
        event_id,
        "HIGH",
        started_at=started_at,
    )

    event[
        "peak_risk_level"
    ] = "HIGH"

    return {
        "risk_event_contract_version": "1.0",
        "status": "EVALUATED",
        "event_action": "ESCALATED",
        "source_risk_status": "EVALUATED",
        "current_risk_level": "HIGH",
        "previous_risk_level": "MODERATE",
        "event_active": True,
        "event": event,
        "resolved_event": None,
        "alert": None,
    }


def deescalated(
    *,
    event_id="risk-event-000001",
    started_at=100.0,
):

    event = active_event(
        event_id,
        "MODERATE",
        started_at=started_at,
    )

    event[
        "peak_risk_level"
    ] = "HIGH"

    return {
        "risk_event_contract_version": "1.0",
        "status": "EVALUATED",
        "event_action": "DEESCALATED",
        "source_risk_status": "EVALUATED",
        "current_risk_level": "MODERATE",
        "previous_risk_level": "HIGH",
        "event_active": True,
        "event": event,
        "resolved_event": None,
        "alert": None,
    }


def data_gap(
    *,
    with_event=True,
    event_id="risk-event-000001",
    level="MODERATE",
    started_at=100.0,
):

    event = None

    if with_event:

        event = active_event(
            event_id,
            level,
            started_at=started_at,
        )

    return {
        "risk_event_contract_version": "1.0",

        "status": "PARTIAL",

        "event_action": "DATA_GAP",

        "source_risk_status": "PARTIAL",

        "current_risk_level": None,

        "previous_risk_level": (
            level
            if with_event
            else None
        ),

        "event_active": (
            with_event
        ),

        "event": event,

        "resolved_event": None,

        "alert": None,
    }


def resolved(
    *,
    event_id="risk-event-000001",
    previous_level="MODERATE",
    resolved_to="NONE",
):

    return {
        "risk_event_contract_version": "1.0",

        "status": "EVALUATED",

        "event_action": "RESOLVED",

        "source_risk_status": "EVALUATED",

        "current_risk_level": resolved_to,

        "previous_risk_level": previous_level,

        "event_active": False,

        "event": None,

        "resolved_event": {
            "runtime_event_id": event_id,

            "started_at_monotonic": 100.0,

            "last_evaluated_at_monotonic": 200.0,

            "current_risk_level": previous_level,

            "peak_risk_level": previous_level,

            "active": False,

            "resolved_at_monotonic": 200.0,

            "resolved_to_risk_level": resolved_to,

            "resolution_reason": (
                "RISK_BELOW_EVENT_THRESHOLD"
            ),
        },

        "alert": None,
    }


def no_event():

    return {
        "risk_event_contract_version": "1.0",
        "status": "EVALUATED",
        "event_action": "NONE",
        "source_risk_status": "EVALUATED",
        "current_risk_level": "NONE",
        "previous_risk_level": None,
        "event_active": False,
        "event": None,
        "resolved_event": None,
        "alert": None,
    }


# ============================================================
# TESTS
# ============================================================

class TestAlertPolicy(
    unittest.TestCase
):

    def test_none_does_not_alert(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        result = policy.update(
            no_event(),
            now=100.0,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["decision"],
            "NO_ALERT",
        )

    def test_moderate_started_alerts_immediately_when_delay_zero(
        self,
    ):

        policy = AlertPolicy(
            immediate_test_config()
        )

        result = policy.update(
            started("MODERATE"),
            now=100.0,
        )

        self.assertTrue(
            result["should_notify"]
        )

        self.assertEqual(
            result["alert_type"],
            "FIRST",
        )

        self.assertEqual(
            result["state"][
                "alert_count"
            ],
            1,
        )

    def test_high_started_alerts_immediately_when_delay_zero(
        self,
    ):

        policy = AlertPolicy(
            immediate_test_config()
        )

        result = policy.update(
            started("HIGH"),
            now=100.0,
        )

        self.assertTrue(
            result["should_notify"]
        )

        self.assertEqual(
            result["alert_type"],
            "FIRST",
        )

    def test_first_alert_delay_is_respected(self):

        policy = AlertPolicy(
            delayed_test_config()
        )

        first = policy.update(
            started(
                "MODERATE",
                started_at=100.0,
            ),
            now=100.0,
        )

        self.assertFalse(
            first["should_notify"]
        )

        self.assertEqual(
            first["decision"],
            "SUPPRESSED",
        )

        second = policy.update(
            updated(
                "MODERATE",
                started_at=100.0,
            ),
            now=109.999,
        )

        self.assertFalse(
            second["should_notify"]
        )

        third = policy.update(
            updated(
                "MODERATE",
                started_at=100.0,
            ),
            now=110.0,
        )

        self.assertTrue(
            third["should_notify"]
        )

        self.assertEqual(
            third["alert_type"],
            "FIRST",
        )

    def test_moderate_does_not_alert_every_frame(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        result = policy.update(
            updated("MODERATE"),
            now=101.0,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["decision"],
            "SUPPRESSED",
        )

    def test_moderate_repeat_at_exact_600_seconds(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        before = policy.update(
            updated("MODERATE"),
            now=699.999,
        )

        self.assertFalse(
            before["should_notify"]
        )

        repeat = policy.update(
            updated("MODERATE"),
            now=700.0,
        )

        self.assertTrue(
            repeat["should_notify"]
        )

        self.assertEqual(
            repeat["alert_type"],
            "REPEAT",
        )

    def test_high_repeat_at_exact_300_seconds(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started("HIGH"),
            now=100.0,
        )

        before = policy.update(
            updated("HIGH"),
            now=399.999,
        )

        self.assertFalse(
            before["should_notify"]
        )

        repeat = policy.update(
            updated("HIGH"),
            now=400.0,
        )

        self.assertTrue(
            repeat["should_notify"]
        )

        self.assertEqual(
            repeat["alert_type"],
            "REPEAT",
        )

    def test_escalation_bypasses_cooldown(self):

        policy = AlertPolicy(
            immediate_test_config(
                escalation_bypasses_cooldown=True,
            )
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        result = policy.update(
            escalated(),
            now=101.0,
        )

        self.assertTrue(
            result["should_notify"]
        )

        self.assertEqual(
            result["alert_type"],
            "ESCALATION",
        )

        self.assertEqual(
            result["state"][
                "alert_count"
            ],
            2,
        )

    def test_escalation_can_respect_cooldown(self):

        policy = AlertPolicy(
            immediate_test_config(
                escalation_bypasses_cooldown=False,
            )
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        result = policy.update(
            escalated(),
            now=101.0,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["decision"],
            "SUPPRESSED",
        )

    def test_escalation_without_bypass_can_alert_after_high_cooldown(
        self,
    ):

        policy = AlertPolicy(
            immediate_test_config(
                escalation_bypasses_cooldown=False,
            )
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        result = policy.update(
            escalated(),
            now=400.0,
        )

        self.assertTrue(
            result["should_notify"]
        )

        self.assertEqual(
            result["alert_type"],
            "ESCALATION",
        )

    def test_deescalation_does_not_alert(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started("HIGH"),
            now=100.0,
        )

        result = policy.update(
            deescalated(),
            now=150.0,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["decision"],
            "NO_ALERT",
        )

    def test_deescalation_does_not_reset_cooldown(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started("HIGH"),
            now=100.0,
        )

        policy.update(
            deescalated(),
            now=200.0,
        )

        # MODERATE cooldown is 600 seconds from
        # last actual alert at t=100.
        before = policy.update(
            updated("MODERATE"),
            now=699.999,
        )

        self.assertFalse(
            before["should_notify"]
        )

        repeat = policy.update(
            updated("MODERATE"),
            now=700.0,
        )

        self.assertTrue(
            repeat["should_notify"]
        )

    def test_data_gap_does_not_alert(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        result = policy.update(
            data_gap(),
            now=200.0,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertEqual(
            result["decision"],
            "DATA_GAP",
        )

    def test_data_gap_preserves_cooldown(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        policy.update(
            data_gap(),
            now=300.0,
        )

        recovered = policy.update(
            updated("MODERATE"),
            now=700.0,
        )

        self.assertTrue(
            recovered["should_notify"]
        )

        self.assertEqual(
            recovered["alert_type"],
            "REPEAT",
        )

    def test_resolution_clears_state_without_popup_by_default(
        self,
    ):

        policy = AlertPolicy(
            immediate_test_config(
                notify_on_resolution=False,
            )
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        result = policy.update(
            resolved(),
            now=200.0,
        )

        self.assertFalse(
            result["should_notify"]
        )

        self.assertIsNone(
            policy.get_active_state()
        )

    def test_resolution_notification_can_be_enabled(self):

        policy = AlertPolicy(
            immediate_test_config(
                notify_on_resolution=True,
            )
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        result = policy.update(
            resolved(),
            now=200.0,
        )

        self.assertTrue(
            result["should_notify"]
        )

        self.assertEqual(
            result["alert_type"],
            "RESOLUTION",
        )

        self.assertIsNone(
            policy.get_active_state()
        )

    def test_resolution_does_not_notify_if_user_was_never_alerted(
        self,
    ):

        policy = AlertPolicy(
            AlertPolicyConfig(
                moderate_first_alert_delay_seconds=1000.0,
                high_first_alert_delay_seconds=1000.0,

                moderate_repeat_cooldown_seconds=600.0,
                high_repeat_cooldown_seconds=300.0,

                escalation_bypasses_cooldown=True,

                notify_on_resolution=True,
            )
        )

        first = policy.update(
            started("MODERATE"),
            now=100.0,
        )

        self.assertFalse(
            first["should_notify"]
        )

        result = policy.update(
            resolved(),
            now=200.0,
        )

        self.assertFalse(
            result["should_notify"]
        )

    def test_new_event_after_resolution_has_new_alert_state(
        self,
    ):

        policy = AlertPolicy(
            immediate_test_config()
        )

        first = policy.update(
            started(
                "MODERATE",
                event_id="risk-event-000001",
            ),
            now=100.0,
        )

        self.assertTrue(
            first["should_notify"]
        )

        policy.update(
            resolved(
                event_id="risk-event-000001",
            ),
            now=200.0,
        )

        second = policy.update(
            started(
                "MODERATE",
                event_id="risk-event-000002",
                started_at=300.0,
            ),
            now=300.0,
        )

        self.assertTrue(
            second["should_notify"]
        )

        self.assertEqual(
            second["event_id"],
            "risk-event-000002",
        )

    def test_event_change_without_resolution_rejected(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started(
                "MODERATE",
                event_id="risk-event-000001",
            ),
            now=100.0,
        )

        with self.assertRaises(
            AlertPolicyError
        ):

            policy.update(
                updated(
                    "MODERATE",
                    event_id="risk-event-000002",
                ),
                now=200.0,
            )

    def test_bad_contract_rejected(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        value = no_event()

        value[
            "risk_event_contract_version"
        ] = "999"

        with self.assertRaises(
            AlertPolicyError
        ):

            policy.update(
                value,
                now=100.0,
            )

    def test_time_cannot_move_backwards(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        policy.update(
            started("MODERATE"),
            now=100.0,
        )

        with self.assertRaises(
            AlertPolicyError
        ):

            policy.update(
                updated("MODERATE"),
                now=99.0,
            )

    def test_input_is_not_modified(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        value = started(
            "MODERATE"
        )

        before = copy.deepcopy(
            value
        )

        policy.update(
            value,
            now=100.0,
        )

        self.assertEqual(
            value,
            before,
        )

    def test_notification_remains_none(self):

        policy = AlertPolicy(
            immediate_test_config()
        )

        result = policy.update(
            started("HIGH"),
            now=100.0,
        )

        self.assertTrue(
            result["should_notify"]
        )

        self.assertIsNone(
            result["notification"]
        )

    def test_negative_config_rejected(self):

        with self.assertRaises(
            AlertPolicyError
        ):

            AlertPolicyConfig(
                moderate_first_alert_delay_seconds=-1.0,
                high_first_alert_delay_seconds=0.0,
                moderate_repeat_cooldown_seconds=600.0,
                high_repeat_cooldown_seconds=300.0,
                escalation_bypasses_cooldown=True,
                notify_on_resolution=False,
            )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )
