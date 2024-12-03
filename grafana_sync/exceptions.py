from typing import TYPE_CHECKING

from grafana_sync.api.models import GrafanaErrorResponse

if TYPE_CHECKING:
    from httpx import Response


class GrafanaNotPristineError(Exception):
    """Base exception for when Grafana instance is not in a pristine state."""


class ExistingFoldersError(GrafanaNotPristineError):
    """Raised when Grafana instance has existing folders."""

    def __init__(self, folder_count: int):
        self.folder_count = folder_count
        message = f"Grafana instance has {folder_count} existing folder(s)"
        super().__init__(message)


class ExistingDashboardsError(GrafanaNotPristineError):
    """Raised when Grafana instance has existing dashboards."""

    def __init__(self, dashboard_count: int):
        self.dashboard_count = dashboard_count
        message = f"Grafana instance has {dashboard_count} existing dashboard(s)"
        super().__init__(message)


class GrafanaRestoreError(Exception):
    """Base exception for restore operations."""

    pass


class BackupNotFoundError(GrafanaRestoreError):
    """Raised when a backup file is not found."""

    pass


class GrafanaApiError(Exception):
    """Custom exception for Grafana API errors that includes the response details."""

    def __init__(self, response: "Response", message: str | None = None):
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
