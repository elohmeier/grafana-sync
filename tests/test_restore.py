import tempfile
from pathlib import Path

import pytest

from grafana_sync.api.client import GrafanaClient
from grafana_sync.api.models import DashboardData
from grafana_sync.backup import GrafanaBackup
from grafana_sync.restore import GrafanaRestore

pytestmark = pytest.mark.docker


@pytest.fixture
def backup_dir():
    """Create a temporary directory for backup/restore testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


async def test_restore_folder(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create and backup a test folder
    folder_uid = "test-restore-folder"
    folder_title = "Test Restore Folder"
    await grafana.create_folder(title=folder_title, uid=folder_uid)
    await backup.backup_folder(folder_uid)

    # Delete the original folder
    await grafana.delete_folder(folder_uid)

    try:
        # Restore the folder
        await restore.restore_folder(folder_uid)

        # Verify restored folder
        folder = await grafana.get_folder(folder_uid)
        assert folder.uid == folder_uid
        assert folder.title == folder_title

    finally:
        await grafana.delete_folder(folder_uid)


async def test_restore_dashboard(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create and backup a test dashboard
    dashboard = DashboardData(
        uid="test-restore-dashboard", title="Test Restore Dashboard"
    )

    await grafana.update_dashboard(dashboard)
    await backup.backup_dashboard("test-restore-dashboard")

    # Delete the original dashboard
    await grafana.delete_dashboard("test-restore-dashboard")

    try:
        # Restore the dashboard
        await restore.restore_dashboard("test-restore-dashboard")

        # Verify restored dashboard
        restored = await grafana.get_dashboard("test-restore-dashboard")
        assert restored.dashboard.uid == "test-restore-dashboard"
        assert restored.dashboard.title == "Test Restore Dashboard"

    finally:
        try:
            await grafana.delete_dashboard("test-restore-dashboard")
        except Exception:
            pass


async def test_restore_recursive(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create test structure
    folder_uid = "test-restore-recursive"
    await grafana.create_folder(title="Test Restore Recursive", uid=folder_uid)

    dashboard = DashboardData(
        uid="test-restore-dash-recursive", title="Test Restore Dashboard Recursive"
    )
    await grafana.update_dashboard(dashboard, folder_uid=folder_uid)

    try:
        # Backup everything
        await backup.backup_recursive()

        # Delete everything
        await grafana.delete_dashboard("test-restore-dash-recursive")
        await grafana.delete_folder(folder_uid)

        # Restore everything
        await restore.restore_recursive()

        # Verify folder was restored
        folder = await grafana.get_folder(folder_uid)
        assert folder.uid == folder_uid
        assert folder.title == "Test Restore Recursive"

        # Verify dashboard was restored
        dashboard = await grafana.get_dashboard("test-restore-dash-recursive")
        assert dashboard.dashboard.uid == "test-restore-dash-recursive"
        assert dashboard.dashboard.title == "Test Restore Dashboard Recursive"

    finally:
        try:
            await grafana.delete_dashboard("test-restore-dash-recursive")
        except Exception:
            pass
        await grafana.delete_folder(folder_uid)


async def test_restore_recursive_top_level_dashboard(
    grafana: GrafanaClient, backup_dir: Path
):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create test structure
    dashboard = DashboardData(
        uid="test-restore-dash-recursive", title="Test Restore Dashboard Recursive"
    )
    await grafana.update_dashboard(dashboard)

    try:
        # Backup everything
        await backup.backup_recursive()

        # Delete everything
        await grafana.delete_dashboard("test-restore-dash-recursive")

        # Restore everything
        await restore.restore_recursive()

        # Verify dashboard was restored
        dashboard = await grafana.get_dashboard("test-restore-dash-recursive")
        assert dashboard.dashboard.uid == "test-restore-dash-recursive"
        assert dashboard.dashboard.title == "Test Restore Dashboard Recursive"

    finally:
        try:
            await grafana.delete_dashboard("test-restore-dash-recursive")
        except Exception:
            pass
