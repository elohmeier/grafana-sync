from asyncclick.testing import CliRunner

from grafana_sync.cli import cli


async def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = await runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert result.output.startswith("cli, version ")
