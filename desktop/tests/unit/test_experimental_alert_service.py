import unittest
from app.services.experimental_alert_service import ExperimentalAlertService


class Response:
    def __init__(self, code=200, data=None):
        self.status_code = code
        self._data = data or {}
        self.text = str(self._data)
        self.ok = 200 <= code < 300

    def json(self):
        return self._data


class FakeAPI:
    def __init__(self):
        self.events = {}
        self.created = 0
        self.ended = 0
        self.fail_end = False
        self.fail_create_once = False

    def create_alert_event(self, session_id, event_type, risk_level):
        assert (session_id, event_type, risk_level) == (5, "NECK_LATERAL_TILT", "MEDIUM")
        if self.fail_create_once:
            self.fail_create_once = False
            return Response(503, {"detail": "temporary error"})
        self.created += 1
        eid = self.created
        self.events[eid] = {"event_id": eid, "event_type": event_type, "ended_at": None}
        return Response(201, {"event_id": eid})

    def end_alert_event(self, event_id):
        if self.fail_end:
            return Response(503, {"detail": "temporary error"})
        self.ended += 1
        self.events[event_id]["ended_at"] = "2026-10-10T10:00:00+00:00"
        return Response(200, self.events[event_id])

    def get_session_alerts(self, session_id):
        return Response(200, list(self.events.values()))

    def get_alert_event(self, event_id):
        return Response(200, self.events[event_id])


class TestExperimentalAlertService(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.api = FakeAPI()
        self.service = ExperimentalAlertService(client=self.api, clock=lambda: self.now)

    def test_does_not_create_before_sixty(self):
        self.assertIsNone(self.service.update(5, 1, 59.9))
        self.assertEqual(self.api.created, 0)

    def test_creates_once_per_episode(self):
        self.assertEqual(self.service.update(5, 1, 60), "created")
        self.service.update(5, 1, 70)
        self.service.update(5, 1, 90)
        self.assertEqual(self.api.created, 1)

    def test_end_on_neutral_then_new_episode(self):
        self.service.update(5, 1, 60)
        self.assertEqual(self.service.update(5, 0, 0), "ended")
        self.assertEqual(self.api.ended, 1)
        self.assertEqual(self.service.update(5, 1, 60), "created")
        self.assertEqual(self.api.created, 2)

    def test_missing_detection_ends(self):
        self.service.update(5, -1, 60)
        self.assertEqual(self.service.update(5, None, None), "ended")
        self.assertEqual(self.api.ended, 1)

    def test_end_failure_retains_event_and_retries(self):
        self.service.update(5, 1, 60)
        self.api.fail_end = True
        self.assertIsNone(self.service.update(5, 0, 0))
        self.assertEqual(self.service.active_event_id, 1)
        self.assertEqual(self.api.created, 1)
        self.api.fail_end = False
        self.now += 6
        self.assertEqual(self.service.update(5, 0, 0), "ended")

    def test_create_failure_retries_after_delay(self):
        self.api.fail_create_once = True
        self.service.update(5, 1, 60)
        self.assertEqual(self.api.created, 0)
        self.now += 6
        self.assertEqual(self.service.update(5, 1, 66), "created")

    def test_threshold_change_closes_active(self):
        self.service.update(5, 1, 60)
        self.assertTrue(self.service.close_if_active())
        self.assertEqual(self.api.ended, 1)
        self.assertIsNone(self.service.active_event_id)

    def test_disabled_threshold_does_not_create(self):
        self.assertIsNone(self.service.update(5, None, None))
        self.assertEqual(self.api.created, 0)


if __name__ == '__main__':
    unittest.main()
