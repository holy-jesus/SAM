from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class SetupStatusResponse(BaseModel):
    is_initialized: bool


class InitAdminRequest(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    full_name: Optional[str] = None
    role: str = "admin"
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
