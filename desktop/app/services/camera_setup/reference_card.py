"""Reference-card camera preparation adapted from feature/camera commit 04211ba.

All frame processing stays on the desktop. Only the resulting numeric reference is
attached to the personal baseline; card images and camera frames are never stored.
"""

from datetime import datetime, timezone

import cv2
import numpy as np

CARD_WIDTH_MM = 85.60
CARD_HEIGHT_MM = 53.98
CARD_RATIO = CARD_WIDTH_MM / CARD_HEIGHT_MM


def order_corners(points):
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    sums = points.sum(axis=1)
    differences = points[:, 0] - points[:, 1]
    return np.array(
        [
            points[np.argmin(sums)],
            points[np.argmax(differences)],
            points[np.argmax(sums)],
            points[np.argmin(differences)],
        ],
        dtype=np.float32,
    )


def guide_bounds(frame, width_ratio=0.35):
    height, width = frame.shape[:2]
    guide_width = int(width * width_ratio)
    guide_height = int(guide_width / CARD_RATIO)
    center_x, center_y = width // 2, height // 2
    return (
        center_x - guide_width // 2,
        center_y - guide_height // 2,
        center_x + guide_width // 2,
        center_y + guide_height // 2,
    )


def _rectangle_angles_valid(box, minimum=65, maximum=115):
    for index in range(4):
        previous = box[(index - 1) % 4]
        current = box[index]
        following = box[(index + 1) % 4]
        first = previous - current
        second = following - current
        lengths = np.linalg.norm(first) * np.linalg.norm(second)
        if lengths == 0:
            return False
        cosine = np.clip(np.dot(first, second) / lengths, -1.0, 1.0)
        angle = np.degrees(np.arccos(cosine))
        if not minimum <= angle <= maximum:
            return False
    return True


def detect_reference_card(frame, bounds):
    x1, y1, x2, y2 = bounds
    guide_width, guide_height = x2 - x1, y2 - y1
    guide_area = guide_width * guide_height
    pad_x, pad_y = int(guide_width * 0.15), int(guide_height * 0.15)
    frame_height, frame_width = frame.shape[:2]
    roi_x1, roi_y1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
    roi_x2 = min(frame_width, x2 + pad_x)
    roi_y2 = min(frame_height, y2 + pad_y)
    roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
    if roi.size == 0:
        return None

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 90)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    offset = np.array([roi_x1, roi_y1], dtype=np.float32)
    best = None
    best_area = 0.0

    for contour in contours:
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        if hull_area < 0.20 * guide_area:
            continue
        perimeter = cv2.arcLength(hull, True)
        approximate = cv2.approxPolyDP(hull, 0.03 * perimeter, True)
        if len(approximate) != 4:
            continue
        box = order_corners(approximate) + offset
        if not _rectangle_angles_valid(box):
            continue
        area = cv2.contourArea(box)
        if area <= 0 or min(hull_area, area) / max(hull_area, area) < 0.75:
            continue
        margin_x, margin_y = guide_width * 0.05, guide_height * 0.05
        inside = np.all(
            (box[:, 0] >= x1 - margin_x)
            & (box[:, 0] <= x2 + margin_x)
            & (box[:, 1] >= y1 - margin_y)
            & (box[:, 1] <= y2 + margin_y)
        )
        if not inside or area <= best_area:
            continue
        top_left, top_right, bottom_right, bottom_left = box
        width = (
            np.linalg.norm(top_right - top_left)
            + np.linalg.norm(bottom_right - bottom_left)
        ) / 2
        height = (
            np.linalg.norm(bottom_left - top_left)
            + np.linalg.norm(bottom_right - top_right)
        ) / 2
        ratio = max(width, height) / max(min(width, height), 1e-6)
        best_area = area
        best = {
            "box": box,
            "ratio": float(ratio),
            "fill": float(area / guide_area),
            "is_card": abs(ratio - CARD_RATIO) / CARD_RATIO <= 0.05,
        }
    return best


def validate_card(card, bounds):
    box = card["box"]
    x1, y1, x2, y2 = bounds
    guide_width, guide_height = x2 - x1, y2 - y1
    card_center = np.mean(box, axis=0)
    guide_center = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
    offset = card_center - guide_center
    position_valid = (
        abs(offset[0]) <= guide_width * 0.08
        and abs(offset[1]) <= guide_height * 0.08
    )
    if not position_valid:
        if abs(offset[0]) > abs(offset[1]):
            guidance = "Move right" if offset[0] < 0 else "Move left"
        else:
            guidance = "Move down" if offset[1] < 0 else "Move up"
    elif card["fill"] < 0.35:
        guidance = "Move the card closer"
    elif card["fill"] > 0.75:
        guidance = "Move the card farther away"
    else:
        guidance = "Hold the card steady"

    top_left, top_right, bottom_right, bottom_left = box
    top_angle = np.degrees(
        np.arctan2(*(top_right - top_left)[::-1])
    )
    bottom_angle = np.degrees(
        np.arctan2(*(bottom_right - bottom_left)[::-1])
    )
    roll = float((top_angle + bottom_angle) / 2)
    width_top = np.linalg.norm(top_right - top_left)
    width_bottom = np.linalg.norm(bottom_right - bottom_left)
    height_left = np.linalg.norm(bottom_left - top_left)
    height_right = np.linalg.norm(bottom_right - top_right)
    horizontal = float(
        abs(height_left - height_right) / max(height_left, height_right, 1e-6)
    )
    vertical = float(
        abs(width_top - width_bottom) / max(width_top, width_bottom, 1e-6)
    )
    size_valid = 0.35 <= card["fill"] <= 0.75
    alignment_valid = abs(roll) <= 5.0 and horizontal <= 0.10 and vertical <= 0.10
    if position_valid and size_valid and not alignment_valid:
        guidance = "Keep the card level and face it directly toward the camera"
    return {
        "valid": bool(position_valid and size_valid and alignment_valid),
        "guidance": guidance,
        "roll": roll,
        "horizontal_perspective": horizontal,
        "vertical_perspective": vertical,
    }


def create_reference(frame, card, validation):
    box = order_corners(card["box"])
    top_left, top_right, bottom_right, bottom_left = box
    width_px = int(
        max(
            np.linalg.norm(top_right - top_left),
            np.linalg.norm(bottom_right - bottom_left),
        )
    )
    height_px = int(
        max(
            np.linalg.norm(bottom_left - top_left),
            np.linalg.norm(bottom_right - top_right),
        )
    )
    if width_px <= 0 or height_px <= 0:
        return None
    scale_x = width_px / CARD_WIDTH_MM
    scale_y = height_px / CARD_HEIGHT_MM
    scale_average = (scale_x + scale_y) / 2
    if abs(scale_x - scale_y) / max(scale_average, 1e-6) > 0.05:
        return None
    frame_height, frame_width = frame.shape[:2]
    return {
        "status": "VALID",
        "frame_width": int(frame_width),
        "frame_height": int(frame_height),
        "card_width_px": width_px,
        "card_height_px": height_px,
        "scale_x": float(scale_x),
        "scale_y": float(scale_y),
        "scale_avg": float(scale_average),
        "card_roll_deg": validation["roll"],
        "horizontal_perspective": validation["horizontal_perspective"],
        "vertical_perspective": validation["vertical_perspective"],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


class CameraCalibrationTracker:
    """Require several consecutive valid frames before accepting a reference."""

    def __init__(self, stable_frames=10):
        self.stable_frames = stable_frames
        self.stable_count = 0
        self.reference = None

    def reset(self):
        self.stable_count = 0
        self.reference = None

    def process(self, frame):
        bounds = guide_bounds(frame)
        card = detect_reference_card(frame, bounds)
        validation = None
        guidance = "Place a standard ID-size card inside the guide"
        if card is None:
            self.stable_count = 0
        elif not card["is_card"]:
            self.stable_count = 0
            guidance = "Use a standard ID-size card"
        else:
            validation = validate_card(card, bounds)
            guidance = validation["guidance"]
            self.stable_count = self.stable_count + 1 if validation["valid"] else 0
            self.stable_count = min(self.stable_count, self.stable_frames)
            if self.stable_count >= self.stable_frames and self.reference is None:
                self.reference = create_reference(frame, card, validation)
                if self.reference is None:
                    self.stable_count = 0
                    guidance = "Card scale is inconsistent. Face the card directly forward"

        display = frame.copy()
        x1, y1, x2, y2 = bounds
        guide_color = (0, 180, 0) if self.reference else (0, 200, 255)
        cv2.rectangle(display, (x1, y1), (x2, y2), guide_color, 2)
        if card is not None:
            card_color = (0, 200, 0) if validation and validation["valid"] else (0, 140, 255)
            cv2.drawContours(display, [card["box"].astype(np.int32)], -1, card_color, 3)
        self._draw_progress(display)
        return {
            "display_frame": display,
            "guidance": "Camera preparation complete" if self.reference else guidance,
            "stable_count": self.stable_count,
            "stable_frames": self.stable_frames,
            "reference": self.reference.copy() if self.reference else None,
        }

    def _draw_progress(self, frame):
        """Draw a readable stability counter in the camera's top-right corner."""
        progress = f"{self.stable_count}/{self.stable_frames}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.65, frame.shape[1] / 1400)
        thickness = 2
        (text_width, text_height), baseline = cv2.getTextSize(
            progress, font, font_scale, thickness
        )
        padding_x, padding_y = 14, 10
        right, top = frame.shape[1] - 16, 16
        left = right - text_width - (padding_x * 2)
        bottom = top + text_height + baseline + (padding_y * 2)
        color = (22, 163, 74) if self.reference else (30, 41, 59)
        cv2.rectangle(frame, (left, top), (right, bottom), color, -1)
        cv2.putText(
            frame,
            progress,
            (left + padding_x, top + padding_y + text_height),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )
