from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import UserRole

class UserBase(BaseModel):
    email: EmailStr
    username: str
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        allowed = {r.value for r in UserRole}
        if value not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}")
        return value

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        return value

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {r.value for r in UserRole}
        if value not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        return value

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class ServerAccessItem(BaseModel):
    server_id: int
    permission: str = "read"

    @field_validator("permission")
    @classmethod
    def validate_permission(cls, value: str) -> str:
        if value not in {"read", "write"}:
            raise ValueError("permission must be 'read' or 'write'")
        return value

class ServerAccessAssignRequest(BaseModel):

    accesses: list[ServerAccessItem]

class ServerAccessResponse(BaseModel):
    server_id: int
    permission: str
    granted_at: datetime

    class Config:
        from_attributes = True
