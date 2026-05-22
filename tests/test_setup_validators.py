from __future__ import annotations

from pathlib import Path

from framekit.modules.setup.validators import validate_path


def test_validate_path_requires_value() -> None:
    ok, message = validate_path("")
    assert ok is False
    assert message


def test_validate_path_must_exist_for_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    ok, message = validate_path(str(missing), must_exist=True)
    assert ok is False
    assert "exist" in message.lower()


def test_validate_path_writable_existing_directory(tmp_path: Path) -> None:
    ok, message = validate_path(str(tmp_path), must_be_writable=True)
    assert ok is True
    assert message == ""


def test_validate_path_writable_rejects_file_when_directory_required(tmp_path: Path) -> None:
    file_path = tmp_path / "data.txt"
    file_path.write_text("x", encoding="utf-8")
    ok, message = validate_path(str(file_path), must_be_writable=True)
    assert ok is False
    assert "directory" in message.lower()


def test_validate_path_writable_rejects_when_parent_missing(tmp_path: Path) -> None:
    target = tmp_path / "missing_parent" / "child"
    ok, message = validate_path(str(target), must_be_writable=True)
    assert ok is False
    assert "parent" in message.lower()
