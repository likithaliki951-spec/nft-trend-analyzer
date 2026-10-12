"""Persistent user account storage, validation, and multi-backend persistence.

Supports persistent hosted databases (Supabase REST) for Streamlit Community Cloud,
with automatic fallback to local SQLite for offline/development environments.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any
import uuid

import requests
import streamlit as st

from auth import hash_password

# ==============================================================================
# Database Exceptions
# ==============================================================================

class StorageError(Exception):
    """Base exception for user store operations."""


class DatabaseConnectionError(StorageError):
    """Raised when the database connection fails (network drop, DNS error, timeout)."""


class DatabasePermissionError(StorageError):
    """Raised when database permissions or credentials are denied (e.g. HTTP 401 or 403)."""


class DatabaseResponseError(StorageError):
    """Raised when database returns malformed data or unexpected response structure."""


# Regular expression for RFC 5322 compliant email validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Re-entrant thread lock to serialize duplicate-registration checks and database writes
_REGISTRATION_LOCK = threading.RLock()

# Local SQLite database path inside .streamlit directory (strictly gitignored)
DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent / ".streamlit" / "users.db"


def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and trimmed whitespace."""
    return str(email).strip().lower()


def validate_registration_inputs(
    email: str,
    name: str,
    password: str,
    password_confirm: str,
) -> tuple[bool, str]:
    """Validate user registration inputs against security and format policies.

    Enforces:
    - Non-empty, trimmed fields
    - Name length >= 2 characters
    - Valid email syntax
    - Password >= 8 characters
    - Password complexity: requires at least one letter and at least one digit or symbol
    - Password confirmation match
    """
    clean_name = str(name).strip()
    if not clean_name:
        return False, "Please enter your full name or display name."
    if len(clean_name) < 2:
        return False, "Name must be at least 2 characters long."
    if len(clean_name) > 100:
        return False, "Name must not exceed 100 characters."

    clean_email = normalize_email(email)
    if not clean_email:
        return False, "Please enter a valid email address."
    if not EMAIL_REGEX.match(clean_email):
        return False, "Invalid email address format. Please enter an address like name@domain.com."

    if not password:
        return False, "Please enter a password."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isalpha() for c in password):
        return False, "Password must contain at least one letter."
    if not (any(c.isdigit() for c in password) or any(not c.isalnum() for c in password)):
        return False, "Password must contain at least one number or special character."

    if password != password_confirm:
        return False, "Passwords do not match. Please re-enter your password confirmation."

    return True, ""


# ==============================================================================
# Database Configuration & Backend Detection
# ==============================================================================

def get_database_config() -> dict[str, Any]:
    """Inspect Streamlit secrets and environment variables for database credentials.

    Prioritizes Supabase service_role_key over anon key so server-side operations
    can read and write to registered_users safely with Row Level Security enabled.
    """
    supabase_url = ""
    supabase_key = ""

    # Check Streamlit secrets
    try:
        if hasattr(st, "secrets"):
            # Check [supabase] section
            if "supabase" in st.secrets:
                supabase_url = str(st.secrets["supabase"].get("url", "")).strip()
                supabase_key = str(
                    st.secrets["supabase"].get("service_role_key", "")
                    or st.secrets["supabase"].get("key", "")
                ).strip()
            # Check top-level secrets
            if not supabase_url and "SUPABASE_URL" in st.secrets:
                supabase_url = str(st.secrets["SUPABASE_URL"]).strip()
            if not supabase_key:
                if "SUPABASE_SERVICE_ROLE_KEY" in st.secrets:
                    supabase_key = str(st.secrets["SUPABASE_SERVICE_ROLE_KEY"]).strip()
                elif "SUPABASE_KEY" in st.secrets:
                    supabase_key = str(st.secrets["SUPABASE_KEY"]).strip()
    except Exception:
        pass

    # Check environment variables
    if not supabase_url:
        supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    if not supabase_key:
        supabase_key = (
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.environ.get("SUPABASE_KEY", "").strip()
        )

    if supabase_url and supabase_key:
        return {
            "type": "supabase",
            "url": supabase_url.rstrip("/"),
            "key": supabase_key,
        }

    return {
        "type": "sqlite",
        "path": DEFAULT_SQLITE_PATH,
    }


def get_storage_info() -> dict[str, Any]:
    """Return descriptive metadata about the current active user storage backend."""
    cfg = get_database_config()
    if cfg["type"] == "supabase":
        return {
            "backend": "Supabase Hosted Cloud Database",
            "is_cloud_persistent": True,
            "description": "Accounts are stored persistently in your Supabase PostgreSQL cluster.",
            "status": "Connected to cloud database",
        }
    return {
        "backend": "Local SQLite Database",
        "is_cloud_persistent": False,
        "description": "Accounts are stored locally in .streamlit/users.db. For persistent public cloud registration, configure Supabase credentials in Streamlit Secrets.",
        "status": "Local development storage active",
    }


# ==============================================================================
# SQLite Backend
# ==============================================================================

def _get_sqlite_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open or create a connection to the SQLite database."""
    target_path = Path(db_path) if db_path else DEFAULT_SQLITE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite_db(db_path: Path | str | None = None) -> None:
    """Initialize the SQLite schema if not already present."""
    with _REGISTRATION_LOCK:
        conn = _get_sqlite_connection(db_path)
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS registered_users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'analyst',
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_reg_users_email ON registered_users(email)"
                )
        finally:
            conn.close()


def _sqlite_get_user(email: str, db_path: Path | str | None = None) -> dict[str, Any] | None:
    """Retrieve a user record from SQLite by email."""
    init_sqlite_db(db_path)
    clean_email = normalize_email(email)
    conn = _get_sqlite_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, name, password_hash, role, created_at FROM registered_users WHERE email = ?",
            (clean_email,),
        )
        row = cur.fetchone()
        if row:
            return {
                "id": row["id"],
                "email": row["email"],
                "name": row["name"],
                "password_hash": row["password_hash"],
                "role": row["role"],
                "created_at": row["created_at"],
            }
        return None
    finally:
        conn.close()


def _sqlite_insert_user(
    email: str,
    name: str,
    password_hash: str,
    role: str = "analyst",
    db_path: Path | str | None = None,
) -> tuple[bool, str]:
    """Insert a new user record into SQLite."""
    init_sqlite_db(db_path)
    clean_email = normalize_email(email)
    clean_name = str(name).strip()
    user_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    conn = _get_sqlite_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO registered_users (id, email, name, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, clean_email, clean_name, password_hash, role, now_iso),
            )
        return True, "User registered successfully."
    except sqlite3.IntegrityError:
        return False, "An account with this email address is already registered."
    except Exception as exc:
        return False, f"Database error during registration: {exc}"
    finally:
        conn.close()


def _sqlite_get_all_users(db_path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Retrieve all users stored in SQLite."""
    init_sqlite_db(db_path)
    conn = _get_sqlite_connection(db_path)
    users = {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email, name, password_hash, role, created_at FROM registered_users")
        for row in cur.fetchall():
            email = row["email"]
            users[email] = {
                "id": row["id"],
                "email": email,
                "name": row["name"],
                "password_hash": row["password_hash"],
                "role": row["role"],
                "created_at": row["created_at"],
            }
        return users
    finally:
        conn.close()


# ==============================================================================
# Supabase Backend (REST API)
# ==============================================================================

def _supabase_headers(api_key: str) -> dict[str, str]:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _supabase_get_user(email: str, cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Fetch user by email from Supabase REST endpoint.

    Raises:
        DatabaseConnectionError: on connection timeout, DNS failure, or connection drop.
        DatabasePermissionError: on HTTP 401 or 403.
        StorageError: on other HTTP error codes (e.g. 500, 502, 503).
        DatabaseResponseError: on malformed JSON or invalid schema response.

    Returns:
        dict: user record if found.
        None: ONLY if the database query succeeded with HTTP 200 and returned an empty list [].
    """
    url = f"{cfg['url']}/rest/v1/registered_users"
    params = {"email": f"eq.{normalize_email(email)}", "select": "*"}
    try:
        res = requests.get(url, headers=_supabase_headers(cfg["key"]), params=params, timeout=6.0)
    except (requests.Timeout, requests.ConnectionError) as exc:
        raise DatabaseConnectionError(f"Cloud database connection failed: {exc}") from exc
    except requests.RequestException as exc:
        raise StorageError(f"Cloud database request error: {exc}") from exc

    if res.status_code in (401, 403):
        raise DatabasePermissionError(
            f"Cloud database access denied (HTTP {res.status_code}). Verify Supabase service_role_key in secrets."
        )
    if res.status_code != 200:
        raise StorageError(f"Cloud database query failed with HTTP {res.status_code}: {res.text[:200]}")

    try:
        data = res.json()
    except Exception as exc:
        raise DatabaseResponseError(f"Cloud database returned invalid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise DatabaseResponseError(f"Cloud database returned unexpected response type: {type(data).__name__}")

    if not data:
        return None

    user = data[0]
    if not isinstance(user, dict):
        raise DatabaseResponseError("Cloud database returned invalid user record structure.")

    return {
        "id": user.get("id"),
        "email": normalize_email(user.get("email", "")),
        "name": user.get("name", ""),
        "password_hash": user.get("password_hash", ""),
        "role": user.get("role", "analyst"),
        "created_at": user.get("created_at"),
    }


def _supabase_insert_user(
    email: str,
    name: str,
    password_hash: str,
    role: str,
    cfg: dict[str, Any],
) -> tuple[bool, str]:
    """Insert user via Supabase REST endpoint.

    Raises:
        DatabaseConnectionError: on connection timeout, DNS failure, or connection drop.
        DatabasePermissionError: on HTTP 401 or 403.
        StorageError: on unhandled server or HTTP errors.
    """
    url = f"{cfg['url']}/rest/v1/registered_users"
    user_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {
        "id": user_id,
        "email": normalize_email(email),
        "name": str(name).strip(),
        "password_hash": password_hash,
        "role": role,
        "created_at": now_iso,
    }
    try:
        res = requests.post(url, headers=_supabase_headers(cfg["key"]), json=payload, timeout=8.0)
    except (requests.Timeout, requests.ConnectionError) as exc:
        raise DatabaseConnectionError(f"Cloud database connection failed during registration: {exc}") from exc
    except requests.RequestException as exc:
        raise StorageError(f"Cloud database request error during registration: {exc}") from exc

    if res.status_code in (200, 201):
        return True, "User registered successfully."
    elif res.status_code == 409 or "duplicate" in res.text.lower() or "unique" in res.text.lower():
        return False, "An account with this email address is already registered."
    elif res.status_code in (401, 403):
        raise DatabasePermissionError(
            f"Cloud database access denied (HTTP {res.status_code}). Verify Supabase service_role_key in secrets."
        )
    raise StorageError(f"Cloud database rejected registration: HTTP {res.status_code} - {res.text[:200]}")


def _supabase_get_all_users(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Fetch all users from Supabase.

    Raises:
        DatabaseConnectionError: on connection failure.
        DatabasePermissionError: on HTTP 401 or 403.
        StorageError: on server or HTTP failure.
        DatabaseResponseError: on malformed data.
    """
    url = f"{cfg['url']}/rest/v1/registered_users"
    params = {"select": "*"}
    users: dict[str, dict[str, Any]] = {}
    try:
        res = requests.get(url, headers=_supabase_headers(cfg["key"]), params=params, timeout=6.0)
    except (requests.Timeout, requests.ConnectionError) as exc:
        raise DatabaseConnectionError(f"Cloud database connection failed: {exc}") from exc
    except requests.RequestException as exc:
        raise StorageError(f"Cloud database error: {exc}") from exc

    if res.status_code in (401, 403):
        raise DatabasePermissionError(f"Cloud database access denied (HTTP {res.status_code}).")
    if res.status_code != 200:
        raise StorageError(f"Cloud database query failed: HTTP {res.status_code}")

    try:
        data = res.json()
    except Exception as exc:
        raise DatabaseResponseError(f"Cloud database returned invalid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise DatabaseResponseError("Unexpected response structure from cloud database.")

    for u in data:
        if isinstance(u, dict):
            em = normalize_email(u.get("email", ""))
            users[em] = {
                "id": u.get("id"),
                "email": em,
                "name": u.get("name", em),
                "password_hash": u.get("password_hash", ""),
                "role": u.get("role", "analyst"),
                "created_at": u.get("created_at"),
            }
    return users


# ==============================================================================
# Public High-Level Interface
# ==============================================================================

def get_registered_user(email: str, db_path: Path | str | None = None) -> dict[str, Any] | None:
    """Retrieve a registered user from the active storage backend.

    If db_path is provided, reads from that SQLite database (e.g. for testing/offline).
    If Supabase is configured and db_path is None, queries Supabase exclusively and never falls
    back to local SQLite, preserving cloud data isolation.
    """
    clean_email = normalize_email(email)
    if db_path is not None:
        return _sqlite_get_user(clean_email, db_path)

    cfg = get_database_config()
    if cfg["type"] == "supabase":
        return _supabase_get_user(clean_email, cfg)

    return _sqlite_get_user(clean_email, DEFAULT_SQLITE_PATH)


def register_user(
    email: str,
    name: str,
    password: str,
    password_confirm: str,
    db_path: Path | str | None = None,
) -> tuple[bool, str]:
    """Register a new analyst account with full validation and duplicate protection.

    - Public registration always assigns role='analyst'; admin escalation is prevented.
    - Employs thread serialization to block concurrent duplicate email creation.
    - Hashes password using salted PBKDF2-HMAC-SHA256 (600,000 iterations).
    - If db_path is provided, registers in that SQLite database.
    - If Supabase is configured and db_path is None, writes ONLY to Supabase (no local mirroring in cloud mode).
    """
    valid, error_msg = validate_registration_inputs(email, name, password, password_confirm)
    if not valid:
        return False, error_msg

    clean_email = normalize_email(email)
    clean_name = str(name).strip()

    with _REGISTRATION_LOCK:
        # 1. Check if user already exists in static secrets configuration
        from auth import get_configured_users
        existing_configured = get_configured_users()
        if clean_email in existing_configured:
            return False, "An account with this email address is already registered."

        # 2. Check active persistent storage
        if db_path is not None:
            existing = _sqlite_get_user(clean_email, db_path)
            if existing:
                return False, "An account with this email address is already registered."
            pwd_hash = hash_password(password)
            return _sqlite_insert_user(clean_email, clean_name, pwd_hash, "analyst", db_path)

        cfg = get_database_config()
        if cfg["type"] == "supabase":
            existing = _supabase_get_user(clean_email, cfg)
            if existing:
                return False, "An account with this email address is already registered."

            pwd_hash = hash_password(password)
            return _supabase_insert_user(clean_email, clean_name, pwd_hash, "analyst", cfg)

        # SQLite backend
        existing = _sqlite_get_user(clean_email, DEFAULT_SQLITE_PATH)
        if existing:
            return False, "An account with this email address is already registered."

        pwd_hash = hash_password(password)
        return _sqlite_insert_user(clean_email, clean_name, pwd_hash, "analyst", DEFAULT_SQLITE_PATH)


def get_all_users(db_path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Return all accounts (combines static secrets admins with persistent registered users).

    Admin accounts in secrets.toml take precedence over registered users with the same email.
    If Supabase is configured, loads ONLY from Supabase + static secrets; does not merge local SQLite.
    """
    users: dict[str, dict[str, Any]] = {}

    if db_path is not None:
        local_users = _sqlite_get_all_users(db_path)
        users.update(local_users)
    else:
        cfg = get_database_config()
        if cfg["type"] == "supabase":
            cloud_users = _supabase_get_all_users(cfg)
            users.update(cloud_users)
        else:
            local_users = _sqlite_get_all_users(DEFAULT_SQLITE_PATH)
            users.update(local_users)

    # Load configured accounts from secrets (admins take precedence)
    from auth import get_configured_users
    configured = get_configured_users()
    for email, data in configured.items():
        users[email] = data

    return users
