"""Authentication, session token security, and access control for NFT Trend Analyzer."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import tomllib
from typing import Any

try:
    import bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    bcrypt = None
    _BCRYPT_AVAILABLE = False

# Ensure project root is prioritized in sys.path for robust Streamlit Community Cloud module resolution
_AUTH_ROOT = Path(__file__).resolve().parent
if str(_AUTH_ROOT) not in sys.path:
    sys.path.insert(0, str(_AUTH_ROOT))

import streamlit as st

AUTH_SESSION_KEY = "auth_session_token"
AUTH_EXPIRY_KEY = "auth_session_expired"
DEFAULT_SESSION_DURATION = 86400  # 24 hours in seconds

# ==============================================================================
# Rate Limiting & Brute-Force Login Attempt Protection
# ==============================================================================

_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_RATE_LIMIT_LOCK = threading.RLock()
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15-minute temporary lockout


def check_login_rate_limit(email: str) -> tuple[bool, str, int]:
    """Check if an email address is currently locked out from login attempts.

    Returns:
        (is_locked: bool, error_message: str, remaining_seconds: int)
    """
    clean_email = str(email).strip().lower()
    now = time.time()
    with _RATE_LIMIT_LOCK:
        attempts = _LOGIN_ATTEMPTS.get(clean_email, [])
        # Prune attempts older than the lockout window
        active_attempts = [t for t in attempts if now - t < LOCKOUT_DURATION_SECONDS]
        _LOGIN_ATTEMPTS[clean_email] = active_attempts

        if len(active_attempts) >= MAX_LOGIN_ATTEMPTS:
            oldest_attempt = min(active_attempts)
            elapsed = now - oldest_attempt
            remaining_seconds = max(1, int(LOCKOUT_DURATION_SECONDS - elapsed))
            remaining_minutes = (remaining_seconds + 59) // 60
            msg = (
                f"Security Notice: Account temporarily locked due to {MAX_LOGIN_ATTEMPTS} failed sign-in attempts. "
                f"Please wait {remaining_minutes} minute(s) before trying again."
            )
            return True, msg, remaining_seconds

        return False, "", 0


def record_login_failure(email: str) -> tuple[int, bool, int]:
    """Record a failed login attempt and return (attempt_count, is_now_locked, remaining_seconds)."""
    clean_email = str(email).strip().lower()
    now = time.time()
    with _RATE_LIMIT_LOCK:
        attempts = _LOGIN_ATTEMPTS.get(clean_email, [])
        active_attempts = [t for t in attempts if now - t < LOCKOUT_DURATION_SECONDS]
        active_attempts.append(now)
        _LOGIN_ATTEMPTS[clean_email] = active_attempts

        count = len(active_attempts)
        if count >= MAX_LOGIN_ATTEMPTS:
            return count, True, LOCKOUT_DURATION_SECONDS
        return count, False, 0


def record_login_success(email: str) -> None:
    """Clear failed login attempt history upon successful authentication."""
    clean_email = str(email).strip().lower()
    with _RATE_LIMIT_LOCK:
        _LOGIN_ATTEMPTS.pop(clean_email, None)


def _load_disk_secrets() -> dict[str, Any]:
    """Directly load secrets from .streamlit/secrets.toml relative to this file or cwd."""
    paths_to_check = [
        Path(__file__).resolve().parent / ".streamlit" / "secrets.toml",
        Path.cwd() / ".streamlit" / "secrets.toml",
    ]
    for p in paths_to_check:
        if p.is_file():
            try:
                with open(p, "rb") as f:
                    return tomllib.load(f)
            except Exception:
                pass
    return {}

def hash_password(
    password: str,
    method: str | None = None,
    iterations: int = 600000,
    salt: bytes | None = None,
) -> str:
    """Hash a password using bcrypt (primary) or salted PBKDF2-HMAC-SHA256 (fallback/configured).

    Bcrypt format: $2b$12$...
    PBKDF2 format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if method == "pbkdf2" or (not _BCRYPT_AVAILABLE and method != "bcrypt"):
        if salt is None:
            salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"

    if _BCRYPT_AVAILABLE:
        # Standard bcrypt with 12 work factor rounds
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

    # Fallback to PBKDF2 if bcrypt is requested but not installed
    if salt is None:
        salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plain password against a stored bcrypt or PBKDF2 hash using constant-time comparison."""
    if not stored_hash or not password:
        return False

    clean_hash = str(stored_hash).strip()

    # 1. Bcrypt hash verification ($2b$, $2a$, $2y$, or bcrypt$ prefix)
    if clean_hash.startswith(("$2b$", "$2a$", "$2y$", "bcrypt$")):
        if clean_hash.startswith("bcrypt$"):
            clean_hash = clean_hash[7:]
        if _BCRYPT_AVAILABLE:
            try:
                return bcrypt.checkpw(password.encode("utf-8"), clean_hash.encode("utf-8"))
            except Exception:
                return False
        return False

    # 2. PBKDF2-HMAC-SHA256 hash verification
    if clean_hash.startswith("pbkdf2_sha256$"):
        try:
            parts = clean_hash.split("$")
            if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
                return False
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected_hash = parts[3]

            derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(derived.hex(), expected_hash)
        except (ValueError, TypeError, IndexError):
            return False

    # 3. Scrypt hash verification (if present)
    if clean_hash.startswith("scrypt$"):
        try:
            parts = clean_hash.split("$")
            if len(parts) == 5:
                n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
                salt = bytes.fromhex(parts[4])
                expected = parts[5]
                derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
                return hmac.compare_digest(derived.hex(), expected)
        except Exception:
            return False

    return False


# ==============================================================================
# Session Token Cryptography (HMAC-SHA256 Signed Tokens)
# ==============================================================================

# Known compromised secrets from version control history and default placeholder tokens
COMPROMISED_COOKIE_SECRETS = {
    "4f8a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a",
    "replace-with-a-random-hex-string-run-openssl-rand-hex-32",
    "replace-with-your-secure-random-32-byte-hex-cookie-secret",
    "replace-with-a-secure-random-64-character-hex-secret",
    "generate-with-python-secrets-token-hex-32",
    "change-me-to-a-secure-random-token",
    "default-insecure-cookie-secret-key",
}

_MODULE_EPHEMERAL_SECRET = secrets.token_hex(32)


def is_secret_insecure(secret: str) -> bool:
    """Return True if the secret is compromised, placeholder, empty, or too short (< 32 chars)."""
    clean = str(secret).strip().lower()
    if not clean:
        return True
    if clean in COMPROMISED_COOKIE_SECRETS:
        return True
    if clean.startswith("replace-with") or clean.startswith("change-me") or clean.startswith("your-secret"):
        return True
    if len(clean) < 32:
        return True
    return False


def is_production_mode() -> bool:
    """Determine whether the application is running in a production or public cloud environment.

    Detects:
    - Streamlit Community Cloud environment flags
    - Explicit ENV/ENVIRONMENT=production environment variable
    - Streamlit secrets [deployment] or environment = "production"
    """
    cloud_vars = [
        "STREAMLIT_SHARING_HOST",
        "IS_STREAMLIT_CLOUD",
        "STREAMLIT_COMMUNITY_CLOUD",
        "STREAMLIT_SERVER_PORT_IS_EXTERNAL",
    ]
    for var in cloud_vars:
        if os.environ.get(var):
            return True

    env_val = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    if env_val in ("production", "prod"):
        return True

    try:
        if hasattr(st, "secrets"):
            if str(st.secrets.get("environment", "")).strip().lower() in ("production", "prod"):
                return True
            if str(st.secrets.get("env", "")).strip().lower() in ("production", "prod"):
                return True
            if isinstance(st.secrets.get("deployment"), dict):
                if str(st.secrets["deployment"].get("environment", "")).strip().lower() in ("production", "prod"):
                    return True
    except Exception:
        pass

    return False


def get_cookie_secret() -> str:
    """Retrieve and validate the HMAC secret key for session signing.

    In production:
    - Enforces a stable, newly rotated cookie secret of >= 32 characters.
    - Rejects previously exposed compromised secrets or template placeholders with RuntimeError.
    - Never silently falls back to ephemeral secrets.

    In local development:
    - Falls back to a secure ephemeral in-process key if no valid secret is configured.
    """
    secret = ""

    # 1. Check [auth] cookie_secret in Streamlit secrets
    try:
        if hasattr(st, "secrets") and "auth" in st.secrets and "cookie_secret" in st.secrets["auth"]:
            secret = str(st.secrets["auth"]["cookie_secret"]).strip()
    except Exception:
        pass

    # 2. Check top-level auth_cookie_secret in Streamlit secrets
    if not secret:
        try:
            if hasattr(st, "secrets") and "auth_cookie_secret" in st.secrets:
                secret = str(st.secrets["auth_cookie_secret"]).strip()
        except Exception:
            pass

    # 3. Check environment variable
    if not secret:
        secret = os.environ.get("AUTH_COOKIE_SECRET", "").strip()

    # 4. Check disk secrets directly from .streamlit/secrets.toml
    if not secret:
        disk_secrets = _load_disk_secrets()
        if disk_secrets:
            disk_cookie = disk_secrets.get("auth", {}).get("cookie_secret") or disk_secrets.get("auth_cookie_secret")
            if disk_cookie:
                secret = str(disk_cookie).strip()

    in_prod = is_production_mode()

    if secret:
        if is_secret_insecure(secret):
            msg = (
                "Security Exception: The configured cookie secret is compromised, placeholder, or insufficient length (<32 chars). "
                "Generate a fresh 32-byte hex secret using: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
            if in_prod:
                raise RuntimeError(msg)
            return _MODULE_EPHEMERAL_SECRET
        return secret

    if in_prod:
        raise RuntimeError(
            "Security Exception: Production deployment requires a configured [auth.cookie_secret] in Streamlit secrets. "
            "Ephemeral fallback is disabled in production to protect user session continuity across dynos. "
            "Generate a 32-byte secret with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    # In local development, secure ephemeral in-process fallback derived per runtime instance
    return _MODULE_EPHEMERAL_SECRET


def create_session_token(
    email: str,
    name: str,
    role: str = "analyst",
    expires_in: int = DEFAULT_SESSION_DURATION,
    secret_key: str | None = None,
) -> str:
    """Generate a cryptographically signed session token with expiration and nonce.

    Token structure: <base64_payload>.<hmac_sha256_signature>
    """
    if secret_key is None:
        secret_key = get_cookie_secret()

    now = int(time.time())
    payload = {
        "email": email.strip().lower(),
        "name": name.strip(),
        "role": role.strip(),
        "iat": now,
        "exp": now + expires_in,
        "nonce": secrets.token_hex(8),
    }

    raw_payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_payload_bytes).decode("ascii").rstrip("=")

    signature = hmac.new(
        secret_key.encode("utf-8"),
        b64_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{b64_payload}.{signature}"


def verify_session_token(token: str, secret_key: str | None = None) -> dict[str, Any] | None:
    """Verify an HMAC-SHA256 signed session token.

    Returns the decoded session payload if valid and unexpired; returns None otherwise.
    """
    if not token or "." not in token:
        return None

    if secret_key is None:
        secret_key = get_cookie_secret()

    try:
        b64_payload, signature = token.split(".", 1)

        # Constant-time signature verification
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            b64_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Pad base64 string if needed
        padding = "=" * (-len(b64_payload) % 4)
        raw_bytes = base64.urlsafe_b64decode(b64_payload + padding)
        payload = json.loads(raw_bytes.decode("utf-8"))

        # Verify expiration
        exp = int(payload.get("exp", 0))
        if time.time() > exp:
            return None

        return payload
    except Exception:
        return None


# ==============================================================================
# User Store & Authentication
# ==============================================================================

def get_configured_users() -> dict[str, dict[str, Any]]:
    """Retrieve user credentials dictionary from st.secrets, disk secrets, or local dev fallback.

    Secrets format in .streamlit/secrets.toml:
    [credentials.users."admin@nfttrends.io"]
    name = "Administrator"
    password_hash = "pbkdf2_sha256$600000$..."
    role = "admin"
    """
    users: dict[str, dict[str, Any]] = {}

    # 1. Streamlit native secrets
    try:
        if hasattr(st, "secrets") and "credentials" in st.secrets:
            secret_users = st.secrets["credentials"].get("users", {})
            for email, data in secret_users.items():
                norm_email = str(email).strip().lower()
                users[norm_email] = {
                    "email": norm_email,
                    "name": str(data.get("name", norm_email)),
                    "password_hash": str(data.get("password_hash", "")),
                    "role": str(data.get("role", "admin")),
                }
    except Exception:
        pass

    # 2. Disk secrets (in case Streamlit was launched from an external working directory)
    if not users:
        disk_secrets = _load_disk_secrets()
        if disk_secrets and "credentials" in disk_secrets:
            disk_users = disk_secrets["credentials"].get("users", {})
            for email, data in disk_users.items():
                norm_email = str(email).strip().lower()
                users[norm_email] = {
                    "email": norm_email,
                    "name": str(data.get("name", norm_email)),
                    "password_hash": str(data.get("password_hash", "")),
                    "role": str(data.get("role", "admin")),
                }

    return users


# Function alias for backwards compatibility
get_users = get_configured_users


def authenticate_user(
    email: str,
    password: str,
    db_path: Path | str | None = None,
) -> tuple[bool, dict[str, Any] | str]:
    """Validate user credentials against configured password hashes or persistent user accounts.

    Enforces:
    - Account rate limiting and brute-force attempt lockout
    - Salted bcrypt and PBKDF2 hash verification
    - Transparent in-place password hash upgrades to bcrypt
    - Propagates database connectivity or permission errors explicitly
    """
    norm_email = email.strip().lower()
    if not norm_email or not password:
        return False, "Please provide both email address and password."

    # Check brute-force login rate limiting
    is_locked, lockout_msg, _ = check_login_rate_limit(norm_email)
    if is_locked:
        return False, lockout_msg

    import user_store

    users = get_configured_users()
    db_user = None

    if norm_email in users:
        user = users[norm_email]
    else:
        try:
            db_user = user_store.get_registered_user(norm_email, db_path=db_path)
        except user_store.DatabasePermissionError as exc:
            return False, f"Authentication service unavailable: Cloud database permission error ({exc})."
        except user_store.DatabaseConnectionError as exc:
            return False, f"Authentication service unavailable: Cloud database connection error ({exc})."
        except user_store.StorageError as exc:
            return False, f"Authentication service unavailable: Database storage error ({exc})."
        user = db_user

    if not users and not db_user:
        return (
            False,
            "Authentication setup required: No authorized accounts are configured in Streamlit secrets (.streamlit/secrets.toml).",
        )

    if not user:
        count, is_now_locked, _ = record_login_failure(norm_email)
        if is_now_locked:
            return (
                False,
                f"Security Warning: Account temporarily locked due to {MAX_LOGIN_ATTEMPTS} failed sign-in attempts. "
                "Please wait 15 minutes before trying again.",
            )
        rem = MAX_LOGIN_ATTEMPTS - count
        return False, f"Invalid email address or password. ({rem} sign-in attempt{'s' if rem != 1 else ''} remaining before lockout.)"

    stored_hash = user.get("password_hash", "")
    if not verify_password(password, stored_hash):
        count, is_now_locked, _ = record_login_failure(norm_email)
        if is_now_locked:
            return (
                False,
                f"Security Warning: Account temporarily locked due to {MAX_LOGIN_ATTEMPTS} failed sign-in attempts. "
                "Please wait 15 minutes before trying again.",
            )
        rem = MAX_LOGIN_ATTEMPTS - count
        return False, f"Invalid email address or password. ({rem} sign-in attempt{'s' if rem != 1 else ''} remaining before lockout.)"

    # Authentication succeeded: reset rate limiter
    record_login_success(norm_email)

    # Transparent migration: upgrade legacy PBKDF2 hashes to bcrypt in active database
    if db_user and stored_hash.startswith("pbkdf2_sha256$") and _BCRYPT_AVAILABLE:
        try:
            new_bcrypt_hash = hash_password(password, method="bcrypt")
            user_store.update_user_password_hash(norm_email, new_bcrypt_hash, db_path=db_path)
        except Exception:
            pass

    return True, {
        "email": user["email"],
        "name": user["name"],
        "role": user.get("role", "analyst"),
    }


# ==============================================================================
# Active Session Management
# ==============================================================================

def get_current_user() -> dict[str, Any] | None:
    """Retrieve the current authenticated user session if valid, or None."""
    # 1. Streamlit Native OIDC (st.user.is_logged_in)
    try:
        if hasattr(st, "user") and getattr(st.user, "is_logged_in", False):
            return {
                "email": str(getattr(st.user, "email", "sso_user@domain.com")).lower(),
                "name": str(getattr(st.user, "name", "SSO Authenticated User")),
                "role": "analyst",
                "provider": "oidc",
                "is_demo": False,
            }
    except Exception:
        pass

    # 2. Cryptographically signed token in session_state
    token = st.session_state.get(AUTH_SESSION_KEY)
    if token:
        payload = verify_session_token(token)
        if payload is not None:
            return payload
        # Token is invalid or expired
        st.session_state.pop(AUTH_SESSION_KEY, None)
        st.session_state[AUTH_EXPIRY_KEY] = True

    return None


def login_user(user_data: dict[str, Any]) -> str:
    """Create session token, record in session state, and clear expiry flag."""
    token = create_session_token(
        email=user_data.get("email", ""),
        name=user_data.get("name", "Analyst"),
        role=user_data.get("role", "analyst"),
    )
    st.session_state[AUTH_SESSION_KEY] = token
    st.session_state.pop(AUTH_EXPIRY_KEY, None)
    return token


def logout_user() -> None:
    """Clear session token, trigger OIDC logout if applicable, and rerun."""
    st.session_state.pop(AUTH_SESSION_KEY, None)
    st.session_state.pop(AUTH_EXPIRY_KEY, None)
    st.session_state.pop("dataset", None)
    st.session_state.pop("dataset_signature", None)

    # Attempt native OIDC logout if available
    try:
        if hasattr(st, "logout") and hasattr(st, "user") and getattr(st.user, "is_logged_in", False):
            st.logout()
    except Exception:
        pass

    st.rerun()


# ==============================================================================
# UI Components: Login Page & Session Status
# ==============================================================================

def render_login_page() -> None:
    """Render the institutional-grade, dark-themed login and registration interface."""
    import user_store

    st.markdown(
        """
        <style>
        .auth-container {
            max-width: 520px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }
        .auth-brand-title {
            font-size: 2.1rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 50%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 0.3rem;
        }
        .auth-brand-subtitle {
            font-size: 0.92rem;
            color: #94a3b8;
            text-align: center;
            line-height: 1.45;
            margin-bottom: 1.2rem;
        }
        .auth-card {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 14px;
            padding: 24px 26px;
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.6);
            margin-bottom: 1.5rem;
        }
        .auth-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            border-bottom: 1px solid #1f2937;
            padding-bottom: 0.8rem;
        }
        .auth-pill {
            font-size: 0.72rem;
            font-weight: 600;
            padding: 3px 9px;
            border-radius: 9999px;
            border: 1px solid;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .pwd-req-box {
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 10px 14px;
            margin-top: 10px;
            margin-bottom: 12px;
            font-size: 0.78rem;
            color: #94a3b8;
        }
        .pwd-req-item {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 3px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Top Branding Header
    st.markdown(
        """
        <div style="text-align: center; margin-top: 1.2rem; margin-bottom: 1.8rem;">
            <div style="display: inline-flex; align-items: center; gap: 8px; margin-bottom: 0.4rem;">
                <span style="font-size: 2rem;">⚡</span>
                <span class="auth-brand-title">NFT Trend Analyzer</span>
            </div>
            <div class="auth-brand-subtitle">
                Institutional Digital Asset Intelligence, Time-Series Forecasting & Machine Learning Valuation
            </div>
            <div style="display: flex; justify-content: center; gap: 0.5rem; flex-wrap: wrap;">
                <span class="auth-pill" style="background: rgba(99, 102, 241, 0.12); color: #818cf8; border-color: rgba(99, 102, 241, 0.3);">
                    🔒 ENTERPRISE SECURITY
                </span>
                <span class="auth-pill" style="background: rgba(16, 185, 129, 0.12); color: #34d399; border-color: rgba(16, 185, 129, 0.3);">
                    🛡️ BCRYPT / RATE-LIMITED
                </span>
                <span class="auth-pill" style="background: rgba(56, 189, 248, 0.12); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3);">
                    v2.4.0
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Session expiration notification
    if st.session_state.get(AUTH_EXPIRY_KEY):
        st.warning(
            "⏳ Your session has expired. For your security, please sign in again with your credentials.",
            icon="⚠️",
        )

    # Centered Form Grid
    _, col_form, _ = st.columns([1, 2, 1])

    with col_form:
        storage_info = user_store.get_storage_info()
        storage_badge_color = "#10b981" if storage_info["is_cloud_persistent"] else "#f59e0b"

        st.markdown(
            f"""
            <div class="auth-card">
                <div class="auth-card-header">
                    <div>
                        <div style="font-size: 1.15rem; font-weight: 700; color: #f8fafc;">
                            Research Terminal Access
                        </div>
                        <div style="font-size: 0.78rem; color: #64748b; margin-top: 2px;">
                            Sign in to access your models, datasets, and project history
                        </div>
                    </div>
                    <span style="font-size: 0.7rem; color: {storage_badge_color}; background: rgba(255,255,255,0.04); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); font-weight: 600;">
                        ● {html.escape(storage_info["backend"])}
                    </span>
                </div>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_register = st.tabs(["🔑 Sign In", "📝 Create Account"])

        # ----------------------------------------------------------------------
        # Tab 1: SIGN IN
        # ----------------------------------------------------------------------
        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                login_email = st.text_input(
                    "Work Email Address",
                    value="",
                    placeholder="name@organization.com",
                    help="Enter your registered analyst or administrator email address.",
                    key="login_email_input",
                )

                show_pwd = st.checkbox("Show password", key="login_show_pwd_chk")

                login_password = st.text_input(
                    "Password",
                    value="",
                    type="default" if show_pwd else "password",
                    placeholder="Enter your password",
                    help="Enter your secure account password.",
                    key="login_pwd_input",
                )

                submit_login = st.form_submit_button(
                    "Sign In to Research Terminal",
                    use_container_width=True,
                    type="primary",
                )

                if submit_login:
                    if not login_email.strip() or not login_password:
                        st.error("Please enter both your email address and password.")
                    else:
                        with st.spinner("Authenticating credentials..."):
                            success, result = authenticate_user(login_email, login_password)
                            if success and isinstance(result, dict):
                                login_user(result)
                                st.success(f"Welcome back, {result.get('name', 'Analyst')}! Loading workspace...")
                                st.rerun()
                            else:
                                st.error(str(result))

        # ----------------------------------------------------------------------
        # Tab 2: CREATE ACCOUNT
        # ----------------------------------------------------------------------
        with tab_register:
            with st.form("register_form", clear_on_submit=False):
                reg_name = st.text_input(
                    "Full Name",
                    value="",
                    placeholder="Alex Morgan",
                    help="Your professional name or display handle.",
                    key="reg_name_input",
                )

                reg_email = st.text_input(
                    "Work Email Address",
                    value="",
                    placeholder="name@organization.com",
                    help="Valid work or institutional email address.",
                    key="reg_email_input",
                )

                show_reg_pwd = st.checkbox("Show password", key="reg_show_pwd_chk")

                reg_password = st.text_input(
                    "Create Password",
                    value="",
                    type="default" if show_reg_pwd else "password",
                    placeholder="Minimum 12 characters",
                    help="Must be at least 12 characters and include uppercase, lowercase, numbers, and special characters.",
                    key="reg_pwd_input",
                )

                reg_password_confirm = st.text_input(
                    "Confirm Password",
                    value="",
                    type="default" if show_reg_pwd else "password",
                    placeholder="Re-enter password",
                    help="Must match your password exactly.",
                    key="reg_pwd_confirm_input",
                )

                # Real-time Password Requirements & Strength Preview
                st.markdown(
                    """
                    <div class="pwd-req-box">
                        <div style="font-weight: 700; color: #cbd5e1; margin-bottom: 6px;">Password Requirements:</div>
                        <div class="pwd-req-item">🔹 At least <b>12 characters</b> long</div>
                        <div class="pwd-req-item">🔹 At least one <b>uppercase letter</b> (A-Z)</div>
                        <div class="pwd-req-item">🔹 At least one <b>lowercase letter</b> (a-z)</div>
                        <div class="pwd-req-item">🔹 At least one <b>numeric digit</b> (0-9)</div>
                        <div class="pwd-req-item">🔹 At least one <b>special character</b> (!@#$%^&*...)</div>
                        <div class="pwd-req-item">🔹 Must not be a common or easily guessable passphrase</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Password strength assessment if user has entered characters
                if reg_password:
                    strength = user_store.get_password_strength(reg_password, reg_email, reg_name)
                    st.markdown(
                        f"""
                        <div style="margin-top: 4px; margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 4px;">
                                <span style="color: #94a3b8;">Password Strength:</span>
                                <span style="color: {strength['color']}; font-weight: 700;">{strength['label']}</span>
                            </div>
                            <div style="background: #1e293b; border-radius: 9999px; height: 6px; width: 100%; overflow: hidden;">
                                <div style="background: {strength['color']}; height: 100%; width: {strength['percent']}%; transition: width 0.3s ease;"></div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                submit_reg = st.form_submit_button(
                    "Create Analyst Account",
                    use_container_width=True,
                    type="primary",
                )

                if submit_reg:
                    with st.spinner("Validating and registering account..."):
                        try:
                            reg_success, reg_msg = user_store.register_user(
                                reg_email, reg_name, reg_password, reg_password_confirm
                            )
                            if reg_success:
                                storage_info = user_store.get_storage_info()
                                backend_name = storage_info.get("backend", "database")
                                st.success(
                                    f"🎉 Account registered successfully in **{backend_name}**!\n\n"
                                    "Please switch to the **Sign In** tab above to access your research terminal."
                                )
                            else:
                                st.error(f"Registration failed: {reg_msg}")
                        except user_store.DatabasePermissionError as exc:
                            st.error(f"Registration failed: Cloud database permission error ({exc}).")
                        except user_store.DatabaseConnectionError as exc:
                            st.error(
                                f"Registration failed: Cloud database connection error ({exc}).\n\n"
                                "💡 If demonstrating locally, comment out the `[supabase]` section in `.streamlit/secrets.toml` "
                                "to activate the built-in Local SQLite database (`.streamlit/users.db`)."
                            )
                        except user_store.StorageError as exc:
                            st.error(f"Registration failed: Database storage error ({exc}).")

        # Streamlit Native OIDC SSO Button (if configured)
        try:
            if hasattr(st, "secrets") and "auth" in st.secrets and hasattr(st, "login"):
                st.markdown(
                    """
                    <div style="text-align: center; margin: 1rem 0; font-size: 0.75rem; color: #64748b;">
                        ── OR SIGN IN WITH IDENTITY PROVIDER ──
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("🌐 Single Sign-On (OIDC)", use_container_width=True):
                    st.login()
        except Exception:
            pass

        st.markdown("</div>", unsafe_allow_html=True)

    # Public Feature & Security Overview
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(
            """
            <div style="background: rgba(17, 24, 39, 0.7); border: 1px solid #1f2937; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-weight: 700; color: #818cf8; font-size: 0.88rem; margin-bottom: 6px;">
                    📊 Multi-Modal Ingestion & PCA
                </div>
                <div style="font-size: 0.78rem; color: #94a3b8; line-height: 1.45;">
                    Dual-dataset join engine with cardinality validation and dynamic PCA feature decomposition.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            """
            <div style="background: rgba(17, 24, 39, 0.7); border: 1px solid #1f2937; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-weight: 700; color: #38bdf8; font-size: 0.88rem; margin-bottom: 6px;">
                    🔒 Institutional-Grade Security
                </div>
                <div style="font-size: 0.78rem; color: #94a3b8; line-height: 1.45;">
                    Salted bcrypt hashing, brute-force rate-limiting, and strict user-isolated project history.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_c:
        st.markdown(
            """
            <div style="background: rgba(17, 24, 39, 0.7); border: 1px solid #1f2937; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-weight: 700; color: #34d399; font-size: 0.88rem; margin-bottom: 6px;">
                    🏷️ Multi-Model Valuation Suite
                </div>
                <div style="font-size: 0.78rem; color: #94a3b8; line-height: 1.45;">
                    Random Forest, Gradient Boosting, SVM, and balanced Logistic Regression valuation bands.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="text-align: center; margin-top: 2rem; font-size: 0.75rem; color: #64748b;">
            NFT Trend Analyzer &bull; Version 2.4.0 &bull; Secure Research Environment
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_user_badge_and_logout(user: dict[str, Any] | None) -> None:
    """Render logged-in user indicator and sign-out button in the sidebar."""
    if not user or not isinstance(user, dict):
        return
    email = user.get("email", "Analyst")
    role = user.get("role", "researcher").replace("_", " ").title()

    st.markdown(
        f"""
        <div style="background: rgba(19, 27, 46, 0.9); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <div style="font-size: 0.8rem; font-weight: 700; color: #f8fafc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 170px;">
                        👤 {html.escape(email)}
                    </div>
                    <div style="font-size: 0.7rem; color: #8b5cf6; font-weight: 600; margin-top: 2px;">
                        ● {html.escape(role)}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🚪 Sign Out", key="auth_sign_out_btn", use_container_width=True):
        logout_user()


def require_authentication() -> dict[str, Any]:
    """Enforce authentication on every rerun.

    If the user is authenticated, returns user metadata dictionary.
    If unauthenticated, renders the login page and halts execution immediately via st.stop().
    """
    current_user = get_current_user()
    if current_user is None:
        render_login_page()
        st.stop()

    return current_user
