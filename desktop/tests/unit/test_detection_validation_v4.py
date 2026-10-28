import unittest

from tools.video_validation.postguard_detection_validation_v4 import (
    calculate_blink_result,
    calculate_posture_events,
    get_posture_labels,
)


class DetectionValidationV4Tests(unittest.TestCase):
    def test_posture_event_detection_counts_overlap_and_miss(self):
        rows = [
            {"timestamp_sec": 0.0, "system_labels": {"NEUTRAL"}},
            {"timestamp_sec": 0.1, "system_labels": {"NEUTRAL"}},
            {"timestamp_sec": 0.2, "system_labels": set()},
            {"timestamp_sec": 0.3, "system_labels": set()},
        ]
        annotations = [
            {"type": "NEUTRAL", "start": 0.0, "end": 0.2},
            {"type": "NEUTRAL", "start": 0.3, "end": 0.4},
        ]

        _summary, details, overall = calculate_posture_events(
            rows, annotations, fps=10
        )

        self.assertEqual(overall["human_events"], 2)
        self.assertEqual(overall["detected"], 1)
        self.assertEqual(overall["missed"], 1)
        self.assertEqual(overall["detection_rate"], 0.5)
        neutral = [row for row in details if row["posture"] == "NEUTRAL"]
        self.assertEqual([row["detected"] for row in neutral], [True, False])

    def test_blink_matching_reports_precision_recall_and_f1(self):
        annotations = [
            {"type": "BLINK", "start": 1.0, "end": 1.0},
            {"type": "BLINK", "start": 2.0, "end": 2.0},
        ]
        system_events = [
            {"timestamp_sec": 1.1},
            {"timestamp_sec": 3.0},
        ]

        summary, details = calculate_blink_result(annotations, system_events)

        self.assertEqual(summary["matched"], 1)
        self.assertEqual(summary["human_missed"], 1)
        self.assertEqual(summary["system_only"], 1)
        self.assertEqual(summary["precision"], 0.5)
        self.assertEqual(summary["recall"], 0.5)
        self.assertEqual(summary["f1_score"], 0.5)
        self.assertEqual(len(details), 3)

    def test_current_assessment_contract_maps_to_v4_labels(self):
        assessment = {
            "status": "COMPLETE",
            "features": {
                "shoulder_tilt": {"status": "LEFT_SHOULDER_HIGH"},
                "neck_lateral_tilt": {"status": "TILT_RIGHT"},
                "neck_flexion": {"status": "FLEXION"},
            },
        }

        self.assertEqual(
            get_posture_labels(assessment),
            {"LEFT_SHOULDER_HIGH", "TILT_RIGHT", "FLEXION"},
        )


if __name__ == "__main__":
    unittest.main()
