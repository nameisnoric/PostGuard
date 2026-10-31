"""PostGuard Camera Reference contract.

This module is the authoritative bridge between:

    Camera Setup
        ↓
    Personal Baseline
        ↓
    Monitoring

Camera Setup currently produces a validated Reference Card together with
a locked Camera Roll correction.

Camera Roll may be confirmed by:

    AUTO_CONFIRMED
    USER_CONFIRMED

Both are valid PostGuard Camera Setup outcomes.

The contract also supports upgrading the previous/legacy reference shape:

    {
        "status": "VALID",
        "roll_correction_deg": ...,
        "roll_correction_source": ...,
        ...
    }

into the complete locked Camera Reference required by Baseline and
Monitoring.

Detection frames are NEVER mirrored.

UI previews may mirror the already-corrected frame separately.
"""

from __future__ import annotations

import copy

from datetime import (
    datetime,
    timezone,
)

from typing import Any

import numpy as np

from app.services.camera_setup.roll_correction import (
    ROLL_LIMIT_DEG,
    ROLL_SOURCE_AUTO,
    ROLL_SOURCE_USER,
    ROLL_SOURCES,
    level_frame,
)


# ============================================================
# CONTRACT VERSION
# ============================================================

CAMERA_REFERENCE_CONTRACT_VERSION = (
    "camera-reference-v2"
)

DETECTION_PREPROCESSING_VERSION = (
    "postguard-detection-frame-v2"
)


# ============================================================
# CAMERA REFERENCE STATES
# ============================================================

CARD_VALID = (
    "CARD_VALID"
)

CAMERA_SETUP_CONFIRMED = (
    "CAMERA_SETUP_CONFIRMED"
)

CAMERA_REFERENCE_LOCKED = (
    "CAMERA_REFERENCE_LOCKED"
)

ROLL_CORRECTION_CONFIRMED = (
    "ROLL_CORRECTION_CONFIRMED"
)


# ============================================================
# COMPATIBILITY CONSTANTS
# ============================================================

ROLL_CORRECTION_AUTO_CONFIRMED = (
    ROLL_SOURCE_AUTO
)

ROLL_CORRECTION_USER_CONFIRMED = (
    ROLL_SOURCE_USER
)

ROLL_CORRECTION_SOURCES = (
    ROLL_SOURCES
)


# ============================================================
# ERRORS
# ============================================================

class CameraReferenceError(
    ValueError
):
    """
    Raised when Camera Reference data or its preprocessing
    contract is invalid.
    """


# ============================================================
# BASIC VALIDATION
# ============================================================

def _is_positive_int(
    value: Any,
) -> bool:

    return (
        type(value)
        is int

        and

        value > 0
    )


def _is_finite_number(
    value: Any,
) -> bool:

    return (
        type(value)
        in (
            int,
            float,
        )

        and

        not isinstance(
            value,
            bool,
        )

        and

        np.isfinite(
            float(
                value
            )
        )
    )


def _require_positive_int(
    value: Any,
    field_name: str,
) -> int:

    if not _is_positive_int(
        value
    ):
        raise CameraReferenceError(
            f"Invalid {field_name}: "
            f"{value!r}"
        )

    return int(
        value
    )


def _require_finite_number(
    value: Any,
    field_name: str,
) -> float:

    if not _is_finite_number(
        value
    ):
        raise CameraReferenceError(
            f"Invalid {field_name}: "
            f"{value!r}"
        )

    return float(
        value
    )


# ============================================================
# ROLL VALIDATION
# ============================================================

def _validate_roll_deg(
    value: Any,
) -> float:
    """
    Validate the already-confirmed software Camera Roll
    correction.

    Current Camera Roll implementation supports:

        -ROLL_LIMIT_DEG .. +ROLL_LIMIT_DEG
    """

    correction = (
        _require_finite_number(
            value,
            "roll_correction_deg",
        )
    )

    if not (
        -float(
            ROLL_LIMIT_DEG
        )
        <=
        correction
        <=
        float(
            ROLL_LIMIT_DEG
        )
    ):
        raise CameraReferenceError(
            "Roll correction must be between "
            f"{-float(ROLL_LIMIT_DEG):+.1f}° "
            "and "
            f"{float(ROLL_LIMIT_DEG):+.1f}°."
        )

    return correction


def _validate_roll_source(
    value: Any,
) -> str:

    if value not in ROLL_CORRECTION_SOURCES:

        raise CameraReferenceError(
            "Unexpected Roll correction source: "
            f"{value!r}. "
            "Expected AUTO_CONFIRMED or "
            "USER_CONFIRMED."
        )

    return str(
        value
    )


# ============================================================
# LOCK CAMERA REFERENCE
# ============================================================

def lock_camera_reference(
    camera: dict[str, Any],
    card_reference: dict[str, Any],
    *,
    roll_correction_deg: float | None = None,
    roll_correction_source: str | None = None,
) -> dict[str, Any]:
    """
    Convert Camera Setup output into the canonical locked
    Camera Reference used by Personal Baseline and Monitoring.

    Both:

        AUTO_CONFIRMED
        USER_CONFIRMED

    are accepted.

    The Roll correction must already have been confirmed by
    Camera Setup before this function is called.
    """

    # ========================================================
    # CAMERA
    # ========================================================

    if not isinstance(
        camera,
        dict,
    ):
        raise CameraReferenceError(
            "Camera data must be a dictionary."
        )

    # ========================================================
    # CARD REFERENCE
    # ========================================================

    if not isinstance(
        card_reference,
        dict,
    ):
        raise CameraReferenceError(
            "Card Reference must be a dictionary."
        )

    card_is_valid = (
        card_reference.get(
            "status"
        )
        ==
        "VALID"

        or

        card_reference.get(
            "card_reference_status"
        )
        ==
        CARD_VALID
    )

    if not card_is_valid:

        raise CameraReferenceError(
            "Card Reference has not passed "
            "Camera Setup validation."
        )

    # ========================================================
    # ROLL SOURCE
    # ========================================================

    if roll_correction_source is None:

        roll_correction_source = (
            card_reference.get(
                "roll_correction_source"
            )
        )

    source = (
        _validate_roll_source(
            roll_correction_source
        )
    )

    # ========================================================
    # ROLL CORRECTION
    # ========================================================

    if roll_correction_deg is None:

        roll_correction_deg = (
            card_reference.get(
                "roll_correction_deg"
            )
        )

    correction = (
        _validate_roll_deg(
            roll_correction_deg
        )
    )

    # ========================================================
    # CAMERA IDENTITY
    # ========================================================

    camera_id = (
        _require_positive_int(
            camera.get(
                "camera_id"
            ),
            "camera_id",
        )
    )

    device_index = (
        camera.get(
            "device_index"
        )
    )

    if (
        type(
            device_index
        )
        is not int

        or

        device_index < 0
    ):
        raise CameraReferenceError(
            "Invalid device_index: "
            f"{device_index!r}"
        )

    # ========================================================
    # SELECTED CAMERA RESOLUTION
    # ========================================================

    selected_width = (
        _require_positive_int(
            camera.get(
                "resolution_width"
            ),
            "resolution_width",
        )
    )

    selected_height = (
        _require_positive_int(
            camera.get(
                "resolution_height"
            ),
            "resolution_height",
        )
    )

    # ========================================================
    # REFERENCE RESOLUTION
    # ========================================================

    reference_width = (
        _require_positive_int(
            card_reference.get(
                "frame_width"
            ),
            "reference.frame_width",
        )
    )

    reference_height = (
        _require_positive_int(
            card_reference.get(
                "frame_height"
            ),
            "reference.frame_height",
        )
    )

    if (
        selected_width
        !=
        reference_width

        or

        selected_height
        !=
        reference_height
    ):
        raise CameraReferenceError(
            "Camera Reference resolution does not "
            "match the selected camera resolution. "
            f"selected="
            f"{selected_width}x{selected_height}, "
            f"reference="
            f"{reference_width}x{reference_height}"
        )

    # ========================================================
    # REFERENCE CARD VALUES
    # ========================================================

    scale_x = (
        _require_finite_number(
            card_reference.get(
                "scale_x"
            ),
            "reference.scale_x",
        )
    )

    scale_y = (
        _require_finite_number(
            card_reference.get(
                "scale_y"
            ),
            "reference.scale_y",
        )
    )

    scale_avg = (
        _require_finite_number(
            card_reference.get(
                "scale_avg"
            ),
            "reference.scale_avg",
        )
    )

    card_roll = (
        _require_finite_number(
            card_reference.get(
                "card_roll_deg"
            ),
            "reference.card_roll_deg",
        )
    )

    horizontal_perspective = (
        _require_finite_number(
            card_reference.get(
                "horizontal_perspective"
            ),
            "reference.horizontal_perspective",
        )
    )

    vertical_perspective = (
        _require_finite_number(
            card_reference.get(
                "vertical_perspective"
            ),
            "reference.vertical_perspective",
        )
    )

    # ========================================================
    # BUILD LOCKED REFERENCE
    # ========================================================

    locked = (
        copy.deepcopy(
            card_reference
        )
    )

    # --------------------------------------------------------
    # Legacy compatibility
    # --------------------------------------------------------

    locked[
        "status"
    ] = (
        "VALID"
    )

    # --------------------------------------------------------
    # Contract states
    # --------------------------------------------------------

    locked[
        "card_reference_status"
    ] = (
        CARD_VALID
    )

    locked[
        "camera_setup_status"
    ] = (
        CAMERA_SETUP_CONFIRMED
    )

    locked[
        "camera_reference_status"
    ] = (
        CAMERA_REFERENCE_LOCKED
    )

    locked[
        "roll_correction_status"
    ] = (
        ROLL_CORRECTION_CONFIRMED
    )

    locked[
        "roll_correction_source"
    ] = (
        source
    )

    locked[
        "roll_correction_deg"
    ] = (
        correction
    )

    # --------------------------------------------------------
    # Locked camera identity
    # --------------------------------------------------------

    locked[
        "locked_camera_id"
    ] = (
        camera_id
    )

    locked[
        "locked_device_index"
    ] = (
        int(
            device_index
        )
    )

    locked[
        "locked_device_id"
    ] = (
        camera.get(
            "device_id"
        )
    )

    # --------------------------------------------------------
    # Locked resolution
    # --------------------------------------------------------

    locked[
        "locked_frame_width"
    ] = (
        reference_width
    )

    locked[
        "locked_frame_height"
    ] = (
        reference_height
    )

    # --------------------------------------------------------
    # Reference Card values
    # --------------------------------------------------------

    locked[
        "scale_x"
    ] = (
        scale_x
    )

    locked[
        "scale_y"
    ] = (
        scale_y
    )

    locked[
        "scale_avg"
    ] = (
        scale_avg
    )

    locked[
        "card_roll_deg"
    ] = (
        card_roll
    )

    locked[
        "horizontal_perspective"
    ] = (
        horizontal_perspective
    )

    locked[
        "vertical_perspective"
    ] = (
        vertical_perspective
    )

    # ========================================================
    # PREPROCESSING CONTRACT
    # ========================================================

    locked[
        "preprocessing_contract"
    ] = {
        "version":
            DETECTION_PREPROCESSING_VERSION,

        # Detector data remains physically oriented.
        "detection_mirror":
            False,

        "software_roll_correction":
            abs(
                correction
            )
            >
            1e-9,

        "roll_correction_deg":
            correction,

        # Same border-removal behavior used by Camera Setup.
        "remove_black_border":
            True,
    }

    # ========================================================
    # VERSION / TIME
    # ========================================================

    locked[
        "contract_version"
    ] = (
        CAMERA_REFERENCE_CONTRACT_VERSION
    )

    locked[
        "locked_at"
    ] = (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )

    return locked


# ============================================================
# LEGACY -> LOCKED UPGRADE
# ============================================================

def _upgrade_legacy_camera_reference(
    camera: dict[str, Any],
) -> dict[str, Any]:
    """
    Upgrade the Camera Reference produced by the current
    Camera Setup page when it still uses the compact legacy
    representation.

    This provides compatibility while the application migrates
    fully to the canonical Camera Reference contract.
    """

    reference = (
        camera.get(
            "camera_calibration"
        )
    )

    if not isinstance(
        reference,
        dict,
    ):
        raise CameraReferenceError(
            "Locked Camera Reference is missing."
        )

    # Already canonical.
    if (
        reference.get(
            "card_reference_status"
        )
        ==
        CARD_VALID

        and

        reference.get(
            "camera_setup_status"
        )
        ==
        CAMERA_SETUP_CONFIRMED

        and

        reference.get(
            "camera_reference_status"
        )
        ==
        CAMERA_REFERENCE_LOCKED
    ):
        return (
            copy.deepcopy(
                reference
            )
        )

    # Legacy Camera Setup reference.
    if (
        reference.get(
            "status"
        )
        !=
        "VALID"
    ):
        raise CameraReferenceError(
            "Card Reference is not valid."
        )

    source = (
        reference.get(
            "roll_correction_source"
        )
    )

    correction = (
        reference.get(
            "roll_correction_deg"
        )
    )

    locked = (
        lock_camera_reference(
            camera,
            reference,
            roll_correction_deg=(
                correction
            ),
            roll_correction_source=(
                source
            ),
        )
    )

    # Keep the upgraded contract in the current camera object.
    #
    # This ensures the same reference is then used by
    # Personal Baseline and Monitoring.
    camera[
        "camera_calibration"
    ] = (
        copy.deepcopy(
            locked
        )
    )

    return locked


# ============================================================
# VALIDATE LOCKED CAMERA REFERENCE
# ============================================================

def validate_locked_camera_reference(
    camera: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate Camera Reference before Personal Baseline or
    Monitoring.

    Legacy references are automatically upgraded once.
    """

    if not isinstance(
        camera,
        dict,
    ):
        raise CameraReferenceError(
            "Camera data must be a dictionary."
        )

    reference = (
        _upgrade_legacy_camera_reference(
            camera
        )
    )

    # ========================================================
    # CARD
    # ========================================================

    if (
        reference.get(
            "card_reference_status"
        )
        !=
        CARD_VALID
    ):
        raise CameraReferenceError(
            "Card Reference is not valid."
        )

    # ========================================================
    # CAMERA SETUP
    # ========================================================

    if (
        reference.get(
            "camera_setup_status"
        )
        !=
        CAMERA_SETUP_CONFIRMED
    ):
        raise CameraReferenceError(
            "Camera Setup has not been confirmed."
        )

    # ========================================================
    # REFERENCE LOCK
    # ========================================================

    if (
        reference.get(
            "camera_reference_status"
        )
        !=
        CAMERA_REFERENCE_LOCKED
    ):
        raise CameraReferenceError(
            "Camera Reference is not locked."
        )

    # ========================================================
    # VERSION
    # ========================================================

    if (
        reference.get(
            "contract_version"
        )
        !=
        CAMERA_REFERENCE_CONTRACT_VERSION
    ):
        raise CameraReferenceError(
            "Unsupported Camera Reference "
            "contract version."
        )

    # ========================================================
    # CAMERA ID
    # ========================================================

    camera_id = (
        _require_positive_int(
            camera.get(
                "camera_id"
            ),
            "camera_id",
        )
    )

    locked_camera_id = (
        _require_positive_int(
            reference.get(
                "locked_camera_id"
            ),
            "reference.locked_camera_id",
        )
    )

    if (
        camera_id
        !=
        locked_camera_id
    ):
        raise CameraReferenceError(
            "Camera Reference belongs "
            "to another camera."
        )

    # ========================================================
    # DEVICE INDEX
    # ========================================================

    device_index = (
        camera.get(
            "device_index"
        )
    )

    if (
        type(
            device_index
        )
        is not int

        or

        device_index < 0
    ):
        raise CameraReferenceError(
            "Invalid camera device index."
        )

    locked_device_index = (
        reference.get(
            "locked_device_index"
        )
    )

    if (
        type(
            locked_device_index
        )
        is not int

        or

        locked_device_index
        !=
        device_index
    ):
        raise CameraReferenceError(
            "Camera device changed after "
            "Camera Reference was locked."
        )

    # ========================================================
    # RESOLUTION
    # ========================================================

    selected_width = (
        _require_positive_int(
            camera.get(
                "resolution_width"
            ),
            "resolution_width",
        )
    )

    selected_height = (
        _require_positive_int(
            camera.get(
                "resolution_height"
            ),
            "resolution_height",
        )
    )

    locked_width = (
        _require_positive_int(
            reference.get(
                "locked_frame_width"
            ),
            "reference.locked_frame_width",
        )
    )

    locked_height = (
        _require_positive_int(
            reference.get(
                "locked_frame_height"
            ),
            "reference.locked_frame_height",
        )
    )

    if (
        selected_width
        !=
        locked_width

        or

        selected_height
        !=
        locked_height
    ):
        raise CameraReferenceError(
            "Camera resolution changed after "
            "Camera Reference was locked."
        )

    # ========================================================
    # ROLL STATUS
    # ========================================================

    if (
        reference.get(
            "roll_correction_status"
        )
        !=
        ROLL_CORRECTION_CONFIRMED
    ):
        raise CameraReferenceError(
            "Roll correction has not been confirmed."
        )

    source = (
        _validate_roll_source(
            reference.get(
                "roll_correction_source"
            )
        )
    )

    correction = (
        _validate_roll_deg(
            reference.get(
                "roll_correction_deg"
            )
        )
    )

    # Silence static-analysis / document the validation result.
    _ = source

    # ========================================================
    # PREPROCESSING CONTRACT
    # ========================================================

    preprocessing = (
        reference.get(
            "preprocessing_contract"
        )
    )

    if not isinstance(
        preprocessing,
        dict,
    ):
        raise CameraReferenceError(
            "Camera preprocessing contract is missing."
        )

    if (
        preprocessing.get(
            "version"
        )
        !=
        DETECTION_PREPROCESSING_VERSION
    ):
        raise CameraReferenceError(
            "Unsupported detection preprocessing "
            "version."
        )

    # Detection must remain unmirrored.
    if (
        preprocessing.get(
            "detection_mirror"
        )
        is not False
    ):
        raise CameraReferenceError(
            "Detection mirror contract is invalid."
        )

    preprocessing_correction = (
        _validate_roll_deg(
            preprocessing.get(
                "roll_correction_deg"
            )
        )
    )

    if (
        abs(
            preprocessing_correction
            -
            correction
        )
        >
        1e-9
    ):
        raise CameraReferenceError(
            "Roll correction differs between "
            "Camera Reference and preprocessing "
            "contract."
        )

    expected_enabled = (
        abs(
            correction
        )
        >
        1e-9
    )

    if (
        preprocessing.get(
            "software_roll_correction"
        )
        is not
        expected_enabled
    ):
        raise CameraReferenceError(
            "Software Roll correction state does not "
            "match the confirmed correction angle."
        )

    if (
        preprocessing.get(
            "remove_black_border"
        )
        is not True
    ):
        raise CameraReferenceError(
            "Unsupported Roll correction border policy."
        )

    return (
        copy.deepcopy(
            reference
        )
    )


# ============================================================
# SHARED DETECTION PREPROCESSING
# ============================================================

def prepare_detection_frame(
    frame: np.ndarray,
    camera: dict[str, Any],
) -> np.ndarray:
    """
    Shared preprocessing used by Personal Baseline and Monitoring.

    Contract:

        raw frame
            ↓
        locked Camera Roll correction
            ↓
        borderless corrected frame
            ↓
        Detection

    Detection frame is NOT mirrored.

    Mirroring is presentation/UI only.
    """

    if not isinstance(
        frame,
        np.ndarray,
    ):
        raise CameraReferenceError(
            "Camera frame must be a numpy array."
        )

    if (
        frame.ndim
        <
        2
    ):
        raise CameraReferenceError(
            "Camera frame has invalid dimensions."
        )

    reference = (
        validate_locked_camera_reference(
            camera
        )
    )

    actual_height = int(
        frame.shape[
            0
        ]
    )

    actual_width = int(
        frame.shape[
            1
        ]
    )

    expected_width = int(
        reference[
            "locked_frame_width"
        ]
    )

    expected_height = int(
        reference[
            "locked_frame_height"
        ]
    )

    if (
        actual_width
        !=
        expected_width

        or

        actual_height
        !=
        expected_height
    ):
        raise CameraReferenceError(
            "Actual camera frame does not match "
            "the locked Camera Reference. "
            f"actual="
            f"{actual_width}x{actual_height}, "
            f"expected="
            f"{expected_width}x{expected_height}"
        )

    correction = float(
        reference[
            "roll_correction_deg"
        ]
    )

    if (
        abs(
            correction
        )
        <=
        1e-9
    ):
        return frame

    return (
        level_frame(
            frame,
            correction,
            remove_black_border=True,
        )
    )