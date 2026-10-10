
"""PostGuard Assessment Rule Engine - Step 8.6.1"""

from math import isfinite


def _number(value, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value, (int, float)
    ):
        raise ValueError(
            f"{field_name} must be a finite number."
        )

    if not isfinite(value):
        raise ValueError(
            f"{field_name} must be a finite number."
        )

    return float(value)


def neck_score(
    flexion_degrees: float | None = None,
    extension: bool | None = None,
) -> int | None:
    """Neck: flexion 1-3 points, extension 4 points."""

    if extension is not None and not isinstance(
        extension, bool
    ):
        raise ValueError(
            "extension must be True, False, or None."
        )

    if extension is True:
        if flexion_degrees is not None:
            raise ValueError(
                "Do not supply flexion_degrees for extension."
            )
        return 4

    if flexion_degrees is None:
        return None

    angle = _number(
        flexion_degrees, "flexion_degrees"
    )

    if angle < 0:
        raise ValueError(
            "flexion_degrees must be >= 0; "
            "classify extension separately."
        )

    if angle <= 10:
        return 1

    if angle <= 20:
        return 2

    return 3


def binary_score(
    value: bool | None,
    name: str,
) -> int | None:
    """False = 0, True = 1, None = unavailable."""

    if value is None:
        return None

    if not isinstance(value, bool):
        raise ValueError(
            f"{name} must be True, False, or None."
        )

    return int(value)


def trunk_score(level: int | None) -> int | None:
    """Trunk: 1=slight, 2=moderate, 3=large."""

    if level is None:
        return None

    if type(level) is not int or level not in (1, 2, 3):
        raise ValueError(
            "trunk_level must be 1, 2, 3, or None."
        )

    return level


def duration_score(
    seconds: float | None,
) -> int | None:
    """Continuous held posture >= 60 seconds = 1."""

    if seconds is None:
        return None

    duration = _number(
        seconds, "sustained_seconds"
    )

    if duration < 0:
        raise ValueError(
            "sustained_seconds cannot be negative."
        )

    return 1 if duration >= 60 else 0


def risk_level(score: int) -> str:
    """PostGuard custom risk bands, 7+ is highest."""

    if type(score) is not int or not 1 <= score <= 10:
        raise ValueError(
            "score must be an integer between 1 and 10."
        )

    if score <= 2:
        return "ACCEPTABLE"

    if score <= 4:
        return "IMPROVEMENT_MAY_BE_NEEDED"

    if score <= 6:
        return "IMPROVE_SOON"

    return "ACTION_REQUIRED"


def assess_posture(
    *,
    neck_flexion_degrees: float | None = None,
    neck_extension: bool | None = None,
    neck_side_bending: bool | None = None,
    neck_rotation: bool | None = None,
    trunk_level: int | None = None,
    sustained_seconds: float | None = None,
) -> dict:
    """Calculate a complete score only if all factors exist."""

    factors = {
        "neck": neck_score(
            neck_flexion_degrees,
            neck_extension,
        ),
        "neck_side_bending": binary_score(
            neck_side_bending,
            "neck_side_bending",
        ),
        "neck_rotation": binary_score(
            neck_rotation,
            "neck_rotation",
        ),
        "trunk": trunk_score(
            trunk_level
        ),
        "muscle_use_duration": duration_score(
            sustained_seconds
        ),
    }

    missing = [
        name
        for name, value in factors.items()
        if value is None
    ]

    if missing:
        return {
            "status": "PARTIAL",
            "factors": factors,
            "missing_factors": missing,
            "raw_score": None,
            "risk_level": None,
        }

    total = sum(factors.values())

    return {
        "status": "COMPLETE",
        "factors": factors,
        "missing_factors": [],
        "raw_score": total,
        "risk_level": risk_level(total),
    }
