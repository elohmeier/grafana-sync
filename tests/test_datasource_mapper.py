from grafana_sync.dashboards.models import (
    DashboardData,
    DataSource,
    DSRef,
    Panel,
    Target,
)


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
