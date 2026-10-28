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
    incomplete = 0
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
        if alert.get("incomplete"):
            incomplete += 1
        elif alert.get("ended_at") is None:
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
        "incomplete_alerts": incomplete,
        "closed_alert_seconds": closed_duration,
        "event_type_counts": event_types,
    }


def summarize_integrated_alerts(risk_events, notifications):
    """Summarize persisted risk episodes and notifications for one session."""
    if not isinstance(risk_events, list) or not isinstance(notifications, list):
        raise ValueError("Integrated alert APIs must return lists")

    event_ids = set()
    active = 0
    resolved = 0
    incomplete = 0
    resolved_duration = 0.0
    for event in risk_events:
        if not isinstance(event, dict):
            raise ValueError("Each risk event must be an object")
        event_id = event.get("risk_event_id")
        if type(event_id) is not int or event_id <= 0 or event_id in event_ids:
            raise ValueError("Invalid or duplicate risk_event_id")
        event_ids.add(event_id)
        event_status = event.get("status")
        if event_status == "ACTIVE":
            active += 1
        elif event_status == "RESOLVED":
            resolved += 1
            duration = event.get("duration_seconds")
            if type(duration) not in (int, float) or duration < 0:
                raise ValueError("Invalid resolved risk-event duration")
            resolved_duration += float(duration)
        elif event_status == "INCOMPLETE":
            incomplete += 1

    notification_ids = set()
    for notification in notifications:
        if not isinstance(notification, dict):
            raise ValueError("Each alert notification must be an object")
        notification_id = notification.get("notification_id")
        if (
            type(notification_id) is not int
            or notification_id <= 0
            or notification_id in notification_ids
        ):
            raise ValueError("Invalid or duplicate notification_id")
        notification_ids.add(notification_id)

    return {
        "total_alerts": len(notifications),
        "active_alerts": active,
        "closed_alerts": resolved,
        "incomplete_alerts": incomplete,
        "closed_alert_seconds": round(resolved_duration),
    }


def local_datetime(value):
    """Format an ISO timestamp in the computer's local timezone."""
    if not value:
        return "--"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return value  # Do not invent a timezone for naive timestamps.
        return dt.astimezone().strftime("%d/%m/%Y %H:%M:%S")
    except (ValueError, TypeError, AttributeError):
        return str(value)


def duration_text(seconds):
    """Format a known duration as HH:MM:SS without inventing missing data."""
    if seconds is None:
        return "N/A"
    if type(seconds) not in (int, float) or seconds < 0:
        return "N/A"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def event_type_label(value):
    """Turn API enum text into a readable label while preserving unknown values."""
    if not isinstance(value, str) or not value:
        return "N/A"
    return value.replace("_", " ").title()
