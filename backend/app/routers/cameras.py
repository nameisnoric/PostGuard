from fastapi import APIRouter, Depends, status, HTTPException   
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.database import get_db
from app.models.camera import Camera
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.cameras import CameraCreate, CameraResponse

router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"]
)

@router.post(
    "",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED
)
def create_camera(
    request: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    camera = Camera(
        user_id=current_user.id,
        device_id=request.device_id,
        camera_name=request.camera_name,
        resolution_width=request.resolution_width,
        resolution_height=request.resolution_height,
        reprojection_error=request.reprojection_error
    )

    db.add(camera)
    db.commit()
    db.refresh(camera)

    return camera

@router.get(
    "",
    response_model=list[CameraResponse],
    status_code=status.HTTP_200_OK
)
def get_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = select(Camera).where(
        Camera.user_id == current_user.id
    )

    cameras = db.scalars(statement).all()

    return cameras

@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
    status_code=status.HTTP_200_OK
)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = select(Camera).where(
        Camera.camera_id == camera_id,
        Camera.user_id == current_user.id
    )

    camera = db.scalar(statement)

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    return camera