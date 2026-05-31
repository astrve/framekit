from __future__ import annotations

from swirrl.core.settings import SettingsStore
from swirrl.ui.click_helper import click
from swirrl.ui.console import print_error, print_info, print_success


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _load_allowed() -> list[str]:
    store = SettingsStore()
    settings = store.load()
    plugins = settings.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        settings["plugins"] = {"allowed": []}
        store.save(settings)
        return []
    allowed = plugins.get("allowed", [])
    if not isinstance(allowed, list):
        plugins["allowed"] = []
        store.save(settings)
        return []
    return [str(item).strip() for item in allowed if str(item).strip()]


def _save_allowed(allowed: list[str]) -> None:
    store = SettingsStore()
    settings = store.load()
    plugins = settings.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        settings["plugins"] = plugins
    plugins["allowed"] = allowed
    store.save(settings)


def _discover_installed_plugins() -> list[dict[str, object]]:
    try:
        from swirrl.core.plugins import list_installed_plugins
    except Exception as exc:
        print_error(f"Could not inspect installed plugins: {exc}")
        return []
    return list_installed_plugins()


def _render_plugin_row(row: dict[str, object], allowed: set[str]) -> str:
    dist = _clean_text(row.get("distribution"))
    name = _clean_text(row.get("name"))
    version = _clean_text(row.get("version"))
    key = (dist or name).lower()
    status = "allowed" if key in allowed else "blocked"
    return f"- {name} | dist={dist or '<unknown>'} | version={version or '?'} | {status}"


@click.group("plugin")
def plugin_command() -> None:
    """Manage third-party plugin allowlist."""


@plugin_command.command("list")
def plugin_list_command() -> None:
    """List installed plugins and allowlist status."""
    allowed = {item.lower() for item in _load_allowed()}
    rows = _discover_installed_plugins()
    if not rows:
        print_info("No installed swirrl.modules plugins discovered.")
        return

    for row in rows:
        print_info(_render_plugin_row(row, allowed))


@plugin_command.command("allow")
@click.argument("distribution")
def plugin_allow_command(distribution: str) -> None:
    """Allow a plugin distribution to load on startup."""
    value = distribution.strip()
    if not value:
        print_error("Distribution name cannot be empty.")
        return
    allowed = _load_allowed()
    keys = {item.lower() for item in allowed}
    if value.lower() in keys:
        print_info(f"Already allowed: {value}")
        return
    allowed.append(value)
    _save_allowed(allowed)
    print_success(f"Allowed plugin distribution: {value}")


@plugin_command.command("disallow")
@click.argument("distribution")
def plugin_disallow_command(distribution: str) -> None:
    """Remove a plugin distribution from allowlist."""
    value = distribution.strip()
    if not value:
        print_error("Distribution name cannot be empty.")
        return
    allowed = _load_allowed()
    next_allowed = [item for item in allowed if item.lower() != value.lower()]
    if len(next_allowed) == len(allowed):
        print_info(f"Not in allowlist: {value}")
        return
    _save_allowed(next_allowed)
    print_success(f"Disallowed plugin distribution: {value}")
