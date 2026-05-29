"""Tests for NFO logo registry - logo management and storage."""

from pathlib import Path

from ouro.modules.nfo.logo_registry import NfoLogoRecord, NfoLogoRegistry


def test_logo_registry_roundtrip(tmp_path: Path):
    """Test that logos can be registered and retrieved from the registry."""
    registry = NfoLogoRegistry(tmp_path / "registry.json")

    record = NfoLogoRecord(
        display_name="My Logo",
        logo_name="my_logo",
        file_path=str((tmp_path / "my_logo.txt").resolve()),
    )

    registry.register(record)
    found = registry.find("my_logo")

    assert found is not None
    assert found.display_name == "My Logo"
    assert found.logo_name == "my_logo"
