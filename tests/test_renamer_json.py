"""Tests for ``swirrl renamer --json`` structured output (P7).

The renamer dry-run path is pure filename parsing, so these tests need only
synthetic empty ``.mkv`` files — no mkvmerge/ffmpeg.
"""

from __future__ import annotations

import json
from pathlib import Path

from swirrl.commands.renamer import run_renamer_command


def test_renamer_json_emits_pure_json_report(tmp_path: Path, capsys):
    (tmp_path / "Some.Movie.2020.1080p.BluRay.x264-GRP.mkv").touch()
    (tmp_path / "Another.Show.S01E01.720p.WEB.h264-TEAM.mkv").touch()

    code = run_renamer_command(
        path=str(tmp_path),
        lang=None,
        apply_changes=False,
        dry_run=True,
        force_lang=False,
        json_output=True,
    )
    assert code == 0

    out = capsys.readouterr().out.strip()
    # Entire stdout must be a single JSON object (web job runner contract).
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["tool"] == "renamer"
    assert payload["applied"] is False
    assert payload["scanned"] == 2
    assert len(payload["files"]) == 2
    for entry in payload["files"]:
        assert {"file", "status", "before", "after"} <= set(entry)
    # Files are unchanged on disk in dry-run mode.
    assert (tmp_path / "Some.Movie.2020.1080p.BluRay.x264-GRP.mkv").exists()


def test_renamer_json_missing_path_reports_error(tmp_path: Path, capsys):
    missing = tmp_path / "does-not-exist"
    code = run_renamer_command(
        path=str(missing),
        lang=None,
        apply_changes=False,
        dry_run=True,
        force_lang=False,
        json_output=True,
    )
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)  # still pure JSON on failure
    assert payload["ok"] is False
    assert code != 0
