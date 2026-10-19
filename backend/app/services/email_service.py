import os

import resend
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv(
    "RESEND_FROM_EMAIL",
    "PostGuard <no-reply@postguardapp.xyz>",
)

if not RESEND_API_KEY:
    raise RuntimeError("RESEND_API_KEY is not setup")

resend.api_key = RESEND_API_KEY


def send_password_reset_otp(
    email: str,
    otp: str,
):
    params: resend.Email.SendParams = {
        "from": RESEND_FROM_EMAIL,
        "to": [email],
        "subject": "PostGuard Password Reset Code",
        "html": f"""
            <h2>PostGuard Password Reset</h2>

            <p>Your verify code is:</p>

            <h1>{otp}</h1>

            <p>This code will expire in 5 minutes.</p>
        """,
    }
    return resend.Emails.send(params)


def send_registration_otp(
    email: str,
    otp: str,
):
    params: resend.Email.SendParams = {
        "from": RESEND_FROM_EMAIL,
        "to": [email],
        "subject": "PostGuard Email Verification Code",
        "html": f"""
            <h2>Welcome to PostGuard</h2>

            <p>Your email verification code is:</p>

            <h1>{otp}</h1>

            <p>This code will expire in 5 minutes.</p>
        """,
    }

    return resend.Emails.send(params)
