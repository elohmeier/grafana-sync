import json
import tempfile
from pathlib import Path

import pytest

from grafana_sync.api.client import GrafanaClient
from grafana_sync.api.models import DashboardData
from grafana_sync.backup import GrafanaBackup

pytestmark = pytest.mark.docker


@pytest.fixture
def backup_dir():
    """Create a temporary directory for backup testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_backup_directories_creation(grafana: GrafanaClient, backup_dir: Path):
    GrafanaBackup(grafana, backup_dir)

    assert (backup_dir / "folders").exists()
    assert (backup_dir / "folders").is_dir()
    assert (backup_dir / "dashboards").exists()
    assert (backup_dir / "dashboards").is_dir()


async def test_backup_folder(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)

    # Create a test folder
    folder_uid = "test-folder"
    await grafana.create_folder(title="Test Folder", uid=folder_uid)

    try:
        # Backup the folder
        await backup.backup_folder(folder_uid)

        # Check if backup file exists
        backup_file = backup_dir / "folders" / f"{folder_uid}.json"
        assert backup_file.exists()

        # Verify content
        with backup_file.open() as f:
            folder_data = json.load(f)
            assert folder_data["uid"] == folder_uid
            assert folder_data["title"] == "Test Folder"

    finally:
        await grafana.delete_folder(folder_uid)


async def test_walk_backup(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)

    # Create test folders and dashboards
    await grafana.create_folder(title="L1", uid="l1")
    await grafana.create_folder(title="L2", uid="l2", parent_uid="l1")

    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")
    dashboard2 = DashboardData(uid="dash2", title="Dashboard 2")

    await grafana.update_dashboard(dashboard1, "l1")
    await grafana.update_dashboard(dashboard2, "l2")

    try:
        # Backup everything first
        await backup.backup_recursive()

        # Test walk_backup
        walk_result = list(backup.walk_backup())

        # Convert to comparable format
        simplified = [
            (
                uid,
                sorted([f.uid for f in folders]),
                sorted([d.dashboard.uid for d in dashboards]),
            )
            for uid, folders, dashboards in walk_result
        ]

        expected = [
            ("general", ["l1"], []),
            ("l1", ["l2"], ["dash1"]),
            ("l2", [], ["dash2"]),
        ]

        assert simplified == expected

    finally:
        await grafana.delete_dashboard("dash1")
        await grafana.delete_dashboard("dash2")
        await grafana.delete_folder("l1")


async def test_walk_backup_top_level(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)

    # Create test dashboards
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")

    await grafana.update_dashboard(dashboard1)

    try:
        # Backup everything first
        await backup.backup_recursive()

        # Test walk_backup
        walk_result = list(backup.walk_backup())

        # Convert to comparable format
        simplified = [
            (
                uid,
                sorted([f.uid for f in folders]),
                sorted([d.dashboard.uid for d in dashboards]),
            )
            for uid, folders, dashboards in walk_result
        ]

        expected = [
            ("general", [], ["dash1"]),
        ]

        assert simplified == expected

    finally:
        await grafana.delete_dashboard("dash1")


async def test_backup_recursive(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)

    # Create test folders
    await grafana.create_folder(title="L1", uid="l1")
    await grafana.create_folder(title="L2", uid="l2", parent_uid="l1")

    try:
        # Perform recursive backup
        await backup.backup_recursive()

        # Check if backup files exist
        assert (backup_dir / "folders" / "l1.json").exists()
        assert (backup_dir / "folders" / "l2.json").exists()

        # Verify folder content
        with (backup_dir / "folders" / "l1.json").open() as f:
            l1_data = json.load(f)
            assert l1_data["uid"] == "l1"
            assert l1_data["title"] == "L1"

        with (backup_dir / "folders" / "l2.json").open() as f:
            l2_data = json.load(f)
            assert l2_data["uid"] == "l2"
            assert l2_data["title"] == "L2"
            assert l2_data["parentUid"] == "l1"

    finally:
        await grafana.delete_folder("l1")


async def test_backup_dashboard(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)

    # Create a test dashboard
    dashboard = DashboardData(uid="test-dashboard", title="Test Dashboard")

    await grafana.update_dashboard(dashboard)

    try:
        # Backup the dashboard
        await backup.backup_dashboard("test-dashboard")

        # Check if backup file exists
        backup_file = backup_dir / "dashboards" / "test-dashboard.json"
        assert backup_file.exists()

        # Verify content
        with backup_file.open() as f:
            dashboard_data = json.load(f)
            assert dashboard_data["dashboard"]["uid"] == "test-dashboard"
            assert dashboard_data["dashboard"]["title"] == "Test Dashboard"

    finally:
        await grafana.delete_dashboard("test-dashboard")
