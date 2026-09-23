from pydantic import BaseModel, EmailStr, field_validator
import re

#register จาก front
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str | None = None

    #Validate Domain
    @field_validator("email")
    @classmethod 
    def validate_ku_email(cls, email: EmailStr):
        if not str(email).lower().endswith("@ku.th"):
            raise ValueError("Email Must Be Use only @ku.th")
        return email

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str):
        if len(password) < 8:
            raise ValueError("Password must be longer or equal 8 characters")
        
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must be have least 1 upper letter")

        if not re.search(r"[a-z]", password):
            raise ValueError("Password must be have least 1 lower letter")
        
        if not re.search(r"\d", password):
            raise ValueError("Password must contain at least one number")

        if not re.search(r"[^A-Za-z0-9]", password):
            raise ValueError("Password must contain at least one special character")

        return password

#ส่งกลับ Backend
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: str | None = None

    model_config = {
        "from_attributes": True
    }

class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def validate_ku_email(cls, email: EmailStr) -> EmailStr:
        if not str(email).lower().endswith("@ku.th"):
            raise ValueError("Email must be use @ku.th domain")
        return email

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def validate_ku_email(cls, email: EmailStr) -> EmailStr:
        if not str(email).lower().endswith("@ku.th"):
            raise ValueError("Email must be use @ku.th domain")
        return email

class MessageResponse(BaseModel):
    message: str

class VerifyResetOTPRequest(BaseModel):
    email: EmailStr
    otp: str

    @field_validator("email")
    @classmethod
    def validate_ku_email(cls, email: EmailStr) -> EmailStr:
        if not str(email).lower().endswith("@ku.th"):
            raise ValueError("Email must be use @ku.th domain")
        return email

    @field_validator("otp")
    @classmethod  
    def validate_otp(cls, otp: str) -> str:
        if not otp.isdigit() or len(otp) != 6:
            raise ValueError("OTP must be exactly 6 digits")
        return otp

class ResetTokenResponse(BaseModel):
    reset_token: str
    token_type : str

class ResetPasswordRequest(BaseModel):
    reset_token : str
    new_password : str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, password: str) -> str:
        if len(password) < 8:
            raise ValueError("Password must be longer or equal 8 characters")
                
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must be have least 1 upper letter")
        
        if not re.search(r"[a-z]", password):
            raise ValueError("Password must be have least 1 lower letter")
                
        if not re.search(r"\d", password):
            raise ValueError("Password must contain at least one number")
        
        if not re.search(r"[^A-Za-z0-9]", password):
            raise ValueError("Password must contain at least one special character")
        
        return password