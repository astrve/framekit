from pathlib import Path

from framekit.modules.nfo.template_registry import (
    NfoTemplateRecord,
    NfoTemplateRegistry,
    builtin_template_records,
    scope_matches,
)


def test_builtin_template_records():
    records = builtin_template_records()
    assert len(records) == 2
    assert records[0].display_name == "Default"
    assert records[1].display_name == "Detailed"


def test_scope_matches():
    assert scope_matches("universal", "movie") is True
    assert scope_matches("movie", "movie") is True
    assert scope_matches("movie", "season_pack") is False


def test_registry_roundtrip(tmp_path: Path):
    registry = NfoTemplateRegistry(tmp_path / "registry.json")
    record = NfoTemplateRecord(
        display_name="My Layout",
        template_name="my_layout",
        source="user",
        scope="movie",
        file_path=str((tmp_path / "Templates" / "my_layout.jinja2").resolve()),
    )

    registry.register(record)
    found = registry.find("my_layout")

    assert found is not None
    assert found.display_name == "My Layout"
    assert found.scope == "movie"
    assert found.file_path is not None
    assert found.file_path.endswith("my_layout.jinja2")
