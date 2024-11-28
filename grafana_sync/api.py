import functools
import logging
from typing import Iterable, NotRequired, Sequence, TypedDict, cast

from grafana_client import GrafanaApi

logger = logging.getLogger(__name__)

# reserved Grafana folder name for the top-level directory
FOLDER_GENERAL = "general"


# see https://grafana.com/docs/grafana/latest/developers/http_api/folder/#get-all-folders
# for other available fields
class GetAllFoldersResponseItem(TypedDict):
    uid: str
    title: str


GetAllFoldersResponse = Sequence[GetAllFoldersResponseItem]


# see https://grafana.com/docs/grafana/latest/developers/http_api/folder_dashboard_search/
# for other available fields
class FolderDashboardSearchResponseItem(TypedDict):
    uid: str
    title: str


FolderDashboardSearchResponse = Sequence[FolderDashboardSearchResponseItem]


# see https://grafana.com/docs/grafana/latest/developers/http_api/folder/#get-folder-by-uid
# for other available fields (parentUid undocumented)
class GetFolderByUidResponse(TypedDict):
    uid: str
    title: str
    parentUid: NotRequired[str]


def walk(
    grafana: GrafanaApi, folder_uid: str, recursive: bool, include_dashboards: bool
) -> Iterable[tuple[str, GetAllFoldersResponse, FolderDashboardSearchResponse]]:
    """Walk through Grafana folder structure, similar to os.walk."""
    # https://grafana.com/docs/grafana/latest/developers/http_api/folder/#get-all-folders
    # non-recursive
    logger.debug("fetching folders for folder_uid %s", folder_uid)
    subfolders = cast(
        GetAllFoldersResponse,
        grafana.folder.get_all_folders(
            parent_uid=folder_uid if folder_uid != FOLDER_GENERAL else None
        ),
    )  # default pagination limit: 1000

    if include_dashboards:
        logger.debug("searching dashboards for folder_uid %s", folder_uid)
        dashboards = cast(
            FolderDashboardSearchResponse,
            grafana.search.search_dashboards(
                folder_uids=[folder_uid],
                type_="dash-db",
            ),
        )
    else:
        dashboards = []

    yield folder_uid, subfolders, dashboards

    if recursive:
        for folder in subfolders:
            yield from walk(grafana, folder["uid"], recursive, include_dashboards)


@functools.lru_cache
def get_folder_data(grafana: GrafanaApi, folder_uid: str) -> GetFolderByUidResponse:
    return cast(
        GetFolderByUidResponse,
        grafana.folder.get_folder(uid=folder_uid),
    )
