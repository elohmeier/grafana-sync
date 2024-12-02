import pytest
import requests
from grafana_client import GrafanaApi
from requests.exceptions import ConnectionError

from grafana_sync.api import walk
from grafana_sync.cli import create_grafana_client


def _remove_ids(items):
    """Remove id fields from folder items for comparison."""
    return [{k: v for k, v in item.items() if k != "id"} for item in items]


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

    # `port_for` takes a container port and returns the corresponding host port
    port = docker_services.port_for("grafana", 3000)
    url = f"http://{docker_ip}:{port}"
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_responsive(url)
    )
    return create_grafana_client(url, username="admin", password="admin")


def test_walk_single_folder(grafana: GrafanaApi):
    grafana.folder.create_folder(title="dummy", uid="dummy", parent_uid=None)

    try:
        lst = list(walk(grafana, "general", True, True))
        lst = [
            (folder_uid, _remove_ids(folders), dashboards)
            for folder_uid, folders, dashboards in lst
        ]
        assert lst == [
            ("general", [{"uid": "dummy", "title": "dummy"}], []),
            ("dummy", [], []),
        ]
    finally:
        grafana.folder.delete_folder("dummy")


def test_walk_recursive_folders(grafana):
    grafana.folder.create_folder(title="l1", uid="l1", parent_uid=None)
    grafana.folder.create_folder(title="l2", uid="l2", parent_uid="l1")

    try:
        lst = list(walk(grafana, "general", True, True))
        lst = [
            (folder_uid, _remove_ids(folders), dashboards)
            for folder_uid, folders, dashboards in lst
        ]
        assert lst == [
            ("general", [{"uid": "l1", "title": "l1"}], []),
            ("l1", [{"uid": "l2", "title": "l2", "parentUid": "l1"}], []),
            ("l2", [], []),
        ]
    finally:
        grafana.folder.delete_folder("l1")
