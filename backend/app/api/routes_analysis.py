"""Exploratory data analysis, time-series, and market activity API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
import pandas as pd

from app.auth import get_current_user
from app.schemas import MarketOverviewRequest, SocialEngagementRequest, TimeSeriesAnalysisRequest
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["Analytics & Ingestion"])

# In-memory session cache per user for fast analytical querying
_USER_ACTIVE_DF: Dict[str, pd.DataFrame] = {}


def get_user_dataframe(user_email: str) -> pd.DataFrame:
    """Retrieve the currently active dataset for this user session or fall back to demo data."""
    if user_email in _USER_ACTIVE_DF and not _USER_ACTIVE_DF[user_email].empty:
        return _USER_ACTIVE_DF[user_email]

    # Check PipelineService for active/restored dataset
    try:
        from app.services.pipeline_service import PipelineService
        session = PipelineService.get_active_session(user_email)
        df = session.get("dataframe")
        if df is not None and not df.empty:
            _USER_ACTIVE_DF[user_email] = df
            return df
    except Exception:
        pass

    # Default to synthetic educational dataset
    df = AnalysisService.get_demo_dataset(n_rows=160)
    _USER_ACTIVE_DF[user_email] = df
    return df


@router.post("/pipeline/upload-and-analyze")
async def pipeline_upload_and_analyze(
    file: UploadFile = File(...),
    project_name: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Execute complete automated 9-step data analysis pipeline on an uploaded dataset."""
    from app.services.pipeline_service import PipelineService

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        result = PipelineService.process_and_analyze_dataset(
            file_bytes=file_bytes,
            filename=file.filename or "uploaded_dataset.csv",
            user_email=user["email"],
            project_name=project_name,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis pipeline failed: {exc}",
        )


@router.get("/active-dataset")
async def get_active_dataset_metadata(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve metadata and analytical statuses for the user's currently active dataset."""
    from app.services.pipeline_service import PipelineService

    session = PipelineService.get_active_session(user["email"])
    bundle = session.get("bundle") or {}
    df = session.get("dataframe")
    rows_count = len(df) if df is not None else 0
    cols_count = len(df.columns) if df is not None else 0

    return {
        "success": True,
        "project_id": session.get("project_id"),
        "dataset_name": session.get("dataset_name", "Active Dataset"),
        "rows_count": rows_count,
        "columns_count": cols_count,
        "columns": list(df.columns) if df is not None else [],
        "features_detected": bundle.get("features_detected", {}),
        "module_statuses": bundle.get("module_statuses", {}),
        "warnings": bundle.get("warnings", []),
        "updated_at": session.get("updated_at"),
    }


@router.get("/active-results/{module_name}")
async def get_active_module_results(
    module_name: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve precomputed analytical results for a specific dashboard module."""
    from app.services.pipeline_service import PipelineService

    session = PipelineService.get_active_session(user["email"])
    bundle = session.get("bundle") or {}
    dataset_name = session.get("dataset_name", "Active Dataset")

    normalized_module = module_name.lower().replace("-", "_")

    if normalized_module in ("price_trends", "price_trends_prediction"):
        mod_data = bundle.get("price_trends") or {}
        return {
            "success": True,
            "dataset_name": dataset_name,
            "features_detected": bundle.get("features_detected", {}),
            **mod_data,
        }

    if normalized_module in ("market_activity", "market_activity_tiers"):
        mod_data = bundle.get("market_activity") or {}
        return {
            "success": True,
            "dataset_name": dataset_name,
            "features_detected": bundle.get("features_detected", {}),
            **mod_data,
        }

    if normalized_module in ("social_engagement", "social_sentiment"):
        mod_data = bundle.get("social_engagement") or {}
        return {
            "success": True,
            "dataset_name": dataset_name,
            "features_detected": bundle.get("features_detected", {}),
            **mod_data,
        }

    if normalized_module in ("marketplace_hub", "marketplace"):
        mod_data = bundle.get("marketplace_hub") or {}
        return {
            "success": True,
            "dataset_name": dataset_name,
            **mod_data,
        }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown module '{module_name}'. Valid modules: price-trends, market-activity, social-engagement, marketplace-hub.",
    )


@router.get("/dataset/demo")
async def load_demo_dataset(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Load verified educational demo dataset into user's active session."""
    df = AnalysisService.get_demo_dataset(n_rows=160)
    _USER_ACTIVE_DF[user["email"]] = df
    return {
        "success": True,
        "message": "Demo dataset loaded successfully.",
        "rows": len(df),
        "columns": list(df.columns),
        "preview": df.head(10).to_dict(orient="records"),
    }


@router.post("/dataset/upload")
async def upload_single_dataset(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Upload and clean a single dataset (CSV, Excel, JSON, Parquet)."""
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        cleaned_df, meta = AnalysisService.process_file_upload(file_bytes, file.filename or "upload.csv")
        _USER_ACTIVE_DF[user["email"]] = cleaned_df
        return {
            "success": True,
            "metadata": meta,
            "preview": cleaned_df.head(10).to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process dataset: {exc}",
        )


@router.post("/dataset/join-upload")
async def upload_and_join_datasets(
    market_file: UploadFile = File(...),
    social_file: UploadFile = File(...),
    market_key: str = Form(...),
    social_key: str = Form(...),
    join_type: str = Form("inner"),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Upload separate market and social engagement files, validate join keys, and merge."""
    m_bytes = await market_file.read()
    s_bytes = await social_file.read()

    try:
        merged_df, diag = AnalysisService.join_datasets(
            m_bytes, market_file.filename or "market.csv",
            s_bytes, social_file.filename or "social.csv",
            market_key=market_key, social_key=social_key, how=join_type,
        )
        _USER_ACTIVE_DF[user["email"]] = merged_df
        return {
            "success": True,
            "diagnostics": diag,
            "rows": len(merged_df),
            "columns": list(merged_df.columns),
            "preview": merged_df.head(10).to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Join failed: {exc}",
        )


@router.post("/market-activity/overview")
async def get_market_overview(
    req: MarketOverviewRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Section 2: High-level market KPIs, volume distributions, and collection metrics."""
    df = get_user_dataframe(user["email"])
    kpis = AnalysisService.get_market_kpis(
        df,
        date_col=req.date_column,
        price_col=req.price_column,
        sales_col=req.sales_column,
        collection_col=req.collection_column,
    )
    return {"success": True, "kpis": kpis}


@router.post("/price-trends/time-series")
async def get_price_trends(
    req: TimeSeriesAnalysisRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Section 1: Time-series historical price trends, rolling averages, and volume."""
    df = get_user_dataframe(user["email"])
    series = AnalysisService.get_time_series_data(
        df,
        date_col=req.date_column,
        price_col=req.price_column,
        sales_col=req.sales_column,
        freq=req.resample_freq,
    )
    from app.core.nft_analysis import infer_column, parse_numeric
    p_col = req.price_column or infer_column(df, "price")
    stats = None
    if p_col and p_col in df.columns:
        prices = parse_numeric(df[p_col]).dropna()
        stats = {
            "mean_price": float(prices.mean()) if not prices.empty else 0.0,
            "max_price": float(prices.max()) if not prices.empty else 0.0,
            "min_price": float(prices.min()) if not prices.empty else 0.0,
            "price_std": float(prices.std()) if len(prices) > 1 else 0.0,
            "data_points": len(series),
        }
    return {
        "success": True,
        "time_series": series,
        "data": series,
        "stats": stats,
    }


@router.post("/social-engagement")
async def get_social_engagement(
    req: SocialEngagementRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Section 3: Social engagement correlation matrices, top signals, and scatter trends."""
    df = get_user_dataframe(user["email"])
    res = AnalysisService.get_social_engagement_data(
        df,
        price_col=req.price_column,
        social_cols=req.social_columns,
    )
    return {"success": True, "social_analysis": res}
