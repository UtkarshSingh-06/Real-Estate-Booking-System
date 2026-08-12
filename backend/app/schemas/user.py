"""User schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import UserRole
from app.schemas.common import ORMModel


class UserOut(ORMModel):
    id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    role: UserRole | str = UserRole.BUYER
    phone: Optional[str] = None
    created_at: datetime


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., min_length=20)
    access_token: Optional[str] = None


class AuthResponse(BaseModel):
    session_token: str
    user: UserOut


class UserRoleUpdate(BaseModel):
    role: UserRole


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
