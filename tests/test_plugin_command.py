from __future__ import annotations

from click.testing import CliRunner

from swirrl.commands.plugin import plugin_command


def test_plugin_allow_adds_distribution(monkeypatch) -> None:
    state = {"allowed": []}
    monkeypatch.setattr("swirrl.commands.plugin._load_allowed", lambda: list(state["allowed"]))
    monkeypatch.setattr(
        "swirrl.commands.plugin._save_allowed",
        lambda values: state.update({"allowed": list(values)}),
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["allow", "swirrl-plugin-demo"])
    assert result.exit_code == 0
    assert state["allowed"] == ["swirrl-plugin-demo"]


def test_plugin_disallow_removes_distribution(monkeypatch) -> None:
    state = {"allowed": ["swirrl-plugin-demo", "other"]}
    monkeypatch.setattr("swirrl.commands.plugin._load_allowed", lambda: list(state["allowed"]))
    monkeypatch.setattr(
        "swirrl.commands.plugin._save_allowed",
        lambda values: state.update({"allowed": list(values)}),
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["disallow", "SWIRRL-plugin-demo"])
    assert result.exit_code == 0
    assert state["allowed"] == ["other"]


def test_plugin_list_displays_status(monkeypatch) -> None:
    monkeypatch.setattr("swirrl.commands.plugin._load_allowed", lambda: ["swirrl-plugin-demo"])
    monkeypatch.setattr(
        "swirrl.core.plugins.list_installed_plugins",
        lambda: [
            {
                "name": "demo",
                "target": "swirrl_plugin_demo:register",
                "distribution": "swirrl-plugin-demo",
                "version": "1.0.0",
            },
            {
                "name": "other",
                "target": "swirrl_plugin_other:register",
                "distribution": "swirrl-plugin-other",
                "version": "1.2.0",
            },
        ],
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["list"])
    assert result.exit_code == 0
    assert "allowed" in result.output
    assert "blocked" in result.output
