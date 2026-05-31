"""Tests for the ``swirrl.modules`` plugin discovery layer.

The plugin loader is best-effort and runs at CLI startup. It must:

* Register plugins whose entry-point callable succeeds.
* Skip plugins whose entry-point cannot be imported, without raising.
* Skip plugins whose ``register`` callable raises, without raising.
* Tolerate the absence of any installed plugin (empty environment).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import click

from swirrl.core import plugins as plugin_module


def _entry_point(name: str, target_callable: Any) -> MagicMock:
    """Build an ``EntryPoint``-shaped mock."""
    ep = MagicMock()
    ep.name = name
    ep.value = f"mock_module:{name}"
    ep.load.return_value = target_callable
    return ep


def test_load_plugins_registers_each_entry_point() -> None:
    """A well-behaved plugin must have its register() called with the CLI."""
    cli = click.Group(name="test-cli")
    captured: dict[str, click.Group | None] = {"cli": None}

    def register(cli_arg: click.Group) -> None:
        captured["cli"] = cli_arg
        cli_arg.add_command(click.Command(name="hello"))

    ep = _entry_point("hello-plugin", register)
    with (
        patch.object(plugin_module, "iter_plugin_entry_points", return_value=[ep]),
        patch.object(plugin_module, "_load_allowed_distributions", return_value={"hello-plugin"}),
    ):
        loaded = plugin_module.load_plugins(cli)

    assert loaded == ["hello-plugin"]
    assert captured["cli"] is cli
    assert "hello" in cli.commands


def test_load_plugins_skips_failing_import() -> None:
    """When entry_point.load() raises, the plugin is skipped, not propagated."""
    cli = click.Group(name="test-cli")
    bad_ep = MagicMock()
    bad_ep.name = "broken-plugin"
    bad_ep.value = "broken:register"
    bad_ep.load.side_effect = ImportError("no such module")

    good_ep = _entry_point("ok-plugin", lambda c: c.add_command(click.Command("ok")))

    with (
        patch.object(plugin_module, "iter_plugin_entry_points", return_value=[bad_ep, good_ep]),
        patch.object(
            plugin_module,
            "_load_allowed_distributions",
            return_value={"broken-plugin", "ok-plugin"},
        ),
    ):
        loaded = plugin_module.load_plugins(cli)

    assert loaded == ["ok-plugin"]
    assert "ok" in cli.commands


def test_load_plugins_skips_non_callable_target() -> None:
    """``register`` must be callable — a stringified target is silently skipped."""
    cli = click.Group(name="test-cli")
    not_callable = _entry_point("nope", "not-a-callable")  # type: ignore[arg-type]

    with (
        patch.object(plugin_module, "iter_plugin_entry_points", return_value=[not_callable]),
        patch.object(plugin_module, "_load_allowed_distributions", return_value={"nope"}),
    ):
        loaded = plugin_module.load_plugins(cli)

    assert loaded == []


def test_load_plugins_swallows_register_exceptions() -> None:
    """A plugin whose ``register()`` raises must not break the host CLI."""
    cli = click.Group(name="test-cli")

    def bad_register(_cli: click.Group) -> None:
        raise RuntimeError("plugin author bug")

    ep = _entry_point("self-destructing", bad_register)
    with (
        patch.object(plugin_module, "iter_plugin_entry_points", return_value=[ep]),
        patch.object(
            plugin_module, "_load_allowed_distributions", return_value={"self-destructing"}
        ),
    ):
        loaded = plugin_module.load_plugins(cli)

    assert loaded == []
    # CLI remains usable — nothing got added, nothing got removed.
    assert cli.commands == {}


def test_load_plugins_no_entry_points_returns_empty() -> None:
    """An environment with no plugins must yield an empty list, not raise."""
    cli = click.Group(name="test-cli")
    with (
        patch.object(plugin_module, "iter_plugin_entry_points", return_value=[]),
        patch.object(plugin_module, "_load_allowed_distributions", return_value=set()),
    ):
        assert plugin_module.load_plugins(cli) == []


def test_load_plugins_blocks_non_allowlisted_distribution() -> None:
    """Plugins are skipped when distribution/name is not allowlisted."""
    cli = click.Group(name="test-cli")
    ep = _entry_point("hello-plugin", lambda c: c.add_command(click.Command(name="hello")))
    with (
        patch.object(plugin_module, "iter_plugin_entry_points", return_value=[ep]),
        patch.object(plugin_module, "_load_allowed_distributions", return_value=set()),
    ):
        loaded = plugin_module.load_plugins(cli)
    assert loaded == []
    assert "hello" not in cli.commands


def test_list_installed_plugins_returns_metadata_rows() -> None:
    """``list_installed_plugins`` exposes name + target + dist info."""
    fake_dist = MagicMock(name="dist")
    fake_dist.name = "swirrl-plugin-demo"
    fake_dist.version = "1.2.3"
    ep = MagicMock()
    ep.name = "demo"
    ep.value = "swirrl_plugin_demo:register"
    ep.dist = fake_dist

    with patch.object(plugin_module, "iter_plugin_entry_points", return_value=[ep]):
        rows = plugin_module.list_installed_plugins()

    assert rows == [
        {
            "name": "demo",
            "target": "swirrl_plugin_demo:register",
            "distribution": "swirrl-plugin-demo",
            "version": "1.2.3",
        }
    ]


def test_entry_point_group_constant() -> None:
    """The public group name must stay stable for third-party packagers."""
    assert plugin_module.ENTRY_POINT_GROUP == "swirrl.modules"
