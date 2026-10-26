from __future__ import annotations

import copy
import unittest

from app.vision.risk_event import (
    RISK_EVENT_CONTRACT_VERSION,
    RiskEventError,
    RiskEventTracker,
)


# ============================================================
# RISK RESULT BUILDERS
# ============================================================

def make_risk(
    level,
):

    return {
        "risk_contract_version": "1.2",

        "status": "EVALUATED",

        "risk_level_available": True,

        "risk_level": level,

        "risk_event": None,

        "alert": None,
    }


def make_partial_risk():

    return {
        "risk_contract_version": "1.2",

        "status": "PARTIAL",

        "risk_level_available": False,

        "risk_level": None,

        "risk_event": None,

        "alert": None,
    }


def make_not_evaluated_risk():

    return {
        "risk_contract_version": "1.2",

        "status": "NOT_EVALUATED",

        "risk_level_available": False,

        "risk_level": None,

        "risk_event": None,

        "alert": None,
    }


# ============================================================
# TESTS
# ============================================================

class TestRiskEventTracker(
    unittest.TestCase
):

    def test_contract_version(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_risk("NONE"),
            now=100.0,
        )

        self.assertEqual(
            result[
                "risk_event_contract_version"
            ],
            RISK_EVENT_CONTRACT_VERSION,
        )

        self.assertEqual(
            result[
                "source_risk_contract_version"
            ],
            "1.2",
        )

    def test_none_does_not_start_event(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_risk("NONE"),
            now=100.0,
        )

        self.assertEqual(
            result["event_action"],
            "NONE",
        )

        self.assertFalse(
            result["event_active"]
        )

        self.assertIsNone(
            result["event"]
        )

    def test_low_does_not_start_event(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_risk("LOW"),
            now=100.0,
        )

        self.assertEqual(
            result["event_action"],
            "NONE",
        )

        self.assertFalse(
            result["event_active"]
        )

    def test_moderate_starts_event(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        self.assertEqual(
            result["event_action"],
            "STARTED",
        )

        self.assertTrue(
            result["event_active"]
        )

        self.assertEqual(
            result["event"][
                "current_risk_level"
            ],
            "MODERATE",
        )

        self.assertEqual(
            result["event"][
                "peak_risk_level"
            ],
            "MODERATE",
        )

    def test_high_can_start_event_directly(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_risk("HIGH"),
            now=100.0,
        )

        self.assertEqual(
            result["event_action"],
            "STARTED",
        )

        self.assertEqual(
            result["event"][
                "current_risk_level"
            ],
            "HIGH",
        )

        self.assertEqual(
            result["event"][
                "peak_risk_level"
            ],
            "HIGH",
        )

    def test_same_moderate_updates_same_event(self):

        tracker = RiskEventTracker()

        first = tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        second = tracker.update(
            make_risk("MODERATE"),
            now=110.0,
        )

        self.assertEqual(
            second["event_action"],
            "UPDATED",
        )

        self.assertEqual(
            first["event"][
                "runtime_event_id"
            ],
            second["event"][
                "runtime_event_id"
            ],
        )

    def test_moderate_to_high_escalates(self):

        tracker = RiskEventTracker()

        tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        result = tracker.update(
            make_risk("HIGH"),
            now=110.0,
        )

        self.assertEqual(
            result["event_action"],
            "ESCALATED",
        )

        self.assertEqual(
            result[
                "previous_risk_level"
            ],
            "MODERATE",
        )

        self.assertEqual(
            result[
                "current_risk_level"
            ],
            "HIGH",
        )

        self.assertEqual(
            result["event"][
                "peak_risk_level"
            ],
            "HIGH",
        )

    def test_high_to_moderate_deescalates(self):

        tracker = RiskEventTracker()

        tracker.update(
            make_risk("HIGH"),
            now=100.0,
        )

        result = tracker.update(
            make_risk("MODERATE"),
            now=110.0,
        )

        self.assertEqual(
            result["event_action"],
            "DEESCALATED",
        )

        self.assertTrue(
            result["event_active"]
        )

        self.assertEqual(
            result["event"][
                "current_risk_level"
            ],
            "MODERATE",
        )

        self.assertEqual(
            result["event"][
                "peak_risk_level"
            ],
            "HIGH",
        )

    def test_moderate_to_low_resolves(self):

        tracker = RiskEventTracker()

        first = tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        event_id = (
            first["event"][
                "runtime_event_id"
            ]
        )

        result = tracker.update(
            make_risk("LOW"),
            now=120.0,
        )

        self.assertEqual(
            result["event_action"],
            "RESOLVED",
        )

        self.assertFalse(
            result["event_active"]
        )

        self.assertIsNone(
            result["event"]
        )

        self.assertEqual(
            result["resolved_event"][
                "runtime_event_id"
            ],
            event_id,
        )

        self.assertEqual(
            result["resolved_event"][
                "resolved_to_risk_level"
            ],
            "LOW",
        )

    def test_high_to_none_resolves(self):

        tracker = RiskEventTracker()

        tracker.update(
            make_risk("HIGH"),
            now=100.0,
        )

        result = tracker.update(
            make_risk("NONE"),
            now=120.0,
        )

        self.assertEqual(
            result["event_action"],
            "RESOLVED",
        )

        self.assertEqual(
            result["resolved_event"][
                "resolved_to_risk_level"
            ],
            "NONE",
        )

    def test_new_event_after_resolution_gets_new_id(self):

        tracker = RiskEventTracker()

        first = tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        first_id = (
            first["event"][
                "runtime_event_id"
            ]
        )

        tracker.update(
            make_risk("NONE"),
            now=110.0,
        )

        second = tracker.update(
            make_risk("MODERATE"),
            now=120.0,
        )

        second_id = (
            second["event"][
                "runtime_event_id"
            ]
        )

        self.assertNotEqual(
            first_id,
            second_id,
        )

    def test_partial_without_event_is_data_gap(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_partial_risk(),
            now=100.0,
        )

        self.assertEqual(
            result["event_action"],
            "DATA_GAP",
        )

        self.assertFalse(
            result["event_active"]
        )

        self.assertIsNone(
            result["event"]
        )

    def test_partial_does_not_resolve_active_event(self):

        tracker = RiskEventTracker()

        started = tracker.update(
            make_risk("HIGH"),
            now=100.0,
        )

        event_id = (
            started["event"][
                "runtime_event_id"
            ]
        )

        result = tracker.update(
            make_partial_risk(),
            now=110.0,
        )

        self.assertEqual(
            result["event_action"],
            "DATA_GAP",
        )

        self.assertTrue(
            result["event_active"]
        )

        self.assertEqual(
            result["event"][
                "runtime_event_id"
            ],
            event_id,
        )

        self.assertEqual(
            result["event"][
                "current_risk_level"
            ],
            "HIGH",
        )

    def test_not_evaluated_is_data_gap(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_not_evaluated_risk(),
            now=100.0,
        )

        self.assertEqual(
            result["event_action"],
            "DATA_GAP",
        )

    def test_event_continues_after_data_gap(self):

        tracker = RiskEventTracker()

        first = tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        event_id = (
            first["event"][
                "runtime_event_id"
            ]
        )

        tracker.update(
            make_partial_risk(),
            now=110.0,
        )

        recovered = tracker.update(
            make_risk("MODERATE"),
            now=120.0,
        )

        self.assertEqual(
            recovered["event_action"],
            "UPDATED",
        )

        self.assertEqual(
            recovered["event"][
                "runtime_event_id"
            ],
            event_id,
        )

    def test_event_can_escalate_after_data_gap(self):

        tracker = RiskEventTracker()

        tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        tracker.update(
            make_partial_risk(),
            now=110.0,
        )

        result = tracker.update(
            make_risk("HIGH"),
            now=120.0,
        )

        self.assertEqual(
            result["event_action"],
            "ESCALATED",
        )

    def test_risk_event_does_not_create_alert(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_risk("HIGH"),
            now=100.0,
        )

        self.assertIsNone(
            result["alert"]
        )

        self.assertFalse(
            result["policy"][
                "creates_alert"
            ]
        )

    def test_input_is_not_modified(self):

        tracker = RiskEventTracker()

        risk = make_risk(
            "MODERATE"
        )

        before = copy.deepcopy(
            risk
        )

        tracker.update(
            risk,
            now=100.0,
        )

        self.assertEqual(
            risk,
            before,
        )

    def test_output_event_is_independent_copy(self):

        tracker = RiskEventTracker()

        result = tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        result["event"][
            "current_risk_level"
        ] = "BROKEN"

        active = (
            tracker.get_active_event()
        )

        self.assertEqual(
            active[
                "current_risk_level"
            ],
            "MODERATE",
        )

    def test_bad_risk_contract_rejected(self):

        tracker = RiskEventTracker()

        risk = make_risk(
            "NONE"
        )

        risk[
            "risk_contract_version"
        ] = "999"

        with self.assertRaises(
            RiskEventError
        ):

            tracker.update(
                risk,
                now=100.0,
            )

    def test_invalid_risk_level_rejected(self):

        tracker = RiskEventTracker()

        risk = make_risk(
            "CRITICAL"
        )

        with self.assertRaises(
            RiskEventError
        ):

            tracker.update(
                risk,
                now=100.0,
            )

    def test_evaluated_without_available_level_rejected(self):

        tracker = RiskEventTracker()

        risk = make_risk(
            "LOW"
        )

        risk[
            "risk_level_available"
        ] = False

        with self.assertRaises(
            RiskEventError
        ):

            tracker.update(
                risk,
                now=100.0,
            )

    def test_partial_with_risk_level_rejected(self):

        tracker = RiskEventTracker()

        risk = make_partial_risk()

        risk[
            "risk_level"
        ] = "HIGH"

        with self.assertRaises(
            RiskEventError
        ):

            tracker.update(
                risk,
                now=100.0,
            )

    # ========================================================
    # NEW CONTRACT TEST
    # ========================================================

    def test_partial_with_available_level_true_rejected(self):

        tracker = RiskEventTracker()

        risk = make_partial_risk()

        risk[
            "risk_level_available"
        ] = True

        with self.assertRaises(
            RiskEventError
        ):

            tracker.update(
                risk,
                now=100.0,
            )

    # ========================================================
    # NEW CONTRACT TEST
    # ========================================================

    def test_not_evaluated_with_available_level_true_rejected(self):

        tracker = RiskEventTracker()

        risk = make_not_evaluated_risk()

        risk[
            "risk_level_available"
        ] = True

        with self.assertRaises(
            RiskEventError
        ):

            tracker.update(
                risk,
                now=100.0,
            )

    def test_time_cannot_move_backwards(self):

        tracker = RiskEventTracker()

        tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        with self.assertRaises(
            RiskEventError
        ):

            tracker.update(
                make_risk(
                    "MODERATE"
                ),
                now=99.0,
            )

    def test_reset_clears_active_event(self):

        tracker = RiskEventTracker()

        tracker.update(
            make_risk("HIGH"),
            now=100.0,
        )

        self.assertIsNotNone(
            tracker.get_active_event()
        )

        tracker.reset()

        self.assertIsNone(
            tracker.get_active_event()
        )

    def test_reset_restarts_runtime_event_sequence(self):

        tracker = RiskEventTracker()

        first = tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        self.assertEqual(
            first["event"][
                "runtime_event_id"
            ],
            "risk-event-000001",
        )

        tracker.reset()

        second = tracker.update(
            make_risk("MODERATE"),
            now=200.0,
        )

        self.assertEqual(
            second["event"][
                "runtime_event_id"
            ],
            "risk-event-000001",
        )

    def test_resume_reset_can_preserve_runtime_event_sequence(self):

        tracker = RiskEventTracker()

        first = tracker.update(
            make_risk("MODERATE"),
            now=100.0,
        )

        tracker.reset(preserve_sequence=True)

        second = tracker.update(
            make_risk("MODERATE"),
            now=200.0,
        )

        self.assertEqual(first["event"]["runtime_event_id"], "risk-event-000001")
        self.assertEqual(second["event"]["runtime_event_id"], "risk-event-000002")


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
