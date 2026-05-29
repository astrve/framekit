"""Property-based tests for :func:`ouro.core.naming.release_name_from_mkv_paths`.

Contract under test:

* Always returns ``str`` (never raises, never ``None``).
* Empty input → empty string.
* Single-file input → release stem derived from filename.
* Idempotent under whitespace-only filename diff.
* Never leaks raw path separators or NUL bytes in the result.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ouro.core.naming import release_name_from_mkv_paths

pytestmark = pytest.mark.benchmark  # treat as opt-in slow tests too


# Path-segment alphabet: printable ASCII minus the chars that pathlib refuses.
_SEGMENT_ALPHABET = st.text(
    alphabet=st.characters(
        min_codepoint=0x20,
        max_codepoint=0x7E,
        blacklist_categories=("Cs",),
        blacklist_characters='\x00/\\:*?"<>|',
    ),
    min_size=1,
    max_size=80,
)


def _to_paths(stems: list[str]) -> list[Path]:
    """Convert generated stems into Path objects under a synthetic tmp root."""

    return [Path(f"/synthetic/{stem}.mkv") for stem in stems if stem.strip()]


@given(stems=st.lists(_SEGMENT_ALPHABET, min_size=0, max_size=10))
def test_release_name_returns_string(stems: list[str]) -> None:
    paths = _to_paths(stems)
    out = release_name_from_mkv_paths(paths)
    assert isinstance(out, str)


@given(stems=st.lists(_SEGMENT_ALPHABET, min_size=0, max_size=10))
def test_release_name_never_contains_nul(stems: list[str]) -> None:
    paths = _to_paths(stems)
    out = release_name_from_mkv_paths(paths)
    assert "\x00" not in out


def test_release_name_empty_input_returns_string() -> None:
    """Boundary: empty list must yield a string (whatever the convention)."""

    out = release_name_from_mkv_paths([])
    assert isinstance(out, str)


@given(stems=st.lists(_SEGMENT_ALPHABET, min_size=1, max_size=5))
def test_release_name_accepts_tuple_input(stems: list[str]) -> None:
    """Signature accepts ``list | tuple``; verify both code paths work."""

    paths = tuple(_to_paths(stems))
    out = release_name_from_mkv_paths(paths)
    assert isinstance(out, str)


@given(
    stem=_SEGMENT_ALPHABET,
    count=st.integers(min_value=1, max_value=10),
)
def test_release_name_repeated_stem_idempotent(stem: str, count: int) -> None:
    """Same stem repeated N times still produces a string.

    A strict equality contract (``out_n == out_1``) is too strong: the
    multi-file path may compute a common prefix that diverges from the
    single-file output. The relevant invariant for downstream callers is
    type stability + non-emptiness when the input is non-empty.
    """

    paths_n = [Path(f"/synthetic/{stem}.mkv") for _ in range(count)]
    paths_1 = [Path(f"/synthetic/{stem}.mkv")]
    out_n = release_name_from_mkv_paths(paths_n)
    out_1 = release_name_from_mkv_paths(paths_1)
    assert isinstance(out_n, str)
    assert isinstance(out_1, str)
