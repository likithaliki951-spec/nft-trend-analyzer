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
import time
import tomllib
from typing import Any

import streamlit as st

AUTH_SESSION_KEY = "auth_session_token"
AUTH_EXPIRY_KEY = "auth_session_expired"
DEFAULT_SESSION_DURATION = 86400  # 24 hours in seconds


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

def hash_password(password: str, iterations: int = 600000, salt: bytes | None = None) -> str:
    """Hash a password using salted PBKDF2-HMAC-SHA256 with 600,000 iterations.

    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plain password against a stored PBKDF2 hash using constant-time comparison."""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = parts[3]

        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived.hex(), expected_hash)
    except (ValueError, TypeError, IndexError):
        return False


# ==============================================================================
# Session Token Cryptography (HMAC-SHA256 Signed Tokens)
# ==============================================================================

_MODULE_EPHEMERAL_SECRET = secrets.token_hex(32)


def get_cookie_secret() -> str:
    """Retrieve the cryptographic HMAC secret key from secrets.toml or environment."""
    # 1. Check [auth] cookie_secret in Streamlit secrets
    try:
        if hasattr(st, "secrets") and "auth" in st.secrets and "cookie_secret" in st.secrets["auth"]:
            secret = str(st.secrets["auth"]["cookie_secret"]).strip()
            if secret:
                return secret
    except Exception:
        pass

    # 2. Check top-level auth_cookie_secret in Streamlit secrets
    try:
        if hasattr(st, "secrets") and "auth_cookie_secret" in st.secrets:
            secret = str(st.secrets["auth_cookie_secret"]).strip()
            if secret:
                return secret
    except Exception:
        pass

    # 3. Check disk secrets directly from .streamlit/secrets.toml
    disk_secrets = _load_disk_secrets()
    if disk_secrets:
        disk_cookie = disk_secrets.get("auth", {}).get("cookie_secret") or disk_secrets.get("auth_cookie_secret")
        if disk_cookie:
            return str(disk_cookie).strip()

    # 4. Secure ephemeral in-process fallback derived per runtime instance (never hardcoded)
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


def authenticate_user(email: str, password: str) -> tuple[bool, dict[str, Any] | str]:
    """Validate user credentials against configured password hashes.

    Returns (True, user_payload) on success, or (False, error_message) on failure.
    """
    norm_email = email.strip().lower()
    if not norm_email or not password:
        return False, "Please provide both email address and password."

    users = get_configured_users()
    if not users:
        return (
            False,
            "Authentication setup required: No authorized accounts are configured in Streamlit secrets (.streamlit/secrets.toml).",
        )

    user = users.get(norm_email)
    if not user:
        return False, "Invalid email address or password."

    stored_hash = user.get("password_hash", "")
    if not verify_password(password, stored_hash):
        return False, "Invalid email address or password."

    return True, {
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
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
    """Render the dark-themed login interface and public application branding."""
    st.markdown(
        """
        <div style="text-align: center; margin-top: 1.5rem; margin-bottom: 2rem;">
            <div style="font-size: 2.2rem; font-weight: 800; letter-spacing: -0.03em; color: #f8fafc;">
                ⚡ NFT Trend Analyzer
            </div>
            <div style="font-size: 0.95rem; color: #94a3b8; margin-top: 0.4rem; max-width: 580px; margin-left: auto; margin-right: auto;">
                Time-Series Market Intelligence, Leak-Free Machine Learning, & Valuation Categorization
            </div>
            <div style="display: flex; justify-content: center; gap: 0.5rem; margin-top: 0.8rem;">
                <span style="background: rgba(139, 92, 246, 0.15); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 9999px; padding: 2px 10px; font-size: 0.72rem; font-weight: 600;">
                    🔒 AUTHENTICATION REQUIRED
                </span>
                <span style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 9999px; padding: 2px 10px; font-size: 0.72rem; font-weight: 600;">
                    v2.4.0
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Session expiration alert
    if st.session_state.get(AUTH_EXPIRY_KEY):
        st.warning(
            "⏳ Your session has expired. For your security, please sign in again.",
            icon="⚠️",
        )

    # Centered login card
    col_left, col_center, col_right = st.columns([1, 1.8, 1])
    with col_center:
        st.markdown(
            """
            <div style="background: #131b2e; border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 12px; padding: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.4); margin-bottom: 1.5rem;">
                <div style="font-size: 1.15rem; font-weight: 700; color: #f1f5f9; margin-bottom: 0.25rem;">
                    Sign In to Research Terminal
                </div>
                <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 1.2rem;">
                    Enter your authorized research credentials below.
                </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            email_placeholder = "admin@yourfirm.com"
            email_input = st.text_input(
                "Work Email",
                placeholder=email_placeholder,
                help="Your registered analyst email address.",
                key="login_email_input",
            )
            password_input = st.text_input(
                "Password",
                type="password",
                placeholder="Enter password",
                help="Your secure authentication key.",
                key="login_pwd_input",
            )

            submit_login = st.form_submit_button(
                "Sign In to Terminal",
                use_container_width=True,
                type="primary",
            )

            if submit_login:
                with st.spinner("Verifying credentials..."):
                    success, result = authenticate_user(email_input, password_input)
                    if success and isinstance(result, dict):
                        login_user(result)
                        st.success("Authentication successful! Loading analytics environment...")
                        st.rerun()
                    else:
                        st.error(f"Authentication failed: {result}")

        # Check if user accounts are configured in Streamlit secrets
        users = get_configured_users()
        if not users:
            st.warning(
                "🔒 **Authentication Setup Required**\n\n"
                "No user accounts are configured in Streamlit secrets.\n\n"
                "To configure your administrator credentials, add your email and hashed password to "
                "`.streamlit/secrets.toml` (locally) or the Secrets tab in Streamlit Community Cloud.\n\n"
                "Generate a hash via: `python -c \"import auth; print(auth.hash_password('YOUR_PASSWORD'))\"`",
                icon="⚠️",
            )

        # Streamlit Native OIDC SSO Button (if authlib / OIDC is configured)
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

    # Public Feature & Security Overview (renders safely without exposing data)
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(
            """
            <div style="background: rgba(19, 27, 46, 0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 14px;">
                <div style="font-weight: 600; color: #8b5cf6; font-size: 0.85rem; margin-bottom: 4px;">📊 7 Analytics Modules</div>
                <div style="font-size: 0.75rem; color: #94a3b8; line-height: 1.4;">
                    Market overview, time-series aggregation, social engagement correlations, SVR, and GRU sequence forecasting.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            """
            <div style="background: rgba(19, 27, 46, 0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 14px;">
                <div style="font-weight: 600; color: #38bdf8; font-size: 0.85rem; margin-bottom: 4px;">🔒 Zero-Exposure Security</div>
                <div style="font-size: 0.75rem; color: #94a3b8; line-height: 1.4;">
                    CSV datasets are processed purely in ephemeral session memory. No user files are written to disk or third-party servers.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_c:
        st.markdown(
            """
            <div style="background: rgba(19, 27, 46, 0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 14px;">
                <div style="font-weight: 600; color: #10b981; font-size: 0.85rem; margin-bottom: 4px;">🏷️ Valuation Intelligence</div>
                <div style="font-size: 0.75rem; color: #94a3b8; line-height: 1.4;">
                    Random Forest & Support Vector classification across price bands, plus live CoinGecko & OpenSea market stats.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="text-align: center; margin-top: 2rem; font-size: 0.75rem; color: #475569;">
            Need access or forgot your password? Contact your research administrator.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_user_badge_and_logout(user: dict[str, Any]) -> None:
    """Render logged-in user indicator and sign-out button in the sidebar."""
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
