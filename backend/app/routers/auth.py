from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
    ForgotPasswordRequest,
    MessageResponse,
    VerifyResetOTPRequest,
    ResetTokenResponse,
    ResetPasswordRequest,
    RegistrationOTPRequest,
    RegistrationOTPVerify
)
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token, generate_otp, hash_otp, verify_otp, create_password_reset_token, decode_password_reset_token
from app.models.password_reset import PasswordResetOTP
from app.services.email_service import send_password_reset_otp, send_registration_otp
from app.models.register_otp import RegistrationOTP

from datetime import datetime, timedelta, timezone

import jwt
import uuid

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

@router.post(
    "/forgot-password",
    response_model= MessageResponse,
    status_code= status.HTTP_200_OK
)

def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    statement = select(User).where(
        User.email == request.email
    )

    user = db.scalar(statement)

    #เช็ค user
    if user is None:
        return{
            "message" : "don't have user"
        }

    #otp 
    otp = generate_otp()

    #hash otp
    otp_hashed = hash_otp(otp)  

    #ทำเวลาหมดอายุ otp 5min
    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(
        minutes= 5
    )

    reset_otp = PasswordResetOTP(
        user_id = user.id,
        otp_hash = otp_hashed,
        expires_at = expires_at,
        used_at = None,
        attempt_count = 0,
        created_at = now
    )

    #insert db
    db.add(reset_otp)
    db.commit()

    send_password_reset_otp(
        email= str(user.email),
        otp = otp
        )
    
    return {
        "message" : "If the email exists, a reset code has been generated"
    }

@router.post(
    "/verify-reset-otp",
    response_model=ResetTokenResponse,
    status_code= status.HTTP_200_OK
)

def verify_reset_otp(
    request: VerifyResetOTPRequest,
    db: Session = Depends(get_db)
):
    statement = select(User).where(
        User.email == request.email
    )
    user = db.scalar(statement)

    if user is None :
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Invalid or expired OTP")
        )

    #หา OTP ล่าสุด
    statement = (
        select(PasswordResetOTP).where(
            PasswordResetOTP.user_id == user.id,    
            PasswordResetOTP.used_at.is_(None)
        )
        .order_by(PasswordResetOTP.created_at.desc())
    )

    reset_otp = db.scalars(statement).first()

    if reset_otp is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or Expire OTP"
        )

    #เช็คจำนวนการกรอก ไม่เกิน 5 นะจ้ะ
    if reset_otp.attempt_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or Expire OTP"
        )

    #เช็ควันหมดอายุ OTP
    now = datetime.now(timezone.utc)

    if reset_otp.expires_at < now:
        raise HTTPException(
            status_code= status.HTTP_400_BAD_REQUEST,
            detail="Invalid or Expire OTP"
        )

    #เช็คเลข OTP
    if not verify_otp(
        request.otp,
        reset_otp.otp_hash
    ):
        reset_otp.attempt_count += 1
        db.commit()

        raise HTTPException(
            status_code= status.HTTP_400_BAD_REQUEST,
            detail="Invalid or Expire OTP"
        )

    #ถ้า verify ตรง
    reset_otp.used_at = datetime.now(timezone.utc)

    reset_token_jti = str(uuid.uuid4())
    reset_otp.reset_token_jti = reset_token_jti
    reset_token = create_password_reset_token(
        user_id = user.id,
        jti = reset_token_jti
    )
    db.commit()

    return {
        "reset_token" : reset_token,
        "token_type" : "bearer"
    }

@router.post(
    "/reset_password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK
)

def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    #ตรวจ reset token
    try:
        user_id, jti = decode_password_reset_token(
            request.reset_token
        )

    except(
        jwt.ExpiredSignatureError,
        jwt.InvalidTokenError,
        ValueError
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expire token"
        )

    #หา user จาก reset token
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    statement = select(PasswordResetOTP).where(
        PasswordResetOTP.user_id == user_id,
        PasswordResetOTP.reset_token_jti == jti
    )

    reset_record = db.scalar(statement)

    if reset_record is None :
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail= "Invalid or expire token"
        )

    #เช็ค reset token ว่าใช้ยัง
    if reset_record.reset_token_used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset Token is already uesd"
        )

    #hash password ใหม่
    new_password_hash = hash_password(
        request.new_password
    )

    #เปลี่ยน password 
    user.password_hash = new_password_hash

    #ปรับว่า reset token ใช้ไปแล้ว
    reset_record.reset_token_used_at = datetime.now(timezone.utc)
    
    db.commit()

    return{
        "message" : "Password is change already"
    }

@router.post(
    "/register/request-otp",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK
)
def request_registration_otp(
    request: RegistrationOTPRequest,
    db: Session = Depends(get_db)
):
    # 1. ตรวจสอบว่า email หรือ username ถูกใช้ไปแล้วหรือยัง
    statement = select(User).where(
        or_(
            User.email == request.email,
            User.username == request.username
        )
    )

    existing_user = db.scalar(statement)

    if existing_user:
        if existing_user.email == request.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        if existing_user.username == request.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

    # 2. สร้าง OTP 6 หลัก
    otp = generate_otp()

    # 3. Hash OTP ก่อนเก็บลง Database
    otp_hashed = hash_otp(otp)

    # 4. Hash Password ก่อนเก็บข้อมูลสมัครชั่วคราว
    password_hashed = hash_password(request.password)

    # 5. กำหนด OTP หมดอายุภายใน 5 นาที
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)

    # 6. สร้าง Pending Registration
    registration_otp = RegistrationOTP(
        email=str(request.email),
        username=request.username,
        password_hash=password_hashed,
        full_name=request.full_name,
        otp_hash=otp_hashed,
        expires_at=expires_at,
        attempt_count=0,
        used_at=None,
        created_at=now
    )

    # 7. บันทึกลง Database
    db.add(registration_otp)
    db.commit()

    # 8. ส่ง OTP ทาง Email
    send_registration_otp(
        email=str(request.email),
        otp=otp
    )

    return {
        "message": "Verification code sent"
    }

@router.post(
    "/register/verify-otp",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def verify_registration_otp(
    request: RegistrationOTPVerify,
    db: Session = Depends(get_db)
):
    # 1. หา Registration OTP ล่าสุดของ email นี้
    statement = (
        select(RegistrationOTP)
        .where(
            RegistrationOTP.email == str(request.email),
            RegistrationOTP.used_at.is_(None)
        )
        .order_by(RegistrationOTP.created_at.desc())
    )

    registration = db.scalars(statement).first()

    # 2. ไม่พบ OTP ที่ยังไม่ได้ใช้
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )

    # 3. ตรวจจำนวนครั้งที่กรอก OTP ผิด
    if registration.attempt_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )

    # 4. ตรวจว่า OTP หมดอายุหรือยัง
    now = datetime.now(timezone.utc)
    if registration:
        print("email:", registration.email)
        print("attempt_count:", registration.attempt_count)
        print("used_at:", registration.used_at)
        print("expires_at:", registration.expires_at)
        print("expires_at tz:", registration.expires_at.tzinfo)

        print("now:", now)
        print("now tz:", now.tzinfo)
        print("OTP entered:", request.otp)

    if registration:
        print(
            "OTP valid:",
            verify_otp(request.otp, registration.otp_hash)
    )

    if registration.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )

    # 5. ตรวจ OTP
    if not verify_otp(
        request.otp,
        registration.otp_hash
    ):
        registration.attempt_count += 1
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )

    # 6. ตรวจ email / username ซ้ำอีกครั้งก่อนสร้าง User
    statement = select(User).where(
        or_(
            User.email == registration.email,
            User.username == registration.username
        )
    )

    existing_user = db.scalar(statement)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )

    # 7. OTP ถูกต้อง -> สร้าง User จริง
    new_user = User(
        email=registration.email,
        username=registration.username,
        password_hash=registration.password_hash,
        full_name=registration.full_name
    )

    db.add(new_user)

    # 8. ทำเครื่องหมายว่า OTP ถูกใช้แล้ว
    registration.used_at = now

    # 9. บันทึกทั้งสองอย่างพร้อมกัน
    db.commit()
    db.refresh(new_user)

    print("=== REGISTRATION OTP DEBUG ===")
    print("registration:", registration)

    return new_user
    


    


    
