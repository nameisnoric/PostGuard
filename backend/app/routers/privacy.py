"""Authenticated Privacy Notice consent endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.privacy import (
    CURRENT_PRIVACY_NOTICE_VERSION,
    has_current_privacy_consent,
)
from app.database.database import get_db
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.user import PrivacyConsentAccept, PrivacyConsentResponse


router = APIRouter(prefix="/users/me/privacy-consent", tags=["Privacy"])


def consent_response(user: User) -> PrivacyConsentResponse:
    return PrivacyConsentResponse(
        notice_version=CURRENT_PRIVACY_NOTICE_VERSION,
        accepted_version=user.privacy_consent_version,
        accepted_at=user.privacy_consent_accepted_at,
        withdrawn_at=user.privacy_consent_withdrawn_at,
        has_current_consent=has_current_privacy_consent(user),
    )


@router.get("", response_model=PrivacyConsentResponse)
def get_privacy_consent(
    current_user: User = Depends(get_current_user),
):
    return consent_response(current_user)


@router.put("", response_model=PrivacyConsentResponse)
def accept_privacy_consent(
    request: PrivacyConsentAccept,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.notice_version != CURRENT_PRIVACY_NOTICE_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The Privacy Notice has changed. Review the current version.",
        )

    current_user.privacy_consent_version = CURRENT_PRIVACY_NOTICE_VERSION
    current_user.privacy_consent_accepted_at = datetime.now(timezone.utc)
    current_user.privacy_consent_withdrawn_at = None
    db.commit()
    db.refresh(current_user)
    return consent_response(current_user)


@router.delete("", response_model=PrivacyConsentResponse)
def withdraw_privacy_consent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active_session = db.scalar(
        select(PostureSession).where(
            PostureSession.user_id == current_user.id,
            PostureSession.status.in_(("RUNNING", "PAUSED")),
        )
    )
    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop the active monitoring session before withdrawing consent.",
        )

    if (
        current_user.privacy_consent_accepted_at is not None
        and current_user.privacy_consent_withdrawn_at is None
    ):
        current_user.privacy_consent_withdrawn_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(current_user)
    return consent_response(current_user)
