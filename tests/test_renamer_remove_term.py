from pathlib import Path

from framekit.modules.renamer.service import RenamerService


def test_renamer_remove_terms(tmp_path: Path) -> None:
    """
    Renamer should remove unwanted terms and clean separators in both preview and apply modes.

    This test verifies that multiple removal terms are handled case-insensitively, that
    separators left behind are collapsed correctly, and that the default language tag is
    inserted when missing. It also confirms that names remain unchanged during a dry run
    and are updated when changes are applied.
    """
    # Create sample files containing remove-term tokens in various positions and cases.
    file1 = tmp_path / "Movie.2024.DSNP.WEB-DL.mkv"
    file2 = tmp_path / "Other.DSNP-AMZN.WEB-DL.mkv"
    file1.touch()
    file2.touch()

    service = RenamerService()
    # Build rename plan with both terms to remove
    plan = service.build_plan(
        tmp_path,
        default_lang="MULTI.VFF",
        force_lang=False,
        remove_terms=("DSNP", "AMZN"),
    )
    targets = sorted(item.target.name for item in plan)
    # The remove terms should be stripped from both the stem and normalized name.
    # The language tag should be inserted at the beginning (default MULTI.VFF),
    # and remove terms should be removed entirely.
    assert targets == [
        "MULTI.VFF.MOVIE.2024.WEB-DL.mkv",
        "MULTI.VFF.OTHER.WEB-DL.mkv",
    ]

    # Dry run: ensure no files are renamed when apply_changes=False
    service.run(
        tmp_path,
        default_lang="MULTI.VFF",
        apply_changes=False,
        force_lang=False,
        remove_terms=("DSNP", "AMZN"),
    )
    names_after_dry = sorted(p.name for p in tmp_path.iterdir())
    assert names_after_dry == [
        "Movie.2024.DSNP.WEB-DL.mkv",
        "Other.DSNP-AMZN.WEB-DL.mkv",
    ]

    # Apply changes: files should be renamed on disk
    service.run(
        tmp_path,
        default_lang="MULTI.VFF",
        apply_changes=True,
        force_lang=False,
        remove_terms=("DSNP", "AMZN"),
    )
    names_after_apply = sorted(p.name for p in tmp_path.iterdir())
    assert names_after_apply == [
        "MULTI.VFF.MOVIE.2024.WEB-DL.mkv",
        "MULTI.VFF.OTHER.WEB-DL.mkv",
    ]
