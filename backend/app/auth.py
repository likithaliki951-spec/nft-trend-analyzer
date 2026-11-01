"""Authentication, security, password policies, and JWT token management."""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
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
# Database / User Store
# ==============================================================================

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
                    role TEXT NOT NULL DEFAULT 'analyst',
                    created_at TEXT NOT NULL
                )
                """
            )
            # SEC-02: Do NOT auto-create default administrator account or password in production
            if not settings.IS_PRODUCTION and settings.ADMIN_DEFAULT_PASSWORD:
                cur = conn.cursor()
                cur.execute("SELECT id FROM registered_users WHERE email = ?", (settings.ADMIN_EMAIL,))
                if not cur.fetchone():
                    admin_id = str(uuid.uuid4())
                    admin_hash = hash_password(settings.ADMIN_DEFAULT_PASSWORD)
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    conn.execute(
                        """
                        INSERT INTO registered_users (id, email, name, password_hash, role, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (admin_id, settings.ADMIN_EMAIL, "Platform Administrator", admin_hash, "admin", now_iso),
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


init_user_db()
init_reset_token_db()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieve user from Supabase or fallback SQLite."""
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
                if data and isinstance(data, list):
                    return data[0]
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
            return dict(row)
        return None
    finally:
        conn.close()


def create_user(email: str, name: str, password_hash: str, role: str = "analyst") -> Tuple[bool, str]:
    """Create new registered user."""
    clean_email = email.strip().lower()
    user_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Check existing
    if get_user_by_email(clean_email):
        return False, "An account with this email address already exists."

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
        payload = {
            "id": user_id,
            "email": clean_email,
            "name": name.strip(),
            "password_hash": password_hash,
            "role": role,
            "created_at": now_iso,
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
            payload = {
                "id": user_id,
                "email": clean_email,
                "name": name.strip(),
                "password_hash": password_hash,
                "role": role,
                "created_at": now_iso,
            }
            res = requests.post(url, headers=headers, json=payload, timeout=5.0)
            if res.status_code in (200, 201):
                try:
                    conn = sqlite3.connect(settings.SQLITE_PATH)
                    with conn:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO registered_users (id, email, name, password_hash, role, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (user_id, clean_email, name.strip(), password_hash, role, now_iso),
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
                INSERT INTO registered_users (id, email, name, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, clean_email, name.strip(), password_hash, role, now_iso),
            )
        return True, user_id
    except sqlite3.IntegrityError:
        return False, "An account with this email address already exists."
    except Exception as exc:
        return False, f"Failed to register user: {exc}"
    finally:
        conn.close()


def update_user_password(email: str, new_hash: str) -> bool:
    """Update password hash."""
    clean_email = email.strip().lower()

    if settings.IS_PRODUCTION:
        if not settings.has_supabase():
            return False

        url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        }
        try:
            res = requests.patch(
                url,
                headers=headers,
                params={"email": f"eq.{clean_email}"},
                json={"password_hash": new_hash},
                timeout=4.0,
            )
            return res.status_code in (200, 204)
        except Exception:
            return False

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
                params={"email": f"eq.{clean_email}"},
                json={"password_hash": new_hash},
                timeout=4.0,
            )
            if res.status_code in (200, 204):
                return True
        except Exception:
            pass

    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        with conn:
            cur = conn.execute(
                "UPDATE registered_users SET password_hash = ? WHERE LOWER(email) = ?",
                (new_hash, clean_email),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def get_all_users_admin() -> list[Dict[str, Any]]:
    """List all users for admin console."""
    if settings.has_supabase():
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/registered_users"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.get(url, headers=headers, params={"select": "id,email,name,role,created_at"}, timeout=4.0)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass

    if settings.IS_PRODUCTION:
        return []

    conn = sqlite3.connect(settings.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email, name, role, created_at FROM registered_users ORDER BY created_at DESC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


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
    """FastAPI dependency to extract and verify the current authenticated user."""
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

    # SEC-04: Reset tokens cannot be used as session authorization tokens
    if payload.get("type") == "reset":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password reset tokens cannot be used for general API authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "name": payload.get("name"),
        "role": payload.get("role", "analyst"),
    }


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """FastAPI dependency requiring administrator privileges."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required for this resource.",
        )
    return user
