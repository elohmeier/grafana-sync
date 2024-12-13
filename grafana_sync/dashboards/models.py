from collections.abc import Generator, Mapping

from pydantic import BaseModel, ConfigDict, Field


class DSRef(BaseModel):
    uid: str
    name: str


class DataSource(BaseModel):
    type_: str = Field(alias="type")
    uid: str

    model_config = ConfigDict(extra="allow")

    @property
    def is_variable(self):
        return self.uid.startswith("${") and self.uid.endswith("}")

    def update(self, ds_map: Mapping[str, DSRef]) -> bool:
        if self.is_variable or self.uid not in ds_map:
            return False

        self.uid = ds_map[self.uid].uid
        return True


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

    def update_datasources(self, ds_map: Mapping[str, DSRef]) -> int:
        ct = 0

        for ds in self.all_datasources:
            if ds.update(ds_map):
                ct += 1

        return ct


class TemplatingItemCurrent(BaseModel):
    text: str | list[str]
    value: str | list[str]

    def update_datasource(self, ds_map: Mapping[str, DSRef]) -> bool:
        if not isinstance(self.text, str):
            return False

        if not isinstance(self.value, str):
            return False

        if self.value not in ds_map:
            return False

        self.text = ds_map[self.value].name
        self.value = ds_map[self.value].uid

        return True


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

    def update_datasources(self, ds_map: Mapping[str, DSRef]) -> int:
        if self.list_ is None:
            return 0

        ct = 0

        for t in self.list_:
            if t.type_ != "datasource" or t.current is None:
                continue

            if t.current.update_datasource(ds_map):
                ct += 1

        return ct


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

    def update_datasources(self, ds_map: Mapping[str, DSRef]) -> int:
        ct = 0

        if self.panels is not None:
            for p in self.panels:
                ct += p.update_datasources(ds_map)

        if self.templating is not None:
            ct += self.templating.update_datasources(ds_map)

        return ct
