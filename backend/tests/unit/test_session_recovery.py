"""Recovery endpoints use an isolated database; no cloud writes."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

try:
    from . import test_session_summaries as fixtures
except ImportError:
    import test_session_summaries as fixtures
from app.models.session import PostureSession
from app.models.user import User
from app.models.alert_event import AlertEvent
from app.models.risk_event import RiskEvent
from app.core.privacy import CURRENT_PRIVACY_NOTICE_VERSION
from app.routers.sessions import router as sessions_router
from app.routers.alert_events import router as alerts_router
from app.routers.auth import get_current_user


class SessionRecoveryTests(unittest.TestCase):
    def setUp(self):
        fixtures.SessionSummaryTests.setUp(self)
        self.app.include_router(sessions_router)
        self.app.include_router(alerts_router)
        self.user = self.db.get(User, 1)
        self.user.privacy_consent_version = CURRENT_PRIVACY_NOTICE_VERSION
        self.user.privacy_consent_accepted_at = datetime.now(timezone.utc)
        self.user.privacy_consent_withdrawn_at = None
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.session = self.db.get(PostureSession, 1)
        self.session.status = "RUNNING"
        self.db.commit()

    tearDown = fixtures.SessionSummaryTests.tearDown

    def test_interrupt_preserves_unknown_end_and_retry_is_idempotent(self):
        for previous in ("RUNNING", "PAUSED"):
            with self.subTest(previous=previous):
                self.session.status = previous
                self.session.paused_duration = 12
                self.db.commit()
                result = self.client.post("/sessions/1/interrupt")
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()["status"], "INTERRUPTED")
                self.assertIsNone(result.json()["ended_at"])
                self.assertIsNone(result.json()["total_duration"])
                self.assertIsNone(result.json()["paused_duration"])
                self.assertEqual(self.client.post("/sessions/1/interrupt").json(), result.json())
                self.assertIsNone(self.client.get("/sessions").json()[0]["total_duration"])
                self.assertEqual(self.client.get("/sessions/1/summary").status_code, 404)
                self.assertEqual(self.client.post("/sessions/1/summary", json=self.payload).status_code, 409)

    def test_other_user_cannot_interrupt(self):
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2)
        self.assertEqual(self.client.post("/sessions/1/interrupt").status_code, 404)
        self.db.refresh(self.session)
        self.assertEqual(self.session.status, "RUNNING")

    def test_completed_session_cannot_be_reclassified(self):
        self.session.status = "COMPLETED"
        self.db.commit()
        self.assertEqual(self.client.post("/sessions/1/interrupt").status_code, 409)

    def test_new_session_blocked_until_previous_is_interrupted(self):
        payload = {"camera_id": 1, "baseline_id": 1}
        self.assertEqual(self.client.post("/sessions/start", json=payload).status_code, 409)
        self.client.post("/sessions/1/interrupt")
        result = self.client.post("/sessions/start", json=payload)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertNotEqual(result.json()["session_id"], 1)

    def test_new_session_requires_camera_preparation_snapshot(self):
        self.client.post("/sessions/1/interrupt")
        baseline = self.db.get(fixtures.PersonalBaseline, 1)
        baseline.camera_scale_avg = None
        baseline.camera_calibrated_at = None
        self.db.commit()

        result = self.client.post(
            "/sessions/start", json={"camera_id": 1, "baseline_id": 1}
        )

        self.assertEqual(result.status_code, 409)
        self.assertIn("Camera preparation", result.json()["detail"])

    def test_unclosed_alert_is_incomplete_not_active_or_zero_duration(self):
        now = datetime.now(timezone.utc)
        open_alert = AlertEvent(session_id=1, event_type="NECK_LATERAL_TILT", risk_level="MEDIUM", started_at=now)
        closed_alert = AlertEvent(session_id=1, event_type="SHOULDER_TILT", risk_level="MEDIUM", started_at=now, ended_at=now, duration=5)
        self.db.add_all([open_alert, closed_alert])
        self.db.commit()
        self.client.post("/sessions/1/interrupt")
        alerts = {a["event_id"]: a for a in self.client.get("/sessions/1/alerts").json()}
        self.assertTrue(alerts[open_alert.event_id]["incomplete"])
        self.assertIsNone(alerts[open_alert.event_id]["duration"])
        self.assertIsNone(alerts[open_alert.event_id]["ended_at"])
        self.assertEqual(alerts[closed_alert.event_id]["duration"], 5)
        self.assertFalse(alerts[closed_alert.event_id]["incomplete"])
        self.assertTrue(self.client.get(f"/alerts/{open_alert.event_id}").json()["incomplete"])
        self.assertEqual(self.client.post(f"/alerts/{open_alert.event_id}/end").status_code, 409)
        for action in ("resume", "pause", "end"):
            self.assertEqual(self.client.post(f"/sessions/1/{action}").status_code, 409)

    def test_pause_and_interrupt_finalize_integrated_risk_events(self):
        now = datetime.now(timezone.utc)
        first = RiskEvent(
            session_id=1, runtime_event_id="risk-event-000001",
            initial_risk_level="MODERATE", current_risk_level="MODERATE",
            max_risk_level="MODERATE", status="ACTIVE", started_at=now,
            duration_seconds=0, active_factors=[], evidence_groups=[],
        )
        self.db.add(first)
        self.db.commit()

        self.assertEqual(self.client.post("/sessions/1/pause").status_code, 200)
        self.db.refresh(first)
        self.assertEqual(first.status, "RESOLVED")
        self.assertEqual(first.resolved_reason, "SESSION_PAUSED")

        self.assertEqual(self.client.post("/sessions/1/resume").status_code, 200)
        second = RiskEvent(
            session_id=1, runtime_event_id="risk-event-000002",
            initial_risk_level="HIGH", current_risk_level="HIGH",
            max_risk_level="HIGH", status="ACTIVE", started_at=now,
            duration_seconds=0, active_factors=[], evidence_groups=[],
        )
        self.db.add(second)
        self.db.commit()
        self.assertEqual(self.client.post("/sessions/1/interrupt").status_code, 200)
        self.db.refresh(second)
        self.assertEqual(second.status, "INCOMPLETE")
        self.assertIsNone(second.ended_at)
        self.assertEqual(second.resolved_reason, "SESSION_INTERRUPTED")


if __name__ == "__main__":
    unittest.main()
