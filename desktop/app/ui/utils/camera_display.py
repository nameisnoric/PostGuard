"""User-facing camera labels that hide internal device and database IDs."""

from __future__ import annotations

import re


def camera_display_number(camera: dict) -> int | None:
    """Return the 1-based camera number assigned by the camera setup UI."""
    if not isinstance(camera, dict):
        return None

    display_number = camera.get("display_number")
    if type(display_number) is int and display_number > 0:
        return display_number

    device_index = camera.get("device_index")
    if type(device_index) is int and device_index >= 0:
        return device_index + 1

    camera_name = str(camera.get("camera_name") or "")
    match = re.fullmatch(r"Camera\s+(\d+)", camera_name, flags=re.IGNORECASE)
    if match:
        return int(match.group(1)) + 1

    return None


def camera_display_name(camera: dict) -> str:
    """Describe a camera in terms users understand, without exposing IDs."""
    number = camera_display_number(camera)
    if number is not None:
        return f"กล้องตัวที่ {number}"

    name = str(camera.get("camera_name") or "").strip()
    return name or "กล้องที่เลือก"

