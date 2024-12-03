import logging
from pathlib import Path
from typing import TYPE_CHECKING

from grafana_sync.api.client import FOLDER_GENERAL, FOLDER_SHAREDWITHME
from grafana_sync.api.models import (
    GetDashboardResponse,
    GetFolderResponse,
    GetReportResponse,
)
from grafana_sync.backup import GrafanaBackup
from grafana_sync.exceptions import BackupNotFoundError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from grafana_sync.api.client import GrafanaClient


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
        self.reports_path = self.backup_path / "reports"

    async def restore_folder(self, folder_uid: str) -> None:
        """Restore a single folder from local storage."""
        folder_file = self.folders_path / f"{folder_uid}.json"

        if not folder_file.exists():
            raise BackupNotFoundError(f"Folder backup {folder_file} not found")

        with folder_file.open() as f:
            folder_data = GetFolderResponse.model_validate_json(f.read())

        try:
            # Try to get existing folder
            await self.grafana.get_folder(folder_uid)
            # Update existing folder - note: parent_uid not supported in update
            await self.grafana.update_folder(
                folder_uid, title=folder_data.title, overwrite=True
            )
            logger.info("Updated folder '%s' from %s", folder_data.title, folder_file)
        except Exception as e:
            logger.debug("Failed to update folder: %s", e)
            # Create new folder if it doesn't exist
            await self.grafana.create_folder(
                title=folder_data.title,
                uid=folder_data.uid,
                parent_uid=folder_data.parentUid,
            )
            logger.info("Created folder '%s' from %s", folder_data.title, folder_file)

    async def restore_dashboard(self, dashboard_uid: str) -> None:
        """Restore a single dashboard from local storage."""
        dashboard_file = self.dashboards_path / f"{dashboard_uid}.json"

        if not dashboard_file.exists():
            raise BackupNotFoundError(f"Dashboard backup {dashboard_file} not found")

        with dashboard_file.open() as f:
            dashboard_data = GetDashboardResponse.model_validate_json(f.read())

        await self.grafana.update_dashboard(
            dashboard_data.dashboard, dashboard_data.meta.folderUid
        )
        logger.info(
            "Restored dashboard '%s' from %s",
            dashboard_data.dashboard.title,
            dashboard_file,
        )

    async def restore_report(self, report_id: int) -> None:
        """Restore a single report from local storage."""
        report_file = self.reports_path / f"{report_id}.json"

        if not report_file.exists():
            raise BackupNotFoundError(f"Report backup {report_file} not found")

        with report_file.open() as f:
            report_data = GetReportResponse.model_validate_json(f.read())

        await self.grafana.create_report(report_data)
        logger.info(
            "Restored report '%s' from %s",
            report_data.name,
            report_file,
        )

    async def restore_recursive(self, include_reports: bool = False) -> None:
        """Recursively restore all folders, dashboards and reports from backup."""
        backup = GrafanaBackup(self.grafana, self.backup_path)
        # First restore all folders (except General)
        for folder_uid, _, dashboards in backup.walk_backup():
            if folder_uid not in [FOLDER_GENERAL, FOLDER_SHAREDWITHME]:
                await self.restore_folder(folder_uid)
            # Restore dashboards in this folder
            for dashboard in dashboards:
                await self.restore_dashboard(dashboard.dashboard.uid)

        # Restore reports if requested
        if include_reports:
            for report_file in self.reports_path.glob("*.json"):
                report_id = int(report_file.stem)
                await self.restore_report(report_id)
