"""Automated tests for user registration, input validation, and account persistence."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

import pytest

import auth
from user_store import (
    DEFAULT_SQLITE_PATH,
    get_all_users,
    get_database_config,
    get_registered_user,
    get_storage_info,
    init_sqlite_db,
    normalize_email,
    register_user,
    validate_registration_inputs,
)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database path for isolated testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = Path(f.name)
    init_sqlite_db(temp_path)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


def test_normalize_email():
    assert normalize_email("  User@Example.COM  ") == "user@example.com"
    assert normalize_email("analyst@nfttrends.io") == "analyst@nfttrends.io"


def test_validate_registration_inputs_success():
    valid, msg = validate_registration_inputs(
        email="analyst@firm.com",
        name="Jane Analyst",
        password="SecurePass2026!",
        password_confirm="SecurePass2026!",
    )
    assert valid is True
    assert msg == ""


def test_validate_registration_inputs_catches_errors():
    # Empty name
    valid, msg = validate_registration_inputs("", "   ", "SecurePass2026!", "SecurePass2026!")
    assert valid is False
    assert "name" in msg.lower()

    # Invalid email
    valid, msg = validate_registration_inputs("not-an-email", "Jane Doe", "SecurePass2026!", "SecurePass2026!")
    assert valid is False
    assert "email" in msg.lower()

    # Short password
    valid, msg = validate_registration_inputs("jane@firm.com", "Jane Doe", "short1!", "short1!")
    assert valid is False
    assert "8 characters" in msg.lower()

    # Weak password (letters only)
    valid, msg = validate_registration_inputs("jane@firm.com", "Jane Doe", "passwordonly", "passwordonly")
    assert valid is False
    assert "number or special character" in msg.lower()

    # Password mismatch
    valid, msg = validate_registration_inputs("jane@firm.com", "Jane Doe", "SecurePass2026!", "DifferentPass2026!")
    assert valid is False
    assert "match" in msg.lower()


def test_register_user_success_and_retrieval(temp_db):
    test_email = "newanalyst@firm.com"
    test_pwd = "StrongPassword#2026"
    test_name = "Alex Research"

    success, msg = register_user(
        email=test_email,
        name=test_name,
        password=test_pwd,
        password_confirm=test_pwd,
        db_path=temp_db,
    )
    assert success is True
    assert "successfully" in msg.lower()

    user = get_registered_user(test_email, db_path=temp_db)
    assert user is not None
    assert user["email"] == test_email
    assert user["name"] == test_name
    assert user["role"] == "analyst"  # Cannot escalate to admin
    assert user["password_hash"].startswith("pbkdf2_sha256$600000$")
    assert auth.verify_password(test_pwd, user["password_hash"]) is True


def test_register_duplicate_email_fails(temp_db):
    test_email = "duplicate@firm.com"
    test_pwd = "StrongPassword#2026"

    # First registration
    s1, _ = register_user(test_email, "User One", test_pwd, test_pwd, db_path=temp_db)
    assert s1 is True

    # Second registration with same email (different case)
    s2, msg2 = register_user("DUPLICATE@firm.com", "User Two", test_pwd, test_pwd, db_path=temp_db)
    assert s2 is False
    assert "already registered" in msg2.lower()


def test_register_duplicate_with_configured_secrets_admin_fails(temp_db):
    with patch("auth.get_configured_users", return_value={"admin@nfttrends.io": {"role": "admin"}}):
        success, msg = register_user(
            "admin@nfttrends.io",
            "Imposter Admin",
            "StrongPassword#2026",
            "StrongPassword#2026",
            db_path=temp_db,
        )
        assert success is False
        assert "already registered" in msg.lower()


def test_storage_info_reporting():
    with patch("user_store.get_database_config", return_value={"type": "sqlite", "path": DEFAULT_SQLITE_PATH}):
        info = get_storage_info()
        assert "SQLite" in info["backend"]
        assert info["is_cloud_persistent"] is False

    with patch("user_store.get_database_config", return_value={"type": "supabase", "url": "https://xyz.supabase.co", "key": "key"}):
        info_cloud = get_storage_info()
        assert "Supabase" in info_cloud["backend"]
        assert info_cloud["is_cloud_persistent"] is True


# ==============================================================================
# Supabase Cloud Backend Mock Tests (Success, Permission, Network, Malformed)
# ==============================================================================

MOCK_SUPABASE_CFG = {
    "type": "supabase",
    "url": "https://mock-app.supabase.co",
    "key": "mock-service-role-key-12345",
}


def test_supabase_get_user_found():
    """Valid HTTP 200 response with user row returns normalized dictionary."""
    from user_store import _supabase_get_user

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "id": "uuid-123",
            "email": "RESEARCHER@FIRM.COM",
            "name": "Jane Researcher",
            "password_hash": "pbkdf2_sha256$600000$...",
            "role": "analyst",
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]

    with patch("requests.get", return_value=mock_resp):
        user = _supabase_get_user("researcher@firm.com", MOCK_SUPABASE_CFG)
        assert user is not None
        assert user["email"] == "researcher@firm.com"
        assert user["name"] == "Jane Researcher"
        assert user["role"] == "analyst"


def test_supabase_get_user_not_found_returns_none():
    """HTTP 200 with empty list [] correctly indicates user does not exist."""
    from user_store import _supabase_get_user

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []

    with patch("requests.get", return_value=mock_resp):
        user = _supabase_get_user("nonexistent@firm.com", MOCK_SUPABASE_CFG)
        assert user is None


def test_supabase_get_user_permission_denied_raises_exception():
    """HTTP 401 or 403 must raise DatabasePermissionError, NEVER returning None (user not found)."""
    import pytest
    from user_store import DatabasePermissionError, _supabase_get_user

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(DatabasePermissionError, match="access denied"):
            _supabase_get_user("analyst@firm.com", MOCK_SUPABASE_CFG)


def test_supabase_get_user_server_error_raises_storage_error():
    """HTTP 500 server error must raise StorageError, NEVER returning None."""
    import pytest
    from user_store import StorageError, _supabase_get_user

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal server error in PostgreSQL cluster"

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(StorageError, match="query failed with HTTP 500"):
            _supabase_get_user("analyst@firm.com", MOCK_SUPABASE_CFG)


def test_supabase_get_user_timeout_raises_connection_error():
    """Connection timeout must raise DatabaseConnectionError."""
    import pytest
    import requests
    from user_store import DatabaseConnectionError, _supabase_get_user

    with patch("requests.get", side_effect=requests.Timeout("Connection timed out")):
        with pytest.raises(DatabaseConnectionError, match="connection failed"):
            _supabase_get_user("analyst@firm.com", MOCK_SUPABASE_CFG)


def test_supabase_get_user_malformed_json_raises_response_error():
    """Malformed or invalid JSON payload must raise DatabaseResponseError."""
    import pytest
    from user_store import DatabaseResponseError, _supabase_get_user

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON string")

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(DatabaseResponseError, match="returned invalid JSON"):
            _supabase_get_user("analyst@firm.com", MOCK_SUPABASE_CFG)


def test_supabase_cloud_mode_never_falls_back_to_sqlite():
    """When Supabase is configured, lookup errors must NOT silently fall back to local SQLite."""
    import pytest
    from user_store import DatabaseConnectionError, get_registered_user

    with patch("user_store.get_database_config", return_value=MOCK_SUPABASE_CFG):
        with patch("user_store._supabase_get_user", side_effect=DatabaseConnectionError("Cloud offline")):
            with patch("user_store._sqlite_get_user") as mock_sqlite:
                with pytest.raises(DatabaseConnectionError):
                    get_registered_user("cloud_user@firm.com")
                # Ensure SQLite was NEVER called
                mock_sqlite.assert_not_called()


def test_supabase_insert_duplicate_returns_clear_failure():
    """HTTP 409 duplicate or unique violation reports duplicate email safely."""
    from user_store import _supabase_insert_user

    mock_resp = MagicMock()
    mock_resp.status_code = 409
    mock_resp.text = '{"message": "duplicate key value violates unique constraint"}'

    with patch("requests.post", return_value=mock_resp):
        success, msg = _supabase_insert_user(
            "dup@firm.com",
            "Jane",
            "hash123",
            "analyst",
            MOCK_SUPABASE_CFG,
        )
        assert success is False
        assert "already registered" in msg.lower()


def test_supabase_insert_permission_denied_raises_exception():
    """HTTP 403 on insert must raise DatabasePermissionError."""
    import pytest
    from user_store import DatabasePermissionError, _supabase_insert_user

    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(DatabasePermissionError):
            _supabase_insert_user(
                "new@firm.com",
                "Jane",
                "hash123",
                "analyst",
                MOCK_SUPABASE_CFG,
            )


def test_concurrent_duplicate_registration_protection(temp_db):
    """Thread lock prevents race conditions during simultaneous registrations with the same email."""
    import threading

    results = []

    def attempt_reg(thread_name):
        ok, msg = register_user(
            "concurrent@firm.com",
            thread_name,
            "SecurePass2026!",
            "SecurePass2026!",
            db_path=temp_db,
        )
        results.append((ok, msg))

    t1 = threading.Thread(target=attempt_reg, args=("Thread 1",))
    t2 = threading.Thread(target=attempt_reg, args=("Thread 2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one thread succeeds, the other is rejected as duplicate
    successes = [r for r in results if r[0] is True]
    failures = [r for r in results if r[0] is False]
    assert len(successes) == 1
    assert len(failures) == 1
    assert "already registered" in failures[0][1].lower()
