"""Pydantic models for authentication requests and responses."""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class LoginRequest(BaseModel):
    """Login request model."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="User password")
    role: str = Field(default="student", description="User role: 'student' or 'admin'")


class RegisterRequest(BaseModel):
    """User registration request model."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    role: str = Field(default="student", description="User role: 'student' or 'admin'")


class TokenResponse(BaseModel):
    """Token response after login/registration."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class RefreshRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class UserResponse(BaseModel):
    """User information response."""

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str = Field(description="ISO 8601 timestamp")

    class Config:
        from_attributes = True


class TokenData(BaseModel):
    """Token payload data."""

    sub: int = Field(description="User ID")
    email: str
    role: str
    type: str = "access"  # 'access' or 'refresh'
