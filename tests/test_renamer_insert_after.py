"""Tests for renamer insert-after feature - inserting terms after specific tokens."""

from pathlib import Path

from framekit.modules.renamer.service import RenamerService


def test_renamer_insert_after_basic(tmp_path: Path) -> None:
    """
    Test basic insert-after functionality: inserting a term after an existing token.
    Note: WEB-DL is normalized to WEB by the renamer's RAW_REPLACEMENTS.
    """
    # Create sample files
    file1 = tmp_path / "Movie.2024.WEB-DL.1080p.mkv"
    file2 = tmp_path / "Show.S01E01.WEB-DL.720p.mkv"
    file1.touch()
    file2.touch()

    service = RenamerService()
    # Build rename plan with insert-after: add "REPACK" after "WEB-DL"
    plan = service.build_plan(
        tmp_path,
        default_lang="MULTI.VFF",
        force_lang=False,
        insert_after_pairs=(("WEB-DL", "REPACK"),),
    )
    targets = sorted(item.target.name for item in plan)
    # The term "REPACK" should be inserted after "WEB-DL" (which becomes "WEB" after normalization)
    # Note: For episodes, language tag is placed after episode code
    assert targets == [
        "MULTI.VFF.MOVIE.2024.WEB.REPACK.1080P.mkv",
        "SHOW.S01E01.MULTI.VFF.WEB.REPACK.720P.mkv",
    ]


def test_renamer_insert_after_multiple(tmp_path: Path) -> None:
    """Test inserting multiple terms after different tokens."""
    file1 = tmp_path / "Movie.2024.WEB-DL.1080p.H264.mkv"
    file1.touch()

    service = RenamerService()
    # Insert "REPACK" after "WEB-DL" and "10bit" after "H264"
    plan = service.build_plan(
        tmp_path,
        default_lang="MULTI.VFF",
        force_lang=False,
        insert_after_pairs=(("WEB-DL", "REPACK"), ("H264", "10bit")),
    )
    targets = [item.target.name for item in plan]
    # Both insertions should work, and inserted terms are uppercased during normalization
    assert targets == ["MULTI.VFF.MOVIE.2024.WEB.REPACK.1080P.H264.10BIT.mkv"]


def test_renamer_insert_after_token_not_found(tmp_path: Path, capsys) -> None:
    """Test that a warning is displayed when the token to insert after is not found."""
    file1 = tmp_path / "Movie.2024.WEB-DL.1080p.mkv"
    file1.touch()

    service = RenamerService()
    # Try to insert after a token that doesn't exist
    plan = service.build_plan(
        tmp_path,
        default_lang="MULTI.VFF",
        force_lang=False,
        insert_after_pairs=(("BLURAY", "REPACK"),),
    )

    # The plan should still be created, but without the insertion
    targets = [item.target.name for item in plan]
    # WEB-DL normalizes to WEB
    assert targets == ["MULTI.VFF.MOVIE.2024.WEB.1080P.mkv"]

    # Check that a warning was printed
    captured = capsys.readouterr()
    assert "BLURAY" in captured.out or "BLURAY" in captured.err


def test_renamer_insert_after_case_insensitive(tmp_path: Path) -> None:
    """Test that insert-after works case-insensitively."""
    file1 = tmp_path / "Movie.2024.web-dl.1080p.mkv"
    file1.touch()

    service = RenamerService()
    # Use uppercase "WEB-DL" to match lowercase "web-dl"
    plan = service.build_plan(
        tmp_path,
        default_lang="MULTI.VFF",
        force_lang=False,
        insert_after_pairs=(("WEB-DL", "REPACK"),),
    )
    targets = [item.target.name for item in plan]
    # WEB-DL normalizes to WEB
    assert targets == ["MULTI.VFF.MOVIE.2024.WEB.REPACK.1080P.mkv"]


def test_renamer_insert_after_with_remove_terms(tmp_path: Path) -> None:
    """Test that insert-after works together with remove-terms."""
    file1 = tmp_path / "Movie.2024.DSNP.WEB-DL.1080p.mkv"
    file1.touch()

    service = RenamerService()
    # Remove "DSNP" and insert "REPACK" after "WEB-DL"
    plan = service.build_plan(
        tmp_path,
        default_lang="MULTI.VFF",
        force_lang=False,
        remove_terms=("DSNP",),
        insert_after_pairs=(("WEB-DL", "REPACK"),),
    )
    targets = [item.target.name for item in plan]
    # DSNP should be removed, REPACK should be inserted after WEB-DL (which becomes WEB)
    assert targets == ["MULTI.VFF.MOVIE.2024.WEB.REPACK.1080P.mkv"]


def test_renamer_insert_after_apply_changes(tmp_path: Path) -> None:
    """Test that insert-after actually renames files when apply_changes=True."""
    file1 = tmp_path / "Movie.2024.WEB-DL.1080p.mkv"
    file1.touch()

    service = RenamerService()

    # Dry run first
    service.run(
        tmp_path,
        default_lang="MULTI.VFF",
        apply_changes=False,
        force_lang=False,
        insert_after_pairs=(("WEB-DL", "REPACK"),),
    )
    names_after_dry = sorted(p.name for p in tmp_path.iterdir())
    assert names_after_dry == ["Movie.2024.WEB-DL.1080p.mkv"]

    # Apply changes
    service.run(
        tmp_path,
        default_lang="MULTI.VFF",
        apply_changes=True,
        force_lang=False,
        insert_after_pairs=(("WEB-DL", "REPACK"),),
    )
    names_after_apply = sorted(p.name for p in tmp_path.iterdir())
    # WEB-DL normalizes to WEB
    assert names_after_apply == ["MULTI.VFF.MOVIE.2024.WEB.REPACK.1080P.mkv"]


def test_renamer_insert_after_first_occurrence_only(tmp_path: Path) -> None:
    """Test that insert-after only inserts after the first occurrence of the token."""
    file1 = tmp_path / "Movie.H264.2024.H264.mkv"
    file1.touch()

    service = RenamerService()
    plan = service.build_plan(
        tmp_path,
        default_lang="MULTI.VFF",
        force_lang=False,
        insert_after_pairs=(("H264", "10bit"),),
    )
    targets = [item.target.name for item in plan]
    # Should only insert after the first H264, and 10bit is uppercased during normalization
    assert targets == ["MULTI.VFF.MOVIE.H264.10BIT.2024.H264.mkv"]
