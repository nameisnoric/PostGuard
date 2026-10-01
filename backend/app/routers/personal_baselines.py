from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.camera import Camera
from app.models.personal_baseline import PersonalBaseline
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.personal_baseline import (
    PersonalBaselineCreate,
    PersonalBaselineResponse,
)

router = APIRouter(
    prefix="/personal-baselines",
    tags=["Personal Baselines"]
)

@router.post(
    "",
    response_model=PersonalBaselineResponse,
    status_code=status.HTTP_201_CREATED
)
def create_personal_baseline(
    request: PersonalBaselineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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

    baseline = PersonalBaseline(
        user_id=current_user.id,
        camera_id=request.camera_id,
        neck_flexion_baseline=request.neck_flexion_baseline,
        shoulder_angle=request.shoulder_angle,
        lateral_tilt_baseline=request.lateral_tilt_baseline,
        shoulder_tilt_status=request.shoulder_tilt_status,
        forward_head_baseline=request.forward_head_baseline,
        neck_rotation_baseline=request.neck_rotation_baseline,
        shoulder_level_difference_baseline=(
            request.shoulder_level_difference_baseline
        ),
        ipd_baseline=request.ipd_baseline,
        screen_distance_baseline=request.screen_distance_baseline
    )

    db.add(baseline)
    db.commit()
    db.refresh(baseline)

    return baseline

@router.get(
    "",
    response_model=list[PersonalBaselineResponse],
    status_code=status.HTTP_200_OK
)
def get_personal_baselines(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = (
        select(PersonalBaseline)
        .where(
            PersonalBaseline.user_id == current_user.id
        )
        .order_by(
            PersonalBaseline.created_at.desc()
        )
    )

    baselines = db.scalars(statement).all()

    return baselines

@router.get(
    "/{baseline_id}",
    response_model=PersonalBaselineResponse,
    status_code=status.HTTP_200_OK
)
def get_personal_baseline(
    baseline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = select(PersonalBaseline).where(
        PersonalBaseline.baseline_id == baseline_id,
        PersonalBaseline.user_id == current_user.id
    )

    baseline = db.scalar(statement)

    if baseline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personal baseline not found"
        )

    return baseline