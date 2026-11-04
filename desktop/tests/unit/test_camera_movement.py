"""Unit tests for PostGuard Camera Movement Guard.

Testing strategy
----------------
The production guard contains two independent concerns:

1. Computer-vision measurement
   - LK optical flow
   - forward/backward consistency
   - RANSAC
   - adaptive spatial support

2. Production movement policy
   - moderate thresholds
   - strong thresholds
   - temporal confirmation

Synthetic image transforms are NOT expected to reproduce real camera
movement exactly.

Therefore:

- Production thresholds are tested directly through `_movement_policy`.
- Synthetic frames test the CV pipeline using synthetic-friendly
  thresholds.
- Stable camera and central person movement must never trigger.
"""

import unittest

import cv2
import numpy as np

from app.services.camera_setup.camera_movement import (
    CameraMovementConfig,
    CameraMovementGuard,
    STATUS_MOVED,
    STATUS_STABLE,
    STATUS_UNAVAILABLE,
)


# ============================================================
# SYNTHETIC SCENES
# ============================================================


def room_frame(
    width=640,
    height=360,
):
    """Feature-rich synthetic room."""

    frame = np.zeros(
        (
            height,
            width,
            3,
        ),
        dtype=np.uint8,
    )

    for y in range(
        20,
        height,
        35,
    ):
        for x in range(
            20,
            width,
            45,
        ):
            intensity = (
                100
                +
                (
                    (
                        x * 7
                        +
                        y * 3
                    )
                    %
                    155
                )
            )

            radius = (
                2
                +
                (
                    (
                        x + y
                    )
                    %
                    5
                )
            )

            cv2.circle(
                frame,
                (
                    x,
                    y,
                ),
                radius,
                (
                    intensity,
                    intensity,
                    intensity,
                ),
                -1,
            )

    cv2.line(
        frame,
        (
            10,
            15,
        ),
        (
            225,
            150,
        ),
        (
            230,
            230,
            230,
        ),
        3,
    )

    cv2.line(
        frame,
        (
            420,
            20,
        ),
        (
            628,
            155,
        ),
        (
            190,
            190,
            190,
        ),
        3,
    )

    cv2.rectangle(
        frame,
        (
            20,
            235,
        ),
        (
            145,
            345,
        ),
        (
            180,
            180,
            180,
        ),
        3,
    )

    cv2.rectangle(
        frame,
        (
            485,
            225,
        ),
        (
            625,
            345,
        ),
        (
            215,
            215,
            215,
        ),
        3,
    )

    cv2.putText(
        frame,
        "POST",
        (
            35,
            75,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (
            200,
            200,
            200,
        ),
        2,
    )

    cv2.putText(
        frame,
        "GUARD",
        (
            490,
            305,
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (
            200,
            200,
            200,
        ),
        2,
    )

    return frame


def right_side_room_frame(
    width=640,
    height=360,
):
    """
    Room with useful texture mainly on the right side.

    Used to validate adaptive spatial support.
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
        15,
        height,
        28,
    ):
        for x in range(
            400,
            width,
            29,
        ):
            intensity = (
                140
                +
                (
                    (
                        x * 5
                        +
                        y
                    )
                    %
                    110
                )
            )

            cv2.circle(
                frame,
                (
                    x,
                    y,
                ),
                4,
                (
                    intensity,
                    intensity,
                    intensity,
                ),
                -1,
            )

    cv2.line(
        frame,
        (
            405,
            10,
        ),
        (
            625,
            160,
        ),
        (
            220,
            220,
            220,
        ),
        3,
    )

    cv2.line(
        frame,
        (
            410,
            350,
        ),
        (
            630,
            205,
        ),
        (
            190,
            190,
            190,
        ),
        3,
    )

    return frame


def single_region_frame(
    width=640,
    height=360,
):
    """Features only in top-right region."""

    frame = np.zeros(
        (
            height,
            width,
            3,
        ),
        dtype=np.uint8,
    )

    for y in range(
        20,
        145,
        20,
    ):
        for x in range(
            420,
            620,
            25,
        ):
            cv2.circle(
                frame,
                (
                    x,
                    y,
                ),
                4,
                (
                    255,
                    255,
                    255,
                ),
                -1,
            )

    return frame


# ============================================================
# TRANSFORMS
# ============================================================


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
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )


def rotate_frame(
    frame,
    angle_deg,
):
    height, width = (
        frame.shape[:2]
    )

    matrix = cv2.getRotationMatrix2D(
        (
            width / 2.0,
            height / 2.0,
        ),
        angle_deg,
        1.0,
    )

    return cv2.warpAffine(
        frame,
        matrix,
        (
            width,
            height,
        ),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )


# ============================================================
# TESTS
# ============================================================


class CameraMovementGuardTests(
    unittest.TestCase
):

    # ========================================================
    # GUARD FACTORIES
    # ========================================================

    def make_production_policy_guard(
        self,
    ):
        """
        Real production thresholds.

        Used only for testing policy decisions.
        """

        return CameraMovementGuard(
            CameraMovementConfig(
                sample_every_frames=1,
                warmup_samples=0,
            )
        )

    def make_pipeline_guard(
        self,
        **overrides,
    ):
        """
        Synthetic CV pipeline configuration.

        Thresholds are intentionally lower than production because
        synthetic image transforms are only intended to verify that
        LK/RANSAC/spatial/voting can propagate movement correctly.
        """

        config = {
            "sample_every_frames":
                1,

            "warmup_samples":
                0,

            "min_tracked_points":
                12,

            "min_inlier_count":
                6,

            "min_inlier_ratio":
                0.30,

            "min_reference_region_points":
                2,

            "min_region_inliers":
                2,

            "min_reference_regions":
                2,

            "min_runtime_regions":
                2,

            "min_region_support_ratio":
                0.50,

            # Synthetic pipeline policy.
            "safe_translation_ratio_threshold":
                0.010,

            "safe_rotation_threshold_deg":
                1.00,

            "safe_scale_change_threshold":
                0.010,

            "moderate_required_signals":
                1,

            "strong_translation_ratio_threshold":
                0.020,

            "strong_rotation_threshold_deg":
                4.00,

            "strong_scale_change_threshold":
                0.030,

            "confirmation_window":
                5,

            "confirmation_hits":
                3,
        }

        config.update(
            overrides
        )

        return CameraMovementGuard(
            CameraMovementConfig(
                **config
            )
        )

    def establish_reference(
        self,
        guard,
        frame,
    ):
        result = guard.update(
            frame
        )

        self.assertEqual(
            result.get(
                "reason"
            ),
            "REFERENCE_CAPTURED",
        )

        self.assertGreaterEqual(
            result.get(
                "available_region_count",
                0,
            ),
            2,
        )

    # ========================================================
    # PRODUCTION POLICY
    # ========================================================

    def test_production_policy_rejects_observed_user_motion(
        self,
    ):
        """
        Real-camera regression:
        16.7 px / 1.46° / 2.2%

        Must NOT invalidate the camera.
        """

        guard = (
            self.make_production_policy_guard()
        )

        diagonal = np.hypot(
            640,
            360,
        )

        result = guard._movement_policy(
            translation_ratio=(
                16.7 / diagonal
            ),
            rotation_deg=1.46,
            scale_change=0.022,
        )

        self.assertFalse(
            result[
                "movement"
            ]
        )

    def test_production_policy_rejects_previous_false_positive(
        self,
    ):
        """
        Previous real-camera false-positive:
        24.1 px / 3.16° / 1.6%

        Must NOT invalidate camera reference.
        """

        guard = (
            self.make_production_policy_guard()
        )

        diagonal = np.hypot(
            640,
            360,
        )

        result = guard._movement_policy(
            translation_ratio=(
                24.1 / diagonal
            ),
            rotation_deg=3.16,
            scale_change=0.016,
        )

        self.assertFalse(
            result[
                "movement"
            ]
        )

    def test_production_policy_accepts_strong_translation(
        self,
    ):
        guard = (
            self.make_production_policy_guard()
        )

        result = guard._movement_policy(
            translation_ratio=0.060,
            rotation_deg=0.5,
            scale_change=0.01,
        )

        self.assertTrue(
            result[
                "movement"
            ]
        )

        self.assertTrue(
            result[
                "strong_translation"
            ]
        )

    def test_production_policy_accepts_strong_rotation(
        self,
    ):
        guard = (
            self.make_production_policy_guard()
        )

        result = guard._movement_policy(
            translation_ratio=0.010,
            rotation_deg=7.0,
            scale_change=0.01,
        )

        self.assertTrue(
            result[
                "movement"
            ]
        )

        self.assertTrue(
            result[
                "strong_rotation"
            ]
        )

    def test_production_policy_accepts_two_moderate_signals(
        self,
    ):
        guard = (
            self.make_production_policy_guard()
        )

        result = guard._movement_policy(
            translation_ratio=0.040,
            rotation_deg=4.0,
            scale_change=0.01,
        )

        self.assertTrue(
            result[
                "movement"
            ]
        )

        self.assertGreaterEqual(
            result[
                "moderate_signal_count"
            ],
            2,
        )

    # ========================================================
    # STABLE PIPELINE
    # ========================================================

    def test_stable_camera_does_not_trigger(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        frame = (
            room_frame()
        )

        self.establish_reference(
            guard,
            frame,
        )

        result = None

        for _ in range(
            20
        ):
            result = guard.update(
                frame
            )

        self.assertFalse(
            guard.moved
        )

        self.assertEqual(
            result.get(
                "status"
            ),
            STATUS_STABLE,
        )

        self.assertEqual(
            result.get(
                "movement_votes"
            ),
            0,
        )

    # ========================================================
    # CENTRAL USER MOVEMENT
    # ========================================================

    def test_central_person_like_motion_does_not_trigger(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        frame = (
            room_frame()
        )

        self.establish_reference(
            guard,
            frame,
        )

        for index in range(
            20
        ):

            changed = (
                frame.copy()
            )

            shift = (
                index
                %
                5
            ) * 12

            cv2.rectangle(
                changed,
                (
                    230 + shift,
                    70,
                ),
                (
                    410 + shift,
                    350,
                ),
                (
                    180,
                    180,
                    180,
                ),
                -1,
            )

            guard.update(
                changed
            )

        self.assertFalse(
            guard.moved
        )

    # ========================================================
    # PIPELINE TRANSLATION
    # ========================================================

    def test_pipeline_translation_can_confirm_movement(
        self,
    ):
        """
        20 px is intentionally used here.

        It keeps synthetic reference features distributed across
        multiple spatial regions while still exceeding the synthetic
        test threshold.

        Production threshold behavior is tested separately above.
        """

        guard = (
            self.make_pipeline_guard()
        )

        frame = (
            room_frame()
        )

        self.establish_reference(
            guard,
            frame,
        )

        moved = translate_frame(
            frame,
            20,
            0,
        )

        result = None

        for _ in range(
            5
        ):
            result = guard.update(
                moved
            )

            if guard.moved:
                break

        self.assertTrue(
            guard.moved,
            msg=(
                "Synthetic translation pipeline failed. "
                f"Last={result}"
            ),
        )

        self.assertEqual(
            result.get(
                "status"
            ),
            STATUS_MOVED,
        )

    # ========================================================
    # PIPELINE ROTATION
    # ========================================================

    def test_pipeline_rotation_can_confirm_movement(
        self,
    ):
        guard = (
            self.make_pipeline_guard(
                min_inlier_ratio=0.30,
            )
        )

        frame = (
            room_frame()
        )

        self.establish_reference(
            guard,
            frame,
        )

        # 8° synthetic rotation.
        moved = rotate_frame(
            frame,
            8.0,
        )

        result = None

        for _ in range(
            5
        ):
            result = guard.update(
                moved
            )

            if guard.moved:
                break

        self.assertTrue(
            guard.moved,
            msg=(
                "Synthetic rotation pipeline failed. "
                f"Last={result}"
            ),
        )

    # ========================================================
    # TEMPORAL CONFIRMATION
    # ========================================================

    def test_single_candidate_does_not_trigger(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        frame = (
            room_frame()
        )

        self.establish_reference(
            guard,
            frame,
        )

        # One movement candidate only.
        guard.update(
            translate_frame(
                frame,
                20,
                0,
            )
        )

        # Back to reference.
        for _ in range(
            8
        ):
            guard.update(
                frame
            )

        self.assertFalse(
            guard.moved
        )

    # ========================================================
    # ADAPTIVE SPATIAL SUPPORT
    # ========================================================

    def test_two_reference_regions_can_support_pipeline(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        frame = (
            right_side_room_frame()
        )

        self.establish_reference(
            guard,
            frame,
        )

        # Small enough to preserve right-side region tracks.
        moved = translate_frame(
            frame,
            20,
            0,
        )

        result = None

        for _ in range(
            5
        ):
            result = guard.update(
                moved
            )

            if guard.moved:
                break

        self.assertTrue(
            guard.moved,
            msg=(
                "Adaptive region pipeline failed. "
                f"Last={result}"
            ),
        )

    def test_region_support_uses_only_reference_regions(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        guard._available_reference_regions = {
            "top_right",
            "bottom_right",
        }

        points = np.array(
            [
                [
                    500.0,
                    60.0,
                ],
                [
                    520.0,
                    80.0,
                ],
                [
                    540.0,
                    100.0,
                ],
                [
                    500.0,
                    260.0,
                ],
                [
                    520.0,
                    280.0,
                ],
                [
                    540.0,
                    300.0,
                ],
            ],
            dtype=np.float32,
        )

        result = (
            guard._runtime_region_support(
                points,
                width=640,
                height=360,
            )
        )

        self.assertEqual(
            result[
                "available_region_count"
            ],
            2,
        )

        self.assertEqual(
            result[
                "active_region_count"
            ],
            2,
        )

        self.assertTrue(
            result[
                "spatial_support_valid"
            ]
        )

    def test_single_region_does_not_qualify_as_global_movement(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        guard._available_reference_regions = {
            "top_right",
            "bottom_right",
        }

        points = np.array(
            [
                [
                    500.0,
                    50.0,
                ],
                [
                    520.0,
                    70.0,
                ],
                [
                    540.0,
                    90.0,
                ],
                [
                    560.0,
                    110.0,
                ],
            ],
            dtype=np.float32,
        )

        result = (
            guard._runtime_region_support(
                points,
                width=640,
                height=360,
            )
        )

        self.assertEqual(
            result[
                "active_region_count"
            ],
            1,
        )

        self.assertFalse(
            result[
                "spatial_support_valid"
            ]
        )

    # ========================================================
    # REFERENCE QUALITY
    # ========================================================

    def test_reference_requires_at_least_two_regions(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        frame = (
            single_region_frame()
        )

        result = guard.update(
            frame
        )

        self.assertFalse(
            guard.moved
        )

        self.assertEqual(
            result.get(
                "status"
            ),
            STATUS_UNAVAILABLE,
        )

    # ========================================================
    # LATCH
    # ========================================================

    def test_movement_is_latched_even_if_camera_returns(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        frame = (
            room_frame()
        )

        self.establish_reference(
            guard,
            frame,
        )

        moved = translate_frame(
            frame,
            20,
            0,
        )

        result = None

        for _ in range(
            5
        ):
            result = guard.update(
                moved
            )

            if guard.moved:
                break

        self.assertTrue(
            guard.moved,
            msg=result,
        )

        # Once latched, returning the image does not undo it.
        result = guard.update(
            frame
        )

        self.assertEqual(
            result.get(
                "status"
            ),
            STATUS_MOVED,
        )

        self.assertTrue(
            guard.moved
        )

    # ========================================================
    # RESET
    # ========================================================

    def test_reset_allows_new_camera_reference_period(
        self,
    ):
        guard = (
            self.make_pipeline_guard()
        )

        frame = (
            room_frame()
        )

        self.establish_reference(
            guard,
            frame,
        )

        moved = translate_frame(
            frame,
            20,
            0,
        )

        result = None

        for _ in range(
            5
        ):
            result = guard.update(
                moved
            )

            if guard.moved:
                break

        self.assertTrue(
            guard.moved,
            msg=result,
        )

        # New Monitoring/reference period.
        guard.reset()

        self.assertFalse(
            guard.moved
        )

        self.establish_reference(
            guard,
            frame,
        )

        result = None

        for _ in range(
            10
        ):
            result = guard.update(
                frame
            )

        self.assertFalse(
            guard.moved
        )

        self.assertEqual(
            result.get(
                "status"
            ),
            STATUS_STABLE,
        )


    def test_persistent_reference_loss_stays_unavailable(
        self,
    ):
        """
        Regression: body motion may temporarily destroy optical-flow
        correspondence. Persistent loss must never become CAMERA_MOVED.
        """

        guard = self.make_pipeline_guard()
        guard._reference_tracking_confirmed = True

        result = None

        for _ in range(
            guard.config.reference_loss_confirmation_samples
            + 10
        ):
            result = guard._reference_lost(
                "INSUFFICIENT_TRACKED_POINTS",
                tracked_points=0,
            )

            self.assertEqual(
                result["status"],
                STATUS_UNAVAILABLE,
            )

            self.assertFalse(
                guard.moved
            )

            self.assertNotEqual(
                result.get("reason"),
                "CONFIRMED_CAMERA_REFERENCE_LOSS",
            )

        self.assertGreaterEqual(
            result["reference_loss_count"],
            guard.config.reference_loss_confirmation_samples,
        )

    def test_reference_loss_clears_stale_movement_votes_without_moving(
        self,
    ):
        """Unavailable samples must not count as movement evidence."""

        guard = self.make_pipeline_guard()
        guard._reference_tracking_confirmed = True

        for _ in range(
            guard.config.confirmation_window
            + 2
        ):
            result = guard._reference_lost(
                "GLOBAL_TRANSFORM_UNAVAILABLE"
            )

        self.assertEqual(
            result["status"],
            STATUS_UNAVAILABLE,
        )
        self.assertEqual(
            result["movement_votes"],
            0,
        )
        self.assertFalse(
            guard.moved
        )

    def test_orb_fallback_detects_large_translation(self):
        """
        Large camera movement may destroy LK correspondence.
        ORB fallback must still recover geometric movement evidence.
        """

        guard = CameraMovementGuard(
            CameraMovementConfig(
                warmup_samples=0,
                sample_every_frames=1,
                min_runtime_regions=2,
                confirmation_window=3,
                confirmation_hits=2,
            )
        )

        reference = room_frame()
        gray, mask = guard._prepare(reference)

        self.assertTrue(
            guard._capture_reference(
                gray,
                mask,
            )
        )

        matrix = np.float32(
            [
                [1.0, 0.0, 55.0],
                [0.0, 1.0, 0.0],
            ]
        )

        shifted = cv2.warpAffine(
            reference,
            matrix,
            (
                reference.shape[1],
                reference.shape[0],
            ),
        )

        shifted_gray, shifted_mask = guard._prepare(
            shifted
        )

        evidence = guard._fallback_geometric_evidence(
            shifted_gray,
            shifted_mask,
        )

        self.assertIsNotNone(
            evidence
        )

        self.assertTrue(
            evidence["evidence_valid"]
        )

        self.assertTrue(
            evidence["movement"]
        )

        self.assertEqual(
            evidence["source"],
            "ORB_FALLBACK",
        )

    def test_orb_fallback_keeps_same_scene_stable(self):
        """
        Fallback matching must not turn a stable scene into movement.
        """

        guard = CameraMovementGuard(
            CameraMovementConfig(
                warmup_samples=0,
                sample_every_frames=1,
                min_runtime_regions=2,
            )
        )

        reference = room_frame()
        gray, mask = guard._prepare(reference)

        self.assertTrue(
            guard._capture_reference(
                gray,
                mask,
            )
        )

        evidence = guard._fallback_geometric_evidence(
            gray,
            mask,
        )

        self.assertIsNotNone(
            evidence
        )

        self.assertTrue(
            evidence["evidence_valid"]
        )

        self.assertFalse(
            evidence["movement"]
        )



if __name__ == "__main__":
    unittest.main()