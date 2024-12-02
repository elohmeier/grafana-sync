import json
import tempfile
from pathlib import Path

import pytest
import requests
from requests.exceptions import ConnectionError

from grafana_sync.backup import GrafanaBackup
from grafana_sync.cli import create_grafana_client


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
    """Create a temporary directory for backup testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_backup_directories_creation(grafana, backup_dir):
    GrafanaBackup(grafana, backup_dir)

    assert (backup_dir / "folders").exists()
    assert (backup_dir / "folders").is_dir()
    assert (backup_dir / "dashboards").exists()
    assert (backup_dir / "dashboards").is_dir()


def test_backup_folder(grafana, backup_dir):
    backup = GrafanaBackup(grafana, backup_dir)

    # Create a test folder
    folder_uid = "test-folder"
    grafana.folder.create_folder(title="Test Folder", uid=folder_uid)

    try:
        # Backup the folder
        backup.backup_folder(folder_uid)

        # Check if backup file exists
        backup_file = backup_dir / "folders" / f"{folder_uid}.json"
        assert backup_file.exists()

        # Verify content
        with backup_file.open() as f:
            folder_data = json.load(f)
            assert folder_data["uid"] == folder_uid
            assert folder_data["title"] == "Test Folder"

    finally:
        grafana.folder.delete_folder(folder_uid)


def test_backup_recursive(grafana, backup_dir):
    backup = GrafanaBackup(grafana, backup_dir)

    # Create test folders
    grafana.folder.create_folder(title="L1", uid="l1")
    grafana.folder.create_folder(title="L2", uid="l2", parent_uid="l1")

    try:
        # Perform recursive backup
        backup.backup_recursive()

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
        grafana.folder.delete_folder("l1")


def test_backup_dashboard(grafana, backup_dir):
    backup = GrafanaBackup(grafana, backup_dir)

    # Create a test dashboard
    dashboard = {
        "dashboard": {
            "id": None,
            "uid": "test-dashboard",
            "title": "Test Dashboard",
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
        # Backup the dashboard
        backup.backup_dashboard("test-dashboard")

        # Check if backup file exists
        backup_file = backup_dir / "dashboards" / "test-dashboard.json"
        assert backup_file.exists()

        # Verify content
        with backup_file.open() as f:
            dashboard_data = json.load(f)
            assert dashboard_data["dashboard"]["uid"] == "test-dashboard"
            assert dashboard_data["dashboard"]["title"] == "Test Dashboard"

    finally:
        grafana.dashboard.delete_dashboard("test-dashboard")
