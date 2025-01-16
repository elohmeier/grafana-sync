import pytest

from grafana_sync.api.client import GrafanaClient
from grafana_sync.exceptions import GrafanaApiError

pytestmark = pytest.mark.docker


async def test_logout_all_fails_without_skip(grafana: GrafanaClient):
    with pytest.raises(GrafanaApiError, match="You cannot logout yourself"):
        await grafana.logout_all_users()


async def test_logout_all_succeeds_with_skip(grafana: GrafanaClient):
    await grafana.logout_all_users(skip_username="admin")
