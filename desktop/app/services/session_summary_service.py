"""Save and retrieve persisted PostGuard session summaries."""

import math

from app.services.api_client import APIClient


RISK_SCORE_METHOD = (
    "POSTGUARD_MODIFIED_RULA_FRONT_VIEW_V1"
)


# ============================================================
# BASIC VALIDATION
# ============================================================

def _optional_float(
    value,
) -> float | None:
    if value is None:
        return None

    if type(value) not in (
        int,
        float,
    ):
        raise ValueError(
            "Invalid numeric summary value"
        )

    value = float(value)

    if not math.isfinite(
        value
    ):
        raise ValueError(
            "Summary contains NaN or infinity"
        )

    return value


def _count(
    value,
) -> int:
    if (
        type(value) is not int
        or
        value < 0
    ):
        raise ValueError(
            "Invalid detection count"
        )

    return value


def _risk_score(
    value,
) -> float | None:
    value = _optional_float(
        value
    )

    if value is None:
        return None

    if not (
        0.0
        <=
        value
        <=
        100.0
    ):
        raise ValueError(
            "Risk Score must be between "
            "0 and 100"
        )

    return value


def _modified_rula_score(
    value,
) -> int:
    if (
        type(value) is not int
        or
        not (
            1
            <=
            value
            <=
            7
        )
    ):
        raise ValueError(
            "Modified RULA score must be "
            "an integer from 1 to 7"
        )

    return value


# ============================================================
# RISK SCORE BUCKET
# ============================================================

def _risk_score_bucket(
    bucket,
) -> dict:
    if not isinstance(
        bucket,
        dict,
    ):
        raise ValueError(
            "Invalid Risk Score bucket"
        )

    bucket_index = bucket.get(
        "bucket_index"
    )

    sample_count = bucket.get(
        "sample_count"
    )

    if (
        type(bucket_index)
        is not int
        or
        bucket_index < 0
    ):
        raise ValueError(
            "Invalid Risk Score bucket_index"
        )

    if (
        type(sample_count)
        is not int
        or
        sample_count <= 0
    ):
        raise ValueError(
            "Invalid Risk Score sample_count"
        )

    start_second = _optional_float(
        bucket.get(
            "start_second"
        )
    )

    end_second = _optional_float(
        bucket.get(
            "end_second"
        )
    )

    if (
        start_second is None
        or
        end_second is None
        or
        start_second < 0.0
        or
        end_second <= start_second
    ):
        raise ValueError(
            "Invalid Risk Score bucket time range"
        )

    average = _risk_score(
        bucket.get(
            "average_risk_score"
        )
    )

    minimum = _risk_score(
        bucket.get(
            "minimum_risk_score"
        )
    )

    maximum = _risk_score(
        bucket.get(
            "maximum_risk_score"
        )
    )

    if (
        average is None
        or
        minimum is None
        or
        maximum is None
    ):
        raise ValueError(
            "Risk Score bucket values "
            "cannot be None"
        )

    if not (
        minimum
        <=
        average
        <=
        maximum
    ):
        raise ValueError(
            "Risk Score bucket must satisfy "
            "minimum <= average <= maximum"
        )

    minimum_rula = (
        _modified_rula_score(
            bucket.get(
                "minimum_modified_rula_score"
            )
        )
    )

    maximum_rula = (
        _modified_rula_score(
            bucket.get(
                "maximum_modified_rula_score"
            )
        )
    )

    if (
        minimum_rula
        >
        maximum_rula
    ):
        raise ValueError(
            "Modified RULA bucket must satisfy "
            "minimum <= maximum"
        )

    return {
        "bucket_index": bucket_index,

        "start_second": (
            start_second
        ),

        "end_second": (
            end_second
        ),

        "sample_count": (
            sample_count
        ),

        "average_risk_score": (
            average
        ),

        "minimum_risk_score": (
            minimum
        ),

        "maximum_risk_score": (
            maximum
        ),

        "minimum_modified_rula_score": (
            minimum_rula
        ),

        "maximum_modified_rula_score": (
            maximum_rula
        ),
    }


def _risk_score_buckets(
    value,
) -> list[dict]:
    if value is None:
        return []

    if not isinstance(
        value,
        list,
    ):
        raise ValueError(
            "risk_score_buckets must be a list"
        )

    buckets = [
        _risk_score_bucket(
            bucket
        )
        for bucket
        in value
    ]

    indexes = [
        bucket[
            "bucket_index"
        ]
        for bucket
        in buckets
    ]

    if (
        len(indexes)
        !=
        len(set(indexes))
    ):
        raise ValueError(
            "Duplicate Risk Score bucket_index"
        )

    buckets.sort(
        key=lambda bucket: (
            bucket[
                "bucket_index"
            ]
        )
    )

    return buckets


# ============================================================
# BUILD BACKEND PAYLOAD
# ============================================================

def build_summary_payload(
    summary: dict,
) -> dict:
    """
    Convert the final Desktop Session Summary to the Backend
    persistence contract.

    Only measured values are sent.

    Missing/incomplete posture-score data remains None instead
    of being converted to Risk Score 0.
    """

    if not isinstance(
        summary,
        dict,
    ):
        raise ValueError(
            "Invalid summary"
        )

    average_risk_score = (
        _risk_score(
            summary.get(
                "average_risk_score"
            )
        )
    )

    minimum_risk_score = (
        _risk_score(
            summary.get(
                "minimum_risk_score"
            )
        )
    )

    maximum_risk_score = (
        _risk_score(
            summary.get(
                "maximum_risk_score"
            )
        )
    )

    score_values = (
        average_risk_score,
        minimum_risk_score,
        maximum_risk_score,
    )

    score_count = sum(
        value is not None
        for value
        in score_values
    )

    # Either all three Session score statistics exist,
    # or none of them exist.
    if score_count not in (
        0,
        3,
    ):
        raise ValueError(
            "AVG/MIN/MAX Risk Scores must "
            "be available together"
        )

    if score_count == 3:
        if not (
            minimum_risk_score
            <=
            average_risk_score
            <=
            maximum_risk_score
        ):
            raise ValueError(
                "Session Risk Scores must satisfy "
                "minimum <= average <= maximum"
            )

    buckets = _risk_score_buckets(
        summary.get(
            "risk_score_buckets"
        )
    )

    if (
        buckets
        and
        score_count != 3
    ):
        raise ValueError(
            "Risk Score buckets require "
            "Session AVG/MIN/MAX"
        )

    risk_score_method = None

    if score_count == 3:
        risk_score_method = (
            summary.get(
                "risk_score_method"
            )
            or
            RISK_SCORE_METHOD
        )

        if (
            not isinstance(
                risk_score_method,
                str,
            )
            or
            not risk_score_method.strip()
            or
            len(risk_score_method) > 40
        ):
            raise ValueError(
                "Invalid risk_score_method"
            )

        risk_score_method = (
            risk_score_method.strip()
        )

    payload = {
        # ----------------------------------------------------
        # PostGuard Risk Score
        # ----------------------------------------------------

        "average_risk_score": (
            average_risk_score
        ),

        "minimum_risk_score": (
            minimum_risk_score
        ),

        "maximum_risk_score": (
            maximum_risk_score
        ),

        "risk_score_method": (
            risk_score_method
        ),

        "risk_score_buckets": (
            buckets
        ),

        # ----------------------------------------------------
        # Existing optional feature
        # ----------------------------------------------------

        "blink_rate": (
            _optional_float(
                summary.get(
                    "blink_rate"
                )
            )
        ),

        # ----------------------------------------------------
        # Detection Summary
        # ----------------------------------------------------

        "detection_count": (
            _count(
                summary[
                    "detection_count"
                ]
            )
        ),

        "pose_detected_count": (
            _count(
                summary[
                    "pose_detected_count"
                ]
            )
        ),

        "face_detected_count": (
            _count(
                summary[
                    "face_detected_count"
                ]
            )
        ),

        "average_shoulder": (
            _optional_float(
                summary.get(
                    "average_shoulder"
                )
            )
        ),

        "average_neck": (
            _optional_float(
                summary.get(
                    "average_neck"
                )
            )
        ),
    }

    if (
        max(
            payload[
                "pose_detected_count"
            ],
            payload[
                "face_detected_count"
            ],
        )
        >
        payload[
            "detection_count"
        ]
    ):
        raise ValueError(
            "Detected counts cannot exceed "
            "detection_count"
        )

    return payload


# ============================================================
# BACKEND RESPONSE VALIDATION
# ============================================================

def _validate_saved_summary(
    data,
    session_id: int,
) -> dict:
    if (
        not isinstance(
            data,
            dict,
        )
        or
        data.get(
            "session_id"
        )
        !=
        session_id
    ):
        raise ValueError(
            "Saved summary session_id mismatch "
            "or invalid response"
        )

    return data


# ============================================================
# LOAD
# ============================================================

def load_session_summary(
    session_id: int,
) -> dict | None:
    """
    Read persisted Session Summary.

    None means that no final report has been persisted yet.
    """

    if (
        type(session_id)
        is not int
        or
        session_id <= 0
    ):
        raise ValueError(
            "Invalid session_id"
        )

    response = APIClient.get(
        f"/sessions/{session_id}/summary"
    )

    if response.status_code == 404:
        return None

    if not response.ok:
        raise RuntimeError(
            "Cannot load Session Summary: "
            f"HTTP {response.status_code}"
        )

    return _validate_saved_summary(
        response.json(),
        session_id,
    )


# ============================================================
# SAVE
# ============================================================

def save_session_summary(
    summary: dict,
) -> dict:
    """
    Persist the final PostGuard Session Summary.

    Backend persists:
    - detection summary
    - Risk Score AVG/MIN/MAX
    - Risk Score method
    - 10-second Risk Score buckets

    Existing Risk Event / Alert values are derived backend-side.
    """

    session_id = summary.get(
        "session_id"
    )

    if (
        type(session_id)
        is not int
        or
        session_id <= 0
    ):
        raise ValueError(
            "Invalid session_id"
        )

    if (
        summary.get(
            "database_status"
        )
        !=
        "COMPLETED"
    ):
        raise ValueError(
            "Session must be COMPLETED "
            "before saving"
        )

    payload = build_summary_payload(
        summary
    )

    response = APIClient.post(
        f"/sessions/{session_id}/summary",
        payload,
    )

    if response.status_code == 201:
        data = (
            _validate_saved_summary(
                response.json(),
                session_id,
            )
        )

        return {
            "status": "SAVED",
            "summary": data,
        }

    # --------------------------------------------------------
    # Retry/recovery
    #
    # If the original request succeeded on the server but
    # the client lost the response, a retry may return 409.
    # Read the already-persisted report instead.
    # --------------------------------------------------------

    if response.status_code == 409:
        existing = APIClient.get(
            f"/sessions/{session_id}/summary"
        )

        if existing.ok:
            data = (
                _validate_saved_summary(
                    existing.json(),
                    session_id,
                )
            )

            return {
                "status": (
                    "ALREADY_EXISTS"
                ),
                "summary": data,
            }

    raise RuntimeError(
        "Cannot save Session Summary: "
        f"HTTP {response.status_code} "
        f"{response.text[:300]}"
    )