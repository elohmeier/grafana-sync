import importlib.resources

import pytest

from grafana_sync.dashboards.models import DashboardData

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


def test_parse_empty_template_current():
    DashboardData.model_validate(
        {
            "templating": {"list": [{"current": {}, "type": "interval"}]},
            "uid": "dashboard",
            "title": "My Dashboard",
        }
    )
