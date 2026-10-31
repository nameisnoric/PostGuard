import unittest
from unittest.mock import patch

from app.services.blink_detection_service import (
    BlinkDetectionService,
)
from app.vision.mediapipe_detection.eye.eye_state import (
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
)


class FakeEyeStateDetector:
    def __init__(self):
        self.results = []

    def reset(self):
        pass

    def start_calibration(
        self,
        timestamp=None,
    ):
        pass

    def update(
        self,
        measurement,
        timestamp=None,
    ):
        if not self.results:
            raise RuntimeError(
                "No fake eye-state result available."
            )

        return self.results.pop(0)


def make_eye_result(
    *,
    state,
    right=None,
    left=None,
    calibrated=True,
):
    if right is None:
        right = state

    if left is None:
        left = state

    return {
        "calibrated": calibrated,
        "calibration_status": (
            "READY"
            if calibrated
            else
            "CALIBRATING"
        ),
        "calibration_progress": (
            1.0
            if calibrated
            else
            0.5
        ),
        "calibration_samples": 30,
        "eye_state": state,
        "right_eye_state": right,
        "left_eye_state": left,
        "right_open_reference": 0.30,
        "left_open_reference": 0.31,
        "right_close_threshold": 0.165,
        "left_close_threshold": 0.1705,
        "right_reopen_threshold": 0.21,
        "left_reopen_threshold": 0.217,
    }


class BlinkDetectionServiceV11Tests(
    unittest.TestCase
):

    def setUp(self):
        self.service = (
            BlinkDetectionService(
                max_closed_seconds=1.0
            )
        )

        self.fake_detector = (
            FakeEyeStateDetector()
        )

        self.service.eye_state_detector = (
            self.fake_detector
        )

        self.measurement = {
            "right_eye_openness": 0.30,
            "left_eye_openness": 0.31,
            "mean_eye_openness": 0.305,
        }

        self.measurement_patch = patch(
            "app.services.blink_detection_service."
            "calculate_eye_openness",
            return_value=self.measurement,
        )

        self.mock_measurement = (
            self.measurement_patch.start()
        )

    def tearDown(self):
        self.measurement_patch.stop()

    # ====================================================
    # OUTPUT CONTRACT
    # ====================================================

    def test_exposes_eye_openness_for_monitoring_ui(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_OPEN
            )
        ]

        result = (
            self.service.process_detection(
                {
                    "face_points": {
                        "dummy": True
                    }
                },
                now=1.0,
            )
        )

        self.assertEqual(
            result[
                "right_eye_openness"
            ],
            0.30,
        )

        self.assertEqual(
            result[
                "left_eye_openness"
            ],
            0.31,
        )

        self.assertEqual(
            result[
                "mean_eye_openness"
            ],
            0.305,
        )

    def test_both_open_pattern(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_OPEN
            )
        ]

        result = (
            self.service.process_detection(
                {},
                now=1.0,
            )
        )

        self.assertEqual(
            result[
                "eye_pattern"
            ],
            "BOTH_OPEN",
        )

    def test_both_closed_pattern(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_CLOSED
            )
        ]

        result = (
            self.service.process_detection(
                {},
                now=1.0,
            )
        )

        self.assertEqual(
            result[
                "eye_pattern"
            ],
            "BOTH_CLOSED",
        )

    def test_right_only_closed_pattern(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_UNKNOWN,
                right=EYE_CLOSED,
                left=EYE_OPEN,
            )
        ]

        result = (
            self.service.process_detection(
                {},
                now=1.0,
            )
        )

        self.assertEqual(
            result[
                "eye_pattern"
            ],
            "RIGHT_ONLY_CLOSED",
        )

    def test_left_only_closed_pattern(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_UNKNOWN,
                right=EYE_OPEN,
                left=EYE_CLOSED,
            )
        ]

        result = (
            self.service.process_detection(
                {},
                now=1.0,
            )
        )

        self.assertEqual(
            result[
                "eye_pattern"
            ],
            "LEFT_ONLY_CLOSED",
        )

    # ====================================================
    # BLINK COUNT
    # ====================================================

    def test_closed_to_open_counts_one_blink(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_OPEN
            ),
            make_eye_result(
                state=EYE_CLOSED
            ),
            make_eye_result(
                state=EYE_OPEN
            ),
        ]

        self.service.process_detection(
            {},
            now=1.0,
        )

        closed = (
            self.service.process_detection(
                {},
                now=1.2,
            )
        )

        opened = (
            self.service.process_detection(
                {},
                now=1.4,
            )
        )

        self.assertFalse(
            closed[
                "blink_event"
            ]
        )

        self.assertTrue(
            opened[
                "blink_event"
            ]
        )

        self.assertEqual(
            opened[
                "blink_count"
            ],
            1,
        )

        self.assertAlmostEqual(
            opened[
                "blink_duration_seconds"
            ],
            0.2,
        )

    def test_open_to_open_does_not_count(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_OPEN
            ),
            make_eye_result(
                state=EYE_OPEN
            ),
        ]

        self.service.process_detection(
            {},
            now=1.0,
        )

        result = (
            self.service.process_detection(
                {},
                now=1.2,
            )
        )

        self.assertFalse(
            result[
                "blink_event"
            ]
        )

        self.assertEqual(
            result[
                "blink_count"
            ],
            0,
        )

    def test_long_eye_closure_is_not_blink(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_OPEN
            ),
            make_eye_result(
                state=EYE_CLOSED
            ),
            make_eye_result(
                state=EYE_OPEN
            ),
        ]

        self.service.process_detection(
            {},
            now=1.0,
        )

        self.service.process_detection(
            {},
            now=1.2,
        )

        result = (
            self.service.process_detection(
                {},
                now=2.5,
            )
        )

        self.assertFalse(
            result[
                "blink_event"
            ]
        )

        self.assertEqual(
            result[
                "blink_count"
            ],
            0,
        )

    def test_unknown_breaks_closed_continuity(
        self,
    ):
        self.fake_detector.results = [
            make_eye_result(
                state=EYE_CLOSED
            ),
            make_eye_result(
                state=EYE_UNKNOWN
            ),
            make_eye_result(
                state=EYE_OPEN
            ),
        ]

        self.service.process_detection(
            {},
            now=1.0,
        )

        self.service.process_detection(
            {},
            now=1.1,
        )

        result = (
            self.service.process_detection(
                {},
                now=1.2,
            )
        )

        self.assertFalse(
            result[
                "blink_event"
            ]
        )

        self.assertEqual(
            result[
                "blink_count"
            ],
            0,
        )

    # ====================================================
    # RESET / PAUSE-RESUME CONTRACT
    # ====================================================

    def test_reset_preserve_count_keeps_blinks(
        self,
    ):
        self.service.total_blinks = 7

        self.service.previous_state = (
            EYE_CLOSED
        )

        self.service.closed_started_at = (
            10.0
        )

        self.service.reset(
            preserve_count=True,
            now=20.0,
        )

        self.assertEqual(
            self.service.total_blinks,
            7,
        )

        self.assertEqual(
            self.service.previous_state,
            EYE_UNKNOWN,
        )

        self.assertIsNone(
            self.service.closed_started_at
        )

    def test_reset_new_session_clears_count(
        self,
    ):
        self.service.total_blinks = 7

        self.service.reset(
            preserve_count=False,
            now=20.0,
        )

        self.assertEqual(
            self.service.total_blinks,
            0,
        )

    # ====================================================
    # BLINK RATE
    # ====================================================

    def test_blink_rate_per_minute(
        self,
    ):
        self.service.total_blinks = 10

        rate = (
            self.service.blink_rate_per_minute(
                120.0
            )
        )

        self.assertAlmostEqual(
            rate,
            5.0,
        )

    def test_invalid_active_time_returns_none(
        self,
    ):
        self.service.total_blinks = 10

        self.assertIsNone(
            self.service.blink_rate_per_minute(
                0
            )
        )

        self.assertIsNone(
            self.service.blink_rate_per_minute(
                None
            )
        )

        self.assertIsNone(
            self.service.blink_rate_per_minute(
                True
            )
        )


if __name__ == "__main__":
    unittest.main()