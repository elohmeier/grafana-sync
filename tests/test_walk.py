from typing import TYPE_CHECKING

import pytest

from grafana_sync.api import GetFoldersResponse, SearchDashboardsResponse

from .utils import docker_grafana_client

if TYPE_CHECKING:
    from grafana_sync.api import GrafanaClient

pytestmark = pytest.mark.docker


@pytest.fixture(scope="session")
def grafana(docker_ip, docker_services):
    return docker_grafana_client(docker_ip, docker_services)


def _to_dicts(items: GetFoldersResponse | SearchDashboardsResponse):
    """Remove id fields from folder items and convert to dict for comparison."""
    return [item.model_dump(exclude={"id"}, exclude_none=True) for item in items.root]


def test_walk_single_folder(grafana: "GrafanaClient"):
    grafana.create_folder(title="dummy", uid="dummy", parent_uid=None)

    try:
        lst = list(grafana.walk("general", True, True))
        lst = [
            (folder_uid, _to_dicts(folders), _to_dicts(dashboards))
            for folder_uid, folders, dashboards in lst
        ]
        assert lst == [
            ("general", [{"uid": "dummy", "title": "dummy"}], []),
            ("dummy", [], []),
        ]
    finally:
        grafana.delete_folder("dummy")


def test_walk_recursive_folders(grafana: "GrafanaClient"):
    grafana.create_folder(title="l1", uid="l1", parent_uid=None)
    grafana.create_folder(title="l2", uid="l2", parent_uid="l1")

    try:
        lst = list(grafana.walk("general", True, True))
        lst = [
            (folder_uid, _to_dicts(folders), _to_dicts(dashboards))
            for folder_uid, folders, dashboards in lst
        ]
        assert lst == [
            ("general", [{"uid": "l1", "title": "l1"}], []),
            ("l1", [{"uid": "l2", "title": "l2", "parentUid": "l1"}], []),
            ("l2", [], []),
        ]
    finally:
        grafana.delete_folder("l1")
