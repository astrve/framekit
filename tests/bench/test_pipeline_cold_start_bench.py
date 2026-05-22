from __future__ import annotations

import pytest

pytestmark = pytest.mark.benchmark


def test_bench_cli_help_render(benchmark) -> None:
    from click.testing import CliRunner

    from framekit.commands.main import cli

    runner = CliRunner()

    def _invoke() -> int:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        return len(result.output)

    benchmark(_invoke)
