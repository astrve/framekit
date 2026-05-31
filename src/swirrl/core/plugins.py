"""Third-party plugin discovery via ``importlib.metadata`` entry-points.

Swirrl exposes a public extension point named ``swirrl.modules``. Any
installed Python distribution that declares an entry-point under this group
can contribute a new CLI subcommand without forking Swirrl:

```toml
# pyproject.toml of a third-party package, e.g. ``swirrl-plugin-anilist``
[project.entry-points."swirrl.modules"]
anilist = "swirrl_plugin_anilist:register"
```

The referenced callable receives the Click root group at startup and is
expected to register one or more commands on it::

    def register(cli):
        cli.add_command(anilist_command, "anilist")

The loader is best-effort: a misbehaving plugin must never break the host
CLI. Failures are logged and the plugin is skipped.
"""

from __future__ import annotations

from importlib import metadata as importlib_metadata
from typing import TYPE_CHECKING, Any, Protocol

from loguru import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    import click


ENTRY_POINT_GROUP = "swirrl.modules"


class _RegisterCallable(Protocol):  # pyright: ignore[reportUnusedClass]  # Protocol used as a type marker for plugin entry-points; not referenced at runtime.
    """Signature plugin ``register`` callables must implement."""

    def __call__(self, cli: click.Group, /) -> None: ...  # pragma: no cover - protocol stub


def _load_allowed_distributions() -> set[str]:
    """Return lowercase allowlist from settings."""
    try:
        from swirrl.core.settings import SettingsStore

        settings = SettingsStore().load()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"Could not load plugin allowlist from settings: {exc}")
        return set()

    plugins = settings.get("plugins", {})
    if not isinstance(plugins, dict):
        return set()
    raw_allowed = plugins.get("allowed", [])
    if not isinstance(raw_allowed, list):
        return set()
    return {str(item).strip().lower() for item in raw_allowed if str(item).strip()}


def iter_plugin_entry_points() -> list[importlib_metadata.EntryPoint]:
    """Return every entry-point declared under ``swirrl.modules``.

    Wrapped to keep ``importlib.metadata`` quirks (Python <3.10 vs >=3.10
    APIs) inside one place. Returns an empty list when nothing is installed,
    never raises.
    """
    try:
        eps = importlib_metadata.entry_points()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"Could not enumerate entry-points: {exc}")
        return []

    # Python 3.10+: ``EntryPoints`` with ``.select(group=...)``.
    if hasattr(eps, "select"):
        try:
            return list(eps.select(group=ENTRY_POINT_GROUP))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"entry_points().select failed: {exc}")
            return []

    # Older API: dict mapping group → list[EntryPoint].
    return list(eps.get(ENTRY_POINT_GROUP, []))  # type: ignore[union-attr]


def load_plugins(cli: click.Group) -> list[str]:
    """Discover and register every ``swirrl.modules`` plugin on ``cli``.

    Returns the list of successfully loaded plugin names. Logs and skips
    every plugin whose entry-point fails to import or whose ``register``
    callable raises — the host CLI must remain usable even when a plugin
    misbehaves.

    Args:
        cli: The Click root group exposed by ``swirrl.commands.main``.

    Returns:
        List of plugin names (the entry-point name, not the distribution).
    """
    allowed_distributions = _load_allowed_distributions()
    loaded: list[str] = []
    for entry_point in iter_plugin_entry_points():
        name = entry_point.name
        dist = getattr(entry_point, "dist", None)
        raw_dist_name = getattr(dist, "name", None) if dist is not None else None
        dist_name = raw_dist_name.strip() if isinstance(raw_dist_name, str) else ""
        dist_key = dist_name.lower()
        name_key = name.strip().lower()
        if dist_name:
            is_allowed = dist_key in allowed_distributions
        else:
            # Fallback for older metadata backends that do not expose ``dist``.
            is_allowed = name_key in allowed_distributions
        if not is_allowed:
            logger.info(
                f"Skipping swirrl plugin {name!r} from distribution "
                f"{(dist_name or '<unknown>')!r}: not in plugins.allowed"
            )
            continue
        try:
            register = entry_point.load()
        except Exception as exc:
            logger.warning(
                f"Skipping swirrl plugin {name!r}: failed to import "
                f"({exc.__class__.__name__}: {exc})"
            )
            continue

        if not callable(register):
            logger.warning(
                f"Skipping swirrl plugin {name!r}: entry-point target "
                f"{register!r} is not callable"
            )
            continue

        try:
            register(cli)
        except Exception as exc:
            logger.warning(
                f"Skipping swirrl plugin {name!r}: register() raised "
                f"({exc.__class__.__name__}: {exc})"
            )
            continue

        loaded.append(name)
        logger.debug(f"Loaded swirrl plugin: {name}")

    return loaded


def list_installed_plugins() -> list[dict[str, Any]]:
    """Return metadata for every installed plugin, without loading them.

    Useful for ``swirrl doctor`` or a future ``swirrl plugins`` listing.
    Each entry contains the plugin ``name``, the dotted ``target`` and the
    distribution name + version when resolvable.
    """
    rows: list[dict[str, Any]] = []
    for entry_point in iter_plugin_entry_points():
        dist = getattr(entry_point, "dist", None)
        dist_name = getattr(dist, "name", None) if dist else None
        dist_version = getattr(dist, "version", None) if dist else None
        rows.append(
            {
                "name": entry_point.name,
                "target": entry_point.value,
                "distribution": dist_name,
                "version": dist_version,
            }
        )
    return rows


__all__ = [
    "ENTRY_POINT_GROUP",
    "iter_plugin_entry_points",
    "list_installed_plugins",
    "load_plugins",
]
