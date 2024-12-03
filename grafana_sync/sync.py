import logging
from typing import TYPE_CHECKING

from grafana_sync.api.client import FOLDER_GENERAL

if TYPE_CHECKING:
    from grafana_sync.api.client import GrafanaClient
    from grafana_sync.api.models import DashboardData

logger = logging.getLogger(__name__)


class GrafanaSync:
    """Handles synchronization of folders and dashboards between Grafana instances."""

    def __init__(
        self,
        src_grafana: "GrafanaClient",
        dst_grafana: "GrafanaClient",
    ) -> None:
        self.src_grafana = src_grafana
        self.dst_grafana = dst_grafana
        self.folder_relocation_queue: dict[str, str] = {}

    async def sync_folder(
        self,
        folder_uid: str,
        can_move: bool,
    ) -> None:
        """Sync a single folder from source to destination Grafana instance."""
        src_folder = await self.src_grafana.get_folder(folder_uid)
        title = src_folder.title
        parent_uid = src_folder.parentUid or FOLDER_GENERAL

        # Check if folder already exists
        try:
            existing_dst_folder = await self.dst_grafana.get_folder(folder_uid)
        except Exception:
            # Folder doesn't exist, create it
            logger.info("Creating folder '%s' in destination", title)
            try:
                if parent_uid == FOLDER_GENERAL:
                    dst_parent_uid = None
                else:
                    # Check if parent_uid is available in dst
                    try:
                        await self.dst_grafana.get_folder(parent_uid)
                    except Exception:
                        dst_parent_uid = None
                    else:
                        dst_parent_uid = parent_uid

                await self.dst_grafana.create_folder(
                    title=title, uid=folder_uid, parent_uid=dst_parent_uid
                )
                logger.info("Created folder '%s' (uid: %s)", title, folder_uid)
            except Exception as e:
                logger.error("Failed to create folder '%s': %s", title, e)
        else:
            if existing_dst_folder.title != title:
                logger.info("Updating folder title '%s' in destination", title)
                try:
                    await self.dst_grafana.update_folder(
                        uid=folder_uid,
                        title=title,
                        overwrite=True,
                    )
                except Exception as e:
                    logger.error("Failed to update folder '%s': %s", title, e)

            # check if the folder needs to be moved
            if (
                can_move
                and (existing_dst_folder.parentUid or FOLDER_GENERAL) != parent_uid
            ):
                # since a parent might not exist yet, we enqueue the relocations
                self.folder_relocation_queue[folder_uid] = parent_uid

    async def move_folders_to_new_parents(self) -> None:
        for folder_uid, parent_uid in self.folder_relocation_queue.items():
            try:
                await self.dst_grafana.move_folder(
                    folder_uid, parent_uid if parent_uid != FOLDER_GENERAL else None
                )
                logger.info(
                    "Moved folder '%s' to new parent '%s'", folder_uid, parent_uid
                )
            except Exception as e:
                logger.error(
                    "Failed to move folder '%s' to new parent '%s': %s",
                    folder_uid,
                    parent_uid,
                    e,
                )

        self.folder_relocation_queue.clear()

    async def get_folder_dashboards(
        self,
        grafana: "GrafanaClient",
        folder_uid: str,
        recursive: bool,
    ) -> set[str]:
        """Get all dashboard UIDs in a folder (and optionally its subfolders)."""
        dashboard_uids = set()

        try:
            async for _, _, dashboards in grafana.walk(
                folder_uid, recursive, include_dashboards=True
            ):
                for dashboard in dashboards.root:
                    dashboard_uids.add(dashboard.uid)
        except Exception as e:
            logger.warning("Failed to get dashboards for folder %s: %s", folder_uid, e)

        return dashboard_uids

    async def delete_dashboard(self, dashboard_uid: str) -> bool:
        """Delete a dashboard from destination Grafana instance."""
        try:
            await self.dst_grafana.delete_dashboard(dashboard_uid)
            logger.info("Deleted dashboard with uid: %s", dashboard_uid)
            return True
        except Exception as e:
            logger.error("Failed to delete dashboard %s: %s", dashboard_uid, e)
            return False

    def _clean_dashboard_for_comparison(self, dashboard_data: "DashboardData") -> dict:
        """Remove dynamic fields from dashboard data for comparison."""
        return dashboard_data.model_dump(exclude={"id", "version"})

    async def sync_dashboard(
        self,
        dashboard_uid: str,
        folder_uid: str | None = None,
    ) -> bool:
        """Sync a single dashboard from source to destination Grafana instance.

        Returns True if sync was successful, False otherwise.
        """
        try:
            # Get dashboard from source
            src_dashboard = await self.src_grafana.get_dashboard(dashboard_uid)
            if not src_dashboard:
                logger.error("Dashboard %s not found in source", dashboard_uid)
                return False

            src_data = src_dashboard.dashboard

            # Check if dashboard exists in destination
            try:
                dst_dashboard = await self.dst_grafana.get_dashboard(dashboard_uid)
                dst_data = dst_dashboard.dashboard

                # Compare dashboards after cleaning
                if self._clean_dashboard_for_comparison(
                    src_data
                ) == self._clean_dashboard_for_comparison(dst_data):
                    logger.info(
                        "Dashboard '%s' (uid: %s) is identical, skipping update",
                        src_data.title,
                        dashboard_uid,
                    )
                    return True
            except Exception:
                # Dashboard doesn't exist in destination
                pass

            # Import dashboard to destination
            await self.dst_grafana.update_dashboard(
                src_data,
                folder_uid=folder_uid if folder_uid != FOLDER_GENERAL else None,
            )
            logger.info(
                "Synced dashboard '%s' (uid: %s)",
                src_data.title,
                dashboard_uid,
            )
            return True
        except Exception as e:
            logger.error("Failed to sync dashboard %s: %s", dashboard_uid, e)
            return False
