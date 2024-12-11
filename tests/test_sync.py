from grafana_sync.api.client import GrafanaClient
from grafana_sync.api.models import DashboardData
from grafana_sync.sync import sync


async def test_sync_dashboard(grafana: GrafanaClient, grafana_dst: GrafanaClient):
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


async def test_sync_folder(grafana: GrafanaClient, grafana_dst: GrafanaClient):
    await grafana.create_folder(title="Folder 1", uid="folder1")
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")

    await grafana.update_dashboard(dashboard1, folder_uid="folder1")

    try:
        await sync(
            src_grafana=grafana,
            dst_grafana=grafana_dst,
        )
    finally:
        await grafana.delete_dashboard("dash1")
        await grafana.delete_folder("folder1")

    dst_db = await grafana_dst.get_dashboard("dash1")
    assert dst_db.dashboard.title == "Dashboard 1"
    assert dst_db.meta.folder_uid == "folder1"

    dst_folder = await grafana_dst.get_folder("folder1")
    assert dst_folder.parent_uid is None
    assert dst_folder.title == "Folder 1"

    await grafana_dst.delete_dashboard("dash1")
    await grafana_dst.delete_folder("folder1")


async def test_sync_selected_folder(grafana: GrafanaClient, grafana_dst: GrafanaClient):
    await grafana.create_folder(title="Folder 1", uid="folder1")
    await grafana.create_folder(title="Folder 2", uid="folder2")
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")
    dashboard2 = DashboardData(uid="dash2", title="Dashboard 2")
    dashboard3 = DashboardData(uid="dash3", title="Dashboard 3")

    await grafana.update_dashboard(dashboard1, folder_uid="folder1")
    await grafana.update_dashboard(dashboard2, folder_uid="folder2")
    await grafana.update_dashboard(dashboard3)  # general

    try:
        await sync(
            src_grafana=grafana,
            dst_grafana=grafana_dst,
            folder_uid="folder1",
        )
    finally:
        await grafana.delete_dashboard("dash1")
        await grafana.delete_dashboard("dash2")
        await grafana.delete_dashboard("dash3")
        await grafana.delete_folder("folder1")
        await grafana.delete_folder("folder2")

    dst_db = await grafana_dst.get_dashboard("dash1")
    assert dst_db.dashboard.title == "Dashboard 1"
    assert dst_db.meta.folder_uid == "folder1"

    await grafana_dst.delete_dashboard("dash1")
    await grafana_dst.delete_folder("folder1")

    # ensure nothing else was synced
    await grafana_dst.check_pristine()
