"""Read-only helpers for displaying PostGuard Alert Events.

The API's `duration` is time from alert creation to alert closure.
It is NOT total posture exposure duration.
"""

from datetime import datetime


def validate_session_id(session_id):
    if type(session_id) is not int or session_id <= 0:
        raise ValueError("session_id must be a positive integer")
    return session_id


def summarize_alerts(alerts):
    if not isinstance(alerts, list):
        raise ValueError("Alert API must return a list")

    ids = set()
    active = 0
    closed = 0
    closed_duration = 0
    event_types = {}

    for alert in alerts:
        if not isinstance(alert, dict):
            raise ValueError("Each alert must be an object")
        event_id = alert.get("event_id")
        if type(event_id) is not int or event_id <= 0 or event_id in ids:
            raise ValueError("Invalid or duplicate event_id")
        ids.add(event_id)
        event_type = alert.get("event_type")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("Invalid event_type")
        event_types[event_type] = event_types.get(event_type, 0) + 1
        if alert.get("ended_at") is None:
            active += 1
        else:
            closed += 1
            duration = alert.get("duration")
            if type(duration) is not int or duration < 0:
                raise ValueError("Invalid duration")
            closed_duration += duration

    return {
        "total_alerts": len(alerts),
        "active_alerts": active,
        "closed_alerts": closed,
        "closed_alert_seconds": closed_duration,
        "event_type_counts": event_types,
    }


def local_datetime(value):
    """Format an ISO timestamp in the computer's local timezone."""
    if not value:
        return "--"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return value  # Do not invent a timezone for naive timestamps.
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, AttributeError):
        return str(value)
