import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    csrf_token: str
    user: UserOut


class MessageResponse(BaseModel):
    message: str
