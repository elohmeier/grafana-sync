import importlib.resources

import pytest

from grafana_sync.api.models import GetDashboardResponse

from . import responses


def read_response(filename: str) -> GetDashboardResponse:
    ref = importlib.resources.files(responses) / filename
    with importlib.resources.as_file(ref) as path, open(path, "rb") as f:
        return GetDashboardResponse.model_validate_json(f.read())


@pytest.mark.parametrize(
    ("filename"),
    [
        ("get-dashboard-response-classic-datasource.json"),
    ],
)
def test_read(filename):
    read_response(filename)
