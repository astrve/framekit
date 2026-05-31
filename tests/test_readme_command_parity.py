from __future__ import annotations

from pathlib import Path

from swirrl.commands.main import cli


def test_readme_command_table_matches_cli_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    table_commands: set[str] = set()
    in_command_table = False
    for line in readme.splitlines():
        stripped = line.strip()
        if stripped == "| Command | Alias(es) | Description |":
            in_command_table = True
            continue
        if in_command_table and not stripped.startswith("|"):
            in_command_table = False
            continue
        if not in_command_table or not (stripped.startswith("| `") and "` |" in stripped):
            continue
        try:
            command = stripped.split("`", 2)[1]
        except Exception:
            continue
        if command:
            table_commands.add(command)

    assert table_commands, "README command table appears empty"
    missing = sorted(command for command in table_commands if command not in cli.commands)
    assert missing == [], f"README commands missing from CLI: {missing}"


def test_readme_contains_no_backup_command_mentions() -> None:
    readme = Path("README.md").read_text(encoding="utf-8").lower()
    assert "swirrl backup" not in readme
    assert "swirrl backup" not in readme
