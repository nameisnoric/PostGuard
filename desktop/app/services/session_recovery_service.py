"""Explicit recovery of sessions left open by a previous application instance."""

import requests

from app.services.api_client import APIClient


# ``ENDED`` was used by an earlier Desktop/API version. It is a terminal
# historical state, so it is valid input but must never be recovered as active.
KNOWN_SESSION_STATUSES = {
    "RUNNING",
    "PAUSED",
    "COMPLETED",
    "INTERRUPTED",
    "ENDED",
}
ACTIVE_SESSION_STATUSES = {"RUNNING", "PAUSED"}


def find_unclosed_sessions() -> list[dict]:
    response = APIClient.get_sessions()
    if not response.ok:
        raise RuntimeError(f"Cannot check previous sessions: HTTP {response.status_code}")
    sessions = response.json()
    if not isinstance(sessions, list) or any(
        not isinstance(item, dict)
        or type(item.get("session_id")) is not int
        or item["session_id"] <= 0
        or item.get("status") not in KNOWN_SESSION_STATUSES
        for item in sessions
    ):
        raise ValueError("Invalid session list")
    return [item for item in sessions if item["status"] in ACTIVE_SESSION_STATUSES]


def interrupt_previous_session(session_id: int) -> None:
    try:
        response = APIClient.interrupt_session(session_id)
    except requests.RequestException:
        # The write may have succeeded before the connection was lost.
        response = APIClient.get_session(session_id)
    if not response.ok:
        raise RuntimeError(f"Cannot interrupt previous session: HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict) or data.get("session_id") != session_id or data.get("status") != "INTERRUPTED":
        raise ValueError("Backend did not confirm the interrupted session")
