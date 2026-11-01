"""Administrator command console, platform telemetry, and user management."""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends

from app.auth import get_all_users_admin, require_admin
from app.schemas import AdminTelemetryResponse, UserResponse
from app.services.storage_service import StorageService

router = APIRouter(prefix="/admin", tags=["Administrator Console"])


@router.get("/telemetry", response_model=AdminTelemetryResponse)
async def get_platform_telemetry(admin_user: Dict[str, Any] = Depends(require_admin)) -> AdminTelemetryResponse:
    """Administrator platform telemetry and health diagnostics."""
    metrics = StorageService.get_system_metrics()
    return AdminTelemetryResponse(**metrics)


@router.get("/users", response_model=List[UserResponse])
async def list_registered_users(admin_user: Dict[str, Any] = Depends(require_admin)) -> List[UserResponse]:
    """Administrator user directory (without exposing password hashes)."""
    users = get_all_users_admin()
    return [
        UserResponse(
            id=str(u.get("id")),
            email=u.get("email"),
            name=u.get("name", u.get("email")),
            role=u.get("role", "analyst"),
            created_at=u.get("created_at"),
        )
        for u in users
    ]
