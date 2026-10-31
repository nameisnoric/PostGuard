"""Camera Roll contract tests.

Final PostGuard Camera Setup design
-----------------------------------

Normal workflow:

    Camera
        ↓
    Automatic Camera Roll detection
        ↓
    Stabilize multiple measurements
        ↓
    Lock one correction
        ↓
    Corrected / borderless image
        ↓
    Reference Card
        ↓
    Personal Baseline
        ↓
    Monitoring

Manual Roll is only a fallback / override.

Important conventions
---------------------

INTERNAL / OpenCV contract:

    internal detected +X°
        -> correction -X°

    internal detected -X°
        -> correction +X°

UI / physical camera convention:

    displayed physical angle
        = -internal detected angle

This display conversion MUST NOT change the correction actually
stored in Camera Reference.

Camera Setup, Personal Baseline and Monitoring must all use
the same prepare_frame() transformation.
"""

import os
import unittest

from unittest.mock import (
    MagicMock,
    patch,
)

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

import cv2
import numpy as np

from PySide6.QtWidgets import (
    QApplication,
)

from app.services.camera_setup import (
    roll_correction,
)

from app.services.camera_setup.roll_correction import (
    AUTO_MAX_ATTEMPTS,
    AUTO_WINDOW,
    ROLL_SOURCE_AUTO,
    ROLL_SOURCE_USER,
    AutoRollCollector,
    correction_from_detected_tilt,
    detect_camera_tilt,
    level_frame,
    prepare_frame,
)

from app.ui.pages.baseline_page import (
    BaselinePage,
)

from app.ui.pages.camera_calibration_page import (
    ESTIMATE_EVERY_N_FRAMES,
    CameraCalibrationPage,
    display_camera_tilt_deg,
    display_image_rotation_deg,
)

from app.ui.pages.monitoring_page import (
    MonitoringPage,
)
from app.vision.camera_setup.camera_reference_contract import (
    CameraReferenceError,
    lock_camera_reference,
    prepare_detection_frame,
)


# ============================================================
# TEST HELPERS
# ============================================================

def line_frame(
    width=320,
    height=180,
):
    """
    Black frame containing one horizontal white line.
    """

    frame = np.zeros(
        (
            height,
            width,
            3,
        ),
        dtype=np.uint8,
    )

    frame[
        height // 2 - 1:
        height // 2 + 1,
        :
    ] = 255

    return frame


def line_angle_deg(
    frame,
):
    """
    Measure the angle of bright pixels.

    Used only for deterministic synthetic unit testing.
    """

    ys, xs = np.nonzero(
        frame[
            :,
            :,
            0,
        ]
        >
        128
    )

    slope = np.polyfit(
        xs,
        ys,
        1,
    )[0]

    return float(
        np.degrees(
            np.arctan(
                slope
            )
        )
    )


def room_frame(
    width=640,
    height=360,
):
    """
    Synthetic level room containing many horizontal
    and vertical structural lines.

    This is a deterministic unit-test fixture,
    not a replacement for real-camera validation.
    """

    frame = np.zeros(
        (
            height,
            width,
            3,
        ),
        dtype=np.uint8,
    )

    for y in range(
        40,
        height - 30,
        50,
    ):
        cv2.line(
            frame,
            (
                0,
                y,
            ),
            (
                width,
                y,
            ),
            (
                255,
                255,
                255,
            ),
            3,
        )

    for x in range(
        60,
        width - 30,
        70,
    ):
        cv2.line(
            frame,
            (
                x,
                0,
            ),
            (
                x,
                height,
            ),
            (
                255,
                255,
                255,
            ),
            3,
        )

    return frame


def camera_rolled(
    frame,
    roll_deg,
):
    """
    Deterministic synthetic image rotation.

    This helper validates the INTERNAL/OpenCV correction contract.

    It does not define the +/- convention used by a phone
    inclinometer or other physical measurement tool.
    """

    return level_frame(
        frame,
        float(
            roll_deg
        ),
    )


def reference(
    deg,
    source,
):
    """
    Minimal Camera Reference Roll fields.
    """

    return {
        "roll_correction_deg":
            deg,

        "roll_correction_source":
            source,
    }


# ============================================================
# LEVEL FRAME
# ============================================================

class LevelFrameTests(
    unittest.TestCase
):

    def test_zero_angle_returns_frame_unchanged(
        self,
    ):
        frame = line_frame()

        self.assertIs(
            level_frame(
                frame,
                0.0,
            ),
            frame,
        )

    def test_rotation_keeps_output_size(
        self,
    ):
        frame = line_frame()

        rotated = level_frame(
            frame,
            7.5,
        )

        self.assertEqual(
            rotated.shape,
            (
                180,
                320,
                3,
            ),
        )

    def test_positive_rotation_changes_line_angle(
        self,
    ):
        frame = line_frame()

        rotated = level_frame(
            frame,
            6.0,
        )

        self.assertAlmostEqual(
            abs(
                line_angle_deg(
                    rotated
                )
            ),
            6.0,
            delta=0.5,
        )

    def test_plus_6_then_minus_6_returns_close_to_level(
        self,
    ):
        frame = line_frame()

        tilted = level_frame(
            frame,
            6.0,
        )

        restored = level_frame(
            tilted,
            -6.0,
        )

        self.assertAlmostEqual(
            line_angle_deg(
                restored
            ),
            0.0,
            delta=0.5,
        )

    def test_borderless_rotation_keeps_output_size(
        self,
    ):
        """
        The production design intentionally zooms slightly after
        rotation so large black corners are not visible.

        Output width and height must remain unchanged.
        """

        white = np.full(
            (
                180,
                320,
                3,
            ),
            255,
            dtype=np.uint8,
        )

        rotated = level_frame(
            white,
            5.0,
        )

        self.assertEqual(
            rotated.shape,
            white.shape,
        )

        # Center must remain valid.
        self.assertTrue(
            (
                rotated[
                    90,
                    160,
                ]
                >
                200
            ).all()
        )

        # Borderless zoom should prevent a large black corner.
        self.assertTrue(
            (
                rotated[
                    0,
                    0,
                ]
                >
                100
            ).all()
        )


# ============================================================
# SIGN CONVENTION
# ============================================================

class SignConventionTests(
    unittest.TestCase
):

    def test_correction_is_minus_internal_detected_tilt(
        self,
    ):
        self.assertEqual(
            correction_from_detected_tilt(
                -2.5
            ),
            2.5,
        )

        self.assertEqual(
            correction_from_detected_tilt(
                2.5
            ),
            -2.5,
        )

    def test_positive_and_negative_internal_roll_are_both_corrected(
        self,
    ):
        room = room_frame()

        for synthetic_roll in (
            +3.0,
            -3.0,
        ):
            scene = camera_rolled(
                room,
                synthetic_roll,
            )

            detected = detect_camera_tilt(
                scene
            )

            self.assertIsNotNone(
                detected
            )

            self.assertAlmostEqual(
                detected,
                synthetic_roll,
                delta=0.5,
            )

            correction = (
                correction_from_detected_tilt(
                    detected
                )
            )

            self.assertAlmostEqual(
                correction,
                -synthetic_roll,
                delta=0.5,
            )

            fixed = level_frame(
                scene,
                correction,
            )

            fixed_detected = (
                detect_camera_tilt(
                    fixed
                )
            )

            self.assertIsNotNone(
                fixed_detected
            )

            self.assertAlmostEqual(
                fixed_detected,
                0.0,
                delta=0.5,
            )

    def test_ui_camera_tilt_uses_physical_angle_convention(
        self,
    ):
        """
        UI physical angle intentionally uses the opposite sign
        from the internal/OpenCV estimator.
        """

        self.assertEqual(
            display_camera_tilt_deg(
                4.0
            ),
            -4.0,
        )

        self.assertEqual(
            display_camera_tilt_deg(
                -4.0
            ),
            4.0,
        )

        self.assertEqual(
            display_camera_tilt_deg(
                0.0
            ),
            0.0,
        )

    def test_ui_camera_tilt_handles_none(
        self,
    ):
        self.assertIsNone(
            display_camera_tilt_deg(
                None
            )
        )

    def test_ui_image_rotation_keeps_internal_correction_sign(
        self,
    ):
        self.assertEqual(
            display_image_rotation_deg(
                -4.0
            ),
            -4.0,
        )

        self.assertEqual(
            display_image_rotation_deg(
                4.0
            ),
            4.0,
        )

        self.assertEqual(
            display_image_rotation_deg(
                -0.0
            ),
            0.0,
        )

    def test_ui_image_rotation_handles_none(
        self,
    ):
        self.assertIsNone(
            display_image_rotation_deg(
                None
            )
        )


# ============================================================
# PREPARE FRAME
# ============================================================

class PrepareFrameTests(
    unittest.TestCase
):

    def test_no_reference_means_no_rotation(
        self,
    ):
        frame = line_frame()

        self.assertIs(
            prepare_frame(
                frame,
                None,
            ),
            frame,
        )

        self.assertIs(
            prepare_frame(
                frame,
                {},
            ),
            frame,
        )

    def test_uses_roll_correction_deg_from_camera_reference(
        self,
    ):
        frame = line_frame()

        calibration = reference(
            3.0,
            ROLL_SOURCE_AUTO,
        )

        got = prepare_frame(
            frame,
            calibration,
        )

        expected = level_frame(
            frame,
            3.0,
        )

        self.assertTrue(
            np.array_equal(
                got,
                expected,
            )
        )

    def test_card_roll_alone_never_rotates_frame(
        self,
    ):
        frame = line_frame()

        got = prepare_frame(
            frame,
            {
                "card_roll_deg":
                    4.0,
            },
        )

        self.assertIs(
            got,
            frame,
        )

    def test_angle_without_confirmed_source_is_ignored(
        self,
    ):
        frame = line_frame()

        self.assertIs(
            prepare_frame(
                frame,
                {
                    "roll_correction_deg":
                        3.0,
                },
            ),
            frame,
        )

        self.assertIs(
            prepare_frame(
                frame,
                reference(
                    3.0,
                    "GUESS",
                ),
            ),
            frame,
        )

    def test_auto_confirmed_correction_is_used(
        self,
    ):
        frame = line_frame()

        got = prepare_frame(
            frame,
            reference(
                -2.0,
                ROLL_SOURCE_AUTO,
            ),
        )

        expected = level_frame(
            frame,
            -2.0,
        )

        self.assertTrue(
            np.array_equal(
                got,
                expected,
            )
        )

    def test_user_confirmed_correction_is_used(
        self,
    ):
        frame = line_frame()

        got = prepare_frame(
            frame,
            reference(
                1.5,
                ROLL_SOURCE_USER,
            ),
        )

        expected = level_frame(
            frame,
            1.5,
        )

        self.assertTrue(
            np.array_equal(
                got,
                expected,
            )
        )


# ============================================================
# AUTO ROLL COLLECTOR
# ============================================================

class AutoRollCollectorTests(
    unittest.TestCase
):

    @staticmethod
    def feed(
        values,
    ):
        iterator = iter(
            values
        )

        return AutoRollCollector(
            estimator=lambda _frame:
                next(
                    iterator
                )
        )

    def test_locks_median_of_stable_values_even_with_gaps(
        self,
    ):
        values = [
            -2.4,
            -2.6,
            -2.5,
            None,
            -2.4,
            -2.5,
            -2.6,
            None,
            -2.5,
            -2.4,
            -2.5,
            -2.6,
        ]

        collector = self.feed(
            values
        )

        for _ in values:
            collector.add(
                None
            )

        self.assertEqual(
            collector.status,
            AutoRollCollector.AUTO,
        )

        self.assertAlmostEqual(
            collector.detected_camera_tilt_deg,
            -2.5,
            places=6,
        )

        self.assertAlmostEqual(
            collector.roll_correction_deg,
            2.5,
            places=6,
        )

    def test_candidate_is_available_before_lock(
        self,
    ):
        collector = AutoRollCollector(
            estimator=lambda _frame:
                -4.25
        )

        collector.add(
            None
        )

        self.assertEqual(
            collector.status,
            AutoRollCollector.DETECTING,
        )

        self.assertAlmostEqual(
            collector.latest_detected_camera_tilt_deg,
            -4.25,
            places=6,
        )

        self.assertAlmostEqual(
            collector.latest_candidate_correction_deg,
            4.25,
            places=6,
        )

        self.assertIsNone(
            collector.roll_correction_deg
        )

    def test_lock_does_not_change_with_later_frames(
        self,
    ):
        values = (
            [-2.5] * AUTO_WINDOW
            +
            [7.0] * 20
        )

        collector = self.feed(
            values
        )

        for _ in range(
            AUTO_WINDOW
        ):
            collector.add(
                None
            )

        self.assertEqual(
            collector.status,
            AutoRollCollector.AUTO,
        )

        locked = (
            collector.roll_correction_deg
        )

        for _ in range(
            20
        ):
            collector.add(
                None
            )

        self.assertEqual(
            collector.status,
            AutoRollCollector.AUTO,
        )

        self.assertEqual(
            collector.roll_correction_deg,
            locked,
        )

    def test_estimator_is_not_called_again_after_lock(
        self,
    ):
        calls = []

        def estimator(
            _frame,
        ):
            calls.append(
                1
            )

            return -2.5

        collector = AutoRollCollector(
            estimator=estimator
        )

        for _ in range(
            AUTO_WINDOW
        ):
            collector.add(
                None
            )

        before = len(
            calls
        )

        for _ in range(
            10
        ):
            collector.add(
                None
            )

        self.assertEqual(
            len(
                calls
            ),
            before,
        )

    def test_unstable_estimates_become_unavailable(
        self,
    ):
        values = [
            (
                -4.0
                if i % 2
                else
                4.0
            )
            for i
            in range(
                AUTO_MAX_ATTEMPTS
            )
        ]

        collector = self.feed(
            values
        )

        for _ in values:
            collector.add(
                None
            )

        self.assertEqual(
            collector.status,
            AutoRollCollector.UNAVAILABLE,
        )

        self.assertIsNone(
            collector.roll_correction_deg
        )

    def test_no_lines_become_unavailable(
        self,
    ):
        collector = AutoRollCollector(
            estimator=lambda _frame:
                None
        )

        for _ in range(
            AUTO_MAX_ATTEMPTS
        ):
            collector.add(
                None
            )

        self.assertEqual(
            collector.status,
            AutoRollCollector.UNAVAILABLE,
        )

        self.assertIsNone(
            collector.roll_correction_deg
        )


# ============================================================
# CAMERA CALIBRATION PAGE
# ============================================================

class CalibrationPageTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or
            QApplication([])
        )

    def setUp(
        self,
    ):
        self.page = (
            CameraCalibrationPage()
        )

        self.card = {
            "status":
                "VALID",

            "scale_avg":
                3.5,

            "frame_width":
                640,

            "frame_height":
                360,

            "card_roll_deg":
                0.5,

            "horizontal_perspective":
                0.0,

            "vertical_perspective":
                0.0,
        }

        patcher = patch(
            "app.ui.pages.camera_calibration_page."
            "QMessageBox.information"
        )

        patcher.start()

        self.addCleanup(
            patcher.stop
        )

    def run_frames(
        self,
        frame,
        count=None,
    ):
        if count is None:
            count = (
                ESTIMATE_EVERY_N_FRAMES
                *
                AUTO_MAX_ATTEMPTS
                +
                3
            )

        self.page.capture = (
            MagicMock()
        )

        self.page.capture.isOpened.return_value = (
            True
        )

        self.page.capture.read.return_value = (
            True,
            frame.copy(),
        )

        for _ in range(
            count
        ):
            self.page.update_frame()

            if (
                self.page.locked_roll
                is not None
            ):
                break

    def test_initial_status_is_detecting(
        self,
    ):
        self.assertIn(
            "กำลังตรวจสอบ",
            self.page.alignment_label.text(),
        )

        self.assertIsNone(
            self.page.locked_roll
        )

    def test_auto_locks_correction_then_card_stage_starts(
        self,
    ):
        self.assertIn(
            "กำลังตรวจสอบ",
            self.page.alignment_label.text(),
        )

        self.run_frames(
            camera_rolled(
                room_frame(),
                3.0,
            )
        )

        locked = (
            self.page.locked_roll
        )

        self.assertIsNotNone(
            locked
        )

        self.assertEqual(
            locked[
                "source"
            ],
            ROLL_SOURCE_AUTO,
        )

        # Internal estimator contract.
        self.assertAlmostEqual(
            locked[
                "detected"
            ],
            3.0,
            delta=0.5,
        )

        # Internal/OpenCV correction contract.
        self.assertAlmostEqual(
            locked[
                "deg"
            ],
            -3.0,
            delta=0.5,
        )

        # Friendly user-facing state.
        self.assertIn(
            "ปรับอัตโนมัติเรียบร้อย",
            self.page.alignment_label.text(),
        )

        self.assertIn(
            "มุมกล้องที่ระบบประเมิน",
            self.page.detected_label.text(),
        )

        self.assertIn(
            "การหมุนภาพที่ใช้",
            self.page.applied_label.text(),
        )

        # Manual is not the normal workflow.
        self.assertTrue(
            self.page.manual_panel.isHidden()
        )

    def test_auto_success_tells_user_to_place_card(
        self,
    ):
        self.run_frames(
            camera_rolled(
                room_frame(),
                3.0,
            )
        )

        self.assertIn(
            "วางบัตร",
            self.page.guidance_label.text(),
        )

    def test_auto_estimator_stops_after_lock(
        self,
    ):
        self.run_frames(
            camera_rolled(
                room_frame(),
                3.0,
            )
        )

        locked = dict(
            self.page.locked_roll
        )

        with patch.object(
            roll_correction,
            "estimate_scene_tilt",
        ) as estimator:

            self.run_frames(
                camera_rolled(
                    room_frame(),
                    -6.0,
                ),
                count=(
                    ESTIMATE_EVERY_N_FRAMES
                    *
                    5
                ),
            )

        estimator.assert_not_called()

        self.assertEqual(
            self.page.locked_roll,
            locked,
        )

    def test_card_is_measured_on_corrected_frame(
        self,
    ):
        raw = camera_rolled(
            room_frame(),
            3.0,
        )

        self.run_frames(
            raw
        )

        fields = (
            self.page.roll_fields()
        )

        seen = {}

        original = (
            self.page.tracker.process
        )

        def spy(
            frame,
        ):
            seen[
                "frame"
            ] = frame.copy()

            return original(
                frame
            )

        self.page.tracker.process = (
            spy
        )

        self.page.update_frame()

        expected = cv2.flip(
            prepare_frame(
                raw,
                fields,
            ),
            1,
        )

        self.assertTrue(
            np.array_equal(
                seen[
                    "frame"
                ],
                expected,
            )
        )

    def test_auto_unavailable_enters_manual_fallback(
        self,
    ):
        self.run_frames(
            np.zeros(
                (
                    360,
                    640,
                    3,
                ),
                dtype=np.uint8,
            )
        )

        self.assertIsNone(
            self.page.locked_roll
        )

        self.assertTrue(
            self.page.manual_mode
        )

        self.assertFalse(
            self.page.manual_panel.isHidden()
        )

        self.assertIn(
            "ปรับด้วยตนเอง",
            self.page.alignment_label.text(),
        )

    def test_manual_mode_tells_user_to_rotate_image_not_camera(
        self,
    ):
        self.page.start_manual_roll()

        text = (
            self.page.roll_hint_label.text()
        )

        self.assertIn(
            "หมุนภาพ",
            text,
        )

        self.assertIn(
            "ไม่ต้องหมุนกล้องจริง",
            text,
        )

    def test_manual_confirm_locks_user_confirmed_correction(
        self,
    ):
        self.page.start_manual_roll()

        # 5 steps × 0.5° = +2.5°
        self.page.roll_slider.setValue(
            5
        )

        self.page.confirm_roll()

        self.assertEqual(
            self.page.roll_fields(),
            reference(
                2.5,
                ROLL_SOURCE_USER,
            ),
        )

        self.assertTrue(
            self.page.manual_panel.isHidden()
        )

        card = (
            self.card.copy()
        )

        card.update(
            self.page.roll_fields()
        )

        self.page._complete_preparation(
            card
        )

        self.assertEqual(
            self.page.calibration_reference[
                "roll_correction_source"
            ],
            ROLL_SOURCE_USER,
        )

        self.assertEqual(
            self.page.calibration_reference[
                "roll_correction_deg"
            ],
            2.5,
        )

    def test_manual_locked_ui_does_not_claim_auto_measurement(
        self,
    ):
        self.page.start_manual_roll()

        self.page.roll_slider.setValue(
            4
        )

        self.page.confirm_roll()

        self.assertIn(
            "ปรับด้วยตนเอง",
            self.page.detected_label.text(),
        )

        self.assertIn(
            "+2.00°",
            self.page.applied_label.text(),
        )

    def test_manual_confirmation_tells_user_to_place_card(
        self,
    ):
        self.page.start_manual_roll()

        self.page.roll_slider.setValue(
            2
        )

        self.page.confirm_roll()

        self.assertIn(
            "วางบัตร",
            self.page.guidance_label.text(),
        )

    def test_changing_correction_after_card_invalidates_card_reference(
        self,
    ):
        self.page._lock_roll(
            -2.0,
            ROLL_SOURCE_AUTO,
            2.0,
        )

        card = (
            self.card.copy()
        )

        card.update(
            self.page.roll_fields()
        )

        self.page._complete_preparation(
            card
        )

        self.assertTrue(
            self.page.continue_button.isEnabled()
        )

        # User overrides Auto.
        self.page.start_manual_roll()

        self.assertIsNone(
            self.page.calibration_reference
        )

        self.assertFalse(
            self.page.continue_button.isEnabled()
        )

        self.assertIsNone(
            self.page.locked_roll
        )

        received = []

        self.page.continue_requested.connect(
            lambda *args:
                received.append(
                    args
                )
        )

        self.page.selected_camera = {
            "camera_id":
                1,
        }

        self.page.handle_continue()

        self.assertEqual(
            received,
            [],
        )

    def test_continue_requires_locked_roll_reference(
        self,
    ):
        received = []

        self.page.continue_requested.connect(
            lambda *args:
                received.append(
                    args
                )
        )

        self.page.selected_camera = {
            "camera_id":
                1,
        }

        # Card reference without Camera Roll lock.
        self.page._complete_preparation(
            self.card
        )

        self.page.handle_continue()

        self.assertEqual(
            received,
            [],
        )

        card = (
            self.card.copy()
        )

        card.update(
            reference(
                1.0,
                ROLL_SOURCE_AUTO,
            )
        )

        self.page._complete_preparation(
            card
        )

        self.page.handle_continue()

        self.assertEqual(
            len(
                received
            ),
            1,
        )

    def test_complete_preparation_enables_continue_button(
        self,
    ):
        card = (
            self.card.copy()
        )

        card.update(
            reference(
                1.0,
                ROLL_SOURCE_AUTO,
            )
        )

        self.page._complete_preparation(
            card
        )

        self.assertTrue(
            self.page.continue_button.isEnabled()
        )

    def test_restart_returns_to_auto_detection(
        self,
    ):
        self.page._lock_roll(
            1.0,
            ROLL_SOURCE_USER,
        )

        self.page.restart_preparation()

        self.assertIsNone(
            self.page.locked_roll
        )

        self.assertEqual(
            self.page.auto_roll.status,
            AutoRollCollector.DETECTING,
        )

        self.assertIn(
            "กำลังตรวจสอบ",
            self.page.alignment_label.text(),
        )


# ============================================================
# BASELINE + MONITORING
# ============================================================

class _StopAfterDetector(Exception):
    pass


def canonical_camera(
    correction_deg=0.0,
    source=ROLL_SOURCE_AUTO,
    *,
    width=640,
    height=360,
):
    """
    Build a complete production-style locked Camera Reference.

    Baseline and Monitoring must use the same camera identity,
    resolution, card reference, and roll correction contract.
    """

    camera = {
        "camera_id": 1,
        "device_index": 0,
        "device_id": "opencv-index:0",
        "camera_name": "Test Camera",
        "resolution_width": width,
        "resolution_height": height,
    }

    card_reference = {
        "status": "VALID",
        "frame_width": width,
        "frame_height": height,
        "scale_x": 3.5,
        "scale_y": 3.5,
        "scale_avg": 3.5,
        "card_roll_deg": 0.25,
        "horizontal_perspective": 0.0,
        "vertical_perspective": 0.0,
        "captured_at": "2026-10-31T00:00:00+00:00",
        "roll_correction_deg": float(correction_deg),
        "roll_correction_source": source,
    }

    locked_reference = lock_camera_reference(
        camera,
        card_reference,
        roll_correction_deg=float(correction_deg),
        roll_correction_source=source,
    )

    camera["camera_calibration"] = locked_reference

    return camera


class DetectorInputTests(unittest.TestCase):
    """
    Personal Baseline and Monitoring must hand DetectionService
    the same corrected, non-mirrored frame.

    Invalid Camera References must fail closed and must not
    silently reach DetectionService.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _frame_seen_by_detector(
        self,
        page,
        frame,
        camera,
    ):
        seen = {}

        def grab(received):
            seen["frame"] = received.copy()
            raise _StopAfterDetector()

        page.selected_camera = camera

        page.capture = MagicMock()
        page.capture.read.return_value = (
            True,
            frame.copy(),
        )

        page.detector = MagicMock()
        page.detector.process_frame.side_effect = grab

        # Detection executes every fifth frame.
        page.frame_count = 4

        # Camera movement is covered by a separate test suite.
        if isinstance(page, MonitoringPage):
            page.is_paused = False
            page.is_stopping = False

            page.camera_movement_guard = MagicMock()
            page.camera_movement_guard.update.return_value = {
                "status": "STABLE",
            }

        with (
            patch(
                "PySide6.QtWidgets.QMessageBox.warning"
            ),
            patch(
                "PySide6.QtWidgets.QMessageBox.critical"
            ),
        ):
            try:
                page.update_frame()
            except _StopAfterDetector:
                pass

        return seen.get("frame")

    def test_baseline_and_monitoring_receive_identical_corrected_frames(
        self,
    ):
        frame = room_frame()

        camera = canonical_camera(
            correction_deg=4.0,
            source=ROLL_SOURCE_AUTO,
        )

        expected = prepare_detection_frame(
            frame.copy(),
            camera,
        )

        baseline = self._frame_seen_by_detector(
            BaselinePage(),
            frame,
            camera,
        )

        monitoring = self._frame_seen_by_detector(
            MonitoringPage(),
            frame,
            camera,
        )

        self.assertIsNotNone(baseline)
        self.assertIsNotNone(monitoring)

        self.assertTrue(
            np.array_equal(
                baseline,
                monitoring,
            )
        )

        self.assertTrue(
            np.array_equal(
                baseline,
                expected,
            )
        )

        self.assertFalse(
            np.array_equal(
                baseline,
                frame,
            )
        )

    def test_auto_correction_reaches_baseline(
        self,
    ):
        frame = room_frame()

        camera = canonical_camera(
            correction_deg=3.5,
            source=ROLL_SOURCE_AUTO,
        )

        expected = prepare_detection_frame(
            frame.copy(),
            camera,
        )

        seen = self._frame_seen_by_detector(
            BaselinePage(),
            frame,
            camera,
        )

        self.assertIsNotNone(seen)

        self.assertTrue(
            np.array_equal(
                seen,
                expected,
            )
        )

    def test_auto_correction_reaches_monitoring(
        self,
    ):
        frame = room_frame()

        camera = canonical_camera(
            correction_deg=-3.5,
            source=ROLL_SOURCE_AUTO,
        )

        expected = prepare_detection_frame(
            frame.copy(),
            camera,
        )

        seen = self._frame_seen_by_detector(
            MonitoringPage(),
            frame,
            camera,
        )

        self.assertIsNotNone(seen)

        self.assertTrue(
            np.array_equal(
                seen,
                expected,
            )
        )

    def test_manual_correction_reaches_both_detectors(
        self,
    ):
        frame = room_frame()

        camera = canonical_camera(
            correction_deg=-1.5,
            source=ROLL_SOURCE_USER,
        )

        expected = prepare_detection_frame(
            frame.copy(),
            camera,
        )

        for page in (
            BaselinePage(),
            MonitoringPage(),
        ):
            seen = self._frame_seen_by_detector(
                page,
                frame,
                camera,
            )

            self.assertIsNotNone(
                seen,
                type(page).__name__,
            )

            self.assertTrue(
                np.array_equal(
                    seen,
                    expected,
                ),
                type(page).__name__,
            )

    def test_card_roll_alone_leaves_detector_frame_untouched(
        self,
    ):
        """
        Card orientation is not Camera Roll.

        Camera correction is 0°, while card orientation is 4°.
        The detector frame must therefore remain unchanged.
        """

        frame = room_frame()

        camera = canonical_camera(
            correction_deg=0.0,
            source=ROLL_SOURCE_AUTO,
        )

        camera["camera_calibration"]["card_roll_deg"] = 4.0

        expected = prepare_detection_frame(
            frame.copy(),
            camera,
        )

        self.assertTrue(
            np.array_equal(
                expected,
                frame,
            )
        )

        for page in (
            BaselinePage(),
            MonitoringPage(),
        ):
            seen = self._frame_seen_by_detector(
                page,
                frame,
                camera,
            )

            self.assertIsNotNone(
                seen,
                type(page).__name__,
            )

            self.assertTrue(
                np.array_equal(
                    seen,
                    frame,
                ),
                type(page).__name__,
            )

    def test_unconfirmed_roll_does_not_reach_detector(
        self,
    ):
        """
        Invalid roll source must be rejected.

        Old behavior:
            invalid reference -> raw frame silently continues

        New behavior:
            invalid reference -> detector receives no frame
        """

        frame = room_frame()

        camera = {
            "camera_id": 1,
            "device_index": 0,
            "device_id": "opencv-index:0",
            "camera_name": "Test Camera",
            "resolution_width": 640,
            "resolution_height": 360,
            "camera_calibration": {
                "status": "VALID",
                "frame_width": 640,
                "frame_height": 360,
                "scale_x": 3.5,
                "scale_y": 3.5,
                "scale_avg": 3.5,
                "card_roll_deg": 0.0,
                "horizontal_perspective": 0.0,
                "vertical_perspective": 0.0,
                "roll_correction_deg": 5.0,
                "roll_correction_source": "GUESS",
            },
        }

        with self.assertRaises(
            CameraReferenceError
        ):
            prepare_detection_frame(
                frame.copy(),
                camera,
            )

        baseline_seen = self._frame_seen_by_detector(
            BaselinePage(),
            frame,
            camera,
        )

        monitoring_seen = self._frame_seen_by_detector(
            MonitoringPage(),
            frame,
            camera,
        )

        self.assertIsNone(baseline_seen)
        self.assertIsNone(monitoring_seen)

    def test_auto_and_manual_sources_are_both_valid_locked_references(
        self,
    ):
        frame = room_frame()

        for source in (
            ROLL_SOURCE_AUTO,
            ROLL_SOURCE_USER,
        ):
            camera = canonical_camera(
                correction_deg=2.0,
                source=source,
            )

            prepared = prepare_detection_frame(
                frame.copy(),
                camera,
            )

            self.assertIsNotNone(prepared)
            self.assertEqual(
                prepared.shape,
                frame.shape,
            )


if __name__ == "__main__":
    unittest.main()
