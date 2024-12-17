import importlib.resources

import pytest

from grafana_sync.dashboards.models import DashboardData, DSRef

from . import dashboards


def read_db(filename: str) -> DashboardData:
    ref = importlib.resources.files(dashboards) / filename
    with importlib.resources.as_file(ref) as path, open(path, "rb") as f:
        return DashboardData.model_validate_json(f.read())


@pytest.mark.parametrize(
    ("filename", "total_ct", "var_ct"),
    [
        ("haproxy-2-full.json", 310, 310),
        ("host-overview.json", 12, 0),
        ("simple-ds-var.json", 2, 2),
        ("simple-novar.json", 2, 0),
    ],
)
def test_datasource_detection(filename, total_ct, var_ct):
    db = read_db(filename)

    assert db.datasource_count == total_ct
    assert db.variable_datasource_count == var_ct


@pytest.mark.parametrize(
    ("filename", "ct"),
    [
        ("haproxy-2-full.json", 0),
        ("host-overview.json", 0),
        ("simple-ds-var.json", 1),
        ("simple-novar.json", 2),
    ],
)
def test_update_datasources(filename, ct):
    db = read_db(filename)

    assert ct == db.update_datasources(
        {"P1809F7CD0C75ACF3": DSRef(uid="foobar", name="foobar")}
    )
