import json
import logging
from pathlib import Path

from grafana_client import GrafanaApi

from .api import FOLDER_GENERAL
from .backup import GrafanaBackup
from .exceptions import BackupNotFoundError

logger = logging.getLogger(__name__)


def _remove_id(item: dict):
    """Remove id fields from  item."""
    return {k: v for k, v in item.items() if k != "id"}


class GrafanaRestore:
    """Handles restoration of folders and dashboards from local storage to a Grafana instance."""

    def __init__(
        self,
        grafana: GrafanaApi,
        backup_path: Path | str,
    ) -> None:
        self.grafana = grafana
        self.backup_path = Path(backup_path)
        self.folders_path = self.backup_path / "folders"
        self.dashboards_path = self.backup_path / "dashboards"

    def restore_folder(self, folder_uid: str) -> None:
        """Restore a single folder from local storage."""
        folder_file = self.folders_path / f"{folder_uid}.json"

        if not folder_file.exists():
            raise BackupNotFoundError(f"Folder backup {folder_file} not found")

        with folder_file.open() as f:
            folder_data = json.load(f)

        try:
            # Try to get existing folder
            self.grafana.folder.get_folder(folder_uid)
            # Update existing folder - note: parent_uid not supported in update
            self.grafana.folder.update_folder(
                folder_uid,
                title=folder_data["title"],
                overwrite=True,
            )
            logger.info(
                "Updated folder '%s' from %s", folder_data["title"], folder_file
            )
        except Exception as e:
            logger.debug("Failed to update folder: %s", e)
            # Create new folder if it doesn't exist
            self.grafana.folder.create_folder(
                title=folder_data["title"],
                uid=folder_data["uid"],
                parent_uid=folder_data.get("parentUid"),
            )
            logger.info(
                "Created folder '%s' from %s", folder_data["title"], folder_file
            )

    def restore_dashboard(self, dashboard_uid: str) -> None:
        """Restore a single dashboard from local storage."""
        dashboard_file = self.dashboards_path / f"{dashboard_uid}.json"

        if not dashboard_file.exists():
            raise BackupNotFoundError(f"Dashboard backup {dashboard_file} not found")

        with dashboard_file.open() as f:
            dashboard_data = json.load(f)

        payload = {
            "dashboard": _remove_id(dashboard_data["dashboard"]),
            "overwrite": True,
        }

        self.grafana.dashboard.update_dashboard(payload)
        logger.info(
            "Restored dashboard '%s' from %s",
            dashboard_data["dashboard"]["title"],
            dashboard_file,
        )

    def restore_recursive(self) -> None:
        """Recursively restore all folders and dashboards from backup."""
        backup = GrafanaBackup(self.grafana, self.backup_path)
        # First restore all folders (except General)
        for folder_uid, _, dashboards in backup.walk_backup():
            if folder_uid != FOLDER_GENERAL:
                self.restore_folder(folder_uid)
            # Restore dashboards in this folder
            for dashboard in dashboards:
                self.restore_dashboard(dashboard["uid"])
