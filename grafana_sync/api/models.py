from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from grafana_sync.dashboards.models import DashboardData, DSRef


class CreateFolderResponse(BaseModel):
    """Response model for folder creation API."""

    uid: str
    title: str
    url: str
    version: int
    parent_uid: str | None = Field(alias="parentUid", default=None)


class GetFoldersResponseItem(BaseModel):
    """Model for individual folder items in get_folders response."""

    uid: str
    title: str
    parent_uid: str | None = Field(alias="parentUid", default=None)


class GetFoldersResponse(RootModel):
    """Response model for get_folders API."""

    root: list[GetFoldersResponseItem]


class GetFolderResponse(BaseModel):
    """Response model for get_folder API."""

    uid: str
    title: str
    url: str
    parent_uid: str | None = Field(alias="parentUid", default=None)


class DatasourceDefinition(BaseModel):
    uid: str
    name: str
    type_: str = Field(alias="type")
    access: str

    # datasource specific optional fields
    url: str | None = None
    user: str | None = None
    database: str | None = None
    json_data: Mapping[str, Any] | None = Field(alias="jsonData", default=None)

    model_config = ConfigDict(extra="allow")

    @property
    def ref(self) -> DSRef:
        return DSRef(uid=self.uid, name=self.name)


class GetDatasourcesResponse(RootModel):
    root: list[DatasourceDefinition]


class CreateDatasourceResponse(BaseModel):
    datasource: DatasourceDefinition

    id: int
    message: str
    name: str


class SearchDashboardsResponseItem(BaseModel):
    """Model for individual dashboard items in search response."""

    uid: str
    title: str
    uri: str
    url: str
    type_: str = Field(alias="type")
    tags: list[str]
    slug: str
    folder_uid: str | None = Field(alias="folderUid", default=None)
    folder_title: str | None = Field(alias="folderTitle", default=None)


class SearchDashboardsResponse(RootModel):
    """Response model for dashboard search API."""

    root: list[SearchDashboardsResponseItem]


class UpdateDashboardRequest(BaseModel):
    dashboard: DashboardData
    folder_uid: str | None = Field(alias="folderUid", default=None)
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
    folder_uid: str = Field(alias="folderUid")

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
    parent_uid: str | None = Field(alias="parentUid", default=None)
