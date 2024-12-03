import logging
import os
import ssl
from typing import AsyncGenerator, Self
from urllib.parse import urlparse

import certifi
import httpx
from httpx import Response

from grafana_sync.api.models import (
    CreateFolderResponse,
    CreateReportResponse,
    DashboardData,
    GetDashboardResponse,
    GetFolderResponse,
    GetFoldersResponse,
    GetReportResponse,
    GetReportsResponse,
    SearchDashboardsResponse,
    UpdateDashboardRequest,
    UpdateDashboardResponse,
    UpdateFolderResponse,
)
from grafana_sync.exceptions import (
    ExistingDashboardsError,
    ExistingFoldersError,
    GrafanaApiError,
)

logger = logging.getLogger(__name__)

# reserved Grafana folder name for the top-level directory
FOLDER_GENERAL = "general"

# virtual folder
FOLDER_SHAREDWITHME = "sharedwithme"


class GrafanaClient:
    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Create a Grafana API client from connection parameters."""
        self.url = url
        self.api_key = api_key
        parsed_url = urlparse(url)
        logging.debug("Parsing URL: %s", url)
        host = parsed_url.hostname or "localhost"
        protocol = parsed_url.scheme or "https"
        port = parsed_url.port

        # Extract credentials from URL if present
        if parsed_url.username and parsed_url.password and not (username or password):
            username = parsed_url.username
            password = parsed_url.password

        self.username = username
        self.password = password

        if api_key:
            auth = (api_key, "")
        elif username and password:
            auth = (username, password)
        else:
            raise ValueError(
                "Either --api-key or both --username and --password must be provided (via parameters or URL)"
            )

        # Construct base URL
        base_url = f"{protocol}://{host}"
        if port:
            base_url = f"{base_url}:{port}"

        url_path_prefix = parsed_url.path.strip("/")
        if url_path_prefix:
            base_url = f"{base_url}/{url_path_prefix}"

        # Create SSL context using environment variables or certifi
        ssl_context = ssl.create_default_context(
            cafile=os.getenv("REQUESTS_CA_BUNDLE")
            or os.getenv("SSL_CERT_FILE")
            or certifi.where(),
            capath=os.getenv("SSL_CERT_DIR"),
        )

        self.client = httpx.AsyncClient(
            base_url=base_url,
            auth=auth,
            headers={"Content-Type": "application/json"},
            follow_redirects=True,
            verify=ssl_context,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.client.aclose()

    def _log_request(self, response: Response) -> None:
        """Log request and response details at debug level."""
        logger.debug(
            "HTTP %s %s\nHeaders: %s\nRequest Body: %s\nResponse Status: %d\nResponse Body: %s",
            response.request.method,
            response.request.url,
            response.request.headers,
            response.request.content.decode() if response.request.content else "None",
            response.status_code,
            response.text,
        )

    def _handle_error(self, response: Response) -> None:
        """Handle error responses from Grafana API.

        Args:
            response: The HTTP response to check

        Raises:
            GrafanaApiError: If the response indicates an error
        """
        self._log_request(response)
        if response.is_error:
            raise GrafanaApiError(response)

    async def create_folder(
        self, title: str, uid: str | None = None, parent_uid: str | None = None
    ) -> CreateFolderResponse:
        """Create a new folder in Grafana.

        Args:
            title: The title of the folder
            uid: Optional unique identifier. Will be auto-generated if not provided
            parent_uid: Optional parent folder UID for nested folders

        Returns:
            CreateFolderResponse: The created folder details

        Raises:
            HTTPError: If the request fails
        """
        data = {"title": title}
        if uid:
            data["uid"] = uid
        if parent_uid:
            data["parentUid"] = parent_uid

        response = await self.client.post("/api/folders", json=data)
        self._handle_error(response)
        return CreateFolderResponse.model_validate_json(response.content)

    async def delete_folder(self, uid: str) -> None:
        """Delete a folder in Grafana.

        Args:
            uid: The unique identifier of the folder to delete

        Raises:
            HTTPError: If the request fails
        """
        response = await self.client.delete(f"/api/folders/{uid}")
        self._handle_error(response)

    async def get_folders(self, parent_uid: str | None = None) -> GetFoldersResponse:
        """Get all folders in Grafana, optionally filtered by parent UID.

        Args:
            parent_uid: Optional parent folder UID to filter by

        Returns:
            GetFoldersResponse: List of folders

        Raises:
            GrafanaApiError: If the request fails
        """
        params = {}
        if parent_uid and parent_uid != FOLDER_GENERAL:
            params["parentUid"] = parent_uid

        response = await self.client.get("/api/folders", params=params)
        self._handle_error(response)
        return GetFoldersResponse.model_validate_json(response.content)

    async def get_folder(self, uid: str) -> GetFolderResponse:
        """Get a specific folder by UID.

        Args:
            uid: The unique identifier of the folder

        Returns:
            GetFolderResponse: The folder details

        Raises:
            GrafanaApiError: If the request fails or folder doesn't exist
        """
        response = await self.client.get(f"/api/folders/{uid}")
        self._handle_error(response)
        return GetFolderResponse.model_validate_json(response.content)

    async def update_folder(
        self,
        uid: str,
        title: str,
        version: int | None = None,
        parent_uid: str | None = None,
        overwrite: bool = False,
    ) -> UpdateFolderResponse:
        """Update a folder in Grafana.

        Args:
            uid: The unique identifier of the folder to update
            title: The new title for the folder
            version: Current version of the folder (required unless overwrite=True)
            parent_uid: Optional new parent folder UID
            overwrite: Whether to overwrite existing folder with same name

        Returns:
            UpdateFolderResponse: The updated folder details

        Raises:
            GrafanaApiError: If the request fails
            ValueError: If version is not provided and overwrite is False
        """
        if not overwrite and version is None:
            raise ValueError("version must be provided when overwrite=False")

        data = {
            "title": title,
            "overwrite": overwrite,
        }
        if not overwrite:
            data["version"] = version
        if parent_uid:
            data["parentUid"] = parent_uid

        response = await self.client.put(f"/api/folders/{uid}", json=data)
        self._handle_error(response)
        return UpdateFolderResponse.model_validate_json(response.content)

    async def move_folder(
        self, uid: str, new_parent_uid: str | None = None
    ) -> UpdateFolderResponse:
        """Move a folder to a new parent folder.

        Args:
            uid: The unique identifier of the folder to move
            new_parent_uid: The UID of the new parent folder, or None for root

        Returns:
            UpdateFolderResponse: The updated folder details

        Raises:
            GrafanaApiError: If the request fails
        """
        # Get current folder details to preserve title
        current = await self.get_folder(uid)

        # Update folder with new parent
        return await self.update_folder(
            uid=uid,
            title=current.title,
            parent_uid=new_parent_uid,
            overwrite=True,
        )

    async def search_dashboards(
        self,
        folder_uids: list[str] | None = None,
        query: str | None = None,
        tag: list[str] | None = None,
        type_: str = "dash-db",
    ) -> SearchDashboardsResponse:
        """Search for dashboards in Grafana.

        Args:
            folder_uids: Optional list of folder UIDs to search in
            query: Optional search query string
            tag: Optional list of tags to filter by
            type_: Type of dashboard to search for (default: dash-db)

        Returns:
            SearchDashboardsResponse: List of matching dashboards

        Raises:
            GrafanaApiError: If the request fails
        """
        params: dict = {"type": type_}

        if folder_uids:
            params["folderUIDs"] = ",".join(folder_uids)
        if query:
            params["query"] = query
        if tag:
            params["tag"] = tag

        response = await self.client.get("/api/search", params=params)
        self._handle_error(response)
        return SearchDashboardsResponse.model_validate_json(response.content)

    async def update_dashboard(
        self, dashboard_data: DashboardData, folder_uid: str | None = None
    ) -> UpdateDashboardResponse:
        """Update or create a dashboard in Grafana.

        Args:
            dashboard_data: The complete dashboard model (must include uid)
            folder_uid: Optional folder UID to move dashboard to

        Returns:
            UpdateDashboardResponse: The updated dashboard details

        Raises:
            GrafanaApiError: If the request fails
        """
        # Prepare the dashboard update payload
        payload = UpdateDashboardRequest(
            dashboard=dashboard_data,
            message="Dashboard updated via API",
            overwrite=True,
            folderUid=None if folder_uid == FOLDER_GENERAL else folder_uid,
        )

        response = await self.client.post(
            "/api/dashboards/db", json=payload.model_dump(exclude={"dashboard": {"id"}})
        )
        self._handle_error(response)
        return UpdateDashboardResponse.model_validate_json(response.content)

    async def delete_dashboard(self, uid: str) -> None:
        """Delete a dashboard in Grafana.

        Args:
            uid: The unique identifier of the dashboard to delete

        Raises:
            GrafanaApiError: If the request fails
        """
        response = await self.client.delete(f"/api/dashboards/uid/{uid}")
        self._handle_error(response)

    async def get_dashboard(self, uid: str) -> GetDashboardResponse:
        """Get a dashboard by its UID.

        Args:
            uid: The unique identifier of the dashboard

        Returns:
            GetDashboardResponse: The dashboard details including meta information

        Raises:
            GrafanaApiError: If the request fails or dashboard doesn't exist
        """
        response = await self.client.get(f"/api/dashboards/uid/{uid}")
        self._handle_error(response)
        return GetDashboardResponse.model_validate_json(response.content)

    async def get_reports(self) -> GetReportsResponse:
        """Get all reports.

        Returns:
            GetReportsResponse: List of reports

        Raises:
            GrafanaApiError: If the request fails
        """
        response = await self.client.get("/api/reports")
        self._handle_error(response)
        return GetReportsResponse.model_validate_json(response.content)

    async def get_report(self, report_id: int) -> GetReportResponse:
        """Get a report by its ID.

        Args:
            report_id: The unique identifier of the report

        Returns:
            GetReportResponse: The report details

        Raises:
            GrafanaApiError: If the request fails
        """
        response = await self.client.get(f"/api/reports/{report_id}")
        self._handle_error(response)
        return GetReportResponse.model_validate_json(response.content)

    async def create_report(self, report: GetReportResponse) -> CreateReportResponse:
        """Create a new report.

        Args:
            report: The report data

        Returns:
            CreateReportResponse: The created report

        Raises:
            GrafanaApiError: If the request fails
        """
        response = await self.client.post(
            "/api/reports", json=report.model_dump(exclude={"id"})
        )
        self._handle_error(response)
        return CreateReportResponse.model_validate_json(response.content)

    async def delete_report(self, report_id: int) -> None:
        """Delete a report.

        Args:
            report_id: The unique identifier of the report

        Raises:
            GrafanaApiError: If the request fails
        """
        response = await self.client.delete(f"/api/reports/{report_id}")
        self._handle_error(response)

    async def walk(
        self,
        folder_uid: str = FOLDER_GENERAL,
        recursive: bool = False,
        include_dashboards: bool = True,
    ) -> AsyncGenerator[tuple[str, GetFoldersResponse, SearchDashboardsResponse], None]:
        """Walk through Grafana folder structure, similar to os.walk.

        Args:
            folder_uid: The folder UID to start walking from (default: "general")
            recursive: Whether to recursively walk through subfolders
            include_dashboards: Whether to include dashboards in the results

        Yields:
            Tuple of (folder_uid, subfolders, dashboards)
        """
        logger.debug("fetching folders for folder_uid %s", folder_uid)
        subfolders = await self.get_folders(parent_uid=folder_uid)

        if include_dashboards:
            logger.debug("searching dashboards for folder_uid %s", folder_uid)
            dashboards = await self.search_dashboards(
                folder_uids=[folder_uid],
                type_="dash-db",
            )
        else:
            dashboards = SearchDashboardsResponse(root=[])

        yield folder_uid, subfolders, dashboards

        if recursive:
            for folder in subfolders.root:
                async for res in self.walk(folder.uid, recursive, include_dashboards):
                    yield res

    async def check_pristine(self) -> None:
        folders = (await self.get_folders()).root
        if len(folders) > 0:
            raise ExistingFoldersError(len(folders))

        # Check for dashboards in the general folder
        dashboards = (await self.search_dashboards()).root
        if len(dashboards) > 0:
            raise ExistingDashboardsError(len(dashboards))
