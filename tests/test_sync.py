import importlib.resources

import pytest

from grafana_sync.api.client import FOLDER_GENERAL, GrafanaClient
from grafana_sync.api.models import (
    DashboardData,
    DatasourceDefinition,
    GetDashboardResponse,
)
from grafana_sync.dashboards.models import DataSource
from grafana_sync.exceptions import DestinationParentNotFoundError, GrafanaApiError
from grafana_sync.sync import sync

from . import dashboards, responses

pytestmark = pytest.mark.docker


def read_db(filename: str) -> DashboardData:
    ref = importlib.resources.files(dashboards) / filename
    with importlib.resources.as_file(ref) as path, open(path, "rb") as f:
        return DashboardData.model_validate_json(f.read())


def read_response(filename: str) -> GetDashboardResponse:
    ref = importlib.resources.files(responses) / filename
    with importlib.resources.as_file(ref) as path, open(path, "rb") as f:
        return GetDashboardResponse.model_validate_json(f.read())


async def test_sync_dashboard(grafana: GrafanaClient, grafana_dst: GrafanaClient):
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")

    await grafana.update_dashboard(dashboard1)

    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
    )

    dst_db = await grafana_dst.get_dashboard("dash1")
    assert dst_db.dashboard.title == "Dashboard 1"


async def test_sync_dashboard_with_ds_migration(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    dashboard1 = read_db("simple-ds-var.json")

    await grafana.update_dashboard(dashboard1)

    await grafana.create_datasource(
        DatasourceDefinition(
            name="prometheus",
            uid="P1809F7CD0C75ACF3",
            type="prometheus",
            access="proxy",
        )
    )

    await grafana_dst.create_datasource(
        DatasourceDefinition(
            name="prometheus-dst",
            uid="my-new-uid",
            type="prometheus",
            access="proxy",
        )
    )

    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        migrate_datasources=True,
    )

    dst_db = await grafana_dst.get_dashboard("simple-ds-var")
    assert dst_db.dashboard.title == "simple-ds-var"

    assert dst_db.dashboard.templating is not None
    assert dst_db.dashboard.templating.list_ is not None
    assert dst_db.dashboard.templating.list_[0].current is not None

    assert dst_db.dashboard.templating.list_[0].current.text == "prometheus-dst"
    assert dst_db.dashboard.templating.list_[0].current.value == "my-new-uid"


async def test_sync_dashboard_with_classic_ds_migration(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    dashboard1 = read_response(
        "get-dashboard-response-classic-datasource.json"
    ).dashboard

    await grafana.update_dashboard(dashboard1)

    await grafana.create_datasource(
        DatasourceDefinition(
            name="InfluxDB Produktion Telegraf",
            uid="P1809F7CD0C75ACF3",
            type="influxdb",
            access="proxy",
        )
    )

    await grafana_dst.create_datasource(
        DatasourceDefinition(
            name="influxdb-dst",
            uid="my-new-uid",
            type="influxdb",
            access="proxy",
        )
    )

    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        migrate_datasources=True,
    )

    dst_db = await grafana_dst.get_dashboard("HA3OWKPWz")
    assert dst_db.dashboard.title == "Total Host Overview"

    assert dst_db.dashboard.panels is not None
    assert dst_db.dashboard.panels[0].datasource is not None
    assert isinstance(dst_db.dashboard.panels[0].datasource, DataSource)
    assert dst_db.dashboard.panels[0].datasource.type_ == "influxdb"
    assert dst_db.dashboard.panels[0].datasource.uid == "my-new-uid"


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


async def test_sync_root_dashboard_to_destination_parent(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    """Test that a dashboard at root level is moved to dst_parent_uid folder when specified."""
    # Create a dashboard at root level in source
    dashboard = DashboardData(uid="dash1", title="Root Dashboard")
    await grafana.update_dashboard(dashboard)  # No folder_uid = root level

    # Create destination parent folder
    await grafana_dst.create_folder(title="Destination Parent", uid="dst_parent")

    # Sync with dst_parent_uid
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        dst_parent_uid="dst_parent",
    )

    # Verify dashboard was moved to destination parent folder
    dst_dash = await grafana_dst.get_dashboard("dash1")
    assert dst_dash.meta.folder_uid == "dst_parent"
    assert dst_dash.dashboard.title == "Root Dashboard"


async def test_sync_with_pruning_and_destination_parent(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    """Test that pruning works correctly when a destination parent is specified."""
    # Create source structure
    await grafana.create_folder(title="Source Folder", uid="src_folder")
    dashboard1 = DashboardData(uid="dash1", title="Dashboard 1")
    dashboard2 = DashboardData(uid="dash2", title="Dashboard 2")
    await grafana.update_dashboard(dashboard1, folder_uid="src_folder")
    await grafana.update_dashboard(dashboard2, folder_uid="src_folder")

    # Create destination parent and structure
    await grafana_dst.create_folder(title="Destination Parent", uid="dst_parent")
    await grafana_dst.create_folder(
        title="Source Folder", uid="src_folder", parent_uid="dst_parent"
    )

    # Create extra dashboard in destination that should be pruned
    dashboard3 = DashboardData(uid="dash3", title="Dashboard 3")
    await grafana_dst.update_dashboard(dashboard3, folder_uid="src_folder")

    # Sync with pruning enabled and destination parent specified
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        folder_uid="src_folder",
        prune=True,
        dst_parent_uid="dst_parent",
    )

    # Verify dashboards 1 and 2 exist in destination under the correct folder
    dst_db1 = await grafana_dst.get_dashboard("dash1")
    assert dst_db1.dashboard.title == "Dashboard 1"
    assert dst_db1.meta.folder_uid == "src_folder"

    dst_db2 = await grafana_dst.get_dashboard("dash2")
    assert dst_db2.dashboard.title == "Dashboard 2"
    assert dst_db2.meta.folder_uid == "src_folder"

    # Verify dashboard 3 was pruned
    with pytest.raises(GrafanaApiError):
        await grafana_dst.get_dashboard("dash3")

    # Verify folder structure
    dst_folder = await grafana_dst.get_folder("src_folder")
    assert dst_folder.parent_uid == "dst_parent"


async def test_move_folders_with_destination_parent(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    """Test that folders are correctly moved when a destination parent is specified."""
    # Create source structure with nested folders
    await grafana.create_folder(title="Parent", uid="parent")
    await grafana.create_folder(title="Child 1", uid="child1", parent_uid="parent")
    await grafana.create_folder(title="Child 2", uid="child2")  # At root level
    await grafana.create_folder(
        title="Grandchild", uid="grandchild", parent_uid="child1"
    )

    # Create destination parent and initial structure (with different hierarchy)
    await grafana_dst.create_folder(title="Destination Parent", uid="dst_parent")
    await grafana_dst.create_folder(
        title="Parent", uid="parent", parent_uid="dst_parent"
    )
    await grafana_dst.create_folder(title="Child 1", uid="child1")  # At root initially
    await grafana_dst.create_folder(title="Child 2", uid="child2")  # At root
    await grafana_dst.create_folder(
        title="Grandchild", uid="grandchild", parent_uid="child2"
    )  # Wrong parent

    # Sync with destination parent
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        dst_parent_uid="dst_parent",
    )

    # Verify final folder structure
    dst_parent = await grafana_dst.get_folder("parent")
    assert dst_parent.parent_uid == "dst_parent"

    dst_child1 = await grafana_dst.get_folder("child1")
    assert dst_child1.parent_uid == "parent"

    dst_child2 = await grafana_dst.get_folder("child2")
    assert dst_child2.parent_uid == "dst_parent"  # Should be under dst_parent

    dst_grandchild = await grafana_dst.get_folder("grandchild")
    assert dst_grandchild.parent_uid == "child1"  # Should match source hierarchy


async def test_sync_existing_general_dashboard_to_destination_parent(
    grafana: GrafanaClient, grafana_dst: GrafanaClient
):
    """Test that an existing dashboard in general folder is moved when dst_parent_uid is set."""
    # Create a dashboard at root level in both source and destination
    dashboard = DashboardData(uid="dash1", title="Root Dashboard")
    await grafana.update_dashboard(dashboard)  # No folder_uid = root level
    await grafana_dst.update_dashboard(dashboard)  # Also at root level

    # Verify initial state - dashboard exists at root in both instances
    src_dash = await grafana.get_dashboard("dash1")
    assert src_dash.meta.folder_uid == ""
    dst_dash = await grafana_dst.get_dashboard("dash1")
    assert dst_dash.meta.folder_uid == ""

    # Create destination parent folder
    await grafana_dst.create_folder(title="Destination Parent", uid="dst_parent")

    # Sync with dst_parent_uid
    await sync(
        src_grafana=grafana,
        dst_grafana=grafana_dst,
        dst_parent_uid="dst_parent",
    )

    # Verify dashboard was moved to destination parent folder
    dst_dash_after = await grafana_dst.get_dashboard("dash1")
    assert dst_dash_after.meta.folder_uid == "dst_parent"
    assert dst_dash_after.dashboard.title == "Root Dashboard"

    # Verify source dashboard remains at root
    src_dash_after = await grafana.get_dashboard("dash1")
    assert src_dash_after.meta.folder_uid == ""


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
