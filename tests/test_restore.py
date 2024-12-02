import tempfile
from pathlib import Path

import pytest
import requests
from grafana_client import GrafanaApi
from requests.exceptions import ConnectionError

from grafana_sync.backup import GrafanaBackup
from grafana_sync.cli import create_grafana_client
from grafana_sync.restore import GrafanaRestore


def is_responsive(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True
    except ConnectionError:
        return False


@pytest.fixture(scope="session")
def grafana(docker_ip, docker_services):
    """Ensure that HTTP service is up and responsive."""
    port = docker_services.port_for("grafana", 3000)
    url = f"http://{docker_ip}:{port}"
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_responsive(url)
    )
    return create_grafana_client(url, username="admin", password="admin")


@pytest.fixture
def backup_dir():
    """Create a temporary directory for backup/restore testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_restore_folder(grafana, backup_dir):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create and backup a test folder
    folder_uid = "test-restore-folder"
    folder_title = "Test Restore Folder"
    grafana.folder.create_folder(title=folder_title, uid=folder_uid)
    backup.backup_folder(folder_uid)

    # Delete the original folder
    grafana.folder.delete_folder(folder_uid)

    try:
        # Restore the folder
        restore.restore_folder(folder_uid)

        # Verify restored folder
        folder = grafana.folder.get_folder(folder_uid)
        assert folder["uid"] == folder_uid
        assert folder["title"] == folder_title

    finally:
        grafana.folder.delete_folder(folder_uid)


def test_restore_dashboard(grafana: GrafanaApi, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create and backup a test dashboard
    dashboard = {
        "dashboard": {
            "id": None,
            "uid": "test-restore-dashboard",
            "title": "Test Restore Dashboard",
            "tags": ["test"],
            "timezone": "browser",
            "schemaVersion": 16,
            "version": 0,
        },
        "folderId": 0,
        "overwrite": True,
    }

    grafana.dashboard.update_dashboard(dashboard)
    backup.backup_dashboard("test-restore-dashboard")

    # Delete the original dashboard
    grafana.dashboard.delete_dashboard("test-restore-dashboard")

    try:
        # Restore the dashboard
        restore.restore_dashboard("test-restore-dashboard")

        # Verify restored dashboard
        restored = grafana.dashboard.get_dashboard("test-restore-dashboard")
        assert restored["dashboard"]["uid"] == "test-restore-dashboard"
        assert restored["dashboard"]["title"] == "Test Restore Dashboard"

    finally:
        try:
            grafana.dashboard.delete_dashboard("test-restore-dashboard")
        except Exception:
            pass


def test_restore_recursive(grafana: GrafanaApi, backup_dir: Path):
    backup = GrafanaBackup(grafana, backup_dir)
    restore = GrafanaRestore(grafana, backup_dir)

    # Create test structure
    folder_uid = "test-restore-recursive"
    grafana.folder.create_folder(title="Test Restore Recursive", uid=folder_uid)

    dashboard = {
        "dashboard": {
            "id": None,
            "uid": "test-restore-dash-recursive",
            "title": "Test Restore Dashboard Recursive",
            "tags": ["test"],
            "timezone": "browser",
            "schemaVersion": 16,
            "version": 0,
        },
        "folderId": 0,
        "overwrite": True,
    }
    grafana.dashboard.update_dashboard(dashboard)

    try:
        # Backup everything
        backup.backup_recursive()

        # Delete everything
        grafana.dashboard.delete_dashboard("test-restore-dash-recursive")
        grafana.folder.delete_folder(folder_uid)

        # Restore everything
        restore.restore_recursive()

        # Verify folder was restored
        folder = grafana.folder.get_folder(folder_uid)
        assert folder["uid"] == folder_uid
        assert folder["title"] == "Test Restore Recursive"

        # Verify dashboard was restored
        dashboard = grafana.dashboard.get_dashboard("test-restore-dash-recursive")
        assert dashboard["dashboard"]["uid"] == "test-restore-dash-recursive"
        assert dashboard["dashboard"]["title"] == "Test Restore Dashboard Recursive"

    finally:
        grafana.dashboard.delete_dashboard("test-restore-dash-recursive")
        grafana.folder.delete_folder(folder_uid)
