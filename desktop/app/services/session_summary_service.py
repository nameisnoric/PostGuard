
"""Save and retrieve persisted PostGuard session summaries."""

import math

from app.services.api_client import APIClient


def _optional_float(value):
    if value is None:
        return None

    if type(value) not in (int, float):
        raise ValueError("Invalid numeric summary value")

    value = float(value)

    if not math.isfinite(value):
        raise ValueError("Summary contains NaN or infinity")

    return value


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Invalid detection count")
    return value


def build_summary_payload(summary: dict) -> dict:
    """Persist measured prototype risk, detection, and eye metrics."""

    if not isinstance(summary, dict):
        raise ValueError("Invalid summary")

    payload = {
        "average_risk_score": _optional_float(summary.get("average_risk_score")),
        "maximum_risk_score": _optional_float(summary.get("maximum_risk_score")),
        "risk_score_method": summary.get("risk_score_method"),
        "blink_rate": _optional_float(summary.get("blink_rate")),

        "detection_count": _count(
            summary["detection_count"]
        ),
        "pose_detected_count": _count(
            summary["pose_detected_count"]
        ),
        "face_detected_count": _count(
            summary["face_detected_count"]
        ),
        "average_shoulder": _optional_float(
            summary.get("average_shoulder")
        ),
        "average_neck": _optional_float(
            summary.get("average_neck")
        ),
    }

    average_risk = payload["average_risk_score"]
    maximum_risk = payload["maximum_risk_score"]
    blink_rate = payload["blink_rate"]
    risk_method = payload["risk_score_method"]
    if average_risk is not None and not 1 <= average_risk <= 7:
        raise ValueError("average_risk_score must be between 1 and 7")
    if maximum_risk is not None and not 1 <= maximum_risk <= 7:
        raise ValueError("maximum_risk_score must be between 1 and 7")
    if (
        average_risk is not None
        and maximum_risk is not None
        and maximum_risk < average_risk
    ):
        raise ValueError("maximum_risk_score cannot be below average_risk_score")
    if blink_rate is not None and blink_rate < 0:
        raise ValueError("blink_rate cannot be negative")
    has_scores = average_risk is not None or maximum_risk is not None
    if has_scores and risk_method != "RULA_ADAPTED_FRONT_V1":
        raise ValueError("RULA-adapted scores require risk_score_method")
    if not has_scores and risk_method is not None:
        raise ValueError("risk_score_method requires risk scores")

    if (
        max(payload["pose_detected_count"], payload["face_detected_count"])
        > payload["detection_count"]
    ):
        raise ValueError("Detected counts cannot exceed detection_count")
    return payload


def _validate_saved_summary(data, session_id: int) -> dict:
    if not isinstance(data, dict) or data.get("session_id") != session_id:
        raise ValueError("Saved summary session_id mismatch or invalid response")
    return data


def load_session_summary(session_id: int) -> dict | None:
    """Read persisted values; None means that no report has been saved yet."""
    if type(session_id) is not int or session_id <= 0:
        raise ValueError("Invalid session_id")

    response = APIClient.get(f"/sessions/{session_id}/summary")
    if response.status_code == 404:
        return None
    if not response.ok:
        raise RuntimeError(f"Cannot load Session Summary: HTTP {response.status_code}")
    return _validate_saved_summary(response.json(), session_id)


def save_session_summary(summary: dict) -> dict:
    """
    POST the summary to Backend.
    Return an explicit result for saved or already-existing data.
    """

    session_id = summary.get("session_id")

    if type(session_id) is not int or session_id <= 0:
        raise ValueError("Invalid session_id")

    if summary.get("database_status") != "COMPLETED":
        raise ValueError(
            "Session must be COMPLETED before saving"
        )

    payload = build_summary_payload(summary)

    response = APIClient.post(
        f"/sessions/{session_id}/summary",
        payload,
    )

    if response.status_code == 201:
        data = _validate_saved_summary(response.json(), session_id)

        return {
            "status": "SAVED",
            "summary": data,
        }

    if response.status_code == 409:
        existing = APIClient.get(
            f"/sessions/{session_id}/summary"
        )

        if existing.ok:
            data = _validate_saved_summary(existing.json(), session_id)

            # Do not claim the existing values equal our payload.
            return {
                "status": "ALREADY_EXISTS",
                "summary": data,
            }

    raise RuntimeError(
        f"Cannot save Session Summary: "
        f"HTTP {response.status_code} "
        f"{response.text[:300]}"
    )
