from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)


class SignInRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AuthResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"


class UserProfile(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    created_at: datetime


class LogoutRequest(BaseModel):
    refresh_token: str | None = None