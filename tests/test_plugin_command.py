from __future__ import annotations

from click.testing import CliRunner

from ouro.commands.plugin import plugin_command


def test_plugin_allow_adds_distribution(monkeypatch) -> None:
    state = {"allowed": []}
    monkeypatch.setattr("ouro.commands.plugin._load_allowed", lambda: list(state["allowed"]))
    monkeypatch.setattr(
        "ouro.commands.plugin._save_allowed",
        lambda values: state.update({"allowed": list(values)}),
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["allow", "ouro-plugin-demo"])
    assert result.exit_code == 0
    assert state["allowed"] == ["ouro-plugin-demo"]


def test_plugin_disallow_removes_distribution(monkeypatch) -> None:
    state = {"allowed": ["ouro-plugin-demo", "other"]}
    monkeypatch.setattr("ouro.commands.plugin._load_allowed", lambda: list(state["allowed"]))
    monkeypatch.setattr(
        "ouro.commands.plugin._save_allowed",
        lambda values: state.update({"allowed": list(values)}),
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["disallow", "OURO-plugin-demo"])
    assert result.exit_code == 0
    assert state["allowed"] == ["other"]


def test_plugin_list_displays_status(monkeypatch) -> None:
    monkeypatch.setattr("ouro.commands.plugin._load_allowed", lambda: ["ouro-plugin-demo"])
    monkeypatch.setattr(
        "ouro.core.plugins.list_installed_plugins",
        lambda: [
            {
                "name": "demo",
                "target": "ouro_plugin_demo:register",
                "distribution": "ouro-plugin-demo",
                "version": "1.0.0",
            },
            {
                "name": "other",
                "target": "ouro_plugin_other:register",
                "distribution": "ouro-plugin-other",
                "version": "1.2.0",
            },
        ],
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["list"])
    assert result.exit_code == 0
    assert "allowed" in result.output
    assert "blocked" in result.output
