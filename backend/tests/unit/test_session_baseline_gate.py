"""Session start requires a completed personal baseline."""

import unittest

try:
    from . import test_session_summaries as fixtures
except ImportError:
    import test_session_summaries as fixtures

from app.models.personal_baseline import PersonalBaseline
from app.models.session import PostureSession
from app.routers.sessions import router as sessions_router


class SessionBaselineGateTests(unittest.TestCase):
    def setUp(self):
        fixtures.SessionSummaryTests.setUp(self)
        self.app.include_router(sessions_router)
        self.db.delete(self.db.get(PostureSession, 1))
        self.db.commit()

    tearDown = fixtures.SessionSummaryTests.tearDown

    def start(self):
        return self.client.post(
            "/sessions/start",
            json={"camera_id": 1, "baseline_id": 1},
        )

    def test_confirmed_complete_baseline_starts_session(self):
        response = self.start()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "RUNNING")

    def test_unconfirmed_or_incomplete_baseline_is_rejected(self):
        baseline = self.db.get(PersonalBaseline, 1)
        for field, invalid_value in (
            ("confirmation_status", "PENDING"),
            ("baseline_status", "NEED_CONFIRMATION"),
            ("neck_flexion_baseline", None),
            ("ipd_baseline", 0.0),
        ):
            with self.subTest(field=field):
                original = getattr(baseline, field)
                setattr(baseline, field, invalid_value)
                self.db.commit()
                response = self.start()
                self.assertEqual(response.status_code, 409, response.text)
                setattr(baseline, field, original)
                self.db.commit()


if __name__ == "__main__":
    unittest.main()
