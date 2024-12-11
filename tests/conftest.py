import httpx
import pytest_asyncio

from grafana_sync.api.client import GrafanaClient


@pytest_asyncio.fixture(scope="function")
async def grafana(docker_ip, docker_services):
    """Ensure that HTTP service is up and responsive."""
    port = docker_services.port_for("grafana", 3000)
    url = f"http://{docker_ip}:{port}"

    with httpx.Client() as httpx_client:

        def is_responsive() -> bool:
            try:
                response = httpx_client.get(f"{url}/login")
                response.raise_for_status()
            except httpx.ReadError:
                return False
            else:
                return True

        docker_services.wait_until_responsive(
            timeout=30.0, pause=0.1, check=is_responsive
        )

    async with GrafanaClient(url, username="admin", password="admin") as client:
        await client.check_pristine()  # abort if there is any data in the instance

        try:
            yield client
        finally:
            await client.delete_all_folders_and_dashboards()  # cleanup after test
            await client.check_pristine()  # check if deletion succeeded


@pytest_asyncio.fixture(scope="function")
async def grafana_dst(docker_ip, docker_services):
    """Ensure that HTTP service is up and responsive."""
    port = docker_services.port_for("grafana_dst", 3000)
    url = f"http://{docker_ip}:{port}"

    with httpx.Client() as httpx_client:

        def is_responsive() -> bool:
            try:
                response = httpx_client.get(f"{url}/login")
                response.raise_for_status()
            except httpx.ReadError:
                return False
            else:
                return True

        docker_services.wait_until_responsive(
            timeout=30.0, pause=0.1, check=is_responsive
        )

    async with GrafanaClient(url, username="admin", password="admin") as client:
        await client.check_pristine()  # abort if there is any data in the instance

        try:
            yield client
        finally:
            await client.delete_all_folders_and_dashboards()  # cleanup after test
            await client.check_pristine()  # check if deletion succeeded
