from grafana_sync.api.client import GrafanaClient
from grafana_sync.api.models import DashboardData
from grafana_sync.sync import sync


async def test_sync_single_dashboard(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")

    await grafana.update_dashboard(dashboard1)

    try:
        await sync(
            src_grafana=grafana,
            dst_grafana=grafana_dst,
        )
    finally:
        await grafana.delete_dashboard("dash1")

    dst_db = await grafana_dst.get_dashboard("dash1")
    assert dst_db.dashboard.title == "Dashboard 1"

    await grafana_dst.delete_dashboard("dash1")
