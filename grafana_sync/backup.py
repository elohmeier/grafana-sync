import json
import logging
from pathlib import Path

from grafana_client import GrafanaApi

from grafana_sync.api import FOLDER_GENERAL, get_folder_data, walk

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
