"""Smoke tests for the pipeline command.

The pipeline module is ~3k lines orchestrating renamer/cleanmkv/nfo/torrent/
prez/encoder/upload. These tests do not try to exercise the full end-to-end
flow — they pin the *public surface* of the module so any subsequent refactor
keeps the import-level API stable:

* All step functions, helpers, presets, and the Click command are importable.
* The Click command exposes the expected option set.
* Preset discovery + loading do not crash on a missing preset directory.
* The pipeline context dataclass round-trips between fields.
* ``run_pipeline_command`` rejects an invalid path early without side effects.

Refactors of the internals (splitting the file, moving helpers into a
package, replacing the YAML emitter, etc.) must keep every assertion below
green.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import click
import pytest

from swirrl.commands import pipeline as pipeline_module
from swirrl.core.settings import DEFAULT_SETTINGS


def test_module_exports_public_surface():
    """The public callables we depend on must remain importable from the module."""
    expected_names = (
        # Click command + main entry
        "pipeline_command",
        "run_pipeline_command",
        # Step helpers (called by tests and by external pipeline runners)
        "_renamer_step",
        "_cleanmkv_step",
        "_nfo_step",
        "_torrent_step",
        "_prez_step",
        "_encoder_step",
        "_upload_step",
        # Preset discovery
        "_list_pipeline_presets",
        "_load_pipeline_preset",
        # Context dataclass
        "PipelineContext",
    )
    for name in expected_names:
        assert hasattr(pipeline_module, name), f"pipeline missing public symbol: {name}"


def test_pipeline_command_is_click_command():
    assert isinstance(pipeline_module.pipeline_command, click.Command)
    # Spot-check a few options that downstream automation relies on.
    option_names = {param.name for param in pipeline_module.pipeline_command.params}
    must_have = {
        "announce",
        "skip_renamer",
        "skip_cleanmkv",
        "skip_nfo",
        "skip_torrent",
        "skip_prez",
        "preset",
        "preview",
        "explain",
    }
    missing = must_have - option_names
    assert not missing, f"pipeline_command lost options: {missing}"


def test_list_pipeline_presets_returns_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Preset listing must not crash even when the user has no preset dir."""
    monkeypatch.chdir(tmp_path)
    presets = pipeline_module._list_pipeline_presets()
    assert isinstance(presets, list)
    for entry in presets:
        assert isinstance(entry, str)


def test_load_unknown_pipeline_preset_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    assert pipeline_module._load_pipeline_preset("definitely-not-a-real-preset") is None


def test_pipeline_context_dataclass_roundtrip():
    """``PipelineContext`` carries release + metadata state across steps."""
    ctx_class = pipeline_module.PipelineContext
    # The dataclass must be constructible with no arguments (defaults present).
    instance = ctx_class()
    # And expose the attributes that step helpers read/write.
    for attr in (
        "release",
        "metadata_context",
        "nfo_path",
        "torrent_path",
        "prez_outputs",
    ):
        assert hasattr(instance, attr), f"PipelineContext missing attribute: {attr}"


def test_run_pipeline_command_rejects_missing_path(tmp_path: Path):
    """A non-existent path must exit non-zero without writing anything."""
    missing = tmp_path / "does-not-exist"
    exit_code = pipeline_module.run_pipeline_command(
        path=str(missing),
        nfo_locale=None,
        announce=None,
        skip_renamer=True,
        skip_cleanmkv=True,
        skip_nfo=True,
        skip_torrent=True,
        skip_prez=True,
    )
    assert exit_code != 0
    # Nothing should have been created at the missing path.
    assert not missing.exists()


def test_pipeline_command_help_renders_without_crash():
    """The Click command's --help must render cleanly (catches Unicode issues)."""
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(pipeline_module.pipeline_command, ["--help"])
    # Click returns 0 for --help. Any traceback in stderr would fail this.
    assert result.exit_code == 0
    assert "pipeline" in result.output.lower() or len(result.output) > 0


@pytest.mark.parametrize(
    ("preset_name", "expected_bbcode_template"),
    [
        ("multi_fr", "detailed"),
        ("multi_en_compact", "compact"),
    ],
)
def test_load_and_apply_preset_applies_runtime_defaults_outside_auto_mode(
    preset_name: str,
    expected_bbcode_template: str,
):
    settings = deepcopy(DEFAULT_SETTINGS)
    settings["modules"]["nfo"]["active_template"] = "default"
    settings["modules"]["prez"]["html_template"] = "minimal_dark"
    settings["modules"]["prez"]["banner_design"] = "astro-gradient"

    preset_config, enabled_modules = pipeline_module._load_and_apply_preset(
        preset_name,
        False,
        settings,
        None,
    )

    assert preset_config is not None
    assert enabled_modules == tuple(preset_config["modules"])
    assert settings["modules"]["nfo"]["active_template"] == "detailed"
    assert settings["modules"]["nfo"]["mode"] == "global"
    assert settings["modules"]["prez"]["bbcode_template"] == expected_bbcode_template
    assert settings["modules"]["prez"]["html_template"] == "magazine_dark"
    assert settings["modules"]["prez"]["banner_design"] == "textual"
    assert "source" not in settings["modules"]["torrent"]
