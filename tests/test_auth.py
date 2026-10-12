"""Tests for authentication, PBKDF2 hashing, HMAC session tokens, and access control."""

from pathlib import Path
import time
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from auth import (
    AUTH_EXPIRY_KEY,
    AUTH_SESSION_KEY,
    _MODULE_EPHEMERAL_SECRET,
    authenticate_user,
    create_session_token,
    get_configured_users,
    get_cookie_secret,
    get_users,
    hash_password,
    verify_password,
    verify_session_token,
)
from nft_analysis import make_synthetic_demo_data


def test_hash_password_and_verify():
    pwd = "research-secret-pass-2026"
    stored_hash = hash_password(pwd)
    assert stored_hash.startswith("pbkdf2_sha256$600000$")
    assert verify_password(pwd, stored_hash) is True
    assert verify_password("wrong-password", stored_hash) is False
    assert verify_password("", stored_hash) is False


def test_verify_password_handles_corrupt_format():
    assert verify_password("pwd", "not_a_valid_hash") is False
    assert verify_password("pwd", "pbkdf2_sha256$invalid") is False
    assert verify_password("pwd", "") is False


def test_session_token_create_and_verify():
    secret_key = "test-hmac-secret-key-32-chars-long"
    token = create_session_token(
        email="analyst@nfttrends.io",
        name="Lead Analyst",
        role="senior_researcher",
        expires_in=3600,
        secret_key=secret_key,
    )
    assert "." in token
    payload = verify_session_token(token, secret_key=secret_key)
    assert payload is not None
    assert payload["email"] == "analyst@nfttrends.io"
    assert payload["name"] == "Lead Analyst"
    assert payload["role"] == "senior_researcher"
    assert payload["exp"] > time.time()


def test_session_token_rejects_tampered_payload_or_signature():
    secret_key = "test-hmac-secret-key-32-chars-long"
    token = create_session_token("analyst@nfttrends.io", "Lead Analyst", secret_key=secret_key)
    b64_payload, sig = token.split(".", 1)

    # Tampered signature
    assert verify_session_token(f"{b64_payload}.fake_signature", secret_key=secret_key) is None

    # Tampered payload
    tampered_payload = b64_payload[:-1] + "A"
    assert verify_session_token(f"{tampered_payload}.{sig}", secret_key=secret_key) is None

    # Wrong secret key
    assert verify_session_token(token, secret_key="different-secret-key") is None


def test_session_token_rejects_expired_token():
    secret_key = "test-hmac-secret-key-32-chars-long"
    # Create an expired token (expires_in = -10 seconds)
    token = create_session_token(
        email="analyst@nfttrends.io",
        name="Lead Analyst",
        expires_in=-10,
        secret_key=secret_key,
    )
    assert verify_session_token(token, secret_key=secret_key) is None


def test_authentication_fails_safely_when_secrets_empty():
    """When secrets are empty, no fallback administrator is created and setup error is returned."""
    with patch("auth._load_disk_secrets", return_value={}):
        with patch.object(st, "secrets", {}, create=True):
            assert get_configured_users() == {}
            assert get_users() == {}
            success, msg = authenticate_user("admin@nfttrends.io", "Admin#NFT2026!")
            assert success is False
            assert "Authentication setup required" in str(msg)


def test_cookie_secret_fallback_ephemeral_when_secrets_empty():
    """When no cookie secret is configured in secrets, get_cookie_secret returns the secure ephemeral secret."""
    with patch("auth._load_disk_secrets", return_value={}):
        with patch.object(st, "secrets", {}, create=True):
            secret = get_cookie_secret()
            assert secret == _MODULE_EPHEMERAL_SECRET
            assert len(secret) >= 32


def test_local_secrets_loads_custom_administrator():
    """The local .streamlit/secrets.toml loads the custom admin account."""
    users = get_configured_users()
    assert "admin@nfttrends.io" in users
    success, res = authenticate_user("admin@nfttrends.io", "Admin#NFT2026!")
    assert success is True
    assert res["email"] == "admin@nfttrends.io"


def test_authenticate_user_with_custom_secrets_credentials():
    """Custom credentials configured in secrets can authenticate successfully."""
    test_email = "admin@nfttrends.io"
    test_password = "Admin#NFT2026!"
    test_hash = hash_password(test_password)

    mock_users = {
        test_email: {
            "email": test_email,
            "name": "System Administrator",
            "password_hash": test_hash,
            "role": "admin",
        }
    }

    with patch("auth.get_configured_users", return_value=mock_users):
        success, res = authenticate_user(test_email, test_password)
        assert success is True
        assert isinstance(res, dict)
        assert res["email"] == test_email
        assert res["role"] == "admin"

        # Wrong password
        failed, msg = authenticate_user(test_email, "wrong-admin-pass")
        assert failed is False
        assert "Invalid email" in str(msg)

        # Unknown user
        unknown, msg = authenticate_user("stranger@nowhere.com", "any-pass")
        assert unknown is False
        assert "Invalid email" in str(msg)

        # Empty inputs
        empty, msg = authenticate_user("", "")
        assert empty is False


def test_unauthenticated_app_access_blocks_dashboard():
    """Unauthenticated users should only see the login form and NOT the dashboard title."""
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
    app.run()

    # The dashboard title should not render because st.stop() halts before it
    dashboard_title = "Analysis of Trending NFTs Using Time-Series Data and Machine Learning"
    assert not any(title.value == dashboard_title for title in app.title)

    # The login card text or input fields should be rendered
    assert len(app.text_input) >= 1


def test_authenticated_app_access_renders_dashboard():
    """Authenticated users with valid HMAC session token can access the dashboard."""
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
    valid_token = create_session_token("analyst@nfttrends.io", "Senior Analyst")
    app.session_state[AUTH_SESSION_KEY] = valid_token
    app.session_state["dataset"] = make_synthetic_demo_data()
    app.session_state["dataset_signature"] = "test-sig"
    app.session_state["date_col"] = "sale_date"
    app.session_state["price_col"] = "price_eth"
    app.session_state["sales_col"] = "sales_count"
    app.run()

    assert not app.exception
    dashboard_title = "Analysis of Trending NFTs Using Time-Series Data and Machine Learning"
    assert any(title.value == dashboard_title for title in app.title)


def test_session_expiration_displays_warning():
    """When a session is expired, the login page displays a session expiration notice."""
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
    # Set expired token
    expired_token = create_session_token("analyst@nfttrends.io", "Senior Analyst", expires_in=-50)
    app.session_state[AUTH_SESSION_KEY] = expired_token
    app.run()

    # The token should be invalidated and warning displayed
    assert AUTH_SESSION_KEY not in app.session_state or app.session_state.get(AUTH_EXPIRY_KEY) is True
    dashboard_title = "Analysis of Trending NFTs Using Time-Series Data and Machine Learning"
    assert not any(title.value == dashboard_title for title in app.title)
    assert any("expired" in str(warning.value).lower() for warning in app.warning)


def test_oidc_mocked_identity_provider_login():
    """Mocking an OpenID Connect identity provider authenticates the user seamlessly."""
    from unittest.mock import MagicMock
    from auth import get_current_user

    mock_user = MagicMock()
    mock_user.is_logged_in = True
    mock_user.email = "sso_researcher@enterprise.org"
    mock_user.name = "SSO Lead Researcher"

    with patch("streamlit.user", mock_user, create=True):
        current = get_current_user()
        assert current is not None
        assert current["email"] == "sso_researcher@enterprise.org"
        assert current["name"] == "SSO Lead Researcher"
        assert current["provider"] == "oidc"


def test_logout_user_clears_session_state():
    """logout_user removes active credentials and session tokens."""
    from auth import logout_user

    # Populate session state
    st_mock = {
        AUTH_SESSION_KEY: "dummy-token",
        AUTH_EXPIRY_KEY: True,
        "dataset": "dummy-dataframe",
        "dataset_signature": "sig-123",
    }
    with patch("streamlit.session_state", st_mock):
        with patch("streamlit.rerun"):
            logout_user()
            assert AUTH_SESSION_KEY not in st_mock
            assert AUTH_EXPIRY_KEY not in st_mock
            assert "dataset" not in st_mock
            assert "dataset_signature" not in st_mock


def test_interactive_login_form_submission_on_localhost():
    """Simulates typing admin@nfttrends.io and Admin#NFT2026! on localhost login form and clicking sign in."""
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
    app.run()
    # Fill in the email and password inputs
    app.text_input[0].input("admin@nfttrends.io")
    app.text_input[1].input("Admin#NFT2026!")
    # Click the sign-in button
    app.button[0].click().run()

    # After login, the dashboard title renders and token is in session_state
    dashboard_title = "Analysis of Trending NFTs Using Time-Series Data and Machine Learning"
    assert any(title.value == dashboard_title for title in app.title)
    assert AUTH_SESSION_KEY in app.session_state


def test_authenticate_registered_user_from_db(tmp_path):
    """Verify that a newly registered user in an isolated persistent store can log in successfully."""
    import uuid
    from user_store import init_sqlite_db, register_user

    test_db = tmp_path / "auth_test.db"
    init_sqlite_db(test_db)

    test_email = f"analyst_{uuid.uuid4().hex[:8]}@nfttrends.io"
    test_password = "RegisteredPass2026!"

    # Register user into isolated database
    reg_ok, msg = register_user(
        test_email,
        "Registered Analyst",
        test_password,
        test_password,
        db_path=test_db,
    )
    assert reg_ok is True, f"Registration failed: {msg}"

    # Authenticate user from isolated database
    auth_ok, user_data = authenticate_user(test_email, test_password, db_path=test_db)
    assert auth_ok is True
    assert isinstance(user_data, dict)
    assert user_data["email"] == test_email
    assert user_data["role"] == "analyst"

    # Reject invalid password for registered user
    fail_ok, fail_msg = authenticate_user(test_email, "WrongPassword!", db_path=test_db)
    assert fail_ok is False
    assert "Invalid email address or password" in str(fail_msg)


def test_production_mode_detection():
    """Verify is_production_mode detects cloud environment variables and secret settings."""
    from auth import is_production_mode

    # Local dev defaults to False
    with patch.dict("os.environ", {}, clear=True):
        assert is_production_mode() is False

    # Environment variables
    with patch.dict("os.environ", {"STREAMLIT_COMMUNITY_CLOUD": "1"}):
        assert is_production_mode() is True

    with patch.dict("os.environ", {"ENV": "production"}):
        assert is_production_mode() is True


def test_production_rejects_missing_cookie_secret():
    """Production mode must raise RuntimeError if cookie secret is missing."""
    import pytest
    from auth import get_cookie_secret

    with patch("auth.is_production_mode", return_value=True):
        with patch.dict("os.environ", {}, clear=True):
            with patch("auth._load_disk_secrets", return_value={}):
                with patch("streamlit.secrets", {}, create=True):
                    with pytest.raises(RuntimeError, match="Production deployment requires a configured"):
                        get_cookie_secret()


def test_production_rejects_compromised_cookie_secret():
    """Production mode must reject previously exposed compromised secrets."""
    import pytest
    from auth import get_cookie_secret

    compromised = "4f8a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a"
    mock_secrets = {"auth": {"cookie_secret": compromised}}

    with patch("auth.is_production_mode", return_value=True):
        with patch("streamlit.secrets", mock_secrets, create=True):
            with pytest.raises(RuntimeError, match="compromised"):
                get_cookie_secret()


def test_production_rejects_placeholder_cookie_secret():
    """Production mode must reject template placeholder secrets."""
    import pytest
    from auth import get_cookie_secret

    mock_secrets = {"auth": {"cookie_secret": "replace-with-a-random-hex-string-run-openssl-rand-hex-32"}}

    with patch("auth.is_production_mode", return_value=True):
        with patch("streamlit.secrets", mock_secrets, create=True):
            with pytest.raises(RuntimeError, match="placeholder"):
                get_cookie_secret()


def test_production_accepts_valid_rotated_secret():
    """Production mode accepts a secure rotated 32-byte (64-hex-char) secret."""
    from auth import get_cookie_secret

    valid_secret = "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0"
    mock_secrets = {"auth": {"cookie_secret": valid_secret}}

    with patch("auth.is_production_mode", return_value=True):
        with patch("streamlit.secrets", mock_secrets, create=True):
            sec = get_cookie_secret()
            assert sec == valid_secret


def test_local_dev_ephemeral_fallback():
    """Local development safely derives an in-process ephemeral secret without crashing."""
    from auth import get_cookie_secret

    with patch("auth.is_production_mode", return_value=False):
        with patch.dict("os.environ", {}, clear=True):
            with patch("auth._load_disk_secrets", return_value={}):
                with patch("streamlit.secrets", {}, create=True):
                    sec = get_cookie_secret()
                    assert isinstance(sec, str)
                    assert len(sec) == 64


def test_authenticate_propagates_database_permission_error():
    """When the cloud database denies access (HTTP 401/403), authenticate_user returns a clear message."""
    from auth import authenticate_user
    import user_store

    with patch("auth.get_configured_users", return_value={}):
        with patch("user_store.get_registered_user", side_effect=user_store.DatabasePermissionError("401 Unauthorized")):
            ok, msg = authenticate_user("analyst@firm.com", "SecretPass123!")
            assert ok is False
            assert "Authentication service unavailable" in str(msg)
            assert "permission error" in str(msg).lower()


def test_authenticate_propagates_database_connection_error():
    """When the cloud database times out or is unreachable, authenticate_user returns an explicit error."""
    from auth import authenticate_user
    import user_store

    with patch("auth.get_configured_users", return_value={}):
        with patch("user_store.get_registered_user", side_effect=user_store.DatabaseConnectionError("Connection timed out")):
            ok, msg = authenticate_user("analyst@firm.com", "SecretPass123!")
            assert ok is False
            assert "Authentication service unavailable" in str(msg)
            assert "connection error" in str(msg).lower()
