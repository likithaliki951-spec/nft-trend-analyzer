"""FastAPI application entrypoint for NFT Trend Analyzer."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend root is in sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_admin import router as admin_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_auth import router as auth_router
from app.api.routes_marketplace import router as marketplace_router
from app.api.routes_ml import router as ml_router
from app.api.routes_workspace import router as workspace_router
from app.config import settings

# SEC-07: Disable interactive API docs and OpenAPI schema in production
docs_url = None if settings.IS_PRODUCTION else "/docs"
redoc_url = None if settings.IS_PRODUCTION else "/redoc"
openapi_url = None if settings.IS_PRODUCTION else "/openapi.json"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise REST API for NFT Trend Analysis, Predictive ML, and Market Intelligence.",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

# SEC-03: Restricted CORS Middleware
# In production, only accept explicitly configured production origins. Reject localhost and arbitrary vercel domains.
if settings.IS_PRODUCTION:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
else:
    # Development: allow localhost development ports and dev regex
    dev_regex = r"^http:\/\/localhost(:\d+)?$|^http:\/\/127\.0\.0\.1(:\d+)?$"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=dev_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

# Mount API Routers under /api/v1
api_v1 = FastAPI(
    title="NFT Trend Analyzer v1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
api_v1.include_router(auth_router)
api_v1.include_router(analysis_router)
api_v1.include_router(ml_router)
api_v1.include_router(marketplace_router)
api_v1.include_router(workspace_router)
api_v1.include_router(admin_router)

app.mount(settings.API_V1_PREFIX, api_v1)


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """System health check endpoint for cloud load balancers and deployment monitors.

    SEC-08: In production, return only minimal status without disclosing bucket names,
    internal paths, connection telemetry, or server architecture.
    """
    if settings.IS_PRODUCTION:
        return JSONResponse(content={"status": "healthy"})

    return JSONResponse(
        content={
            "status": "healthy",
            "version": settings.VERSION,
            "supabase_connected": settings.has_supabase(),
            "environment": settings.ENV,
            "storage_bucket": settings.SUPABASE_STORAGE_BUCKET,
        }
    )


@app.get("/", tags=["Root"])
async def root_endpoint() -> JSONResponse:
    """Root metadata endpoint."""
    if settings.IS_PRODUCTION:
        return JSONResponse(content={"name": settings.PROJECT_NAME, "status": "active"})

    return JSONResponse(
        content={
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
            "api_prefix": settings.API_V1_PREFIX,
        }
    )
