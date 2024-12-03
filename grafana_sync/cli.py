import logging
from typing import TYPE_CHECKING, Mapping

import asyncclick as click
from rich import print as rprint
from rich import print_json
from rich.tree import Tree

from grafana_sync.api.client import FOLDER_GENERAL, GrafanaClient
from grafana_sync.backup import GrafanaBackup
from grafana_sync.restore import GrafanaRestore
from grafana_sync.sync import GrafanaSync

if TYPE_CHECKING:
    from grafana_sync.api.models import (
        GetFolderResponse,
        GetFoldersResponseItem,
        SearchDashboardsResponseItem,
    )

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
@click.option(
    "--url",
    envvar="GRAFANA_URL",
    required=True,
    help="Grafana URL",
)
@click.option(
    "--log-level",
    envvar="LOG_LEVEL",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
    help="Set logging level",
)
@click.option(
    "--api-key",
    envvar="GRAFANA_API_KEY",
    help="Grafana API key for token authentication",
)
@click.option(
    "--username",
    envvar="GRAFANA_USERNAME",
    help="Grafana username for basic authentication",
)
@click.option(
    "--password",
    envvar="GRAFANA_PASSWORD",
    help="Grafana password for basic authentication",
)
@click.pass_context
async def cli(
    ctx: click.Context,
    url: str,
    api_key: str | None,
    username: str | None,
    password: str | None,
    log_level: str,
):
    """Sync Grafana dashboards and folders."""
    logging.basicConfig(level=getattr(logging, log_level.upper()))
    try:
        ctx.obj = await ctx.with_async_resource(
            GrafanaClient(url, api_key, username, password)
        )
    except ValueError as ex:
        raise click.UsageError(ex.args[0]) from ex


@cli.command(name="list")
@click.option(
    "-f",
    "--folder-uid",
    default=FOLDER_GENERAL,
    help="Optional folder UID to list only subfolders of this folder",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="List folders recursively",
)
@click.option(
    "-d",
    "--include-dashboards",
    is_flag=True,
    help="Include dashboards in the output",
)
@click.option(
    "-j",
    "--output-json",
    is_flag=True,
    help="Display output in JSON format",
)
@click.pass_context
async def list_folders(
    ctx: click.Context,
    folder_uid: str,
    recursive: bool,
    include_dashboards: bool,
    output_json: bool,
) -> None:
    """List folders in a Grafana instance."""
    grafana = ctx.ensure_object(GrafanaClient)

    class TreeDashboardItem:
        """Represents a dashboard item in the folder tree structure."""

        def __init__(self, data: "SearchDashboardsResponseItem") -> None:
            """Initialize dashboard item with API response data."""
            self.data = data

        @property
        def label(self) -> str:
            """Get the display label for the dashboard."""
            return f"📊 {self.data.title} ({self.data.uid})"

        def to_tree(self, parent: Tree) -> None:
            """Add this dashboard as a node to the parent tree."""
            parent.add(self.label)

        def to_obj(self):
            """Convert dashboard item to JSON-compatible representation."""
            return self.data

    class TreeFolderItem:
        """Represents a folder item in the folder tree structure."""

        children: list["TreeFolderItem | TreeDashboardItem"]

        def __init__(self, data: "GetFolderResponse | GetFoldersResponseItem") -> None:
            """Initialize folder item with API response data."""
            self.children = []
            self.data = data

        def __repr__(self) -> str:
            return f"TreeFolderItem({self.data.title})"

        @property
        def label(self) -> str:
            """Get the display label for the folder."""
            return f"📁 {self.data.title} ({self.data.uid})"

        def to_tree(self, parent: Tree | None = None) -> Tree:
            """Convert folder and its children to a rich Tree structure.

            Args:
                parent: Optional parent tree node to add this folder to

            Returns:
                The created tree node for this folder
            """
            if parent is None:
                r_tree = Tree(self.label)
            else:
                r_tree = parent.add(self.label)

            for c in self.children:
                c.to_tree(r_tree)

            return r_tree

        def to_obj(self):
            """Convert folder and its children to JSON-compatible representation."""
            children_data = [c.to_obj() for c in self.children]
            if self.data:
                return {
                    "type": "dash-folder",
                    "children": children_data,
                } | self.data.model_dump()
            else:
                return children_data

    folder_nodes: Mapping[str | None, TreeFolderItem] = {}

    async for root_uid, folders, dashboards in grafana.walk(
        folder_uid, recursive, include_dashboards
    ):
        if root_uid in folder_nodes:
            root_node = folder_nodes[root_uid]
        else:
            root_folder_data = await grafana.get_folder(root_uid)
            root_node = TreeFolderItem(root_folder_data)
            folder_nodes[root_uid] = root_node

        for folder in folders.root:
            if folder.uid not in folder_nodes:
                itm = TreeFolderItem(folder)
                folder_nodes[folder.uid] = itm
                root_node.children.append(itm)

        for dashboard in dashboards.root:
            itm = TreeDashboardItem(dashboard)
            root_node.children.append(itm)

    main_node = folder_nodes[folder_uid]
    if output_json:
        print_json(data=main_node.to_obj())
    else:
        rprint(main_node.to_tree())


@cli.command(name="sync")
@click.option(
    "--dst-url",
    envvar="GRAFANA_DST_URL",
    required=True,
    help="Destination Grafana URL",
)
@click.option(
    "--dst-api-key",
    envvar="GRAFANA_DST_API_KEY",
    help="Destination Grafana API key for token authentication",
)
@click.option(
    "--dst-username",
    envvar="GRAFANA_DST_USERNAME",
    help="Destination Grafana username for basic authentication",
)
@click.option(
    "--dst-password",
    envvar="GRAFANA_DST_PASSWORD",
    help="Destination Grafana password for basic authentication",
)
@click.option(
    "-f",
    "--folder-uid",
    default=FOLDER_GENERAL,
    help="Optional folder UID to sync only this folder and its subfolders",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Sync folders recursively",
)
@click.option(
    "-d",
    "--include-dashboards",
    is_flag=True,
    help="Include dashboards in the sync",
)
@click.option(
    "-p",
    "--prune",
    is_flag=True,
    help="Remove dashboards in destination that don't exist in source",
)
@click.pass_context
async def sync_folders(
    ctx: click.Context,
    dst_url: str,
    dst_api_key: str | None,
    dst_username: str | None,
    dst_password: str | None,
    folder_uid: str,
    recursive: bool,
    include_dashboards: bool,
    prune: bool,
) -> None:
    """Sync folders from source to destination Grafana instance."""
    src_grafana = ctx.ensure_object(GrafanaClient)
    async with GrafanaClient(
        dst_url, dst_api_key, dst_username, dst_password
    ) as dst_grafana:
        syncer = GrafanaSync(src_grafana, dst_grafana)

        # Track source dashboards if pruning is enabled
        src_dashboard_uids = set()
        dst_dashboard_uids = set()

        if include_dashboards and prune:
            # Get all dashboards in destination folders before we start syncing
            dst_dashboard_uids = await syncer.get_folder_dashboards(
                dst_grafana, folder_uid, recursive
            )

        # if a folder was requested sync it first
        if folder_uid != FOLDER_GENERAL:
            await syncer.sync_folder(folder_uid, can_move=False)

        # Now walk and sync child folders and optionally dashboards
        async for root_uid, folders, dashboards in src_grafana.walk(
            folder_uid, recursive, include_dashboards=include_dashboards
        ):
            for folder in folders.root:
                await syncer.sync_folder(folder.uid, can_move=True)

            # Sync dashboards if requested
            if include_dashboards:
                for dashboard in dashboards.root:
                    dashboard_uid = dashboard.uid
                    if syncer.sync_dashboard(dashboard_uid, root_uid):
                        src_dashboard_uids.add(dashboard_uid)

        await syncer.move_folders_to_new_parents()

        # Prune dashboards that don't exist in source
        if include_dashboards and prune:
            dashboards_to_delete = dst_dashboard_uids - src_dashboard_uids
            for dashboard_uid in dashboards_to_delete:
                await syncer.delete_dashboard(dashboard_uid)


@cli.command(name="backup")
@click.option(
    "-f",
    "--folder-uid",
    default=FOLDER_GENERAL,
    help="Optional folder UID to backup only this folder and its subfolders",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Backup folders recursively",
)
@click.option(
    "-d",
    "--include-dashboards",
    is_flag=True,
    help="Include dashboards in the backup",
)
@click.option(
    "--backup-path",
    type=click.Path(),
    required=True,
    help="Path to store backup files",
)
@click.option(
    "--include-reports",
    is_flag=True,
    help="Include reports in the backup",
)
@click.pass_context
async def backup_folders(
    ctx: click.Context,
    folder_uid: str,
    recursive: bool,
    include_dashboards: bool,
    backup_path: str,
    include_reports: bool,
) -> None:
    """Backup folders and dashboards from Grafana instance to local storage."""
    grafana = ctx.ensure_object(GrafanaClient)
    backup = GrafanaBackup(grafana, backup_path)

    if folder_uid != FOLDER_GENERAL:
        # Backup the specified folder first
        await backup.backup_folder(folder_uid)

    if recursive:
        # Recursively backup from the specified folder
        await backup.backup_recursive(folder_uid, include_dashboards, include_reports)
    elif include_dashboards:
        # Non-recursive, just backup dashboards in the specified folder
        async for _, _, dashboards in grafana.walk(
            folder_uid,
            recursive=False,
            include_dashboards=True,
        ):
            for dashboard in dashboards.root:
                await backup.backup_dashboard(dashboard.uid)


@cli.command(name="restore")
@click.option(
    "-f",
    "--folder-uid",
    help="Optional folder UID to restore only this folder",
)
@click.option(
    "-d",
    "--dashboard-uid",
    help="Optional dashboard UID to restore only this dashboard",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Restore all folders and dashboards from backup",
)
@click.option(
    "--backup-path",
    type=click.Path(exists=True),
    required=True,
    help="Path to read backup files from",
)
@click.option(
    "--include-reports",
    is_flag=True,
    help="Include reports in the restore",
)
@click.pass_context
async def restore_folders(
    ctx: click.Context,
    folder_uid: str | None,
    dashboard_uid: str | None,
    recursive: bool,
    backup_path: str,
    include_reports: bool,
) -> None:
    """Restore folders and dashboards from local storage to Grafana instance."""
    grafana = ctx.ensure_object(GrafanaClient)
    restore = GrafanaRestore(grafana, backup_path)

    if recursive:
        await restore.restore_recursive(include_reports)
    elif folder_uid:
        await restore.restore_folder(folder_uid)
    elif dashboard_uid:
        await restore.restore_dashboard(dashboard_uid)
    else:
        raise click.UsageError(
            "Either --recursive, --folder-uid or --dashboard-uid must be specified"
        )
