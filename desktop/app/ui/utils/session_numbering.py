"""User-facing sequence numbers for persisted monitoring sessions."""

from __future__ import annotations


def build_session_number_map(sessions: list[dict] | tuple[dict, ...]) -> dict[int, int]:
    """Map internal session IDs to a chronological 1-based user sequence."""
    valid = [
        session
        for session in sessions
        if isinstance(session, dict)
        and type(session.get("session_id")) is int
        and session["session_id"] > 0
    ]
    if not valid:
        return {}

    if all(isinstance(session.get("started_at"), str) and session["started_at"] for session in valid):
        ordered = sorted(
            valid,
            key=lambda session: (session["started_at"], session["session_id"]),
        )
    else:
        ordered = sorted(valid, key=lambda session: session["session_id"])

    return {
        session["session_id"]: sequence
        for sequence, session in enumerate(ordered, start=1)
    }


def session_number_text(session_id: object, number_map: dict[int, int]) -> str:
    """Return a plain sequence value suitable for a ``ครั้งที่`` column."""
    if type(session_id) is not int:
        return "--"
    sequence = number_map.get(session_id)
    return str(sequence) if sequence is not None else "--"
