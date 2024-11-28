import logging
from typing import Mapping
from urllib.parse import urlparse

import click
from grafana_client import GrafanaApi
from rich import print as rprint
from rich import print_json
from rich.tree import Tree

from grafana_sync.api import (
    FOLDER_GENERAL,
    FolderDashboardSearchResponseItem,
    GetAllFoldersResponseItem,
    get_folder_data,
    walk,
)
from grafana_sync.sync import GrafanaSync

logger = logging.getLogger(__name__)


def create_grafana_client(
    url: str,
    api_key: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> GrafanaApi:
    """Create a Grafana API client from connection parameters."""
    parsed_url = urlparse(url)
    logging.debug("Parsing URL: %s", url)
    host = parsed_url.hostname or "localhost"
    protocol = parsed_url.scheme or "https"
    port = parsed_url.port

    # Extract credentials from URL if present
    if parsed_url.username and parsed_url.password and not (username or password):
        username = parsed_url.username
        password = parsed_url.password

    if api_key:
        auth = (api_key, "")
    elif username and password:
        auth = (username, password)
    else:
        raise click.UsageError(
            "Either --api-key or both --username and --password must be provided (via parameters or URL)"
        )

    url_path_prefix = parsed_url.path.strip("/")
    if url_path_prefix:
        url_path_prefix = f"{url_path_prefix}/"

    return GrafanaApi(
        auth,
        host=host,
        port=port,
        protocol=protocol,
        url_path_prefix=url_path_prefix,
    )


@click.group()
@click.version_option()
@click.option(
    "--url",
    envvar="GRAFANA_URL",
    required=True,
    help="Grafana URL",
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
def cli(
    ctx: click.Context,
    url: str,
    api_key: str | None,
    username: str | None,
    password: str | None,
):
    """Sync Grafana dashboards and folders."""
    logging.basicConfig(level=logging.INFO)
    ctx.obj = create_grafana_client(url, api_key, username, password)


@cli.command(name="list-folders")
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
def list_folders(
    ctx: click.Context,
    folder_uid: str,
    recursive: bool,
    include_dashboards: bool,
    output_json: bool,
) -> None:
    """List folders in a Grafana instance."""
    grafana = ctx.ensure_object(GrafanaApi)

    class TreeDashboardItem:
        """Represents a dashboard item in the folder tree structure."""

        def __init__(self, data: FolderDashboardSearchResponseItem) -> None:
            """Initialize dashboard item with API response data."""
            self.data = data

        @property
        def label(self) -> str:
            """Get the display label for the dashboard."""
            return f"📊 {self.data['title']} ({self.data['uid']})"

        def to_tree(self, parent: Tree) -> None:
            """Add this dashboard as a node to the parent tree."""
            parent.add(self.label)

        def to_obj(self):
            """Convert dashboard item to JSON-compatible representation."""
            return self.data

    class TreeFolderItem:
        """Represents a folder item in the folder tree structure."""

        children: list["TreeFolderItem | TreeDashboardItem"]

        def __init__(self, data: GetAllFoldersResponseItem) -> None:
            """Initialize folder item with API response data."""
            self.children = []
            self.data = data

        def __repr__(self) -> str:
            return f"TreeFolderItem({self.data['title']})"

        @property
        def label(self) -> str:
            """Get the display label for the folder."""
            return f"📁 {self.data['title']} ({self.data['uid']})"

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
                return {"type": "dash-folder", "children": children_data} | self.data
            else:
                return children_data

    folder_nodes: Mapping[str | None, TreeFolderItem] = {}

    for root_uid, folders, dashboards in walk(
        grafana, folder_uid, recursive, include_dashboards
    ):
        if root_uid in folder_nodes:
            root_node = folder_nodes[root_uid]
        else:
            root_folder_data = get_folder_data(grafana, root_uid)
            root_node = TreeFolderItem(root_folder_data)
            folder_nodes[root_uid] = root_node

        for folder in folders:
            if folder["uid"] not in folder_nodes:
                itm = TreeFolderItem(folder)
                folder_nodes[folder["uid"]] = itm
                root_node.children.append(itm)

        for dashboard in dashboards:
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
def sync_folders(
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
    src_grafana = ctx.ensure_object(GrafanaApi)
    dst_grafana = create_grafana_client(
        dst_url, dst_api_key, dst_username, dst_password
    )

    syncer = GrafanaSync(src_grafana, dst_grafana)

    # Track source dashboards if pruning is enabled
    src_dashboard_uids = set()
    dst_dashboard_uids = set()

    if include_dashboards and prune:
        # Get all dashboards in destination folders before we start syncing
        dst_dashboard_uids = syncer.get_folder_dashboards(
            dst_grafana, folder_uid, recursive
        )

    # if a folder was requested sync it first
    if folder_uid != FOLDER_GENERAL:
        syncer.sync_folder(folder_uid, can_move=False)

    # Now walk and sync child folders and optionally dashboards
    for root_uid, folders, dashboards in walk(
        src_grafana, folder_uid, recursive, include_dashboards=include_dashboards
    ):
        for folder in folders:
            syncer.sync_folder(folder["uid"], can_move=True)

        # Sync dashboards if requested
        if include_dashboards:
            for dashboard in dashboards:
                dashboard_uid = dashboard["uid"]
                if syncer.sync_dashboard(dashboard_uid, root_uid):
                    src_dashboard_uids.add(dashboard_uid)

    syncer.move_folders_to_new_parents()

    # Prune dashboards that don't exist in source
    if include_dashboards and prune:
        dashboards_to_delete = dst_dashboard_uids - src_dashboard_uids
        for dashboard_uid in dashboards_to_delete:
            syncer.delete_dashboard(dashboard_uid)
