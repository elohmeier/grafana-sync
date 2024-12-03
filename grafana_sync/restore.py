import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .api import FOLDER_GENERAL, GetDashboardResponse, GetFolderResponse
from .backup import GrafanaBackup
from .exceptions import BackupNotFoundError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from grafana_sync.api import GrafanaClient


class GrafanaRestore:
    """Handles restoration of folders and dashboards from local storage to a Grafana instance."""

    def __init__(
        self,
        grafana: "GrafanaClient",
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
            folder_data = GetFolderResponse.model_validate_json(f.read())

        try:
            # Try to get existing folder
            self.grafana.get_folder(folder_uid)
            # Update existing folder - note: parent_uid not supported in update
            self.grafana.update_folder(
                folder_uid, title=folder_data.title, overwrite=True
            )
            logger.info("Updated folder '%s' from %s", folder_data.title, folder_file)
        except Exception as e:
            logger.debug("Failed to update folder: %s", e)
            # Create new folder if it doesn't exist
            self.grafana.create_folder(
                title=folder_data.title,
                uid=folder_data.uid,
                parent_uid=folder_data.parentUid,
            )
            logger.info("Created folder '%s' from %s", folder_data.title, folder_file)

    def restore_dashboard(self, dashboard_uid: str) -> None:
        """Restore a single dashboard from local storage."""
        dashboard_file = self.dashboards_path / f"{dashboard_uid}.json"

        if not dashboard_file.exists():
            raise BackupNotFoundError(f"Dashboard backup {dashboard_file} not found")

        with dashboard_file.open() as f:
            dashboard_data = GetDashboardResponse.model_validate_json(f.read())

        self.grafana.update_dashboard(
            dashboard_data.dashboard, dashboard_data.meta.folderUid
        )
        logger.info(
            "Restored dashboard '%s' from %s",
            dashboard_data.dashboard.title,
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
                self.restore_dashboard(dashboard.dashboard.uid)
