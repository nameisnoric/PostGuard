"""Presentation helpers for PostGuard's RULA-adapted risk score."""

import math


def rula_score_to_percent(score):
    """Map the internal RULA-adapted score range 1–7 to 0–100%."""
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    value = float(score)
    if not math.isfinite(value) or not 1 <= value <= 7:
        return None
    return (value - 1.0) * 100.0 / 6.0


def format_rula_percent(score, decimals=0):
    """Return a user-facing percentage, or ``N/A`` for an invalid score."""
    percent = rula_score_to_percent(score)
    if percent is None:
        return "N/A"
    return f"{percent:.{max(0, int(decimals))}f}%"
