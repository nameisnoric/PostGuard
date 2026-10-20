"""Privacy Notice version and consent-state helpers."""

CURRENT_PRIVACY_NOTICE_VERSION = "2026-10-20"


def has_current_privacy_consent(user) -> bool:
    return (
        user.privacy_consent_version == CURRENT_PRIVACY_NOTICE_VERSION
        and user.privacy_consent_accepted_at is not None
        and user.privacy_consent_withdrawn_at is None
    )
