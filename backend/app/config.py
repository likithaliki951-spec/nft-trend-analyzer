"""Configuration and environment variables for the NFT Trend Analyzer backend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Ensure backend root .env is loaded if present
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_BACKEND_DIR / ".env", override=False)

OLD_DEFAULT_SECRET = "nft-trend-analyzer-super-secret-key-32-chars-min"
DEV_FALLBACK_SECRET = "dev-local-secret-key-for-testing-only-minimum-32chars"


class Settings:
    # Project Identity
    PROJECT_NAME: str = "NFT Trend Analyzer API"
    VERSION: str = "3.0.0"
    API_V1_PREFIX: str = "/api/v1"

    def __init__(self) -> None:
        # Environment
        self.ENV: str = os.getenv("ENV", "development").lower()
        self.IS_PRODUCTION: bool = self.ENV in ("production", "prod")

        # Secret Key Validation (SEC-02)
        raw_secret = os.getenv("SECRET_KEY", "").strip()
        if self.IS_PRODUCTION:
            if not raw_secret:
                raise RuntimeError(
                    "Production configuration error: SECRET_KEY environment variable is missing or empty. "
                    "A secure, random secret (>= 32 characters) must be configured in production."
                )
            if raw_secret == OLD_DEFAULT_SECRET:
                raise RuntimeError(
                    "Production configuration error: SECRET_KEY cannot use the insecure hardcoded default secret. "
                    "Generate a cryptographically random string (>= 32 characters)."
                )
            if len(raw_secret) < 32:
                raise RuntimeError(
                    f"Production configuration error: SECRET_KEY must be at least 32 characters long (received {len(raw_secret)})."
                )
            self.SECRET_KEY = raw_secret
        else:
            # Dev-only fallback for local testing convenience
            self.SECRET_KEY = raw_secret or DEV_FALLBACK_SECRET

        self.ALGORITHM: str = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

        # Supabase Connectivity
        self.SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.SUPABASE_SERVICE_ROLE_KEY: str = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
        )
        self.SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
        self.SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "user-datasets")

        # Admin Account (SEC-02: Never create default passwords in production)
        self.ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@nfttrends.io").lower()
        self.ADMIN_DEFAULT_PASSWORD: str = os.getenv("ADMIN_DEFAULT_PASSWORD", "")

        # Email Provider Configuration (Free tier: Resend API or SMTP)
        self.EMAIL_PROVIDER_API_KEY: str = (
            os.getenv("EMAIL_PROVIDER_API_KEY", "") or os.getenv("RESEND_API_KEY", "")
        )
        self.EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@nfttrends.io")
        self.SMTP_HOST: str = os.getenv("SMTP_HOST", "")
        self.SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USER: str = os.getenv("SMTP_USER", "")
        self.SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

        self.EMAIL_PROVIDER_CONFIGURED: bool = bool(
            self.EMAIL_PROVIDER_API_KEY or self.SMTP_HOST or os.getenv("SENDGRID_API_KEY")
        )

        # CORS Settings (SEC-03)
        self.FRONTEND_URL: str = os.getenv("FRONTEND_URL", "").rstrip("/")
        self.CORS_ORIGIN_REGEX: Optional[str] = os.getenv("CORS_ORIGIN_REGEX", None)

        if self.IS_PRODUCTION:
            # In production: ONLY explicitly configured production origins. Reject localhost and arbitrary domains.
            trusted: List[str] = []
            if self.FRONTEND_URL and "localhost" not in self.FRONTEND_URL and "127.0.0.1" not in self.FRONTEND_URL:
                trusted.append(self.FRONTEND_URL)
            allowed_raw = os.getenv("ALLOWED_ORIGINS", "")
            if allowed_raw:
                for o in allowed_raw.split(","):
                    clean_o = o.strip()
                    if clean_o and clean_o != "*" and "localhost" not in clean_o and "127.0.0.1" not in clean_o:
                        trusted.append(clean_o)
            self.CORS_ORIGINS = trusted
        else:
            # Development: allow localhost development ports
            dev_origins = [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]
            if self.FRONTEND_URL:
                dev_origins.append(self.FRONTEND_URL)
            self.CORS_ORIGINS = dev_origins

        # File storage paths
        self.BASE_DIR: Path = Path(__file__).resolve().parent.parent
        self.LOCAL_STORAGE_DIR: Path = self.BASE_DIR / "storage"
        self.SQLITE_PATH: Path = self.BASE_DIR / "database.db"

    def has_supabase(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_ROLE_KEY)


settings = Settings()
settings.LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
