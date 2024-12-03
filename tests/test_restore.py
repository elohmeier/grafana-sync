import tempfile
from pathlib import Path

import pytest

from grafana_sync.api import DashboardData, GrafanaClient
from grafana_sync.backup import GrafanaBackup
from grafana_sync.restore import GrafanaRestore

from .utils import docker_grafana_client


@pytest.fixture(scope="session")
def grafana(docker_ip, docker_services):
    return docker_grafana_client(docker_ip, docker_services)


@pytest.fixture
def backup_dir():
    """Create a temporary directory for backup/restore testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_restore_folder(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create and backup a test folder
    folder_uid = "test-restore-folder"
    folder_title = "Test Restore Folder"
    grafana.create_folder(title=folder_title, uid=folder_uid)
    backup.backup_folder(folder_uid)

    # Delete the original folder
    grafana.delete_folder(folder_uid)

    try:
        # Restore the folder
        restore.restore_folder(folder_uid)

        # Verify restored folder
        folder = grafana.get_folder(folder_uid)
        assert folder.uid == folder_uid
        assert folder.title == folder_title

    finally:
        grafana.delete_folder(folder_uid)


def test_restore_dashboard(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create and backup a test dashboard
    dashboard = DashboardData(
        uid="test-restore-dashboard", title="Test Restore Dashboard"
    )

    grafana.update_dashboard(dashboard)
    backup.backup_dashboard("test-restore-dashboard")

    # Delete the original dashboard
    grafana.delete_dashboard("test-restore-dashboard")

    try:
        # Restore the dashboard
        restore.restore_dashboard("test-restore-dashboard")

        # Verify restored dashboard
        restored = grafana.get_dashboard("test-restore-dashboard")
        assert restored.dashboard.uid == "test-restore-dashboard"
        assert restored.dashboard.title == "Test Restore Dashboard"

    finally:
        try:
            grafana.delete_dashboard("test-restore-dashboard")
        except Exception:
            pass


def test_restore_recursive(grafana: GrafanaClient, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create test structure
    folder_uid = "test-restore-recursive"
    grafana.create_folder(title="Test Restore Recursive", uid=folder_uid)

    dashboard = DashboardData(
        uid="test-restore-dash-recursive", title="Test Restore Dashboard Recursive"
    )
    grafana.update_dashboard(dashboard, folder_uid=folder_uid)

    try:
        # Backup everything
        backup.backup_recursive()

        # Delete everything
        grafana.delete_dashboard("test-restore-dash-recursive")
        grafana.delete_folder(folder_uid)

        # Restore everything
        restore.restore_recursive()

        # Verify folder was restored
        folder = grafana.get_folder(folder_uid)
        assert folder.uid == folder_uid
        assert folder.title == "Test Restore Recursive"

        # Verify dashboard was restored
        dashboard = grafana.get_dashboard("test-restore-dash-recursive")
        assert dashboard.dashboard.uid == "test-restore-dash-recursive"
        assert dashboard.dashboard.title == "Test Restore Dashboard Recursive"

    finally:
        try:
            grafana.delete_dashboard("test-restore-dash-recursive")
        except Exception:
            pass
        grafana.delete_folder(folder_uid)
