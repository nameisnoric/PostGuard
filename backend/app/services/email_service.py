import os

import resend
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

if not RESEND_API_KEY:
    raise RuntimeError("RESEND_API_KEY is not setup")

resend.api_key = RESEND_API_KEY

def send_password_reset_otp(
    email: str,
    otp: str
):
    #ส่วน head email
    params: resend.Email.SendParams = {
        "from" : "PostGuard <onboarding@resend.dev>",
        "to" : ["witsanu.e@ku.th"],
        "subject" : "PostGuard Password Reset Code",
        "html" : f"""
            <h2>PostGuard Password Reset</h2>

            <p>Your verify code is :</p>

            <h1>{otp}</h1>

            <p>This code will expire in 5 minutes</p>
            
            """
    }
    return resend.Emails.send(params)