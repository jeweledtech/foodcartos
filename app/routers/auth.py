"""
Authentication Router

Handles user registration, login, and token management.
Uses Supabase Auth under the hood.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

router = APIRouter()


class UserRegister(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str
    organization_name: str
    role: str = "owner"


class UserLogin(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Authentication token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/register", response_model=TokenResponse)
async def register(user: UserRegister):
    """
    Register a new user and organization.

    Creates:
    - User account in Supabase Auth
    - Organization record
    - Links user to organization with specified role
    """
    # TODO: Implement with Supabase
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Registration not yet implemented",
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """
    Authenticate user and return tokens.

    Returns JWT tokens for API access.
    """
    # TODO: Implement with Supabase
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Login not yet implemented",
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token.
    """
    # TODO: Implement with Supabase
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token refresh not yet implemented",
    )


@router.post("/logout")
async def logout():
    """
    Logout user and invalidate tokens.
    """
    # TODO: Implement with Supabase
    return {"message": "Logged out successfully"}
