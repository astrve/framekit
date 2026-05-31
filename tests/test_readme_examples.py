from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner

from swirrl.commands.main import cli


def _extract_fk_commands(readme_text: str) -> list[str]:
    pattern = re.compile(r"^\s*swirrl\s+([a-zA-Z0-9_-]+)", re.MULTILINE)
    commands: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(readme_text):
        cmd = match.group(1).strip()
        if not cmd or cmd in seen:
            continue
        seen.add(cmd)
        commands.append(cmd)
    return commands


def test_readme_fk_commands_have_help() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    commands = _extract_fk_commands(readme)
    assert commands

    runner = CliRunner()
    available = set(cli.commands)
    for command in commands:
        if command not in available:
            continue
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0, f"README command failed: swirrl {command} --help"
