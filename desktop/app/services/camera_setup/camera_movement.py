"""PostGuard Production Camera Movement Guard.

Policy
------
The guard detects camera-reference invalidation rather than every tiny
physical vibration.

A Session is invalidated only when a reliable global transform shows
significant camera movement and the movement confirmation policy passes.

Tracking/reference loss is an availability problem. It may make movement
evaluation temporarily UNAVAILABLE, but it is not geometric evidence that
the camera moved and must never confirm CAMERA_MOVED by itself.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

import cv2
import numpy as np


STATUS_WARMING_UP = "WARMING_UP"
STATUS_STABLE = "STABLE"
STATUS_MOVED = "MOVED"
STATUS_UNAVAILABLE = "UNAVAILABLE"


REGION_TOP_LEFT = "top_left"
REGION_TOP_RIGHT = "top_right"
REGION_BOTTOM_LEFT = "bottom_left"
REGION_BOTTOM_RIGHT = "bottom_right"

REGION_NAMES = (
    REGION_TOP_LEFT,
    REGION_TOP_RIGHT,
    REGION_BOTTOM_LEFT,
    REGION_BOTTOM_RIGHT,
)


@dataclass(frozen=True)
class CameraMovementConfig:
    # --------------------------------------------------------
    # Analysis
    # --------------------------------------------------------

    analysis_width: int = 640

    sample_every_frames: int = 3

    warmup_samples: int = 20

    # --------------------------------------------------------
    # LK tracking
    # --------------------------------------------------------

    max_corners: int = 240

    quality_level: float = 0.01

    min_distance: int = 8

    min_tracked_points: int = 18

    min_inlier_count: int = 8

    min_inlier_ratio: float = 0.55

    max_forward_backward_error_px: float = 1.5

    # --------------------------------------------------------
    # Legacy thresholds
    #
    # Kept because MonitoringPage currently passes these.
    # --------------------------------------------------------

    translation_ratio_threshold: float = 0.012

    rotation_threshold_deg: float = 1.50

    scale_change_threshold: float = 0.030

    # --------------------------------------------------------
    # Production movement thresholds
    #
    # Moderate movement requires 2 independent signals.
    # --------------------------------------------------------

    safe_translation_ratio_threshold: float = 0.035

    safe_rotation_threshold_deg: float = 3.50

    safe_scale_change_threshold: float = 0.040

    moderate_required_signals: int = 2

    # --------------------------------------------------------
    # Strong movement
    #
    # One very strong signal is sufficient.
    # --------------------------------------------------------

    strong_translation_ratio_threshold: float = 0.055

    strong_rotation_threshold_deg: float = 6.00

    strong_scale_change_threshold: float = 0.080

    # --------------------------------------------------------
    # Spatial support
    # --------------------------------------------------------

    min_reference_region_points: int = 2

    min_region_inliers: int = 2

    min_reference_regions: int = 2

    min_runtime_regions: int = 2

    min_region_support_ratio: float = 0.50

    # Compatibility with previous MonitoringPage.
    min_active_regions: int | None = None

    # --------------------------------------------------------
    # Movement confirmation
    # --------------------------------------------------------

    confirmation_window: int = 5

    confirmation_hits: int = 3

    # --------------------------------------------------------
    # Persistent reference loss
    #
    # At ~30 FPS and sample_every_frames=3:
    # 12 samples ~= 1.2 seconds.
    #
    # This prevents a temporary body/hand movement from ending
    # the Session but catches a large physical camera move.
    # --------------------------------------------------------

    reference_loss_confirmation_samples: int = 12

    # --------------------------------------------------------
    # Large-movement fallback
    #
    # When LK loses the original reference completely, ORB
    # descriptor matching provides a second geometric path.
    # Reference loss by itself still never means MOVED.
    # --------------------------------------------------------

    fallback_orb_features: int = 900
    fallback_ratio_test: float = 0.78
    fallback_min_matches: int = 16
    fallback_min_inliers: int = 10
    fallback_min_inlier_ratio: float = 0.50


class CameraMovementGuard:
    """Detect camera-reference invalidation during Monitoring."""

    def __init__(
        self,
        config: CameraMovementConfig | None = None,
    ) -> None:

        self.config = (
            config
            or CameraMovementConfig()
        )

        self._validate_config()

        self.reset()

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_config(
        self,
    ) -> None:

        if self.config.analysis_width <= 0:
            raise ValueError(
                "analysis_width must be positive"
            )

        if self.config.sample_every_frames <= 0:
            raise ValueError(
                "sample_every_frames must be positive"
            )

        if self.config.warmup_samples < 0:
            raise ValueError(
                "warmup_samples cannot be negative"
            )

        if self.config.max_corners < 4:
            raise ValueError(
                "max_corners is too small"
            )

        if not (
            0.0
            <
            self.config.quality_level
            <=
            1.0
        ):
            raise ValueError(
                "quality_level must be in (0, 1]"
            )

        if self.config.min_distance <= 0:
            raise ValueError(
                "min_distance must be positive"
            )

        if self.config.min_tracked_points < 4:
            raise ValueError(
                "min_tracked_points is too small"
            )

        if self.config.min_inlier_count < 4:
            raise ValueError(
                "min_inlier_count is too small"
            )

        if not (
            0.0
            <
            self.config.min_inlier_ratio
            <=
            1.0
        ):
            raise ValueError(
                "min_inlier_ratio must be in (0, 1]"
            )

        if (
            self.config.max_forward_backward_error_px
            <=
            0.0
        ):
            raise ValueError(
                "max_forward_backward_error_px "
                "must be positive"
            )

        if not (
            1
            <=
            self.config.moderate_required_signals
            <=
            3
        ):
            raise ValueError(
                "moderate_required_signals must be 1..3"
            )

        if self.config.min_reference_region_points < 1:
            raise ValueError(
                "min_reference_region_points "
                "must be positive"
            )

        if self.config.min_region_inliers < 1:
            raise ValueError(
                "min_region_inliers must be positive"
            )

        if not (
            1
            <=
            self.config.min_reference_regions
            <=
            4
        ):
            raise ValueError(
                "min_reference_regions must be 1..4"
            )

        if not (
            1
            <=
            self.config.min_runtime_regions
            <=
            4
        ):
            raise ValueError(
                "min_runtime_regions must be 1..4"
            )

        if not (
            0.0
            <
            self.config.min_region_support_ratio
            <=
            1.0
        ):
            raise ValueError(
                "min_region_support_ratio must be in (0, 1]"
            )

        if (
            self.config.min_active_regions
            is not None
            and
            not (
                1
                <=
                self.config.min_active_regions
                <=
                4
            )
        ):
            raise ValueError(
                "min_active_regions must be 1..4"
            )

        if self.config.confirmation_window < 1:
            raise ValueError(
                "confirmation_window must be positive"
            )

        if self.config.confirmation_hits < 1:
            raise ValueError(
                "confirmation_hits must be positive"
            )

        if (
            self.config.confirmation_hits
            >
            self.config.confirmation_window
        ):
            raise ValueError(
                "confirmation_hits cannot exceed "
                "confirmation_window"
            )

        if (
            self.config.reference_loss_confirmation_samples
            <
            1
        ):
            raise ValueError(
                "reference_loss_confirmation_samples "
                "must be positive"
            )

        if self.config.fallback_orb_features < 100:
            raise ValueError(
                "fallback_orb_features is too small"
            )

        if not (
            0.5
            <=
            self.config.fallback_ratio_test
            <
            1.0
        ):
            raise ValueError(
                "fallback_ratio_test must be in [0.5, 1.0)"
            )

        if self.config.fallback_min_matches < 4:
            raise ValueError(
                "fallback_min_matches is too small"
            )

        if self.config.fallback_min_inliers < 4:
            raise ValueError(
                "fallback_min_inliers is too small"
            )

        if not (
            0.0
            <
            self.config.fallback_min_inlier_ratio
            <=
            1.0
        ):
            raise ValueError(
                "fallback_min_inlier_ratio must be in (0, 1]"
            )

    # ========================================================
    # STATE
    # ========================================================

    @property
    def moved(
        self,
    ) -> bool:

        return self._latched

    def reset(
        self,
    ) -> None:

        self._frame_counter = 0

        self._sample_counter = 0

        self._reference_gray = None

        self._reference_points = None

        # Secondary large-movement reference. ORB is used only
        # when LK cannot provide enough tracked points.
        self._reference_orb_keypoints = None
        self._reference_orb_descriptors = None

        self._reference_region_counts = {
            name: 0
            for name in REGION_NAMES
        }

        self._available_reference_regions = set()

        self._movement_votes = deque(
            maxlen=self.config.confirmation_window
        )

        # Consecutive valid-frame tracking failures.
        self._reference_loss_count = 0

        # Reference-loss confirmation is disabled until the
        # captured reference has produced at least one usable
        # runtime global transform.
        self._reference_tracking_confirmed = False

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
            len(frame.shape) < 2
        ):

            return (
                None,
                None,
            )

        height, width = (
            frame.shape[:2]
        )

        if (
            width < 80
            or
            height < 80
        ):

            return (
                None,
                None,
            )

        scale = min(
            1.0,
            self.config.analysis_width
            /
            float(width),
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

        # Keep only outer background.
        # Central user/body motion is excluded.
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
            0.20
        )

        center_x1 = int(
            width
            *
            0.80
        )

        center_y0 = int(
            height
            *
            0.08
        )

        center_y1 = int(
            height
            *
            0.96
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
    # REGION HELPERS
    # ========================================================

    @staticmethod
    def _region_name(
        x: float,
        y: float,
        width: int,
        height: int,
    ) -> str:

        mid_x = (
            float(width)
            *
            0.5
        )

        mid_y = (
            float(height)
            *
            0.5
        )

        if (
            x < mid_x
            and
            y < mid_y
        ):
            return REGION_TOP_LEFT

        if (
            x >= mid_x
            and
            y < mid_y
        ):
            return REGION_TOP_RIGHT

        if (
            x < mid_x
            and
            y >= mid_y
        ):
            return REGION_BOTTOM_LEFT

        return REGION_BOTTOM_RIGHT

    def _count_regions(
        self,
        points,
        width: int,
        height: int,
    ) -> dict[str, int]:

        counts = {
            name: 0
            for name in REGION_NAMES
        }

        for point in points:

            x = float(
                point[0]
            )

            y = float(
                point[1]
            )

            region = (
                self._region_name(
                    x,
                    y,
                    width,
                    height,
                )
            )

            counts[
                region
            ] += 1

        return counts

    def _reference_region_support(
        self,
        points,
        width: int,
        height: int,
    ) -> dict:

        counts = (
            self._count_regions(
                points,
                width,
                height,
            )
        )

        available = {
            name
            for name, count in counts.items()
            if (
                count
                >=
                self.config.min_reference_region_points
            )
        }

        return {
            "counts":
                counts,

            "available_regions":
                available,

            "available_region_count":
                len(
                    available
                ),
        }

    def _runtime_region_support(
        self,
        points,
        width: int,
        height: int,
    ) -> dict:

        counts = (
            self._count_regions(
                points,
                width,
                height,
            )
        )

        available = set(
            self._available_reference_regions
        )

        active = {
            name
            for name in available
            if (
                counts.get(
                    name,
                    0,
                )
                >=
                self.config.min_region_inliers
            )
        }

        available_count = len(
            available
        )

        active_count = len(
            active
        )

        if available_count > 0:

            support_ratio = (
                active_count
                /
                available_count
            )

        else:

            support_ratio = 0.0

        required_by_ratio = int(
            math.ceil(
                available_count
                *
                self.config.min_region_support_ratio
            )
        )

        required_regions = max(
            self.config.min_runtime_regions,
            required_by_ratio,
        )

        required_regions = min(
            required_regions,
            available_count,
        )

        spatial_valid = (
            available_count
            >=
            self.config.min_reference_regions

            and

            active_count
            >=
            required_regions

            and

            support_ratio
            >=
            self.config.min_region_support_ratio
        )

        return {
            "top_left_inliers":
                int(
                    counts[
                        REGION_TOP_LEFT
                    ]
                ),

            "top_right_inliers":
                int(
                    counts[
                        REGION_TOP_RIGHT
                    ]
                ),

            "bottom_left_inliers":
                int(
                    counts[
                        REGION_BOTTOM_LEFT
                    ]
                ),

            "bottom_right_inliers":
                int(
                    counts[
                        REGION_BOTTOM_RIGHT
                    ]
                ),

            "available_region_count":
                int(
                    available_count
                ),

            "active_region_count":
                int(
                    active_count
                ),

            "region_support_ratio":
                float(
                    support_ratio
                ),

            "spatial_support_valid":
                bool(
                    spatial_valid
                ),
        }

    # ========================================================
    # REFERENCE CAPTURE
    # ========================================================

    def _capture_reference(
        self,
        gray,
        mask,
    ) -> bool:

        points = cv2.goodFeaturesToTrack(
            gray,
            mask=mask,
            maxCorners=self.config.max_corners,
            qualityLevel=self.config.quality_level,
            minDistance=self.config.min_distance,
            blockSize=7,
        )

        if (
            points is None
            or
            len(points)
            <
            self.config.min_tracked_points
        ):

            return False

        flat = (
            points.reshape(
                -1,
                2,
            )
        )

        region_support = (
            self._reference_region_support(
                flat,
                gray.shape[1],
                gray.shape[0],
            )
        )

        if (
            region_support[
                "available_region_count"
            ]
            <
            self.config.min_reference_regions
        ):

            return False

        self._reference_gray = (
            gray.copy()
        )

        self._reference_points = (
            points.copy()
        )

        orb = cv2.ORB_create(
            nfeatures=self.config.fallback_orb_features
        )

        orb_keypoints, orb_descriptors = (
            orb.detectAndCompute(
                self._reference_gray,
                mask,
            )
        )

        self._reference_orb_keypoints = (
            orb_keypoints
            if orb_keypoints is not None
            else []
        )

        self._reference_orb_descriptors = (
            orb_descriptors.copy()
            if orb_descriptors is not None
            else None
        )

        self._reference_region_counts = dict(
            region_support[
                "counts"
            ]
        )

        self._available_reference_regions = set(
            region_support[
                "available_regions"
            ]
        )

        self._movement_votes.clear()

        self._reference_loss_count = 0
        self._reference_tracking_confirmed = False
        return True

    # ========================================================
    # MOVEMENT POLICY
    # ========================================================

    def _movement_policy(
        self,
        *,
        translation_ratio: float,
        rotation_deg: float,
        scale_change: float,
    ) -> dict:

        translation_ratio = abs(
            float(
                translation_ratio
            )
        )

        rotation_abs = abs(
            float(
                rotation_deg
            )
        )

        scale_change = abs(
            float(
                scale_change
            )
        )

        moderate_translation = (
            translation_ratio
            >=
            self.config.safe_translation_ratio_threshold
        )

        moderate_rotation = (
            rotation_abs
            >=
            self.config.safe_rotation_threshold_deg
        )

        moderate_scale = (
            scale_change
            >=
            self.config.safe_scale_change_threshold
        )

        moderate_count = sum(
            (
                int(
                    moderate_translation
                ),
                int(
                    moderate_rotation
                ),
                int(
                    moderate_scale
                ),
            )
        )

        strong_translation = (
            translation_ratio
            >=
            self.config.strong_translation_ratio_threshold
        )

        strong_rotation = (
            rotation_abs
            >=
            self.config.strong_rotation_threshold_deg
        )

        strong_scale = (
            scale_change
            >=
            self.config.strong_scale_change_threshold
        )

        movement = (
            strong_translation

            or

            strong_rotation

            or

            strong_scale

            or

            (
                moderate_count
                >=
                self.config.moderate_required_signals
            )
        )

        return {
            "movement":
                bool(
                    movement
                ),

            "moderate_signal_count":
                int(
                    moderate_count
                ),

            "moderate_translation":
                bool(
                    moderate_translation
                ),

            "moderate_rotation":
                bool(
                    moderate_rotation
                ),

            "moderate_scale":
                bool(
                    moderate_scale
                ),

            "strong_translation":
                bool(
                    strong_translation
                ),

            "strong_rotation":
                bool(
                    strong_rotation
                ),

            "strong_scale":
                bool(
                    strong_scale
                ),
        }

    # ========================================================
    # FALLBACK GEOMETRIC MATCHING
    # ========================================================

    def _fallback_geometric_evidence(
        self,
        gray,
        mask,
    ) -> dict | None:
        """
        Try to recover geometric evidence after LK tracking loss.

        ORB descriptor matching is intentionally used only as a
        fallback. A missing/weak match returns None and therefore
        remains UNAVAILABLE. Only a valid RANSAC transform may
        contribute a movement vote.
        """

        if (
            self._reference_orb_descriptors is None
            or
            not self._reference_orb_keypoints
        ):
            return None

        orb = cv2.ORB_create(
            nfeatures=self.config.fallback_orb_features
        )

        current_keypoints, current_descriptors = (
            orb.detectAndCompute(
                gray,
                mask,
            )
        )

        if (
            current_descriptors is None
            or
            current_keypoints is None
            or
            len(current_keypoints) < 4
        ):
            return None

        matcher = cv2.BFMatcher(
            cv2.NORM_HAMMING,
            crossCheck=False,
        )

        pairs = matcher.knnMatch(
            self._reference_orb_descriptors,
            current_descriptors,
            k=2,
        )

        good = []

        for pair in pairs:
            if len(pair) < 2:
                continue

            best, second = pair

            if (
                best.distance
                <
                self.config.fallback_ratio_test
                *
                second.distance
            ):
                good.append(
                    best
                )

        if (
            len(good)
            <
            self.config.fallback_min_matches
        ):
            return None

        reference_points = np.float32(
            [
                self._reference_orb_keypoints[
                    match.queryIdx
                ].pt
                for match in good
            ]
        )

        current_points = np.float32(
            [
                current_keypoints[
                    match.trainIdx
                ].pt
                for match in good
            ]
        )

        matrix, inliers = (
            cv2.estimateAffinePartial2D(
                reference_points,
                current_points,
                method=cv2.RANSAC,
                ransacReprojThreshold=4.0,
                maxIters=3000,
                confidence=0.99,
                refineIters=10,
            )
        )

        if (
            matrix is None
            or
            inliers is None
        ):
            return None

        inlier_mask = (
            inliers.reshape(-1)
            ==
            1
        )

        inlier_count = int(
            np.count_nonzero(
                inlier_mask
            )
        )

        match_count = int(
            len(good)
        )

        inlier_ratio = (
            inlier_count
            /
            max(
                1,
                match_count,
            )
        )

        if (
            inlier_count
            <
            self.config.fallback_min_inliers
            or
            inlier_ratio
            <
            self.config.fallback_min_inlier_ratio
        ):
            return None

        reference_inliers = (
            reference_points[
                inlier_mask
            ]
        )

        spatial = (
            self._runtime_region_support(
                reference_inliers,
                gray.shape[1],
                gray.shape[0],
            )
        )

        if not spatial[
            "spatial_support_valid"
        ]:
            return None

        a = float(
            matrix[0, 0]
        )

        b = float(
            matrix[1, 0]
        )

        translation_x = float(
            matrix[0, 2]
        )

        translation_y = float(
            matrix[1, 2]
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

        scale = math.hypot(
            a,
            b,
        )

        scale_change = abs(
            scale
            -
            1.0
        )

        rotation_deg = math.degrees(
            math.atan2(
                b,
                a,
            )
        )

        policy = (
            self._movement_policy(
                translation_ratio=translation_ratio,
                rotation_deg=rotation_deg,
                scale_change=scale_change,
            )
        )

        return {
            "source":
                "ORB_FALLBACK",

            "tracked_points":
                match_count,

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
                    scale
                ),

            "scale_change":
                float(
                    scale_change
                ),

            "evidence_valid":
                True,

            **spatial,
            **policy,
        }

    def _use_fallback_evidence(
        self,
        evidence: dict,
    ) -> dict:
        """
        Feed valid fallback geometry through the same temporal
        confirmation window as the normal LK/RANSAC path.
        """

        candidate = bool(
            evidence.get(
                "movement"
            )
        )

        self._movement_votes.append(
            candidate
        )

        movement_hits = int(
            sum(
                self._movement_votes
            )
        )

        self._clear_reference_loss()

        result = {
            "status":
                STATUS_STABLE,

            "reason":
                (
                    "MOVEMENT_CANDIDATE_FALLBACK"
                    if candidate
                    else
                    "STABLE_FALLBACK"
                ),

            "reference_loss_count":
                0,

            "movement_votes":
                movement_hits,

            "movement_window":
                int(
                    len(
                        self._movement_votes
                    )
                ),

            **evidence,
        }

        if (
            len(
                self._movement_votes
            )
            >=
            self.config.confirmation_window
            and
            movement_hits
            >=
            self.config.confirmation_hits
        ):
            self._latched = True

            result[
                "status"
            ] = STATUS_MOVED

            result[
                "reason"
            ] = (
                "CONFIRMED_GLOBAL_CAMERA_MOVEMENT_FALLBACK"
            )

        self.last_result = (
            result
        )

        return dict(
            result
        )

    # ========================================================
    # REFERENCE LOSS
    # ========================================================

    def _reference_lost(
        self,
        reason: str,
        *,
        tracked_points: int | None = None,
    ) -> dict:
        """
        Handle a valid frame where the locked background
        reference cannot currently be tracked reliably.

        IMPORTANT:
        tracking/reference loss means movement evidence is
        unavailable. It is never sufficient evidence to latch
        STATUS_MOVED, regardless of how long the loss lasts.

        The diagnostic loss counter is kept for logging and
        compatibility only. Actual camera movement can still be
        confirmed by the normal geometric movement path.
        """

        # Missing transform data is not a movement vote.
        # Append False so stale candidate votes cannot survive
        # indefinitely across a period without usable evidence.
        self._movement_votes.append(
            False
        )

        if self._reference_tracking_confirmed:
            self._reference_loss_count += 1
        else:
            self._reference_loss_count = 0

        result = {
            "status":
                STATUS_UNAVAILABLE,

            "reason":
                reason,

            "reference_loss_count":
                int(
                    self._reference_loss_count
                ),

            # Compatibility / diagnostic metadata only.
            # Reaching this value does NOT mean CAMERA_MOVED.
            "reference_loss_required":
                int(
                    self.config.reference_loss_confirmation_samples
                ),

            "reference_loss_armed":
                bool(
                    self._reference_tracking_confirmed
                ),

            "reference_lost":
                True,

            "movement_votes":
                int(
                    sum(
                        self._movement_votes
                    )
                ),

            "movement_window":
                int(
                    len(
                        self._movement_votes
                    )
                ),

            "tracked_points":
                tracked_points,
        }

        self.last_result = (
            result
        )

        return dict(
            result
        )

    def _clear_reference_loss(
        self,
    ) -> None:

        self._reference_loss_count = 0

    # ========================================================
    # GENERIC UNAVAILABLE
    # ========================================================

    def _unavailable(
        self,
        reason: str,
        **extra,
    ) -> dict:

        self._movement_votes.append(
            False
        )

        self.last_result = {
            "status":
                STATUS_UNAVAILABLE,

            "reason":
                reason,

            "movement_votes":
                int(
                    sum(
                        self._movement_votes
                    )
                ),

            "movement_window":
                int(
                    len(
                        self._movement_votes
                    )
                ),

            **extra,
        }

        return dict(
            self.last_result
        )

    # ========================================================
    # UPDATE
    # ========================================================

    def update(
        self,
        frame,
    ) -> dict:

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

        # Invalid/no frame belongs to Camera Loss handling,
        # not camera movement.
        if gray is None:

            self._clear_reference_loss()

            return self._unavailable(
                "INVALID_FRAME"
            )

        self._sample_counter += 1

        # ====================================================
        # WARMUP
        # ====================================================

        if (
            self._sample_counter
            <=
            self.config.warmup_samples
        ):

            self.last_result = {
                "status":
                    STATUS_WARMING_UP,

                "reason":
                    "CAMERA_STABILIZING",
            }

            return dict(
                self.last_result
            )

        # ====================================================
        # INITIAL REFERENCE
        # ====================================================

        if (
            self._reference_gray
            is None
            or
            self._reference_points
            is None
        ):

            if not self._capture_reference(
                gray,
                mask,
            ):

                return self._unavailable(
                    "INSUFFICIENT_DISTRIBUTED_BACKGROUND_FEATURES"
                )

            self.last_result = {
                "status":
                    STATUS_WARMING_UP,

                "reason":
                    "REFERENCE_CAPTURED",

                "tracked_points":
                    int(
                        len(
                            self._reference_points
                        )
                    ),

                "available_region_count":
                    int(
                        len(
                            self._available_reference_regions
                        )
                    ),
            }

            return dict(
                self.last_result
            )

        if (
            self._reference_gray.shape
            !=
            gray.shape
        ):

            return self._reference_lost(
                "FRAME_SIZE_CHANGED"
            )

        # ====================================================
        # FORWARD LK
        # ====================================================

        forward_points, forward_status, _ = (
            cv2.calcOpticalFlowPyrLK(
                self._reference_gray,
                gray,
                self._reference_points,
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
            forward_points is None
            or
            forward_status is None
        ):

            return self._reference_lost(
                "OPTICAL_FLOW_FAILED"
            )

        # ====================================================
        # BACKWARD LK
        # ====================================================

        backward_points, backward_status, _ = (
            cv2.calcOpticalFlowPyrLK(
                gray,
                self._reference_gray,
                forward_points,
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
            backward_points is None
            or
            backward_status is None
        ):

            return self._reference_lost(
                "BACKWARD_FLOW_FAILED"
            )

        reference_flat = (
            self._reference_points.reshape(
                -1,
                2,
            )
        )

        forward_flat = (
            forward_points.reshape(
                -1,
                2,
            )
        )

        backward_flat = (
            backward_points.reshape(
                -1,
                2,
            )
        )

        forward_valid = (
            forward_status.reshape(
                -1
            )
            ==
            1
        )

        backward_valid = (
            backward_status.reshape(
                -1
            )
            ==
            1
        )

        fb_error = (
            np.linalg.norm(
                reference_flat
                -
                backward_flat,
                axis=1,
            )
        )

        consistent = (
            forward_valid

            &

            backward_valid

            &

            (
                fb_error
                <=
                self.config.max_forward_backward_error_px
            )
        )

        reference_valid = (
            reference_flat[
                consistent
            ]
        )

        current_valid = (
            forward_flat[
                consistent
            ]
        )

        tracked_count = int(
            len(
                reference_valid
            )
        )

        # Large physical camera movement often arrives here.
        if (
            tracked_count
            <
            self.config.min_tracked_points
        ):

            fallback = (
                self._fallback_geometric_evidence(
                    gray,
                    mask,
                )
            )

            if fallback is not None:
                return self._use_fallback_evidence(
                    fallback
                )

            return self._reference_lost(
                "INSUFFICIENT_TRACKED_POINTS",

                tracked_points=(
                    tracked_count
                ),
            )

        # Reference is successfully visible again.
        self._clear_reference_loss()

        # ====================================================
        # RANSAC GLOBAL TRANSFORM
        # ====================================================

        matrix, inliers = (
            cv2.estimateAffinePartial2D(
                reference_valid,
                current_valid,
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

            fallback = (
                self._fallback_geometric_evidence(
                    gray,
                    mask,
                )
            )

            if fallback is not None:
                return self._use_fallback_evidence(
                    fallback
                )

            return self._reference_lost(
                "GLOBAL_TRANSFORM_UNAVAILABLE",

                tracked_points=(
                    tracked_count
                ),
            )
        self._reference_tracking_confirmed = True
        inlier_mask = (
            inliers.reshape(
                -1
            )
            ==
            1
        )

        inlier_count = int(
            np.count_nonzero(
                inlier_mask
            )
        )

        inlier_ratio = (
            inlier_count
            /
            max(
                1,
                tracked_count,
            )
        )

        reference_inliers = (
            reference_valid[
                inlier_mask
            ]
        )

        spatial = (
            self._runtime_region_support(
                reference_inliers,
                gray.shape[1],
                gray.shape[0],
            )
        )

        # ====================================================
        # TRANSFORM
        # ====================================================

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

        translation_px = (
            math.hypot(
                translation_x,
                translation_y,
            )
        )

        diagonal = (
            math.hypot(
                gray.shape[1],
                gray.shape[0],
            )
        )

        translation_ratio = (
            translation_px
            /
            max(
                diagonal,
                1.0,
            )
        )

        scale = (
            math.hypot(
                a,
                b,
            )
        )

        scale_change = abs(
            scale
            -
            1.0
        )

        rotation_deg = (
            math.degrees(
                math.atan2(
                    b,
                    a,
                )
            )
        )

        # ====================================================
        # QUALITY
        # ====================================================

        evidence_valid = (
            inlier_count
            >=
            self.config.min_inlier_count

            and

            inlier_ratio
            >=
            self.config.min_inlier_ratio

            and

            spatial[
                "spatial_support_valid"
            ]
        )

        policy = (
            self._movement_policy(
                translation_ratio=(
                    translation_ratio
                ),
                rotation_deg=(
                    rotation_deg
                ),
                scale_change=(
                    scale_change
                ),
            )
        )

        candidate = (
            evidence_valid
            and
            policy[
                "movement"
            ]
        )

        # ====================================================
        # TEMPORAL VOTING
        # ====================================================

        self._movement_votes.append(
            bool(
                candidate
            )
        )

        movement_hits = int(
            sum(
                self._movement_votes
            )
        )

        result = {
            "status":
                STATUS_STABLE,

            "reason":
                (
                    "MOVEMENT_CANDIDATE"
                    if candidate
                    else
                    "STABLE"
                ),

            "tracked_points":
                tracked_count,

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
                    scale
                ),

            "scale_change":
                float(
                    scale_change
                ),

            "evidence_valid":
                bool(
                    evidence_valid
                ),

            "reference_loss_count":
                0,

            "movement_votes":
                movement_hits,

            "movement_window":
                int(
                    len(
                        self._movement_votes
                    )
                ),

            **spatial,
            **policy,
        }

        if (
            len(
                self._movement_votes
            )
            >=
            self.config.confirmation_window

            and

            movement_hits
            >=
            self.config.confirmation_hits
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
                "CONFIRMED_GLOBAL_CAMERA_MOVEMENT"
            )

        self.last_result = (
            result
        )

        return dict(
            result
        )