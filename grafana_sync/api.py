import logging
import os
import ssl
from typing import Iterable, Self
from urllib.parse import urlparse

import certifi
import httpx
from httpx import Response
from pydantic import BaseModel, ConfigDict, Field, RootModel

logger = logging.getLogger(__name__)

# reserved Grafana folder name for the top-level directory
FOLDER_GENERAL = "general"


class GrafanaErrorResponse(BaseModel):
    """Model for Grafana API error responses."""

    message: str
    status: str | None = None


class CreateFolderResponse(BaseModel):
    """Response model for folder creation API."""

    uid: str
    title: str
    url: str
    version: int
    parentUid: str | None = None


class GetFoldersResponseItem(BaseModel):
    """Model for individual folder items in get_folders response."""

    uid: str
    title: str
    parentUid: str | None = None


class GetFoldersResponse(RootModel):
    """Response model for get_folders API."""

    root: list[GetFoldersResponseItem]


class GetFolderResponse(BaseModel):
    """Response model for get_folder API."""

    uid: str
    title: str
    url: str
    parentUid: str | None = None


class SearchDashboardsResponseItem(BaseModel):
    """Model for individual dashboard items in search response."""

    uid: str
    title: str
    uri: str
    url: str
    type_: str = Field(alias="type")
    tags: list[str]
    slug: str
    folderUid: str | None = None
    folderTitle: str | None = None


class SearchDashboardsResponse(RootModel):
    """Response model for dashboard search API."""

    root: list[SearchDashboardsResponseItem]


class DashboardData(BaseModel):
    uid: str
    title: str

    model_config = ConfigDict(extra="allow")


class UpdateDashboardRequest(BaseModel):
    dashboard: DashboardData
    folderUid: str | None = None
    message: str | None = None
    overwrite: bool | None = None


class UpdateDashboardResponse(BaseModel):
    """Response model for dashboard update API."""

    id: int
    uid: str
    url: str
    status: str
    version: int
    slug: str


class DashboardMeta(BaseModel):
    folderUid: str

    model_config = ConfigDict(extra="allow")


class GetDashboardResponse(BaseModel):
    """Response model for dashboard get API."""

    dashboard: DashboardData
    meta: DashboardMeta


class Report(BaseModel):
    """Model for report data."""

    id: int
    name: str

    model_config = ConfigDict(extra="allow")


class GetReportsResponse(RootModel):
    """Response model for reports list API."""

    root: list[Report]


class GetReportResponse(BaseModel):
    """Response model for single report API."""

    report: Report


class UpdateFolderResponse(BaseModel):
    """Response model for folder update API."""

    uid: str
    title: str
    url: str
    version: int
    parentUid: str | None = None


class GrafanaApiError(Exception):
    """Custom exception for Grafana API errors that includes the response details."""

    def __init__(self, response: Response, message: str | None = None):
        self.response = response
        self.status_code = response.status_code
        self.request_method = response.request.method
        self.request_url = str(response.request.url)

        try:
            error_data = GrafanaErrorResponse.model_validate_json(response.content)
            self.error_message = error_data.message
            self.error_status = error_data.status
        except Exception:
            self.error_message = response.text
            self.error_status = None

        self.message = (
            message
            or f"Grafana API error: {self.request_method} {self.request_url} "
            f"returned {response.status_code} - {self.error_message}"
            + (f" ({self.error_status})" if self.error_status else "")
        )
        super().__init__(self.message)


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

        self.client = httpx.Client(
            base_url=base_url,
            auth=auth,
            headers={"Content-Type": "application/json"},
            follow_redirects=True,
            verify=ssl_context,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.client.close()

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

    def create_folder(
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

        response = self.client.post("/api/folders", json=data)
        self._handle_error(response)
        return CreateFolderResponse.model_validate_json(response.content)

    def delete_folder(self, uid: str) -> None:
        """Delete a folder in Grafana.

        Args:
            uid: The unique identifier of the folder to delete

        Raises:
            HTTPError: If the request fails
        """
        response = self.client.delete(f"/api/folders/{uid}")
        self._handle_error(response)

    def get_folders(self, parent_uid: str | None = None) -> GetFoldersResponse:
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

        response = self.client.get("/api/folders", params=params)
        self._handle_error(response)
        return GetFoldersResponse.model_validate_json(response.content)

    def get_folder(self, uid: str) -> GetFolderResponse:
        """Get a specific folder by UID.

        Args:
            uid: The unique identifier of the folder

        Returns:
            GetFolderResponse: The folder details

        Raises:
            GrafanaApiError: If the request fails or folder doesn't exist
        """
        response = self.client.get(f"/api/folders/{uid}")
        self._handle_error(response)
        return GetFolderResponse.model_validate_json(response.content)

    def update_folder(
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

        response = self.client.put(f"/api/folders/{uid}", json=data)
        self._handle_error(response)
        return UpdateFolderResponse.model_validate_json(response.content)

    def move_folder(
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
        current = self.get_folder(uid)

        # Update folder with new parent
        return self.update_folder(
            uid=uid,
            title=current.title,
            parent_uid=new_parent_uid,
            overwrite=True,
        )

    def search_dashboards(
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
            params["folderUids"] = ",".join(folder_uids)
        if query:
            params["query"] = query
        if tag:
            params["tag"] = tag

        response = self.client.get("/api/search", params=params)
        self._handle_error(response)
        return SearchDashboardsResponse.model_validate_json(response.content)

    def update_dashboard(
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

        response = self.client.post(
            "/api/dashboards/db", json=payload.model_dump(exclude={"dashboard": {"id"}})
        )
        self._handle_error(response)
        return UpdateDashboardResponse.model_validate_json(response.content)

    def delete_dashboard(self, uid: str) -> None:
        """Delete a dashboard in Grafana.

        Args:
            uid: The unique identifier of the dashboard to delete

        Raises:
            GrafanaApiError: If the request fails
        """
        response = self.client.delete(f"/api/dashboards/uid/{uid}")
        self._handle_error(response)

    def get_dashboard(self, uid: str) -> GetDashboardResponse:
        """Get a dashboard by its UID.

        Args:
            uid: The unique identifier of the dashboard

        Returns:
            GetDashboardResponse: The dashboard details including meta information

        Raises:
            GrafanaApiError: If the request fails or dashboard doesn't exist
        """
        response = self.client.get(f"/api/dashboards/uid/{uid}")
        self._handle_error(response)
        return GetDashboardResponse.model_validate_json(response.content)

    def get_reports(self) -> GetReportsResponse:
        """Get all reports.

        Returns:
            GetReportsResponse: List of reports

        Raises:
            GrafanaApiError: If the request fails
        """
        response = self.client.get("/api/reports")
        self._handle_error(response)
        return GetReportsResponse.model_validate_json(response.content)

    def get_report(self, report_id: int) -> GetReportResponse:
        """Get a report by its ID.

        Args:
            report_id: The unique identifier of the report

        Returns:
            GetReportResponse: The report details

        Raises:
            GrafanaApiError: If the request fails
        """
        response = self.client.get(f"/api/reports/{report_id}")
        self._handle_error(response)
        return GetReportResponse.model_validate_json(response.content)

    def create_report(self, report: Report) -> GetReportResponse:
        """Create a new report.

        Args:
            report: The report data

        Returns:
            GetReportResponse: The created report

        Raises:
            GrafanaApiError: If the request fails
        """
        response = self.client.post(
            "/api/reports", json=report.model_dump(exclude={"id"})
        )
        self._handle_error(response)
        return GetReportResponse.model_validate_json(response.content)

    def delete_report(self, report_id: int) -> None:
        """Delete a report.

        Args:
            report_id: The unique identifier of the report

        Raises:
            GrafanaApiError: If the request fails
        """
        response = self.client.delete(f"/api/reports/{report_id}")
        self._handle_error(response)

    def walk(
        self,
        folder_uid: str = FOLDER_GENERAL,
        recursive: bool = False,
        include_dashboards: bool = True,
    ) -> Iterable[tuple[str, GetFoldersResponse, SearchDashboardsResponse]]:
        """Walk through Grafana folder structure, similar to os.walk.

        Args:
            folder_uid: The folder UID to start walking from (default: "general")
            recursive: Whether to recursively walk through subfolders
            include_dashboards: Whether to include dashboards in the results

        Yields:
            Tuple of (folder_uid, subfolders, dashboards)
        """
        logger.debug("fetching folders for folder_uid %s", folder_uid)
        subfolders = self.get_folders(
            parent_uid=folder_uid if folder_uid != FOLDER_GENERAL else None
        )

        if include_dashboards:
            logger.debug("searching dashboards for folder_uid %s", folder_uid)
            dashboards = self.search_dashboards(
                folder_uids=[folder_uid],
                type_="dash-db",
            )
        else:
            dashboards = SearchDashboardsResponse(root=[])

        yield folder_uid, subfolders, dashboards

        if recursive:
            for folder in subfolders.root:
                yield from self.walk(folder.uid, recursive, include_dashboards)
