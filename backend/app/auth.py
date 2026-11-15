"""Authentication, security, password policies, and JWT token management."""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import requests

from app.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Common weak passwords blacklist
COMMON_WEAK_PASSWORDS = {
    "password", "password123", "password1234", "admin123", "administrator",
    "qwerty123456", "123456789012", "welcome12345", "letmein12345",
    "nftanalytics", "nfttrendanalyzer", "crypto2026!", "blockchain1",
}


# ==============================================================================
# Password Cryptography & Validation
# ==============================================================================

def validate_password_strength(password: str, email: str = "", name: str = "") -> Tuple[bool, str]:
    """Validate enterprise password policy.

    Requirements:
    - >= 12 characters
    - Uppercase letter
    - Lowercase letter
    - Number (0-9)
    - Special character
    - Not in common weak passwords blacklist
    - No email handle or personal name inside password
    """
    pwd = str(password or "")
    if len(pwd) < 12:
        return False, "Password must be at least 12 characters long."
    if not any(c.isupper() for c in pwd):
        return False, "Password must include at least one uppercase letter (A-Z)."
    if not any(c.islower() for c in pwd):
        return False, "Password must include at least one lowercase letter (a-z)."
    if not any(c.isdigit() for c in pwd):
        return False, "Password must include at least one numeric digit (0-9)."
    if not any(not c.isalnum() for c in pwd):
        return False, "Password must include at least one special character (!@#$%^&*...)."
    if pwd.strip().lower() in COMMON_WEAK_PASSWORDS:
        return False, "This password is too common or easily guessable. Choose a stronger passphrase."

    clean_email = email.strip().lower()
    if clean_email and "@" in clean_email:
        handle = clean_email.split("@")[0]
        if len(handle) >= 3 and handle in pwd.lower():
            return False, "Password cannot contain parts of your email address."

    clean_name = str(name).strip().lower()
    if clean_name:
        for part in clean_name.split():
            if len(part) >= 3 and part in pwd.lower():
                return False, "Password cannot contain your personal name."

    return True, ""


def hash_password(password: str) -> str:
    """Hash password using salted bcrypt with cost factor 12."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password supporting bcrypt and legacy pbkdf2_sha256."""
    if not password or not stored_hash:
        return False

    # 1. Bcrypt hashes
    if stored_hash.startswith(("$2b$", "$2a$", "$2y$")):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception:
            return False

    # 2. PBKDF2-SHA256 hashes
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            parts = stored_hash.split("$")
            if len(parts) == 4:
                _, iter_str, salt_hex, target_hash = parts
                iterations = int(iter_str)
                salt_bytes = bytes.fromhex(salt_hex)
                computed = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt_bytes,
                    iterations,
                ).hex()
                return hmac.compare_digest(computed, target_hash)
        except Exception:
            return False

    return False


# ==============================================================================
# Database / User Store & Audit Logging
# ==============================================================================

GMAIL_REGEX = re.compile(r"^[\w\.\+-]+@(gmail\.com|googlemail\.com)$", re.IGNORECASE)

def is_valid_gmail(email: str) -> bool:
    """Validate that email belongs strictly to a valid Gmail / Googlemail domain."""
    if not email:
        return False
    return bool(GMAIL_REGEX.match(email.strip()))


# In-memory sliding window rate limiter
_RATE_LIMIT_STORE: Dict[str, list[float]] = {}

def check_rate_limit(key: str, max_requests: int = 15, window_seconds: int = 60) -> bool:
    """Sliding-window rate limiter per client key."""
    now = time.time()
    timestamps = _RATE_LIMIT_STORE.get(key, [])
    valid_ts = [t for t in timestamps if now - t < window_seconds]
    if len(valid_ts) >= max_requests:
        _RATE_LIMIT_STORE[key] = valid_ts
        return False
    valid_ts.append(now)
    _RATE_LIMIT_STORE[key] = valid_ts
    return True


def init_user_db() -> None:
    """Initialize local SQLite user table if Supabase is offline (dev only)."""
    if settings.IS_PRODUCTION:
        return  # SEC-02: Do NOT initialize local SQLite user tables in production

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS registered_users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    account_status TEXT NOT NULL DEFAULT 'active',
                    email_verified INTEGER NOT NULL DEFAULT 1,
                    approved_by TEXT,
                    approved_at TEXT,
                    updated_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            # Idempotently upgrade SQLite columns if table already existed from earlier versions
            cols_to_add = [
                ("role", "TEXT NOT NULL DEFAULT 'user'"),
                ("account_status", "TEXT NOT NULL DEFAULT 'active'"),
                ("email_verified", "INTEGER NOT NULL DEFAULT 1"),
                ("approved_by", "TEXT"),
                ("approved_at", "TEXT"),
                ("updated_at", "TEXT"),
            ]
            for col_name, col_def in cols_to_add:
                try:
                    conn.execute(f"ALTER TABLE registered_users ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Normalize any legacy 'analyst' roles to 'user' in SQLite
            try:
                conn.execute("UPDATE registered_users SET role = 'user' WHERE role = 'analyst' OR role IS NULL")
            except Exception:
                pass

            # Local development & test suite fallback: seed test admin if configured and not production
            if not settings.IS_PRODUCTION and settings.ADMIN_DEFAULT_PASSWORD:
                cur = conn.cursor()
                cur.execute("SELECT id FROM registered_users WHERE email = ?", (settings.ADMIN_EMAIL,))
                row = cur.fetchone()
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if not row:
                    admin_id = str(uuid.uuid4())
                    admin_hash = hash_password(settings.ADMIN_DEFAULT_PASSWORD)
                    conn.execute(
                        """
                        INSERT INTO registered_users (id, email, name, password_hash, role, account_status, email_verified, approved_by, approved_at, updated_at, created_at)
                        VALUES (?, ?, ?, ?, 'admin', 'active', 1, 'dev_seed', ?, ?, ?)
                        """,
                        (admin_id, settings.ADMIN_EMAIL, "Platform Administrator", admin_hash, now_iso, now_iso, now_iso),
                    )
                else:
                    conn.execute(
                        "UPDATE registered_users SET role = 'admin', account_status = 'active', email_verified = 1 WHERE email = ?",
                        (settings.ADMIN_EMAIL,),
                    )
    finally:
        conn.close()


def init_reset_token_db() -> None:
    """Initialize persistent schema for single-use password reset tokens (SEC-04)."""
    if settings.IS_PRODUCTION:
        return  # SEC-04: Do NOT initialize local SQLite reset token tables in production

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    jti TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    used_at TEXT,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reset_tokens_jti ON password_reset_tokens (jti)")
    finally:
        conn.close()


def init_activity_log_db() -> None:
    """Initialize audit activity log table in SQLite for local dev/test."""
    if settings.IS_PRODUCTION:
        return

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_activity_log (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    user_email TEXT,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}',
                    ip_address TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON admin_activity_log (created_at DESC)")
    finally:
        conn.close()


def init_admin_verification_token_db() -> None:
    """Initialize persistent schema for single-use administrator verification tokens."""
    if settings.IS_PRODUCTION:
        return

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_verification_tokens (
                    jti TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    used_at TEXT,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_verify_tokens_jti ON admin_verification_tokens (jti)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_verify_tokens_email ON admin_verification_tokens (user_email)")
    finally:
        conn.close()


init_user_db()
init_reset_token_db()
init_activity_log_db()
init_admin_verification_token_db()


def _normalize_user_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure consistent typing and normalized fields across Supabase and SQLite."""
    role = str(data.get("role", "user")).lower()
    if role == "analyst":
        role = "user"

    account_status = str(data.get("account_status", "active") or "active").lower()
    email_verified = data.get("email_verified")
    if email_verified is None:
        email_verified = True
    else:
        email_verified = bool(email_verified)

    return {
        "id": str(data.get("id")),
        "email": str(data.get("email", "")).lower().strip(),
        "name": str(data.get("name", "")).strip(),
        "password_hash": str(data.get("password_hash", "")),
        "role": role,
        "account_status": account_status,
        "email_verified": email_verified,
        "approved_by": data.get("approved_by"),
        "approved_at": data.get("approved_at"),
        "updated_at": data.get("updated_at"),
        "created_at": str(data.get("created_at", "")),
    }


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieve user from Supabase or fallback SQLite with normalized RBAC metadata."""
    clean_email = email.strip().lower()

    # Try Supabase if configured
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.get(url, headers=headers, params={"email": f"eq.{clean_email}"}, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return _normalize_user_record(data[0])
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return None  # Never read local SQLite in production

    # SQLite fallback
    conn = sqlite3.connect(settings.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM registered_users WHERE LOWER(email) = ?", (clean_email,))
        row = cur.fetchone()
        if row:
            return _normalize_user_record(dict(row))
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve user by user_id from Supabase or fallback SQLite."""
    clean_id = str(user_id).strip()

    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.get(url, headers=headers, params={"id": f"eq.{clean_id}"}, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return _normalize_user_record(data[0])
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return None

    conn = sqlite3.connect(settings.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM registered_users WHERE id = ?", (clean_id,))
        row = cur.fetchone()
        if row:
            return _normalize_user_record(dict(row))
        return None
    finally:
        conn.close()


def has_active_admin() -> bool:
    """Check whether at least one active administrator already exists.

    Fails closed in production if the database cannot be queried.
    """
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.get(
                url,
                headers=headers,
                params={"role": "eq.admin", "account_status": "eq.active", "select": "id", "limit": "1"},
                timeout=4.0,
            )
            if res.status_code == 200:
                data = res.json()
                return bool(data and isinstance(data, list) and len(data) > 0)
            if settings.IS_PRODUCTION:
                raise RuntimeError(f"Database error checking active admin existence (HTTP {res.status_code}).")
        except Exception as exc:
            if settings.IS_PRODUCTION:
                raise RuntimeError(f"Production database unreachable checking active admin: {exc}")

    if settings.IS_PRODUCTION:
        raise RuntimeError("Production database connection not configured.")

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM registered_users WHERE role = 'admin' AND account_status = 'active' LIMIT 1")
        return cur.fetchone() is not None
    finally:
        conn.close()


def has_admin_been_initialized() -> bool:
    """Check whether ANY platform administrator account has ever been initialized.

    Initial setup is permanently locked out once ANY administrator account has
    ever been established (active, suspended, rejected, or approved_by = 'initial_setup').
    Unapproved 'pending' applications do not block initial setup.
    """
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.get(
                url,
                headers=headers,
                params={
                    "role": "eq.admin",
                    "or": "(approved_by.eq.initial_setup,account_status.in.(active,suspended,rejected))",
                    "select": "id",
                    "limit": "1",
                },
                timeout=4.0,
            )
            if res.status_code == 200:
                data = res.json()
                return bool(data and isinstance(data, list) and len(data) > 0)
            if settings.IS_PRODUCTION:
                raise RuntimeError(f"Database error checking initialized admin status (HTTP {res.status_code}).")
        except Exception as exc:
            if settings.IS_PRODUCTION:
                raise RuntimeError(f"Production database unreachable checking initialized admin: {exc}")

    if settings.IS_PRODUCTION:
        raise RuntimeError("Production database connection not configured.")

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id FROM registered_users
            WHERE role = 'admin'
              AND (approved_by = 'initial_setup' OR account_status IN ('active', 'suspended', 'rejected'))
            LIMIT 1
            """
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def count_active_admins() -> int:
    """Return count of active administrators for lockout protection."""
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.get(
                url,
                headers=headers,
                params={"role": "eq.admin", "account_status": "eq.active", "select": "id"},
                timeout=4.0,
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list):
                    return len(data)
            if settings.IS_PRODUCTION:
                raise RuntimeError("Failed to query active admin count from production database.")
        except Exception:
            if settings.IS_PRODUCTION:
                raise RuntimeError("Production database unreachable while querying admin count.")

    if settings.IS_PRODUCTION:
        return 0

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM registered_users WHERE role = 'admin' AND account_status = 'active'")
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def initialize_first_admin(email: str, name: str, password_hash: str) -> Tuple[bool, str]:
    """Atomically create the first platform administrator.

    Guarantees:
    - Atomic at the database level.
    - Prevents concurrent requests from creating multiple initial administrators.
    - Fails closed if production database cannot be reached.
    """
    clean_email = email.strip().lower()
    clean_name = name.strip()
    user_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Supabase Mode (Production / Configured)
    if settings.IS_PRODUCTION or settings.has_supabase():
        if not settings.has_supabase():
            logger.error("Production mode active without SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY configured.")
            return False, "Database service unavailable during administrator initialization."

        # Atomic database RPC execution (fail closed on any error, timeout, or invalid response)
        rpc_url = f"{settings.SUPABASE_URL}/rest/v1/rpc/initialize_first_admin"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        }
        try:
            rpc_res = requests.post(
                rpc_url,
                headers=headers,
                json={
                    "p_id": user_id,
                    "p_email": clean_email,
                    "p_name": clean_name,
                    "p_password_hash": password_hash,
                    "p_created_at": now_iso,
                },
                timeout=5.0,
            )
            if rpc_res.status_code == 200:
                data = rpc_res.json()
                if isinstance(data, dict):
                    if data.get("success"):
                        return True, str(data.get("user_id", user_id))
                    rpc_err = str(data.get("error", "Failed to initialize administrator."))
                    logger.error("Database RPC initialize_first_admin returned failure: %s", rpc_err)
                    return False, rpc_err
                logger.error("Database RPC initialize_first_admin returned non-dict payload: %s", type(data))
                return False, "Database service unavailable during administrator initialization."
            elif rpc_res.status_code == 404:
                logger.error("Database RPC initialize_first_admin routine not found (HTTP 404).")
                return False, "Database service unavailable during administrator initialization."
            else:
                logger.error("Database RPC initialize_first_admin failed with HTTP %s: %s", rpc_res.status_code, rpc_res.text)
                return False, "Database service unavailable during administrator initialization."
        except Exception as exc:
            logger.error("Database connection exception during administrator initialization: %s", exc)
            return False, "Database service unavailable during administrator initialization."

    # 2. Development / Test Mode: SQLite with immediate exclusive transaction
    init_user_db()
    conn = sqlite3.connect(settings.SQLITE_PATH, isolation_level=None, timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("BEGIN EXCLUSIVE")
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM registered_users
                WHERE role = 'admin'
                  AND (approved_by = 'initial_setup' OR account_status IN ('active', 'suspended', 'rejected'))
                """
            )
            if cur.fetchone()[0] > 0:
                cur.execute("ROLLBACK")
                return False, "Initial administrator setup has already been completed and is permanently disabled."

            cur.execute("SELECT id FROM registered_users WHERE LOWER(email) = ?", (clean_email,))
            if cur.fetchone():
                cur.execute("ROLLBACK")
                return False, "An account with this email address already exists."

            cur.execute(
                """
                INSERT INTO registered_users
                (id, email, name, password_hash, role, account_status, email_verified, approved_by, approved_at, updated_at, created_at)
                VALUES (?, ?, ?, ?, 'admin', 'active', 1, 'initial_setup', ?, ?, ?)
                """,
                (user_id, clean_email, clean_name, password_hash, now_iso, now_iso, now_iso),
            )
            cur.execute("COMMIT")
            return True, user_id
        except Exception:
            cur.execute("ROLLBACK")
            raise
    except Exception as exc:
        logger.error("SQLite database error during administrator initialization: %s", exc)
        return False, "Database service unavailable during administrator initialization."
    finally:
        conn.close()


def delete_user(user_id: str) -> bool:
    """Delete a user account by ID (used for registration rollbacks)."""
    clean_id = str(user_id).strip()
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            }
            res = requests.delete(url, headers=headers, params={"id": f"eq.{clean_id}"}, timeout=4.0)
            if res.status_code in (200, 204):
                return True
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return False

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM registered_users WHERE id = ?", (clean_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def create_user(
    email: str,
    name: str,
    password_hash: str,
    role: str = "user",
    account_status: str = "active",
    email_verified: bool = True,
    approved_by: Optional[str] = None,
    approved_at: Optional[str] = None,
) -> Tuple[bool, str]:
    """Create new registered user with RBAC status and audit tracking."""
    clean_email = email.strip().lower()
    clean_name = name.strip()
    norm_role = "admin" if role == "admin" else "user"
    user_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Check existing
    if get_user_by_email(clean_email):
        return False, "An account with this email address already exists."

    payload = {
        "id": user_id,
        "email": clean_email,
        "name": clean_name,
        "password_hash": password_hash,
        "role": norm_role,
        "account_status": account_status,
        "email_verified": email_verified,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "updated_at": now_iso,
        "created_at": now_iso,
    }

    # Production Mode: MUST persist to Supabase PostgreSQL (fail closed)
    if settings.IS_PRODUCTION:
        if not settings.has_supabase():
            return False, "Production mode requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to be configured. Local database fallback is strictly disabled."

        url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=5.0)
            if res.status_code in (200, 201):
                return True, user_id
            if res.status_code == 409 or "duplicate" in res.text.lower():
                return False, "An account with this email address already exists."
            return False, f"Failed to register user in production database (HTTP {res.status_code})."
        except Exception as exc:
            return False, f"Production database connection error: {exc}"

    # Development Mode: Insert into Supabase if configured
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }
            res = requests.post(url, headers=headers, json=payload, timeout=5.0)
            if res.status_code in (200, 201):
                try:
                    conn = sqlite3.connect(settings.SQLITE_PATH)
                    with conn:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO registered_users
                            (id, email, name, password_hash, role, account_status, email_verified, approved_by, approved_at, updated_at, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (user_id, clean_email, clean_name, password_hash, norm_role, account_status, 1 if email_verified else 0, approved_by, approved_at, now_iso, now_iso),
                        )
                    conn.close()
                except Exception:
                    pass
                return True, user_id
        except Exception:
            pass

    # Development Fallback to SQLite
    init_user_db()
    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO registered_users
                (id, email, name, password_hash, role, account_status, email_verified, approved_by, approved_at, updated_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, clean_email, clean_name, password_hash, norm_role, account_status, 1 if email_verified else 0, approved_by, approved_at, now_iso, now_iso),
            )
        return True, user_id
    except sqlite3.IntegrityError:
        return False, "An account with this email address already exists."
    except Exception as exc:
        return False, f"Failed to register user: {exc}"
    finally:
        conn.close()


def update_user_status(
    user_id: str,
    new_status: str,
    approved_by: Optional[str] = None,
    approved_at: Optional[str] = None,
) -> bool:
    """Update user account status (e.g., active, suspended, rejected) and approval metadata."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clean_id = str(user_id).strip()

    patch_data: Dict[str, Any] = {
        "account_status": new_status,
        "updated_at": now_iso,
    }
    if approved_by is not None:
        patch_data["approved_by"] = approved_by
    if approved_at is not None:
        patch_data["approved_at"] = approved_at

    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.patch(
                url,
                headers=headers,
                params={"id": f"eq.{clean_id}"},
                json=patch_data,
                timeout=4.0,
            )
            if res.status_code in (200, 204):
                # Also sync local SQLite if dev
                if not settings.IS_PRODUCTION:
                    try:
                        conn = sqlite3.connect(settings.SQLITE_PATH)
                        with conn:
                            conn.execute(
                                "UPDATE registered_users SET account_status = ?, approved_by = COALESCE(?, approved_by), approved_at = COALESCE(?, approved_at), updated_at = ? WHERE id = ?",
                                (new_status, approved_by, approved_at, now_iso, clean_id),
                            )
                        conn.close()
                    except Exception:
                        pass
                return True
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return False

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            cur = conn.execute(
                "UPDATE registered_users SET account_status = ?, approved_by = COALESCE(?, approved_by), approved_at = COALESCE(?, approved_at), updated_at = ? WHERE id = ?",
                (new_status, approved_by, approved_at, now_iso, clean_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def update_user_status_conditional(
    user_id: str,
    new_status: str,
    expected_status: Optional[str] = None,
    expected_role: Optional[str] = None,
    require_email_verified: bool = False,
    approved_by: Optional[str] = None,
    approved_at: Optional[str] = None,
) -> bool:
    """Atomically and conditionally update user account status matching constraints.

    Used for atomic approval and rejection to prevent race conditions.
    """
    clean_id = str(user_id).strip()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    patch_data: Dict[str, Any] = {
        "account_status": new_status,
        "updated_at": now_iso,
    }
    if approved_by is not None:
        patch_data["approved_by"] = approved_by
    if approved_at is not None:
        patch_data["approved_at"] = approved_at

    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }
            params: Dict[str, str] = {"id": f"eq.{clean_id}"}
            if expected_status:
                params["account_status"] = f"eq.{expected_status}"
            if expected_role:
                params["role"] = f"eq.{expected_role}"
            if require_email_verified:
                params["email_verified"] = "is.true"

            res = requests.patch(url, headers=headers, params=params, json=patch_data, timeout=4.0)
            if res.status_code == 200:
                rows = res.json()
                if isinstance(rows, list) and len(rows) > 0:
                    if not settings.IS_PRODUCTION:
                        try:
                            conn = sqlite3.connect(settings.SQLITE_PATH)
                            with conn:
                                conn.execute(
                                    "UPDATE registered_users SET account_status = ?, approved_by = COALESCE(?, approved_by), approved_at = COALESCE(?, approved_at), updated_at = ? WHERE id = ?",
                                    (new_status, approved_by, approved_at, now_iso, clean_id),
                                )
                            conn.close()
                        except Exception:
                            pass
                    return True
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return False

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            cur = conn.cursor()
            query = "UPDATE registered_users SET account_status = ?, updated_at = ?"
            params_list: list[Any] = [new_status, now_iso]
            if approved_by is not None:
                query += ", approved_by = ?"
                params_list.append(approved_by)
            if approved_at is not None:
                query += ", approved_at = ?"
                params_list.append(approved_at)

            query += " WHERE id = ?"
            params_list.append(clean_id)

            if expected_status:
                query += " AND account_status = ?"
                params_list.append(expected_status)
            if expected_role:
                query += " AND role = ?"
                params_list.append(expected_role)
            if require_email_verified:
                query += " AND email_verified = 1"

            cur.execute(query, tuple(params_list))
            return cur.rowcount > 0
    finally:
        conn.close()


def update_user_email_verified(user_id: str, verified: bool = True) -> bool:
    """Update email verification status."""
    clean_id = str(user_id).strip()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.patch(
                url,
                headers=headers,
                params={"id": f"eq.{clean_id}"},
                json={"email_verified": verified, "updated_at": now_iso},
                timeout=4.0,
            )
            if res.status_code in (200, 204):
                return True
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return False

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            cur = conn.execute(
                "UPDATE registered_users SET email_verified = ?, updated_at = ? WHERE id = ?",
                (1 if verified else 0, now_iso, clean_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def update_user_password(email: str, new_hash: str) -> bool:
    """Update password hash."""
    clean_email = email.strip().lower()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if settings.IS_PRODUCTION:
        if not settings.has_supabase():
            return False

        url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        try:
            res = requests.patch(
                url,
                headers=headers,
                params={"email": f"eq.{clean_email}"},
                json={"password_hash": new_hash, "updated_at": now_iso},
                timeout=4.0,
            )
            if res.status_code == 200:
                rows = res.json()
                if isinstance(rows, list) and len(rows) > 0:
                    return True
            # Case-insensitive retry if 0 rows matched exact lowercase
            res_ilike = requests.patch(
                url,
                headers=headers,
                params={"email": f"ilike.{clean_email}"},
                json={"password_hash": new_hash, "updated_at": now_iso},
                timeout=4.0,
            )
            if res_ilike.status_code == 200:
                rows_ilike = res_ilike.json()
                if isinstance(rows_ilike, list) and len(rows_ilike) > 0:
                    return True
            return False
        except Exception:
            return False

    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }
            res = requests.patch(
                url,
                headers=headers,
                params={"email": f"eq.{clean_email}"},
                json={"password_hash": new_hash, "updated_at": now_iso},
                timeout=4.0,
            )
            if res.status_code == 200:
                rows = res.json()
                if isinstance(rows, list) and len(rows) > 0:
                    return True
            res_ilike = requests.patch(
                url,
                headers=headers,
                params={"email": f"ilike.{clean_email}"},
                json={"password_hash": new_hash, "updated_at": now_iso},
                timeout=4.0,
            )
            if res_ilike.status_code == 200:
                rows_ilike = res_ilike.json()
                if isinstance(rows_ilike, list) and len(rows_ilike) > 0:
                    return True
        except Exception:
            pass

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            cur = conn.execute(
                "UPDATE registered_users SET password_hash = ?, updated_at = ? WHERE LOWER(email) = ?",
                (new_hash, now_iso, clean_email),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def get_all_users_admin(
    status_filter: Optional[str] = None,
    role_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> list[Dict[str, Any]]:
    """List registered users with status/role filters and search (excluding password hashes)."""
    raw_users: list[Dict[str, Any]] = []

    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            params: Dict[str, str] = {
                "select": "id,email,name,role,account_status,email_verified,created_at,approved_at,approved_by",
                "order": "created_at.desc",
            }
            if status_filter:
                params["account_status"] = f"eq.{status_filter.lower().strip()}"
            if role_filter:
                params["role"] = f"eq.{role_filter.lower().strip()}"

            res = requests.get(url, headers=headers, params=params, timeout=4.0)
            if res.status_code == 200:
                raw_users = [_normalize_user_record(u) for u in res.json()]
        except Exception:
            pass

    if not raw_users and not settings.IS_PRODUCTION:
        conn = sqlite3.connect(settings.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            query = "SELECT id, email, name, role, account_status, email_verified, created_at, approved_at, approved_by FROM registered_users"
            filters = []
            params_list = []
            if status_filter:
                filters.append("account_status = ?")
                params_list.append(status_filter.lower().strip())
            if role_filter:
                filters.append("role = ?")
                params_list.append(role_filter.lower().strip())

            if filters:
                query += " WHERE " + " AND ".join(filters)
            query += " ORDER BY created_at DESC"

            cur.execute(query, tuple(params_list))
            raw_users = [_normalize_user_record(dict(r)) for r in cur.fetchall()]
        finally:
            conn.close()

    # Search filter in-memory if requested
    if search:
        s = search.strip().lower()
        raw_users = [u for u in raw_users if s in u.get("email", "").lower() or s in u.get("name", "").lower()]

    return raw_users


def get_admin_approvals() -> list[Dict[str, Any]]:
    """Retrieve pending administrator registration requests."""
    return get_all_users_admin(status_filter="pending", role_filter="admin")


def get_dashboard_stats() -> Dict[str, Any]:
    """Retrieve accurate database counts for the administrator dashboard."""
    users = get_all_users_admin()
    total_registered = len(users)
    active_users = sum(1 for u in users if u.get("role") in ("user", "analyst") and u.get("account_status") == "active")
    pending_users = sum(1 for u in users if u.get("role") in ("user", "analyst") and u.get("account_status") == "pending")
    suspended_users = sum(1 for u in users if u.get("account_status") == "suspended")
    approved_admins = sum(1 for u in users if u.get("role") == "admin" and u.get("account_status") == "active")
    pending_admins = sum(1 for u in users if u.get("role") == "admin" and u.get("account_status") == "pending")

    activity_count = 0
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/admin_activity_log"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Prefer": "count=exact",
            }
            res = requests.head(url, headers=headers, timeout=3.0)
            range_header = res.headers.get("content-range", "")
            if "/" in range_header:
                activity_count = int(range_header.split("/")[-1])
        except Exception:
            pass

    if activity_count == 0 and not settings.IS_PRODUCTION:
        try:
            conn = sqlite3.connect(settings.SQLITE_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM admin_activity_log")
            activity_count = int(cur.fetchone()[0])
            conn.close()
        except Exception:
            pass

    recent_regs = sorted(users, key=lambda x: str(x.get("created_at", "")), reverse=True)[:8]

    return {
        "total_registered_users": total_registered,
        "active_users": active_users,
        "pending_users": pending_users,
        "suspended_users": suspended_users,
        "approved_administrators": approved_admins,
        "pending_admin_requests": pending_admins,
        "recent_activity_count": activity_count,
        "recent_registrations": recent_regs,
    }


def _scrub_sensitive_dict(d: Any) -> Any:
    """Recursively scrub passwords, tokens, hashes, and secrets from audit logging payloads."""
    if isinstance(d, dict):
        scrubbed = {}
        for k, v in d.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "token", "secret", "setup", "credential", "hash", "key")):
                scrubbed[k] = "[REDACTED]"
            else:
                scrubbed[k] = _scrub_sensitive_dict(v)
        return scrubbed
    elif isinstance(d, list):
        return [_scrub_sensitive_dict(item) for item in d]
    return d


def log_activity(
    action: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Record an audit trail event for security compliance and telemetry.

    Guarantees:
    - Never exposes passwords, setup tokens, session secrets, or verification tokens in activity logs.
    """
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log_id = str(uuid.uuid4())
    safe_details = _scrub_sensitive_dict(details or {})

    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/admin_activity_log"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "id": log_id,
                "user_id": user_id,
                "user_email": user_email,
                "action": action,
                "details": safe_details,
                "ip_address": ip_address,
                "created_at": now_iso,
            }
            requests.post(url, headers=headers, json=payload, timeout=2.0)
            return
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return

    try:
        conn = sqlite3.connect(settings.SQLITE_PATH)
        with conn:
            conn.execute(
                """
                INSERT INTO admin_activity_log (id, user_id, user_email, action, details, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (log_id, user_id, user_email, action, json.dumps(safe_details), ip_address, now_iso),
            )
        conn.close()
    except Exception:
        pass


def get_recent_activity(limit: int = 50) -> list[Dict[str, Any]]:
    """Retrieve audit activity history for administrator review."""
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/admin_activity_log"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.get(
                url,
                headers=headers,
                params={"order": "created_at.desc", "limit": str(limit)},
                timeout=4.0,
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list):
                    return data
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return []

    conn = sqlite3.connect(settings.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, user_id, user_email, action, details, ip_address, created_at FROM admin_activity_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            if isinstance(d.get("details"), str):
                try:
                    d["details"] = json.loads(d["details"])
                except Exception:
                    d["details"] = {}
            rows.append(d)
        return rows
    finally:
        conn.close()


def create_admin_verification_token(email: str) -> str:
    """Generate a signed single-use email verification token for pending admin accounts.

    Security guarantees:
    - Cryptographically secure token generation (HMAC-SHA256 JWT with UUID v4 jti).
    - Database-backed persistence in admin_verification_tokens table.
    - Expiration: 24 hours.
    - Never logs token.
    """
    clean_email = email.strip().lower()
    delta = datetime.timedelta(hours=24)
    jti = str(uuid.uuid4())
    payload = {
        "email": clean_email,
        "type": "admin_email_verify",
        "jti": jti,
    }
    token = create_access_token(payload, expires_delta=delta)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (datetime.datetime.now(datetime.timezone.utc) + delta).isoformat()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Supabase (Production / Configured)
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/admin_verification_tokens"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.post(
                url,
                headers=headers,
                json={
                    "jti": jti,
                    "user_email": clean_email,
                    "token_hash": token_hash,
                    "used_at": None,
                    "expires_at": expires_at,
                    "created_at": now_iso,
                },
                timeout=4.0,
            )
            if res.status_code in (200, 201):
                return token
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        raise RuntimeError("Failed to persist verification token in production database.")

    # 2. SQLite (Development / Test)
    init_admin_verification_token_db()
    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO admin_verification_tokens
                (jti, user_email, token_hash, used_at, expires_at, created_at)
                VALUES (?, ?, ?, NULL, ?, ?)
                """,
                (jti, clean_email, token_hash, expires_at, now_iso),
            )
    finally:
        conn.close()

    return token


def consume_admin_verification_token(token: str, expected_email: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Validate and atomically consume a single-use administrator verification token.

    Enforces:
    1. Valid HMAC signature and non-empty identity.
    2. Explicit purpose: payload["type"] == "admin_email_verify".
    3. Expiration validity (payload exp and database expires_at > now).
    4. Email matching: payload email == expected_email.
    5. Target account existence, admin role, and pending status.
    6. Database-backed single-use consumption and replay protection.
    7. Atomically sets email_verified = True.

    Returns: (is_valid, message, user_dict)
    """
    payload = decode_access_token(token)
    if not payload or not payload.get("email"):
        return False, "Email verification token is invalid or has expired.", None

    if payload.get("type") != "admin_email_verify":
        return False, "Invalid token purpose: verification tokens cannot be used for this action.", None

    if time.time() > payload.get("exp", 0):
        return False, "Email verification token has expired.", None

    clean_email = str(payload.get("email", "")).strip().lower()
    clean_expected = str(expected_email or "").strip().lower()
    if clean_email != clean_expected:
        return False, "Verification token does not match the provided email address.", None

    user = get_user_by_email(clean_email)
    if not user:
        return False, "Administrator application not found.", None

    if user.get("role") != "admin":
        return False, "Verification token can only be used for administrator applications.", None

    if user.get("account_status") != "pending":
        return False, "Administrator application is not in pending status.", None

    if user.get("email_verified") is True:
        return False, "Administrator email address has already been verified.", None

    jti = payload.get("jti")
    if not jti:
        return False, "Malformed verification token: missing identifier.", None

    submitted_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Supabase Mode (Production / Configured)
    if settings.IS_PRODUCTION or settings.has_supabase():
        if not settings.has_supabase():
            return False, "Database service unavailable.", None

        url = f"{settings.SUPABASE_URL}/rest/v1/admin_verification_tokens"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        patch_params = {
            "jti": f"eq.{jti}",
            "token_hash": f"eq.{submitted_hash}",
            "used_at": "is.null",
            "expires_at": f"gt.{now_iso}",
        }
        try:
            patch_res = requests.patch(url, headers=headers, params=patch_params, json={"used_at": now_iso}, timeout=4.0)
            if patch_res.status_code == 200:
                rows = patch_res.json()
                if isinstance(rows, list) and len(rows) == 1:
                    update_user_email_verified(user["id"], verified=True)
                    user["email_verified"] = True
                    return True, "Email address verified successfully.", user
                if isinstance(rows, list) and len(rows) == 0:
                    check_res = requests.get(url, headers=headers, params={"jti": f"eq.{jti}"}, timeout=4.0)
                    if check_res.status_code == 200:
                        rec = check_res.json()
                        if rec and isinstance(rec, list) and len(rec) > 0:
                            item = rec[0]
                            if item.get("used_at"):
                                return False, "Verification token has already been used.", None
                            if item.get("expires_at") and item.get("expires_at") <= now_iso:
                                return False, "Email verification token has expired.", None
                    return False, "Verification token has already been consumed or is invalid.", None
        except Exception:
            if settings.IS_PRODUCTION:
                return False, "Database service timed out during token verification.", None

    # 2. SQLite (Development / Test)
    init_admin_verification_token_db()
    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE admin_verification_tokens
                SET used_at = ?
                WHERE jti = ? AND token_hash = ? AND used_at IS NULL AND expires_at > ?
                """,
                (now_iso, jti, submitted_hash, now_iso),
            )
            if cur.rowcount == 1:
                cur.execute(
                    "UPDATE registered_users SET email_verified = 1, updated_at = ? WHERE id = ?",
                    (now_iso, str(user["id"]).strip()),
                )
                user["email_verified"] = True
                return True, "Email address verified successfully.", user

            # Check why it failed
            cur.execute("SELECT used_at, expires_at FROM admin_verification_tokens WHERE jti = ?", (jti,))
            row = cur.fetchone()
            if row:
                used_at, exp_at = row
                if used_at is not None:
                    return False, "Verification token has already been used.", None
                if exp_at and exp_at <= now_iso:
                    return False, "Email verification token has expired.", None
            return False, "Verification token has already been consumed or is invalid.", None
    finally:
        conn.close()


def verify_admin_verification_token(token: str) -> Optional[str]:
    """Verify and decode an admin email verification token (backward-compatible inspect)."""
    payload = decode_access_token(token)
    if not payload or payload.get("type") != "admin_email_verify":
        return None
    if time.time() > payload.get("exp", 0):
        return None
    return payload.get("email")


# ==============================================================================
# JWT Session Tokens & Password Reset Tokens
# ==============================================================================

def create_access_token(user_data: Dict[str, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Create a cryptographically signed HMAC-SHA256 JWT token with explicit type scope."""
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_data.get("id"),
        "email": user_data.get("email"),
        "name": user_data.get("name"),
        "role": user_data.get("role", "analyst"),
        "type": user_data.get("type", "session"),  # 'session' or 'reset'
        "jti": user_data.get("jti", str(uuid.uuid4())),
        "exp": int(expire.timestamp()),
        "iat": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
    }

    header = {"alg": "HS256", "typ": "JWT"}
    b64_header = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("utf-8").rstrip("=")
    b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    signing_input = f"{b64_header}.{b64_payload}"

    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    b64_sig = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    return f"{signing_input}.{b64_sig}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify an HMAC-SHA256 JWT access token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        b64_header, b64_payload, b64_sig = parts

        signing_input = f"{b64_header}.{b64_payload}"
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        b64_expected_sig = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")

        if not hmac.compare_digest(b64_sig, b64_expected_sig):
            return None

        # Decode payload
        padding = "=" * (-len(b64_payload) % 4)
        payload_bytes = base64.urlsafe_b64decode(b64_payload + padding)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Verify exp
        if time.time() > payload.get("exp", 0):
            return None

        return payload
    except Exception:
        return None


def create_password_reset_token(email: str, expires_delta: Optional[datetime.timedelta] = None) -> Optional[str]:
    """Generate a single-use scoped password reset token and persist its tracking record (SEC-04)."""
    clean_email = email.strip().lower()
    user = get_user_by_email(clean_email)
    if not user:
        return None

    jti = str(uuid.uuid4())
    delta = expires_delta or datetime.timedelta(hours=1)
    expires_dt = datetime.datetime.now(datetime.timezone.utc) + delta
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    exp_iso = expires_dt.isoformat()

    payload = {
        "id": str(user.get("id")),
        "email": clean_email,
        "type": "reset",
        "jti": jti,
    }

    token = create_access_token(payload, expires_delta=delta)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    # 1. Production Mode: MUST persist to Supabase PostgreSQL; fail-closed on failure
    if settings.IS_PRODUCTION:
        if not settings.has_supabase():
            # In production, require valid Supabase configuration. Never fall back to SQLite.
            return None

        url = f"{settings.SUPABASE_URL}/rest/v1/password_reset_tokens"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        # Invalidate any prior active unconsumed reset tokens for this email address
        try:
            requests.patch(
                url,
                headers=headers,
                params={"user_email": f"eq.{clean_email}", "used_at": "is.null"},
                json={"used_at": now_iso},
                timeout=4.0,
            )
        except Exception:
            pass

        payload_db = {
            "jti": jti,
            "user_email": clean_email,
            "token_hash": token_hash,
            "expires_at": exp_iso,
            "created_at": now_iso,
        }
        try:
            res = requests.post(url, headers=headers, json=payload_db, timeout=4.0)
            if res.status_code in (200, 201):
                return token
            # Supabase rejected insert in production: fail closed
            return None
        except Exception:
            # Network timeout or error in production: fail closed
            return None

    # 2. Development Mode: Try Supabase if configured, otherwise persist to local SQLite
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/password_reset_tokens"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }
            try:
                requests.patch(
                    url,
                    headers=headers,
                    params={"user_email": f"eq.{clean_email}", "used_at": "is.null"},
                    json={"used_at": now_iso},
                    timeout=4.0,
                )
            except Exception:
                pass

            payload_db = {
                "jti": jti,
                "user_email": clean_email,
                "token_hash": token_hash,
                "expires_at": exp_iso,
                "created_at": now_iso,
            }
            requests.post(url, headers=headers, json=payload_db, timeout=4.0)
        except Exception:
            pass

    # Development SQLite fallback
    init_reset_token_db()
    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            # Invalidate any prior unconsumed tokens for this user in SQLite
            conn.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE LOWER(user_email) = ? AND used_at IS NULL",
                (now_iso, clean_email),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO password_reset_tokens (jti, user_email, token_hash, used_at, expires_at, created_at)
                VALUES (?, ?, ?, NULL, ?, ?)
                """,
                (jti, clean_email, token_hash, exp_iso, now_iso),
            )
    finally:
        conn.close()

    return token


def consume_password_reset_token(token: str) -> Tuple[bool, str, Optional[str]]:
    """Validate and atomically consume a single-use password reset token (SEC-04).

    Enforces:
    1. Valid HMAC signature
    2. Explicit scope: payload["type"] == "reset"
    3. Expiration validity (payload exp and database expires_at > now)
    4. Cryptographic binding: database token_hash must match SHA-256 of submitted token
    5. Atomic single-use consumption preventing concurrent reuse race conditions
    6. Production fail-closed: requires operational Supabase; zero SQLite fallback in production

    Returns: (is_valid, message, user_email)
    """
    payload = decode_access_token(token)
    if not payload or not payload.get("email"):
        return False, "Password reset link is invalid or has expired.", None

    # 1. Enforce token scope: must be 'reset'
    if payload.get("type") != "reset":
        return False, "Invalid token scope: ordinary session tokens cannot be used to reset passwords.", None

    # 2. Check expiration timestamp in payload
    if time.time() > payload.get("exp", 0):
        return False, "Password reset token has expired.", None

    jti = payload.get("jti")
    if not jti:
        return False, "Malformed reset token: missing token identifier.", None

    # 3. Compute SHA-256 hash of the submitted token
    submitted_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 4. Production Mode: MUST validate and consume via Supabase PostgreSQL (fail closed)
    if settings.IS_PRODUCTION:
        if not settings.has_supabase():
            return False, "Authentication service is currently unavailable. Please try again later.", None

        url = f"{settings.SUPABASE_URL}/rest/v1/password_reset_tokens"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        patch_params = {
            "jti": f"eq.{jti}",
            "token_hash": f"eq.{submitted_hash}",
            "used_at": "is.null",
            "expires_at": f"gt.{now_iso}",
        }

        try:
            patch_res = requests.patch(
                url,
                headers=headers,
                params=patch_params,
                json={"used_at": now_iso},
                timeout=4.0,
            )
        except Exception:
            return False, "Authentication service timed out. Please try again later.", None

        if patch_res.status_code != 200:
            return False, "Authentication service encountered an error. Please try again later.", None

        if not patch_res.text or not patch_res.text.strip():
            return False, "Authentication service returned an empty response. Please try again later.", None

        try:
            consumed_rows = patch_res.json()
        except Exception:
            return False, "Authentication service returned an unexpected response.", None

        if not isinstance(consumed_rows, list):
            return False, "Authentication service returned an unexpected response.", None

        if len(consumed_rows) == 1:
            return True, "Token consumed successfully.", payload["email"]

        if len(consumed_rows) == 0:
            # 0 rows updated: determine exact rejection reason without leaking sensitive data
            try:
                check_res = requests.get(
                    url,
                    headers=headers,
                    params={"jti": f"eq.{jti}", "select": "token_hash,used_at,expires_at"},
                    timeout=4.0,
                )
                if check_res.status_code == 200:
                    rows = check_res.json()
                    if rows and isinstance(rows, list):
                        record = rows[0]
                        if record.get("token_hash") != submitted_hash:
                            return False, "Password reset token is invalid.", None
                        if record.get("used_at") is not None:
                            return False, "Password reset token has already been used.", None
                        if record.get("expires_at") and record.get("expires_at") <= now_iso:
                            return False, "Password reset token has expired.", None
            except Exception:
                pass

            return False, "Password reset token is unrecognized, invalid, or has already been consumed.", None

        return False, "Authentication service returned an unexpected response.", None

    # 5. Development Mode: Try Supabase if configured, otherwise use local SQLite
    if settings.has_supabase():
        url = f"{settings.SUPABASE_URL}/rest/v1/password_reset_tokens"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        patch_params = {
            "jti": f"eq.{jti}",
            "token_hash": f"eq.{submitted_hash}",
            "used_at": "is.null",
            "expires_at": f"gt.{now_iso}",
        }
        try:
            patch_res = requests.patch(
                url,
                headers=headers,
                params=patch_params,
                json={"used_at": now_iso},
                timeout=4.0,
            )
            if patch_res.status_code != 200:
                return False, "Authentication service encountered an error. Please try again later.", None

            if not patch_res.text or not patch_res.text.strip():
                return False, "Authentication service returned an empty response. Please try again later.", None

            try:
                consumed_rows = patch_res.json()
            except Exception:
                return False, "Authentication service returned an unexpected response.", None

            if not isinstance(consumed_rows, list):
                return False, "Authentication service returned an unexpected response.", None

            if len(consumed_rows) == 1:
                # Sync local SQLite for local testing
                try:
                    conn = sqlite3.connect(settings.SQLITE_PATH)
                    with conn:
                        conn.execute("UPDATE password_reset_tokens SET used_at = ? WHERE jti = ?", (now_iso, jti))
                    conn.close()
                except Exception:
                    pass
                return True, "Token consumed successfully.", payload["email"]

            if len(consumed_rows) == 0:
                # 0 rows updated: check reason
                try:
                    check_res = requests.get(
                        url,
                        headers=headers,
                        params={"jti": f"eq.{jti}", "select": "token_hash,used_at,expires_at"},
                        timeout=4.0,
                    )
                    if check_res.status_code == 200:
                        rows = check_res.json()
                        if rows and isinstance(rows, list):
                            record = rows[0]
                            if record.get("token_hash") != submitted_hash:
                                return False, "Password reset token is invalid.", None
                            if record.get("used_at") is not None:
                                return False, "Password reset token has already been used.", None
                            if record.get("expires_at") and record.get("expires_at") <= now_iso:
                                return False, "Password reset token has expired.", None
                except Exception:
                    pass
                return False, "Password reset token is unrecognized, invalid, or has already been consumed.", None

            return False, "Authentication service returned an unexpected response.", None
        except Exception:
            pass  # Fall through to SQLite in development

    # Development SQLite Atomic Update
    init_reset_token_db()
    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            cur = conn.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = ?
                WHERE jti = ? AND token_hash = ? AND used_at IS NULL AND expires_at > ?
                """,
                (now_iso, jti, submitted_hash, now_iso),
            )
            if cur.rowcount == 1:
                return True, "Token consumed successfully.", payload["email"]

            # 0 rows updated: determine reason
            check_cur = conn.execute("SELECT token_hash, used_at, expires_at FROM password_reset_tokens WHERE jti = ?", (jti,))
            row = check_cur.fetchone()
            if not row:
                return False, "Password reset token is unrecognized, invalid, or has already been consumed.", None
            if row[0] != submitted_hash:
                return False, "Password reset token is invalid.", None
            if row[1] is not None:
                return False, "Password reset token has already been used.", None
            if row[2] and row[2] <= now_iso:
                return False, "Password reset token has expired.", None

            return False, "Password reset token is unrecognized, invalid, or has already been consumed.", None
    finally:
        conn.close()


# ==============================================================================
# FastAPI Route Dependencies
# ==============================================================================

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """FastAPI dependency to extract, verify, and authoritatively validate current user state against DB."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid authentication token. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Special-purpose tokens (password reset, email verification) cannot be used as session authorization tokens
    if payload.get("type") in ("reset", "admin_email_verify"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Special purpose tokens cannot be used for general API authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clean_email = str(payload.get("email", "")).strip().lower()
    if not clean_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Authoritative DB lookup: never trust JWT role or status claims blindly
    user = get_user_by_email(clean_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists or has been deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    account_status = user.get("account_status", "active")
    if account_status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended. Please contact administrator support.",
        )
    if account_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account request was rejected.",
        )
    if account_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is pending administrator approval.",
        )
    if account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or pending verification.",
        )

    return {
        "id": str(user.get("id")),
        "email": user.get("email"),
        "name": user.get("name"),
        "role": user.get("role", "user"),
        "account_status": account_status,
        "email_verified": bool(user.get("email_verified", True)),
    }


async def require_active_account(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency verifying that account is verified and fully active."""
    if user.get("account_status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active account required.",
        )
    return user


async def require_user(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency ensuring caller is an active regular user."""
    if user.get("role") not in ("user", "analyst"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Regular user account required.",
        )
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """FastAPI dependency requiring backend-verified administrator privileges."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required for this resource.",
        )
    return user
