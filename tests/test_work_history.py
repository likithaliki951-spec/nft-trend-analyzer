"""Automated test suite for user work history, project persistence, and cross-user isolation."""

from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
import pytest

from work_history import (
    delete_project,
    get_admin_system_metrics,
    get_project,
    init_work_history_db,
    list_user_projects,
    load_project_dataframe,
    normalize_email,
    save_project,
)


@pytest.fixture
def temp_workspace():
    """Create isolated temporary database and storage directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)
        db_path = dir_path / "test_users.db"
        storage_path = dir_path / "storage"
        init_work_history_db(db_path)
        yield db_path, storage_path


def make_sample_dataframe() -> pd.DataFrame:
    """Create a test DataFrame mimicking an NFT analytics session."""
    return pd.DataFrame(
        {
            "token_id": [101, 102, 103, 104, 105],
            "collection_name": ["CryptoPunks", "CryptoPunks", "BoredApe", "BoredApe", "Azuki"],
            "sale_price_eth": [15.5, 22.0, 12.3, 18.0, 8.5],
            "sales_count": [3, 5, 2, 8, 1],
            "twitter_mentions": [120, 340, 210, 500, 80],
        }
    )


def test_save_and_list_user_projects(temp_workspace):
    db_path, storage_path = temp_workspace
    user_a = "analyst_a@nfttrends.io"
    df = make_sample_dataframe()

    success, msg, project_id = save_project(
        user_email=user_a,
        project_name="Punks & Apes Q3 Evaluation",
        dataset_name="punks_apes.csv",
        dataframe=df,
        analysis_type="Market Analysis & Predictions",
        summary_data={"best_model": "Random Forest", "r2": 0.88},
        db_path=db_path,
        storage_root=storage_path,
    )

    assert success is True
    assert project_id is not None
    assert "successfully" in msg.lower()

    # List projects for User A
    projects = list_user_projects(user_a, db_path=db_path)
    assert len(projects) == 1
    proj = projects[0]
    assert proj["id"] == project_id
    assert proj["project_name"] == "Punks & Apes Q3 Evaluation"
    assert proj["dataset_name"] == "punks_apes.csv"
    assert proj["summary"]["best_model"] == "Random Forest"
    assert proj["summary"]["row_count"] == 5


def test_cross_user_isolation_strictly_enforced(temp_workspace):
    """User B must NOT be able to view, load, or delete User A's saved project."""
    db_path, storage_path = temp_workspace
    user_a = "analyst_a@nfttrends.io"
    user_b = "adversary_b@otherfirm.com"
    df = make_sample_dataframe()

    # User A saves a project
    success, _, project_id = save_project(
        user_email=user_a,
        project_name="Confidential Alpha Analysis",
        dataset_name="alpha.csv",
        dataframe=df,
        db_path=db_path,
        storage_root=storage_path,
    )
    assert success is True

    # User B lists projects -> Should be EMPTY
    b_projects = list_user_projects(user_b, db_path=db_path)
    assert len(b_projects) == 0

    # User B attempts to get project by ID -> Must return None
    forbidden_proj = get_project(project_id, user_b, db_path=db_path)
    assert forbidden_proj is None

    # User B attempts to load User A's DataFrame -> Must return None
    forbidden_df = load_project_dataframe(project_id, user_b, db_path=db_path)
    assert forbidden_df is None

    # User B attempts to delete User A's project -> Must fail
    del_success, del_msg = delete_project(project_id, user_b, db_path=db_path)
    assert del_success is False
    assert "access denied" in del_msg.lower() or "not found" in del_msg.lower()

    # Confirm project still exists for User A
    assert get_project(project_id, user_a, db_path=db_path) is not None


def test_reopen_and_load_project_dataframe(temp_workspace):
    """Legitimate owner can reload the exact saved DataFrame across sessions."""
    db_path, storage_path = temp_workspace
    user = "lead_analyst@firm.com"
    original_df = make_sample_dataframe()

    _, _, project_id = save_project(
        user_email=user,
        project_name="Session Snapshot",
        dataset_name="original.csv",
        dataframe=original_df,
        db_path=db_path,
        storage_root=storage_path,
    )

    reloaded_df = load_project_dataframe(project_id, user, db_path=db_path)
    assert reloaded_df is not None
    assert len(reloaded_df) == len(original_df)
    assert list(reloaded_df.columns) == list(original_df.columns)
    assert np.allclose(reloaded_df["sale_price_eth"], original_df["sale_price_eth"])


def test_delete_project_removes_record_and_file(temp_workspace):
    """Deleting a project cleanly purges database record and storage file."""
    db_path, storage_path = temp_workspace
    user = "researcher@firm.com"
    df = make_sample_dataframe()

    _, _, project_id = save_project(
        user_email=user,
        project_name="Temporary Investigation",
        dataset_name="temp.csv",
        dataframe=df,
        db_path=db_path,
        storage_root=storage_path,
    )

    proj = get_project(project_id, user, db_path=db_path)
    saved_file = Path(proj["storage_path"])
    assert saved_file.exists()

    del_success, del_msg = delete_project(project_id, user, db_path=db_path)
    assert del_success is True
    assert "deleted" in del_msg.lower()

    # Record gone
    assert get_project(project_id, user, db_path=db_path) is None
    # Storage file unlinked
    assert not saved_file.exists()


def test_save_empty_dataframe_rejected(temp_workspace):
    db_path, storage_path = temp_workspace
    empty_df = pd.DataFrame()
    success, msg, pid = save_project(
        user_email="user@test.com",
        project_name="Empty",
        dataset_name="empty.csv",
        dataframe=empty_df,
        db_path=db_path,
        storage_root=storage_path,
    )
    assert success is False
    assert pid is None
    assert "empty" in msg.lower()


def test_admin_system_metrics(temp_workspace):
    db_path, storage_path = temp_workspace
    df = make_sample_dataframe()

    save_project("user1@firm.com", "P1", "d1.csv", df, "TypeA", db_path=db_path, storage_root=storage_path)
    save_project("user2@firm.com", "P2", "d2.csv", df, "TypeB", db_path=db_path, storage_root=storage_path)
    save_project("user1@firm.com", "P3", "d3.csv", df, "TypeA", db_path=db_path, storage_root=storage_path)

    metrics = get_admin_system_metrics(db_path=db_path)
    assert metrics["total_saved_projects"] == 3
    assert metrics["unique_users_with_history"] == 2
    assert metrics["projects_by_type"]["TypeA"] == 2
    assert metrics["projects_by_type"]["TypeB"] == 1
