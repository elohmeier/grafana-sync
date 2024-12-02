class GrafanaRestoreError(Exception):
    """Base exception for restore operations."""

    pass


class BackupNotFoundError(GrafanaRestoreError):
    """Raised when a backup file is not found."""

    pass
