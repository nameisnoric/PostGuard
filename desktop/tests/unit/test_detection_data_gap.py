import unittest
from unittest.mock import Mock

from app.services.detection_service import DetectionService
from app.services.wellness_alert_policy import WellnessAlertPolicy


class DetectionDataGapTests(unittest.TestCase):
    def test_gap_preserves_pipeline_contract_without_safe_result(self):
        service = DetectionService.__new__(DetectionService)
        service.risk_event_tracker = Mock()
        service.alert_policy = Mock()
        service.temporal_tracker = Mock()
        service.session_context = None
        service.wellness_alert_policy = WellnessAlertPolicy()
        event = {
            "event_action": "DATA_GAP",
            "event_active": True,
            "current_risk_level": "HIGH",
        }
        policy = {"should_notify": False, "decision": "DATA_GAP"}
        service.risk_event_tracker.update.return_value = event
        service.alert_policy.update.return_value = policy

        result = service.process_data_gap(
            "camera_frame_unavailable",
            timestamp=42.0,
        )

        risk = service.risk_event_tracker.update.call_args.args[0]
        self.assertEqual(risk["status"], "NOT_EVALUATED")
        self.assertIsNone(risk["risk_level"])
        self.assertEqual(result["risk_event"], event)
        self.assertEqual(result["alert_policy"], policy)
        self.assertEqual(result["data_gap_reason"], "CAMERA_FRAME_UNAVAILABLE")
        self.assertEqual(
            result["wellness_alert"]["events"][0]["action"],
            "DATA_GAP",
        )
        service.temporal_tracker.reset.assert_called_once_with()
        service.alert_policy.update.assert_called_once_with(event, now=42.0)

    def test_resume_restarts_blink_window(self):
        service = DetectionService.__new__(DetectionService)
        service.blink_statistics = Mock()

        service.resume_after_data_gap(timestamp=20.0)

        service.blink_statistics.start.assert_called_once_with(timestamp=20.0)


if __name__ == "__main__":
    unittest.main()
