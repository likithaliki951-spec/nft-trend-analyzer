"""Authentication and account lifecycle API endpoints."""

from __future__ import annotations

import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import (
    consume_password_reset_token,
    create_access_token,
    create_password_reset_token,
    create_user,
    decode_access_token,
    get_current_user,
    get_user_by_email,
    hash_password,
    update_user_password,
    validate_password_strength,
    verify_password,
)
from app.config import settings
from app.schemas import (
    AuthTokenResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthTokenResponse)
async def register(req: UserRegisterRequest) -> AuthTokenResponse:
    """Register a new analyst account with enterprise validation."""
    clean_email = req.email.strip().lower()
    clean_name = req.name.strip()

    if req.password != req.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password and confirmation password do not match.",
        )

    is_valid, msg = validate_password_strength(req.password, email=clean_email, name=clean_name)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    pwd_hash = hash_password(req.password)
    success, result = create_user(clean_email, clean_name, pwd_hash, role="analyst")
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

    user_data = {
        "id": result,
        "email": clean_email,
        "name": clean_name,
        "role": "analyst",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    token = create_access_token(user_data)
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user_data),
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(req: UserLoginRequest) -> AuthTokenResponse:
    """Sign in using work email and password."""
    clean_email = req.email.strip().lower()
    user = get_user_by_email(clean_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password.",
        )

    stored_hash = user.get("password_hash", "")
    if not verify_password(req.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password.",
        )

    # Transparent migration: upgrade legacy PBKDF2 hash to bcrypt
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            new_hash = hash_password(req.password)
            update_user_password(clean_email, new_hash)
        except Exception:
            pass

    user_data = {
        "id": str(user.get("id")),
        "email": clean_email,
        "name": user.get("name", clean_email),
        "role": user.get("role", "analyst"),
        "created_at": user.get("created_at"),
    }
    token = create_access_token(user_data)
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user_data),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> UserResponse:
    """Get the current authenticated user's profile."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"],
    )


@router.post("/forgot-password")
async def forgot_password(req: PasswordResetRequest) -> Dict[str, Any]:
    """Request a password reset link.

    SEC-01:
    - Never reveals whether an email is registered (returns identical generic response).
    - Never returns a reset token in JSON or response headers.
    - If email service provider is configured, dispatches out-of-band link.
    """
    clean_email = req.email.strip().lower()
    user = get_user_by_email(clean_email)

    if user and settings.EMAIL_PROVIDER_CONFIGURED:
        token = create_password_reset_token(clean_email)
        if token:
            try:
                from app.services.email_service import EmailService
                EmailService.send_password_reset_email(clean_email, token)
            except Exception:
                pass  # Do not leak failure reason or token to public client

    # Constant generic response preventing user enumeration and token leakage
    return {
        "success": True,
        "message": "If this email address is registered, password reset instructions have been prepared.",
    }


@router.post("/reset-password")
async def reset_password(req: PasswordResetConfirmRequest) -> Dict[str, Any]:
    """Confirm password reset with new strong password.

    SEC-04:
    - Enforces scope: requires payload['type'] == 'reset'. Ordinary login tokens rejected.
    - Atomically consumes token in persistent storage to prevent replay / concurrent reuse.
    """
    success, msg, email = consume_password_reset_token(req.token)
    if not success or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if req.new_password != req.new_password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation do not match.",
        )

    is_valid, policy_msg = validate_password_strength(req.new_password, email=email, name=user.get("name", ""))
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=policy_msg)

    new_hash = hash_password(req.new_password)
    update_user_password(email, new_hash)

    return {"success": True, "message": "Password updated successfully. You can now log in with your new credentials."}
