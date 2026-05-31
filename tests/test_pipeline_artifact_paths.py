from pathlib import Path
from types import SimpleNamespace
from typing import cast

from swirrl.commands import pipeline, pipeline_orchestrator, pipeline_steps
from swirrl.core.models.nfo import ReleaseNfoData


def test_pipeline_output_folder_defaults_to_release_dir(tmp_path: Path) -> None:
    root = tmp_path / "Movie"
    root.mkdir()

    assert pipeline._pipeline_output_folder(root, root) == root / "Release"
    assert pipeline_orchestrator._pipeline_output_folder(root, root) == root / "Release"


def test_pipeline_sidecar_nfo_writes_to_output_folder(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    output_dir = tmp_path / "Release"
    mkv = media_dir / "Movie.2024.mkv"
    mkv.write_bytes(b"x")
    release = cast(ReleaseNfoData, SimpleNamespace(episodes=[SimpleNamespace(file_path=mkv)]))

    written = pipeline_steps._write_pipeline_sidecar_nfo(
        release=release,
        rendered="nfo",
        output_folder=output_dir,
        dry_run=False,
    )

    assert written == output_dir / "Movie.2024.nfo"
    assert written.read_text(encoding="utf-8") == "nfo"
    assert not mkv.with_suffix(".nfo").exists()


def test_pipeline_per_file_nfos_write_to_output_folder(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    output_dir = tmp_path / "Release"
    episode = media_dir / "Show.S01E01.mkv"
    episode.write_bytes(b"x")

    written = pipeline_steps._write_pipeline_per_file_nfos(
        [(object(), cast(ReleaseNfoData, SimpleNamespace()), "episode-nfo", episode)],
        output_dir,
    )

    assert written == [output_dir / "Show.S01E01.nfo"]
    assert written[0].read_text(encoding="utf-8") == "episode-nfo"
    assert not episode.with_suffix(".nfo").exists()
