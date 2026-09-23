import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash
import uuid

import secrets

load_dotenv()

#hash
password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)

#เช็คว่า password ตรงมั้ย
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

#JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not setup")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTE = 30

def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTE
    )

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token

def decode_access_token(token: str) -> int:
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )

    user_id = payload.get("sub")

    if user_id is None:
        raise ValueError("Invalid Token")
    
    return int(user_id)

#OTP
def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

#hash OTP
def hash_otp(otp: str) -> str:
    return password_hash.hash(otp)

#verify OTP
def verify_otp(
    plain_otp: str,
    hashed_otp: str
) -> bool : 
    return password_hash.verify(
        plain_otp,
        hashed_otp
    )

#token ตอน reset password
def create_password_reset_token(user_id: int, jti: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta (minutes=10)

    payload = {
        "sub" : str(user_id),
        "purpose": "password_reset",
        "jti": jti,
        "exp" : expire
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token

def decode_password_reset_token(token : str) -> tuple[int, str]:
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )

    if payload.get("purpose") != "password_reset":
        raise ValueError("Invalid reset token")

    user_id = payload.get("sub")
    jti = payload.get("jti")

    if user_id is None:
        raise ValueError("Invalid reset token")

    return int(user_id), jti