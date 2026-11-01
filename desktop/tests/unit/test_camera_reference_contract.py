import unittest

import numpy as np

from app.vision.camera_setup.camera_reference_contract import (
    CARD_VALID,
    CAMERA_REFERENCE_LOCKED,
    CAMERA_SETUP_CONFIRMED,
    ROLL_CORRECTION_USER_CONFIRMED,
    CameraReferenceError,
    lock_camera_reference,
    prepare_detection_frame,
    validate_locked_camera_reference,
)
from app.vision.camera_setup.camera_roll import level_frame


class CameraReferenceContractTests(unittest.TestCase):

    def make_camera(self):
        return {
            "camera_id": 10,
            "device_index": 0,
            "device_id": "opencv-index:0",
            "camera_name": "Test Camera",
            "resolution_width": 1280,
            "resolution_height": 720,
        }

    def make_card_reference(self):
        return {
            "status": "VALID",
            "frame_width": 1280,
            "frame_height": 720,
            "scale_x": 5.1,
            "scale_y": 5.0,
            "scale_avg": 5.05,
            "card_roll_deg": 2.5,
            "horizontal_perspective": 0.03,
            "vertical_perspective": 0.04,
            "captured_at": "2026-10-31T00:00:00+00:00",
        }

    def make_locked_camera(self, correction=0.0):
        camera = self.make_camera()
        camera["camera_calibration"] = lock_camera_reference(
            camera,
            self.make_card_reference(),
            roll_correction_deg=correction,
            roll_correction_source=ROLL_CORRECTION_USER_CONFIRMED,
        )
        return camera

    def test_lock_reference_separates_states(self):
        camera = self.make_camera()

        locked = lock_camera_reference(
            camera,
            self.make_card_reference(),
            roll_correction_deg=0.0,
            roll_correction_source=ROLL_CORRECTION_USER_CONFIRMED,
        )

        self.assertEqual(locked["card_reference_status"], CARD_VALID)
        self.assertEqual(
            locked["camera_setup_status"],
            CAMERA_SETUP_CONFIRMED,
        )
        self.assertEqual(
            locked["camera_reference_status"],
            CAMERA_REFERENCE_LOCKED,
        )
        self.assertEqual(
            locked["roll_correction_status"],
            "ROLL_CORRECTION_CONFIRMED",
        )
        self.assertEqual(
            locked["roll_correction_source"],
            ROLL_CORRECTION_USER_CONFIRMED,
        )
        self.assertEqual(locked["roll_correction_deg"], 0.0)
        self.assertFalse(
            locked["preprocessing_contract"]["software_roll_correction"]
        )

    def test_card_roll_is_not_used_as_correction(self):
        camera = self.make_camera()
        reference = self.make_card_reference()
        reference["card_roll_deg"] = 4.0

        locked = lock_camera_reference(
            camera,
            reference,
            roll_correction_deg=-1.5,
            roll_correction_source=ROLL_CORRECTION_USER_CONFIRMED,
        )

        self.assertEqual(locked["card_roll_deg"], 4.0)
        self.assertEqual(locked["roll_correction_deg"], -1.5)

    def test_reference_resolution_must_match_camera(self):
        camera = self.make_camera()
        reference = self.make_card_reference()
        reference["frame_width"] = 640

        with self.assertRaises(CameraReferenceError):
            lock_camera_reference(
                camera,
                reference,
                roll_correction_source=ROLL_CORRECTION_USER_CONFIRMED,
            )

    def test_locked_reference_is_valid(self):
        camera = self.make_locked_camera(correction=2.5)

        reference = validate_locked_camera_reference(camera)

        self.assertEqual(
            reference["camera_reference_status"],
            CAMERA_REFERENCE_LOCKED,
        )
        self.assertEqual(
            reference["roll_correction_deg"],
            2.5,
        )

    def test_camera_change_invalidates_reference(self):
        camera = self.make_locked_camera()
        camera["device_index"] = 1

        with self.assertRaises(CameraReferenceError):
            validate_locked_camera_reference(camera)

    def test_resolution_change_invalidates_reference(self):
        camera = self.make_locked_camera()
        camera["resolution_width"] = 640

        with self.assertRaises(CameraReferenceError):
            validate_locked_camera_reference(camera)

    def test_unconfirmed_roll_status_is_rejected(self):
        camera = self.make_locked_camera(correction=3.0)
        camera["camera_calibration"]["roll_correction_status"] = (
            "NOT_VALIDATED"
        )

        with self.assertRaises(CameraReferenceError):
            validate_locked_camera_reference(camera)

    def test_non_finite_roll_is_rejected(self):
        camera = self.make_camera()

        with self.assertRaises(CameraReferenceError):
            lock_camera_reference(
                camera,
                self.make_card_reference(),
                roll_correction_deg=float("nan"),
                roll_correction_source=ROLL_CORRECTION_USER_CONFIRMED,
            )

    def test_prepare_detection_frame_keeps_zero_roll_raw_frame(self):
        camera = self.make_locked_camera(correction=0.0)
        frame = np.zeros(
            (720, 1280, 3),
            dtype=np.uint8,
        )

        result = prepare_detection_frame(
            frame,
            camera,
        )

        self.assertIs(result, frame)

    def test_prepare_detection_frame_applies_confirmed_roll(self):
        camera = self.make_locked_camera(correction=3.0)
        frame = np.zeros(
            (720, 1280, 3),
            dtype=np.uint8,
        )
        frame[100:150, 200:260] = 255

        result = prepare_detection_frame(
            frame,
            camera,
        )

        expected = level_frame(
            frame,
            3.0,
            remove_black_border=True,
        )

        np.testing.assert_array_equal(
            result,
            expected,
        )

    def test_actual_frame_resolution_is_checked(self):
        camera = self.make_locked_camera()
        wrong_frame = np.zeros(
            (480, 640, 3),
            dtype=np.uint8,
        )

        with self.assertRaises(CameraReferenceError):
            prepare_detection_frame(
                wrong_frame,
                camera,
            )


if __name__ == "__main__":
    unittest.main()
