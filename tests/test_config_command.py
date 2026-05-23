from __future__ import annotations

from click.testing import CliRunner

from framekit.commands.main import cli


def test_config_explain_masks_secret_values(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "framekit.yaml"
    settings_file.write_text(
        "metadata:\n  tmdb_read_access_token: secret-token\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FRAMEKIT_CONFIG", str(settings_file))

    result = CliRunner().invoke(cli, ["config", "explain", "metadata"])

    assert result.exit_code == 0
    assert "secret-token" not in result.output
    assert "********" in result.output


def test_config_doctor_reports_invalid_module_yaml(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "framekit.yaml"
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    settings_file.write_text("general:\n  locale: en\n", encoding="utf-8")
    (modules_dir / "renamer.yaml").write_text("default_language_tag: [", encoding="utf-8")
    monkeypatch.setenv("FRAMEKIT_CONFIG", str(settings_file))

    result = CliRunner().invoke(cli, ["config", "doctor", "renamer"])

    assert result.exit_code == 1
    assert "renamer.yaml" in result.output
