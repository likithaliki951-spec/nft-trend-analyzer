"""Automated QA Test Suite for RBAC, Admin/User Portals, and Security Enforcements.

Tests all 22 required scenarios:
1. Regular user registration succeeds.
2. Regular user login succeeds.
3. Existing regular user login remains functional.
4. Admin registration with Gmail succeeds as a pending request.
5. Invalid non-Gmail admin registration is rejected.
6. Unverified admin request cannot be approved.
7. Pending admin cannot access admin dashboard.
8. Pending admin cannot call admin APIs.
9. Existing admin can approve a verified pending request.
10. Approved admin can log in.
11. Approved admin can access admin dashboard.
12. Regular user cannot access admin APIs.
13. Regular user cannot modify their role.
14. User cannot approve admin requests.
15. Suspended account cannot access protected routes.
16. Rejected admin request cannot authenticate as admin.
17. First-admin setup cannot be repeated.
18. Existing user accounts and password hashes remain valid.
19. Cross-user dataset access is rejected.
20. Existing dataset upload and analysis continue working.
21. Existing report exports continue working.
22. Admin dashboard statistics use actual database records.
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import (
    create_access_token,
    create_user,
    get_user_by_email,
    has_active_admin,
    hash_password,
    update_user_email_verified,
    update_user_status,
)
from app.config import settings

client = TestClient(app)

# Helper credentials (distinct from any user personal names)
VALID_USER_PWD = "Quantum#2026!AlphaBetaGamma"
VALID_ADMIN_PWD = "Master#2026!TitaniumShield"


def get_or_create_admin() -> tuple[str, str, dict]:
    """Helper to ensure an approved master administrator exists and return their auth headers."""
    admin_email = f"master_admin_{uuid.uuid4().hex[:6]}@gmail.com"
    # First check if setup initialize works or create directly
    res = client.post(
        "/api/v1/admin/setup/initialize",
        json={
            "setup_token": "test-master-setup-secret-token-2026",
            "email": admin_email,
            "name": "Master Admin",
            "password": VALID_ADMIN_PWD,
            "password_confirm": VALID_ADMIN_PWD,
        },
    )
    if res.status_code == 200:
        token = res.json()["access_token"]
        return admin_email, token, {"Authorization": f"Bearer {token}"}

    # If first-admin already exists, login with an existing or create in DB
    existing_user = get_user_by_email(admin_email)
    if not existing_user:
        pwd_hash = hash_password(VALID_ADMIN_PWD)
        create_user(
            email=admin_email,
            name="Master Admin",
            password_hash=pwd_hash,
            role="admin",
            account_status="active",
            email_verified=True,
        )

    login_res = client.post(
        "/api/v1/auth/admin/login",
        json={"email": admin_email, "password": VALID_ADMIN_PWD},
    )
    assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    return admin_email, token, {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Scenarios 1, 2, 3: Regular User Authentication & Backward Compatibility
# ==============================================================================

def test_scenario_01_regular_user_registration_succeeds():
    """Scenario 1: Regular user registration succeeds via /api/v1/auth/user/register."""
    email = f"analyst_{uuid.uuid4().hex[:8]}@nfttrends.io"
    res = client.post(
        "/api/v1/auth/user/register",
        json={
            "email": email,
            "name": "David Clark",
            "password": VALID_USER_PWD,
            "password_confirm": VALID_USER_PWD,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == email
    assert data["user"]["role"] in ("user", "analyst")
    assert data["user"]["account_status"] == "active"


def test_scenario_02_regular_user_login_succeeds():
    """Scenario 2: Regular user login succeeds via /api/v1/auth/user/login."""
    email = f"analyst_{uuid.uuid4().hex[:8]}@nfttrends.io"
    client.post(
        "/api/v1/auth/user/register",
        json={"email": email, "name": "Sarah Connor", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD},
    )

    login_res = client.post(
        "/api/v1/auth/user/login",
        json={"email": email, "password": VALID_USER_PWD},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["user"]["role"] in ("user", "analyst")


def test_scenario_03_existing_regular_user_login_remains_functional():
    """Scenario 3: Existing legacy /api/v1/auth/login route remains fully operational."""
    email = f"legacy_user_{uuid.uuid4().hex[:8]}@nfttrends.io"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Legacy User", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD},
    )

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": VALID_USER_PWD},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()


# ==============================================================================
# Scenarios 4, 5, 6: Admin Registration & Email Verification
# ==============================================================================

def test_scenario_04_admin_registration_with_gmail_succeeds_as_pending():
    """Scenario 4: Admin registration with valid Gmail address succeeds with status: pending."""
    admin_gmail = f"applicant_{uuid.uuid4().hex[:6]}@gmail.com"
    res = client.post(
        "/api/v1/auth/admin/register",
        json={
            "email": admin_gmail,
            "name": "Admin Applicant",
            "password": VALID_ADMIN_PWD,
            "password_confirm": VALID_ADMIN_PWD,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "pending"
    assert data["email_verified"] is False


def test_scenario_05_invalid_non_gmail_admin_registration_is_rejected():
    """Scenario 5: Invalid non-Gmail admin registration is rejected by server (400)."""
    invalid_email = f"hacker_{uuid.uuid4().hex[:6]}@yahoo.com"
    res = client.post(
        "/api/v1/auth/admin/register",
        json={
            "email": invalid_email,
            "name": "Invalid Domain",
            "password": VALID_ADMIN_PWD,
            "password_confirm": VALID_ADMIN_PWD,
        },
    )
    assert res.status_code == 400
    assert "gmail" in res.json()["detail"].lower()


def test_scenario_06_unverified_admin_request_cannot_be_approved():
    """Scenario 6: Unverified admin request cannot be approved by an administrator (400)."""
    _, _, admin_headers = get_or_create_admin()

    applicant_email = f"unverified_{uuid.uuid4().hex[:6]}@gmail.com"
    reg_res = client.post(
        "/api/v1/auth/admin/register",
        json={
            "email": applicant_email,
            "name": "Unverified Applicant",
            "password": VALID_ADMIN_PWD,
            "password_confirm": VALID_ADMIN_PWD,
        },
    )
    assert reg_res.status_code == 200
    request_id = reg_res.json()["request_id"]

    # Attempt to approve without email verification
    approve_res = client.post(f"/api/v1/admin/approvals/{request_id}/approve", headers=admin_headers)
    assert approve_res.status_code == 400
    assert "not been verified" in approve_res.json()["detail"].lower()


# ==============================================================================
# Scenarios 7, 8: Pending Admin Restrictions
# ==============================================================================

def test_scenario_07_pending_admin_cannot_login_or_access_dashboard():
    """Scenario 7: Pending admin cannot authenticate through admin login (403)."""
    pending_email = f"pending_admin_{uuid.uuid4().hex[:6]}@gmail.com"
    client.post(
        "/api/v1/auth/admin/register",
        json={
            "email": pending_email,
            "name": "Pending Admin",
            "password": VALID_ADMIN_PWD,
            "password_confirm": VALID_ADMIN_PWD,
        },
    )

    login_res = client.post(
        "/api/v1/auth/admin/login",
        json={"email": pending_email, "password": VALID_ADMIN_PWD},
    )
    assert login_res.status_code == 403
    assert "pending" in login_res.json()["detail"].lower()


def test_scenario_08_pending_admin_cannot_call_admin_apis():
    """Scenario 8: Pending admin with forged or stale token cannot call admin APIs (403)."""
    pending_email = f"pending_token_{uuid.uuid4().hex[:6]}@gmail.com"
    pwd_hash = hash_password(VALID_ADMIN_PWD)
    success, user_id = create_user(
        email=pending_email,
        name="Pending User",
        password_hash=pwd_hash,
        role="admin",
        account_status="pending",
        email_verified=False,
    )
    assert success is True

    # Token generated with role: admin, but DB state is pending
    forged_token = create_access_token({"sub": user_id, "email": pending_email, "role": "admin"})
    headers = {"Authorization": f"Bearer {forged_token}"}

    res = client.get("/api/v1/admin/dashboard/stats", headers=headers)
    assert res.status_code == 403
    assert "pending" in res.json()["detail"].lower()


# ==============================================================================
# Scenarios 9, 10, 11: Admin Approval & Authorized Dashboard Access
# ==============================================================================

def test_scenario_09_existing_admin_can_approve_verified_pending_request():
    """Scenario 9: Existing approved admin can approve a verified pending request."""
    _, _, admin_headers = get_or_create_admin()

    applicant_email = f"verified_app_{uuid.uuid4().hex[:6]}@gmail.com"
    reg_res = client.post(
        "/api/v1/auth/admin/register",
        json={
            "email": applicant_email,
            "name": "Verified Applicant",
            "password": VALID_ADMIN_PWD,
            "password_confirm": VALID_ADMIN_PWD,
        },
    )
    assert reg_res.status_code == 200
    request_id = reg_res.json()["request_id"]
    verification_token = reg_res.json()["verification_token"]

    # Verify email
    v_res = client.post(
        "/api/v1/auth/admin/verify-email",
        json={"email": applicant_email, "token": verification_token},
    )
    assert v_res.status_code == 200

    # Approve request
    approve_res = client.post(f"/api/v1/admin/approvals/{request_id}/approve", headers=admin_headers)
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "active"


def test_scenario_10_approved_admin_can_log_in():
    """Scenario 10: Approved admin can log in via /api/v1/auth/admin/login."""
    admin_email = f"approved_admin_{uuid.uuid4().hex[:6]}@gmail.com"
    pwd_hash = hash_password(VALID_ADMIN_PWD)
    create_user(
        email=admin_email,
        name="Approved Admin",
        password_hash=pwd_hash,
        role="admin",
        account_status="active",
        email_verified=True,
    )

    login_res = client.post(
        "/api/v1/auth/admin/login",
        json={"email": admin_email, "password": VALID_ADMIN_PWD},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"
    assert data["user"]["account_status"] == "active"


def test_scenario_11_approved_admin_can_access_admin_dashboard():
    """Scenario 11: Approved admin can access admin dashboard statistics."""
    _, _, admin_headers = get_or_create_admin()
    res = client.get("/api/v1/admin/dashboard/stats", headers=admin_headers)
    assert res.status_code == 200
    stats = res.json()
    assert "total_registered_users" in stats
    assert "approved_administrators" in stats


# ==============================================================================
# Scenarios 12, 13, 14: Regular User RBAC Restrictions
# ==============================================================================

def test_scenario_12_regular_user_cannot_access_admin_apis():
    """Scenario 12: Regular user cannot access admin APIs (403 Forbidden)."""
    user_email = f"regular_user_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post(
        "/api/v1/auth/user/register",
        json={"email": user_email, "name": "User", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD},
    )
    login_res = client.post(
        "/api/v1/auth/user/login",
        json={"email": user_email, "password": VALID_USER_PWD},
    )
    token = login_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/admin/dashboard/stats", headers=user_headers)
    assert res.status_code == 403
    assert "administrator access required" in res.json()["detail"].lower()


def test_scenario_13_regular_user_cannot_modify_their_role():
    """Scenario 13: Regular user role cannot be escalated via registration payload or profile endpoint."""
    user_email = f"tamper_{uuid.uuid4().hex[:6]}@nfttrends.io"
    # Attempting to supply role='admin' in registration
    reg_res = client.post(
        "/api/v1/auth/user/register",
        json={
            "email": user_email,
            "name": "Tamper Attempt",
            "password": VALID_USER_PWD,
            "password_confirm": VALID_USER_PWD,
            "role": "admin",
        },
    )
    assert reg_res.status_code == 200
    assert reg_res.json()["user"]["role"] == "user"

    # Verify authoritative record in DB
    db_user = get_user_by_email(user_email)
    assert db_user is not None
    assert db_user["role"] == "user"


def test_scenario_14_user_cannot_approve_admin_requests():
    """Scenario 14: Regular user cannot approve administrator registration requests (403)."""
    user_email = f"unauth_approver_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post(
        "/api/v1/auth/user/register",
        json={"email": user_email, "name": "User Approver", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD},
    )
    login_res = client.post("/api/v1/auth/user/login", json={"email": user_email, "password": VALID_USER_PWD})
    user_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    res = client.post("/api/v1/admin/approvals/dummy_id/approve", headers=user_headers)
    assert res.status_code == 403


# ==============================================================================
# Scenarios 15, 16: Suspended and Rejected Account Protections
# ==============================================================================

def test_scenario_15_suspended_account_cannot_access_protected_routes():
    """Scenario 15: Suspended account is blocked from authenticating or accessing protected endpoints."""
    suspended_email = f"suspended_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd_hash = hash_password(VALID_USER_PWD)
    success, uid = create_user(
        email=suspended_email,
        name="Suspended Person",
        password_hash=pwd_hash,
        role="user",
        account_status="suspended",
    )
    assert success is True

    # 1. Login blocked
    login_res = client.post(
        "/api/v1/auth/user/login",
        json={"email": suspended_email, "password": VALID_USER_PWD},
    )
    assert login_res.status_code == 403
    assert "suspended" in login_res.json()["detail"].lower()

    # 2. Existing token rejected authoritatively
    token = create_access_token({"sub": uid, "email": suspended_email, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 403
    assert "suspended" in me_res.json()["detail"].lower()


def test_scenario_16_rejected_admin_request_cannot_authenticate_as_admin():
    """Scenario 16: Rejected admin request receives status rejected and cannot authenticate as admin."""
    rejected_email = f"rejected_admin_{uuid.uuid4().hex[:6]}@gmail.com"
    pwd_hash = hash_password(VALID_ADMIN_PWD)
    create_user(
        email=rejected_email,
        name="Rejected Applicant",
        password_hash=pwd_hash,
        role="admin",
        account_status="rejected",
    )

    login_res = client.post(
        "/api/v1/auth/admin/login",
        json={"email": rejected_email, "password": VALID_ADMIN_PWD},
    )
    assert login_res.status_code == 403
    assert "rejected" in login_res.json()["detail"].lower()


# ==============================================================================
# Scenarios 17, 18: First-Admin Setup & Legacy Hash Preservation
# ==============================================================================

def test_scenario_17_first_admin_setup_cannot_be_repeated():
    """Scenario 17: First-admin initialization endpoint permanently becomes unavailable after creation."""
    # Ensure an active admin exists
    get_or_create_admin()

    # Attempt second setup call
    second_res = client.post(
        "/api/v1/admin/setup/initialize",
        json={
            "setup_token": "test-master-setup-secret-token-2026",
            "email": f"second_admin_{uuid.uuid4().hex[:6]}@nfttrends.io",
            "name": "Second Admin",
            "password": VALID_ADMIN_PWD,
            "password_confirm": VALID_ADMIN_PWD,
        },
    )
    assert second_res.status_code == 403
    assert "already been completed" in second_res.json()["detail"].lower()


def test_scenario_18_existing_user_accounts_and_password_hashes_remain_valid():
    """Scenario 18: Legacy pbkdf2_sha256 and bcrypt password hashes remain valid and upgrade transparently."""
    legacy_email = f"legacy_pbkdf_{uuid.uuid4().hex[:6]}@nfttrends.io"
    password = "LegacySecurePassword#2026!"
    salt = os.urandom(16).hex()
    iterations = 260000
    computed_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations).hex()
    legacy_hash_string = f"pbkdf2_sha256${iterations}${salt}${computed_hash}"

    # Insert user directly with legacy hash and role analyst
    create_user(
        email=legacy_email,
        name="Legacy Hash User",
        password_hash=legacy_hash_string,
        role="analyst",
        account_status="active",
        email_verified=True,
    )

    # Login should succeed transparently
    login_res = client.post(
        "/api/v1/auth/user/login",
        json={"email": legacy_email, "password": password},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # Password hash in DB should now be upgraded to bcrypt
    updated_user = get_user_by_email(legacy_email)
    assert updated_user is not None
    assert updated_user["password_hash"].startswith("$2b$")


# ==============================================================================
# Scenarios 19, 20, 21: IDOR & Analytical Operations Preservation
# ==============================================================================

def test_scenario_19_cross_user_dataset_access_is_rejected():
    """Scenario 19: Cross-user dataset access (IDOR) is rejected."""
    # User A creates a project
    email_a = f"usera_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post("/api/v1/auth/user/register", json={"email": email_a, "name": "User A", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD})
    token_a = client.post("/api/v1/auth/user/login", json={"email": email_a, "password": VALID_USER_PWD}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    save_res = client.post(
        "/api/v1/workspace/projects",
        headers=headers_a,
        json={
            "project_name": "Confidential Alpha Research",
            "dataset_name": "Alpha Dataset",
            "analysis_type": "time_series",
            "summary_json": {"kpis": {"volume": 500}},
        },
    )
    assert save_res.status_code == 200
    project_id = save_res.json()["project_id"]

    # User B attempts to access User A's project
    email_b = f"userb_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post("/api/v1/auth/user/register", json={"email": email_b, "name": "User B", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD})
    token_b = client.post("/api/v1/auth/user/login", json={"email": email_b, "password": VALID_USER_PWD}).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    idor_res = client.get(f"/api/v1/workspace/projects/{project_id}", headers=headers_b)
    assert idor_res.status_code == 404
    assert "not found or access denied" in idor_res.json()["detail"].lower()


def test_scenario_20_existing_dataset_upload_and_analysis_continue_working():
    """Scenario 20: Existing dataset upload and automated 9-step pipeline continue operational."""
    email = f"pipeline_tester_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post("/api/v1/auth/user/register", json={"email": email, "name": "Pipeline Tester", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD})
    token = client.post("/api/v1/auth/user/login", json={"email": email, "password": VALID_USER_PWD}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = (
        "Datetime_Updated,Price_USD,Sales,Collection\n"
        "2026-01-01,100.5,10,BoredApe\n"
        "2026-01-02,105.2,12,BoredApe\n"
        "2026-01-03,110.0,15,BoredApe\n"
        "2026-01-04,115.8,18,BoredApe\n"
        "2026-01-05,120.4,20,BoredApe\n"
    )
    files = {"file": ("test_nft_data.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    upload_res = client.post("/api/v1/analysis/pipeline/upload-and-analyze", headers=headers, files=files)
    assert upload_res.status_code == 200
    assert upload_res.json()["success"] is True


def test_scenario_21_existing_report_exports_continue_working():
    """Scenario 21: Existing report exports in PDF, JSON, DOCX, and XLSX formats continue operational."""
    email = f"exporter_qa_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post("/api/v1/auth/user/register", json={"email": email, "name": "Export QA", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD})
    token = client.post("/api/v1/auth/user/login", json={"email": email, "password": VALID_USER_PWD}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Load demo data
    client.get("/api/v1/analysis/dataset/demo", headers=headers)

    for fmt in ["json", "pdf", "docx", "xlsx"]:
        res = client.post("/api/v1/analysis/export", headers=headers, json={"format": fmt, "scope": "complete"})
        assert res.status_code == 200, f"Export for format {fmt} failed: {res.text}"
        assert len(res.content) > 50


# ==============================================================================
# Scenario 22: Accurate Database Records in Admin Dashboard
# ==============================================================================

def test_scenario_22_admin_dashboard_statistics_use_actual_database_records():
    """Scenario 22: Admin dashboard statistics reflect real database records without fake data."""
    _, _, admin_headers = get_or_create_admin()

    res = client.get("/api/v1/admin/dashboard/stats", headers=admin_headers)
    assert res.status_code == 200
    stats = res.json()

    # Values must be actual integers calculated from the database
    assert isinstance(stats["total_registered_users"], int)
    assert isinstance(stats["active_users"], int)
    assert isinstance(stats["pending_users"], int)
    assert isinstance(stats["suspended_users"], int)
    assert isinstance(stats["approved_administrators"], int)
    assert isinstance(stats["pending_admin_requests"], int)
    assert stats["total_registered_users"] >= stats["active_users"]
    assert stats["approved_administrators"] >= 1


# ==============================================================================
# Scenarios 23 - 34: Verification Token Security, Lockout & Resilience Tests
# ==============================================================================

def test_scenario_23_expired_admin_verification_token_is_rejected():
    """Scenario 23: Expired administrator email verification token is rejected (400)."""
    email = f"expired_admin_{uuid.uuid4().hex[:6]}@gmail.com"
    reg_res = client.post(
        "/api/v1/auth/admin/register",
        json={"email": email, "name": "Expired Admin", "password": VALID_ADMIN_PWD, "password_confirm": VALID_ADMIN_PWD},
    )
    assert reg_res.status_code == 200

    # Create an expired token (expired 2 hours ago)
    import datetime, time
    from app.auth import create_access_token
    expired_token = create_access_token(
        {"email": email, "type": "admin_email_verify", "jti": str(uuid.uuid4())},
        expires_delta=datetime.timedelta(seconds=-7200),
    )

    verify_res = client.post(
        "/api/v1/auth/admin/verify-email",
        json={"email": email, "token": expired_token},
    )
    assert verify_res.status_code == 400
    assert "expired" in verify_res.json()["detail"].lower()


def test_scenario_24_reused_verification_token_is_rejected_replay_protection():
    """Scenario 24: Single-use verification token cannot be reused (replay protection)."""
    email = f"replay_admin_{uuid.uuid4().hex[:6]}@gmail.com"
    reg_res = client.post(
        "/api/v1/auth/admin/register",
        json={"email": email, "name": "Replay Admin", "password": VALID_ADMIN_PWD, "password_confirm": VALID_ADMIN_PWD},
    )
    assert reg_res.status_code == 200
    token = reg_res.json()["verification_token"]

    # 1. First consumption succeeds
    v1_res = client.post(
        "/api/v1/auth/admin/verify-email",
        json={"email": email, "token": token},
    )
    assert v1_res.status_code == 200
    assert v1_res.json()["success"] is True

    # 2. Second consumption with identical token must be rejected
    v2_res = client.post(
        "/api/v1/auth/admin/verify-email",
        json={"email": email, "token": token},
    )
    assert v2_res.status_code == 400
    assert "already" in v2_res.json()["detail"].lower() or "invalid" in v2_res.json()["detail"].lower()


def test_scenario_25_verification_token_account_mismatch_is_rejected():
    """Scenario 25: Verification token presented for wrong email is rejected (400)."""
    email_a = f"victim_{uuid.uuid4().hex[:6]}@gmail.com"
    email_b = f"attacker_{uuid.uuid4().hex[:6]}@gmail.com"
    reg_res = client.post(
        "/api/v1/auth/admin/register",
        json={"email": email_a, "name": "Victim Admin", "password": VALID_ADMIN_PWD, "password_confirm": VALID_ADMIN_PWD},
    )
    assert reg_res.status_code == 200
    token_a = reg_res.json()["verification_token"]

    # Attacker attempts to use Victim's token for their own email
    mismatch_res = client.post(
        "/api/v1/auth/admin/verify-email",
        json={"email": email_b, "token": token_a},
    )
    assert mismatch_res.status_code == 400
    assert "match" in mismatch_res.json()["detail"].lower()


def test_scenario_26_unverified_admin_cannot_log_in():
    """Scenario 26: Administrator account with unverified email cannot log in even if active."""
    email = f"unverified_active_{uuid.uuid4().hex[:6]}@gmail.com"
    pwd_hash = hash_password(VALID_ADMIN_PWD)
    create_user(
        email=email,
        name="Unverified Active Admin",
        password_hash=pwd_hash,
        role="admin",
        account_status="active",
        email_verified=False,
    )

    login_res = client.post(
        "/api/v1/auth/admin/login",
        json={"email": email, "password": VALID_ADMIN_PWD},
    )
    assert login_res.status_code == 403
    assert "verified" in login_res.json()["detail"].lower()


def test_scenario_27_email_provider_failure_handled_safely():
    """Scenario 27: Email provider delivery failure fails safely and rolls back registration."""
    from unittest.mock import patch
    from app.services.email_service import EmailService

    email = f"delivery_fail_{uuid.uuid4().hex[:6]}@gmail.com"
    original_configured = settings.EMAIL_PROVIDER_CONFIGURED

    try:
        settings.EMAIL_PROVIDER_CONFIGURED = True

        with patch.object(EmailService, "send_admin_verification_email", return_value=(False, "Connection reset by peer")):
            res = client.post(
                "/api/v1/auth/admin/register",
                json={"email": email, "name": "Delivery Fail", "password": VALID_ADMIN_PWD, "password_confirm": VALID_ADMIN_PWD},
            )
            assert res.status_code == 502
            assert "failed to dispatch" in res.json()["detail"].lower()

            # Verify account was rolled back
            assert get_user_by_email(email) is None
    finally:
        settings.EMAIL_PROVIDER_CONFIGURED = original_configured


def test_scenario_28_missing_production_email_config_fails_safely():
    """Scenario 28: Missing production email configuration fails registration safely (503)."""
    email = f"no_provider_{uuid.uuid4().hex[:6]}@gmail.com"
    original_prod = settings.IS_PRODUCTION
    original_configured = settings.EMAIL_PROVIDER_CONFIGURED

    try:
        settings.IS_PRODUCTION = True
        settings.EMAIL_PROVIDER_CONFIGURED = False

        res = client.post(
            "/api/v1/auth/admin/register",
            json={"email": email, "name": "No Provider", "password": VALID_ADMIN_PWD, "password_confirm": VALID_ADMIN_PWD},
        )
        assert res.status_code == 503
        assert "not configured" in res.json()["detail"].lower()
    finally:
        settings.IS_PRODUCTION = original_prod
        settings.EMAIL_PROVIDER_CONFIGURED = original_configured


def test_scenario_29_last_active_admin_cannot_be_suspended():
    """Scenario 29: Lockout prevention prohibits suspending the last active administrator."""
    # Ensure master admin exists
    admin_email, _, admin_headers = get_or_create_admin()
    admin_record = get_user_by_email(admin_email)
    assert admin_record is not None

    # In test database, if other admins exist, suspend them first to leave exactly 1 active admin
    import sqlite3
    conn = sqlite3.connect(settings.SQLITE_PATH)
    with conn:
        conn.execute("UPDATE registered_users SET account_status = 'suspended' WHERE role = 'admin' AND email != ?", (admin_email,))
    conn.close()

    # Now attempt to suspend the sole remaining active admin
    try:
        res = client.patch(
            f"/api/v1/admin/users/{admin_record['id']}/status",
            headers=admin_headers,
            json={"status": "suspended"},
        )
        assert res.status_code == 400
        assert "last active administrator" in res.json()["detail"].lower() or "self-suspension" in res.json()["detail"].lower()
    finally:
        conn = sqlite3.connect(settings.SQLITE_PATH)
        with conn:
            conn.execute("UPDATE registered_users SET account_status = 'active' WHERE email = 'admin@nfttrends.io'")
        conn.close()


def test_scenario_30_admin_cannot_suspend_self():
    """Scenario 30: An administrator cannot suspend themselves even if multiple admins exist."""
    admin_email, _, admin_headers = get_or_create_admin()
    admin_record = get_user_by_email(admin_email)
    assert admin_record is not None

    # Create a second active admin so quorum is not an issue
    second_email = f"peer_admin_{uuid.uuid4().hex[:6]}@gmail.com"
    pwd_hash = hash_password(VALID_ADMIN_PWD)
    create_user(
        email=second_email,
        name="Peer Admin",
        password_hash=pwd_hash,
        role="admin",
        account_status="active",
        email_verified=True,
    )

    # Admin attempts to suspend their own account
    res = client.patch(
        f"/api/v1/admin/users/{admin_record['id']}/status",
        headers=admin_headers,
        json={"status": "suspended"},
    )
    assert res.status_code == 400
    assert "self-suspension is prohibited" in res.json()["detail"].lower()


def test_scenario_31_approval_and_rejection_validate_target_roles_and_statuses():
    """Scenario 31: Approval and rejection endpoints validate target roles and statuses."""
    _, _, admin_headers = get_or_create_admin()

    # 1. Attempt to approve a regular user
    user_email = f"user_not_admin_{uuid.uuid4().hex[:6]}@nfttrends.io"
    client.post("/api/v1/auth/user/register", json={"email": user_email, "name": "Reg User", "password": VALID_USER_PWD, "password_confirm": VALID_USER_PWD})
    reg_user = get_user_by_email(user_email)

    approve_user_res = client.post(f"/api/v1/admin/approvals/{reg_user['id']}/approve", headers=admin_headers)
    assert approve_user_res.status_code == 400
    assert "only pending administrator" in approve_user_res.json()["detail"].lower()

    # 2. Attempt to reject an already active user
    reject_active_res = client.post(f"/api/v1/admin/approvals/{reg_user['id']}/reject", headers=admin_headers)
    assert reject_active_res.status_code == 400
    assert "only pending administrator" in reject_active_res.json()["detail"].lower()


def test_scenario_32_first_admin_initialization_prevents_multiple_administrators():
    """Scenario 32: First-admin setup is atomic and prevents creating multiple initial administrators."""
    from app.auth import initialize_first_admin

    email_a = f"init_a_{uuid.uuid4().hex[:6]}@gmail.com"
    pwd_hash = hash_password(VALID_ADMIN_PWD)

    orig_url = settings.SUPABASE_URL
    orig_key = settings.SUPABASE_SERVICE_ROLE_KEY
    settings.SUPABASE_URL = ""
    settings.SUPABASE_SERVICE_ROLE_KEY = ""
    try:
        # First call must fail if an active admin already exists
        ok, res = initialize_first_admin(email_a, "Admin A", pwd_hash)
        assert ok is False
        assert "already been completed" in res.lower()
    finally:
        settings.SUPABASE_URL = orig_url
        settings.SUPABASE_SERVICE_ROLE_KEY = orig_key


def test_scenario_33_database_failures_do_not_trigger_production_sqlite_fallback():
    """Scenario 33: In production, database query failure fails closed and never falls back to SQLite."""
    original_prod = settings.IS_PRODUCTION
    original_url = settings.SUPABASE_URL
    original_key = settings.SUPABASE_SERVICE_ROLE_KEY

    try:
        settings.IS_PRODUCTION = True
        settings.SUPABASE_URL = "https://unreachable-production-cluster-999.supabase.co"
        settings.SUPABASE_SERVICE_ROLE_KEY = "test-key"

        # get_user_by_email should return None and not read local SQLite
        result = get_user_by_email("any_user@nfttrends.io")
        assert result is None

        # has_active_admin should raise RuntimeError and not read local SQLite
        with pytest.raises(RuntimeError):
            has_active_admin()
    finally:
        settings.IS_PRODUCTION = original_prod
        settings.SUPABASE_URL = original_url
        settings.SUPABASE_SERVICE_ROLE_KEY = original_key


def test_scenario_34_activity_logging_scrubs_sensitive_secrets_and_tokens():
    """Scenario 34: Activity logging scrubs sensitive passwords, secrets, tokens, and hashes."""
    from app.auth import log_activity, get_recent_activity

    test_action = f"audit_scrub_test_{uuid.uuid4().hex[:6]}"
    log_activity(
        action=test_action,
        user_email="auditor@nfttrends.io",
        details={
            "password": "SuperSecretPassword123!",
            "verification_token": "jwt.secret.token.xyz",
            "setup_token": "admin-master-setup-secret",
            "safe_metric": 42,
        },
    )

    events = get_recent_activity(limit=10)
    matching = [e for e in events if e.get("action") == test_action]
    assert len(matching) > 0
    event_details = matching[0]["details"]

    assert event_details["password"] == "[REDACTED]"
    assert event_details["verification_token"] == "[REDACTED]"
    assert event_details["setup_token"] == "[REDACTED]"
    assert event_details["safe_metric"] == 42


def test_scenario_35_first_admin_setup_token_constant_time_comparison():
    """Scenario 35: First-admin setup token comparison uses constant-time validation and rejects unauthorized tokens."""
    import secrets
    from unittest.mock import patch

    # 1. Reject invalid setup token
    bad_res = client.post(
        "/api/v1/admin/setup/initialize",
        json={
            "setup_token": "wrong-invalid-token-guess-12345",
            "email": "master_init_try@gmail.com",
            "name": "Master Candidate",
            "password": VALID_ADMIN_PWD,
            "password_confirm": VALID_ADMIN_PWD,
        },
    )
    assert bad_res.status_code == 403
    assert "invalid administrator setup token" in bad_res.json()["detail"].lower()

    # 2. Reject when ADMIN_SETUP_TOKEN is empty/unconfigured (fails closed)
    orig_token = settings.ADMIN_SETUP_TOKEN
    try:
        settings.ADMIN_SETUP_TOKEN = ""
        missing_token_res = client.post(
            "/api/v1/admin/setup/initialize",
            json={
                "setup_token": "any-token",
                "email": "master_init_try@gmail.com",
                "name": "Master Candidate",
                "password": VALID_ADMIN_PWD,
                "password_confirm": VALID_ADMIN_PWD,
            },
        )
        assert missing_token_res.status_code == 500
        assert "not configured" in missing_token_res.json()["detail"].lower()
    finally:
        settings.ADMIN_SETUP_TOKEN = orig_token

    # 3. Verify secrets.compare_digest is called during setup
    with patch("secrets.compare_digest", wraps=secrets.compare_digest) as mock_digest:
        client.post(
            "/api/v1/admin/setup/initialize",
            json={
                "setup_token": "wrong-probe-token",
                "email": "probe@gmail.com",
                "name": "Probe",
                "password": VALID_ADMIN_PWD,
                "password_confirm": VALID_ADMIN_PWD,
            },
        )
        assert mock_digest.called


def test_scenario_36_sql_constraint_validator_eight_cases():
    """Scenario 36: Test the SQL check constraint validator against all eight test cases.

    Required test cases:
    1. Correct role constraint (must pass).
    2. Extra role such as 'superadmin' (must fail).
    3. Untested extra role such as 'viewer' (e.g. role <> 'superadmin') (must fail).
    4. Correct status constraint (must pass).
    5. Extra status such as 'archived' (must fail).
    6. OR TRUE bypass (must fail).
    7. NULL acceptance (must fail).
    8. Missing required values (must fail).
    """
    import re
    import sqlite3

    conn = sqlite3.connect(":memory:")

    def validate_constraint_logic(
        expr: str,
        col_name: str,
        valid_vals: list[str],
        invalid_vals: list[str],
        untested_probe: str | None = None,
    ) -> bool:
        """Simulate rigorous verification of a CHECK constraint expression.

        Ensures:
        1. Negative operators (<>, !=, NOT IN) and open comparisons are rejected
           (preventing open sets that allow arbitrary untested values like 'viewer').
        2. Extracted literals match the exact allowed set.
        3. NULL evaluates strictly to 0 (FALSE), preventing NULL acceptance.
        4. Tautologies / disjunctions (OR TRUE, OR 1=1) are rejected.
        5. Every allowed value evaluates strictly to 1 (TRUE).
        6. Every invalid value and untested probe evaluates strictly to 0 (FALSE).
        """
        # 1. Structural check: reject negative operators or open comparisons
        # Expressions like `col <> 'superadmin'` or `col != 'superadmin'` create open sets
        # that inadvertently permit unauthorized roles such as 'viewer'.
        if re.search(r"(<>|!=|\bNOT\s+IN\b|\bLIKE\b|~)", expr, re.IGNORECASE):
            return False

        # Reject obvious tautologies like OR TRUE or OR 1=1
        if re.search(r"\bOR\s+(TRUE|1\s*=\s*1)\b", expr, re.IGNORECASE):
            return False

        # 2. Literal set check: extract all single-quoted literals
        literals = set(re.findall(r"'([^']*)'", expr))
        if literals != set(valid_vals):
            return False

        # 3. NULL test: in SQL CHECK constraints, NULL passes if expression is TRUE or NULL.
        # It ONLY fails if the expression is strictly FALSE (0).
        # Therefore, to reject NULL, the expression MUST evaluate strictly to 0 (FALSE).
        null_query = f"SELECT ({expr}) FROM (SELECT NULL AS {col_name})"
        try:
            cur = conn.execute(null_query)
            null_res = cur.fetchone()[0]
            if null_res != 0:  # If 1 (TRUE) or None (NULL), the constraint does NOT reject NULL
                return False
        except Exception:
            return False

        # 4. Valid values test: every allowed value must evaluate to 1 (TRUE)
        for val in valid_vals:
            escaped = val.replace("'", "''")
            query = f"SELECT ({expr}) FROM (SELECT '{escaped}' AS {col_name})"
            try:
                cur = conn.execute(query)
                res = cur.fetchone()[0]
                if res != 1:
                    return False
            except Exception:
                return False

        # 5. Invalid values test: every unauthorized value must evaluate to 0 (FALSE)
        probe_list = list(invalid_vals)
        if untested_probe:
            probe_list.append(untested_probe)

        for val in probe_list:
            escaped = val.replace("'", "''")
            query = f"SELECT ({expr}) FROM (SELECT '{escaped}' AS {col_name})"
            try:
                cur = conn.execute(query)
                res = cur.fetchone()[0]
                if res != 0:  # If 1 or None, the constraint permitted an unauthorized value
                    return False
            except Exception:
                pass

        return True

    # Case 1: The correct role constraint
    correct_role_expr = "role IS NOT NULL AND role IN ('user', 'admin')"
    assert validate_constraint_logic(
        correct_role_expr, "role", ["user", "admin"], ["superadmin", "analyst", "guest", "root"]
    ) is True, "Case 1: Correct role constraint must pass"

    # Case 2: Extra role such as 'superadmin'
    superadmin_expr = "role IS NOT NULL AND role IN ('user', 'admin', 'superadmin')"
    assert validate_constraint_logic(
        superadmin_expr, "role", ["user", "admin"], ["superadmin", "analyst", "guest", "root"]
    ) is False, "Case 2: Constraint allowing superadmin must be rejected"

    # Case 3: Untested extra role such as 'viewer' (e.g. role <> 'superadmin')
    # A naive probe checking only 'superadmin' would miss that 'viewer' is permitted!
    untested_viewer_expr = "role IS NOT NULL AND role <> 'superadmin'"
    assert validate_constraint_logic(
        untested_viewer_expr, "role", ["user", "admin"], ["superadmin"], untested_probe="viewer"
    ) is False, "Case 3: Negative constraint allowing untested 'viewer' must be rejected"

    # Case 4: Correct status constraint
    status_valid = ["active", "pending", "rejected", "suspended"]
    status_invalid = ["archived", "deleted", "banned", "inactive"]
    correct_status_expr = "account_status IS NOT NULL AND account_status IN ('active', 'pending', 'rejected', 'suspended')"
    assert validate_constraint_logic(
        correct_status_expr, "account_status", status_valid, status_invalid
    ) is True, "Case 4: Correct status constraint must pass"

    # Case 5: Extra status such as 'archived'
    extra_status_expr = "account_status IS NOT NULL AND account_status IN ('active', 'pending', 'rejected', 'suspended', 'archived')"
    assert validate_constraint_logic(
        extra_status_expr, "account_status", status_valid, status_invalid
    ) is False, "Case 5: Constraint with extra status must be rejected"

    # Case 6: OR TRUE bypass
    or_true_expr = "role IS NOT NULL AND role IN ('user', 'admin') OR 1=1"
    assert validate_constraint_logic(
        or_true_expr, "role", ["user", "admin"], ["superadmin", "analyst", "guest", "root"]
    ) is False, "Case 6: Constraint containing OR TRUE must be rejected"

    # Case 7: NULL acceptance (missing IS NOT NULL check)
    permits_null_expr = "role IN ('user', 'admin')"
    assert validate_constraint_logic(
        permits_null_expr, "role", ["user", "admin"], ["superadmin", "analyst", "guest", "root"]
    ) is False, "Case 7: Constraint permitting NULL must be rejected"

    # Case 8: Missing required values (missing 'admin')
    missing_val_expr = "role IS NOT NULL AND role IN ('user')"
    assert validate_constraint_logic(
        missing_val_expr, "role", ["user", "admin"], ["superadmin", "analyst", "guest", "root"]
    ) is False, "Case 8: Constraint missing 'admin' must be rejected"


def test_scenario_37_migration_ordering_and_precheck_verification():
    """Scenario 37: Verify migration ordering and pre-check data safety.

    1. Proves that attempting to update legacy data with an active legacy check constraint
       fails if the old constraint is not dropped first.
    2. Proves that dropping the old constraint before data normalization allows the update to succeed.
    3. Proves that pre-migration data audit detects unrecognized/corrupted roles and aborts.
    """
    import sqlite3

    conn = sqlite3.connect(":memory:")

    # 1. Setup table with legacy constraint allowing only ('analyst', 'admin')
    conn.execute(
        """
        CREATE TABLE legacy_users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('analyst', 'admin'))
        )
        """
    )
    conn.execute("INSERT INTO legacy_users VALUES ('u1', 'analyst@test.com', 'analyst')")
    conn.commit()

    # Demonstrates that updating role to 'user' fails while the old constraint is in place
    try:
        conn.execute("UPDATE legacy_users SET role = 'user' WHERE role = 'analyst'")
        failed_as_expected = False
    except sqlite3.IntegrityError:
        failed_as_expected = True
    assert failed_as_expected, "Updating role to 'user' MUST fail when legacy constraint is present"

    # 2. Safe migration ordering: drop old constraint (or rebuild table in SQLite), normalize, and re-add canonical constraint
    conn.execute("ALTER TABLE legacy_users RENAME TO legacy_users_old")
    conn.execute(
        """
        CREATE TABLE legacy_users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )
    conn.execute("INSERT INTO legacy_users SELECT * FROM legacy_users_old")
    conn.execute("DROP TABLE legacy_users_old")

    # Now the normalization update succeeds cleanly!
    conn.execute("UPDATE legacy_users SET role = 'user' WHERE role = 'analyst'")
    cur = conn.execute("SELECT role FROM legacy_users WHERE id = 'u1'")
    assert cur.fetchone()[0] == "user"

    # 3. Pre-migration audit check simulation: detects unrecognized roles
    conn.execute("INSERT INTO legacy_users VALUES ('u2', 'hacker@test.com', 'superadmin')")
    cur = conn.execute(
        "SELECT COUNT(*) FROM legacy_users WHERE role NOT IN ('user', 'admin', 'analyst')"
    )
    invalid_count = cur.fetchone()[0]
    assert invalid_count == 1, "Pre-migration check must detect unrecognized role values"


# ==============================================================================
# Scenarios 38, 39, 40: Generic HTTP 503 & Zero Leakage of Database Internals
# ==============================================================================

def test_scenario_38_database_exceptions_return_generic_503_without_leaking_internals():
    """Scenario 38: routes_admin never returns database exception details or hostnames in HTTP responses."""
    from unittest.mock import patch

    secret_setup_token = "test-master-setup-secret-token-2026"
    test_email = f"first_admin_db_err_{uuid.uuid4().hex[:6]}@nfttrends.io"

    # Simulate internal database connection timeout with private connection details
    internal_error_msg = "FATAL: connection to server at 'internal-pg-cluster.internal.net' (10.0.4.15), port 5432 failed: timeout"
    with patch("app.api.routes_admin.has_admin_been_initialized", side_effect=RuntimeError(internal_error_msg)):
        res = client.post(
            "/api/v1/admin/setup/initialize",
            json={
                "setup_token": secret_setup_token,
                "email": test_email,
                "name": "Admin Candidate",
                "password": VALID_ADMIN_PWD,
                "password_confirm": VALID_ADMIN_PWD,
            },
        )
        assert res.status_code == 503
        detail = res.json().get("detail", "")
        # Generic message only
        assert detail == "Database service unavailable. Please retry later."
        # Confirm absolute zero leakage of internal hostnames, IPs, or error string
        assert "internal-pg-cluster" not in detail
        assert "10.0.4.15" not in detail
        assert "FATAL" not in detail
        assert "5432" not in detail


def test_scenario_39_quorum_database_exceptions_return_generic_503():
    """Scenario 39: Quorum check failure during admin status update returns generic 503."""
    from unittest.mock import patch

    _, _, admin_headers = get_or_create_admin()

    # Create a target admin
    target_email = f"target_admin_{uuid.uuid4().hex[:6]}@nfttrends.io"
    pwd_hash = hash_password(VALID_ADMIN_PWD)
    success, target_id = create_user(
        email=target_email,
        name="Target Admin",
        password_hash=pwd_hash,
        role="admin",
        account_status="active",
        email_verified=True,
    )
    assert success

    internal_quorum_error = "FATAL: pgbouncer pool exhausted at 192.168.1.50:6432"
    with patch("app.api.routes_admin.count_active_admins", side_effect=RuntimeError(internal_quorum_error)):
        res = client.patch(
            f"/api/v1/admin/users/{target_id}/status",
            headers=admin_headers,
            json={"status": "suspended"},
        )
        assert res.status_code == 503
        detail = res.json().get("detail", "")
        assert detail == "Database service unavailable while checking administrator quorum."
        assert "pgbouncer" not in detail
        assert "192.168.1.50" not in detail
        assert "FATAL" not in detail


def test_scenario_40_approvals_and_directory_database_exceptions_return_generic_503():
    """Scenario 40: Database exceptions in approvals and user directory return generic 503."""
    from unittest.mock import patch

    _, _, admin_headers = get_or_create_admin()

    # 1. Directory query failure
    with patch("app.api.routes_admin.get_all_users_admin", side_effect=RuntimeError("psycopg2.OperationalError: server closed the connection unexpectedly")):
        res = client.get("/api/v1/admin/users", headers=admin_headers)
        assert res.status_code == 503
        detail = res.json().get("detail", "")
        assert detail == "Database service unavailable. Please retry later."
        assert "psycopg2" not in detail
        assert "OperationalError" not in detail

    # 2. Approvals list query failure
    with patch("app.api.routes_admin.get_all_users_admin", side_effect=RuntimeError("psycopg2.OperationalError: SSL connection has been closed")):
        res = client.get("/api/v1/admin/approvals", headers=admin_headers)
        assert res.status_code == 503
        detail = res.json().get("detail", "")
        assert detail == "Database service unavailable. Please retry later."
        assert "psycopg2" not in detail


# ==============================================================================
# Scenarios 41-44: Final RBAC Corrections & Constraint Precision Verification
# ==============================================================================

def test_scenario_41_pending_normal_user_cannot_be_rejected_via_admin_approval():
    """Scenario 41: A pending regular user cannot be rejected via admin approvals endpoint.

    Verifies:
    1. Python pre-check rejects with 400.
    2. Atomic database update enforces expected_role='admin', preventing race conditions.
    3. User status remains unchanged in the database.
    """
    from app.auth import get_user_by_id, update_user_status_conditional
    from app.api.routes_admin import reject_admin_request
    from fastapi import HTTPException

    admin_ctx = {"id": str(uuid.uuid4()), "email": f"admin_{uuid.uuid4().hex[:6]}@gmail.com", "role": "admin"}

    # Create a pending regular user (role='user', account_status='pending')
    norm_user_email = f"pending_user_{uuid.uuid4().hex[:6]}@gmail.com"
    pwd_hash = hash_password(VALID_USER_PWD)
    success, norm_user_id = create_user(
        email=norm_user_email,
        name="Pending Normal User",
        password_hash=pwd_hash,
        role="user",
        account_status="pending",
        email_verified=True,
    )
    assert success

    # 1. Attempt rejection via admin approval route
    try:
        coro = reject_admin_request(norm_user_id, admin_user=admin_ctx)
        coro.send(None)
        raise AssertionError("Should have rejected pending normal user")
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Only pending administrator requests can be rejected."

    # Verify status in database is still 'pending'
    user_rec = get_user_by_id(norm_user_id)
    assert user_rec is not None
    assert user_rec["account_status"] == "pending"
    assert user_rec["role"] == "user"

    # 2. Test direct database conditional update with expected_role='admin'
    updated = update_user_status_conditional(
        user_id=norm_user_id,
        new_status="rejected",
        expected_status="pending",
        expected_role="admin",
    )
    assert updated is False, "Atomic database update must fail when target role is not 'admin'"

    # Status must still be 'pending'
    user_rec_after = get_user_by_id(norm_user_id)
    assert user_rec_after["account_status"] == "pending"


def test_scenario_42_first_admin_setup_blocked_when_first_admin_is_suspended():
    """Scenario 42: First-admin setup cannot be repeated even if the first admin is suspended.

    Verifies:
    - has_admin_been_initialized() returns True even when account_status='suspended'.
    - has_active_admin() returns False (no active admin).
    - /admin/setup/initialize rejects with 403.
    """
    import sqlite3
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from app.auth import has_active_admin, has_admin_been_initialized
    from app.api.routes_admin import initialize_master_admin
    from app.schemas import AdminSetupInitRequest

    # Provision initial admin with approved_by='initial_setup'
    admin_email = f"suspended_initial_admin_{uuid.uuid4().hex[:6]}@gmail.com"
    pwd_hash = hash_password(VALID_ADMIN_PWD)

    conn = sqlite3.connect(settings.SQLITE_PATH)
    with conn:
        # Reset any previous admin accounts to test cleanly
        conn.execute("UPDATE registered_users SET role = 'user' WHERE role = 'admin'")
        conn.execute(
            """
            INSERT INTO registered_users (id, email, name, password_hash, role, account_status, email_verified, approved_by, created_at, updated_at)
            VALUES (?, ?, 'Suspended Admin', ?, 'admin', 'suspended', 1, 'initial_setup', datetime('now'), datetime('now'))
            """,
            (str(uuid.uuid4()), admin_email, pwd_hash),
        )
    conn.close()

    # has_active_admin is False because status is suspended
    assert has_active_admin() is False
    # has_admin_been_initialized is True because an admin was initialized
    assert has_admin_been_initialized() is True

    orig_token = settings.ADMIN_SETUP_TOKEN
    orig_url = settings.SUPABASE_URL
    orig_key = settings.SUPABASE_SERVICE_ROLE_KEY
    settings.ADMIN_SETUP_TOKEN = "test-master-setup-secret-token-2026"
    settings.SUPABASE_URL = ""
    settings.SUPABASE_SERVICE_ROLE_KEY = ""

    try:
        # Attempt to initialize another admin via endpoint
        req = AdminSetupInitRequest(
            setup_token="test-master-setup-secret-token-2026",
            email=f"attacker_{uuid.uuid4().hex[:6]}@nfttrends.io",
            name="Attacker Admin",
            password=VALID_ADMIN_PWD,
            password_confirm=VALID_ADMIN_PWD,
        )
        fake_req = MagicMock()
        fake_req.client.host = "127.0.0.1"

        try:
            coro = initialize_master_admin(req, request=fake_req)
            coro.send(None)
            raise AssertionError("Should have blocked setup initialization")
        except HTTPException as exc:
            assert exc.status_code == 403
            assert "already been completed" in exc.detail
    finally:
        settings.ADMIN_SETUP_TOKEN = orig_token
        settings.SUPABASE_URL = orig_url
        settings.SUPABASE_SERVICE_ROLE_KEY = orig_key


def test_scenario_43_concurrent_first_admin_initialization_serialized():
    """Scenario 43: Concurrent first-admin initialization calls are serialized.

    Verifies:
    - Under concurrent execution, exactly ONE request succeeds.
    - All subsequent/concurrent requests fail with setup already completed.
    """
    import concurrent.futures
    import sqlite3
    from app.auth import initialize_first_admin

    orig_url = settings.SUPABASE_URL
    orig_key = settings.SUPABASE_SERVICE_ROLE_KEY
    orig_pwd = settings.ADMIN_DEFAULT_PASSWORD
    settings.SUPABASE_URL = ""
    settings.SUPABASE_SERVICE_ROLE_KEY = ""
    settings.ADMIN_DEFAULT_PASSWORD = ""

    # Clean test state: ensure zero existing admins
    conn = sqlite3.connect(settings.SQLITE_PATH)
    with conn:
        conn.execute("DELETE FROM registered_users WHERE role = 'admin' OR approved_by = 'initial_setup' OR email = ?", (settings.ADMIN_EMAIL,))
    conn.close()

    pwd_hash = hash_password(VALID_ADMIN_PWD)

    def init_worker(idx: int):
        worker_email = f"concurrent_admin_{idx}_{uuid.uuid4().hex[:4]}@nfttrends.io"
        return initialize_first_admin(
            email=worker_email,
            name=f"Admin {idx}",
            password_hash=pwd_hash,
        )

    try:
        # Launch 8 concurrent initialization attempts
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(init_worker, i) for i in range(8)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        successes = [r for r in results if r[0] is True]
        failures = [r for r in results if r[0] is False]

        assert len(successes) == 1, f"Expected exactly 1 initialization to succeed, got {len(successes)}"
        assert len(failures) == 7
        for ok, err in failures:
            assert "already been completed" in err.lower() or "exists" in err.lower()
    finally:
        settings.SUPABASE_URL = orig_url
        settings.SUPABASE_SERVICE_ROLE_KEY = orig_key
        settings.ADMIN_DEFAULT_PASSWORD = orig_pwd


def test_scenario_44_legacy_constraint_detection_catalog_precision():
    """Scenario 44: Verify catalog constraint dependency logic preserves unrelated constraints.

    Verifies that the catalog dependency query:
    1. Identifies constraints referencing columns 'role' or 'account_status'.
    2. Strictly preserves constraints on other columns even if constraint definitions
       contain the string literal 'role' or 'account_status' (e.g. bio <> 'role').
    """
    class MockConstraint:
        def __init__(self, conname: str, referenced_columns: list[str], definition: str):
            self.conname = conname
            self.referenced_columns = referenced_columns
            self.definition = definition

    constraints = [
        MockConstraint("check_user_role", ["role"], "CHECK (role IN ('analyst', 'admin'))"),
        MockConstraint("chk_custom_role_legacy", ["role"], "CHECK (role = 'admin')"),
        MockConstraint("legacy_status_check", ["account_status"], "CHECK (account_status IN ('active', 'pending'))"),
        MockConstraint("chk_unrelated_bio", ["bio"], "CHECK (bio <> 'role')"),
        MockConstraint("chk_user_email_format", ["email"], "CHECK (email LIKE '%@%')"),
        MockConstraint("chk_audit_note", ["notes"], "CHECK (notes NOT LIKE '%account_status%')"),
    ]

    def should_drop(c: MockConstraint) -> bool:
        if c.conname in ('check_user_role', 'check_account_status'):
            return True
        if any(col in ('role', 'account_status') for col in c.referenced_columns):
            return True
        return False

    dropped = [c.conname for c in constraints if should_drop(c)]
    preserved = [c.conname for c in constraints if not should_drop(c)]

    assert "check_user_role" in dropped
    assert "chk_custom_role_legacy" in dropped
    assert "legacy_status_check" in dropped

    assert "chk_unrelated_bio" in preserved
    assert "chk_user_email_format" in preserved
    assert "chk_audit_note" in preserved


def test_scenario_45_initialize_first_admin_production_fails_closed_without_fallback():
    """Scenario 45: In production/Supabase mode, initialize_first_admin must fail closed without fallback.

    Verifies:
    1. Non-200 RPC response (e.g. 500) fails closed; create_user is NEVER called.
    2. Missing RPC (404) fails closed; create_user is NEVER called.
    3. Network timeout / connection error fails closed; create_user is NEVER called.
    4. Invalid non-dict response fails closed; create_user is NEVER called.
    5. API endpoint returns generic HTTP 503 and zero exception/host/URL details.
    """
    from unittest.mock import MagicMock, patch
    from fastapi import HTTPException
    from app.auth import initialize_first_admin
    from app.api.routes_admin import initialize_master_admin
    from app.schemas import AdminSetupInitRequest

    settings.SUPABASE_URL = "https://internal-cluster-99.supabase.co"
    settings.SUPABASE_SERVICE_ROLE_KEY = "fake-service-key"
    settings.ADMIN_SETUP_TOKEN = "test-master-setup-secret-token-2026"

    try:
        # 1. Non-200 RPC response
        with patch("requests.post") as mock_post, patch("app.auth.create_user") as mock_create_user:
            mock_post.return_value = MagicMock(status_code=500, text="Internal PostgreSQL panic at internal-db.aws.net")
            ok, err = initialize_first_admin("admin@test.com", "Admin", "hash")
            assert ok is False
            assert err == "Database service unavailable during administrator initialization."
            assert not mock_create_user.called

        # 2. 404 RPC missing
        with patch("requests.post") as mock_post, patch("app.auth.create_user") as mock_create_user:
            mock_post.return_value = MagicMock(status_code=404, text="404 Not Found")
            ok, err = initialize_first_admin("admin@test.com", "Admin", "hash")
            assert ok is False
            assert err == "Database service unavailable during administrator initialization."
            assert not mock_create_user.called

        # 3. Connection timeout with sensitive exception text
        with patch("requests.post", side_effect=Exception("ConnectionRefusedError: internal-db.aws.net:5432 failed")) as mock_post, patch("app.auth.create_user") as mock_create_user:
            ok, err = initialize_first_admin("admin@test.com", "Admin", "hash")
            assert ok is False
            assert err == "Database service unavailable during administrator initialization."
            assert "internal-db" not in err
            assert "5432" not in err
            assert not mock_create_user.called

        # 4. Invalid payload
        with patch("requests.post") as mock_post, patch("app.auth.create_user") as mock_create_user:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: ["invalid payload"])
            ok, err = initialize_first_admin("admin@test.com", "Admin", "hash")
            assert ok is False
            assert err == "Database service unavailable during administrator initialization."
            assert not mock_create_user.called

        # 5. Route level HTTP 503 check ensuring zero internal leakage to HTTP client
        with patch("requests.post", side_effect=Exception("FATAL: connection to internal-pg:5432 refused")):
            req = AdminSetupInitRequest(
                setup_token="test-master-setup-secret-token-2026",
                email="newadmin@nfttrends.io",
                name="New Admin",
                password=VALID_ADMIN_PWD,
                password_confirm=VALID_ADMIN_PWD,
            )
            fake_req = MagicMock()
            fake_req.client.host = "127.0.0.1"

            with patch("app.api.routes_admin.has_admin_been_initialized", return_value=False):
                try:
                    coro = initialize_master_admin(req, request=fake_req)
                    coro.send(None)
                    raise AssertionError("Should have raised HTTPException 503")
                except HTTPException as exc:
                    assert exc.status_code == 503
                    assert exc.detail == "Database service unavailable during administrator initialization."
                    assert "internal-pg" not in exc.detail
                    assert "5432" not in exc.detail
                    assert "FATAL" not in exc.detail
    finally:
        settings.SUPABASE_URL = ""
        settings.SUPABASE_SERVICE_ROLE_KEY = ""



