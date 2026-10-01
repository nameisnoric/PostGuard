from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.camera import Camera
from app.models.personal_baseline import PersonalBaseline
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.session import SessionResponse, SessionStart
from app.models.alert_event import AlertEvent

from datetime import timezone, datetime

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"]
)

@router.post(
    "/start",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED
)
def start_session(
    request: SessionStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. ตรวจสอบว่า Camera เป็นของ User ที่ Login อยู่
    camera_statement = select(Camera).where(
        Camera.camera_id == request.camera_id,
        Camera.user_id == current_user.id
    )

    camera = db.scalar(camera_statement)

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    # 2. ตรวจสอบว่า Personal Baseline เป็นของ User ที่ Login อยู่
    baseline_statement = select(PersonalBaseline).where(
        PersonalBaseline.baseline_id == request.baseline_id,
        PersonalBaseline.user_id == current_user.id
    )

    baseline = db.scalar(baseline_statement)

    if baseline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personal baseline not found"
        )

    # 3. ตรวจสอบว่า Baseline ถูกสร้างจาก Camera ตัวเดียวกับที่กำลังใช้
    if baseline.camera_id != request.camera_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Personal baseline does not belong to this camera"
        )

    # 4. ตรวจสอบว่า User ไม่มี Session ที่กำลังทำงานอยู่
    active_session_statement = select(PostureSession).where(
        PostureSession.user_id == current_user.id,
        PostureSession.status.in_(["RUNNING", "PAUSED"])
    )

    active_session = db.scalar(active_session_statement)

    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active session already exists"
        )

    # 5. สร้าง Session ใหม่
    new_session = PostureSession(
        user_id=current_user.id,
        camera_id=request.camera_id,
        baseline_id=request.baseline_id,
        status="RUNNING",
        total_duration=0,
        paused_duration=0,
        pause_count=0
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return new_session

@router.post(
    "/{session_id}/pause",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK
)
def pause_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == current_user.id
    )

    posture_session = db.scalar(statement)

    if posture_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if posture_session.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a running session can be paused"
        )

    now = datetime.now(timezone.utc)

    # หา Alert ทั้งหมดที่ยังเปิดอยู่ใน Session นี้
    active_alert_statement = select(AlertEvent).where(
        AlertEvent.session_id == session_id,
        AlertEvent.ended_at.is_(None)
    )

    active_alerts = db.scalars(active_alert_statement).all()

    # ปิด Alert ที่ยัง Active ทั้งหมด
    for alert_event in active_alerts:
        duration_seconds = int(
            (now - alert_event.started_at).total_seconds()
        )

        alert_event.ended_at = now
        alert_event.duration = duration_seconds

    # เปลี่ยน Session เป็น PAUSED
    posture_session.status = "PAUSED"
    posture_session.paused_at = now
    posture_session.pause_count += 1

    db.commit()
    db.refresh(posture_session)

    return posture_session

@router.post(
    "/{session_id}/resume",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK
)
def resume_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == current_user.id
    )

    posture_session = db.scalar(statement)

    if posture_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if posture_session.status != "PAUSED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a paused session can be resumed"
        )

    if posture_session.paused_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session pause time is missing"
        )

    now = datetime.now(timezone.utc)

    pause_seconds = int(
        (now - posture_session.paused_at).total_seconds()
    )

    posture_session.paused_duration += pause_seconds
    posture_session.paused_at = None
    posture_session.status = "RUNNING"

    db.commit()
    db.refresh(posture_session)

    return posture_session

@router.post(
    "/{session_id}/end",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK
)
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == current_user.id
    )

    posture_session = db.scalar(statement)

    if posture_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if posture_session.status not in ["RUNNING", "PAUSED"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an active session can be ended"
        )

    now = datetime.now(timezone.utc)

    # ปิด Alert ที่ยัง Active อยู่ทั้งหมด
    active_alert_statement = select(AlertEvent).where(
        AlertEvent.session_id == session_id,
        AlertEvent.ended_at.is_(None)
    )

    active_alerts = db.scalars(active_alert_statement).all()

    for alert_event in active_alerts:
        duration_seconds = int(
            (now - alert_event.started_at).total_seconds()
        )

        alert_event.ended_at = now
        alert_event.duration = duration_seconds

    # ถ้า End ขณะที่ Session กำลัง Pause
    # ต้องเก็บเวลา Pause รอบสุดท้ายด้วย
    if posture_session.status == "PAUSED":
        if posture_session.paused_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session pause time is missing"
            )

        pause_seconds = int(
            (now - posture_session.paused_at).total_seconds()
        )

        posture_session.paused_duration += pause_seconds
        posture_session.paused_at = None

    # คำนวณเวลาทั้งหมดตั้งแต่ Start → End
    total_seconds = int(
        (now - posture_session.started_at).total_seconds()
    )

    posture_session.total_duration = total_seconds
    posture_session.ended_at = now
    posture_session.status = "COMPLETED"

    db.commit()
    db.refresh(posture_session)

    return posture_session

@router.get(
    "",
    response_model=list[SessionResponse],
    status_code=status.HTTP_200_OK
)
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = (
        select(PostureSession)
        .where(
            PostureSession.user_id == current_user.id
        )
        .order_by(
            PostureSession.started_at.desc()
        )
    )

    sessions = db.scalars(statement).all()

    return sessions

@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK
)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == current_user.id
    )

    posture_session = db.scalar(statement)

    if posture_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return posture_session