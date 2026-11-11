"""Pytest fixtures and environment configuration for NFT Trend Analyzer test suite."""

import os
from pathlib import Path
import pytest

# Configure test environment variables before importing app modules
os.environ["ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key-for-automated-qa-testing-minimum-32chars"
os.environ["ADMIN_SETUP_TOKEN"] = "test-master-setup-secret-token-2026"
os.environ["ADMIN_DEFAULT_PASSWORD"] = "Admin#NFT2026!"
# In local test suite, disable live Supabase remote network calls to use fast local SQLite store
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""

from app.config import settings
from app.auth import (
    init_user_db,
    init_reset_token_db,
    init_activity_log_db,
    init_admin_verification_token_db,
)

@pytest.fixture(autouse=True)
def setup_test_databases():
    """Ensure test database tables are provisioned."""
    init_user_db()
    init_reset_token_db()
    init_activity_log_db()
    init_admin_verification_token_db()
    try:
        import sqlite3
        conn = sqlite3.connect(settings.SQLITE_PATH)
        with conn:
            conn.execute(
                "UPDATE registered_users SET account_status = 'active', email_verified = 1 WHERE email = ?",
                (settings.ADMIN_EMAIL,),
            )
        conn.close()
    except Exception:
        pass
    yield
