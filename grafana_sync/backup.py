import logging
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Iterable, Sequence

from grafana_sync.api.client import FOLDER_GENERAL, FOLDER_SHAREDWITHME
from grafana_sync.api.models import GetDashboardResponse, GetFoldersResponseItem

if TYPE_CHECKING:
    from grafana_sync.api.client import GrafanaClient

logger = logging.getLogger(__name__)


class GrafanaBackup:
    """Handles backup of folders and dashboards from a Grafana instance to local storage."""

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

        self._ensure_backup_dirs()

    def _ensure_backup_dirs(self) -> None:
        """Ensure backup directories exist."""
        self.folders_path.mkdir(parents=True, exist_ok=True)
        self.dashboards_path.mkdir(parents=True, exist_ok=True)
        self.reports_path.mkdir(parents=True, exist_ok=True)

    async def backup_folder(self, folder_uid: str) -> None:
        """Backup a single folder to local storage."""
        folder_data = await self.grafana.get_folder(folder_uid)
        folder_file = self.folders_path / f"{folder_uid}.json"

        with folder_file.open("w") as f:
            f.write(folder_data.model_dump_json(indent=2))

        logger.info("Backed up folder '%s' to %s", folder_data.title, folder_file)

    async def backup_dashboard(self, dashboard_uid: str) -> None:
        """Backup a single dashboard to local storage."""
        dashboard = await self.grafana.get_dashboard(dashboard_uid)
        if not dashboard:
            logger.error("Dashboard %s not found", dashboard_uid)
            return

        dashboard_file = self.dashboards_path / f"{dashboard_uid}.json"

        with dashboard_file.open("w") as f:
            f.write(dashboard.model_dump_json(indent=2))

        logger.info(
            "Backed up dashboard '%s' to %s",
            dashboard.dashboard.title,
            dashboard_file,
        )

    def walk_backup(
        self, folder_uid: str = FOLDER_GENERAL
    ) -> Iterable[
        tuple[str, Sequence[GetFoldersResponseItem], Sequence[GetDashboardResponse]]
    ]:
        """Walk through the backup folder structure, similar to walk()."""
        folders_path = self.folders_path
        dashboards_path = self.dashboards_path

        def get_subfolders(
            parent_uid: str,
        ) -> Generator[GetFoldersResponseItem, None, None]:
            for folder_file in folders_path.glob("*.json"):
                with folder_file.open() as f:
                    folder_data = GetFoldersResponseItem.model_validate_json(f.read())

                parent = folder_data.parentUid
                if (parent_uid == FOLDER_GENERAL and parent is None) or (
                    parent_uid != FOLDER_GENERAL and parent == parent_uid
                ):
                    yield folder_data

        def get_dashboards(
            folder_uid: str,
        ) -> Generator[GetDashboardResponse, None, None]:
            for dashboard_file in dashboards_path.glob("*.json"):
                with dashboard_file.open() as f:
                    dashboard_data = GetDashboardResponse.model_validate_json(f.read())
                if folder_uid == FOLDER_GENERAL:
                    if dashboard_data.meta.folderUid == "":
                        yield dashboard_data
                elif dashboard_data.meta.folderUid == folder_uid:
                    yield dashboard_data

        def walk_recursive(
            current_uid: str,
        ) -> Iterable[
            tuple[str, Sequence[GetFoldersResponseItem], Sequence[GetDashboardResponse]]
        ]:
            # skip special folder
            if current_uid == FOLDER_SHAREDWITHME:
                return

            subfolders = list(get_subfolders(current_uid))
            dashboards = list(get_dashboards(current_uid))
            yield current_uid, subfolders, dashboards

            for folder in subfolders:
                yield from walk_recursive(folder.uid)

        yield from walk_recursive(folder_uid)

    async def backup_report(self, report_id: int) -> None:
        """Backup a single report to local storage."""
        report = await self.grafana.get_report(report_id)
        report_file = self.reports_path / f"{report_id}.json"

        with report_file.open("w") as f:
            f.write(report.model_dump_json(indent=2))

        logger.info("Backed up report '%s' to %s", report.name, report_file)

    async def backup_recursive(
        self,
        folder_uid: str = FOLDER_GENERAL,
        include_dashboards: bool = True,
        include_reports: bool = False,
    ) -> None:
        """Recursively backup folders, dashboards, and reports starting from a folder."""
        self._ensure_backup_dirs()

        async for folder_uid, _, dashboards in self.grafana.walk(
            folder_uid,
            recursive=True,
            include_dashboards=include_dashboards,
        ):
            # Backup folder
            if folder_uid != FOLDER_GENERAL:
                await self.backup_folder(folder_uid)

            # Backup dashboards
            if include_dashboards:
                for dashboard in dashboards.root:
                    await self.backup_dashboard(dashboard.uid)

        # Backup reports
        if include_reports:
            reports = await self.grafana.get_reports()
            for report in reports.root:
                await self.backup_report(report.id)
