from __future__ import annotations

from pathlib import Path


def _patch_platform_dirs(monkeypatch, *, config_dir: Path, cache_dir: Path) -> None:
    from ouro.core import paths

    monkeypatch.setattr(paths, "user_config_dir", lambda *_args: str(config_dir))
    monkeypatch.setattr(paths, "user_cache_dir", lambda *_args: str(cache_dir))


def test_settings_store_uses_user_config_when_no_project_file(tmp_path, monkeypatch) -> None:
    from ouro.core.settings import SettingsStore

    workspace = tmp_path / "release"
    config_dir = tmp_path / "user-config"
    cache_dir = tmp_path / "user-cache"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.delenv("OURO_CONFIG", raising=False)
    _patch_platform_dirs(monkeypatch, config_dir=config_dir, cache_dir=cache_dir)

    store = SettingsStore()
    store.load()

    assert store.path == config_dir / "ouro.yaml"
    assert store.path.exists()
    assert not (workspace / "ouro.yaml").exists()


def test_existing_project_settings_file_wins_over_user_config(tmp_path, monkeypatch) -> None:
    from ouro.core.paths import get_settings_path

    project = tmp_path / "project"
    nested = project / "Season 01"
    config_dir = tmp_path / "user-config"
    cache_dir = tmp_path / "user-cache"
    nested.mkdir(parents=True)
    project_config = project / "ouro.yaml"
    project_config.write_text("general:\n  locale: fr\n", encoding="utf-8")

    monkeypatch.chdir(nested)
    monkeypatch.delenv("OURO_CONFIG", raising=False)
    _patch_platform_dirs(monkeypatch, config_dir=config_dir, cache_dir=cache_dir)

    assert get_settings_path() == project_config


def test_configured_global_settings_path_is_used_when_no_project_file(
    tmp_path, monkeypatch
) -> None:
    from ouro.core.paths import get_settings_path, set_configured_global_settings_path

    workspace = tmp_path / "release"
    config_dir = tmp_path / "user-config"
    cache_dir = tmp_path / "user-cache"
    custom_settings = tmp_path / "custom-config" / "ouro.yaml"
    workspace.mkdir()

    monkeypatch.chdir(workspace)
    monkeypatch.delenv("OURO_CONFIG", raising=False)
    _patch_platform_dirs(monkeypatch, config_dir=config_dir, cache_dir=cache_dir)

    set_configured_global_settings_path(custom_settings)

    assert get_settings_path() == custom_settings
    assert (config_dir / "settings-path.txt").read_text(encoding="utf-8") == str(
        custom_settings.resolve()
    )


def test_existing_project_settings_file_wins_over_configured_global_path(
    tmp_path, monkeypatch
) -> None:
    from ouro.core.paths import get_settings_path, set_configured_global_settings_path

    project = tmp_path / "project"
    nested = project / "Season 01"
    config_dir = tmp_path / "user-config"
    cache_dir = tmp_path / "user-cache"
    custom_settings = tmp_path / "custom-config" / "ouro.yaml"
    nested.mkdir(parents=True)
    project_config = project / "ouro.yaml"
    project_config.write_text("general:\n  locale: fr\n", encoding="utf-8")

    monkeypatch.chdir(nested)
    monkeypatch.delenv("OURO_CONFIG", raising=False)
    _patch_platform_dirs(monkeypatch, config_dir=config_dir, cache_dir=cache_dir)

    set_configured_global_settings_path(custom_settings)

    assert get_settings_path() == project_config


def test_ouro_config_env_overrides_project_and_user_config(tmp_path, monkeypatch) -> None:
    from ouro.core.paths import get_settings_path

    workspace = tmp_path / "workspace"
    config_dir = tmp_path / "user-config"
    cache_dir = tmp_path / "user-cache"
    override = tmp_path / "explicit" / "custom.yaml"
    workspace.mkdir()
    (workspace / "ouro.yaml").write_text("general:\n  locale: fr\n", encoding="utf-8")

    monkeypatch.chdir(workspace)
    monkeypatch.setenv("OURO_CONFIG", str(override))
    _patch_platform_dirs(monkeypatch, config_dir=config_dir, cache_dir=cache_dir)

    assert get_settings_path() == override


def test_settings_store_merges_module_yaml_next_to_active_config(tmp_path, monkeypatch) -> None:
    from ouro.core.settings import SettingsStore

    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache"
    settings_file = config_dir / "ouro.yaml"
    modules_dir = config_dir / "modules"
    modules_dir.mkdir(parents=True)
    settings_file.write_text(
        "modules:\n  renamer:\n    default_language_tag: MULTI.VFF\n",
        encoding="utf-8",
    )
    (modules_dir / "renamer.yaml").write_text(
        "default_language_tag: MULTI\njunk_terms:\n  - DUAL\n",
        encoding="utf-8",
    )
    (modules_dir / "seedbox.yaml").write_text("seedboxes:\n", encoding="utf-8")

    monkeypatch.setenv("OURO_CONFIG", str(settings_file))
    _patch_platform_dirs(monkeypatch, config_dir=config_dir, cache_dir=cache_dir)

    settings = SettingsStore().load()

    assert settings["modules"]["renamer"]["default_language_tag"] == "MULTI"
    assert settings["modules"]["renamer"]["junk_terms"] == ["DUAL"]
    assert settings["seedbox"]["seedboxes"] == []
