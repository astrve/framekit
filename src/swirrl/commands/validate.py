"""Release validation command."""

from __future__ import annotations

import json
from pathlib import Path

from swirrl.core.i18n import tr
from swirrl.modules.validate.rules import BUILTIN_RULESETS
from swirrl.modules.validate.service import (
    ValidationResult,
    ValidationService,
    ValidationSeverity,
)
from swirrl.ui.click_helper import click
from swirrl.ui.console import console, print_error, print_info, print_success


def _severity_style(severity: ValidationSeverity) -> str:
    if severity == ValidationSeverity.ERROR:
        return "bold red"
    elif severity == ValidationSeverity.WARNING:
        return "yellow"
    return "dim"


def _print_result(result: ValidationResult) -> None:
    """Print validation results as a rich table."""
    from rich.table import Table

    if not result.issues and result.is_valid:
        print_success(
            f"Release '{result.release_name}' passed all checks ({result.checks_passed} passed)"
        )
        return

    table = Table(title=f"Validation: {result.release_name}", show_lines=False)
    table.add_column("Severity", width=8)
    table.add_column("Category", width=12)
    table.add_column("Issue")
    table.add_column("Suggestion", style="dim")

    for issue in result.issues:
        sev_text = issue.severity.value.upper()
        style = _severity_style(issue.severity)
        table.add_row(
            f"[{style}]{sev_text}[/]",
            issue.category,
            issue.message,
            issue.suggestion,
        )

    console.print(table)
    console.print()

    if result.is_valid:
        print_success(f"Passed: {result.checks_passed} | Warnings: {result.checks_warned}")
    else:
        print_error(
            f"Failed: {result.checks_failed} | Warnings: {result.checks_warned} "
            f"| Passed: {result.checks_passed}"
        )


@click.command("validate")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--ruleset",
    "-r",
    type=click.Choice(list(BUILTIN_RULESETS.keys())),
    default="default",
    help="Validation ruleset to use.",
)
@click.option("--strict", is_flag=True, help="Use strict validation rules.")
@click.option(
    "--require-nfo/--no-require-nfo",
    default=None,
    help="Override NFO requirement.",
)
@click.option(
    "--require-subs/--no-require-subs",
    default=None,
    help="Override subtitle requirement.",
)
@click.option("--min-resolution", type=int, default=None, help="Minimum video width in pixels.")
@click.option("--max-size-gb", type=float, default=None, help="Maximum file size in GB.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output structured JSON to stdout instead of a table.")
def validate_command(
    path: str,
    ruleset: str,
    strict: bool,
    require_nfo: bool | None,
    require_subs: bool | None,
    min_resolution: int | None,
    max_size_gb: float | None,
    json_output: bool,
) -> None:
    r"""Validate a release folder against tracker requirements.

    Checks media files for codec compatibility, quality, naming,
    and required sidecars (NFO, subtitles) before uploading.

    \b
    Examples:
        swirrl validate "Release folder"
        swirrl validate "Release folder" --ruleset strict
        swirrl validate "Release folder" --min-resolution 1920 --require-subs
        swirrl validate "Release folder" --json
    """
    if strict:
        rules = BUILTIN_RULESETS["strict"]
    else:
        rules = BUILTIN_RULESETS.get(ruleset, BUILTIN_RULESETS["default"])

    if require_nfo is not None:
        rules.require_nfo = require_nfo
    if require_subs is not None:
        rules.require_subs = require_subs
    if min_resolution is not None:
        rules.min_resolution_width = min_resolution
    if max_size_gb is not None:
        rules.max_file_size_gb = max_size_gb

    release_path = Path(path)
    if not json_output:
        print_info(tr("validate.start", default=f"Validating: {release_path.name}"))

    service = ValidationService(rules=rules)
    result = service.validate(release_path)

    if json_output:
        payload = {
            "release_name": result.release_name,
            "is_valid": result.is_valid,
            "checks_passed": result.checks_passed,
            "checks_warned": result.checks_warned,
            "checks_failed": result.checks_failed,
            "issues": [
                {
                    "severity": issue.severity.value,
                    "category": issue.category,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                }
                for issue in result.issues
            ],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        _print_result(result)

    if not result.is_valid:
        return 1
