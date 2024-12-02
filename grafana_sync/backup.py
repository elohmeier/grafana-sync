import json
import logging
from pathlib import Path
from typing import Iterable, Sequence

from grafana_client import GrafanaApi

from grafana_sync.api import (
    FOLDER_GENERAL,
    GetAllFoldersResponse,
    FolderDashboardSearchResponse,
    get_folder_data,
    walk,
)

logger = logging.getLogger(__name__)


class GrafanaBackup:
    """Handles backup of folders and dashboards from a Grafana instance to local storage."""

    def __init__(
        self,
        grafana: GrafanaApi,
        backup_path: Path | str,
    ) -> None:
        self.grafana = grafana
        self.backup_path = Path(backup_path)
        self.folders_path = self.backup_path / "folders"
        self.dashboards_path = self.backup_path / "dashboards"

        self._ensure_backup_dirs()

    def _ensure_backup_dirs(self) -> None:
        """Ensure backup directories exist."""
        self.folders_path.mkdir(parents=True, exist_ok=True)
        self.dashboards_path.mkdir(parents=True, exist_ok=True)

    def backup_folder(self, folder_uid: str) -> None:
        """Backup a single folder to local storage."""
        folder_data = get_folder_data(self.grafana, folder_uid)
        folder_file = self.folders_path / f"{folder_uid}.json"

        with folder_file.open("w") as f:
            json.dump(folder_data, f, indent=2)

        logger.info("Backed up folder '%s' to %s", folder_data["title"], folder_file)

    def backup_dashboard(self, dashboard_uid: str) -> None:
        """Backup a single dashboard to local storage."""
        dashboard = self.grafana.dashboard.get_dashboard(dashboard_uid)
        if not dashboard:
            logger.error("Dashboard %s not found", dashboard_uid)
            return

        dashboard_file = self.dashboards_path / f"{dashboard_uid}.json"

        with dashboard_file.open("w") as f:
            json.dump(dashboard, f, indent=2)

        logger.info(
            "Backed up dashboard '%s' to %s",
            dashboard["dashboard"]["title"],
            dashboard_file,
        )

    def walk_backup(
        self, folder_uid: str = FOLDER_GENERAL
    ) -> Iterable[tuple[str, GetAllFoldersResponse, FolderDashboardSearchResponse]]:
        """Walk through the backup folder structure, similar to walk()."""
        folders_path = self.folders_path
        dashboards_path = self.dashboards_path

        def get_subfolders(parent_uid: str) -> GetAllFoldersResponse:
            result = []
            for folder_file in folders_path.glob("*.json"):
                with folder_file.open() as f:
                    folder_data = json.load(f)
                    parent = folder_data.get("parentUid")
                    if (parent_uid == FOLDER_GENERAL and parent is None) or (
                        parent_uid != FOLDER_GENERAL and parent == parent_uid
                    ):
                        result.append(
                            {
                                "uid": folder_data["uid"],
                                "title": folder_data["title"],
                            }
                        )
            return result

        def get_dashboards(folder_uid: str) -> FolderDashboardSearchResponse:
            result = []
            for dashboard_file in dashboards_path.glob("*.json"):
                with dashboard_file.open() as f:
                    dashboard_data = json.load(f)
                    if dashboard_data["meta"].get("folderUid") == folder_uid:
                        result.append(
                            {
                                "uid": dashboard_data["dashboard"]["uid"],
                                "title": dashboard_data["dashboard"]["title"],
                            }
                        )
            return result

        def walk_recursive(
            current_uid: str,
        ) -> Iterable[tuple[str, Sequence, Sequence]]:
            subfolders = get_subfolders(current_uid)
            dashboards = get_dashboards(current_uid)
            yield current_uid, subfolders, dashboards

            for folder in subfolders:
                yield from walk_recursive(folder["uid"])

        yield from walk_recursive(folder_uid)

    def backup_recursive(
        self,
        folder_uid: str = FOLDER_GENERAL,
        include_dashboards: bool = True,
    ) -> None:
        """Recursively backup folders and optionally dashboards starting from a folder."""
        self._ensure_backup_dirs()

        for folder_uid, _, dashboards in walk(
            self.grafana,
            folder_uid,
            recursive=True,
            include_dashboards=include_dashboards,
        ):
            # Backup folder
            if folder_uid != FOLDER_GENERAL:
                self.backup_folder(folder_uid)

            # Backup dashboards
            if include_dashboards:
                for dashboard in dashboards:
                    self.backup_dashboard(dashboard["uid"])
