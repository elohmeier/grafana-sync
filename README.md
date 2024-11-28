# grafana-sync

[![PyPI](https://img.shields.io/pypi/v/grafana-sync.svg)](https://pypi.org/project/grafana-sync/)
[![Changelog](https://img.shields.io/github/v/release/elohmeier/grafana-sync?include_prereleases&label=changelog)](https://github.com/elohmeier/grafana-sync/releases)
[![Tests](https://github.com/elohmeier/grafana-sync/actions/workflows/test.yml/badge.svg)](https://github.com/elohmeier/grafana-sync/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/elohmeier/grafana-sync/blob/master/LICENSE)

Sync Grafana dashboards and folders

## Installation

Install this tool using `pip`:
```bash
pip install grafana-sync
```
## Usage

For help, run:
```bash
grafana-sync --help
```
You can also use:
```bash
python -m grafana_sync --help
```
## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:
```bash
cd grafana-sync
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
python -m pytest
```
