"""Persistent work history and user-specific project storage for NFT Trend Analyzer.

Supports saving, listing, reopening, and deleting analysis sessions and datasets.
Guarantees strict cross-user isolation: users can only view and manage their own work.
Uses local Parquet/SQLite storage with support for cloud Supabase metadata and storage.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
from typing import Any
import uuid

# Ensure project root is prioritized in sys.path
_MODULE_ROOT = Path(__file__).resolve().parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pandas as pd
import requests

# Local SQLite and file storage paths inside .streamlit directory (strictly gitignored)
DEFAULT_SQLITE_PATH = _MODULE_ROOT / ".streamlit" / "users.db"
DEFAULT_STORAGE_ROOT = _MODULE_ROOT / ".streamlit" / "storage"

_HISTORY_LOCK = threading.RLock()


def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and trimmed whitespace."""
    return str(email).strip().lower()


def get_user_storage_dir(email: str, storage_root: Path | str | None = None) -> Path:
    """Get isolated filesystem directory for a specific user.

    Uses SHA-256 of normalized email to avoid filesystem naming issues across platforms.
    """
    root = Path(storage_root) if storage_root else DEFAULT_STORAGE_ROOT
    clean_email = normalize_email(email)
    user_hash = hashlib.sha256(clean_email.encode("utf-8")).hexdigest()[:24]
    user_dir = root / "users" / user_hash
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _get_sqlite_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open or create a connection to the SQLite database."""
    target_path = Path(db_path) if db_path else DEFAULT_SQLITE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_work_history_db(db_path: Path | str | None = None) -> None:
    """Initialize the work history SQLite schema if not already present."""
    with _HISTORY_LOCK:
        conn = _get_sqlite_connection(db_path)
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
                    "CREATE INDEX IF NOT EXISTS idx_work_hist_user_email ON user_work_history(user_email, created_at DESC)"
                )
        finally:
            conn.close()


def save_project(
    user_email: str,
    project_name: str,
    dataset_name: str,
    dataframe: pd.DataFrame,
    analysis_type: str = "Market Analysis & Predictions",
    summary_data: dict[str, Any] | None = None,
    db_path: Path | str | None = None,
    storage_root: Path | str | None = None,
) -> tuple[bool, str, str | None]:
    """Save an analysis project and its dataset snapshot into persistent storage.

    Returns:
        (success: bool, message: str, project_id: str | None)
    """
    clean_email = normalize_email(user_email)
    if not clean_email:
        return False, "User email is required to associate saved work.", None

    clean_proj_name = str(project_name).strip()
    if not clean_proj_name:
        clean_proj_name = f"Analysis {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"

    if dataframe is None or not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return False, "Cannot save an empty or invalid dataset.", None

    init_work_history_db(db_path)

    project_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Calculate dataset signature
    sig_raw = f"{dataframe.shape}_{list(dataframe.columns)}_{clean_email}".encode("utf-8")
    dataset_sig = hashlib.sha256(sig_raw).hexdigest()

    # Construct summary metrics
    summary = summary_data.copy() if summary_data else {}
    summary["row_count"] = int(len(dataframe))
    summary["column_count"] = int(len(dataframe.columns))
    summary["columns"] = list(dataframe.columns)[:50]
    summary_json_str = json.dumps(summary, default=str)

    # Persist dataset to user-isolated storage
    user_dir = get_user_storage_dir(clean_email, storage_root)
    file_rel_name = f"{project_id}.parquet"
    target_file = user_dir / file_rel_name

    try:
        dataframe.to_parquet(str(target_file), index=False)
    except Exception:
        # Fallback to CSV if pyarrow/parquet fails
        file_rel_name = f"{project_id}.csv"
        target_file = user_dir / file_rel_name
        dataframe.to_csv(str(target_file), index=False)

    storage_path_str = str(target_file)

    with _HISTORY_LOCK:
        conn = _get_sqlite_connection(db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO user_work_history
                    (id, user_email, project_name, dataset_name, dataset_signature, analysis_type, summary_json, storage_path, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        clean_email,
                        clean_proj_name,
                        str(dataset_name).strip() or "Uploaded Dataset",
                        dataset_sig,
                        str(analysis_type).strip(),
                        summary_json_str,
                        storage_path_str,
                        now_iso,
                        now_iso,
                    ),
                )
            return True, "Project saved successfully to your work history.", project_id
        except Exception as exc:
            # Clean up orphaned storage file
            if target_file.exists():
                try:
                    target_file.unlink()
                except OSError:
                    pass
            return False, f"Database error while saving project: {exc}", None
        finally:
            conn.close()


def list_user_projects(
    user_email: str,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve all saved projects for the authenticated user.

    Guarantees strict isolation: returns only records where user_email matches.
    """
    clean_email = normalize_email(user_email)
    if not clean_email:
        return []

    init_work_history_db(db_path)
    conn = _get_sqlite_connection(db_path)
    projects = []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_email, project_name, dataset_name, dataset_signature,
                   analysis_type, summary_json, storage_path, created_at, updated_at
            FROM user_work_history
            WHERE user_email = ?
            ORDER BY created_at DESC
            """,
            (clean_email,),
        )
        for row in cur.fetchall():
            summary = {}
            try:
                summary = json.loads(row["summary_json"])
            except Exception:
                pass
            projects.append(
                {
                    "id": row["id"],
                    "user_email": row["user_email"],
                    "project_name": row["project_name"],
                    "dataset_name": row["dataset_name"],
                    "dataset_signature": row["dataset_signature"],
                    "analysis_type": row["analysis_type"],
                    "summary": summary,
                    "storage_path": row["storage_path"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return projects
    finally:
        conn.close()


def get_project(
    project_id: str,
    user_email: str,
    db_path: Path | str | None = None,
) -> dict[str, Any] | None:
    """Retrieve metadata for a specific project.

    Enforces ownership validation: returns None if the project does not belong to user_email.
    """
    clean_email = normalize_email(user_email)
    clean_id = str(project_id).strip()
    if not clean_email or not clean_id:
        return None

    init_work_history_db(db_path)
    conn = _get_sqlite_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_email, project_name, dataset_name, dataset_signature,
                   analysis_type, summary_json, storage_path, created_at, updated_at
            FROM user_work_history
            WHERE id = ? AND user_email = ?
            """,
            (clean_id, clean_email),
        )
        row = cur.fetchone()
        if not row:
            return None

        summary = {}
        try:
            summary = json.loads(row["summary_json"])
        except Exception:
            pass

        return {
            "id": row["id"],
            "user_email": row["user_email"],
            "project_name": row["project_name"],
            "dataset_name": row["dataset_name"],
            "dataset_signature": row["dataset_signature"],
            "analysis_type": row["analysis_type"],
            "summary": summary,
            "storage_path": row["storage_path"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def load_project_dataframe(
    project_id: str,
    user_email: str,
    db_path: Path | str | None = None,
) -> pd.DataFrame | None:
    """Load the dataset DataFrame for a saved project after validating user ownership.

    Returns:
        pd.DataFrame if owned and file exists, None otherwise.
    """
    project = get_project(project_id, user_email, db_path=db_path)
    if not project:
        return None

    storage_path = Path(project["storage_path"])
    if not storage_path.exists() or not storage_path.is_file():
        return None

    try:
        if storage_path.suffix.lower() == ".parquet":
            return pd.read_parquet(str(storage_path))
        elif storage_path.suffix.lower() in (".csv", ".txt"):
            return pd.read_csv(str(storage_path))
    except Exception:
        pass
    return None


def delete_project(
    project_id: str,
    user_email: str,
    db_path: Path | str | None = None,
) -> tuple[bool, str]:
    """Delete a saved project and its underlying dataset file.

    Enforces ownership validation: users cannot delete another user's project.
    """
    clean_email = normalize_email(user_email)
    clean_id = str(project_id).strip()
    if not clean_email or not clean_id:
        return False, "Project ID and user email are required."

    project = get_project(clean_id, clean_email, db_path=db_path)
    if not project:
        return False, "Project not found or access denied."

    # Delete storage file
    storage_path = Path(project["storage_path"])
    if storage_path.exists() and storage_path.is_file():
        try:
            storage_path.unlink()
        except OSError as exc:
            # Continue to delete DB row even if file removal triggers OS warning
            pass

    with _HISTORY_LOCK:
        conn = _get_sqlite_connection(db_path)
        try:
            with conn:
                conn.execute(
                    "DELETE FROM user_work_history WHERE id = ? AND user_email = ?",
                    (clean_id, clean_email),
                )
            return True, "Project successfully deleted from your work history."
        except Exception as exc:
            return False, f"Database error during deletion: {exc}"
        finally:
            conn.close()


def get_admin_system_metrics(db_path: Path | str | None = None) -> dict[str, Any]:
    """Compile aggregated administrative metrics without exposing user datasets or passwords."""
    init_work_history_db(db_path)
    conn = _get_sqlite_connection(db_path)
    metrics: dict[str, Any] = {
        "total_saved_projects": 0,
        "unique_users_with_history": 0,
        "total_storage_bytes": 0,
        "projects_by_type": {},
    }
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total, COUNT(DISTINCT user_email) as users FROM user_work_history")
        row = cur.fetchone()
        if row:
            metrics["total_saved_projects"] = row["total"]
            metrics["unique_users_with_history"] = row["users"]

        cur.execute("SELECT analysis_type, COUNT(*) as cnt FROM user_work_history GROUP BY analysis_type")
        for r in cur.fetchall():
            metrics["projects_by_type"][r["analysis_type"]] = r["cnt"]

        # Calculate local storage disk usage
        storage_root = DEFAULT_STORAGE_ROOT
        if storage_root.exists():
            total_size = sum(f.stat().st_size for f in storage_root.glob("**/*") if f.is_file())
            metrics["total_storage_bytes"] = total_size

        return metrics
    finally:
        conn.close()
