import httpx
from pytest_docker.plugin import Services

from grafana_sync.api import GrafanaClient


class GrafanaNotPristineError(Exception):
    """Base exception for when Grafana instance is not in a pristine state."""


class ExistingFoldersError(GrafanaNotPristineError):
    """Raised when Grafana instance has existing folders."""

    def __init__(self, folder_count: int):
        self.folder_count = folder_count
        message = f"Grafana instance has {folder_count} existing folder(s)"
        super().__init__(message)


class ExistingDashboardsError(GrafanaNotPristineError):
    """Raised when Grafana instance has existing dashboards."""

    def __init__(self, dashboard_count: int):
        self.dashboard_count = dashboard_count
        message = f"Grafana instance has {dashboard_count} existing dashboard(s)"
        super().__init__(message)


def docker_grafana_client(docker_ip: str, docker_services: Services) -> GrafanaClient:
    """Ensure that HTTP service is up and responsive."""
    port = docker_services.port_for("grafana", 3000)
    url = f"http://{docker_ip}:{port}"

    with httpx.Client() as httpx_client:

        def is_responsive() -> bool:
            try:
                response = httpx_client.get(f"{url}/login")
                response.raise_for_status()
                return True
            except httpx.ReadError:
                return False

        docker_services.wait_until_responsive(
            timeout=30.0, pause=0.1, check=is_responsive
        )

    gf_client = GrafanaClient(url, username="admin", password="admin")

    folders = gf_client.get_folders().root
    if len(folders) > 0:
        raise ExistingFoldersError(len(folders))

    # Check for dashboards in the general folder
    dashboards = gf_client.search_dashboards().root
    if len(dashboards) > 0:
        raise ExistingDashboardsError(len(dashboards))

    return gf_client
