import httpx
import pytest_asyncio

from grafana_sync.api.client import GrafanaClient


@pytest_asyncio.fixture(scope="function")
def grafana(docker_ip, docker_services):
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

    return gf_client
