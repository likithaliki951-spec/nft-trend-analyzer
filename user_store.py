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
import sys
import threading
from typing import Any
import uuid

# Ensure project root is prioritized in sys.path for robust Streamlit Community Cloud module resolution
_STORE_ROOT = Path(__file__).resolve().parent
if str(_STORE_ROOT) not in sys.path:
    sys.path.insert(0, str(_STORE_ROOT))

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

# Expanded list of common, weak, and leaked passwords to explicitly reject
COMMON_WEAK_PASSWORDS = {
    "password1234",
    "password12345",
    "password123456",
    "admin123456!",
    "welcome1234!",
    "qwertyuiop12",
    "123456789012",
    "changeme1234!",
    "passcode1234!",
    "letmein12345!",
    "iloveyou12345",
    "monkey123456!",
    "dragon123456!",
    "football1234!",
    "trustnoone123!",
    "sunshine1234!",
    "princess1234!",
    "superman1234!",
    "master123456!",
    "login1234567!",
    "default12345!",
    "system123456!",
    "terminal1234!",
    "analyst12345!",
    "nfttrends123!",
    "correcthorse1!",
    "administrator!",
    "abc123456789!",
    "p@ssword1234!",
    "iloveyou123!",
}

# Re-entrant thread lock to serialize duplicate-registration checks and database writes
_REGISTRATION_LOCK = threading.RLock()

# Local SQLite database path inside .streamlit directory (strictly gitignored)
DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent / ".streamlit" / "users.db"


def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and trimmed whitespace."""
    return str(email).strip().lower()


def get_password_strength(password: str, user_email: str = "", user_name: str = "") -> dict[str, Any]:
    """Calculate password strength score, component criteria, and user feedback.

    Enforces:
    - Minimum 12 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one number (0-9)
    - At least one special character
    - Not on common/weak password blacklist
    - Does not contain user's name or email handle
    """
    pwd = str(password or "")
    clean_email = normalize_email(user_email)
    clean_name = str(user_name or "").strip().lower()

    met_criteria = {
        "min_length": len(pwd) >= 12,
        "uppercase": any(c.isupper() for c in pwd),
        "lowercase": any(c.islower() for c in pwd),
        "digit": any(c.isdigit() for c in pwd),
        "special": any(not c.isalnum() for c in pwd),
        "not_common": pwd.strip().lower() not in COMMON_WEAK_PASSWORDS,
    }

    # Check for personal information in password
    has_personal_info = False
    if clean_email and "@" in clean_email:
        handle = clean_email.split("@")[0].strip()
        if len(handle) >= 3 and handle in pwd.lower():
            has_personal_info = True
    if clean_name:
        for part in clean_name.split():
            if len(part) >= 3 and part in pwd.lower():
                has_personal_info = True
    met_criteria["no_personal_info"] = not has_personal_info

    # Scoring
    score = 0
    if met_criteria["min_length"]:
        score += 1
    if len(pwd) >= 16:
        score += 1
    if met_criteria["uppercase"] and met_criteria["lowercase"]:
        score += 1
    if met_criteria["digit"]:
        score += 1
    if met_criteria["special"]:
        score += 1
    if not met_criteria["not_common"] or not met_criteria["no_personal_info"]:
        score = min(score, 1)

    normalized_score = min(4, score)

    strength_map = {
        0: ("Very Weak", "#ef4444", 15),
        1: ("Weak", "#f97316", 35),
        2: ("Moderate", "#eab308", 60),
        3: ("Strong", "#3b82f6", 85),
        4: ("Very Strong", "#10b981", 100),
    }
    label, color, percent = strength_map[normalized_score]

    suggestions = []
    if not met_criteria["min_length"]:
        suggestions.append("Minimum 12 characters required.")
    if not met_criteria["uppercase"]:
        suggestions.append("Add at least one uppercase letter (A-Z).")
    if not met_criteria["lowercase"]:
        suggestions.append("Add at least one lowercase letter (a-z).")
    if not met_criteria["digit"]:
        suggestions.append("Add at least one number (0-9).")
    if not met_criteria["special"]:
        suggestions.append("Add at least one special character (!@#$%^&*...).")
    if not met_criteria["not_common"]:
        suggestions.append("This password is too common or easily guessable.")
    if not met_criteria["no_personal_info"]:
        suggestions.append("Password must not contain parts of your name or email.")

    is_valid = (
        met_criteria["min_length"]
        and met_criteria["uppercase"]
        and met_criteria["lowercase"]
        and met_criteria["digit"]
        and met_criteria["special"]
        and met_criteria["not_common"]
        and met_criteria["no_personal_info"]
    )

    return {
        "score": normalized_score,
        "percent": percent,
        "label": label,
        "color": color,
        "met_criteria": met_criteria,
        "suggestions": suggestions,
        "is_valid": is_valid,
    }


def validate_registration_inputs(
    email: str,
    name: str,
    password: str,
    password_confirm: str,
) -> tuple[bool, str]:
    """Validate user registration inputs against enhanced security and format policies.

    Enforces:
    - Non-empty, trimmed fields
    - Name length >= 2 characters
    - Valid email syntax
    - Password >= 12 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one number (0-9)
    - At least one special character (!@#$%^&*...)
    - Rejection of common/weak passwords
    - Rejection of passwords containing user name or email handle
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
    if len(password) < 12:
        return False, "Password must be at least 12 characters long."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    if not any(not c.isalnum() for c in password):
        return False, "Password must contain at least one special character."

    strength = get_password_strength(password, clean_email, clean_name)
    if not strength["met_criteria"]["not_common"]:
        return False, "This password is too common or easily guessable. Please choose a more complex passphrase."
    if not strength["met_criteria"]["no_personal_info"]:
        return False, "Password must not contain parts of your name or email address."

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


def _sqlite_update_password_hash(
    email: str,
    new_hash: str,
    db_path: Path | str | None = None,
) -> bool:
    """Update a user's password hash in SQLite (used for transparent password hash upgrades)."""
    init_sqlite_db(db_path)
    clean_email = normalize_email(email)
    conn = _get_sqlite_connection(db_path)
    try:
        with conn:
            cur = conn.execute(
                "UPDATE registered_users SET password_hash = ? WHERE email = ?",
                (new_hash, clean_email),
            )
            return cur.rowcount > 0
    except Exception:
        return False
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


def update_user_password_hash(
    email: str,
    new_hash: str,
    db_path: Path | str | None = None,
) -> bool:
    """Update a user's password hash in the active backend for transparent algorithm upgrades."""
    clean_email = normalize_email(email)
    if db_path is not None:
        return _sqlite_update_password_hash(clean_email, new_hash, db_path)

    cfg = get_database_config()
    if cfg["type"] == "sqlite":
        return _sqlite_update_password_hash(clean_email, new_hash, DEFAULT_SQLITE_PATH)

    # For Supabase:
    url = f"{cfg['url']}/rest/v1/registered_users"
    params = {"email": f"eq.{clean_email}"}
    try:
        res = requests.patch(
            url,
            headers=_supabase_headers(cfg["key"]),
            params=params,
            json={"password_hash": new_hash},
            timeout=5.0,
        )
        return res.status_code in (200, 204)
    except Exception:
        return False


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
