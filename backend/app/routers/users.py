"""Authenticated user profile endpoints."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.routers.auth import get_authenticated_user, get_current_user
from app.schemas.user import UserProfileUpdate, UserResponse
from app.services.avatar_storage import (
    AvatarStorageError, SupabaseAvatarStorage, get_avatar_storage,
)


router = APIRouter(prefix="/users/me", tags=["Profile"])
MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_AVATAR_PIXELS = 25_000_000
AVATAR_SIZE = (400, 400)
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
ACCOUNT_DELETION_DELAY = timedelta(days=14)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post("/deletion-request", response_model=UserResponse)
def request_account_deletion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Place an active account in the required 14-day recovery period."""
    requested_at = utc_now()
    current_user.account_status = "PENDING_DELETION"
    current_user.deletion_requested_at = requested_at
    current_user.deletion_scheduled_for = requested_at + ACCOUNT_DELETION_DELAY
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/deletion-request", response_model=UserResponse)
def cancel_account_deletion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Recover an account while its 14-day recovery period is still open."""
    if current_user.account_status != "PENDING_DELETION":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account does not have a pending deletion request.",
        )
    deadline = current_user.deletion_scheduled_for
    if deadline is None or as_utc(deadline) <= utc_now():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="The account recovery period has ended.",
        )
    current_user.account_status = "ACTIVE"
    current_user.deletion_requested_at = None
    current_user.deletion_scheduled_for = None
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_profile(
    profile: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist the signed-in user's username and full name."""
    username_owner = db.scalar(
        select(User).where(
            User.username == profile.username,
            User.id != current_user.id,
        )
    )
    if username_owner:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use.",
        )

    current_user.username = profile.username
    current_user.full_name = profile.full_name
    try:
        db.commit()
        db.refresh(current_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use.",
        ) from exc
    return current_user


def normalize_avatar(content: bytes) -> bytes:
    """Validate, crop and re-encode an upload so metadata is not retained."""
    if not content or len(content) > MAX_AVATAR_BYTES:
        raise ValueError("Avatar must be a non-empty image no larger than 5 MB.")
    try:
        with Image.open(BytesIO(content)) as source:
            source.verify()
        with Image.open(BytesIO(content)) as source:
            if source.format not in {"JPEG", "PNG"}:
                raise ValueError("Avatar must be a JPG or PNG image.")
            if source.width * source.height > MAX_AVATAR_PIXELS:
                raise ValueError("Avatar dimensions are too large.")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image = ImageOps.fit(
                image,
                AVATAR_SIZE,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            output = BytesIO()
            image.save(output, format="WEBP", quality=85, method=6)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Avatar must be a readable JPG or PNG image.") from exc


@router.put("/avatar", status_code=status.HTTP_200_OK)
async def upload_avatar(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: SupabaseAvatarStorage = Depends(get_avatar_storage),
):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Avatar must be a JPG or PNG image.")
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="Avatar must not exceed 5 MB.")
    try:
        normalized = normalize_avatar(await request.body())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    new_path = f"users/{current_user.id}/{uuid4().hex}.webp"
    previous_path = current_user.avatar_path
    try:
        storage.upload(new_path, normalized)
        current_user.avatar_path = new_path
        db.commit()
        db.refresh(current_user)
    except AvatarStorageError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        try:
            storage.delete(new_path)
        except AvatarStorageError:
            pass
        raise

    if previous_path and previous_path != new_path:
        try:
            storage.delete(previous_path)
        except AvatarStorageError:
            pass
    return {"avatar_path": new_path}


@router.get("/avatar")
def read_avatar(
    current_user: User = Depends(get_current_user),
    storage: SupabaseAvatarStorage = Depends(get_avatar_storage),
):
    if not current_user.avatar_path:
        raise HTTPException(status_code=404, detail="Avatar is not set.")
    try:
        content = storage.download(current_user.avatar_path)
    except AvatarStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.delete("/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: SupabaseAvatarStorage = Depends(get_avatar_storage),
):
    previous_path = current_user.avatar_path
    if not previous_path:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    current_user.avatar_path = None
    db.commit()
    try:
        storage.delete(previous_path)
    except AvatarStorageError:
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)
