"""Unit tests for Monitoring Camera Movement Guard."""

import unittest

import cv2
import numpy as np

from app.services.camera_setup.camera_movement import (
    CameraMovementConfig,
    CameraMovementGuard,
    STATUS_MOVED,
)


def room_frame(
    width=640,
    height=360,
):
    """
    Synthetic background with many stable structural features.
    """

    frame = np.zeros(
        (
            height,
            width,
            3,
        ),
        dtype=np.uint8,
    )

    for x in range(
        20,
        width,
        40,
    ):
        cv2.line(
            frame,
            (
                x,
                0,
            ),
            (
                x,
                height - 1,
            ),
            (
                255,
                255,
                255,
            ),
            2,
        )

    for y in range(
        20,
        height,
        40,
    ):
        cv2.line(
            frame,
            (
                0,
                y,
            ),
            (
                width - 1,
                y,
            ),
            (
                255,
                255,
                255,
            ),
            2,
        )

    return frame


def translate_frame(
    frame,
    dx,
    dy,
):
    matrix = np.float32(
        [
            [
                1,
                0,
                dx,
            ],
            [
                0,
                1,
                dy,
            ],
        ]
    )

    return cv2.warpAffine(
        frame,
        matrix,
        (
            frame.shape[1],
            frame.shape[0],
        ),
    )


class CameraMovementGuardTests(
    unittest.TestCase
):

    def make_guard(
        self,
    ):
        return CameraMovementGuard(
            CameraMovementConfig(
                sample_every_frames=1,
                consecutive_hits=2,
            )
        )

    def test_stable_camera_does_not_trigger(
        self,
    ):
        guard = (
            self.make_guard()
        )

        frame = (
            room_frame()
        )

        for _ in range(
            8
        ):
            guard.update(
                frame
            )

        self.assertFalse(
            guard.moved
        )

    def test_global_translation_triggers_camera_movement(
        self,
    ):
        guard = (
            self.make_guard()
        )

        frame = (
            room_frame()
        )

        guard.update(
            frame
        )

        guard.update(
            translate_frame(
                frame,
                12,
                0,
            )
        )

        result = (
            guard.update(
                translate_frame(
                    frame,
                    24,
                    0,
                )
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            STATUS_MOVED,
        )

        self.assertTrue(
            guard.moved
        )

    def test_central_person_like_motion_does_not_trigger(
        self,
    ):
        guard = (
            self.make_guard()
        )

        frame = (
            room_frame()
        )

        guard.update(
            frame
        )

        for index in range(
            5
        ):
            changed = (
                frame.copy()
            )

            cv2.rectangle(
                changed,
                (
                    260
                    +
                    index
                    *
                    5,
                    120,
                ),
                (
                    380
                    +
                    index
                    *
                    5,
                    300,
                ),
                (
                    255,
                    255,
                    255,
                ),
                -1,
            )

            guard.update(
                changed
            )

        self.assertFalse(
            guard.moved
        )

    def test_movement_is_latched_even_if_camera_returns(
        self,
    ):
        """
        Important real-world contract.

        If the user:
            lifts laptop
            -> moves it
            -> puts it back

        the old session is still considered invalid.

        Returning the camera does not erase the movement event.
        """

        guard = (
            self.make_guard()
        )

        frame = (
            room_frame()
        )

        guard.update(
            frame
        )

        guard.update(
            translate_frame(
                frame,
                12,
                0,
            )
        )

        guard.update(
            translate_frame(
                frame,
                24,
                0,
            )
        )

        self.assertTrue(
            guard.moved
        )

        # Camera returns to original position.
        result = (
            guard.update(
                frame
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            STATUS_MOVED,
        )

        self.assertTrue(
            guard.moved
        )

    def test_reset_allows_new_camera_reference_period(
        self,
    ):
        guard = (
            self.make_guard()
        )

        frame = (
            room_frame()
        )

        guard.update(
            frame
        )

        guard.update(
            translate_frame(
                frame,
                12,
                0,
            )
        )

        guard.update(
            translate_frame(
                frame,
                24,
                0,
            )
        )

        self.assertTrue(
            guard.moved
        )

        guard.reset()

        self.assertFalse(
            guard.moved
        )


if __name__ == "__main__":
    unittest.main()