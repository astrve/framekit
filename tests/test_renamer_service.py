from __future__ import annotations

from framekit.core.models.renamer import RenamePlanItem
from framekit.modules.renamer import service as renamer_service


def test_renamer_service_reports_planned_collision_and_unchanged(monkeypatch, tmp_path):
    source = tmp_path / "old.mkv"
    target = tmp_path / "new.mkv"
    unchanged = tmp_path / "same.mkv"
    conflict = tmp_path / "conflict.mkv"
    for path in (source, unchanged, conflict):
        path.write_bytes(b"x")

    plan = [
        RenamePlanItem(source=source, target=target, reason="normalized", changed=True),
        RenamePlanItem(source=unchanged, target=unchanged, reason="normalized", changed=False),
        RenamePlanItem(
            source=conflict,
            target=tmp_path / "taken.mkv",
            reason="normalized",
            changed=True,
            collision=True,
        ),
    ]

    monkeypatch.setattr(renamer_service, "build_rename_plan", lambda *args, **kwargs: plan)

    report = renamer_service.RenamerService().run(
        tmp_path,
        default_lang="MULTI.VFF",
        apply_changes=False,
        force_lang=False,
    )

    assert report.scanned == 3
    assert report.processed == 3
    assert report.modified == 1
    assert report.skipped == 2
    assert [detail.status for detail in report.details] == ["planned", "unchanged", "collision"]
    assert source.exists()
    assert not target.exists()
    assert report.errors[0].code == "rename_collision"


def test_renamer_service_applies_regular_rename(monkeypatch, tmp_path):
    source = tmp_path / "old.mkv"
    target = tmp_path / "new.mkv"
    source.write_bytes(b"x")
    plan = [RenamePlanItem(source=source, target=target, reason="normalized", changed=True)]

    monkeypatch.setattr(renamer_service, "build_rename_plan", lambda *args, **kwargs: plan)

    report = renamer_service.RenamerService().run(
        tmp_path,
        default_lang="MULTI.VFF",
        apply_changes=True,
        force_lang=False,
    )

    assert report.modified == 1
    assert report.details[0].status == "renamed"
    assert not source.exists()
    assert target.read_bytes() == b"x"


def test_renamer_service_passes_remove_terms_to_planner(monkeypatch, tmp_path):
    source = tmp_path / "Movie.DSNP.mkv"
    target = tmp_path / "Movie.mkv"
    source.write_bytes(b"x")

    captured = {}

    def fake_build(folder, **kwargs):
        captured["remove_terms"] = kwargs["remove_terms"]
        return [RenamePlanItem(source=source, target=target, reason="normalized", changed=True)]

    monkeypatch.setattr(renamer_service, "build_rename_plan", fake_build)

    report = renamer_service.RenamerService().run(
        tmp_path,
        default_lang="MULTI.VFF",
        apply_changes=False,
        force_lang=False,
        remove_terms=("DSNP",),
    )

    assert captured["remove_terms"] == ("DSNP",)
    assert report.details[0].after["name"] == "Movie.mkv"
