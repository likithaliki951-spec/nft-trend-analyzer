"""Pydantic schemas for request validation and API responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# Authentication Schemas
# ==============================================================================

class UserRegisterRequest(BaseModel):
    email: str
    name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=12)
    password_confirm: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=12)
    new_password_confirm: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: Optional[str] = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ==============================================================================
# Section 1: Price Trends & Prediction Schemas
# ==============================================================================

class TimeSeriesAnalysisRequest(BaseModel):
    date_column: Optional[str] = None
    price_column: Optional[str] = None
    sales_column: Optional[str] = None
    resample_freq: str = "D"  # D = daily, W = weekly, M = monthly


class MLTrainRequest(BaseModel):
    date_column: Optional[str] = None
    target_column: Optional[str] = None
    use_pca: bool = False
    target_pca_components: int = 60


class PCADiagnosticsResponse(BaseModel):
    enabled: bool
    input_features_count: int = 0
    retained_components: int = 0
    total_explained_variance: float = 0.0
    explained_variance_ratio: List[float] = []
    cumulative_variance_ratio: List[float] = []
    component_names: List[str] = []
    status_message: str = ""


# ==============================================================================
# Section 2: Market Activity Schemas
# ==============================================================================

class MarketOverviewRequest(BaseModel):
    date_column: Optional[str] = None
    price_column: Optional[str] = None
    sales_column: Optional[str] = None
    collection_column: Optional[str] = None


class ValuationClassifiersRequest(BaseModel):
    feature_columns: Optional[List[str]] = None
    target_column: Optional[str] = None
    custom_bands: Optional[List[float]] = None  # e.g., [0.05, 0.5, 2.5]


class SingleValuationRequest(BaseModel):
    features: Dict[str, float]
    model_name: str = "random_forest"  # random_forest, logistic_regression, svm


# ==============================================================================
# Section 3: Social Engagement Schemas
# ==============================================================================

class SocialEngagementRequest(BaseModel):
    price_column: Optional[str] = None
    social_columns: Optional[List[str]] = None


# ==============================================================================
# Section 4: Marketplace Hub Schemas
# ==============================================================================

class CurrencyConvertRequest(BaseModel):
    eth_amount: float = Field(..., ge=0)


class CollectionStatsRequest(BaseModel):
    slug: str = Field(..., min_length=2)


# ==============================================================================
# Workspace & Persistent Projects Schemas
# ==============================================================================

class SaveProjectRequest(BaseModel):
    project_name: str = Field(..., min_length=2, max_length=150)
    dataset_name: str
    analysis_type: str = "Unified Analysis"
    summary_json: Dict[str, Any] = {}
    dataframe_records: Optional[List[Dict[str, Any]]] = None  # If passing processed data directly


class ProjectSummaryResponse(BaseModel):
    id: str
    user_email: str
    project_name: str
    dataset_name: str
    analysis_type: str
    summary_json: Dict[str, Any]
    storage_path: str
    created_at: str
    updated_at: str


# ==============================================================================
# Admin Schemas
# ==============================================================================

class AdminTelemetryResponse(BaseModel):
    active_users_count: int
    total_projects_saved: int
    storage_size_bytes: int
    storage_size_formatted: str
    database_backend: str
    database_status: str
    server_time: str
    platform_info: str
    python_version: str


# ==============================================================================
# Report Export Schemas
# ==============================================================================

class ReportExportRequest(BaseModel):
    format: str = Field("pdf", description="Export format: pdf, json, docx, or xlsx")
    scope: str = Field("complete", description="Module scope: complete, price_trends, market_activity, social_engagement, marketplace_hub, ml_results, or dataset_summary")
    project_id: Optional[str] = Field(None, description="Optional ID of saved project to export instead of current active session")
    custom_title: Optional[str] = Field(None, description="Optional custom title for the report")
    include_charts: bool = Field(True, description="Whether to generate and embed visual chart figures into supported export formats")
