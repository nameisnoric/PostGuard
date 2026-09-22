from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserLogin, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token

import jwt

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

router = APIRouter(
    prefix = "/auth",
    tags = ["Auth"]
)

security = HTTPBearer()

@router.post(
    "/register",
    response_model = UserResponse,
    status_code = status.HTTP_201_CREATED
)

def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    statement = select(User).where(
        or_(
            User.email == user_data.email,
            User.username == user_data.username
        )
    )

    existing_user = db.scalar(statement)

    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "Email already registered"
            )

        if existing_user.username == user_data.username:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "Username already taken"
            )

    new_user = User(
        email = user_data.email,
        username = user_data.username,
        password_hash = hash_password(user_data.password),
        full_name = user_data.full_name
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.post(
    "/login",
    response_model = TokenResponse,
    status_code=status.HTTP_200_OK
)

def login_user(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    #หา email
    statement = select(User).where(
        User.email == user_data.email
    )

    user = db.scalar(statement)

    #ไม่เจอ email
    if user is  None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    #เช็ค password hash
    if not verify_password(
        user_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid email or password'
        )
    #JWT
    access_token = create_access_token(user.id)

    return{
        "access_token": access_token,
        "token_type":"bearer"
    }

def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
):
    token = credentials.credentials

    try:
        user_id = decode_access_token(token)

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or Expired token"
        )

    user = db.get(User, user_id)

    if user is None :
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User Not Found"
        )

    return user

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK
    )

def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user

    
