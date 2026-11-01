"""Persistent storage service for datasets, analysis sessions, and project history.

Implements private Supabase Storage object storage for production with user-isolated
paths and strict ownership checks. Local disk fallback is strictly restricted to
explicit local development environments.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests

from app.config import settings


def _email_hash(email: str) -> str:
    """Deterministic hash for user-isolated storage prefixes."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]


class StorageService:

    @staticmethod
    def _supabase_headers() -> Dict[str, str]:
        """Headers for Supabase Storage & PostgREST requests."""
        return {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        }

    @staticmethod
    def upload_to_supabase_storage(object_path: str, data_bytes: bytes) -> Tuple[bool, str]:
        """Upload raw bytes to private Supabase Storage bucket."""
        if not settings.has_supabase():
            return False, "Supabase credentials not configured."

        url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}/{object_path}"
        headers = {
            **StorageService._supabase_headers(),
            "Content-Type": "application/octet-stream",
            "x-upsert": "true",
        }

        try:
            res = requests.post(url, headers=headers, data=data_bytes, timeout=15.0)
            if res.status_code in (200, 201):
                return True, "Upload successful"
            return False, f"Supabase Storage returned HTTP {res.status_code}: {res.text}"
        except Exception as exc:
            return False, f"Supabase Storage network error: {exc}"

    @staticmethod
    def download_from_supabase_storage(object_path: str) -> Tuple[Optional[pd.DataFrame], str]:
        """Download and deserialize Parquet dataset from private Supabase Storage."""
        if not settings.has_supabase():
            return None, "Supabase credentials not configured."

        # Try authenticated endpoint first, then standard object endpoint
        endpoints = [
            f"{settings.SUPABASE_URL}/storage/v1/object/authenticated/{settings.SUPABASE_STORAGE_BUCKET}/{object_path}",
            f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}/{object_path}",
        ]

        headers = StorageService._supabase_headers()

        for url in endpoints:
            try:
                res = requests.get(url, headers=headers, timeout=15.0)
                if res.status_code == 200:
                    bio = io.BytesIO(res.content)
                    df = pd.read_parquet(bio)
                    return df, "Downloaded successfully from private Supabase Storage"
            except Exception:
                continue

        return None, f"Failed to retrieve {object_path} from Supabase Storage."

    @staticmethod
    def delete_from_supabase_storage(object_path: str) -> Tuple[bool, str]:
        """Delete object from Supabase Storage."""
        if not settings.has_supabase():
            return False, "Supabase credentials not configured."

        url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}/{object_path}"
        headers = StorageService._supabase_headers()

        try:
            res = requests.delete(url, headers=headers, timeout=10.0)
            if res.status_code in (200, 204):
                return True, "Deleted from Supabase Storage"
            # Also try batch prefix delete format
            batch_url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}"
            res2 = requests.delete(
                batch_url,
                headers={**headers, "Content-Type": "application/json"},
                json={"prefixes": [object_path]},
                timeout=10.0,
            )
            return res2.status_code in (200, 204), f"Supabase delete status: {res2.status_code}"
        except Exception as exc:
            return False, f"Delete failed: {exc}"

    @staticmethod
    def init_db() -> None:
        """Initialize work history schema in local SQLite (development only)."""
        if settings.IS_PRODUCTION:
            return  # Do not initialize local SQLite in production

        conn = sqlite3.connect(settings.SQLITE_PATH)
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_work_history (
                        id TEXT PRIMARY KEY,
                        user_email TEXT NOT NULL,
                        project_name TEXT NOT NULL,
                        dataset_name TEXT NOT NULL,
                        dataset_signature TEXT NOT NULL,
                        analysis_type TEXT NOT NULL,
                        summary_json TEXT NOT NULL,
                        storage_path TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_work_hist_email ON user_work_history (LOWER(user_email), created_at DESC)"
                )
        finally:
            conn.close()

    @staticmethod
    def save_project(
        user_email: str,
        project_name: str,
        dataset_name: str,
        analysis_type: str,
        summary_json: Dict[str, Any],
        dataframe: Optional[pd.DataFrame] = None,
    ) -> Tuple[bool, str]:
        """Save analysis project with strict account isolation.

        Production requirements:
        - Must persist to Supabase PostgreSQL and private Supabase Storage.
        - Fails explicitly if Supabase Storage is unavailable.
        - Local disk fallback is strictly disabled in production.
        """
        clean_email = user_email.strip().lower()
        project_id = str(uuid.uuid4())
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        object_path = f"{_email_hash(clean_email)}/{project_id}.parquet"
        sig = hashlib.sha256(f"{clean_email}:{project_name}:{now_iso}".encode("utf-8")).hexdigest()[:12]

        parquet_bytes: Optional[bytes] = None
        if dataframe is not None and not dataframe.empty:
            bio = io.BytesIO()
            dataframe.to_parquet(bio, index=False)
            parquet_bytes = bio.getvalue()

        # Handle Production Environment
        if settings.IS_PRODUCTION:
            if not settings.has_supabase():
                return False, (
                    "Production requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to be configured. "
                    "Local disk storage fallback is strictly forbidden in production."
                )

            # Upload Parquet dataset to private Supabase Storage
            storage_path = "metadata_only"
            if parquet_bytes:
                up_ok, up_msg = StorageService.upload_to_supabase_storage(object_path, parquet_bytes)
                if not up_ok:
                    return False, f"Production persistent storage failure: {up_msg}"
                storage_path = f"supabase://{settings.SUPABASE_STORAGE_BUCKET}/{object_path}"

            # Save metadata record to Supabase PostgreSQL
            url = f"{settings.SUPABASE_URL}/rest/v1/user_work_history"
            headers = {
                **StorageService._supabase_headers(),
                "Content-Type": "application/json",
            }
            payload = {
                "id": project_id,
                "user_email": clean_email,
                "project_name": project_name.strip(),
                "dataset_name": dataset_name.strip(),
                "dataset_signature": sig,
                "analysis_type": analysis_type,
                "summary_json": summary_json,
                "storage_path": storage_path,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=6.0)
                if res.status_code in (200, 201):
                    return True, project_id
                return False, f"Failed to persist metadata to Supabase: HTTP {res.status_code} {res.text}"
            except Exception as exc:
                return False, f"Supabase metadata insertion error: {exc}"

        # Development Environment: Try Supabase if configured, otherwise use local dev storage
        storage_path = "metadata_only"
        if parquet_bytes:
            if settings.has_supabase():
                up_ok, _ = StorageService.upload_to_supabase_storage(object_path, parquet_bytes)
                if up_ok:
                    storage_path = f"supabase://{settings.SUPABASE_STORAGE_BUCKET}/{object_path}"

            # If Supabase not configured or failed in dev, use local disk
            if storage_path == "metadata_only":
                user_dir = settings.LOCAL_STORAGE_DIR / "users" / _email_hash(clean_email)
                user_dir.mkdir(parents=True, exist_ok=True)
                file_path = user_dir / f"{project_id}.parquet"
                with open(file_path, "wb") as f:
                    f.write(parquet_bytes)
                storage_path = str(file_path.relative_to(settings.BASE_DIR))

        # Persist metadata (Supabase if available in dev, otherwise local SQLite)
        if settings.has_supabase():
            try:
                url = f"{settings.SUPABASE_URL}/rest/v1/user_work_history"
                headers = {**StorageService._supabase_headers(), "Content-Type": "application/json"}
                payload = {
                    "id": project_id,
                    "user_email": clean_email,
                    "project_name": project_name.strip(),
                    "dataset_name": dataset_name.strip(),
                    "dataset_signature": sig,
                    "analysis_type": analysis_type,
                    "summary_json": summary_json,
                    "storage_path": storage_path,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
                res = requests.post(url, headers=headers, json=payload, timeout=5.0)
                if res.status_code in (200, 201):
                    return True, project_id
            except Exception:
                pass

        # Dev SQLite fallback
        StorageService.init_db()
        conn = sqlite3.connect(settings.SQLITE_PATH)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO user_work_history (
                        id, user_email, project_name, dataset_name, dataset_signature,
                        analysis_type, summary_json, storage_path, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id, clean_email, project_name.strip(), dataset_name.strip(), sig,
                        analysis_type, json.dumps(summary_json), storage_path, now_iso, now_iso,
                    ),
                )
            return True, project_id
        except Exception as exc:
            return False, f"Failed to save project to local database: {exc}"
        finally:
            conn.close()

    @staticmethod
    def list_projects(user_email: str) -> List[Dict[str, Any]]:
        """List all projects belonging strictly to the specified user."""
        clean_email = user_email.strip().lower()

        # Supabase read
        if settings.has_supabase():
            try:
                url = f"{settings.SUPABASE_URL}/rest/v1/user_work_history"
                headers = StorageService._supabase_headers()
                res = requests.get(
                    url,
                    headers=headers,
                    params={"user_email": f"eq.{clean_email}", "order": "created_at.desc"},
                    timeout=5.0,
                )
                if res.status_code == 200:
                    return res.json()
            except Exception:
                pass

        if settings.IS_PRODUCTION:
            return []  # Never read local SQLite in production

        # SQLite fallback in development
        StorageService.init_db()
        conn = sqlite3.connect(settings.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM user_work_history WHERE LOWER(user_email) = ? ORDER BY created_at DESC",
                (clean_email,),
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                if isinstance(d.get("summary_json"), str):
                    try:
                        d["summary_json"] = json.loads(d["summary_json"])
                    except Exception:
                        d["summary_json"] = {}
                rows.append(d)
            return rows
        finally:
            conn.close()

    @staticmethod
    def get_project(project_id: str, user_email: str) -> Optional[Dict[str, Any]]:
        """Retrieve project with strict user ownership verification."""
        clean_email = user_email.strip().lower()
        projects = StorageService.list_projects(clean_email)
        for p in projects:
            if str(p.get("id")) == str(project_id):
                return p
        return None

    @staticmethod
    def load_project_dataframe(project_id: str, user_email: str) -> Tuple[Optional[pd.DataFrame], str]:
        """Download and load project Parquet dataframe with strict ownership verification.

        Production: Must load from private Supabase Storage. Refuses local disk fallback.
        Development: Supabase Storage preferred with local disk fallback if offline.
        """
        clean_email = user_email.strip().lower()

        # 1. Strict ownership verification
        project = StorageService.get_project(project_id, clean_email)
        if not project:
            return None, "Project not found or access denied: strict ownership isolation enforced."

        object_path = f"{_email_hash(clean_email)}/{project_id}.parquet"

        # 2. Try private Supabase Storage
        if settings.has_supabase():
            df, msg = StorageService.download_from_supabase_storage(object_path)
            if df is not None:
                return df, "Dataset loaded from private Supabase Storage."
            if settings.IS_PRODUCTION:
                return None, f"Production storage retrieval failed: {msg}. Local fallback is disabled."

        # 3. Local development fallback
        if not settings.IS_PRODUCTION:
            user_dir = settings.LOCAL_STORAGE_DIR / "users" / _email_hash(clean_email)
            file_path = user_dir / f"{project_id}.parquet"
            if file_path.exists():
                try:
                    df = pd.read_parquet(file_path)
                    return df, "Dataset loaded from local development cache."
                except Exception as exc:
                    return None, f"Local parquet read error: {exc}"

        return None, "Dataset file unavailable for this project."

    @staticmethod
    def delete_project(project_id: str, user_email: str) -> Tuple[bool, str]:
        """Delete project ensuring cross-user isolation and storage cleanup."""
        clean_email = user_email.strip().lower()

        # Verify ownership first
        project = StorageService.get_project(project_id, clean_email)
        if not project:
            return False, "Project not found or you do not have permission to delete it."

        object_path = f"{_email_hash(clean_email)}/{project_id}.parquet"

        # Delete from Supabase Storage
        if settings.has_supabase():
            StorageService.delete_from_supabase_storage(object_path)
            try:
                url = f"{settings.SUPABASE_URL}/rest/v1/user_work_history"
                headers = StorageService._supabase_headers()
                requests.delete(
                    url,
                    headers=headers,
                    params={"id": f"eq.{project_id}", "user_email": f"eq.{clean_email}"},
                    timeout=5.0,
                )
            except Exception:
                pass

        # Cleanup local dev file if exists
        try:
            user_dir = settings.LOCAL_STORAGE_DIR / "users" / _email_hash(clean_email)
            file_path = user_dir / f"{project_id}.parquet"
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass

        # Cleanup local dev SQLite
        if not settings.IS_PRODUCTION:
            StorageService.init_db()
            conn = sqlite3.connect(settings.SQLITE_PATH)
            try:
                with conn:
                    conn.execute(
                        "DELETE FROM user_work_history WHERE id = ? AND LOWER(user_email) = ?",
                        (project_id, clean_email),
                    )
            finally:
                conn.close()

        return True, "Project and associated dataset deleted successfully."

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Platform statistics for administrator command console."""
        user_count = 1
        project_count = 0

        if settings.has_supabase():
            try:
                u_res = requests.get(
                    f"{settings.SUPABASE_URL}/rest/v1/registered_users",
                    headers=StorageService._supabase_headers(),
                    params={"select": "count", "limit": "1"},
                    timeout=3.0,
                )
                p_res = requests.get(
                    f"{settings.SUPABASE_URL}/rest/v1/user_work_history",
                    headers=StorageService._supabase_headers(),
                    params={"select": "count", "limit": "1"},
                    timeout=3.0,
                )
                if u_res.status_code == 200:
                    user_count = len(u_res.json()) or 1
                if p_res.status_code == 200:
                    project_count = len(p_res.json()) or 0
            except Exception:
                pass

        if not settings.IS_PRODUCTION and user_count == 1:
            StorageService.init_db()
            conn = sqlite3.connect(settings.SQLITE_PATH)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM registered_users")
                user_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM user_work_history")
                project_count = cur.fetchone()[0]
            except Exception:
                pass
            finally:
                conn.close()

        total_size = 0
        if settings.LOCAL_STORAGE_DIR.exists():
            for f in settings.LOCAL_STORAGE_DIR.rglob("*"):
                if f.is_file():
                    total_size += f.stat().st_size

        mb_size = total_size / (1024 * 1024)

        return {
            "active_users_count": user_count,
            "total_projects_saved": project_count,
            "storage_size_bytes": total_size,
            "storage_size_formatted": f"{mb_size:.2f} MB" if mb_size >= 1 else f"{total_size / 1024:.1f} KB",
            "database_backend": "Supabase Hosted Cloud Database" if settings.has_supabase() else "Local SQLite Database",
            "database_status": "Connected to cloud database" if settings.has_supabase() else "Local development storage active",
            "server_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "platform_info": "Linux / Docker Container" if os.name != "nt" else "Windows / Local Runtime",
            "python_version": "3.13",
        }


StorageService.init_db()
