from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from ouro.commands.main import cli


def test_pipeline_auto_mode_headless_smoke(tmp_path: Path) -> None:
    source = tmp_path / "release"
    source.mkdir()
    (source / "sample.mkv").write_bytes(b"\x00")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["pipeline", str(source), "--auto", "--dry-run", "--modules", "renamer"],
    )
    assert result.exit_code == 0
