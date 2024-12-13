import importlib.resources

import pytest

from grafana_sync.dashboards.models import DashboardData

from . import dashboards


@pytest.mark.parametrize(
    ("filename", "total_ct", "var_ct"),
    [
        ("haproxy-2-full.json", 310, 310),
        ("simple-ds-var.json", 2, 2),
        ("simple-novar.json", 2, 0),
    ],
)
def test_datasource_detection(filename, total_ct, var_ct):
    ref = importlib.resources.files(dashboards) / filename
    with importlib.resources.as_file(ref) as path, open(path, "rb") as f:
        db = DashboardData.model_validate_json(f.read())

    assert db.datasource_count == total_ct
    assert db.variable_datasource_count == var_ct
