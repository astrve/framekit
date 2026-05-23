from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from rich import box
from rich.table import Table

from framekit.core.exceptions import SettingsError
from framekit.core.paths import get_cache_dir, get_config_dir
from framekit.core.settings import SettingsStore, redact_settings, validate_settings
from framekit.ui.branding import print_module_banner
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_success, print_warning


def _select_module(settings: dict[str, Any], module: str | None) -> Any:
    if not module:
        return settings
    key = module.strip().lower()
    if key in settings.get("modules", {}):
        return settings["modules"][key]
    return settings.get(key, {})


def _module_file(store: SettingsStore, module: str) -> Path:
    return store.module_config_dir() / f"{module}.yaml"


def _known_module_names(settings: dict[str, Any]) -> list[str]:
    names = set(settings.get("modules", {}).keys())
    names.update(name for name in ("upload", "seedbox", "watch") if name in settings)
    return sorted(names)


def run_config_explain(module: str | None, *, json_output: bool = False) -> int:
    """Show resolved configuration for all settings or one module."""
    store = SettingsStore()
    settings = store.load()
    selected = redact_settings(_select_module(settings, module))
    payload = {
        "settings_file": str(store.path),
        "config_dir": str(get_config_dir()),
        "cache_dir": str(get_cache_dir()),
        "module_dir": str(store.module_config_dir()),
        "module": module or "all",
        "module_file": str(_module_file(store, module)) if module else "",
        "settings": selected,
    }
    if json_output:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return 0

    print_module_banner("Config")
    table = Table(title="Resolved configuration", box=box.HEAVY, expand=True)
    table.add_column("Field", width=20, no_wrap=True)
    table.add_column("Value", ratio=1, overflow="fold")
    for key in ("settings_file", "config_dir", "cache_dir", "module_dir", "module_file"):
        value = payload[key]
        if value:
            table.add_row(key, value)
    table.add_row("module", payload["module"])
    console.print(table)
    console.print_json(json.dumps(selected, indent=2, ensure_ascii=False))
    return 0


def _validate_yaml_file(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return f"{path}: invalid YAML ({exc.__class__.__name__})"
    except OSError as exc:
        return f"{path}: unreadable ({exc})"
    if data is not None and not isinstance(data, dict):
        return f"{path}: YAML root must be an object"
    return None


def run_config_doctor(module: str | None) -> int:
    """Validate main settings and optional module YAML files."""
    store = SettingsStore()
    errors: list[str] = []
    warnings: list[str] = []

    for path in [store.path, *sorted(store.module_config_dir().glob("*.yaml"))]:
        error = _validate_yaml_file(path)
        if error:
            errors.append(error)

    try:
        settings = store.load()
        validate_settings(settings)
    except SettingsError as exc:
        errors.append(str(exc))
        settings = {}

    if module and settings:
        known = _known_module_names(settings)
        if module not in known:
            warnings.append(f"Unknown module: {module}")
        module_path = _module_file(store, module)
        if not module_path.exists():
            warnings.append(f"No module override file: {module_path}")

    print_module_banner("Config Doctor")
    if errors:
        for error in errors:
            print_error(error)
        return 1
    for warning in warnings:
        print_warning(warning)
    print_success("Configuration valid.")
    return 0


@click.group(name="config", help="Explain and validate Framekit configuration.")
def config_group() -> None:
    """Framekit config commands."""


@config_group.command("explain", help="Show resolved configuration with secrets masked.")
@click.argument("module", required=False)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON.")
@click.pass_context
def config_explain_command(ctx: click.Context, module: str | None, json_output: bool) -> None:
    """Handle config explain command."""
    ctx.exit(run_config_explain(module, json_output=json_output))


@config_group.command("doctor", help="Validate configuration and optional module YAML.")
@click.argument("module", required=False)
@click.pass_context
def config_doctor_command(ctx: click.Context, module: str | None) -> None:
    """Handle config doctor command."""
    ctx.exit(run_config_doctor(module))
