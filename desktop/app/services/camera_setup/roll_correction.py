"""Shared camera-roll preprocessing for Camera Setup, Baseline and Monitoring.

Flow:
    raw frame
    -> Auto Roll estimate (Camera Setup only)
    -> stabilize / lock once
    -> automatic image correction
    -> Reference Card
    -> Baseline
    -> Monitoring

Goals:
    - Support Camera Roll in both directions.
    - Keep a normal camera close to 0 degrees.
    - Show candidate angle before Auto lock.
    - Apply one locked correction throughout the session.
    - Remove black borders after rotation by scaling the corrected image.
"""

from __future__ import annotations

import cv2
import numpy as np


# ============================================================
# PUBLIC CONTRACT
# ============================================================

ROLL_SOURCE_AUTO = "AUTO_CONFIRMED"
ROLL_SOURCE_USER = "USER_CONFIRMED"

ROLL_SOURCES = (
    ROLL_SOURCE_AUTO,
    ROLL_SOURCE_USER,
)

ROLL_LIMIT_DEG = 30.0


# ============================================================
# MULTI-FRAME AUTO LOCK
# ============================================================

AUTO_WINDOW = 6
AUTO_MAX_SPREAD_DEG = 2.0
AUTO_MAX_ATTEMPTS = 60


# ============================================================
# SINGLE-FRAME SETTINGS
# ============================================================

NEUTRAL_DEADZONE_DEG = 0.80

DUAL_AXIS_AGREEMENT_DEG = 3.0
AXIS_SPREAD_MAX_DEG = 2.5

SPATIAL_COLS = 4
SPATIAL_ROWS = 3

MIN_AXIS_LINES = 2
MIN_AXIS_BINS = 2

SINGLE_AXIS_MIN_LINES = 3
SINGLE_AXIS_MIN_BINS = 2
SINGLE_AXIS_MAX_SPREAD_DEG = 2.0
SINGLE_AXIS_MIN_CONSISTENCY = 0.60

NEUTRAL_MIN_BINS = 2
NEUTRAL_SUPPORT_RADIUS_DEG = 1.75
NEUTRAL_MIN_SUPPORT_RATIO = 0.55

MAX_AXIS_DEVIATION_DEG = 30.0

LINE_WEIGHT_CAP_RATIO = 0.22


# ============================================================
# SIGN CONVENTION
# ============================================================

def correction_from_detected_tilt(
    detected_camera_tilt_deg,
):
    """
    Correction must be opposite to detected Camera Roll.

    Real / detected +4°
        -> correction -4°

    Real / detected -4°
        -> correction +4°
    """

    return -float(
        detected_camera_tilt_deg
    )


# ============================================================
# FRAME CORRECTION
# ============================================================

def _borderless_rotation_scale(
    width,
    height,
    roll_deg,
):
    """
    Calculate the minimum zoom needed to hide black borders
    after rotation while keeping the output width/height unchanged.

    This is the same idea used by the older PostGuard
    Camera Roll implementation.
    """

    angle_rad = np.radians(
        abs(
            float(
                roll_deg
            )
        )
    )

    cos_a = float(
        np.cos(
            angle_rad
        )
    )

    sin_a = float(
        np.sin(
            angle_rad
        )
    )

    width = float(
        max(
            width,
            1,
        )
    )

    height = float(
        max(
            height,
            1,
        )
    )

    scale_x = (
        cos_a
        +
        (
            height
            /
            width
        )
        *
        sin_a
    )

    scale_y = (
        cos_a
        +
        (
            width
            /
            height
        )
        *
        sin_a
    )

    scale = max(
        scale_x,
        scale_y,
        1.0,
    )

    return float(
        scale
    )


def level_frame(
    frame,
    roll_deg,
    remove_black_border=True,
):
    """
    Correct Camera Roll.

    Output:
        - same width
        - same height
        - corrected roll

    remove_black_border=True:
        zooms the rotated image just enough to avoid black corners.

    The same locked correction is later used by:
        Camera Reference
        Baseline
        Monitoring

    Therefore all three stages see the same corrected geometry.
    """

    if frame is None:
        return frame

    angle = float(
        roll_deg
        or
        0.0
    )

    if abs(
        angle
    ) <= 1e-9:
        return frame

    height, width = (
        frame.shape[:2]
    )

    if remove_black_border:

        scale = (
            _borderless_rotation_scale(
                width,
                height,
                angle,
            )
        )

    else:
        scale = 1.0

    matrix = (
        cv2.getRotationMatrix2D(
            (
                width / 2.0,
                height / 2.0,
            ),
            angle,
            scale,
        )
    )

    corrected = cv2.warpAffine(
        frame,
        matrix,
        (
            width,
            height,
        ),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(
            0,
            0,
            0,
        ),
    )

    return corrected


def prepare_frame(
    frame,
    camera_calibration,
):
    """
    Apply only a locked Camera Roll correction.

    card_roll_deg is intentionally ignored.

    Border removal is always enabled so Camera Setup,
    Baseline and Monitoring receive the same transform.
    """

    angle = 0.0

    if (
        isinstance(
            camera_calibration,
            dict,
        )
        and
        camera_calibration.get(
            "roll_correction_source"
        )
        in
        ROLL_SOURCES
    ):

        angle = float(
            camera_calibration.get(
                "roll_correction_deg"
            )
            or
            0.0
        )

    return level_frame(
        frame,
        angle,
        remove_black_border=True,
    )


# ============================================================
# VISUAL GRID
# ============================================================

def draw_level_grid(
    frame,
    step=160,
):
    """
    Visual alignment grid only.

    Never run Auto estimator on a frame
    after this grid has been drawn.
    """

    height, width = (
        frame.shape[:2]
    )

    for x in range(
        step,
        width,
        step,
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
            1,
        )

    for y in range(
        step,
        height,
        step,
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
            1,
        )

    cv2.line(
        frame,
        (
            width // 2,
            0,
        ),
        (
            width // 2,
            height,
        ),
        (
            0,
            255,
            255,
        ),
        2,
    )

    cv2.line(
        frame,
        (
            0,
            height // 2,
        ),
        (
            width,
            height // 2,
        ),
        (
            0,
            255,
            255,
        ),
        2,
    )

    return frame


# ============================================================
# ROBUST HELPERS
# ============================================================

def _normalize_axis_angle(
    angle_deg,
):
    """
    Convert a line angle into deviation from
    the nearest horizontal or vertical axis.

    Result:
        -45° .. +45°
    """

    return (
        float(
            angle_deg
        )
        +
        45.0
    ) % 90.0 - 45.0


def _weighted_median(
    values,
    weights,
):

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    weights = np.asarray(
        weights,
        dtype=np.float64,
    )

    if (
        values.size == 0
        or
        values.size
        !=
        weights.size
    ):

        return None

    total = float(
        np.sum(
            weights
        )
    )

    if total <= 0.0:
        return None

    order = np.argsort(
        values
    )

    values = values[
        order
    ]

    weights = weights[
        order
    ]

    cumulative = np.cumsum(
        weights
    )

    index = int(
        np.searchsorted(
            cumulative,
            total * 0.5,
            side="left",
        )
    )

    index = min(
        index,
        len(
            values
        )
        -
        1,
    )

    return float(
        values[
            index
        ]
    )


def _mad(
    values,
    center,
):

    if not values:
        return None

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    return float(
        np.median(
            np.abs(
                values
                -
                float(
                    center
                )
            )
        )
    )


def _spatial_bin(
    x,
    y,
    width,
    height,
):

    col = int(
        (
            float(
                x
            )
            /
            max(
                float(
                    width
                ),
                1.0,
            )
        )
        *
        SPATIAL_COLS
    )

    row = int(
        (
            float(
                y
            )
            /
            max(
                float(
                    height
                ),
                1.0,
            )
        )
        *
        SPATIAL_ROWS
    )

    col = max(
        0,
        min(
            SPATIAL_COLS - 1,
            col,
        ),
    )

    row = max(
        0,
        min(
            SPATIAL_ROWS - 1,
            row,
        ),
    )

    return (
        row,
        col,
    )


# ============================================================
# AXIS SUMMARY
# ============================================================

def _axis_summary(
    records,
):
    """
    Summarize structural evidence for one axis.

    Every spatial region contributes one representative angle,
    reducing domination by one object.
    """

    if len(
        records
    ) < MIN_AXIS_LINES:

        return None

    by_bin = {}

    for record in records:

        by_bin.setdefault(
            record[
                "bin"
            ],
            [],
        ).append(
            record
        )

    bin_angles = []

    for bin_records in (
        by_bin.values()
    ):

        values = [
            record[
                "angle"
            ]
            for record
            in bin_records
        ]

        weights = [
            record[
                "weight"
            ]
            for record
            in bin_records
        ]

        value = (
            _weighted_median(
                values,
                weights,
            )
        )

        if value is not None:

            bin_angles.append(
                float(
                    value
                )
            )

    if not bin_angles:
        return None

    center = float(
        np.median(
            np.asarray(
                bin_angles,
                dtype=np.float64,
            )
        )
    )

    spread = _mad(
        bin_angles,
        center,
    )

    if spread is None:
        spread = 0.0

    close_count = sum(
        1
        for angle
        in bin_angles
        if abs(
            angle - center
        ) <= 2.0
    )

    consistency = (
        close_count
        /
        len(
            bin_angles
        )
    )

    return {
        "angle":
            center,

        "spread":
            float(
                spread
            ),

        "lines":
            len(
                records
            ),

        "bins":
            len(
                bin_angles
            ),

        "bin_angles":
            bin_angles,

        "consistency":
            float(
                consistency
            ),
    }


# ============================================================
# STRUCTURAL LINE EXTRACTION
# ============================================================

def _extract_evidence(
    frame,
):

    if frame is None:
        return None

    height, width = (
        frame.shape[:2]
    )

    if (
        height < 80
        or
        width < 80
    ):

        return None

    x0 = int(
        width * 0.05
    )

    x1 = int(
        width * 0.95
    )

    y0 = int(
        height * 0.05
    )

    y1 = int(
        height * 0.95
    )

    crop = frame[
        y0:y1,
        x0:x1,
    ]

    if crop.size == 0:
        return None

    crop_height, crop_width = (
        crop.shape[:2]
    )

    gray = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2GRAY,
    )

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(
            8,
            8,
        ),
    )

    gray = clahe.apply(
        gray
    )

    blurred = cv2.GaussianBlur(
        gray,
        (
            5,
            5,
        ),
        0,
    )

    edges = cv2.Canny(
        blurred,
        40,
        120,
    )

    min_dimension = min(
        crop_height,
        crop_width,
    )

    min_line_length = max(
        35,
        int(
            min_dimension
            *
            0.10
        ),
    )

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 360.0,
        threshold=30,
        minLineLength=min_line_length,
        maxLineGap=30,
    )

    if lines is None:
        return None

    horizontal = []
    vertical = []

    diagonal = float(
        np.hypot(
            crop_width,
            crop_height,
        )
    )

    max_weight = (
        diagonal
        *
        LINE_WEIGHT_CAP_RATIO
    )

    for (
        x_start,
        y_start,
        x_end,
        y_end,
    ) in lines.reshape(
        -1,
        4,
    ):

        dx = float(
            x_end - x_start
        )

        dy = float(
            y_end - y_start
        )

        length = float(
            np.hypot(
                dx,
                dy,
            )
        )

        if (
            length
            <
            min_line_length
        ):
            continue

        raw_angle = float(
            np.degrees(
                np.arctan2(
                    dy,
                    dx,
                )
            )
        )

        orientation = (
            raw_angle
            %
            180.0
        )

        horizontal_distance = min(
            orientation,
            180.0
            -
            orientation,
        )

        vertical_distance = abs(
            orientation
            -
            90.0
        )

        if (
            min(
                horizontal_distance,
                vertical_distance,
            )
            >
            MAX_AXIS_DEVIATION_DEG
        ):
            continue

        axis_angle = (
            _normalize_axis_angle(
                raw_angle
            )
        )

        if (
            abs(
                axis_angle
            )
            >
            ROLL_LIMIT_DEG
        ):
            continue

        midpoint_x = (
            float(
                x_start
                +
                x_end
            )
            *
            0.5
        )

        midpoint_y = (
            float(
                y_start
                +
                y_end
            )
            *
            0.5
        )

        bin_id = (
            _spatial_bin(
                midpoint_x,
                midpoint_y,
                crop_width,
                crop_height,
            )
        )

        record = {
            "angle":
                float(
                    axis_angle
                ),

            "weight":
                float(
                    min(
                        length,
                        max_weight,
                    )
                ),

            "bin":
                bin_id,
        }

        if (
            horizontal_distance
            <=
            vertical_distance
        ):

            horizontal.append(
                record
            )

        else:

            vertical.append(
                record
            )

    return {
        "horizontal":
            horizontal,

        "vertical":
            vertical,
    }


# ============================================================
# NEUTRAL CHECK
# ============================================================

def _neutral_from_available_axes(
    horizontal,
    vertical,
):
    """
    Level-camera fast path.

    Both axes are not required.
    """

    bin_angles = []

    for summary in (
        horizontal,
        vertical,
    ):

        if summary is not None:

            bin_angles.extend(
                summary[
                    "bin_angles"
                ]
            )

    if (
        len(
            bin_angles
        )
        <
        NEUTRAL_MIN_BINS
    ):

        return False

    median_angle = float(
        np.median(
            np.asarray(
                bin_angles,
                dtype=np.float64,
            )
        )
    )

    if (
        abs(
            median_angle
        )
        >
        NEUTRAL_DEADZONE_DEG
    ):

        return False

    close = sum(
        1
        for angle
        in bin_angles
        if abs(
            angle
        )
        <=
        NEUTRAL_SUPPORT_RADIUS_DEG
    )

    support_ratio = (
        close
        /
        len(
            bin_angles
        )
    )

    return (
        support_ratio
        >=
        NEUTRAL_MIN_SUPPORT_RATIO
    )


# ============================================================
# SCENE ESTIMATOR
# ============================================================

def estimate_scene_tilt(
    frame,
):
    """
    Estimate structural scene roll.

    Paths:
        A) neutral
        B) dual-axis agreement
        C) strong single-axis fallback
    """

    evidence = (
        _extract_evidence(
            frame
        )
    )

    if evidence is None:
        return None

    horizontal = (
        _axis_summary(
            evidence[
                "horizontal"
            ]
        )
    )

    vertical = (
        _axis_summary(
            evidence[
                "vertical"
            ]
        )
    )

    # ========================================================
    # PATH A: neutral
    # ========================================================

    if (
        _neutral_from_available_axes(
            horizontal,
            vertical,
        )
    ):

        return 0.0

    # ========================================================
    # PATH B: dual-axis
    # ========================================================

    if (
        horizontal is not None
        and
        vertical is not None
        and
        horizontal[
            "bins"
        ]
        >=
        MIN_AXIS_BINS
        and
        vertical[
            "bins"
        ]
        >=
        MIN_AXIS_BINS
        and
        horizontal[
            "spread"
        ]
        <=
        AXIS_SPREAD_MAX_DEG
        and
        vertical[
            "spread"
        ]
        <=
        AXIS_SPREAD_MAX_DEG
    ):

        h_angle = float(
            horizontal[
                "angle"
            ]
        )

        v_angle = float(
            vertical[
                "angle"
            ]
        )

        agreement = abs(
            h_angle
            -
            v_angle
        )

        if (
            agreement
            <=
            DUAL_AXIS_AGREEMENT_DEG
        ):

            result = float(
                np.median(
                    np.asarray(
                        [
                            h_angle,
                            v_angle,
                        ],
                        dtype=np.float64,
                    )
                )
            )

            if (
                abs(
                    result
                )
                <=
                ROLL_LIMIT_DEG
            ):

                return result

    # ========================================================
    # PATH C: one strong axis
    # ========================================================

    candidates = []

    for summary in (
        horizontal,
        vertical,
    ):

        if summary is None:
            continue

        if (
            summary[
                "lines"
            ]
            <
            SINGLE_AXIS_MIN_LINES
        ):
            continue

        if (
            summary[
                "bins"
            ]
            <
            SINGLE_AXIS_MIN_BINS
        ):
            continue

        if (
            summary[
                "spread"
            ]
            >
            SINGLE_AXIS_MAX_SPREAD_DEG
        ):
            continue

        if (
            summary[
                "consistency"
            ]
            <
            SINGLE_AXIS_MIN_CONSISTENCY
        ):
            continue

        angle = float(
            summary[
                "angle"
            ]
        )

        if (
            abs(
                angle
            )
            >
            ROLL_LIMIT_DEG
        ):
            continue

        candidates.append(
            summary
        )

    if not candidates:
        return None

    best = max(
        candidates,
        key=lambda item: (
            item[
                "bins"
            ],
            item[
                "lines"
            ],
            -item[
                "spread"
            ],
        ),
    )

    return float(
        best[
            "angle"
        ]
    )


# ============================================================
# CAMERA TILT
# ============================================================

def detect_camera_tilt(
    frame,
):
    """
    Convert structural scene angle into physical Camera Roll.

    OpenCV/image coordinates use the opposite sign from
    the physical camera-roll convention used by PostGuard.

    Therefore:

        scene -4°
        -> detected camera tilt +4°
        -> correction -4°

        scene +4°
        -> detected camera tilt -4°
        -> correction +4°
    """

    scene_angle = estimate_scene_tilt(
        frame
    )

    if scene_angle is None:
        return None

    camera_tilt = -float(
        scene_angle
    )

    if (
        abs(camera_tilt)
        <=
        NEUTRAL_DEADZONE_DEG
    ):
        return 0.0

    return camera_tilt

# ============================================================
# MULTI-FRAME LOCK
# ============================================================

class AutoRollCollector:
    """
    Stabilize reliable estimates before applying correction.

    latest_* fields are visible before lock,
    so the UI can show candidate values.
    """

    DETECTING = "DETECTING"
    AUTO = "AUTO"
    UNAVAILABLE = "UNAVAILABLE"

    def __init__(
        self,
        estimator=detect_camera_tilt,
    ):

        self._estimator = (
            estimator
        )

        self.reset()

    def reset(
        self,
    ):

        self.status = (
            self.DETECTING
        )

        self.attempts = 0

        self.samples = []

        self.latest_detected_camera_tilt_deg = (
            None
        )

        self.latest_candidate_correction_deg = (
            None
        )

        self.detected_camera_tilt_deg = (
            None
        )

        self.roll_correction_deg = (
            None
        )

    def add(
        self,
        frame,
    ):

        if (
            self.status
            !=
            self.DETECTING
        ):

            return self.status

        self.attempts += 1

        detected = (
            self._estimator(
                frame
            )
        )

        if detected is not None:

            detected = float(
                detected
            )

            self.latest_detected_camera_tilt_deg = (
                detected
            )

            self.latest_candidate_correction_deg = (
                correction_from_detected_tilt(
                    detected
                )
            )

            if (
                abs(
                    detected
                )
                <=
                ROLL_LIMIT_DEG
            ):

                self.samples.append(
                    detected
                )

        recent = self.samples[
            -AUTO_WINDOW:
        ]

        if (
            len(
                recent
            )
            ==
            AUTO_WINDOW
        ):

            spread = float(
                max(
                    recent
                )
                -
                min(
                    recent
                )
            )

            if (
                spread
                <=
                AUTO_MAX_SPREAD_DEG
            ):

                tilt = float(
                    np.median(
                        np.asarray(
                            recent,
                            dtype=np.float64,
                        )
                    )
                )

                if (
                    abs(
                        tilt
                    )
                    <=
                    NEUTRAL_DEADZONE_DEG
                ):

                    tilt = 0.0

                correction = (
                    correction_from_detected_tilt(
                        tilt
                    )
                )

                if (
                    abs(
                        correction
                    )
                    <=
                    ROLL_LIMIT_DEG
                ):

                    self.detected_camera_tilt_deg = (
                        tilt
                    )

                    self.roll_correction_deg = (
                        correction
                    )

                    self.latest_detected_camera_tilt_deg = (
                        tilt
                    )

                    self.latest_candidate_correction_deg = (
                        correction
                    )

                    self.status = (
                        self.AUTO
                    )

                    return self.status

        if (
            self.attempts
            >=
            AUTO_MAX_ATTEMPTS
        ):

            self.status = (
                self.UNAVAILABLE
            )

        return self.status