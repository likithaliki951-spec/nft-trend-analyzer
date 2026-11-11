"""Administrator command console, RBAC approvals, user directory, and platform activity."""

from __future__ import annotations

import datetime
import logging
import secrets
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status as http_status

logger = logging.getLogger(__name__)

from app.auth import (
    count_active_admins,
    create_access_token,
    create_user,
    get_all_users_admin,
    get_dashboard_stats,
    get_recent_activity,
    get_user_by_email,
    get_user_by_id,
    has_active_admin,
    has_admin_been_initialized,
    hash_password,
    initialize_first_admin,
    log_activity,
    require_admin,
    update_user_status,
    update_user_status_conditional,
    validate_password_strength,
)
from app.config import settings
from app.schemas import (
    AdminActivityItem,
    AdminApprovalItem,
    AdminDashboardStatsResponse,
    AdminSetupInitRequest,
    AdminStatusUpdateRequest,
    AdminTelemetryResponse,
    AuthTokenResponse,
    UserResponse,
)
from app.services.storage_service import StorageService

router = APIRouter(prefix="/admin", tags=["Administrator Console"])


# ==============================================================================
# First-Admin One-Time Secure Initialization
# ==============================================================================

@router.post("/setup/initialize", response_model=AuthTokenResponse)
async def initialize_master_admin(req: AdminSetupInitRequest, request: Request) -> AuthTokenResponse:
    """Secure one-time initial setup to create the first platform administrator.

    Security Rules:
    - Requires a cryptographically strong, non-empty ADMIN_SETUP_TOKEN.
    - Permanently becomes UNAVAILABLE after the first active administrator exists.
    - Password policy strictly enforced.
    - Created administrator receives status 'active' and verified email.
    """
    configured_token = settings.ADMIN_SETUP_TOKEN
    if not configured_token:
        # If running in production without ADMIN_SETUP_TOKEN configured, fail closed
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Administrator setup token (ADMIN_SETUP_TOKEN) is not configured in the environment.",
        )

    if not secrets.compare_digest(req.setup_token, configured_token):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Invalid administrator setup token.",
        )

    # Check whether an administrator has already been initialized (fail closed on DB error)
    try:
        admin_already_exists = has_admin_been_initialized()
    except Exception as exc:
        logger.error("Database error during administrator verification pre-check: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    if admin_already_exists:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Initial administrator setup has already been completed and is permanently disabled.",
        )

    clean_email = req.email.strip().lower()
    clean_name = req.name.strip()

    if req.password != req.password_confirm:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Password and confirmation password do not match.",
        )

    is_valid, msg = validate_password_strength(req.password, email=clean_email, name=clean_name)
    if not is_valid:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=msg)

    pwd_hash = hash_password(req.password)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        success, result = initialize_first_admin(
            email=clean_email,
            name=clean_name,
            password_hash=pwd_hash,
        )
    except Exception as exc:
        logger.error("Database error executing administrator initialization: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable during administrator initialization.",
        )

    if not success:
        res_lower = result.lower()
        if "already" in res_lower:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Initial administrator setup has already been completed and is permanently disabled.",
            )
        if "exists" in res_lower and "email" in res_lower:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists.",
            )
        # For all database, network, RPC, or unexpected internal failures, log on server and return generic HTTP 503
        logger.error("Database or service failure during administrator initialization: %s", result)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable during administrator initialization.",
        )

    user_data = {
        "id": result,
        "email": clean_email,
        "name": clean_name,
        "role": "admin",
        "account_status": "active",
        "email_verified": True,
        "approved_by": "initial_setup",
        "approved_at": now_iso,
        "created_at": now_iso,
    }

    client_ip = request.client.host if request.client else "127.0.0.1"
    log_activity(
        action="admin_initialized",
        user_id=result,
        user_email=clean_email,
        details={"name": clean_name, "setup_method": "one_time_token"},
        ip_address=client_ip,
    )

    token = create_access_token(user_data)
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user_data),
    )


# ==============================================================================
# Admin Approvals Management
# ==============================================================================

@router.get("/approvals", response_model=List[AdminApprovalItem])
async def list_pending_admin_requests(
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> List[AdminApprovalItem]:
    """Retrieve all pending administrator registration requests awaiting review."""
    try:
        pending_users = get_all_users_admin(status_filter="pending", role_filter="admin")
    except Exception as exc:
        logger.error("Database error retrieving pending administrator requests: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )
    return [
        AdminApprovalItem(
            id=str(u.get("id")),
            email=u.get("email"),
            name=u.get("name", u.get("email")),
            role="admin",
            account_status="pending",
            email_verified=bool(u.get("email_verified", False)),
            created_at=str(u.get("created_at")),
        )
        for u in pending_users
    ]


@router.post("/approvals/{request_id}/approve")
async def approve_admin_request(
    request_id: str,
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Approve a pending administrator application.

    Enforces:
    - Caller must be an active administrator.
    - Target user must exist and be in 'pending' status.
    - Target applicant's email address MUST be verified before approval.
    """
    try:
        target_user = get_user_by_id(request_id)
        if not target_user:
            # Fallback by email if ID not matched
            target_user = get_user_by_email(request_id)
    except Exception as exc:
        logger.error("Database error retrieving user during administrator approval: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    if not target_user:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Administrator application not found.",
        )

    if target_user.get("role") != "admin" or target_user.get("account_status") != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Only pending administrator requests can be approved.",
        )

    # SEC rule: Unverified admin request cannot be approved
    if not target_user.get("email_verified"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve administrator request: applicant's email address has not been verified.",
        )

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        ok = update_user_status_conditional(
            user_id=target_user["id"],
            new_status="active",
            expected_status="pending",
            expected_role="admin",
            require_email_verified=True,
            approved_by=admin_user["id"],
            approved_at=now_iso,
        )
    except Exception as exc:
        logger.error("Database error executing conditional status update during administrator approval: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Failed to approve administrator request: applicant must be pending, email-verified, and hold admin role.",
        )

    log_activity(
        action="admin_approved",
        user_id=target_user["id"],
        user_email=target_user["email"],
        details={"approved_by": admin_user["email"]},
    )

    return {
        "success": True,
        "message": f"Administrator application for {target_user['email']} has been approved.",
        "user_id": target_user["id"],
        "status": "active",
    }


@router.post("/approvals/{request_id}/reject")
async def reject_admin_request(
    request_id: str,
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Reject a pending administrator application."""
    try:
        target_user = get_user_by_id(request_id)
        if not target_user:
            target_user = get_user_by_email(request_id)
    except Exception as exc:
        logger.error("Database error retrieving user during administrator rejection: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    if not target_user:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Administrator application not found.",
        )

    if target_user.get("role") != "admin" or target_user.get("account_status") != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Only pending administrator requests can be rejected.",
        )

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        ok = update_user_status_conditional(
            user_id=target_user["id"],
            new_status="rejected",
            expected_status="pending",
            expected_role="admin",
            approved_by=admin_user["id"],
            approved_at=now_iso,
        )
    except Exception as exc:
        logger.error("Database error executing conditional status update during administrator rejection: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Failed to reject administrator application: applicant must hold admin role and be in pending status.",
        )

    log_activity(
        action="admin_rejected",
        user_id=target_user["id"],
        user_email=target_user["email"],
        details={"rejected_by": admin_user["email"]},
    )

    return {
        "success": True,
        "message": f"Administrator application for {target_user['email']} has been rejected.",
        "user_id": target_user["id"],
        "status": "rejected",
    }


# ==============================================================================
# User Management & Directory
# ==============================================================================

@router.get("/users", response_model=List[UserResponse])
async def list_registered_users(
    status: Optional[str] = Query(None, description="Filter by account_status: active, pending, suspended"),
    role: Optional[str] = Query(None, description="Filter by role: user, admin"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> List[UserResponse]:
    """Administrator user directory with status filters and search (excluding password hashes)."""
    try:
        users = get_all_users_admin(status_filter=status, role_filter=role, search=search)
    except Exception as exc:
        logger.error("Database error fetching user directory: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )
    return [
        UserResponse(
            id=str(u.get("id")),
            email=u.get("email"),
            name=u.get("name", u.get("email")),
            role=u.get("role", "user"),
            account_status=u.get("account_status", "active"),
            email_verified=bool(u.get("email_verified", True)),
            created_at=u.get("created_at"),
            approved_at=u.get("approved_at"),
            approved_by=u.get("approved_by"),
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_details(
    user_id: str,
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> UserResponse:
    """Retrieve administrative metadata for a specific user.

    Does not disclose password hashes, reset tokens, or private user datasets.
    """
    try:
        user = get_user_by_id(user_id)
        if not user:
            user = get_user_by_email(user_id)
    except Exception as exc:
        logger.error("Database error fetching user details: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    if not user:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    return UserResponse(
        id=str(user.get("id")),
        email=user.get("email"),
        name=user.get("name", user.get("email")),
        role=user.get("role", "user"),
        account_status=user.get("account_status", "active"),
        email_verified=bool(user.get("email_verified", True)),
        created_at=user.get("created_at"),
        approved_at=user.get("approved_at"),
        approved_by=user.get("approved_by"),
    )


@router.patch("/users/{user_id}/status")
async def update_account_status(
    user_id: str,
    req: AdminStatusUpdateRequest,
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Suspend or re-activate a user or administrator account.

    Enforces:
    - Target status must be 'active' or 'suspended'.
    - An administrator cannot suspend their own active account (lockout prevention).
    """
    target_status = req.status.strip().lower()
    if target_status not in ("active", "suspended"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Status must be either 'active' or 'suspended'.",
        )

    try:
        target_user = get_user_by_id(user_id)
        if not target_user:
            target_user = get_user_by_email(user_id)
    except Exception as exc:
        logger.error("Database error retrieving user for status update: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    if not target_user:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    # Lockout prevention: self-suspension
    if (str(target_user.get("id")) == str(admin_user.get("id")) or target_user.get("email") == admin_user.get("email")) and target_status == "suspended":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Self-suspension is prohibited to prevent administrator lockout.",
        )

    # Lockout prevention: last active administrator
    if target_user.get("role") == "admin" and target_status == "suspended" and target_user.get("account_status") == "active":
        try:
            active_admin_count = count_active_admins()
        except Exception as exc:
            logger.error("Database error checking active administrator quorum: %s", exc)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable while checking administrator quorum.",
            )
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Cannot suspend the last active administrator. At least one active administrator must remain.",
            )

    try:
        ok = update_user_status(target_user["id"], target_status)
    except Exception as exc:
        logger.error("Database error updating account status: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update account status.",
        )

    log_activity(
        action=f"user_{target_status}",
        user_id=target_user["id"],
        user_email=target_user["email"],
        details={"new_status": target_status, "changed_by": admin_user["email"]},
    )

    return {
        "success": True,
        "message": f"Account {target_user['email']} status updated to {target_status}.",
        "user_id": target_user["id"],
        "account_status": target_status,
    }


# ==============================================================================
# Platform Monitoring & Telemetry
# ==============================================================================

@router.get("/dashboard/stats", response_model=AdminDashboardStatsResponse)
async def get_admin_dashboard_stats(
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> AdminDashboardStatsResponse:
    """Retrieve accurate database counts and metrics for the administrator dashboard."""
    try:
        stats = get_dashboard_stats()
    except Exception as exc:
        logger.error("Database error fetching admin dashboard stats: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    return AdminDashboardStatsResponse(
        total_registered_users=stats["total_registered_users"],
        active_users=stats["active_users"],
        pending_users=stats["pending_users"],
        suspended_users=stats["suspended_users"],
        approved_administrators=stats["approved_administrators"],
        pending_admin_requests=stats["pending_admin_requests"],
        recent_activity_count=stats["recent_activity_count"],
        recent_registrations=[
            UserResponse(
                id=str(u.get("id")),
                email=u.get("email"),
                name=u.get("name", u.get("email")),
                role=u.get("role", "user"),
                account_status=u.get("account_status", "active"),
                email_verified=bool(u.get("email_verified", True)),
                created_at=u.get("created_at"),
            )
            for u in stats.get("recent_registrations", [])
        ],
    )


@router.get("/activity", response_model=List[AdminActivityItem])
async def list_admin_activity(
    limit: int = Query(50, ge=1, le=200),
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> List[AdminActivityItem]:
    """Retrieve audit activity history for platform monitoring."""
    try:
        events = get_recent_activity(limit=limit)
    except Exception as exc:
        logger.error("Database error fetching admin activity log: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please retry later.",
        )

    return [
        AdminActivityItem(
            id=str(e.get("id")),
            user_id=e.get("user_id"),
            user_email=e.get("user_email"),
            action=e.get("action", ""),
            details=e.get("details", {}) if isinstance(e.get("details"), dict) else {},
            ip_address=e.get("ip_address"),
            created_at=str(e.get("created_at")),
        )
        for e in events
    ]


@router.get("/telemetry", response_model=AdminTelemetryResponse)
async def get_platform_telemetry(admin_user: Dict[str, Any] = Depends(require_admin)) -> AdminTelemetryResponse:
    """Administrator platform telemetry and health diagnostics."""
    try:
        metrics = StorageService.get_system_metrics()
    except Exception as exc:
        logger.error("System error fetching platform telemetry: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service telemetry unavailable. Please retry later.",
        )
    return AdminTelemetryResponse(**metrics)
