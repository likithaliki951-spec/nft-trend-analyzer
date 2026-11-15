"""Authentication and account lifecycle API endpoints with separate User and Admin portals."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

logger = logging.getLogger("nft_trend_analyzer.auth")

from app.auth import (
    check_rate_limit,
    consume_admin_verification_token,
    consume_password_reset_token,
    create_access_token,
    create_admin_verification_token,
    create_password_reset_token,
    create_user,
    decode_access_token,
    delete_user,
    get_current_user,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    is_valid_gmail,
    log_activity,
    update_user_email_verified,
    update_user_password,
    validate_password_strength,
    verify_admin_verification_token,
    verify_password,
)
from app.config import settings
from app.schemas import (
    AdminLoginRequest,
    AdminRegisterRequest,
    AdminVerifyEmailRequest,
    AuthTokenResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ==============================================================================
# Helper functions
# ==============================================================================

def _get_client_ip(request: Request) -> str:
    """Extract client IP address considering proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


# ==============================================================================
# Regular User Authentication Portal
# ==============================================================================

@router.post("/user/register", response_model=AuthTokenResponse)
async def user_register(req: UserRegisterRequest, request: Request) -> AuthTokenResponse:
    """Register a new regular user account with enterprise password validation.

    Regular users cannot register themselves as administrators.
    Role is strictly hardcoded to 'user'.
    """
    client_ip = _get_client_ip(request)
    if settings.IS_PRODUCTION and not check_rate_limit(f"reg_user_{client_ip}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please wait a minute before trying again.",
        )

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
    # Role is strictly user, status active, email verified true
    success, result = create_user(
        email=clean_email,
        name=clean_name,
        password_hash=pwd_hash,
        role="user",
        account_status="active",
        email_verified=True,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

    user_data = {
        "id": result,
        "email": clean_email,
        "name": clean_name,
        "role": "user",
        "account_status": "active",
        "email_verified": True,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    log_activity(
        action="user_registered",
        user_id=result,
        user_email=clean_email,
        details={"name": clean_name, "role": "user"},
        ip_address=client_ip,
    )

    token = create_access_token(user_data)
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user_data),
    )


@router.post("/user/login", response_model=AuthTokenResponse)
async def user_login(req: UserLoginRequest, request: Request) -> AuthTokenResponse:
    """Sign in using regular user credentials.

    Enforces account status checks and prevents admin credentials from using the user portal.
    """
    client_ip = _get_client_ip(request)
    if settings.IS_PRODUCTION and not check_rate_limit(f"login_user_{client_ip}", max_requests=20, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a minute before trying again.",
        )

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

    # SEC requirement: Separate login portals.
    # Administrators must not use the regular user login portal.
    user_role = user.get("role", "user")
    if user_role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator credentials cannot be used in the User Portal. Please authenticate at the Admin Portal (/admin/login).",
        )

    account_status = user.get("account_status", "active")
    if account_status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended. Please contact administrator support.",
        )
    if account_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending administrator approval.",
        )
    if account_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account registration was rejected.",
        )
    if account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
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
        "role": user_role,
        "account_status": account_status,
        "email_verified": bool(user.get("email_verified", True)),
        "created_at": user.get("created_at"),
    }

    log_activity(
        action="user_login",
        user_id=str(user.get("id")),
        user_email=clean_email,
        ip_address=client_ip,
    )

    token = create_access_token(user_data)
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user_data),
    )


# Backward-compatible routes
@router.post("/register", response_model=AuthTokenResponse, include_in_schema=False)
async def legacy_register(req: UserRegisterRequest, request: Request) -> AuthTokenResponse:
    """Legacy alias routing to user registration."""
    return await user_register(req, request)


@router.post("/login", response_model=AuthTokenResponse, include_in_schema=False)
async def legacy_login(req: UserLoginRequest, request: Request) -> AuthTokenResponse:
    """Legacy alias routing to appropriate login handler based on account role."""
    clean_email = req.email.strip().lower()
    user = get_user_by_email(clean_email)
    if user and user.get("role") == "admin":
        admin_req = AdminLoginRequest(email=req.email, password=req.password)
        return await admin_login(admin_req, request)
    return await user_login(req, request)


# ==============================================================================
# Administrator Authentication Portal
# ==============================================================================

@router.post("/admin/register")
async def admin_register(req: AdminRegisterRequest, request: Request) -> Dict[str, Any]:
    """Submit a subsequent administrator registration request.

    Critical Security Rules:
    - Restricted to valid Gmail address (@gmail.com / @googlemail.com).
    - Status is created as 'pending'.
    - Email verification is required.
    - An existing approved administrator must review and approve the request.
    - Pending administrators cannot access admin dashboard or protected admin APIs.
    """
    client_ip = _get_client_ip(request)
    if settings.IS_PRODUCTION and not check_rate_limit(f"reg_admin_{client_ip}", max_requests=5, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many administrator registration attempts. Please wait a minute.",
        )

    clean_email = req.email.strip().lower()
    clean_name = req.name.strip()

    # 1. Server-side Gmail validation
    if not is_valid_gmail(clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator registration is strictly restricted to valid Gmail addresses (@gmail.com or @googlemail.com).",
        )

    if req.password != req.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password and confirmation password do not match.",
        )

    is_valid, msg = validate_password_strength(req.password, email=clean_email, name=clean_name)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # 2. Check if account already exists
    if get_user_by_email(clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # In production, require email provider to be configured before accepting admin registrations
    if settings.IS_PRODUCTION and not settings.EMAIL_PROVIDER_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery provider is not configured. Administrator registration cannot proceed safely.",
        )

    pwd_hash = hash_password(req.password)

    # 3. Create administrator account in PENDING status with unverified email
    success, result = create_user(
        email=clean_email,
        name=clean_name,
        password_hash=pwd_hash,
        role="admin",
        account_status="pending",
        email_verified=False,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

    # Generate single-use email verification token
    verification_token = create_admin_verification_token(clean_email)

    if settings.EMAIL_PROVIDER_CONFIGURED:
        from app.services.email_service import EmailService
        sent, err_msg = EmailService.send_admin_verification_email(clean_email, verification_token)
        if not sent:
            delete_user(result)
            err_detail = (
                "Failed to dispatch administrator verification email. Please try again later."
                if settings.IS_PRODUCTION
                else f"Failed to dispatch administrator verification email: {err_msg}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=err_detail,
            )

    log_activity(
        action="admin_registration_request",
        user_id=result,
        user_email=clean_email,
        details={"name": clean_name, "status": "pending", "email_verified": False},
        ip_address=client_ip,
    )

    response_payload: Dict[str, Any] = {
        "success": True,
        "request_id": result,
        "email": clean_email,
        "status": "pending",
        "email_verified": False,
        "message": "Administrator registration request submitted successfully. Your request is pending email verification and approval by an active administrator.",
    }

    # In development/test mode without an external email provider, return the verification token
    # to facilitate automated QA testing
    if not settings.IS_PRODUCTION:
        response_payload["verification_token"] = verification_token

    return response_payload


@router.post("/admin/verify-email")
async def admin_verify_email(req: AdminVerifyEmailRequest, request: Request) -> Dict[str, Any]:
    """Verify email ownership for pending administrator applications with database-backed replay protection."""
    clean_email = req.email.strip().lower()
    success, message, user = consume_admin_verification_token(req.token, clean_email)
    if not success or not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    log_activity(
        action="admin_email_verified",
        user_id=user["id"],
        user_email=clean_email,
        ip_address=_get_client_ip(request),
    )

    return {
        "success": True,
        "message": message,
    }


@router.post("/admin/login", response_model=AuthTokenResponse)
async def admin_login(req: AdminLoginRequest, request: Request) -> AuthTokenResponse:
    """Sign in using verified administrator credentials.

    Enforces:
    - User must possess role: admin.
    - User must have account_status: active.
    - User email must be verified.
    - Pending, rejected, or suspended accounts are strictly rejected.
    """
    client_ip = _get_client_ip(request)
    if settings.IS_PRODUCTION and not check_rate_limit(f"login_admin_{client_ip}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many administrator sign-in attempts. Please wait a minute.",
        )

    clean_email = req.email.strip().lower()
    user = get_user_by_email(clean_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials.",
        )

    stored_hash = user.get("password_hash", "")
    if not verify_password(req.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials.",
        )

    # Check role
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Regular user accounts cannot access the Administrator Console. Please sign in via the User Portal (/user/login).",
        )

    # Check status
    account_status = user.get("account_status", "active")
    if account_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account is pending approval by an active administrator. Please check back once your request has been reviewed.",
        )
    if account_status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account has been suspended. Please contact platform administration.",
        )
    if account_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator registration request was rejected.",
        )
    if account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account is not active.",
        )

    # Check email verification
    if not bool(user.get("email_verified")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator email is not verified. Please complete email verification before signing in.",
        )

    # Upgrade hash if legacy
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
        "role": "admin",
        "account_status": "active",
        "email_verified": bool(user.get("email_verified", True)),
        "created_at": user.get("created_at"),
    }

    log_activity(
        action="admin_login",
        user_id=str(user.get("id")),
        user_email=clean_email,
        ip_address=client_ip,
    )

    token = create_access_token(user_data)
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user_data),
    )


# ==============================================================================
# Common Profile & Password Reset Endpoints
# ==============================================================================

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> UserResponse:
    """Get the current authenticated user's authoritative profile."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"],
        account_status=current_user.get("account_status", "active"),
        email_verified=current_user.get("email_verified", True),
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

    if user:
        if not settings.EMAIL_PROVIDER_CONFIGURED:
            logger.warning(
                "Password reset requested for %s, but no email provider is configured. "
                "Configure EMAIL_PROVIDER_API_KEY (or RESEND_API_KEY) and EMAIL_FROM.",
                clean_email,
            )
        else:
            token = create_password_reset_token(clean_email)
            if token:
                try:
                    from app.services.email_service import EmailService
                    ok, msg = EmailService.send_password_reset_email(clean_email, token)
                    if not ok:
                        logger.error("Password reset email dispatch failed for %s: %s", clean_email, msg)
                    else:
                        logger.info("Password reset email dispatched successfully for %s", clean_email)
                except Exception as exc:
                    logger.error("Unexpected error dispatching reset email to %s: %s", clean_email, type(exc).__name__)
            else:
                logger.error("Failed to generate password reset token for %s", clean_email)
    else:
        logger.info("Password reset requested for non-existent email (silently ignoring)")

    return {
        "success": True,
        "message": "If this email address is registered, password reset instructions have been prepared.",
    }


@router.post("/reset-password")
async def reset_password(req: PasswordResetConfirmRequest) -> Dict[str, Any]:
    """Confirm password reset with new strong password."""
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
    updated = update_user_password(email, new_hash)
    if not updated:
        logger.error("Failed to update password in database for %s during password reset", email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password. Please request a new reset link and try again.",
        )

    log_activity(
        action="password_reset_completed",
        user_id=user.get("id"),
        user_email=email,
    )

    return {"success": True, "message": "Password updated successfully. You can now log in with your new credentials."}
