from collections.abc import Mapping, Sequence

from grafana_sync.api.models import DatasourceDefinition
from grafana_sync.dashboards.models import DSRef
from grafana_sync.exceptions import UnsupportedDatasourceTypeError


def ds_matches(ds_a: DatasourceDefinition, ds_b) -> bool:
    if ds_a.type_ != ds_b.type_:
        return False

    if ds_a.access != ds_b.access:
        return False

    # accept direct matches
    if ds_a.uid == ds_b.uid:
        return True

    if ds_a.type_ == "prometheus":
        if ds_a.url == ds_b.url:
            return True
    elif ds_a.type_ == "influxdb":
        if (
            ds_a.url == ds_b.url
            and ds_a.user == ds_b.user
            and ds_a.database == ds_b.database
        ):
            return True
    elif ds_a.type_ == "mssql":
        if (
            ds_a.user == ds_b.user
            and ds_a.url == ds_b.url
            and ds_a.json_data is not None
            and ds_b.json_data is not None
            and ds_a.json_data["database"] == ds_b.json_data["database"]
        ):
            return True
    else:
        raise UnsupportedDatasourceTypeError(ds_a.type_)

    return False


def map_datasources(
    src: Sequence[DatasourceDefinition],
    dst: Sequence[DatasourceDefinition],
) -> Mapping[str, DSRef]:
    ds_map: dict[str, DSRef] = {}
    for src_ds in src:
        for dst_ds in dst:
            if ds_matches(src_ds, dst_ds):
                ds_map[src_ds.uid] = dst_ds.ref
                break

    return ds_map
