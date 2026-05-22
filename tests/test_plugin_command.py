from __future__ import annotations

from click.testing import CliRunner

from framekit.commands.plugin import plugin_command


def test_plugin_allow_adds_distribution(monkeypatch) -> None:
    state = {"allowed": []}
    monkeypatch.setattr("framekit.commands.plugin._load_allowed", lambda: list(state["allowed"]))
    monkeypatch.setattr(
        "framekit.commands.plugin._save_allowed",
        lambda values: state.update({"allowed": list(values)}),
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["allow", "framekit-plugin-demo"])
    assert result.exit_code == 0
    assert state["allowed"] == ["framekit-plugin-demo"]


def test_plugin_disallow_removes_distribution(monkeypatch) -> None:
    state = {"allowed": ["framekit-plugin-demo", "other"]}
    monkeypatch.setattr("framekit.commands.plugin._load_allowed", lambda: list(state["allowed"]))
    monkeypatch.setattr(
        "framekit.commands.plugin._save_allowed",
        lambda values: state.update({"allowed": list(values)}),
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["disallow", "FRAMEKIT-plugin-demo"])
    assert result.exit_code == 0
    assert state["allowed"] == ["other"]


def test_plugin_list_displays_status(monkeypatch) -> None:
    monkeypatch.setattr("framekit.commands.plugin._load_allowed", lambda: ["framekit-plugin-demo"])
    monkeypatch.setattr(
        "framekit.core.plugins.list_installed_plugins",
        lambda: [
            {
                "name": "demo",
                "target": "framekit_plugin_demo:register",
                "distribution": "framekit-plugin-demo",
                "version": "1.0.0",
            },
            {
                "name": "other",
                "target": "framekit_plugin_other:register",
                "distribution": "framekit-plugin-other",
                "version": "1.2.0",
            },
        ],
    )

    runner = CliRunner()
    result = runner.invoke(plugin_command, ["list"])
    assert result.exit_code == 0
    assert "allowed" in result.output
    assert "blocked" in result.output
