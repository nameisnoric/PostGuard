"""PostGuard Session Comparison v1.1.

Compare two persisted completed PostGuard Sessions.

Important:
- No Detection is recalculated.
- No Modified RULA is recalculated.
- No Risk Score is recalculated.
- Only persisted Session Summary values are used.
- Risk Score progress is comparable only when both Sessions
  use the same risk_score_method.
- Progress is based on average_risk_score only.
- Alert rate is informational and normalized by active time.
"""

import math

from app.services.session_risk_insight_service import (
    TREND_IMPROVING,
    TREND_STABLE,
    TREND_WORSENING,
    classify_risk_trend,
)


SESSION_COMPARISON_CONTRACT_VERSION = "1.1"

STATUS_AVAILABLE = "AVAILABLE"
STATUS_SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
STATUS_SAME_SESSION = "SAME_SESSION"
STATUS_SCORE_UNAVAILABLE = "SCORE_UNAVAILABLE"
STATUS_METHOD_MISMATCH = "METHOD_MISMATCH"


# ============================================================
# VALIDATION
# ============================================================

def _valid_number(
    value,
) -> float | None:
    if type(value) not in (
        int,
        float,
    ):
        return None

    value = float(
        value
    )

    if not math.isfinite(
        value
    ):
        return None

    return value


def _valid_score(
    value,
) -> float | None:
    value = _valid_number(
        value
    )

    if value is None:
        return None

    if not 0.0 <= value <= 100.0:
        return None

    return value


def _valid_count(
    value,
) -> int | None:
    if (
        type(value) is int
        and
        value >= 0
    ):
        return value

    return None


def _valid_session_id(
    value,
) -> int | None:
    if (
        type(value) is int
        and
        value > 0
    ):
        return value

    return None


def _valid_method(
    value,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    return value or None


# ============================================================
# TIME
# ============================================================

def _active_seconds(
    session,
) -> int | None:
    if not isinstance(
        session,
        dict,
    ):
        return None

    if (
        session.get(
            "status"
        )
        !=
        "COMPLETED"
    ):
        return None

    total = _valid_number(
        session.get(
            "total_duration"
        )
    )

    paused = _valid_number(
        session.get(
            "paused_duration"
        )
    )

    if (
        total is None
        or
        paused is None
        or
        total < 0
        or
        paused < 0
        or
        paused > total
    ):
        return None

    return int(
        total - paused
    )


def _alert_rate_per_minute(
    alert_count,
    active_seconds,
) -> float | None:
    """
    Normalize Alert count by active monitoring time.

    Example:
        3 alerts / 161 seconds
        = 1.118 alerts/minute
    """

    alert_count = _valid_count(
        alert_count
    )

    if (
        alert_count is None
        or
        type(active_seconds) is not int
        or
        active_seconds <= 0
    ):
        return None

    return (
        float(alert_count)
        /
        (
            float(active_seconds)
            /
            60.0
        )
    )


# ============================================================
# INDEXES
# ============================================================

def _session_index(
    sessions,
) -> dict[int, dict]:
    result = {}

    if not isinstance(
        sessions,
        list,
    ):
        return result

    for session in sessions:
        if not isinstance(
            session,
            dict,
        ):
            continue

        session_id = _valid_session_id(
            session.get(
                "session_id"
            )
        )

        if session_id is None:
            continue

        result[
            session_id
        ] = session

    return result


def _summary_index(
    summaries,
) -> dict[int, dict]:
    result = {}

    if not isinstance(
        summaries,
        list,
    ):
        return result

    for summary in summaries:
        if not isinstance(
            summary,
            dict,
        ):
            continue

        session_id = _valid_session_id(
            summary.get(
                "session_id"
            )
        )

        if session_id is None:
            continue

        result[
            session_id
        ] = summary

    return result


# ============================================================
# CANDIDATES
# ============================================================

def build_comparison_candidates(
    sessions,
    summaries,
) -> list[dict]:
    """
    Completed Sessions that have a persisted average Risk Score.

    Order follows /sessions, normally newest first.
    """

    summary_by_session_id = (
        _summary_index(
            summaries
        )
    )

    candidates = []

    if not isinstance(
        sessions,
        list,
    ):
        return candidates

    for session in sessions:
        if not isinstance(
            session,
            dict,
        ):
            continue

        if (
            session.get(
                "status"
            )
            !=
            "COMPLETED"
        ):
            continue

        session_id = _valid_session_id(
            session.get(
                "session_id"
            )
        )

        if session_id is None:
            continue

        summary = (
            summary_by_session_id.get(
                session_id
            )
        )

        if not isinstance(
            summary,
            dict,
        ):
            continue

        average = _valid_score(
            summary.get(
                "average_risk_score"
            )
        )

        if average is None:
            continue

        candidates.append(
            {
                "session_id": session_id,

                "average_risk_score": (
                    average
                ),

                "risk_score_method": (
                    _valid_method(
                        summary.get(
                            "risk_score_method"
                        )
                    )
                ),

                "started_at": (
                    session.get(
                        "started_at"
                    )
                ),
            }
        )

    return candidates


# ============================================================
# METRICS
# ============================================================

def _metric_delta(
    newer,
    older,
):
    """
    B - A when both numbers are available.
    """

    newer = _valid_number(
        newer
    )

    older = _valid_number(
        older
    )

    if (
        newer is None
        or
        older is None
    ):
        return None

    return (
        newer
        -
        older
    )


def _build_session_metrics(
    session,
    summary,
) -> dict:
    active_seconds = (
        _active_seconds(
            session
        )
    )

    alert_count = (
        _valid_count(
            summary.get(
                "total_alert_count"
            )
        )
    )

    return {
        "average_risk_score": (
            _valid_score(
                summary.get(
                    "average_risk_score"
                )
            )
        ),

        "minimum_risk_score": (
            _valid_score(
                summary.get(
                    "minimum_risk_score"
                )
            )
        ),

        "maximum_risk_score": (
            _valid_score(
                summary.get(
                    "maximum_risk_score"
                )
            )
        ),

        "total_alert_count": (
            alert_count
        ),

        "active_seconds": (
            active_seconds
        ),

        "alert_rate_per_minute": (
            _alert_rate_per_minute(
                alert_count,
                active_seconds,
            )
        ),

        "risk_score_method": (
            _valid_method(
                summary.get(
                    "risk_score_method"
                )
            )
        ),
    }


# ============================================================
# HUMAN-FACING TREND
# ============================================================

def comparison_trend_text(
    trend,
) -> str:
    mapping = {
        TREND_IMPROVING: "ดีขึ้น",
        TREND_STABLE: "ใกล้เคียงเดิม",
        TREND_WORSENING: "ควรระวังมากขึ้น",
    }

    return mapping.get(
        trend,
        "ไม่สามารถสรุปได้",
    )


def comparison_explanation(
    trend,
    average_delta,
) -> str:
    if type(average_delta) not in (
        int,
        float,
    ):
        return (
            "ยังไม่มีข้อมูลเพียงพอสำหรับสรุป"
        )

    difference = abs(
        float(
            average_delta
        )
    )

    if trend == TREND_IMPROVING:
        return (
            "คะแนนความเสี่ยงเฉลี่ยลดลง "
            f"{difference:.2f} คะแนน "
            "จึงถือว่าดีขึ้นจากครั้งก่อน"
        )

    if trend == TREND_WORSENING:
        return (
            "คะแนนความเสี่ยงเฉลี่ยเพิ่มขึ้น "
            f"{difference:.2f} คะแนน "
            "จึงควรระวังท่าทางมากขึ้น"
        )

    if trend == TREND_STABLE:
        return (
            "คะแนนเปลี่ยนแปลง "
            f"{difference:.2f} คะแนน "
            "ซึ่งยังไม่มากพอที่จะถือว่า "
            "ดีขึ้นหรือแย่ลงอย่างชัดเจน"
        )

    return (
        "ยังไม่มีข้อมูลเพียงพอสำหรับสรุป"
    )


# ============================================================
# COMPARISON
# ============================================================

def compare_sessions(
    sessions,
    summaries,
    session_a_id: int,
    session_b_id: int,
) -> dict:
    """
    Compare Session A -> Session B.

    Session A:
        previous/reference Session.

    Session B:
        newer/target Session.

    Risk Score delta:
        B - A

    Negative:
        lower measured posture risk.

    Positive:
        higher measured posture risk.

    Progress classification uses average_risk_score only.
    """

    if (
        _valid_session_id(
            session_a_id
        )
        is None
        or
        _valid_session_id(
            session_b_id
        )
        is None
    ):
        return {
            "contract_version": (
                SESSION_COMPARISON_CONTRACT_VERSION
            ),
            "status": (
                STATUS_SESSION_NOT_FOUND
            ),
        }

    if (
        session_a_id
        ==
        session_b_id
    ):
        return {
            "contract_version": (
                SESSION_COMPARISON_CONTRACT_VERSION
            ),
            "status": STATUS_SAME_SESSION,
            "session_a_id": session_a_id,
            "session_b_id": session_b_id,
        }

    session_by_id = (
        _session_index(
            sessions
        )
    )

    summary_by_id = (
        _summary_index(
            summaries
        )
    )

    session_a = (
        session_by_id.get(
            session_a_id
        )
    )

    session_b = (
        session_by_id.get(
            session_b_id
        )
    )

    summary_a = (
        summary_by_id.get(
            session_a_id
        )
    )

    summary_b = (
        summary_by_id.get(
            session_b_id
        )
    )

    if any(
        value is None
        for value
        in (
            session_a,
            session_b,
            summary_a,
            summary_b,
        )
    ):
        return {
            "contract_version": (
                SESSION_COMPARISON_CONTRACT_VERSION
            ),
            "status": (
                STATUS_SESSION_NOT_FOUND
            ),
            "session_a_id": session_a_id,
            "session_b_id": session_b_id,
        }

    metrics_a = (
        _build_session_metrics(
            session_a,
            summary_a,
        )
    )

    metrics_b = (
        _build_session_metrics(
            session_b,
            summary_b,
        )
    )

    average_a = (
        metrics_a[
            "average_risk_score"
        ]
    )

    average_b = (
        metrics_b[
            "average_risk_score"
        ]
    )

    if (
        average_a is None
        or
        average_b is None
    ):
        return {
            "contract_version": (
                SESSION_COMPARISON_CONTRACT_VERSION
            ),
            "status": STATUS_SCORE_UNAVAILABLE,
            "session_a_id": session_a_id,
            "session_b_id": session_b_id,
            "session_a": metrics_a,
            "session_b": metrics_b,
        }

    method_a = (
        metrics_a[
            "risk_score_method"
        ]
    )

    method_b = (
        metrics_b[
            "risk_score_method"
        ]
    )

    if (
        method_a is None
        or
        method_b is None
        or
        method_a != method_b
    ):
        return {
            "contract_version": (
                SESSION_COMPARISON_CONTRACT_VERSION
            ),
            "status": STATUS_METHOD_MISMATCH,
            "session_a_id": session_a_id,
            "session_b_id": session_b_id,
            "session_a": metrics_a,
            "session_b": metrics_b,
        }

    average_delta = (
        average_b
        -
        average_a
    )

    trend = classify_risk_trend(
        average_b,
        average_a,
    )

    deltas = {
        "average_risk_score": (
            average_delta
        ),

        "minimum_risk_score": (
            _metric_delta(
                metrics_b[
                    "minimum_risk_score"
                ],
                metrics_a[
                    "minimum_risk_score"
                ],
            )
        ),

        "maximum_risk_score": (
            _metric_delta(
                metrics_b[
                    "maximum_risk_score"
                ],
                metrics_a[
                    "maximum_risk_score"
                ],
            )
        ),

        "total_alert_count": (
            _metric_delta(
                metrics_b[
                    "total_alert_count"
                ],
                metrics_a[
                    "total_alert_count"
                ],
            )
        ),

        "active_seconds": (
            _metric_delta(
                metrics_b[
                    "active_seconds"
                ],
                metrics_a[
                    "active_seconds"
                ],
            )
        ),

        "alert_rate_per_minute": (
            _metric_delta(
                metrics_b[
                    "alert_rate_per_minute"
                ],
                metrics_a[
                    "alert_rate_per_minute"
                ],
            )
        ),
    }

    return {
        "contract_version": (
            SESSION_COMPARISON_CONTRACT_VERSION
        ),

        "status": STATUS_AVAILABLE,

        "session_a_id": session_a_id,
        "session_b_id": session_b_id,

        "session_a": metrics_a,
        "session_b": metrics_b,

        "risk_score_method": method_a,

        "deltas": deltas,

        "trend": trend,

        "trend_text": (
            comparison_trend_text(
                trend
            )
        ),

        "explanation": (
            comparison_explanation(
                trend,
                average_delta,
            )
        ),
    }