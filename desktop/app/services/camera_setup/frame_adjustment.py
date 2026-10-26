"""Apply the numeric camera alignment captured during camera preparation."""

import math

import cv2


def adjust_camera_frame(frame, calibration_reference):
    """Return a level frame using the saved card roll, preserving frame size."""
    if frame is None or getattr(frame, "size", 0) == 0:
        return frame
    if not isinstance(calibration_reference, dict):
        return frame
    if calibration_reference.get("status") != "VALID":
        return frame

    roll = calibration_reference.get("card_roll_deg")
    if isinstance(roll, bool) or not isinstance(roll, (int, float)):
        return frame
    roll = float(roll)
    if not math.isfinite(roll) or abs(roll) < 0.01:
        return frame

    height, width = frame.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, roll, 1.0)
    return cv2.warpAffine(
        frame,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
