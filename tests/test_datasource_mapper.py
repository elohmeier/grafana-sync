import importlib.resources

import pytest

from grafana_sync.api.models import GetDashboardResponse
from grafana_sync.dashboards.models import (
    DashboardData,
    DataSource,
    DSRef,
    Panel,
    Target,
)

from . import dashboards, responses


def read_db(filename: str) -> DashboardData:
    ref = importlib.resources.files(dashboards) / filename
    with importlib.resources.as_file(ref) as path, open(path, "rb") as f:
        return DashboardData.model_validate_json(f.read())


def read_response(filename: str) -> GetDashboardResponse:
    ref = importlib.resources.files(responses) / filename
    with importlib.resources.as_file(ref) as path, open(path, "rb") as f:
        return GetDashboardResponse.model_validate_json(f.read())


def test_ds_inheritance():
    db = DashboardData(
        uid="test",
        title="test",
        panels=[
            Panel(
                datasource=DataSource(
                    type="influxdb",
                    uid="orig-uid",
                ),
                targets=[
                    Target(
                        datasource=DataSource(uid="${DataSource}"),
                    )
                ],
            )
        ],
    )

    db.update_datasources({"orig-uid": DSRef(uid="new-uid", name="InfluxDB")})

    assert db == DashboardData(
        uid="test",
        title="test",
        panels=[
            Panel(
                datasource=DataSource(
                    type="influxdb",
                    uid="new-uid",
                ),
                targets=[
                    Target(
                        datasource=DataSource(uid="${DataSource}"),
                    )
                ],
            )
        ],
    )


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


@pytest.mark.parametrize(
    ("filename", "ct"),
    [
        ("get-dashboard-datasource-string.json", 1),
        ("get-dashboard-panel-target.json", 1),
    ],
)
def test_update_classic_datasource_from_response(filename, ct):
    res = read_response(filename)
    db = res.dashboard

    ds_config = {
        "InfluxDB Produktion Telegraf": DataSource(
            type="influxdb", uid="influxdb-prod-telegraf"
        )
    }

    db.upgrade_datasources(ds_config)

    assert ct == db.update_datasources(
        {
            "influxdb-prod-telegraf": DSRef(uid="foobar", name="foobar"),
            "influx": DSRef(uid="foobar", name="foobar"),
        }
    )
