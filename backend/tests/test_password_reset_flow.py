"""Comprehensive test suite for password reset, email dispatch, and token lifecycle.

Verifies:
1. Forgot-password returns generic success for non-existent users (enumeration defense).
2. Forgot-password dispatches email via Resend with URL-encoded token and email parameters.
3. Resend sandbox/domain errors (HTTP 403) are logged with provider error details while returning generic 200.
4. Requesting a new reset token invalidates any prior unconsumed tokens for that user.
5. Successful password reset updates the hash so login with the new password succeeds.
6. Login with the old password fails immediately after reset.
7. Replaying a consumed token is rejected (atomic single-use enforcement).
8. Expired tokens are rejected.
9. Password policy violations (weak password, mismatched confirmation) are rejected.
"""

from __future__ import annotations

import datetime
import json
import logging
import urllib.parse
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests import conftest  # Ensure test database and environment initialization
from app.main import app
from app.auth import (
    create_password_reset_token,
    consume_password_reset_token,
    create_user,
    get_user_by_email,
    hash_password,
    update_user_password,
    verify_password,
)
from app.config import settings

client = TestClient(app)

INITIAL_PWD = "Original#Pwd2026!Alpha"
NEW_PWD = "Updated#Pwd2026!OmegaShield"


@pytest.fixture
def test_user():
    """Create a unique regular user for testing."""
    email = f"analyst_{uuid.uuid4().hex[:8]}@nfttrends.io"
    name = "Test Analyst"
    pwd_hash = hash_password(INITIAL_PWD)
    ok, msg = create_user(
        email=email,
        name=name,
        password_hash=pwd_hash,
        role="user",
        account_status="active",
        email_verified=True,
    )
    assert ok, f"User creation failed: {msg}"
    return {"email": email, "name": name, "password": INITIAL_PWD}


def test_forgot_password_nonexistent_email_returns_generic_success():
    """SEC-01: Non-existent email returns generic success without leaking user existence."""
    with patch("requests.post") as mock_post:
        res = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent_ghost_user_999@example.com"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "password reset instructions" in data["message"].lower()
        # Ensure email provider was never contacted
        mock_post.assert_not_called()


def test_forgot_password_dispatches_email_with_token_and_email_params(test_user):
    """Email is dispatched via provider with link containing both token and email parameters."""
    captured_payloads = []

    def mock_requests_post(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {"id": "resend_msg_test_123"}
        mock_res.text = json.dumps({"id": "resend_msg_test_123"})
        if "api.resend.com" in url:
            captured_payloads.append(kwargs.get("json", {}))
        return mock_res

    # Temporarily ensure EMAIL_PROVIDER_API_KEY is present
    original_key = settings.EMAIL_PROVIDER_API_KEY
    original_cfg = settings.EMAIL_PROVIDER_CONFIGURED
    settings.EMAIL_PROVIDER_API_KEY = "re_test_fake_key_123"
    settings.EMAIL_PROVIDER_CONFIGURED = True

    try:
        with patch("requests.post", side_effect=mock_requests_post):
            res = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": test_user["email"]},
            )
            assert res.status_code == 200
            assert res.json()["success"] is True

            assert len(captured_payloads) == 1
            payload = captured_payloads[0]
            assert payload["to"] == [test_user["email"]]
            assert "Reset Your NFT Trend Analyzer Password" in payload["subject"]

            # Verify reset link includes both token and email parameters
            encoded_email = urllib.parse.quote(test_user["email"])
            assert "/reset-password?token=" in payload["text"]
            assert f"email={encoded_email}" in payload["text"]
            assert "/reset-password?token=" in payload["html"]
            assert f"email={encoded_email}" in payload["html"]
    finally:
        settings.EMAIL_PROVIDER_API_KEY = original_key
        settings.EMAIL_PROVIDER_CONFIGURED = original_cfg


def test_forgot_password_handles_resend_sandbox_403_safely_and_logs(test_user, caplog):
    """When Resend returns 403 (sandbox mode restriction), user gets generic 200 and error is logged."""
    resend_error_body = {
        "statusCode": 403,
        "name": "validation_error",
        "message": "You can only send testing emails to your own email address (owner@example.com).",
    }

    def mock_requests_post(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 403
        mock_res.json.return_value = resend_error_body
        mock_res.text = json.dumps(resend_error_body)
        return mock_res

    original_key = settings.EMAIL_PROVIDER_API_KEY
    original_cfg = settings.EMAIL_PROVIDER_CONFIGURED
    settings.EMAIL_PROVIDER_API_KEY = "re_test_fake_key_123"
    settings.EMAIL_PROVIDER_CONFIGURED = True

    try:
        with caplog.at_level(logging.ERROR):
            with patch("requests.post", side_effect=mock_requests_post):
                res = client.post(
                    "/api/v1/auth/forgot-password",
                    json={"email": test_user["email"]},
                )
                # User-facing response stays generic 200 (does not leak email or internal failure)
                assert res.status_code == 200
                assert res.json()["success"] is True

                # Error log must include Resend's diagnostic message for Render observability
                assert any(
                    "You can only send testing emails to your own email address" in record.message
                    for record in caplog.records
                )
    finally:
        settings.EMAIL_PROVIDER_API_KEY = original_key
        settings.EMAIL_PROVIDER_CONFIGURED = original_cfg


def test_requesting_new_token_invalidates_prior_tokens(test_user):
    """When a new reset token is requested, any existing unconsumed tokens are invalidated."""
    token1 = create_password_reset_token(test_user["email"])
    assert token1 is not None

    token2 = create_password_reset_token(test_user["email"])
    assert token2 is not None
    assert token1 != token2

    # Attempt to consume token1 -> must fail because token2 invalidated it
    success1, msg1, _ = consume_password_reset_token(token1)
    assert not success1
    assert "already been used" in msg1.lower() or "unrecognized" in msg1.lower() or "consumed" in msg1.lower()

    # Attempt to consume token2 -> must succeed
    success2, msg2, email2 = consume_password_reset_token(token2)
    assert success2
    assert email2 == test_user["email"]


def test_full_password_reset_and_login_lifecycle(test_user):
    """Full lifecycle: forgot-password -> reset with token -> old password rejected -> new password logs in."""
    email = test_user["email"]

    # 1. Generate reset token
    token = create_password_reset_token(email)
    assert token is not None

    # 2. Reset password via endpoint
    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "new_password": NEW_PWD,
            "new_password_confirm": NEW_PWD,
        },
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] is True

    # 3. Old password must be rejected at login
    old_login = client.post(
        "/api/v1/auth/user/login",
        json={"email": email, "password": INITIAL_PWD},
    )
    assert old_login.status_code == 401

    # 4. New password must authenticate successfully
    new_login = client.post(
        "/api/v1/auth/user/login",
        json={"email": email, "password": NEW_PWD},
    )
    assert new_login.status_code == 200
    login_data = new_login.json()
    assert "access_token" in login_data
    assert login_data["user"]["email"] == email


def test_reused_reset_token_rejected_replay_protection(test_user):
    """SEC-04: Reset token cannot be reused once consumed."""
    email = test_user["email"]
    token = create_password_reset_token(email)

    # First reset succeeds
    res1 = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": NEW_PWD, "new_password_confirm": NEW_PWD},
    )
    assert res1.status_code == 200

    # Second reset with identical token must be rejected
    res2 = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "Another#Pwd2026!Second", "new_password_confirm": "Another#Pwd2026!Second"},
    )
    assert res2.status_code == 400
    assert "already been used" in res2.json()["detail"].lower() or "invalid" in res2.json()["detail"].lower()


def test_expired_reset_token_rejected(test_user):
    """Expired reset token is rejected."""
    email = test_user["email"]
    # Create token already expired in the past
    expired_token = create_password_reset_token(email, expires_delta=datetime.timedelta(seconds=-10))
    assert expired_token is not None

    res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": expired_token, "new_password": NEW_PWD, "new_password_confirm": NEW_PWD},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_password_policy_enforcement_on_reset(test_user):
    """Reset endpoint rejects passwords that violate policy or confirmation mismatch."""
    token = create_password_reset_token(test_user["email"])

    # Mismatched confirmation
    res_mismatch = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": NEW_PWD, "new_password_confirm": "DoesNotMatch#123"},
    )
    assert res_mismatch.status_code == 400
    assert "match" in res_mismatch.json()["detail"].lower()

    # Complexity violation: 12+ chars but missing numbers, special chars, uppercase
    res_no_complexity = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "alllowercaseletters", "new_password_confirm": "alllowercaseletters"},
    )
    assert res_no_complexity.status_code == 400

    # Weak password (<12 characters) triggers schema 422
    res_weak = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "Short#1", "new_password_confirm": "Short#1"},
    )
    assert res_weak.status_code in (400, 422)


def test_password_reset_zero_rows_patch_returns_500_and_no_success(test_user):
    """When update_user_password matches zero rows (returns empty list), reset_password returns HTTP 500 and not success."""
    email = test_user["email"]
    token = create_password_reset_token(email)
    assert token is not None

    def mock_patch(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        if "registered_users" in str(url):
            # Prefer: return=representation with 0 rows matched returns HTTP 200 with []
            mock_res.json.return_value = []
            mock_res.text = "[]"
        else:
            # Token consumption in password_reset_tokens succeeds
            mock_res.json.return_value = [{"jti": "mock_jti"}]
            mock_res.text = '[{"jti": "mock_jti"}]'
        return mock_res

    def mock_get(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = [{"id": "user-123", "email": email, "name": "Test User", "role": "user"}]
        mock_res.text = '[{"id": "user-123"}]'
        return mock_res

    with patch.object(settings, "IS_PRODUCTION", True), \
         patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock_service_key"), \
         patch("requests.patch", side_effect=mock_patch), \
         patch("requests.get", side_effect=mock_get):

        # Direct verification: update_user_password returns False when 0 rows returned
        assert update_user_password(email, "some_new_hash") is False

        # Endpoint verification: reset_password returns 500 and does NOT report success
        res = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": token,
                "new_password": NEW_PWD,
                "new_password_confirm": NEW_PWD,
            },
        )
        assert res.status_code == 500
        data = res.json()
        assert data.get("success") is not True
        assert "Failed to update password" in data.get("detail", "")


def test_admin_register_resend_sandbox_403_logs_clear_guidance(caplog):
    """Admin registration encountering Resend 403 logs actionable guidance and returns generic message in production."""
    email = f"admin_applicant_{uuid.uuid4().hex[:6]}@gmail.com"
    resend_error_body = {
        "statusCode": 403,
        "name": "validation_error",
        "message": "You can only send testing emails to your own email address (owner@example.com).",
    }

    def mock_requests_post(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 403
        mock_res.json.return_value = resend_error_body
        mock_res.text = json.dumps(resend_error_body)
        return mock_res

    original_key = settings.EMAIL_PROVIDER_API_KEY
    original_cfg = settings.EMAIL_PROVIDER_CONFIGURED

    settings.EMAIL_PROVIDER_API_KEY = "re_test_fake_key_123"
    settings.EMAIL_PROVIDER_CONFIGURED = True

    try:
        with caplog.at_level(logging.ERROR):
            with patch("requests.post", side_effect=mock_requests_post):
                res = client.post(
                    "/api/v1/auth/admin/register",
                    json={
                        "email": email,
                        "name": "New Admin Applicant",
                        "password": "Master#2026!TitaniumShield",
                        "password_confirm": "Master#2026!TitaniumShield",
                    },
                )
                assert res.status_code == 502
                assert "failed to dispatch" in res.json()["detail"].lower()

                # Verify actionable Render log guidance without exposing secrets
                assert any(
                    "Resend sandbox or unverified domain: verify a domain in Resend and set EMAIL_FROM" in record.message
                    for record in caplog.records
                )
    finally:
        settings.EMAIL_PROVIDER_API_KEY = original_key
        settings.EMAIL_PROVIDER_CONFIGURED = original_cfg


