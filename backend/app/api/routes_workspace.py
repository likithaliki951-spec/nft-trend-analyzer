"""Persistent user workspace, saved project management, and session restoration."""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
import pandas as pd

from app.api.routes_analysis import _USER_ACTIVE_DF, get_user_dataframe
from app.auth import get_current_user
from app.schemas import ProjectSummaryResponse, SaveProjectRequest
from app.services.storage_service import StorageService

router = APIRouter(prefix="/workspace", tags=["Workspace & History"])


@router.get("/projects", response_model=List[ProjectSummaryResponse])
async def list_user_projects(user: Dict[str, Any] = Depends(get_current_user)) -> List[ProjectSummaryResponse]:
    """List all saved research projects belonging strictly to the authenticated user."""
    projects = StorageService.list_projects(user["email"])
    return [ProjectSummaryResponse(**p) for p in projects]


@router.post("/projects")
async def save_user_project(
    req: SaveProjectRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Snapshot and save active analysis, metrics, and dataset to persistent storage."""
    df = get_user_dataframe(user["email"])
    if req.dataframe_records:
        df = pd.DataFrame(req.dataframe_records)

    success, result = StorageService.save_project(
        user_email=user["email"],
        project_name=req.project_name,
        dataset_name=req.dataset_name,
        analysis_type=req.analysis_type,
        summary_json=req.summary_json,
        dataframe=df,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save project: {result}",
        )

    return {"success": True, "project_id": result, "message": "Project saved successfully to persistent workspace."}


@router.get("/projects/{project_id}")
async def reopen_user_project(
    project_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Reopen a saved project and restore its dataset into active session with strict ownership verification."""
    project = StorageService.get_project(project_id, user["email"])
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied.",
        )

    # Reload dataset into active memory session
    reloaded_df, msg = StorageService.load_project_dataframe(project_id, user["email"])
    if reloaded_df is not None:
        _USER_ACTIVE_DF[user["email"]] = reloaded_df
        try:
            from app.services.pipeline_service import PipelineService
            PipelineService.set_active_project(project_id, user["email"])
        except Exception:
            pass
    elif project.get("storage_path") and project.get("storage_path") != "metadata_only":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to restore project dataset from persistent storage: {msg}. Please check your storage connectivity.",
        )

    return {
        "success": True,
        "project": project,
        "dataset_restored": reloaded_df is not None,
        "storage_status": msg,
        "message": f"Successfully reopened '{project.get('project_name')}' into workspace.",
    }


@router.post("/select-active/{project_id}")
async def select_active_workspace_project(
    project_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Select a saved project and immediately activate its analysis results across all four modules."""
    from app.services.pipeline_service import PipelineService

    ok, msg, bundle = PipelineService.set_active_project(project_id, user["email"])
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    return {
        "success": True,
        "status": "active",
        "message": msg,
        "project_id": project_id,
        "dataset_name": bundle.get("dataset_name") if bundle else "Activated Dataset",
        "total_records": bundle.get("rows_count") if bundle else 0,
        "module_statuses": bundle.get("module_statuses") if bundle else {},
    }


@router.delete("/projects/{project_id}")
async def delete_user_project(
    project_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete a saved project with cross-user isolation protection."""
    success, msg = StorageService.delete_project(project_id, user["email"])
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return {"success": True, "message": msg}
