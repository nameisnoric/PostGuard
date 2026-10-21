import math
import statistics
import time


CONTEXT_VALID = "VALID"
CONTEXT_TRANSITION = "TRANSITION"
CONTEXT_UNKNOWN = "UNKNOWN"


class PostureContextFilter:
    """
    Context / Quality Filter สำหรับ PostGuard

    VALID
    -----
    Landmark ส่วนบนใช้งานได้
    และผู้ใช้นิ่งพอที่จะนำ Feature ไปประเมิน

    TRANSITION
    ----------
    ผู้ใช้กำลังเปลี่ยนท่า เช่น
    - ก้มคอ
    - เงยคอ
    - หันหัว
    - ยกไหล่
    - ขยับตัว

    เมื่อหยุดและค้างท่า
    ระบบต้องกลับเป็น VALID

    UNKNOWN
    -------
    Landmark หลักใช้งานไม่ได้ เช่น
    - Pose หาย
    - ไหล่หาย
    - Visibility ต่ำ
    - ไหล่หลุดเฟรม
    - ผู้ใช้อยู่ไกลเกินไป

    Important
    ---------
    Required:
        left_shoulder
        right_shoulder

    Optional Motion Points:
        nose
        left_ear
        right_ear

    ไม่ใช้:
        hip
        waist
        knee
        ankle
    """

    REQUIRED_POINTS = (
        "left_shoulder",
        "right_shoulder",
    )

    OPTIONAL_MOTION_POINTS = (
        "nose",
        "left_ear",
        "right_ear",
    )

    def __init__(
        self,
        min_visibility=0.45,
        min_presence=0.45,
        min_shoulder_width_ratio=0.04,
        frame_margin_ratio=0.015,
        median_motion_threshold=0.025,
        max_motion_threshold=0.070,
        stable_time_seconds=0.35,
        max_frame_gap_seconds=0.75,
    ):
        self.min_visibility = float(
            min_visibility
        )

        self.min_presence = float(
            min_presence
        )

        self.min_shoulder_width_ratio = float(
            min_shoulder_width_ratio
        )

        self.frame_margin_ratio = float(
            frame_margin_ratio
        )

        self.median_motion_threshold = float(
            median_motion_threshold
        )

        self.max_motion_threshold = float(
            max_motion_threshold
        )

        self.stable_time_seconds = float(
            stable_time_seconds
        )

        self.max_frame_gap_seconds = float(
            max_frame_gap_seconds
        )

        self._previous_points = None

        self._previous_timestamp = None

        self._stable_since = None

    # ======================================================
    # Reset
    # ======================================================

    def reset(self):
        """
        Reset temporal state

        ใช้เมื่อ:
        - เริ่ม Session ใหม่
        - เปลี่ยนกล้อง
        - กล้องกลับมาหลังจากหลุด
        - Pose หาย
        """

        self._previous_points = None

        self._previous_timestamp = None

        self._stable_since = None

    # ======================================================
    # Numeric Helper
    # ======================================================

    @staticmethod
    def _is_finite_number(
        value
    ):
        if value is None:
            return False

        try:
            return math.isfinite(
                float(value)
            )

        except (
            TypeError,
            ValueError,
        ):
            return False

    # ======================================================
    # Distance
    # ======================================================

    @staticmethod
    def _distance(
        point_a,
        point_b,
    ):
        return math.hypot(
            float(
                point_b["x"]
            )
            -
            float(
                point_a["x"]
            ),
            float(
                point_b["y"]
            )
            -
            float(
                point_a["y"]
            ),
        )

    # ======================================================
    # Basic Coordinate Validation
    # ======================================================

    def _point_has_coordinates(
        self,
        point,
    ):
        if not isinstance(
            point,
            dict,
        ):
            return False

        return (
            self._is_finite_number(
                point.get(
                    "x"
                )
            )
            and
            self._is_finite_number(
                point.get(
                    "y"
                )
            )
        )

    # ======================================================
    # Required Landmark Quality
    # ======================================================

    def _required_point_quality_ok(
        self,
        point,
    ):
        if not self._point_has_coordinates(
            point
        ):
            return False

        visibility = point.get(
            "visibility"
        )

        if visibility is not None:

            if not self._is_finite_number(
                visibility
            ):
                return False

            if (
                float(
                    visibility
                )
                <
                self.min_visibility
            ):
                return False

        presence = point.get(
            "presence"
        )

        if presence is not None:

            if not self._is_finite_number(
                presence
            ):
                return False

            if (
                float(
                    presence
                )
                <
                self.min_presence
            ):
                return False

        return True

    # ======================================================
    # Frame Boundary
    # ======================================================

    def _point_inside_frame(
        self,
        point,
        frame_width,
        frame_height,
    ):
        if not self._point_has_coordinates(
            point
        ):
            return False

        x = float(
            point["x"]
        )

        y = float(
            point["y"]
        )

        margin_x = (
            float(
                frame_width
            )
            *
            self.frame_margin_ratio
        )

        margin_y = (
            float(
                frame_height
            )
            *
            self.frame_margin_ratio
        )

        return (
            margin_x
            <= x
            <= (
                float(
                    frame_width
                )
                -
                margin_x
            )
            and
            margin_y
            <= y
            <= (
                float(
                    frame_height
                )
                -
                margin_y
            )
        )

    # ======================================================
    # Quality Check
    # ======================================================

    def _quality_check(
        self,
        points,
        frame_width,
        frame_height,
    ):
        if (
            not self._is_finite_number(
                frame_width
            )
            or
            not self._is_finite_number(
                frame_height
            )
        ):
            return {
                "valid": False,
                "reason": "invalid_frame_size",
                "shoulder_width_px": None,
            }

        frame_width = float(
            frame_width
        )

        frame_height = float(
            frame_height
        )

        if (
            frame_width <= 0
            or
            frame_height <= 0
        ):
            return {
                "valid": False,
                "reason": "invalid_frame_size",
                "shoulder_width_px": None,
            }

        if not isinstance(
            points,
            dict,
        ):
            return {
                "valid": False,
                "reason": "pose_not_detected",
                "shoulder_width_px": None,
            }

        # --------------------------------------------------
        # Required Points
        # --------------------------------------------------

        for point_name in (
            self.REQUIRED_POINTS
        ):
            point = points.get(
                point_name
            )

            if point is None:

                return {
                    "valid": False,
                    "reason": (
                        f"missing_{point_name}"
                    ),
                    "shoulder_width_px": None,
                }

            if not self._required_point_quality_ok(
                point
            ):
                return {
                    "valid": False,
                    "reason": (
                        f"low_quality_"
                        f"{point_name}"
                    ),
                    "shoulder_width_px": None,
                }

            if not self._point_inside_frame(
                point,
                frame_width,
                frame_height,
            ):
                return {
                    "valid": False,
                    "reason": (
                        f"{point_name}_"
                        "near_or_outside_frame"
                    ),
                    "shoulder_width_px": None,
                }

        # --------------------------------------------------
        # Shoulder Width
        # --------------------------------------------------

        left_shoulder = (
            points[
                "left_shoulder"
            ]
        )

        right_shoulder = (
            points[
                "right_shoulder"
            ]
        )

        shoulder_width_px = (
            self._distance(
                left_shoulder,
                right_shoulder,
            )
        )

        minimum_width_px = (
            frame_width
            *
            self.min_shoulder_width_ratio
        )

        if (
            shoulder_width_px
            <
            minimum_width_px
        ):
            return {
                "valid": False,

                "reason": (
                    "shoulders_too_small_"
                    "or_user_too_far"
                ),

                "shoulder_width_px": float(
                    shoulder_width_px
                ),
            }

        return {
            "valid": True,

            "reason": "quality_ok",

            "shoulder_width_px": float(
                shoulder_width_px
            ),
        }

    # ======================================================
    # Optional Motion Point
    # ======================================================

    def _motion_point_available(
        self,
        point,
        frame_width,
        frame_height,
    ):
        if not self._point_has_coordinates(
            point
        ):
            return False

        if not self._point_inside_frame(
            point,
            frame_width,
            frame_height,
        ):
            return False

        visibility = point.get(
            "visibility"
        )

        if visibility is not None:

            if not self._is_finite_number(
                visibility
            ):
                return False

            if (
                float(
                    visibility
                )
                <
                0.25
            ):
                return False

        return True

    # ======================================================
    # Snapshot
    # ======================================================

    def _create_snapshot(
        self,
        points,
        frame_width,
        frame_height,
    ):
        snapshot = {}

        # --------------------------------------------------
        # Shoulders always included
        # --------------------------------------------------

        for point_name in (
            self.REQUIRED_POINTS
        ):
            point = points.get(
                point_name
            )

            if self._point_has_coordinates(
                point
            ):
                snapshot[
                    point_name
                ] = {
                    "x": float(
                        point["x"]
                    ),
                    "y": float(
                        point["y"]
                    ),
                }

        # --------------------------------------------------
        # Head points optional
        # --------------------------------------------------

        for point_name in (
            self.OPTIONAL_MOTION_POINTS
        ):
            point = points.get(
                point_name
            )

            if self._motion_point_available(
                point,
                frame_width,
                frame_height,
            ):
                snapshot[
                    point_name
                ] = {
                    "x": float(
                        point["x"]
                    ),
                    "y": float(
                        point["y"]
                    ),
                }

        return snapshot

    # ======================================================
    # Motion
    # ======================================================

    def _calculate_motion_scores(
        self,
        current_snapshot,
        shoulder_width_px,
    ):
        if (
            self._previous_points
            is None
        ):
            return (
                None,
                None,
                0,
            )

        if (
            shoulder_width_px
            <=
            1e-6
        ):
            return (
                None,
                None,
                0,
            )

        common_points = (
            set(
                self._previous_points.keys()
            )
            &
            set(
                current_snapshot.keys()
            )
        )

        if not common_points:
            return (
                None,
                None,
                0,
            )

        normalized_displacements = []

        for point_name in (
            common_points
        ):
            previous = (
                self._previous_points[
                    point_name
                ]
            )

            current = (
                current_snapshot[
                    point_name
                ]
            )

            displacement_px = math.hypot(
                current["x"]
                -
                previous["x"],
                current["y"]
                -
                previous["y"],
            )

            normalized_displacement = (
                displacement_px
                /
                shoulder_width_px
            )

            normalized_displacements.append(
                float(
                    normalized_displacement
                )
            )

        if not normalized_displacements:
            return (
                None,
                None,
                0,
            )

        median_motion = float(
            statistics.median(
                normalized_displacements
            )
        )

        max_motion = float(
            max(
                normalized_displacements
            )
        )

        return (
            median_motion,
            max_motion,
            len(
                normalized_displacements
            ),
        )

    # ======================================================
    # Result
    # ======================================================

    @staticmethod
    def _build_result(
        state,
        allow_posture_evaluation,
        reason,
        shoulder_width_px=None,
        median_motion=None,
        max_motion=None,
        motion_points_used=0,
        stable_seconds=0.0,
    ):
        return {
            "state": (
                state
            ),

            "allow_posture_evaluation": bool(
                allow_posture_evaluation
            ),

            "reason": (
                reason
            ),

            "shoulder_width_px": (
                float(
                    shoulder_width_px
                )
                if shoulder_width_px
                is not None
                else None
            ),

            "median_motion": (
                float(
                    median_motion
                )
                if median_motion
                is not None
                else None
            ),

            "max_motion": (
                float(
                    max_motion
                )
                if max_motion
                is not None
                else None
            ),

            "motion_points_used": int(
                motion_points_used
            ),

            "stable_seconds": float(
                stable_seconds
            ),
        }

    # ======================================================
    # Update
    # ======================================================

    def update(
        self,
        points,
        frame_width,
        frame_height,
        timestamp=None,
    ):
        if timestamp is None:
            timestamp = (
                time.perf_counter()
            )

        if not self._is_finite_number(
            timestamp
        ):
            timestamp = (
                time.perf_counter()
            )

        timestamp = float(
            timestamp
        )

        # --------------------------------------------------
        # Landmark Quality
        # --------------------------------------------------

        quality = (
            self._quality_check(
                points,
                frame_width,
                frame_height,
            )
        )

        if not quality[
            "valid"
        ]:
            reason = (
                quality[
                    "reason"
                ]
            )

            shoulder_width_px = (
                quality.get(
                    "shoulder_width_px"
                )
            )

            self.reset()

            return self._build_result(
                state=CONTEXT_UNKNOWN,

                allow_posture_evaluation=False,

                reason=reason,

                shoulder_width_px=(
                    shoulder_width_px
                ),
            )

        shoulder_width_px = float(
            quality[
                "shoulder_width_px"
            ]
        )

        # --------------------------------------------------
        # Snapshot
        # --------------------------------------------------

        current_snapshot = (
            self._create_snapshot(
                points,
                frame_width,
                frame_height,
            )
        )

        # --------------------------------------------------
        # Frame Gap
        # --------------------------------------------------

        if (
            self._previous_timestamp
            is not None
        ):
            frame_gap = (
                timestamp
                -
                self._previous_timestamp
            )

            if (
                frame_gap < 0
                or
                frame_gap
                >
                self.max_frame_gap_seconds
            ):
                self.reset()

                self._previous_points = (
                    current_snapshot
                )

                self._previous_timestamp = (
                    timestamp
                )

                return self._build_result(
                    state=CONTEXT_TRANSITION,

                    allow_posture_evaluation=False,

                    reason="frame_gap_reset",

                    shoulder_width_px=(
                        shoulder_width_px
                    ),
                )

        # --------------------------------------------------
        # First Valid Frame
        # --------------------------------------------------

        if (
            self._previous_points
            is None
        ):
            self._previous_points = (
                current_snapshot
            )

            self._previous_timestamp = (
                timestamp
            )

            self._stable_since = None

            return self._build_result(
                state=CONTEXT_TRANSITION,

                allow_posture_evaluation=False,

                reason="warming_up",

                shoulder_width_px=(
                    shoulder_width_px
                ),
            )

        # --------------------------------------------------
        # Motion Score
        # --------------------------------------------------

        (
            median_motion,
            max_motion,
            motion_points_used,
        ) = self._calculate_motion_scores(
            current_snapshot,
            shoulder_width_px,
        )

        self._previous_points = (
            current_snapshot
        )

        self._previous_timestamp = (
            timestamp
        )

        if (
            median_motion is None
            or
            max_motion is None
        ):
            self._stable_since = None

            return self._build_result(
                state=CONTEXT_TRANSITION,

                allow_posture_evaluation=False,

                reason="motion_not_available",

                shoulder_width_px=(
                    shoulder_width_px
                ),

                motion_points_used=(
                    motion_points_used
                ),
            )

        # --------------------------------------------------
        # Moving?
        # --------------------------------------------------

        is_moving = (
            median_motion
            >
            self.median_motion_threshold

            or

            max_motion
            >
            self.max_motion_threshold
        )

        if is_moving:
            self._stable_since = None

            return self._build_result(
                state=CONTEXT_TRANSITION,

                allow_posture_evaluation=False,

                reason="posture_transition",

                shoulder_width_px=(
                    shoulder_width_px
                ),

                median_motion=(
                    median_motion
                ),

                max_motion=(
                    max_motion
                ),

                motion_points_used=(
                    motion_points_used
                ),

                stable_seconds=0.0,
            )

        # --------------------------------------------------
        # Stable Timer
        # --------------------------------------------------

        if self._stable_since is None:
            self._stable_since = (
                timestamp
            )

        stable_seconds = max(
            0.0,
            timestamp
            -
            self._stable_since,
        )

        if (
            stable_seconds
            <
            self.stable_time_seconds
        ):
            return self._build_result(
                state=CONTEXT_TRANSITION,

                allow_posture_evaluation=False,

                reason="stabilizing",

                shoulder_width_px=(
                    shoulder_width_px
                ),

                median_motion=(
                    median_motion
                ),

                max_motion=(
                    max_motion
                ),

                motion_points_used=(
                    motion_points_used
                ),

                stable_seconds=(
                    stable_seconds
                ),
            )

        # --------------------------------------------------
        # VALID
        # --------------------------------------------------

        return self._build_result(
            state=CONTEXT_VALID,

            allow_posture_evaluation=True,

            reason="stable_upper_body",

            shoulder_width_px=(
                shoulder_width_px
            ),

            median_motion=(
                median_motion
            ),

            max_motion=(
                max_motion
            ),

            motion_points_used=(
                motion_points_used
            ),

            stable_seconds=(
                stable_seconds
            ),
        )