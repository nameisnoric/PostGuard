"""Load persisted PostGuard Session Risk Score analytics."""

import math

from app.services.api_client import APIClient


# ============================================================
# BASIC VALIDATION
# ============================================================

def _session_id(
    value,
) -> int:
    if (
        type(value) is not int
        or
        value <= 0
    ):
        raise ValueError(
            "Invalid session_id"
        )

    return value


def _finite_float(
    value,
    *,
    name: str,
) -> float:
    if type(value) not in (
        int,
        float,
    ):
        raise ValueError(
            f"Invalid {name}"
        )

    value = float(value)

    if not math.isfinite(
        value
    ):
        raise ValueError(
            f"{name} must be finite"
        )

    return value


def _risk_score(
    value,
    *,
    name: str,
) -> float:
    value = _finite_float(
        value,
        name=name,
    )

    if not (
        0.0
        <=
        value
        <=
        100.0
    ):
        raise ValueError(
            f"{name} must be between 0 and 100"
        )

    return value


def _rula_score(
    value,
    *,
    name: str,
) -> int:
    if (
        type(value) is not int
        or
        value < 1
        or
        value > 7
    ):
        raise ValueError(
            f"{name} must be 1-7"
        )

    return value


# ============================================================
# BUCKET VALIDATION
# ============================================================

def _validate_bucket(
    bucket,
) -> dict:
    if not isinstance(
        bucket,
        dict,
    ):
        raise ValueError(
            "Invalid Risk Score bucket"
        )

    bucket_id = bucket.get(
        "bucket_id"
    )

    session_id = bucket.get(
        "session_id"
    )

    bucket_index = bucket.get(
        "bucket_index"
    )

    sample_count = bucket.get(
        "sample_count"
    )

    if (
        type(bucket_id) is not int
        or
        bucket_id <= 0
    ):
        raise ValueError(
            "Invalid bucket_id"
        )

    _session_id(
        session_id
    )

    if (
        type(bucket_index) is not int
        or
        bucket_index < 0
    ):
        raise ValueError(
            "Invalid bucket_index"
        )

    if (
        type(sample_count) is not int
        or
        sample_count <= 0
    ):
        raise ValueError(
            "Invalid sample_count"
        )

    start_second = _finite_float(
        bucket.get(
            "start_second"
        ),
        name="start_second",
    )

    end_second = _finite_float(
        bucket.get(
            "end_second"
        ),
        name="end_second",
    )

    if (
        start_second < 0.0
        or
        end_second <= start_second
    ):
        raise ValueError(
            "Invalid bucket time range"
        )

    average = _risk_score(
        bucket.get(
            "average_risk_score"
        ),
        name="average_risk_score",
    )

    minimum = _risk_score(
        bucket.get(
            "minimum_risk_score"
        ),
        name="minimum_risk_score",
    )

    maximum = _risk_score(
        bucket.get(
            "maximum_risk_score"
        ),
        name="maximum_risk_score",
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

    minimum_rula = _rula_score(
        bucket.get(
            "minimum_modified_rula_score"
        ),
        name=(
            "minimum_modified_rula_score"
        ),
    )

    maximum_rula = _rula_score(
        bucket.get(
            "maximum_modified_rula_score"
        ),
        name=(
            "maximum_modified_rula_score"
        ),
    )

    if minimum_rula > maximum_rula:
        raise ValueError(
            "Modified RULA bucket must satisfy "
            "minimum <= maximum"
        )

    return {
        "bucket_id": (
            bucket_id
        ),

        "session_id": (
            session_id
        ),

        "bucket_index": (
            bucket_index
        ),

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


# ============================================================
# LOAD BUCKETS
# ============================================================

def load_session_risk_score_buckets(
    session_id: int,
) -> list[dict]:
    """
    Load graph-ready 10-second buckets from Backend.

    The returned buckets are sorted by bucket_index.

    No score is fabricated if Backend returns an empty list.
    """

    session_id = _session_id(
        session_id
    )

    response = APIClient.get(
        (
            f"/sessions/{session_id}"
            "/risk-score-buckets"
        )
    )

    if not response.ok:
        raise RuntimeError(
            "Cannot load Risk Score buckets: "
            f"HTTP {response.status_code}"
        )

    data = response.json()

    if not isinstance(
        data,
        list,
    ):
        raise ValueError(
            "Invalid Risk Score bucket response"
        )

    buckets = [
        _validate_bucket(
            item
        )
        for item
        in data
    ]

    for bucket in buckets:
        if (
            bucket["session_id"]
            !=
            session_id
        ):
            raise ValueError(
                "Risk Score bucket session_id mismatch"
            )

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
        key=lambda item: (
            item[
                "bucket_index"
            ]
        )
    )

    return buckets