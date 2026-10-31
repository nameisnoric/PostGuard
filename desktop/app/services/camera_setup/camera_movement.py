"""Camera movement detection during PostGuard Monitoring.

Purpose
-------

Camera Setup and Personal Baseline are valid only while the physical
camera remains in the same placement.

This guard detects global motion of the camera during Monitoring.

It intentionally does NOT use:

    shoulder tilt
    neck tilt
    posture factors
    face position

because those values can change when the USER moves.

Instead it tracks background features around the outer area of the frame
and estimates a global affine transform between consecutive sampled frames.

Typical camera movement:

    move laptop
    rotate laptop
    lift laptop
    tilt laptop display
    slide webcam / notebook
    change camera position

produces coherent movement across many background features.

Normal body movement usually affects the center of the image and is
therefore largely excluded by the background mask.

Once camera movement is confirmed, the guard is LATCHED.

The Monitoring session must not continue using the old Camera Reference
or Personal Baseline.
"""

from __future__ import annotations

from dataclasses import dataclass

import math

import cv2
import numpy as np


STATUS_WARMING_UP = "WARMING_UP"
STATUS_STABLE = "STABLE"
STATUS_MOVED = "MOVED"
STATUS_UNAVAILABLE = "UNAVAILABLE"


@dataclass(
    frozen=True
)
class CameraMovementConfig:
    """
    Engineering policy for Camera Movement Detection.

    These are prototype validation thresholds, not ergonomic thresholds.
    """

    # Resize only for movement analysis.
    # The actual Detection frame is NOT resized.
    analysis_width: int = 640

    # Analyze roughly every third camera frame.
    sample_every_frames: int = 3

    # Background feature detector.
    max_corners: int = 180
    quality_level: float = 0.01
    min_distance: int = 8

    # Minimum evidence required.
    min_tracked_points: int = 18
    min_inlier_ratio: float = 0.55

    # Camera movement thresholds.
    #
    # Translation is normalized by frame diagonal.
    translation_ratio_threshold: float = 0.008

    # Global camera rotation between samples.
    rotation_threshold_deg: float = 1.20

    # Zoom / forward-backward camera movement approximation.
    scale_change_threshold: float = 0.025

    # Require more than one consecutive movement measurement.
    consecutive_hits: int = 2


class CameraMovementGuard:
    """
    Detect physical camera movement from RAW camera frames.

    IMPORTANT:

        feed RAW frames into this class.

    Do NOT feed frames after:

        Camera Roll correction
        mirror flip
        crop
        zoom

    because this class is trying to detect movement of the physical camera.
    """

    def __init__(
        self,
        config: CameraMovementConfig | None = None,
    ):
        self.config = (
            config
            or
            CameraMovementConfig()
        )

        self.reset()

    @property
    def moved(
        self,
    ) -> bool:
        return self._latched

    def reset(
        self,
    ) -> None:
        self._frame_counter = 0

        self._previous_gray = None

        self._movement_hits = 0

        self._latched = False

        self.last_result = {
            "status":
                STATUS_WARMING_UP,

            "reason":
                "NO_REFERENCE",
        }

    # ========================================================
    # FRAME PREPARATION
    # ========================================================

    def _prepare(
        self,
        frame,
    ):
        if (
            frame is None
            or
            not hasattr(
                frame,
                "shape",
            )
            or
            len(
                frame.shape
            )
            <
            2
        ):
            return (
                None,
                None,
            )

        height, width = (
            frame.shape[:2]
        )

        if (
            height < 80
            or
            width < 80
        ):
            return (
                None,
                None,
            )

        scale = min(
            1.0,
            self.config.analysis_width
            /
            float(
                width
            ),
        )

        if scale < 1.0:

            resized_width = max(
                1,
                int(
                    round(
                        width
                        *
                        scale
                    )
                ),
            )

            resized_height = max(
                1,
                int(
                    round(
                        height
                        *
                        scale
                    )
                ),
            )

            frame = cv2.resize(
                frame,
                (
                    resized_width,
                    resized_height,
                ),
                interpolation=cv2.INTER_AREA,
            )

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY,
        )

        gray = cv2.GaussianBlur(
            gray,
            (
                5,
                5,
            ),
            0,
        )

        height, width = (
            gray.shape[:2]
        )

        # ====================================================
        # BACKGROUND MASK
        #
        # Use outer image regions.
        #
        # Exclude most of the center where the user normally is.
        # ====================================================

        mask = np.full(
            (
                height,
                width,
            ),
            255,
            dtype=np.uint8,
        )

        center_x0 = int(
            width
            *
            0.25
        )

        center_x1 = int(
            width
            *
            0.75
        )

        center_y0 = int(
            height
            *
            0.12
        )

        center_y1 = int(
            height
            *
            0.90
        )

        mask[
            center_y0:center_y1,
            center_x0:center_x1,
        ] = 0

        return (
            gray,
            mask,
        )

    # ========================================================
    # UPDATE
    # ========================================================

    def update(
        self,
        frame,
    ) -> dict:
        """
        Process one RAW camera frame.

        Returns:

            {
                "status": ...,
                "reason": ...,
                "translation_px": ...,
                "translation_ratio": ...,
                "rotation_deg": ...,
                "scale_change": ...,
                ...
            }
        """

        # Once moved, remain moved until explicit reset.
        if self._latched:
            return dict(
                self.last_result
            )

        self._frame_counter += 1

        if (
            self._frame_counter
            %
            self.config.sample_every_frames
            !=
            0
        ):
            return dict(
                self.last_result
            )

        gray, mask = (
            self._prepare(
                frame
            )
        )

        if gray is None:

            self.last_result = {
                "status":
                    STATUS_UNAVAILABLE,

                "reason":
                    "INVALID_FRAME",
            }

            return dict(
                self.last_result
            )

        # ====================================================
        # FIRST REFERENCE FRAME
        # ====================================================

        if (
            self._previous_gray
            is None
        ):
            self._previous_gray = (
                gray
            )

            self.last_result = {
                "status":
                    STATUS_WARMING_UP,

                "reason":
                    "REFERENCE_CAPTURED",
            }

            return dict(
                self.last_result
            )

        previous = (
            self._previous_gray
        )

        # Always advance reference.
        self._previous_gray = (
            gray
        )

        if (
            previous.shape
            !=
            gray.shape
        ):
            self._movement_hits = 0

            self.last_result = {
                "status":
                    STATUS_UNAVAILABLE,

                "reason":
                    "FRAME_SIZE_CHANGED",
            }

            return dict(
                self.last_result
            )

        # ====================================================
        # BACKGROUND FEATURES
        # ====================================================

        points = cv2.goodFeaturesToTrack(
            previous,
            mask=mask,
            maxCorners=self.config.max_corners,
            qualityLevel=self.config.quality_level,
            minDistance=self.config.min_distance,
            blockSize=7,
        )

        if (
            points is None
            or
            len(
                points
            )
            <
            self.config.min_tracked_points
        ):
            self._movement_hits = max(
                0,
                self._movement_hits
                -
                1,
            )

            self.last_result = {
                "status":
                    STATUS_UNAVAILABLE,

                "reason":
                    "INSUFFICIENT_BACKGROUND_FEATURES",

                "tracked_points":
                    (
                        0
                        if points is None
                        else
                        int(
                            len(
                                points
                            )
                        )
                    ),
            }

            return dict(
                self.last_result
            )

        # ====================================================
        # OPTICAL FLOW
        # ====================================================

        next_points, status, _ = (
            cv2.calcOpticalFlowPyrLK(
                previous,
                gray,
                points,
                None,
                winSize=(
                    21,
                    21,
                ),
                maxLevel=3,
                criteria=(
                    cv2.TERM_CRITERIA_EPS
                    |
                    cv2.TERM_CRITERIA_COUNT,
                    30,
                    0.01,
                ),
            )
        )

        if (
            next_points is None
            or
            status is None
        ):
            self._movement_hits = max(
                0,
                self._movement_hits
                -
                1,
            )

            self.last_result = {
                "status":
                    STATUS_UNAVAILABLE,

                "reason":
                    "OPTICAL_FLOW_FAILED",
            }

            return dict(
                self.last_result
            )

        valid = (
            status.reshape(
                -1
            )
            ==
            1
        )

        previous_points = (
            points.reshape(
                -1,
                2,
            )[
                valid
            ]
        )

        current_points = (
            next_points.reshape(
                -1,
                2,
            )[
                valid
            ]
        )

        if (
            len(
                previous_points
            )
            <
            self.config.min_tracked_points
        ):
            self._movement_hits = max(
                0,
                self._movement_hits
                -
                1,
            )

            self.last_result = {
                "status":
                    STATUS_UNAVAILABLE,

                "reason":
                    "INSUFFICIENT_TRACKED_POINTS",

                "tracked_points":
                    int(
                        len(
                            previous_points
                        )
                    ),
            }

            return dict(
                self.last_result
            )

        # ====================================================
        # GLOBAL TRANSFORM
        # ====================================================

        matrix, inliers = (
            cv2.estimateAffinePartial2D(
                previous_points,
                current_points,
                method=cv2.RANSAC,
                ransacReprojThreshold=3.0,
                maxIters=2000,
                confidence=0.99,
                refineIters=10,
            )
        )

        if (
            matrix is None
            or
            inliers is None
        ):
            self._movement_hits = max(
                0,
                self._movement_hits
                -
                1,
            )

            self.last_result = {
                "status":
                    STATUS_UNAVAILABLE,

                "reason":
                    "GLOBAL_TRANSFORM_UNAVAILABLE",

                "tracked_points":
                    int(
                        len(
                            previous_points
                        )
                    ),
            }

            return dict(
                self.last_result
            )

        inlier_count = int(
            np.count_nonzero(
                inliers
            )
        )

        inlier_ratio = (
            inlier_count
            /
            max(
                1,
                len(
                    previous_points
                ),
            )
        )

        a = float(
            matrix[
                0,
                0,
            ]
        )

        b = float(
            matrix[
                1,
                0,
            ]
        )

        translation_x = float(
            matrix[
                0,
                2,
            ]
        )

        translation_y = float(
            matrix[
                1,
                2,
            ]
        )

        estimated_scale = math.hypot(
            a,
            b,
        )

        rotation_deg = math.degrees(
            math.atan2(
                b,
                a,
            )
        )

        translation_px = math.hypot(
            translation_x,
            translation_y,
        )

        diagonal = math.hypot(
            gray.shape[1],
            gray.shape[0],
        )

        translation_ratio = (
            translation_px
            /
            max(
                diagonal,
                1.0,
            )
        )

        scale_change = abs(
            estimated_scale
            -
            1.0
        )

        # ====================================================
        # EVIDENCE QUALITY
        # ====================================================

        evidence_valid = (
            inlier_count
            >=
            self.config.min_tracked_points
            and
            inlier_ratio
            >=
            self.config.min_inlier_ratio
        )

        threshold_hit = (
            evidence_valid
            and
            (
                translation_ratio
                >=
                self.config.translation_ratio_threshold

                or

                abs(
                    rotation_deg
                )
                >=
                self.config.rotation_threshold_deg

                or

                scale_change
                >=
                self.config.scale_change_threshold
            )
        )

        if threshold_hit:
            self._movement_hits += 1

        else:
            self._movement_hits = 0

        result = {
            "status":
                STATUS_STABLE,

            "reason":
                "STABLE",

            "tracked_points":
                int(
                    len(
                        previous_points
                    )
                ),

            "inlier_count":
                inlier_count,

            "inlier_ratio":
                float(
                    inlier_ratio
                ),

            "translation_px":
                float(
                    translation_px
                ),

            "translation_ratio":
                float(
                    translation_ratio
                ),

            "rotation_deg":
                float(
                    rotation_deg
                ),

            "scale":
                float(
                    estimated_scale
                ),

            "scale_change":
                float(
                    scale_change
                ),

            "consecutive_hits":
                int(
                    self._movement_hits
                ),
        }

        # ====================================================
        # LATCH MOVEMENT
        # ====================================================

        if (
            self._movement_hits
            >=
            self.config.consecutive_hits
        ):
            self._latched = True

            result[
                "status"
            ] = (
                STATUS_MOVED
            )

            result[
                "reason"
            ] = (
                "GLOBAL_BACKGROUND_MOTION"
            )

        self.last_result = (
            result
        )

        return dict(
            result
        )