"""Migration and round-trip tests for the settings schema.

Pins the v11 → v12 migration: removed keys (``ssl_cert_pins``,
``general.path_resolution_mode``, ``general.export_json_reports``,
``general.dry_run_by_default``, ``metadata.tmdb_api_key``) must disappear, and
``SettingsStore`` round-trips must preserve a stable, normalised shape.
"""

from __future__ import annotations

from pathlib import Path

from framekit.core.settings import (
    DEFAULT_SETTINGS,
    SETTINGS_SCHEMA_VERSION,
    SettingsStore,
    _migrate_legacy_settings,
    normalize_settings,
)


def test_schema_version_is_v14() -> None:
    assert SETTINGS_SCHEMA_VERSION == 14
    assert DEFAULT_SETTINGS["schema_version"] == 14


def test_default_settings_no_longer_carry_removed_keys() -> None:
    general = DEFAULT_SETTINGS["general"]
    assert "path_resolution_mode" not in general
    assert "export_json_reports" not in general
    assert "dry_run_by_default" not in general

    metadata = DEFAULT_SETTINGS["metadata"]
    assert "tmdb_api_key" not in metadata
    assert "tmdb_read_access_token" in metadata


def test_migrate_v11_strips_removed_general_keys() -> None:
    legacy = {
        "schema_version": 11,
        "general": {
            "locale": "en",
            "path_resolution_mode": "module_last_then_module_default_then_global_then_cwd",
            "export_json_reports": True,
            "dry_run_by_default": True,
        },
        "metadata": {"provider": "tmdb"},
    }

    migrated = _migrate_legacy_settings(legacy)

    assert migrated["schema_version"] == 14
    assert "path_resolution_mode" not in migrated["general"]
    assert "export_json_reports" not in migrated["general"]
    assert "dry_run_by_default" not in migrated["general"]
    assert migrated["general"]["locale"] == "en"


def test_migrate_v11_drops_legacy_tmdb_api_key() -> None:
    legacy = {
        "schema_version": 11,
        "metadata": {
            "provider": "tmdb",
            "tmdb_api_key": "deadbeefdeadbeefdeadbeefdeadbeef",
            "tmdb_read_access_token": "",
        },
    }

    migrated = _migrate_legacy_settings(legacy)

    assert "tmdb_api_key" not in migrated["metadata"]
    assert migrated["metadata"]["tmdb_read_access_token"] == ""


def test_migrate_keeps_existing_read_access_token() -> None:
    legacy = {
        "schema_version": 11,
        "metadata": {
            "provider": "tmdb",
            "tmdb_api_key": "old_key",
            "tmdb_read_access_token": "eyJ.test.token",
        },
    }
    migrated = _migrate_legacy_settings(legacy)
    assert "tmdb_api_key" not in migrated["metadata"]
    assert migrated["metadata"]["tmdb_read_access_token"] == "eyJ.test.token"


def test_normalize_pipeline_defaults_stop_on_error_false() -> None:
    normalized = normalize_settings({})
    assert normalized["modules"]["pipeline"]["stop_on_error"] is False


def test_store_round_trip_preserves_schema(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "framekit.yaml")
    data = store.load()
    assert data["schema_version"] == 14
    assert "tmdb_api_key" not in data["metadata"]
    assert "path_resolution_mode" not in data["general"]

    data["metadata"]["tmdb_read_access_token"] = "eyJabc.def.ghi"
    store.save(data)
    reloaded = store.load()
    assert reloaded["metadata"]["tmdb_read_access_token"] == "eyJabc.def.ghi"
    assert reloaded["schema_version"] == 14


def test_store_creates_file_with_default_content(tmp_path: Path) -> None:
    yaml_path = tmp_path / "framekit.yaml"
    store = SettingsStore(yaml_path)
    store.ensure_exists()
    assert yaml_path.exists()
    text = yaml_path.read_text(encoding="utf-8")
    assert "schema_version: 14" in text
    assert "tmdb_api_key" not in text
    assert "path_resolution_mode" not in text


def test_plugins_allowlist_defaults_to_empty() -> None:
    assert DEFAULT_SETTINGS["plugins"]["allowed"] == []
