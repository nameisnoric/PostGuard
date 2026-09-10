from pydantic import BaseModel, EmailStr

#ตรวจจาก Frontend   
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str | None = None

#ส่งกลับ Backend
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: str | None = None

    model_config = {
        "from_attributes": True
    }