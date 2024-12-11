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

    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
    )

    dst_db = await grafana_dst.get_dashboard("dash1")
    assert dst_db.dashboard.title == "Dashboard 1"
    assert dst_db.meta.folder_uid == "folder1"

    dst_folder = await grafana_dst.get_folder("folder1")
    assert dst_folder.parent_uid is None
    assert dst_folder.title == "Folder 1"


async def test_sync_folder_relocation(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    # Create parent folders
    await grafana.create_folder(title="Parent 1", uid="parent1")
    await grafana.create_folder(title="Parent 2", uid="parent2")

    # Create child folder in Parent 1
    await grafana.create_folder(title="Child", uid="child", parent_uid="parent1")

    # Create same structure in destination, but with Child under Parent 1
    await grafana_dst.create_folder(title="Parent 1", uid="parent1")
    await grafana_dst.create_folder(title="Parent 2", uid="parent2")
    await grafana_dst.create_folder(title="Child", uid="child", parent_uid="parent1")

    # Move child folder to Parent 2 in source
    await grafana.move_folder("child", "parent2")

    # Verify folder was moved
    src_child = await grafana.get_folder("child")
    assert src_child.parent_uid == "parent2"

    # Sync should move the folder in destination
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        recursive=True,
    )

    # Verify folder was moved
    dst_child = await grafana_dst.get_folder("child")
    assert dst_child.parent_uid == "parent2"


async def test_sync_folder_no_relocation(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    # Create parent folders
    await grafana.create_folder(title="Parent 1", uid="parent1")
    await grafana.create_folder(title="Parent 2", uid="parent2")

    # Create child folder in Parent 1
    await grafana.create_folder(title="Child", uid="child", parent_uid="parent1")

    # Create same structure in destination, but with Child under Parent 1
    await grafana_dst.create_folder(title="Parent 1", uid="parent1")
    await grafana_dst.create_folder(title="Parent 2", uid="parent2")
    await grafana_dst.create_folder(title="Child", uid="child", parent_uid="parent1")

    # Move child folder to Parent 2 in source
    await grafana.move_folder("child", "parent2")

    # Verify folder was moved in source
    src_child = await grafana.get_folder("child")
    assert src_child.parent_uid == "parent2"

    # Sync with relocate_folders=False should not move the folder in destination
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        recursive=True,
        relocate_folders=False,
    )

    # Verify folder was NOT moved in destination
    dst_child = await grafana_dst.get_folder("child")
    assert dst_child.parent_uid == "parent1"


async def test_sync_dashboard_relocation(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    # Create folders in source and destination
    await grafana.create_folder(title="Folder 1", uid="folder1")
    await grafana.create_folder(title="Folder 2", uid="folder2")
    await grafana_dst.create_folder(title="Folder 1", uid="folder1")
    await grafana_dst.create_folder(title="Folder 2", uid="folder2")

    # Create dashboard in Folder 1
    dashboard = DashboardData(uid="dash1", title="Dashboard 1")
    await grafana.update_dashboard(dashboard, folder_uid="folder1")
    await grafana_dst.update_dashboard(dashboard, folder_uid="folder1")

    # Move dashboard to Folder 2 in source
    dashboard = DashboardData(uid="dash1", title="Dashboard 1")
    await grafana.update_dashboard(dashboard, folder_uid="folder2")

    # Verify dashboard was moved
    src_db = await grafana.get_dashboard("dash1")
    assert src_db.meta.folder_uid == "folder2"

    # Sync should move the dashboard in destination
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
    )

    # Verify dashboard was moved
    dst_db = await grafana_dst.get_dashboard("dash1")
    assert dst_db.meta.folder_uid == "folder2"


async def test_sync_selected_folder(grafana: GrafanaClient, grafana_dst: GrafanaClient):
    await grafana.create_folder(title="Folder 1", uid="folder1")
    await grafana.create_folder(title="Folder 2", uid="folder2")
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")
    dashboard2 = DashboardData(uid="dash2", title="Dashboard 2")
    dashboard3 = DashboardData(uid="dash3", title="Dashboard 3")

    await grafana.update_dashboard(dashboard1, folder_uid="folder1")
    await grafana.update_dashboard(dashboard2, folder_uid="folder2")
    await grafana.update_dashboard(dashboard3)  # general

    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        folder_uid="folder1",
    )

    dst_db = await grafana_dst.get_dashboard("dash1")
    assert dst_db.dashboard.title == "Dashboard 1"
    assert dst_db.meta.folder_uid == "folder1"

    # ensure nothing else was synced
    await grafana_dst.delete_folder("folder1")
    await grafana_dst.check_pristine()


async def test_sync_with_pruning(grafana: GrafanaClient, grafana_dst: GrafanaClient):
    # Create folders in source and destination
    await grafana.create_folder(title="Folder 1", uid="folder1")
    await grafana_dst.create_folder(title="Folder 1", uid="folder1")

    # Create dashboards in source
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")
    dashboard2 = DashboardData(uid="dash2", title="Dashboard 2")
    await grafana.update_dashboard(dashboard1, folder_uid="folder1")
    await grafana.update_dashboard(dashboard2, folder_uid="folder1")

    # Create extra dashboard in destination that should be pruned
    dashboard3 = DashboardData(uid="dash3", title="Dashboard 3")
    await grafana_dst.update_dashboard(dashboard3, folder_uid="folder1")

    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        folder_uid="folder1",
        prune=True,
    )

    # Verify dashboards 1 and 2 exist in destination
    dst_db1 = await grafana_dst.get_dashboard("dash1")
    assert dst_db1.dashboard.title == "Dashboard 1"
    dst_db2 = await grafana_dst.get_dashboard("dash2")
    assert dst_db2.dashboard.title == "Dashboard 2"

    # Verify dashboard 3 was pruned
    try:
        await grafana_dst.get_dashboard("dash3")
        raise AssertionError("Dashboard 3 should have been pruned")
    except Exception:
        pass
