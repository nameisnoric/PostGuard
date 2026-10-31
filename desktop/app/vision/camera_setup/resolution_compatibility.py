from __future__ import annotations

import math
from typing import Any


RESOLUTION_COMPATIBLE = "COMPATIBLE"
RESOLUTION_MISMATCH = "MISMATCH"
RESOLUTION_NOT_EVALUATED = "NOT_EVALUATED"


def _positive_integer(value: Any) -> int | None:
    """
    Convert a value to a positive integer only when it represents
    a valid whole-number pixel dimension.

    bool is intentionally rejected because bool is a subclass of int.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, float):
        if (
            math.isfinite(value)
            and value > 0
            and value.is_integer()
        ):
            return int(value)

    return None


def extract_baseline_resolution(
    baseline: dict | None,
) -> tuple[int, int] | None:
    """
    Read the authoritative camera resolution stored with
    the Personal Baseline.

    Returns:
        (width, height)

    or None when the baseline does not contain a usable resolution.
    """

    if not isinstance(baseline, dict):
        return None

    width = _positive_integer(
        baseline.get("camera_frame_width")
    )

    height = _positive_integer(
        baseline.get("camera_frame_height")
    )

    if width is None or height is None:
        return None

    return width, height


def extract_frame_resolution(
    frame: Any,
) -> tuple[int, int] | None:
    """
    Read the actual resolution from a frame returned by camera.read().

    OpenCV frame.shape:
        (height, width, channels)

    The real frame is the source of truth. We intentionally do not use
    CAP_PROP_FRAME_WIDTH / CAP_PROP_FRAME_HEIGHT as proof that the camera
    actually produced the requested resolution.
    """

    if frame is None:
        return None

    shape = getattr(frame, "shape", None)

    if shape is None or len(shape) < 2:
        return None

    height = _positive_integer(shape[0])
    width = _positive_integer(shape[1])

    if width is None or height is None:
        return None

    return width, height


def evaluate_resolution_compatibility(
    baseline: dict | None,
    frame: Any,
) -> dict:
    """
    Compare Personal-Baseline resolution with the resolution of an
    actual frame read when Monitoring starts.

    Exact equality is required because the current PostGuard baseline
    contains pixel-based measurements such as eye distance.

    This function does not:
    - resize the frame,
    - change calibration,
    - apply camera roll correction,
    - apply perspective correction,
    - modify Posture Risk / RULA.
    """

    expected = extract_baseline_resolution(
        baseline
    )

    if expected is None:
        return {
            "evaluated": False,
            "status": RESOLUTION_NOT_EVALUATED,
            "compatible": False,
            "expected_width": None,
            "expected_height": None,
            "actual_width": None,
            "actual_height": None,
            "reason": "invalid_baseline_resolution",
        }

    expected_width, expected_height = expected

    actual = extract_frame_resolution(
        frame
    )

    if actual is None:
        return {
            "evaluated": False,
            "status": RESOLUTION_NOT_EVALUATED,
            "compatible": False,
            "expected_width": expected_width,
            "expected_height": expected_height,
            "actual_width": None,
            "actual_height": None,
            "reason": "invalid_camera_frame",
        }

    actual_width, actual_height = actual

    compatible = (
        actual_width == expected_width
        and
        actual_height == expected_height
    )

    return {
        "evaluated": True,
        "status": (
            RESOLUTION_COMPATIBLE
            if compatible
            else RESOLUTION_MISMATCH
        ),
        "compatible": compatible,
        "expected_width": expected_width,
        "expected_height": expected_height,
        "actual_width": actual_width,
        "actual_height": actual_height,
        "reason": (
            "resolution_match"
            if compatible
            else "resolution_mismatch"
        ),
    }