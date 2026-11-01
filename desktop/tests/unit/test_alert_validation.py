import tempfile
import unittest
from pathlib import Path

from tools.video_validation.alert_validation_core import (
    calculate_summary, export_validation_report, load_alert_ground_truth,
    match_alerts, save_alert_ground_truth,
)
from tools.video_validation.postguard_alert_validation import AlertGroundTruthApp


class AlertValidationTests(unittest.TestCase):
    def test_programmatic_seek_update_does_not_reopen_frame(self):
        app = AlertGroundTruthApp.__new__(AlertGroundTruthApp)
        app.capture = object()
        app.playing = False
        app.updating_seek = True
        shown_frames = []
        app.show_frame = shown_frames.append

        app.seek_changed("12")
        self.assertEqual(shown_frames, [])

        app.updating_seek = False
        app.seek_changed("12")
        self.assertEqual(shown_frames, [12])

    def test_new_alert_ground_truth_round_trip(self):
        markers = [
            {"event_type": "POSTURE_RISK", "alert_type": "FIRST", "timestamp_sec": 60.0, "note": "leaning"},
            {"event_type": "POSTURE_RISK", "alert_type": "RESOLVED", "timestamp_sec": 72.5, "note": "neutral"},
            {"event_type": "LOW_BLINK_RATE", "alert_type": "FIRST", "timestamp_sec": 90.0, "note": ""},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alert_gt.csv"
            save_alert_ground_truth(path, markers)
            self.assertEqual(load_alert_ground_truth(path), markers)

    def test_matching_requires_same_event_and_alert_type(self):
        expected = [
            {"event_type": "POSTURE_RISK", "alert_type": "FIRST", "timestamp_sec": 60.0},
            {"event_type": "POSTURE_RISK", "alert_type": "RESOLVED", "timestamp_sec": 80.0},
        ]
        actual = [
            {"event_type": "POSTURE_RISK", "alert_type": "FIRST", "timestamp_sec": 61.0},
            {"event_type": "LOW_BLINK_RATE", "alert_type": "FIRST", "timestamp_sec": 80.0},
        ]
        details = match_alerts(expected, actual, tolerance_seconds=2.0)
        summary = calculate_summary(details, 120.0)
        self.assertEqual(summary["matched"], 1)
        self.assertEqual(summary["missed"], 1)
        self.assertEqual(summary["system_only"], 1)
        self.assertEqual(summary["f1_score"], 0.5)
        self.assertEqual(summary["mean_latency_seconds"], 1.0)

    def test_empty_result_is_not_applicable(self):
        summary = calculate_summary([], 60.0)
        self.assertIsNone(summary["precision"])
        self.assertIsNone(summary["recall"])
        self.assertIsNone(summary["f1_score"])

    def test_report_exports_details_and_system_alerts(self):
        ground_truth = [{
            "event_type": "SCREEN_DISTANCE", "alert_type": "FIRST",
            "timestamp_sec": 10.0, "note": "too close",
        }]
        actual = [{
            "event_type": "SCREEN_DISTANCE", "alert_type": "FIRST",
            "timestamp_sec": 10.5, "value": 1.4,
        }]
        metadata = {"video": "sample.mp4", "duration_seconds": 30.0}
        with tempfile.TemporaryDirectory() as directory:
            report = export_validation_report(
                directory, ground_truth, actual, metadata, tolerance_seconds=1.0
            )
            self.assertEqual(report["summary"]["f1_score"], 1.0)
            self.assertTrue(Path(report["report_path"]).is_file())
            self.assertTrue(Path(report["details_path"]).is_file())
            self.assertTrue(Path(report["system_alerts_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
