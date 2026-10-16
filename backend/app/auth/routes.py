from fastapi import APIRouter, Depends, Header
from typing import Optional, Dict, Any

from backend.app.auth.models import UserSignUp, UserLogin, PasswordReset, AuthResponse, UserResponse
from backend.app.auth.service import AuthService, get_current_user_required

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=AuthResponse, summary="User Sign-up")
async def signup(payload: UserSignUp) -> AuthResponse:
    """Create a new account with email and password."""
    return AuthService.signup(payload)


@router.post("/login", response_model=AuthResponse, summary="User Login")
async def login(payload: UserLogin) -> AuthResponse:
    """Log in with registered email and password."""
    return AuthService.login(payload)


@router.get("/me", response_model=UserResponse, summary="Current User Profile")
async def get_current_user_profile(user: UserResponse = Depends(get_current_user_required)) -> UserResponse:
    """Return profile of currently authenticated user."""
    return user


@router.post("/reset-password", summary="Password Reset")
async def reset_password(payload: PasswordReset) -> Dict[str, str]:
    """Reset account password."""
    return AuthService.reset_password(payload)


@router.post("/logout", summary="User Logout")
async def logout(authorization: Optional[str] = Header(None)) -> Dict[str, str]:
    """Log out and revoke current session token."""
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            AuthService.logout(parts[1])
    return {"message": "Successfully logged out."}

