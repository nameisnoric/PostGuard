"""PostGuard Session Risk Insight v1.1.

This module derives user-facing Session Risk insights from
persisted Session Summary data.

Important:
- It does NOT recalculate posture detection.
- It does NOT recalculate Modified RULA.
- It does NOT change the persisted PostGuard Risk Score.
- Risk comparisons use only Sessions produced by the same
  risk_score_method.
"""

import math


SESSION_RISK_INSIGHT_CONTRACT_VERSION = "1.1"

TREND_DEADBAND_POINTS = 5.0

TREND_IMPROVING = "IMPROVING"
TREND_STABLE = "STABLE"
TREND_WORSENING = "WORSENING"
TREND_NO_COMPARISON = "NO_COMPARISON"
TREND_NO_DATA = "NO_DATA"


def _valid_score(value) -> float | None:
    """Return a finite PostGuard Risk Score between 0 and 100."""

    if type(value) not in (
        int,
        float,
    ):
        return None

    value = float(value)

    if not math.isfinite(value):
        return None

    if not 0.0 <= value <= 100.0:
        return None

    return value


def _valid_session_id(value) -> int | None:
    if (
        type(value) is int
        and
        value > 0
    ):
        return value

    return None


def _valid_method(value) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    return value


def _summary_index(
    summaries,
) -> dict[int, dict]:
    if not isinstance(
        summaries,
        list,
    ):
        return {}

    result = {}

    for summary in summaries:
        if not isinstance(
            summary,
            dict,
        ):
            continue

        session_id = (
            _valid_session_id(
                summary.get(
                    "session_id"
                )
            )
        )

        if session_id is None:
            continue

        result[
            session_id
        ] = summary

    return result


def _ordered_scored_reports(
    sessions,
    summaries,
) -> list[dict]:
    """
    Return completed scored Sessions in /sessions order.

    PostGuard currently receives Sessions newest first.
    """

    if not isinstance(
        sessions,
        list,
    ):
        return []

    summary_by_session_id = (
        _summary_index(
            summaries
        )
    )

    reports = []

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

        session_id = (
            _valid_session_id(
                session.get(
                    "session_id"
                )
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

        score = _valid_score(
            summary.get(
                "average_risk_score"
            )
        )

        if score is None:
            continue

        reports.append(
            {
                "session_id": session_id,
                "score": score,
                "method": _valid_method(
                    summary.get(
                        "risk_score_method"
                    )
                ),
                "summary": summary,
                "session": session,
            }
        )

    return reports


def classify_risk_trend(
    current_score: float,
    previous_score: float,
) -> str:
    """
    Compare two PostGuard Risk Scores.

    Lower score = lower measured posture risk.

    delta <= -5:
        IMPROVING

    -5 < delta < +5:
        STABLE

    delta >= +5:
        WORSENING

    ±5 is an engineering display deadband,
    not a medical threshold.
    """

    current = _valid_score(
        current_score
    )

    previous = _valid_score(
        previous_score
    )

    if (
        current is None
        or
        previous is None
    ):
        raise ValueError(
            "Risk Trend requires valid scores between 0 and 100"
        )

    delta = (
        current
        -
        previous
    )

    if (
        delta
        <=
        -TREND_DEADBAND_POINTS
    ):
        return TREND_IMPROVING

    if (
        delta
        >=
        TREND_DEADBAND_POINTS
    ):
        return TREND_WORSENING

    return TREND_STABLE


def build_session_risk_insight(
    sessions,
    summaries,
) -> dict:
    """
    Build the latest Session insight.

    Overall Session Risk Score:
        persisted average_risk_score.

    Risk Trend:
        latest scored completed Session
        vs nearest previous scored completed Session
        using the SAME risk_score_method.
    """

    reports = (
        _ordered_scored_reports(
            sessions,
            summaries,
        )
    )

    if not reports:
        return {
            "contract_version": (
                SESSION_RISK_INSIGHT_CONTRACT_VERSION
            ),
            "status": TREND_NO_DATA,
            "session_id": None,
            "previous_session_id": None,
            "overall_session_risk_score": None,
            "previous_session_risk_score": None,
            "score_delta": None,
            "trend": TREND_NO_DATA,
            "risk_score_method": None,
            "deadband_points": TREND_DEADBAND_POINTS,
        }

    current = reports[
        0
    ]

    current_session_id = (
        current[
            "session_id"
        ]
    )

    current_score = (
        current[
            "score"
        ]
    )

    current_method = (
        current[
            "method"
        ]
    )

    if current_method is None:
        return {
            "contract_version": (
                SESSION_RISK_INSIGHT_CONTRACT_VERSION
            ),
            "status": TREND_NO_COMPARISON,
            "session_id": current_session_id,
            "previous_session_id": None,
            "overall_session_risk_score": current_score,
            "previous_session_risk_score": None,
            "score_delta": None,
            "trend": TREND_NO_COMPARISON,
            "risk_score_method": None,
            "deadband_points": TREND_DEADBAND_POINTS,
        }

    previous = next(
        (
            report
            for report
            in reports[
                1:
            ]
            if (
                report[
                    "method"
                ]
                ==
                current_method
            )
        ),
        None,
    )

    if previous is None:
        return {
            "contract_version": (
                SESSION_RISK_INSIGHT_CONTRACT_VERSION
            ),
            "status": TREND_NO_COMPARISON,
            "session_id": current_session_id,
            "previous_session_id": None,
            "overall_session_risk_score": current_score,
            "previous_session_risk_score": None,
            "score_delta": None,
            "trend": TREND_NO_COMPARISON,
            "risk_score_method": current_method,
            "deadband_points": TREND_DEADBAND_POINTS,
        }

    previous_score = (
        previous[
            "score"
        ]
    )

    delta = (
        current_score
        -
        previous_score
    )

    trend = classify_risk_trend(
        current_score,
        previous_score,
    )

    return {
        "contract_version": (
            SESSION_RISK_INSIGHT_CONTRACT_VERSION
        ),
        "status": "AVAILABLE",
        "session_id": current_session_id,
        "previous_session_id": (
            previous[
                "session_id"
            ]
        ),
        "overall_session_risk_score": current_score,
        "previous_session_risk_score": previous_score,
        "score_delta": float(
            delta
        ),
        "trend": trend,
        "risk_score_method": current_method,
        "deadband_points": TREND_DEADBAND_POINTS,
    }


def build_session_risk_trend_series(
    sessions,
    summaries,
    max_points: int = 10,
) -> list[dict]:
    """
    Build chart points for Dashboard Risk Trend History.

    Rules:
    - COMPLETED Sessions only.
    - average_risk_score must be available.
    - Uses the risk_score_method of the latest scored Session.
    - Sessions using another method are excluded.
    - Missing scores are skipped, never converted to zero.
    - Returned order is oldest -> newest for graph display.
    """

    if (
        type(max_points) is not int
        or
        max_points <= 0
    ):
        raise ValueError(
            "max_points must be a positive integer"
        )

    reports = (
        _ordered_scored_reports(
            sessions,
            summaries,
        )
    )

    if not reports:
        return []

    current_method = (
        reports[
            0
        ][
            "method"
        ]
    )

    # A report without a method cannot safely be compared
    # with historical reports. It can still appear as one
    # standalone point.
    if current_method is None:
        current = reports[
            0
        ]

        return [
            {
                "session_id": (
                    current[
                        "session_id"
                    ]
                ),
                "score": (
                    current[
                        "score"
                    ]
                ),
                "risk_score_method": None,
            }
        ]

    comparable = [
        report
        for report
        in reports
        if (
            report[
                "method"
            ]
            ==
            current_method
        )
    ]

    # reports are newest -> oldest.
    # Keep latest N, then reverse for chart.
    comparable = (
        comparable[
            :max_points
        ]
    )

    comparable.reverse()

    return [
        {
            "session_id": (
                report[
                    "session_id"
                ]
            ),
            "score": (
                report[
                    "score"
                ]
            ),
            "risk_score_method": (
                report[
                    "method"
                ]
            ),
        }
        for report
        in comparable
    ]


def risk_trend_label(
    trend,
) -> str:
    labels = {
        TREND_IMPROVING: "Improving",
        TREND_STABLE: "Stable",
        TREND_WORSENING: "Worsening",
        TREND_NO_COMPARISON: "No comparison",
        TREND_NO_DATA: "N/A",
    }

    return labels.get(
        trend,
        "N/A",
    )


def risk_trend_description(
    insight,
) -> str:
    if not isinstance(
        insight,
        dict,
    ):
        return (
            "ไม่มีข้อมูลสำหรับเปรียบเทียบ"
        )

    trend = insight.get(
        "trend"
    )

    current_session_id = (
        insight.get(
            "session_id"
        )
    )

    previous_session_id = (
        insight.get(
            "previous_session_id"
        )
    )

    delta = insight.get(
        "score_delta"
    )

    if trend == TREND_NO_DATA:
        return (
            "ยังไม่มี Session ที่มี "
            "PostGuard Risk Score"
        )

    if trend == TREND_NO_COMPARISON:
        return (
            f"Session #{current_session_id} "
            "ยังไม่มี Session ก่อนหน้าที่ใช้ "
            "Risk Score Method เดียวกันสำหรับเปรียบเทียบ"
        )

    if (
        type(delta)
        not in (
            int,
            float,
        )
    ):
        return (
            "ไม่มีข้อมูล delta "
            "สำหรับเปรียบเทียบ"
        )

    sign = (
        "+"
        if delta > 0
        else
        ""
    )

    return (
        f"Session #{current_session_id} "
        f"เทียบกับ #{previous_session_id}: "
        f"{sign}{delta:.2f} points"
    )