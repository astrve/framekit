from __future__ import annotations

from click.testing import CliRunner

from ouro.commands.main import cli


def _compact_output(value: str) -> str:
    return " ".join(value.split())


def test_rename_parent_derives_library_name_from_nested_release(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "ouro.yaml"
    monkeypatch.setenv("OURO_CONFIG", str(settings_file))

    container = tmp_path / "Dirty.Parent"
    final = container / "Release" / "EYE.FOR.AN.EYE.1996.MULTI.VFF.1080P.WEB.AAC.2.0.x264-ACKER"
    final.mkdir(parents=True)
    (final / "EYE.FOR.AN.EYE.1996.MULTI.VFF.1080P.WEB.AAC.2.0.x264-ACKER.mkv").write_bytes(b"mkv")
    (final / "EYE.FOR.AN.EYE.1996.MULTI.VFF.1080P.WEB.AAC.2.0.x264-ACKER.nfo").write_text(
        "nfo",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["rename-parent", str(container)])

    assert result.exit_code == 0
    assert "Eye For An Eye (1996) - 1080p WEB" in _compact_output(result.output)
    assert not container.exists()
    assert (tmp_path / "Eye For An Eye (1996) - 1080p WEB").exists()


def test_rename_parent_processes_children_when_given_batch_parent(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "ouro.yaml"
    monkeypatch.setenv("OURO_CONFIG", str(settings_file))

    batch = tmp_path / "batch"
    first = batch / "first"
    second = batch / "second"
    for container, stem in (
        (first, "FIRST.MOVIE.2020.720P.WEB-GRP"),
        (second, "SECOND.MOVIE.2021.1080P.BLURAY-GRP"),
    ):
        final = container / "Release" / stem
        final.mkdir(parents=True)
        (final / f"{stem}.mkv").write_bytes(b"mkv")
        (final / f"{stem}.nfo").write_text("nfo", encoding="utf-8")

    result = CliRunner().invoke(cli, ["rename-parent", str(batch)])

    assert result.exit_code == 0
    output = _compact_output(result.output)
    assert "First Movie (2020) - 720p WEB" in output
    assert "Second Movie (2021) - 1080p BluRay" in output
    assert not first.exists()
    assert not second.exists()
    assert (batch / "First Movie (2020) - 720p WEB").exists()
    assert (batch / "Second Movie (2021) - 1080p BluRay").exists()


def test_rename_parent_dry_run_keeps_folder_unchanged(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "ouro.yaml"
    monkeypatch.setenv("OURO_CONFIG", str(settings_file))

    container = tmp_path / "Dirty.Parent"
    final = container / "Release" / "EYE.FOR.AN.EYE.1996.MULTI.VFF.1080P.WEB.AAC.2.0.x264-ACKER"
    final.mkdir(parents=True)
    (final / "EYE.FOR.AN.EYE.1996.MULTI.VFF.1080P.WEB.AAC.2.0.x264-ACKER.mkv").write_bytes(b"mkv")
    (final / "EYE.FOR.AN.EYE.1996.MULTI.VFF.1080P.WEB.AAC.2.0.x264-ACKER.nfo").write_text(
        "nfo",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["rename-parent", str(container), "--dry-run"])

    assert result.exit_code == 0
    assert "would be renamed" in result.output
    assert container.exists()
    assert not (tmp_path / "Eye For An Eye (1996) - 1080p WEB").exists()
