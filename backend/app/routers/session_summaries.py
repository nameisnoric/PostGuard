from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.alert_event import AlertEvent
from app.models.session import PostureSession
from app.models.session_summary import SessionSummary
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.session_summary import (
    SessionSummaryCreate,
    SessionSummaryResponse
)

router = APIRouter(
    tags=["Session Summaries"]
)

@router.post(
    "/sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
    status_code=status.HTTP_201_CREATED
)
def create_session_summary(
    session_id: int,
    request: SessionSummaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. ตรวจสอบว่า Session มีอยู่และเป็นของ User คนนี้
    session_statement = select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == current_user.id
    )

    posture_session = db.scalar(session_statement)

    if posture_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # 2. ต้องจบ Session ก่อนจึงจะสร้าง Summary ได้
    if posture_session.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session must be completed before creating a summary"
        )

    # 3. ตรวจสอบว่า Session นี้มี Summary อยู่แล้วหรือไม่
    existing_summary_statement = select(SessionSummary).where(
        SessionSummary.session_id == session_id
    )

    existing_summary = db.scalar(existing_summary_statement)

    if existing_summary is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session summary already exists"
        )

    # 4. ดึง Alert Events ทั้งหมดของ Session
    alert_statement = select(AlertEvent).where(
        AlertEvent.session_id == session_id
    )

    alert_events = db.scalars(alert_statement).all()

    # 5. คำนวณ Risk Duration
    low_risk_duration = sum(
        alert.duration
        for alert in alert_events
        if alert.risk_level == "LOW"
    )

    medium_risk_duration = sum(
        alert.duration
        for alert in alert_events
        if alert.risk_level == "MEDIUM"
    )

    high_risk_duration = sum(
        alert.duration
        for alert in alert_events
        if alert.risk_level == "HIGH"
    )

    # 6. นับจำนวน Alert แยกตาม Risk Level
    low_risk_alert_count = sum(
        1
        for alert in alert_events
        if alert.risk_level == "LOW"
    )

    medium_risk_alert_count = sum(
        1
        for alert in alert_events
        if alert.risk_level == "MEDIUM"
    )

    high_risk_alert_count = sum(
        1
        for alert in alert_events
        if alert.risk_level == "HIGH"
    )

    # 7. จำนวน Alert ทั้งหมด
    total_alert_count = len(alert_events)

    # 8. หา Event Type ที่เกิดบ่อยที่สุด
    most_frequent_alert_event = None

    if alert_events:
        event_counter = Counter(
            alert.event_type
            for alert in alert_events
        )

        most_frequent_alert_event = (
            event_counter.most_common(1)[0][0]
        )

    # 9. สร้าง Session Summary
    session_summary = SessionSummary(
        session_id=session_id,

        average_risk_score=request.average_risk_score,
        maximum_risk_score=request.maximum_risk_score,

        low_risk_duration=low_risk_duration,
        medium_risk_duration=medium_risk_duration,
        high_risk_duration=high_risk_duration,

        low_risk_alert_count=low_risk_alert_count,
        medium_risk_alert_count=medium_risk_alert_count,
        high_risk_alert_count=high_risk_alert_count,

        total_alert_count=total_alert_count,

        most_frequent_alert_event=most_frequent_alert_event,

        blink_rate=request.blink_rate
    )

    db.add(session_summary)
    db.commit()
    db.refresh(session_summary)

    return session_summary

@router.get(
    "/sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
    status_code=status.HTTP_200_OK
)
def get_session_summary(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ตรวจสอบว่า Session มีอยู่และเป็นของ User คนนี้
    session_statement = select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == current_user.id
    )

    posture_session = db.scalar(session_statement)

    if posture_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # หา Summary ของ Session
    summary_statement = select(SessionSummary).where(
        SessionSummary.session_id == session_id
    )

    session_summary = db.scalar(summary_statement)

    if session_summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session summary not found"
        )

    return session_summary

@router.get(
    "/summaries",
    response_model=list[SessionSummaryResponse],
    status_code=status.HTTP_200_OK
)
def get_summaries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = (
        select(SessionSummary)
        .join(
            PostureSession,
            SessionSummary.session_id == PostureSession.session_id
        )
        .where(
            PostureSession.user_id == current_user.id
        )
        .order_by(
            PostureSession.started_at.desc()
        )
    )

    session_summaries = db.scalars(statement).all()

    return session_summaries