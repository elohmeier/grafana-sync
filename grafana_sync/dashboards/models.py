from collections.abc import Generator

from pydantic import BaseModel, ConfigDict, Field


class DataSource(BaseModel):
    type_: str = Field(alias="type")
    uid: str

    model_config = ConfigDict(extra="allow")

    @property
    def is_variable(self):
        return self.uid.startswith("${") and self.uid.endswith("}")


class Target(BaseModel):
    datasource: DataSource | None = None

    @property
    def all_datasources(self) -> Generator[DataSource, None, None]:
        if self.datasource is not None:
            yield self.datasource


class Panel(BaseModel):
    datasource: DataSource | None = None
    targets: list[Target] | None = None
    panels: list["Panel"] | None = None

    model_config = ConfigDict(extra="allow")

    @property
    def all_datasources(self) -> Generator[DataSource, None, None]:
        if self.datasource is not None:
            yield self.datasource

        if self.targets is not None:
            for t in self.targets:
                yield from t.all_datasources

        if self.panels is not None:
            for p in self.panels:
                yield from p.all_datasources


class TemplatingItemCurrent(BaseModel):
    text: str | list[str]
    value: str | list[str]


class TemplatingItem(BaseModel):
    current: TemplatingItemCurrent | None = None
    datasource: DataSource | None = None
    type_: str = Field(alias="type")

    model_config = ConfigDict(extra="allow")

    @property
    def all_datasources(self) -> Generator[DataSource, None, None]:
        if self.datasource is not None:
            yield self.datasource


class Templating(BaseModel):
    list_: list[TemplatingItem] | None = Field(alias="list", default=None)

    model_config = ConfigDict(extra="allow")

    @property
    def all_datasources(self) -> Generator[DataSource, None, None]:
        if self.list_ is not None:
            for t in self.list_:
                yield from t.all_datasources


class DashboardData(BaseModel):
    uid: str
    title: str
    version: int | None = None

    panels: list[Panel] | None = None
    templating: Templating | None = None

    model_config = ConfigDict(extra="allow")

    @property
    def all_datasources(self) -> Generator[DataSource, None, None]:
        if self.panels is not None:
            for p in self.panels:
                yield from p.all_datasources

        if self.templating is not None:
            yield from self.templating.all_datasources

    @property
    def datasource_count(self) -> int:
        return len(list(self.all_datasources))

    @property
    def variable_datasource_count(self) -> int:
        return len([ds for ds in self.all_datasources if ds.is_variable])
