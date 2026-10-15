r"""Opt-in API test on configured PostgreSQL; rollback all rows, mock email delivery.

Run from backend:
.\.venv\Scripts\python.exe -m scripts.check_password_reset --rollback-test
Uses real password hashing/JWT. Never prints passwords, OTPs, tokens or DB URLs.
Database ID sequences may advance even though test rows are rolled back.
"""

import argparse
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def check():
    load_dotenv(".env")
    from app.database.database import get_db
    from app.models.user import User
    from app.models.password_reset import PasswordResetOTP
    from app.core.security import hash_password
    from app.routers.auth import router

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 10})
    marker = "reset_check_" + uuid.uuid4().hex
    old_password = uuid.uuid4().hex + "Old1!"
    new_password = uuid.uuid4().hex + "New2!"
    with engine.connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            user = User(email=marker + "@ku.th", username=marker, password_hash=hash_password(old_password))
            db.add(user)
            db.flush()
            email = user.email
            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: db
            with TestClient(app) as client, patch("app.routers.auth.send_password_reset_otp") as send:
                def request_code():
                    result = client.post("/auth/forgot-password", json={"email": email})
                    assert result.status_code == 200, "Request OTP failed"
                    return send.call_args.kwargs["otp"]

                otp = request_code()
                wrong = "000000" if otp != "000000" else "111111"
                assert client.post("/auth/verify-reset-otp", json={"email": email, "otp": wrong}).status_code == 400
                record = db.scalar(select(PasswordResetOTP).where(PasswordResetOTP.user_id == user.id).order_by(PasswordResetOTP.created_at.desc()))
                assert record.attempt_count == 1
                record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                db.commit()
                assert client.post("/auth/verify-reset-otp", json={"email": email, "otp": otp}).status_code == 400
                otp = request_code()
                verified = client.post("/auth/verify-reset-otp", json={"email": email, "otp": otp})
                assert verified.status_code == 200, "Verify failed"
                token = verified.json()["reset_token"]
                assert client.post("/auth/reset_password", json={"reset_token": token, "new_password": "weak"}).status_code == 422
                result = client.post("/auth/reset_password", json={"reset_token": token, "new_password": new_password})
                assert result.status_code == 200, "Reset failed"
                assert client.post("/auth/reset_password", json={"reset_token": token, "new_password": old_password}).status_code == 401
                assert client.post("/auth/login", json={"email": email, "password": old_password}).status_code == 401
                assert client.post("/auth/login", json={"email": email, "password": new_password}).status_code == 200
                assert client.post("/auth/reset_password", json={"reset_token": "invalid", "new_password": new_password}).status_code == 401
                print("PASS: request, incorrect/expired OTP, resend, verify, password policy, reset, token reuse and login")
                print("Email delivery mocked; no emails sent")
        finally:
            db.close()
            transaction.rollback()
        assert connection.scalar(select(User.id).where(User.username == marker)) is None
        print("PASS: temporary account and OTP records rolled back")
    engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollback-test", action="store_true", required=True)
    parser.parse_args()
    try:
        check()
    except Exception as error:
        print("FAIL:", type(error).__name__)
        raise SystemExit(1)
