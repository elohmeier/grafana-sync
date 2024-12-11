import pytest

from grafana_sync.api.client import FOLDER_GENERAL, GrafanaClient
from grafana_sync.api.models import DashboardData
from grafana_sync.exceptions import DestinationParentNotFoundError
from grafana_sync.sync import sync

pytestmark = pytest.mark.docker


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


async def test_sync_dashboard_no_relocation(
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

    # Verify dashboard was moved in source
    src_db = await grafana.get_dashboard("dash1")
    assert src_db.meta.folder_uid == "folder2"

    # Sync with relocate_dashboards=False should not move the dashboard in destination
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        relocate_dashboards=False,
    )

    # Get version before sync
    dst_db_before = await grafana_dst.get_dashboard("dash1")
    version_before = dst_db_before.dashboard.version

    # Verify dashboard was NOT moved in destination and version didn't change
    dst_db_after = await grafana_dst.get_dashboard("dash1")
    assert dst_db_after.meta.folder_uid == "folder1"
    assert (
        dst_db_after.dashboard.version == version_before
    )  # Version should not increase


async def test_sync_to_destination_parent(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    # Create source structure
    await grafana.create_folder(title="Folder 1", uid="folder1")
    await grafana.create_folder(title="Folder 2", uid="folder2")
    await grafana.create_folder(title="Child", uid="child", parent_uid="folder1")

    # Create destination parent folder
    await grafana_dst.create_folder(title="Destination Parent", uid="dst_parent")

    # Create some dashboards
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")
    dashboard2 = DashboardData(uid="dash2", title="Dashboard 2")
    dashboard3 = DashboardData(uid="dash3", title="Dashboard 3")

    await grafana.update_dashboard(dashboard1, folder_uid="folder1")
    await grafana.update_dashboard(dashboard2, folder_uid="folder2")
    await grafana.update_dashboard(dashboard3, folder_uid="child")

    # Sync everything under the destination parent
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        dst_parent_uid="dst_parent",
    )

    # Verify folders were created under destination parent
    dst_folder1 = await grafana_dst.get_folder("folder1")
    assert dst_folder1.parent_uid == "dst_parent"

    dst_folder2 = await grafana_dst.get_folder("folder2")
    assert dst_folder2.parent_uid == "dst_parent"

    dst_child = await grafana_dst.get_folder("child")
    assert (
        dst_child.parent_uid == "folder1"
    )  # Should maintain hierarchy under new parent

    # Verify dashboards are in correct folders
    dash1 = await grafana_dst.get_dashboard("dash1")
    assert dash1.meta.folder_uid == "folder1"

    dash2 = await grafana_dst.get_dashboard("dash2")
    assert dash2.meta.folder_uid == "folder2"

    dash3 = await grafana_dst.get_dashboard("dash3")
    assert dash3.meta.folder_uid == "child"


async def test_sync_to_general_folder(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    # Create source structure with nested folders
    await grafana.create_folder(title="Parent", uid="parent")
    await grafana.create_folder(title="Child", uid="child", parent_uid="parent")

    # Create a dashboard in the child folder
    dashboard = DashboardData(uid="dash1", title="Dashboard 1")
    await grafana.update_dashboard(dashboard, folder_uid="child")

    # Sync with dst_parent_uid set to FOLDER_GENERAL
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        dst_parent_uid=FOLDER_GENERAL,
    )

    # Verify parent folder is at root level
    dst_parent = await grafana_dst.get_folder("parent")
    assert dst_parent.parent_uid is None

    # Verify child folder maintains its hierarchy
    dst_child = await grafana_dst.get_folder("child")
    assert dst_child.parent_uid == "parent"

    # Verify dashboard is in correct folder
    dash = await grafana_dst.get_dashboard("dash1")
    assert dash.meta.folder_uid == "child"


async def test_sync_to_nonexistent_parent(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    # Create source structure with nested folders
    await grafana.create_folder(title="Parent", uid="parent")
    await grafana.create_folder(title="Child", uid="child", parent_uid="parent")

    # Create a dashboard in the child folder
    dashboard = DashboardData(uid="dash1", title="Dashboard 1")
    await grafana.update_dashboard(dashboard, folder_uid="child")

    # Attempt sync with non-existent destination parent
    with pytest.raises(DestinationParentNotFoundError) as exc_info:
        await sync(
            src_grafana=grafana,
            dst_grafana=grafana_dst,
            dst_parent_uid="nonexistent",
        )

    assert exc_info.value.parent_uid == "nonexistent"
    assert (
        str(exc_info.value)
        == "Destination parent folder with UID 'nonexistent' does not exist"
    )

    # Verify nothing was synced
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
