from pydantic import BaseModel, ConfigDict, Field, RootModel


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


class GetReportResponse(BaseModel):
    """Response model for single report API."""

    id: int
    name: str

    model_config = ConfigDict(extra="allow")


class CreateReportResponse(BaseModel):
    id: int
    message: str


class GetReportsResponse(RootModel):
    """Response model for reports list API."""

    root: list[GetReportResponse]


class UpdateFolderResponse(BaseModel):
    """Response model for folder update API."""

    uid: str
    title: str
    url: str
    version: int
    parentUid: str | None = None


class GrafanaErrorResponse(BaseModel):
    """Model for Grafana API error responses."""

    message: str
    status: str | None = None
