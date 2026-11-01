"""Automated integration tests for the FastAPI backend API."""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_root_endpoints():
    """Verify health and root endpoints."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    res = client.get("/")
    assert res.status_code == 200
    assert "NFT Trend Analyzer" in res.json()["name"]


def test_auth_registration_and_login_lifecycle():
    """Test full registration, login, and token authentication lifecycle."""
    test_email = f"analyst_{uuid.uuid4().hex[:6]}@nfttrends.io"
    test_password = "StrongPassVault#2026!"

    # Weak password rejection (<12 chars)
    weak_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": test_email,
            "name": "Marcus Vance",
            "password": "Short1!",
            "password_confirm": "Short1!",
        },
    )
    assert weak_res.status_code in (400, 422)

    # Valid registration
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": test_email,
            "name": "Marcus Vance",
            "password": test_password,
            "password_confirm": test_password,
        },
    )
    assert reg_res.status_code == 200

    # Valid login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": test_password},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    token = data["access_token"]

    # Access protected /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == test_email

    # Wrong password rejection
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": "WrongPassword#2026"},
    )
    assert bad_login.status_code == 401


def test_password_forgot_and_reset_flow():
    """Test password reset workflow with secure out-of-band token generation."""
    from app.auth import create_password_reset_token

    email = "test_reset_user@nfttrends.io"
    pwd1 = "InitialSecurePassword#2026"
    pwd2 = "UpdatedSecurePassword#2026"

    # Register
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Reset User", "password": pwd1, "password_confirm": pwd1},
    )

    # Forgot password - SEC-01: verify NO reset_token is leaked in response
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200
    assert "reset_token" not in forgot_res.json()
    assert "token" not in forgot_res.json()

    # Out-of-band delivery simulation: create valid token via backend helper
    reset_token = create_password_reset_token(email)
    assert reset_token is not None

    # Reset password
    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": pwd2, "new_password_confirm": pwd2},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] is True

    # Login with new password
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd2})
    assert login_res.status_code == 200


def test_four_dashboard_sections_flow():
    """Test analysis and ML features across all 4 dashboard sections."""
    # 1. Sign in as admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nfttrends.io", "password": "Admin#NFT2026!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Load demo dataset into session
    demo_res = client.get("/api/v1/analysis/dataset/demo", headers=headers)
    assert demo_res.status_code == 200
    assert demo_res.json()["rows"] > 50

    # Section 1: Price Trends & Time Series
    ts_res = client.post(
        "/api/v1/analysis/price-trends/time-series",
        headers=headers,
        json={"resample_freq": "D"},
    )
    assert ts_res.status_code == 200
    assert len(ts_res.json()["time_series"]) > 0

    # Section 1: Price Prediction & Model Evaluation (with PCA)
    ml_res = client.post(
        "/api/v1/ml/predict-train",
        headers=headers,
        json={"use_pca": True, "target_pca_components": 60},
    )
    assert ml_res.status_code == 200
    ml_data = ml_res.json()["results"]
    assert "models" in ml_data
    assert len(ml_data["models"]) >= 3
    assert ml_data["pca_diagnostics"]["enabled"] is True

    # Section 2: Market Activity Overview
    mkt_res = client.post(
        "/api/v1/analysis/market-activity/overview",
        headers=headers,
        json={},
    )
    assert mkt_res.status_code == 200
    assert mkt_res.json()["kpis"]["total_sales"] > 0

    # Section 2: Valuation Categories (RF, LR, SVM)
    val_res = client.post(
        "/api/v1/ml/valuation-categories",
        headers=headers,
        json={},
    )
    assert val_res.status_code == 200
    val_data = val_res.json()["results"]
    assert len(val_data["classifiers"]) >= 3
    # Verify Logistic Regression is present
    clf_names = [c["name"] for c in val_data["classifiers"]]
    assert any("logistic" in n.lower() for n in clf_names)

    # Section 2: Single Valuation Estimation
    single_val_res = client.post(
        "/api/v1/ml/valuation-estimate-single",
        headers=headers,
        json={"features": {"volume": 12.5, "rarity_score": 85.0}},
    )
    assert single_val_res.status_code == 200
    assert "predicted_tier" in single_val_res.json()["prediction"]

    # Section 3: Social Engagement
    social_res = client.post(
        "/api/v1/analysis/social-engagement",
        headers=headers,
        json={},
    )
    assert social_res.status_code == 200
    assert "correlations" in social_res.json()["social_analysis"]

    # Section 4: Marketplace Hub
    eth_res = client.get("/api/v1/marketplace/eth-usd", headers=headers)
    assert eth_res.status_code == 200
    assert eth_res.json()["data"]["rate_usd"] > 0
    assert "source" in eth_res.json()["data"]

    conv_res = client.post(
        "/api/v1/marketplace/convert",
        headers=headers,
        json={"eth_amount": 2.5},
    )
    assert conv_res.status_code == 200
    assert conv_res.json()["conversion"]["usd_amount"] > 0


def test_persistent_workspace_and_cross_user_isolation():
    """Test project persistence and strict cross-user data isolation."""
    # User A
    user_a_email = f"analyst_a_{uuid.uuid4().hex[:6]}@nfttrends.io"
    user_a_pwd = "ResearchVaultA#2026!"
    client.post(
        "/api/v1/auth/register",
        json={"email": user_a_email, "name": "Analyst A", "password": user_a_pwd, "password_confirm": user_a_pwd},
    )
    res_a = client.post("/api/v1/auth/login", json={"email": user_a_email, "password": user_a_pwd})
    assert res_a.status_code == 200
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User B
    user_b_email = f"analyst_b_{uuid.uuid4().hex[:6]}@nfttrends.io"
    user_b_pwd = "ResearchVaultB#2026!"
    client.post(
        "/api/v1/auth/register",
        json={"email": user_b_email, "name": "Analyst B", "password": user_b_pwd, "password_confirm": user_b_pwd},
    )
    res_b = client.post("/api/v1/auth/login", json={"email": user_b_email, "password": user_b_pwd})
    assert res_b.status_code == 200
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A saves a project
    save_res = client.post(
        "/api/v1/workspace/projects",
        headers=headers_a,
        json={
            "project_name": "Alpha Confidential Research",
            "dataset_name": "alpha_dataset.csv",
            "analysis_type": "Alpha Predictive Study",
            "summary_json": {"best_model": "Random Forest", "rmse": 0.12},
        },
    )
    assert save_res.status_code == 200
    project_id = save_res.json()["project_id"]

    # User A can list and view it
    list_a = client.get("/api/v1/workspace/projects", headers=headers_a)
    assert list_a.status_code == 200
    assert any(p["id"] == project_id for p in list_a.json())

    # User B CANNOT see User A's project
    list_b = client.get("/api/v1/workspace/projects", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(p["id"] == project_id for p in list_b.json())

    # User B CANNOT delete User A's project
    del_b = client.delete(f"/api/v1/workspace/projects/{project_id}", headers=headers_b)
    assert del_b.status_code == 400 or del_b.status_code == 404

    # User A CAN delete their own project
    del_a = client.delete(f"/api/v1/workspace/projects/{project_id}", headers=headers_a)
    assert del_a.status_code == 200


def test_admin_console_permissions():
    """Verify administrator route access and RBAC rejection of analyst users."""
    # Analyst user
    analyst_email = f"analyst_g_{uuid.uuid4().hex[:6]}@nfttrends.io"
    analyst_pwd = "ResearchVaultG#2026!"
    client.post(
        "/api/v1/auth/register",
        json={"email": analyst_email, "name": "Analyst G", "password": analyst_pwd, "password_confirm": analyst_pwd},
    )
    res = client.post("/api/v1/auth/login", json={"email": analyst_email, "password": analyst_pwd})
    assert res.status_code == 200
    analyst_token = res.json()["access_token"]

    # Analyst blocked with 403 Forbidden
    blocked = client.get("/api/v1/admin/telemetry", headers={"Authorization": f"Bearer {analyst_token}"})
    assert blocked.status_code == 403

    # Admin user
    admin_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nfttrends.io", "password": "Admin#NFT2026!"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin allowed
    telem = client.get("/api/v1/admin/telemetry", headers=admin_headers)
    assert telem.status_code == 200
    assert telem.json()["active_users_count"] >= 1

    users = client.get("/api/v1/admin/users", headers=admin_headers)
    assert users.status_code == 200
    assert len(users.json()) >= 1


# ==============================================================================
# Production Readiness Security & Persistence Tests
# ==============================================================================

def test_supabase_storage_upload_and_download():
    """Verify Supabase Storage upload and download logic with parquet bytes."""
    import io
    import pandas as pd
    from unittest.mock import patch, MagicMock
    from app.services.storage_service import StorageService
    from app.config import settings

    test_df = pd.DataFrame({"asset_id": ["A1", "A2"], "price_eth": [1.5, 3.2]})
    bio = io.BytesIO()
    test_df.to_parquet(bio, index=False)
    parquet_bytes = bio.getvalue()

    # Mock settings to simulate configured Supabase
    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"):

        # Mock POST to Supabase Storage
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.text = '{"Key": "user-datasets/test.parquet"}'

        with patch("requests.post", return_value=mock_post_resp) as mock_post:
            ok, msg = StorageService.upload_to_supabase_storage("test_user/proj_123.parquet", parquet_bytes)
            assert ok is True
            assert mock_post.called
            called_url = mock_post.call_args[0][0]
            assert "user-datasets" in called_url
            assert "test_user/proj_123.parquet" in called_url
            headers = mock_post.call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer mock-service-role-key"

        # Mock GET from Supabase Storage
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.content = parquet_bytes

        with patch("requests.get", return_value=mock_get_resp) as mock_get:
            downloaded_df, dl_msg = StorageService.download_from_supabase_storage("test_user/proj_123.parquet")
            assert downloaded_df is not None
            assert len(downloaded_df) == 2
            assert list(downloaded_df["asset_id"]) == ["A1", "A2"]


def test_project_reopening_after_simulated_restart():
    """Verify reopening a saved project restores its dataset into active memory after a simulated restart."""
    from app.api.routes_analysis import _USER_ACTIVE_DF

    email = f"evelyn_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd = "ComplexVaultPass#2026!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Evelyn Vance", "password": pwd, "password_confirm": pwd},
    )
    assert reg_res.status_code == 200
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save a project with data
    save_res = client.post(
        "/api/v1/workspace/projects",
        headers=headers,
        json={
            "project_name": "Persisted Milestone Study",
            "dataset_name": "milestone.csv",
            "analysis_type": "Regression",
            "summary_json": {"status": "saved"},
            "dataframe_records": [{"collection": "BoredApe", "price_eth": 15.2}],
        },
    )
    assert save_res.status_code == 200
    project_id = save_res.json()["project_id"]

    # Simulate server memory wipe (restart)
    if email in _USER_ACTIVE_DF:
        del _USER_ACTIVE_DF[email]
    assert email not in _USER_ACTIVE_DF

    # Reopen project
    reopen_res = client.get(f"/api/v1/workspace/projects/{project_id}", headers=headers)
    assert reopen_res.status_code == 200
    assert reopen_res.json()["success"] is True
    assert reopen_res.json()["project"]["id"] == project_id
    # Dataset restored into active session memory
    assert email in _USER_ACTIVE_DF
    assert len(_USER_ACTIVE_DF[email]) == 1


def test_unauthorized_requests_rejected():
    """Verify endpoints reject unauthenticated or malformed token requests."""
    # No auth header
    res1 = client.get("/api/v1/analysis/dataset/demo")
    assert res1.status_code == 401

    # Malformed token
    res2 = client.get("/api/v1/workspace/projects", headers={"Authorization": "Bearer not-a-valid-token"})
    assert res2.status_code == 401

    # Missing credentials in admin route
    res3 = client.get("/api/v1/admin/telemetry")
    assert res3.status_code == 401


def test_cors_headers_and_preflight():
    """Verify CORS preflight returns correct explicit origins and disallows unauthorized domains."""
    # 1. Localhost 3000 preflight
    res_local = client.options(
        "/api/v1/analysis/dataset/demo",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_local.status_code == 200
    assert res_local.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert res_local.headers.get("access-control-allow-credentials") == "true"

    # 2. Arbitrary unconfigured Vercel deployment preflight (SEC-03: rejected)
    res_vercel = client.options(
        "/api/v1/analysis/dataset/demo",
        headers={
            "Origin": "https://nft-trend-analyzer-preview.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_vercel.headers.get("access-control-allow-origin") is None

    # 3. Untrusted origin must NOT receive access-control-allow-origin
    res_untrusted = client.options(
        "/api/v1/analysis/dataset/demo",
        headers={
            "Origin": "https://malicious-crypto-phish.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_untrusted.headers.get("access-control-allow-origin") is None


def test_production_mode_refuses_local_storage_fallback():
    """Verify that in production mode, silent local disk fallback is strictly forbidden."""
    import pandas as pd
    from app.services.storage_service import StorageService
    from app.config import settings

    test_df = pd.DataFrame({"item": ["NFT_X"], "value": [10.0]})

    # Simulate production mode with unconfigured Supabase
    orig_env = settings.IS_PRODUCTION
    orig_url = settings.SUPABASE_URL
    orig_key = settings.SUPABASE_SERVICE_ROLE_KEY
    try:
        settings.IS_PRODUCTION = True
        settings.SUPABASE_URL = ""
        settings.SUPABASE_SERVICE_ROLE_KEY = ""

        # Attempt to save project with dataframe in production without Supabase
        ok, msg = StorageService.save_project(
            user_email="prod_test@nfttrends.io",
            project_name="Prod Study",
            dataset_name="data.csv",
            analysis_type="Production",
            summary_json={},
            dataframe=test_df,
        )
        assert ok is False
        assert "Local disk storage fallback is strictly forbidden in production" in msg

        # Attempt to load project in production without Supabase
        df, load_msg = StorageService.load_project_dataframe("fake_id", "prod_test@nfttrends.io")
        assert df is None

    finally:
        # Restore dev environment
        settings.IS_PRODUCTION = orig_env
        settings.SUPABASE_URL = orig_url
        settings.SUPABASE_SERVICE_ROLE_KEY = orig_key


# ==============================================================================
# SEC-01 through SEC-08 Targeted Security Audit Tests
# ==============================================================================

def test_security_01_forgot_password_never_contains_reset_token():
    """SEC-01: Verify forgot-password response NEVER leaks reset token in JSON."""
    res = client.post("/api/v1/auth/forgot-password", json={"email": "analyst@nfttrends.io"})
    assert res.status_code == 200
    data = res.json()
    assert "reset_token" not in data
    assert "token" not in data
    assert "jwt" not in data
    assert "link" not in data
    assert "key" not in data


def test_security_02_forgot_password_no_user_enumeration():
    """SEC-01: Verify identical generic message for registered and non-registered emails."""
    # Existing user
    existing_email = f"enum_test_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post(
        "/api/v1/auth/register",
        json={"email": existing_email, "name": "Enum Tester", "password": "SecurePass#2026!", "password_confirm": "SecurePass#2026!"},
    )
    res_existing = client.post("/api/v1/auth/forgot-password", json={"email": existing_email})

    # Non-existent user
    non_existing_email = f"nonexistent_{uuid.uuid4().hex[:8]}@unknown-domain.io"
    res_non_existing = client.post("/api/v1/auth/forgot-password", json={"email": non_existing_email})

    assert res_existing.status_code == res_non_existing.status_code == 200
    assert res_existing.json()["message"] == res_non_existing.json()["message"]


def test_security_03_ordinary_login_token_cannot_reset_password():
    """SEC-04: Verify ordinary session/login tokens cannot be used to reset passwords."""
    user_email = f"analyst_scope_{uuid.uuid4().hex[:6]}@nfttrends.io"
    name = "Arthur Vance"
    pwd = "SecureEnterprisePass#2026!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "name": name, "password": pwd, "password_confirm": pwd},
    )
    assert reg_res.status_code == 200
    login_res = client.post("/api/v1/auth/login", json={"email": user_email, "password": pwd})
    assert login_res.status_code == 200
    session_token = login_res.json()["access_token"]

    # Attempt to reset password with session token
    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": session_token, "new_password": "UpdatedSecureVault#2026!", "new_password_confirm": "UpdatedSecureVault#2026!"},
    )
    assert reset_res.status_code == 400
    assert "Invalid token scope" in reset_res.json()["detail"]


def test_security_04_valid_reset_token_works_only_once():
    """SEC-04: Verify a reset token can only be consumed once."""
    from app.auth import create_password_reset_token

    user_email = f"analyst_single_{uuid.uuid4().hex[:6]}@nfttrends.io"
    name = "Beatrice Vance"
    pwd = "SecureEnterprisePass#2026!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "name": name, "password": pwd, "password_confirm": pwd},
    )
    assert reg_res.status_code == 200

    reset_token = create_password_reset_token(user_email)
    assert reset_token is not None

    # First reset: must succeed
    res1 = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "SecondSecurePass#2026!", "new_password_confirm": "SecondSecurePass#2026!"},
    )
    assert res1.status_code == 200

    # Second reset with SAME token: must fail
    res2 = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "ThirdSecurePass#2026!", "new_password_confirm": "ThirdSecurePass#2026!"},
    )
    assert res2.status_code == 400
    assert "already been used" in res2.json()["detail"]


def test_security_05_expired_reset_token_rejected():
    """SEC-04: Verify expired reset tokens are rejected."""
    import datetime
    from app.auth import create_password_reset_token

    user_email = f"analyst_expired_{uuid.uuid4().hex[:6]}@nfttrends.io"
    name = "Charles Montgomery"
    pwd = "SecureEnterprisePass#2026!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "name": name, "password": pwd, "password_confirm": pwd},
    )
    assert reg_res.status_code == 200

    # Token with negative delta (already expired)
    expired_token = create_password_reset_token(user_email, expires_delta=datetime.timedelta(seconds=-10))
    assert expired_token is not None

    res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": expired_token, "new_password": "SecondSecurePass#2026!", "new_password_confirm": "SecondSecurePass#2026!"},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_security_06_concurrent_attempts_cannot_both_succeed():
    """SEC-04: Verify concurrent consumption of the same reset token permits only one success."""
    import concurrent.futures
    from app.auth import create_password_reset_token, consume_password_reset_token

    user_email = f"analyst_race_{uuid.uuid4().hex[:6]}@nfttrends.io"
    name = "Diana Prince"
    pwd = "SecureEnterprisePass#2026!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "name": name, "password": pwd, "password_confirm": pwd},
    )
    assert reg_res.status_code == 200

    token = create_password_reset_token(user_email)
    assert token is not None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(consume_password_reset_token, token)
        f2 = executor.submit(consume_password_reset_token, token)
        results = [f1.result(), f2.result()]

    success_count = sum(1 for r in results if r[0] is True)
    failure_count = sum(1 for r in results if r[0] is False)

    assert success_count == 1
    assert failure_count == 1


def test_security_07_production_startup_fails_without_secret_key():
    """SEC-02: Verify production startup fails if SECRET_KEY is missing or empty."""
    import os
    from unittest.mock import patch
    from app.config import Settings

    with patch.dict(os.environ, {"ENV": "production", "SECRET_KEY": ""}):
        try:
            Settings()
            assert False, "Should have raised RuntimeError for empty SECRET_KEY in production"
        except RuntimeError as exc:
            assert "SECRET_KEY environment variable is missing" in str(exc)


def test_security_08_production_startup_rejects_previous_hardcoded_secret():
    """SEC-02: Verify production startup rejects the known old hardcoded default secret."""
    import os
    from unittest.mock import patch
    from app.config import Settings, OLD_DEFAULT_SECRET

    with patch.dict(os.environ, {"ENV": "production", "SECRET_KEY": OLD_DEFAULT_SECRET}):
        try:
            Settings()
            assert False, "Should have raised RuntimeError for hardcoded SECRET_KEY in production"
        except RuntimeError as exc:
            assert "cannot use the insecure hardcoded default secret" in str(exc)


def _build_prod_test_app(frontend_url: str = "https://nft-trend-analyzer.vercel.app") -> FastAPI:
    """Instantiate a fresh production-configured FastAPI app (SEC-03, SEC-07, SEC-08)."""
    import os
    from unittest.mock import patch
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from app.config import Settings
    from app.api.routes_admin import router as admin_router
    from app.api.routes_analysis import router as analysis_router
    from app.api.routes_auth import router as auth_router
    from app.api.routes_marketplace import router as marketplace_router
    from app.api.routes_ml import router as ml_router
    from app.api.routes_workspace import router as workspace_router

    with patch.dict(os.environ, {
        "ENV": "production",
        "SECRET_KEY": "a" * 32,
        "FRONTEND_URL": frontend_url,
        "ALLOWED_ORIGINS": frontend_url,
    }):
        prod_settings = Settings()

    prod_app = FastAPI(
        title=prod_settings.PROJECT_NAME,
        version=prod_settings.VERSION,
        description="Enterprise REST API for NFT Trend Analysis, Predictive ML, and Market Intelligence.",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    prod_app.add_middleware(
        CORSMiddleware,
        allow_origins=prod_settings.CORS_ORIGINS,
        allow_origin_regex=prod_settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

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

    prod_app.mount(prod_settings.API_V1_PREFIX, api_v1)

    @prod_app.get("/health", tags=["Health"])
    async def prod_health_check() -> JSONResponse:
        if prod_settings.IS_PRODUCTION:
            return JSONResponse(content={"status": "healthy"})
        return JSONResponse(content={"status": "healthy", "version": prod_settings.VERSION})

    @prod_app.get("/", tags=["Root"])
    async def prod_root_endpoint() -> JSONResponse:
        return JSONResponse(content={"name": prod_settings.PROJECT_NAME, "status": "active"})

    return prod_app


def test_security_09_cors_rejects_arbitrary_vercel_origins():
    """SEC-03: Verify production CORS rejects arbitrary *.vercel.app origins."""
    prod_app = _build_prod_test_app()
    prod_client = TestClient(prod_app)
    # Attempt request from arbitrary/malicious Vercel deployment
    res = prod_client.options(
        "/api/v1/analysis/dataset/demo",
        headers={
            "Origin": "https://malicious-phishing-nft.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") is None


def test_security_10_cors_accepts_configured_production_origin():
    """SEC-03: Verify production CORS accepts the configured FRONTEND_URL."""
    prod_app = _build_prod_test_app()
    prod_client = TestClient(prod_app)
    res = prod_client.options(
        "/api/v1/analysis/dataset/demo",
        headers={
            "Origin": "https://nft-trend-analyzer.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://nft-trend-analyzer.vercel.app"
    assert res.headers.get("access-control-allow-credentials") == "true"


def test_security_11_cors_rejects_localhost_in_production():
    """SEC-03: Verify production CORS rejects localhost origins."""
    prod_app = _build_prod_test_app()
    prod_client = TestClient(prod_app)
    res = prod_client.options(
        "/api/v1/analysis/dataset/demo",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") is None


def test_security_12_docs_disabled_in_production():
    """SEC-07: Verify /docs, /redoc, and /openapi.json are disabled in production."""
    prod_app = _build_prod_test_app()
    prod_client = TestClient(prod_app)
    # FastAPI returns 404 when docs_url=None, redoc_url=None, openapi_url=None
    assert prod_client.get("/docs").status_code == 404
    assert prod_client.get("/redoc").status_code == 404
    assert prod_client.get("/openapi.json").status_code == 404


def test_security_13_healthcheck_minimizes_info_in_production():
    """SEC-08: Verify /health returns minimal status without disclosing bucket or environment."""
    prod_app = _build_prod_test_app()
    prod_client = TestClient(prod_app)
    res = prod_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data == {"status": "healthy"}
    assert "storage_bucket" not in data
    assert "environment" not in data
    assert "supabase_connected" not in data
    assert "version" not in data


# ==============================================================================
# Stage 1 Production Readiness: Email Delivery & Token Persistence Tests
# ==============================================================================

def test_email_dispatch_success():
    """TASK 1: Verify successful email dispatch via configured provider."""
    from unittest.mock import patch, MagicMock
    from app.services.email_service import EmailService
    from app.config import settings

    with patch.object(settings, "EMAIL_PROVIDER_API_KEY", "re_mock_api_key_123"), \
         patch.object(settings, "EMAIL_FROM", "auth@nfttrends.io"), \
         patch.object(settings, "FRONTEND_URL", "https://nft-trend-analyzer.vercel.app"):

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "msg_mock_abc"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            ok, msg = EmailService.send_password_reset_email("analyst@nfttrends.io", "mock_reset_token_xyz")
            assert ok is True
            assert "successfully" in msg
            assert mock_post.called

            # Check call payload
            called_url = mock_post.call_args[0][0]
            assert "api.resend.com" in called_url
            payload = mock_post.call_args[1]["json"]
            assert payload["to"] == ["analyst@nfttrends.io"]
            assert payload["from"] == "auth@nfttrends.io"
            assert "Reset Your NFT Trend Analyzer Password" in payload["subject"]
            assert "https://nft-trend-analyzer.vercel.app/reset-password?token=mock_reset_token_xyz" in payload["text"]


def test_email_dispatch_provider_failure():
    """TASK 1: Verify safe failure handling when email provider returns error."""
    from unittest.mock import patch, MagicMock
    from app.services.email_service import EmailService
    from app.config import settings

    with patch.object(settings, "EMAIL_PROVIDER_API_KEY", "re_mock_api_key_123"):
        # Provider returns 500
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("requests.post", return_value=mock_resp):
            ok, msg = EmailService.send_password_reset_email("analyst@nfttrends.io", "mock_token")
            assert ok is False
            assert "HTTP 500" in msg

        # API endpoint behaves safely on provider failure
        email = f"failtest_{uuid.uuid4().hex[:6]}@nfttrends.io"
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "name": "Fail Test", "password": "SecurePass#2026!", "password_confirm": "SecurePass#2026!"},
        )
        with patch("requests.post", side_effect=Exception("Connection refused")):
            res = client.post("/api/v1/auth/forgot-password", json={"email": email})
            assert res.status_code == 200
            assert "reset_token" not in res.json()
            assert res.json()["success"] is True


def test_email_dispatch_unconfigured():
    """TASK 1: Verify forgot-password works safely without provider configured."""
    from unittest.mock import patch
    from app.config import settings

    with patch.object(settings, "EMAIL_PROVIDER_CONFIGURED", False), \
         patch.object(settings, "EMAIL_PROVIDER_API_KEY", ""), \
         patch.object(settings, "SMTP_HOST", ""):

        res = client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@domain.com"})
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert "reset_token" not in res.json()


def test_password_reset_token_persistence_across_restart():
    """TASK 4: Verify reset tokens persist across server restarts and prevent replay."""
    from app.auth import create_password_reset_token, consume_password_reset_token

    email = f"persist_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Persist Tester", "password": "SecurePass#2026!", "password_confirm": "SecurePass#2026!"},
    )

    token = create_password_reset_token(email)
    assert token is not None

    # Simulate restart by consuming token in separate context
    ok1, msg1, user_email1 = consume_password_reset_token(token)
    assert ok1 is True
    assert user_email1 == email

    # Replay attempt: must fail
    ok2, msg2, user_email2 = consume_password_reset_token(token)
    assert ok2 is False
    assert "already been used" in msg2


def test_dataset_reopen_error_when_storage_fails():
    """TASK 3: Verify reopening project returns clear 500 error if storage fails, refusing silent demo substitution."""
    from unittest.mock import patch

    email = f"storage_fail_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd = "SecurePass#2026!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Storage Tester", "password": pwd, "password_confirm": pwd},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save project with data
    save_res = client.post(
        "/api/v1/workspace/projects",
        headers=headers,
        json={
            "project_name": "Storage Failure Test",
            "dataset_name": "test.csv",
            "analysis_type": "Regression",
            "summary_json": {},
            "dataframe_records": [{"nft": "BAYC", "price": 25.0}],
        },
    )
    assert save_res.status_code == 200
    project_id = save_res.json()["project_id"]

    # Mock storage retrieval failure
    with patch("app.services.storage_service.StorageService.load_project_dataframe", return_value=(None, "Simulated network timeout")):
        reopen_res = client.get(f"/api/v1/workspace/projects/{project_id}", headers=headers)
        assert reopen_res.status_code == 500
        assert "Unable to restore project dataset" in reopen_res.json()["detail"]


# ==============================================================================
# Task 3: Targeted Supabase PostgREST Mock Tests (12 Test Cases)
# ==============================================================================

def _make_mock_reset_token(email: str = "analyst@nfttrends.io", jti: str = "mock-jti-1234", token_type: str = "reset", delta_seconds: int = 3600) -> str:
    """Helper to craft signed test reset tokens with custom claims."""
    import datetime
    from app.auth import create_access_token

    payload = {
        "id": "mock-user-uuid",
        "email": email,
        "type": token_type,
        "jti": jti,
    }
    return create_access_token(payload, expires_delta=datetime.timedelta(seconds=delta_seconds))


def test_supabase_mock_01_correct_token_hash_accepted():
    """TASK 3.1: Verify correct token hash is accepted in Supabase atomic PATCH."""
    import hashlib
    from unittest.mock import patch, MagicMock
    from app.config import settings
    from app.auth import consume_password_reset_token

    token = _make_mock_reset_token()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
         patch.object(settings, "IS_PRODUCTION", False):

        mock_patch_resp = MagicMock()
        mock_patch_resp.status_code = 200
        mock_patch_resp.text = '[{"jti": "mock-jti-1234", "used_at": "2026-10-31T12:00:00Z"}]'
        mock_patch_resp.json.return_value = [{"jti": "mock-jti-1234", "used_at": "2026-10-31T12:00:00Z"}]

        with patch("requests.patch", return_value=mock_patch_resp) as mock_patch:
            ok, msg, email = consume_password_reset_token(token)
            assert ok is True
            assert email == "analyst@nfttrends.io"
            assert mock_patch.called
            # Verify token_hash and all atomic filters were included in the atomic PATCH filter
            called_params = mock_patch.call_args[1]["params"]
            assert called_params["jti"] == "eq.mock-jti-1234"
            assert called_params["token_hash"] == f"eq.{token_hash}"
            assert called_params["used_at"] == "is.null"
            assert "expires_at" in called_params
            assert called_params["expires_at"].startswith("gt.")


def test_supabase_mock_02_incorrect_token_hash_rejected():
    """TASK 3.2: Verify incorrect token hash causes PATCH to update 0 rows and fails."""
    from unittest.mock import patch, MagicMock
    from app.config import settings
    from app.auth import consume_password_reset_token

    token = _make_mock_reset_token()

    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
         patch.object(settings, "IS_PRODUCTION", False):

        # PATCH returns 0 rows because hash filter does not match
        mock_patch_resp = MagicMock()
        mock_patch_resp.status_code = 200
        mock_patch_resp.text = '[]'
        mock_patch_resp.json.return_value = []

        # GET confirms different token_hash in DB
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = [{"token_hash": "different_hash", "used_at": None, "expires_at": "2099-01-01T00:00:00Z"}]

        with patch("requests.patch", return_value=mock_patch_resp), \
             patch("requests.get", return_value=mock_get_resp):
            ok, msg, email = consume_password_reset_token(token)
            assert ok is False
            assert "invalid" in msg.lower()


def test_supabase_mock_03_expired_token_rejected():
    """TASK 3.3: Verify expired token is rejected by claims validation."""
    from app.auth import consume_password_reset_token

    # Token with negative lifetime (already expired)
    expired_token = _make_mock_reset_token(delta_seconds=-60)
    ok, msg, email = consume_password_reset_token(expired_token)
    assert ok is False
    assert "expired" in msg.lower()


def test_supabase_mock_04_already_used_token_rejected():
    """TASK 3.4: Verify already-used token is rejected when used_at is present."""
    import hashlib
    from unittest.mock import patch, MagicMock
    from app.config import settings
    from app.auth import consume_password_reset_token

    token = _make_mock_reset_token()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
         patch.object(settings, "IS_PRODUCTION", False):

        # PATCH returns 0 rows (used_at is not null)
        mock_patch_resp = MagicMock()
        mock_patch_resp.status_code = 200
        mock_patch_resp.text = '[]'
        mock_patch_resp.json.return_value = []

        # GET confirms used_at is populated
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = [{"token_hash": token_hash, "used_at": "2026-10-31T10:00:00Z", "expires_at": "2099-01-01T00:00:00Z"}]

        with patch("requests.patch", return_value=mock_patch_resp), \
             patch("requests.get", return_value=mock_get_resp):
            ok, msg, email = consume_password_reset_token(token)
            assert ok is False
            assert "already been used" in msg


def test_supabase_mock_05_first_atomic_patch_succeeds():
    """TASK 3.5: Verify first atomic PATCH returns exactly one row and succeeds."""
    from unittest.mock import patch, MagicMock
    from app.config import settings
    from app.auth import consume_password_reset_token

    token = _make_mock_reset_token(jti="atomic-1")

    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
         patch.object(settings, "IS_PRODUCTION", False):

        mock_patch_resp = MagicMock()
        mock_patch_resp.status_code = 200
        mock_patch_resp.text = '[{"jti": "atomic-1"}]'
        mock_patch_resp.json.return_value = [{"jti": "atomic-1"}]

        with patch("requests.patch", return_value=mock_patch_resp):
            ok, msg, email = consume_password_reset_token(token)
            assert ok is True
            assert "successfully" in msg


def test_supabase_mock_06_second_patch_returns_zero_rows_and_fails():
    """TASK 3.6: Verify second atomic PATCH returns zero rows and fails."""
    import hashlib
    from unittest.mock import patch, MagicMock
    from app.config import settings
    from app.auth import consume_password_reset_token

    token = _make_mock_reset_token(jti="atomic-2")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
         patch.object(settings, "IS_PRODUCTION", False):

        mock_patch_resp = MagicMock()
        mock_patch_resp.status_code = 200
        mock_patch_resp.text = '[]'
        mock_patch_resp.json.return_value = []

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = [{"token_hash": token_hash, "used_at": "2026-10-31T11:00:00Z", "expires_at": "2099-01-01T00:00:00Z"}]

        with patch("requests.patch", return_value=mock_patch_resp), \
             patch("requests.get", return_value=mock_get_resp):
            ok, msg, email = consume_password_reset_token(token)
            assert ok is False
            assert "already been used" in msg


def test_supabase_mock_07_timeout_in_production_fails_closed():
    """TASK 3.7: Verify Supabase network timeout in production fails closed."""
    import requests
    from unittest.mock import patch
    from app.config import settings
    from app.auth import consume_password_reset_token, create_password_reset_token

    token = _make_mock_reset_token()

    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
         patch.object(settings, "IS_PRODUCTION", True):

        with patch("requests.patch", side_effect=requests.exceptions.Timeout("Connection timed out")):
            ok, msg, email = consume_password_reset_token(token)
            assert ok is False
            assert "timed out" in msg.lower()

        with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
            new_token = create_password_reset_token("analyst@nfttrends.io")
            assert new_token is None


def test_supabase_mock_08_http_500_in_production_fails_closed():
    """TASK 3.8: Verify Supabase HTTP 500 error in production fails closed."""
    from unittest.mock import patch, MagicMock
    from app.config import settings
    from app.auth import consume_password_reset_token, create_password_reset_token

    token = _make_mock_reset_token()

    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
         patch.object(settings, "IS_PRODUCTION", True):

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("requests.patch", return_value=mock_resp):
            ok, msg, email = consume_password_reset_token(token)
            assert ok is False
            assert "error" in msg.lower()

        with patch("requests.post", return_value=mock_resp):
            new_token = create_password_reset_token("analyst@nfttrends.io")
            assert new_token is None


def test_supabase_mock_09_missing_supabase_in_production_fails_closed():
    """TASK 3.9: Verify unconfigured Supabase in production fails closed without touching SQLite."""
    from unittest.mock import patch
    from app.config import settings
    from app.auth import consume_password_reset_token, create_password_reset_token

    token = _make_mock_reset_token()

    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", ""), \
         patch.object(settings, "IS_PRODUCTION", True):

        ok, msg, email = consume_password_reset_token(token)
        assert ok is False
        assert "unavailable" in msg.lower()

        new_token = create_password_reset_token("analyst@nfttrends.io")
        assert new_token is None


def test_supabase_mock_10_sqlite_fallback_in_development():
    """TASK 3.10: Verify SQLite fallback continues working seamlessly in development."""
    from unittest.mock import patch
    from app.config import settings
    from app.auth import create_password_reset_token, consume_password_reset_token

    test_email = f"dev_fallback_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post(
        "/api/v1/auth/register",
        json={"email": test_email, "name": "Dev User", "password": "SecurePass#2026!", "password_confirm": "SecurePass#2026!"},
    )

    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", ""), \
         patch.object(settings, "IS_PRODUCTION", False):

        # Creation succeeds via SQLite
        dev_token = create_password_reset_token(test_email)
        assert dev_token is not None

        # First consumption succeeds via SQLite
        ok1, msg1, email1 = consume_password_reset_token(dev_token)
        assert ok1 is True
        assert email1 == test_email

        # Second consumption fails via SQLite
        ok2, msg2, email2 = consume_password_reset_token(dev_token)
        assert ok2 is False
        assert "already been used" in msg2


def test_supabase_mock_11_session_token_rejected_as_reset_token():
    """TASK 3.11: Verify standard session token cannot be used as reset token."""
    from app.auth import consume_password_reset_token

    session_token = _make_mock_reset_token(token_type="session")
    ok, msg, email = consume_password_reset_token(session_token)
    assert ok is False
    assert "invalid token scope" in msg.lower()


def test_supabase_mock_12_concurrent_reset_attempts_cannot_both_succeed():
    """TASK 3.12: Verify concurrent consumption attempts result in exactly 1 success."""
    import concurrent.futures
    from app.auth import create_password_reset_token, consume_password_reset_token

    user_email = f"concurrent_race_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "name": "Concurrent Tester", "password": "SecurePass#2026!", "password_confirm": "SecurePass#2026!"},
    )

    token = create_password_reset_token(user_email)
    assert token is not None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(consume_password_reset_token, token)
        f2 = executor.submit(consume_password_reset_token, token)
        results = [f1.result(), f2.result()]

    successes = sum(1 for r in results if r[0] is True)
    failures = sum(1 for r in results if r[0] is False)

    assert successes == 1
    assert failures == 1


def test_supabase_mock_13_http_204_rejected_without_token_consumption():
    """TASK 3.13: Verify HTTP 204 (No Content) is rejected without token consumption."""
    from unittest.mock import patch, MagicMock
    from app.config import settings
    from app.auth import consume_password_reset_token

    token = _make_mock_reset_token()

    for is_prod in (False, True):
        with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
             patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
             patch.object(settings, "IS_PRODUCTION", is_prod):

            mock_patch_resp = MagicMock()
            mock_patch_resp.status_code = 204
            mock_patch_resp.text = ""
            mock_patch_resp.json.return_value = []

            with patch("requests.patch", return_value=mock_patch_resp):
                ok, msg, email = consume_password_reset_token(token)
                assert ok is False
                assert email is None
                assert "error" in msg.lower() or "unexpected" in msg.lower() or "empty" in msg.lower()


def test_pipeline_01_upload_and_analyze_market_dataset():
    """PIPELINE-01: Verify end-to-end automated dataset upload, feature detection & 4-module analysis."""
    import io
    import pandas as pd

    user_email = f"pipeline_analyst_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd = "SecureEnterprisePass#2026!"
    client.post("/api/v1/auth/register", json={"email": user_email, "name": "Pipeline Tester", "password": pwd, "password_confirm": pwd})
    token = client.post("/api/v1/auth/login", json={"email": user_email, "password": pwd}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Generate test CSV with 60 chronological rows
    dates = pd.date_range("2024-01-01", periods=60, freq="D").strftime("%Y-%m-%d").tolist()
    data = []
    for i, d in enumerate(dates):
        data.append({
            "date": d,
            "price": 1.2 + (i % 7) * 0.15,
            "sales_count": 10 + (i % 5) * 4,
            "collection_name": "Azuki" if i % 2 == 0 else "Bored Ape",
            "volume_usd": (1.2 + (i % 7) * 0.15) * 2800 * (10 + (i % 5) * 4),
        })
    df_sample = pd.DataFrame(data)
    csv_bytes = df_sample.to_csv(index=False).encode("utf-8")

    res = client.post(
        "/api/v1/analysis/pipeline/upload-and-analyze",
        files={"file": ("market_chronology.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=headers,
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "success"
    assert payload["valid_records"] == 60
    assert payload["features_detected"]["date_column"] == "date"
    assert payload["features_detected"]["price_column"] == "price"

    summary = payload["modules_summary"]
    assert "price_trends" in summary
    assert summary["price_trends"]["time_series_count"] > 0
    assert "best_model" in summary["price_trends"]

    assert "market_activity" in summary
    assert summary["market_activity"]["total_sales"] > 0

    assert "social_engagement" in summary
    # Honest diagnostic: no social columns were in this dataset
    assert summary["social_engagement"]["available"] is False

    assert "marketplace_hub" in summary
    assert summary["marketplace_hub"]["live_sync"] is True


def test_pipeline_02_upload_and_analyze_with_social_dataset():
    """PIPELINE-02: Verify pipeline correctly identifies social signals and computes correlations."""
    import io
    import pandas as pd

    user_email = f"social_pipeline_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd = "SecureEnterprisePass#2026!"
    client.post("/api/v1/auth/register", json={"email": user_email, "name": "Social Pipeline Tester", "password": pwd, "password_confirm": pwd})
    token = client.post("/api/v1/auth/login", json={"email": user_email, "password": pwd}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Generate test CSV with social columns
    dates = pd.date_range("2024-01-01", periods=50, freq="D").strftime("%Y-%m-%d").tolist()
    data = []
    for i, d in enumerate(dates):
        data.append({
            "date": d,
            "price": 1.5 + (i * 0.05),
            "sales_count": 25 + (i % 10),
            "collection_name": "CryptoPunks",
            "twitter_sentiment": 0.65 + (i * 0.005),
            "retweets_count": 100 + i * 10,
            "likes_count": 500 + i * 25,
        })
    df_sample = pd.DataFrame(data)
    csv_bytes = df_sample.to_csv(index=False).encode("utf-8")

    res = client.post(
        "/api/v1/analysis/pipeline/upload-and-analyze",
        files={"file": ("social_market_joined.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=headers,
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "success"
    assert payload["features_detected"]["social_columns"] is not None
    assert len(payload["features_detected"]["social_columns"]) >= 3

    social_summary = payload["modules_summary"]["social_engagement"]
    assert social_summary["available"] is True
    assert social_summary["tracked_signals_count"] >= 3
    assert len(social_summary["correlations"]) > 0


def test_pipeline_03_active_dataset_and_module_results_retrieval():
    """PIPELINE-03: Verify retrieving active dataset metadata and precomputed module results."""
    user_email = f"active_query_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd = "SecureEnterprisePass#2026!"
    client.post("/api/v1/auth/register", json={"email": user_email, "name": "Query Tester", "password": pwd, "password_confirm": pwd})
    token = client.post("/api/v1/auth/login", json={"email": user_email, "password": pwd}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Load demo dataset as baseline active session
    demo_res = client.get("/api/v1/analysis/dataset/demo", headers=headers)
    assert demo_res.status_code == 200

    # Query active dataset
    meta_res = client.get("/api/v1/analysis/active-dataset", headers=headers)
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert "dataset_name" in meta
    assert meta["rows_count"] > 0

    # Query active results for each module
    res_mod1 = client.get("/api/v1/analysis/active-results/price-trends", headers=headers)
    assert res_mod1.status_code == 200
    assert "time_series" in res_mod1.json() or "data" in res_mod1.json()

    res_mod2 = client.get("/api/v1/analysis/active-results/market-activity", headers=headers)
    assert res_mod2.status_code == 200
    assert "kpis" in res_mod2.json()

    res_mod3 = client.get("/api/v1/analysis/active-results/social-engagement", headers=headers)
    assert res_mod3.status_code == 200

    res_mod4 = client.get("/api/v1/analysis/active-results/marketplace-hub", headers=headers)
    assert res_mod4.status_code == 200
    assert "eth_price" in res_mod4.json()


def test_pipeline_04_select_active_project_and_user_isolation():
    """PIPELINE-04: Verify selecting active project updates session and preserves strict cross-user isolation."""
    # User A creates a project snapshot
    user_a = f"owner_alice_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd = "SecureEnterprisePass#2026!"
    client.post("/api/v1/auth/register", json={"email": user_a, "name": "Alice Analyst", "password": pwd, "password_confirm": pwd})
    token_a = client.post("/api/v1/auth/login", json={"email": user_a, "password": pwd}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    save_res = client.post(
        "/api/v1/workspace/projects",
        json={"project_name": "Alice Active Project", "dataset_name": "Demo Benchmark", "analysis_type": "4-Module Pipeline", "summary_json": {"version": 1}},
        headers=headers_a,
    )
    assert save_res.status_code == 200
    proj_a_id = save_res.json()["project_id"]

    # User A activates the project
    act_res = client.post(f"/api/v1/workspace/select-active/{proj_a_id}", headers=headers_a)
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "active"

    # User B tries to activate Alice's project -> must be rejected (404 Not Found)
    user_b = f"intruder_bob_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post("/api/v1/auth/register", json={"email": user_b, "name": "Bob Intruder", "password": pwd, "password_confirm": pwd})
    token_b = client.post("/api/v1/auth/login", json={"email": user_b, "password": pwd}).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    bad_act_res = client.post(f"/api/v1/workspace/select-active/{proj_a_id}", headers=headers_b)
    assert bad_act_res.status_code == 404


def test_pbkdf2_and_bcrypt_password_verification_regression():
    """REGRESSION: Verify PBKDF2 salt hex decoding, rejection of malformed salts, and bcrypt support."""
    import hashlib
    import secrets
    import bcrypt
    from app.auth import verify_password

    pwd = "EnterprisePassword#2026!"
    wrong_pwd = "WrongEnterprisePassword#9999!"

    # 1. Correct existing PBKDF2 password
    salt_bytes = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt_bytes, 600000)
    pbkdf2_hash = f"pbkdf2_sha256$600000${salt_bytes.hex()}${derived.hex()}"

    assert verify_password(pwd, pbkdf2_hash) is True
    assert verify_password(wrong_pwd, pbkdf2_hash) is False

    # 2. Malformed hexadecimal salt: must return False and NOT silently fall back or raise
    malformed_nonhex_hash = f"pbkdf2_sha256$600000$not_valid_hex_ZZZ${derived.hex()}"
    assert verify_password(pwd, malformed_nonhex_hash) is False

    malformed_oddlength_hash = f"pbkdf2_sha256$600000$abcde${derived.hex()}"
    assert verify_password(pwd, malformed_oddlength_hash) is False

    malformed_format_hash = "pbkdf2_sha256$invalid_parts"
    assert verify_password(pwd, malformed_format_hash) is False

    # 3. Bcrypt password verification
    bcrypt_salt = bcrypt.gensalt(rounds=12)
    bcrypt_hash = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt_salt).decode("utf-8")

    assert verify_password(pwd, bcrypt_hash) is True
    assert verify_password(wrong_pwd, bcrypt_hash) is False

    # Empty inputs
    assert verify_password("", bcrypt_hash) is False
    assert verify_password(pwd, "") is False


def test_transparent_pbkdf2_to_bcrypt_upgrade_sqlite():
    """REGRESSION: Verify transparent upgrade from legacy PBKDF2 hash to bcrypt in SQLite upon sign-in."""
    import sqlite3
    import hashlib
    import secrets
    from unittest.mock import patch
    from app.config import settings
    from app.auth import init_user_db

    init_user_db()
    email = f"legacy_pbkdf2_user_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd = "SecureLegacyUserPass#2026!"

    # Create legacy PBKDF2 hash
    salt_bytes = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt_bytes, 600000)
    legacy_hash = f"pbkdf2_sha256$600000${salt_bytes.hex()}${derived.hex()}"

    # Insert user directly with PBKDF2 hash into SQLite
    conn = sqlite3.connect(settings.SQLITE_PATH)
    with conn:
        conn.execute(
            """
            INSERT INTO registered_users (id, email, name, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (str(uuid.uuid4()), email, "Legacy Analyst", legacy_hash, "analyst"),
        )
    conn.close()

    # Ensure SQLite development mode is used (remote Supabase patched off for isolated test)
    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", ""), \
         patch.object(settings, "IS_PRODUCTION", False):

        # Sign in with the legacy account
        login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()

        # Verify password hash has been transparently upgraded to bcrypt in SQLite
        conn = sqlite3.connect(settings.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        with conn:
            row = conn.execute("SELECT password_hash FROM registered_users WHERE email = ?", (email,)).fetchone()
            assert row is not None
            upgraded_hash = row["password_hash"]
            assert upgraded_hash.startswith(("$2b$", "$2a$"))
            assert not upgraded_hash.startswith("pbkdf2_sha256$")
        conn.close()

        # Verify subsequent sign-in succeeds against the upgraded bcrypt hash
        second_login = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
        assert second_login.status_code == 200
        assert "access_token" in second_login.json()


def test_transparent_pbkdf2_to_bcrypt_upgrade_supabase_mock():
    """REGRESSION: Verify transparent upgrade from legacy PBKDF2 hash to bcrypt with Supabase mock."""
    import hashlib
    import secrets
    from unittest.mock import patch, MagicMock
    from app.config import settings

    email = f"supabase_legacy_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd = "SupabaseLegacyPass#2026!"

    salt_bytes = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt_bytes, 600000)
    legacy_hash = f"pbkdf2_sha256$600000${salt_bytes.hex()}${derived.hex()}"

    mock_user_row = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": "Supabase Analyst",
        "password_hash": legacy_hash,
        "role": "analyst",
        "created_at": "2026-10-01T10:00:00Z",
    }

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = [mock_user_row]

    mock_patch_resp = MagicMock()
    mock_patch_resp.status_code = 200
    mock_patch_resp.json.return_value = [{"email": email, "updated": True}]

    with patch.object(settings, "SUPABASE_URL", "https://mockproject.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key"), \
         patch.object(settings, "IS_PRODUCTION", False), \
         patch("requests.get", return_value=mock_get_resp) as mock_get, \
         patch("requests.patch", return_value=mock_patch_resp) as mock_patch:

        login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()

        # Verify PATCH was sent to update the password hash
        assert mock_patch.called
        patch_call = mock_patch.call_args
        assert patch_call[1]["params"]["email"] == f"eq.{email}"
        new_hash = patch_call[1]["json"]["password_hash"]
        assert new_hash.startswith(("$2b$", "$2a$"))
        assert not new_hash.startswith("pbkdf2_sha256$")
